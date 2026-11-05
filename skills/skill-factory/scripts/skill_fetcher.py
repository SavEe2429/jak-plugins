#!/usr/bin/env python3
"""
skill_fetcher.py - Targeted single-skill fetcher with upstream provenance verification.
Part of the 'skill-factory' meta-skill.

What it does (and what it actually proves):
1. Targeted fetch: installs ONLY the requested skill directory, never the whole bundle.
2. Pinned source: resolves the requested ref to an immutable commit SHA and downloads
   every file from that exact commit (no branch race between metadata and content).
3. Upstream content verification: each downloaded file is hashed as a Git blob
   (sha1("blob <len>\\0" + bytes)) and compared with the blob SHA listed in GitHub's
   tree for that commit. A mismatch aborts the install.
4. Stage -> scan -> install: files are written to a staging directory, scanned with
   the local AST security scanner, and moved into the skills directory only if the
   scan is CLEAN (or the user explicitly passes --accept-findings).
5. Path containment: every repository-supplied path is resolved and must stay inside
   the destination directory.
6. Re-verification (--verify): checks local files against the provenance record,
   re-downloads the pinned files to detect a rewritten provenance record, confirms the
   file list against the pinned tree, and optionally reports newer upstream commits.

Limits (stated honestly):
- The trust root is GitHub over TLS plus the recorded repository/commit. If someone
  rewrites the provenance record to point at a different repository, verification
  proves consistency with THAT repository; the source repository is always printed so
  a human can confirm it.
- A static scan is not a runtime guarantee.

Free usage: unauthenticated GitHub REST API allows 60 requests/hour. Fetch uses 2 API
calls, --verify uses up to 3 (0 with --offline). Raw file downloads go through
raw.githubusercontent.com and do not consume REST API quota. Set GITHUB_TOKEN
(free personal access token) to raise the limit to 5,000/hour.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional

for _stream in (sys.stdout, sys.stderr):
    if _stream.encoding and _stream.encoding.lower() != "utf-8":
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from security_scanner import scan_skill_directory
except Exception:  # pragma: no cover - scanner is shipped alongside this script
    scan_skill_directory = None

PROVENANCE_FILE = ".provenance.json"
SCHEMA_VERSION = "2.0.0"
USER_AGENT = "skill-factory-skill-fetcher"
MAX_FILES = 200
MAX_FILE_BYTES = 2 * 1024 * 1024
TIMEOUT = 20


class FetchError(Exception):
    """Raised for any condition that must abort a fetch or verification."""


# --------------------------------------------------------------------------- hashing


def git_blob_sha1(data: bytes) -> str:
    """Git object id of a blob: sha1(b'blob <len>\\0' + data)."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------- paths


def safe_join(base: Path, rel: str) -> Path:
    """Join a repository-supplied relative POSIX path under base, rejecting escapes."""
    pure = PurePosixPath(rel)
    if not rel or pure.is_absolute() or ".." in pure.parts or "\\" in rel or ":" in rel:
        raise FetchError(f"Unsafe path from repository rejected: {rel!r}")
    base_resolved = base.resolve()
    target = (base_resolved / Path(*pure.parts)).resolve()
    try:
        target.relative_to(base_resolved)
    except ValueError:
        raise FetchError(f"Path escapes destination directory: {rel!r}") from None
    return target


def list_local_files(skill_dir: Path) -> List[str]:
    files = []
    for p in skill_dir.rglob("*"):
        if p.is_file() and p.name != PROVENANCE_FILE and "__pycache__" not in p.parts:
            files.append(p.relative_to(skill_dir).as_posix())
    return sorted(files)


# --------------------------------------------------------------------------- network


def _http_get(url: str, accept: Optional[str] = None, api: bool = False) -> bytes:
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    token = os.environ.get("GITHUB_TOKEN")
    if api and token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = resp.read(MAX_FILE_BYTES + 1)
            if len(data) > MAX_FILE_BYTES and not api:
                raise FetchError(f"File exceeds {MAX_FILE_BYTES} bytes: {url}")
            return data
    except urllib.error.HTTPError as e:
        if e.code in (403, 429) and e.headers.get("X-RateLimit-Remaining") == "0":
            raise FetchError(
                "GitHub API rate limit reached (60/hour unauthenticated). "
                "Wait for the reset or set a free GITHUB_TOKEN."
            ) from None
        raise FetchError(f"HTTP {e.code} for {url}") from None
    except urllib.error.URLError as e:
        raise FetchError(f"Network error for {url}: {e.reason}") from None


def resolve_commit(repo: str, ref: str) -> str:
    """Resolve a branch/tag/HEAD to an immutable 40-char commit SHA (1 API call)."""
    url = f"https://api.github.com/repos/{repo}/commits/{urllib.parse.quote(ref, safe='')}"
    sha = _http_get(url, accept="application/vnd.github.sha", api=True).decode().strip()
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise FetchError(f"Could not resolve ref {ref!r} to a commit SHA")
    return sha


def get_tree(repo: str, commit: str) -> List[Dict[str, Any]]:
    """Recursive tree listing for a commit (1 API call)."""
    url = f"https://api.github.com/repos/{repo}/git/trees/{commit}?recursive=1"
    data = json.loads(_http_get(url, accept="application/vnd.github+json", api=True))
    if data.get("truncated"):
        raise FetchError("Repository tree is too large and was truncated by GitHub; cannot verify the file list.")
    return data.get("tree", [])


def download_pinned(repo: str, commit: str, path: str) -> bytes:
    """Download raw bytes at a pinned commit via CDN (no REST API quota)."""
    url = f"https://raw.githubusercontent.com/{repo}/{commit}/{urllib.parse.quote(path)}"
    return _http_get(url)


# --------------------------------------------------------------------------- tree helpers


def find_skill_dir(tree: List[Dict[str, Any]], skill_name: str, explicit_path: Optional[str]) -> str:
    skill_dirs = [
        item["path"][: -len("/SKILL.md")]
        for item in tree
        if item.get("type") == "blob" and item.get("path", "").endswith("/SKILL.md")
    ]
    if explicit_path:
        explicit_path = explicit_path.strip("/")
        if explicit_path not in skill_dirs:
            raise FetchError(f"No SKILL.md at {explicit_path!r} in this commit")
        return explicit_path
    matches = [d for d in skill_dirs if d.rsplit("/", 1)[-1].lower() == skill_name.lower()]
    if not matches:
        raise FetchError(f"Skill {skill_name!r} not found (no <dir>/{skill_name}/SKILL.md)")
    if len(matches) > 1:
        raise FetchError(f"Ambiguous skill name; candidates: {matches}. Re-run with --path.")
    return matches[0]


def files_under(tree: List[Dict[str, Any]], skill_path: str) -> List[Dict[str, Any]]:
    prefix = skill_path + "/"
    files = [
        {"path": item["path"][len(prefix):], "repo_path": item["path"], "git_blob_sha": item["sha"],
         "size": item.get("size", 0)}
        for item in tree
        if item.get("type") == "blob" and item.get("path", "").startswith(prefix)
    ]
    if len(files) > MAX_FILES:
        raise FetchError(f"Skill has {len(files)} files (limit {MAX_FILES}); refusing.")
    for f in files:
        if f["size"] > MAX_FILE_BYTES:
            raise FetchError(f"File too large: {f['path']} ({f['size']} bytes)")
    return files


# --------------------------------------------------------------------------- fetch


def _scan(directory: Path) -> Dict[str, Any]:
    if scan_skill_directory is None:
        return {"status": "SCANNER_UNAVAILABLE", "findings": []}
    r = scan_skill_directory(directory)
    return {
        "status": r.get("status", "UNKNOWN"),
        "critical_count": r.get("critical_count", 0),
        "high_count": r.get("high_count", 0),
        "findings": r.get("findings", []),
    }


def fetch_skill(
    repo: str,
    skill_name: str,
    target_dir: Path,
    ref: str = "HEAD",
    explicit_path: Optional[str] = None,
    dry_run: bool = False,
    force: bool = False,
    accept_findings: bool = False,
) -> Dict[str, Any]:
    target_dir = target_dir.resolve()
    dest = safe_join(target_dir, skill_name)
    if dest.exists() and not force and not dry_run:
        raise FetchError(f"{dest} already exists. Use --verify, or --force to replace (a backup is kept).")

    commit = resolve_commit(repo, ref)
    tree = get_tree(repo, commit)
    skill_path = find_skill_dir(tree, skill_name, explicit_path)
    files = files_under(tree, skill_path)

    staging_root = Path(tempfile.mkdtemp(prefix="skill-fetch-"))
    staging = staging_root / skill_name
    staging.mkdir()
    try:
        records = []
        for f in files:
            out = safe_join(staging, f["path"])
            data = download_pinned(repo, commit, f["repo_path"])
            actual = git_blob_sha1(data)
            if actual != f["git_blob_sha"]:
                raise FetchError(
                    f"Content mismatch for {f['path']}: upstream blob {f['git_blob_sha']}, got {actual}"
                )
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
            records.append({"path": f["path"], "git_blob_sha": actual, "sha256": sha256_hex(data),
                            "size": len(data)})

        scan = _scan(staging)
        blocked = scan["status"] != "CLEAN"
        provenance = {
            "schema_version": SCHEMA_VERSION,
            "skill_name": skill_name,
            "source_repository": f"https://github.com/{repo}",
            "requested_ref": ref,
            "pinned_commit": commit,
            "skill_path": skill_path,
            "files": sorted(records, key=lambda r: r["path"]),
            "verification": "GIT_BLOB_SHA1_MATCH_AT_PINNED_COMMIT",
            "security_scan": {k: v for k, v in scan.items() if k != "findings"},
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        result = {"status": "VERIFIED", "target_path": str(dest), "provenance": provenance,
                  "scan_findings": scan["findings"]}

        if blocked and not accept_findings:
            result["status"] = "BLOCKED_BY_SCAN"
            return result
        if dry_run:
            result["status"] = "VERIFIED_DRY_RUN"
            return result

        (staging / PROVENANCE_FILE).write_text(
            json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        backup = None
        if dest.exists():
            stamp = datetime.now().strftime("%Y%m%d%H%M%S")
            backup = target_dir.parent / f".skill-backup-{skill_name}-{stamp}"
            shutil.move(str(dest), str(backup))
        try:
            shutil.move(str(staging), str(dest))
        except Exception:
            if backup is not None and not dest.exists():
                shutil.move(str(backup), str(dest))
            raise
        result["status"] = "INSTALLED"
        result["backup"] = str(backup) if backup else None
        return result
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)


# --------------------------------------------------------------------------- verify


def verify_installed_skill(skill_dir: Path, offline: bool = False, check_upstream: bool = True) -> Dict[str, Any]:
    prov_path = skill_dir / PROVENANCE_FILE
    if not skill_dir.is_dir():
        return {"status": "ERROR", "problems": [f"{skill_dir} does not exist"]}
    if not prov_path.exists():
        return {"status": "UNVERIFIED", "problems": ["No provenance record; skill was added manually."]}
    try:
        prov = json.loads(prov_path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"status": "ERROR", "problems": [f"Corrupt provenance record: {e}"]}
    if prov.get("schema_version") != SCHEMA_VERSION or "files" not in prov:
        return {"status": "LEGACY_PROVENANCE",
                "problems": ["Provenance record predates content verification; re-fetch with --force."]}

    problems: List[str] = []
    recorded = {f["path"]: f for f in prov["files"]}

    # 1. Local files vs record (modified, deleted, or added files)
    local = set(list_local_files(skill_dir))
    for rel in sorted(set(recorded) - local):
        problems.append(f"deleted: {rel}")
    for rel in sorted(local - set(recorded)):
        problems.append(f"added (not in upstream record): {rel}")
    for rel in sorted(local & set(recorded)):
        data = safe_join(skill_dir, rel).read_bytes()
        if git_blob_sha1(data) != recorded[rel]["git_blob_sha"]:
            problems.append(f"modified: {rel}")
    local_ok = not problems

    result: Dict[str, Any] = {
        "skill_name": prov.get("skill_name"),
        "source_repository": prov.get("source_repository"),
        "skill_path": prov.get("skill_path"),
        "pinned_commit": prov.get("pinned_commit"),
        "local_ok": local_ok,
        "record_ok": None,
        "upstream_latest_commit": None,
        "upstream_changed_files": None,
    }
    if not local_ok:
        result.update(status="LOCALLY_MODIFIED", problems=problems)
        return result
    if offline:
        result.update(status="LOCAL_MATCHES_RECORD_ONLY", problems=[
            "Offline mode: the provenance record itself was not checked against upstream."])
        return result

    # 2. Record vs pinned upstream (detects a rewritten provenance record)
    repo = prov["source_repository"].replace("https://github.com/", "").strip("/")
    commit, skill_path = prov["pinned_commit"], prov["skill_path"]
    try:
        pinned_files = {f["path"]: f for f in files_under(get_tree(repo, commit), skill_path)}
        if set(pinned_files) != set(recorded):
            problems.append("file list differs from upstream tree at pinned commit")
        for rel, rec in recorded.items():
            up = pinned_files.get(rel)
            if up and up["git_blob_sha"] != rec["git_blob_sha"]:
                problems.append(f"record mismatch vs upstream: {rel}")
        for rel in sorted(set(recorded) & set(pinned_files)):
            data = download_pinned(repo, commit, pinned_files[rel]["repo_path"])
            if git_blob_sha1(data) != pinned_files[rel]["git_blob_sha"]:
                problems.append(f"upstream served unexpected content: {rel}")
    except FetchError as e:
        result.update(status="ERROR", problems=[str(e)])
        return result
    result["record_ok"] = not problems
    if problems:
        result.update(status="PROVENANCE_MISMATCH", problems=problems)
        return result

    # 3. Optional: newer upstream commits touching this skill
    status = "VERIFIED"
    if check_upstream:
        try:
            latest = resolve_commit(repo, prov.get("requested_ref") or "HEAD")
            result["upstream_latest_commit"] = latest
            if latest != commit:
                latest_files = {f["path"]: f["git_blob_sha"] for f in files_under(get_tree(repo, latest), skill_path)}
                changed = sorted(
                    p for p in set(latest_files) | set(recorded)
                    if latest_files.get(p) != recorded.get(p, {}).get("git_blob_sha")
                )
                result["upstream_changed_files"] = changed
                if changed:
                    status = "VERIFIED_UPSTREAM_UPDATED"
            else:
                result["upstream_changed_files"] = []
        except FetchError as e:
            problems.append(f"upstream update check skipped: {e}")
    result.update(status=status, problems=problems)
    return result


# --------------------------------------------------------------------------- CLI


def _print_fetch(res: Dict[str, Any]) -> None:
    prov = res["provenance"]
    print("=" * 78)
    print(" TARGETED SKILL FETCH - UPSTREAM CONTENT VERIFICATION")
    print("=" * 78)
    print(f"Status            : {res['status']}")
    print(f"Skill             : {prov['skill_name']}  ->  {res['target_path']}")
    print(f"Source            : {prov['source_repository']}  /  {prov['skill_path']}")
    print(f"Pinned commit     : {prov['pinned_commit']}  (requested ref: {prov['requested_ref']})")
    print(f"Files verified    : {len(prov['files'])} (git blob SHA-1 matched upstream tree)")
    for f in prov["files"]:
        print(f"   {f['git_blob_sha'][:12]}  {f['path']}")
    print(f"Security scan     : {prov['security_scan'].get('status')}")
    for finding in res.get("scan_findings", [])[:10]:
        print(f"   ! {finding}")
    if res.get("backup"):
        print(f"Previous version  : backed up to {res['backup']}")
    if res["status"] == "BLOCKED_BY_SCAN":
        print("Nothing was installed. Review findings; re-run with --accept-findings to override.")
    elif res["status"] == "VERIFIED_DRY_RUN":
        print("Dry run: nothing was written.")
    print("=" * 78)


def _print_verify(res: Dict[str, Any]) -> None:
    print("=" * 78)
    print(" INSTALLED SKILL VERIFICATION")
    print("=" * 78)
    print(f"Status            : {res['status']}")
    for key in ("skill_name", "source_repository", "skill_path", "pinned_commit",
                "local_ok", "record_ok", "upstream_latest_commit", "upstream_changed_files"):
        if key in res:
            print(f"{key:18s}: {res[key]}")
    for p in res.get("problems", []):
        print(f"   - {p}")
    print("=" * 78)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--repo", "-r", help="GitHub repository owner/name (e.g. mattpocock/skills)")
    parser.add_argument("--skill", "-s", help="Skill directory name to fetch (e.g. tdd)")
    parser.add_argument("--path", help="Exact skill directory path in the repo (disambiguates duplicates)")
    parser.add_argument("--ref", default="HEAD", help="Branch, tag, or commit to pin (default: default branch)")
    parser.add_argument("--target-dir", "-t", default=".agents/skills", help="Skills directory")
    parser.add_argument("--dry-run", action="store_true", help="Download, verify, and scan without installing")
    parser.add_argument("--force", action="store_true", help="Replace an existing install (keeps a backup)")
    parser.add_argument("--accept-findings", action="store_true", help="Install even if the scan is not CLEAN")
    parser.add_argument("--verify", metavar="SKILL", help="Verify an installed skill (name or directory)")
    parser.add_argument("--offline", action="store_true", help="With --verify: local check only, no network")
    parser.add_argument("--no-upstream-check", action="store_true", help="With --verify: skip newer-commit check")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    try:
        if args.verify:
            skill_dir = Path(args.verify)
            if not skill_dir.is_dir():
                skill_dir = Path(args.target_dir) / args.verify
            res = verify_installed_skill(skill_dir, offline=args.offline,
                                         check_upstream=not args.no_upstream_check)
            print(json.dumps(res, indent=2)) if args.json else _print_verify(res)
            return 0 if res["status"].startswith("VERIFIED") or res["status"] == "LOCAL_MATCHES_RECORD_ONLY" else 1

        if not args.repo or not args.skill:
            parser.error("--repo and --skill are required (or use --verify)")
        res = fetch_skill(args.repo, args.skill, Path(args.target_dir), ref=args.ref,
                          explicit_path=args.path, dry_run=args.dry_run, force=args.force,
                          accept_findings=args.accept_findings)
        print(json.dumps(res, indent=2, default=str)) if args.json else _print_fetch(res)
        return 0 if res["status"] in ("INSTALLED", "VERIFIED_DRY_RUN") else 1
    except FetchError as e:
        print(f"[FAILED] {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
