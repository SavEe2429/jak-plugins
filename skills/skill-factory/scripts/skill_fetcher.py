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
4. Stage -> scan -> install: files are written to a staging directory on the same volume,
   scanned with the local AST security scanner (fail-closed if scanner is unavailable),
   and moved into the skills directory only if the scan is CLEAN (or the user explicitly
   passes --accept-findings for WARNING/FAIL findings).
5. Path containment: every repository-supplied path is resolved, validated against Windows
   reserved device names/illegal characters/case-insensitive collisions, and must stay
   inside the destination directory.
6. Re-verification (--verify): checks local files against the provenance record,
   re-downloads the pinned files to detect a rewritten provenance record, confirms the
   file list against the pinned tree, and optionally reports newer upstream commits.

Limits (stated honestly):
- The trust root is GitHub over TLS plus the recorded repository/commit. If someone
  rewrites the provenance record to point at a different repository, verification
  proves consistency with THAT repository; the source repository is always printed so
  a human can confirm it.
- A static scan is not a runtime guarantee or an OS sandbox.

Free usage: unauthenticated GitHub REST API allows 60 requests/hour. No token is
read from the environment or sent. Raw file downloads use raw.githubusercontent.com.
Before any skill files are downloaded, the repository license must be identified by
GitHub and must be on the permissive-license allowlist.
"""

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import time
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
MAX_TOTAL_BYTES = 10 * 1024 * 1024
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
MAX_REDIRECTS = 3
MAX_NESTED_LICENSES = 10
CHUNK_SIZE = 64 * 1024
TIMEOUT = 20
OVERALL_FETCH_DEADLINE = 120.0
ALLOWED_HOSTS = frozenset({"api.github.com", "raw.githubusercontent.com"})
PERMISSIVE_LICENSES = frozenset({"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "0BSD", "Zlib", "BSL-1.0", "Unlicense"})
REPO_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9._-]{1,100}$")
WINDOWS_RESERVED_NAMES = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
    "COM\u00b9", "COM\u00b2", "COM\u00b3",
    "LPT\u00b9", "LPT\u00b2", "LPT\u00b3",
})
WINDOWS_INVALID_CHARS = frozenset('<>:"\\|?*')


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
    """Join a repository-supplied relative POSIX path under base, rejecting escapes and Windows hazards."""
    if not isinstance(rel, str) or not rel:
        raise FetchError(f"Unsafe path from repository rejected: {rel!r}")
    if any(ord(c) < 32 or c in WINDOWS_INVALID_CHARS for c in rel):
        raise FetchError(f"Unsafe path from repository rejected: {rel!r}")
    raw_parts = rel.split("/")
    if any(part in ("", ".", "..") for part in raw_parts):
        raise FetchError(f"Unsafe path from repository rejected: {rel!r}")
    pure = PurePosixPath(rel)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise FetchError(f"Unsafe path from repository rejected: {rel!r}")
    for part in pure.parts:
        if not part or part.endswith(".") or part.endswith(" "):
            raise FetchError(f"Unsafe path segment from repository rejected: {rel!r}")
        stem = part.split(".")[0].strip().upper()
        if stem in WINDOWS_RESERVED_NAMES:
            raise FetchError(f"Unsafe Windows reserved path rejected: {rel!r}")
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
        if p.is_file() and "__pycache__" not in p.parts:
            rel_posix = p.relative_to(skill_dir).as_posix()
            if rel_posix != PROVENANCE_FILE:
                files.append(rel_posix)
    return sorted(files)


# --------------------------------------------------------------------------- network


def _validate_github_https_url(url: str, error_msg: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme != "https"
        or hostname not in ALLOWED_HOSTS
        or parsed.port not in (None, 443)
        or parsed.username
        or parsed.password
    ):
        raise FetchError(error_msg)


class _GitHubRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, max_redirects: int = MAX_REDIRECTS) -> None:
        super().__init__()
        self.max_redirects = max_redirects
        self.redirect_count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_github_https_url(
            newurl, "GitHub returned a redirect outside the approved HTTPS hosts"
        )
        hops = getattr(req, "_github_redirect_hops", 0) + 1
        self.redirect_count += 1
        if hops > self.max_redirects or self.redirect_count > self.max_redirects:
            raise FetchError(f"Exceeded maximum redirects ({self.max_redirects})")
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req is not None:
            setattr(new_req, "_github_redirect_hops", hops)
        return new_req


def validate_repo(repo: str) -> str:
    if (
        not isinstance(repo, str)
        or not REPO_PATTERN.fullmatch(repo)
        or ".." in repo
        or repo.endswith(".")
        or repo.lower().endswith(".git")
    ):
        raise FetchError("Invalid GitHub repository identifier; expected owner/repository")
    return repo


def validate_commit(commit: str) -> str:
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
        raise FetchError("Invalid commit identifier; expected a full 40-character Git SHA")
    return commit.lower()


def _http_get(url: str, accept: Optional[str] = None, api: bool = False) -> bytes:
    _validate_github_https_url(url, "Request URL is outside the approved GitHub HTTPS hosts")
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _GitHubRedirectHandler(),
    )
    limit = MAX_RESPONSE_BYTES if api else MAX_FILE_BYTES
    start_mono = time.monotonic()
    try:
        with opener.open(req, timeout=TIMEOUT) as resp:
            chunks: List[bytes] = []
            total = 0
            while True:
                if time.monotonic() - start_mono > TIMEOUT:
                    raise FetchError(f"Request timed out after {TIMEOUT}s: {url}")
                chunk = resp.read(CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    raise FetchError(f"Response exceeds {limit} bytes: {url}")
                chunks.append(chunk)
            return b"".join(chunks)
    except urllib.error.HTTPError as e:
        if e.code in (403, 429) and e.headers.get("X-RateLimit-Remaining") == "0":
            raise FetchError(
                "GitHub API rate limit reached (60/hour unauthenticated). "
                "Wait for the unauthenticated quota to reset."
            ) from None
        raise FetchError(f"HTTP {e.code} for {url}") from None
    except urllib.error.URLError as e:
        raise FetchError(f"Network error for {url}: {e.reason}") from None


def resolve_commit(repo: str, ref: str) -> str:
    """Resolve a branch/tag/HEAD to an immutable 40-char commit SHA (1 API call)."""
    repo = validate_repo(repo)
    url = f"https://api.github.com/repos/{repo}/commits/{urllib.parse.quote(ref, safe='')}"
    sha = _http_get(url, accept="application/vnd.github.sha", api=True).decode().strip()
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise FetchError(f"Could not resolve ref {ref!r} to a commit SHA")
    return sha


def get_tree(repo: str, commit: str) -> List[Dict[str, Any]]:
    """Return the recursive tree listing for a validated immutable commit."""
    repo = validate_repo(repo)
    commit = validate_commit(commit)
    url = f"https://api.github.com/repos/{repo}/git/trees/{commit}?recursive=1"
    data = json.loads(_http_get(url, accept="application/vnd.github+json", api=True))
    if data.get("truncated"):
        raise FetchError("Repository tree is too large and was truncated by GitHub; cannot verify the file list.")
    return data.get("tree", [])


def get_repository_license(repo: str, ref: Optional[str] = None) -> Dict[str, str]:
    """Require a GitHub-recognized permissive SPDX license at the pinned repository ref."""
    repo = validate_repo(repo)
    url = f"https://api.github.com/repos/{repo}/license"
    if ref:
        url += "?ref=" + urllib.parse.quote(validate_commit(ref), safe="")
    try:
        payload = json.loads(_http_get(url, accept="application/vnd.github+json", api=True))
    except FetchError as exc:
        raise FetchError(f"Cannot verify repository license; refusing download: {exc}") from None
    license_data = payload.get("license") or {}
    spdx_id = license_data.get("spdx_id")
    if not spdx_id or spdx_id == "NOASSERTION":
        raise FetchError("Repository has no GitHub-recognized SPDX license; refusing download")
    if spdx_id not in PERMISSIVE_LICENSES:
        raise FetchError(f"License {spdx_id} is not on the approved permissive-license allowlist")
    return {"spdx_id": spdx_id, "name": str(license_data.get("name") or spdx_id),
            "path": str(payload.get("path") or "LICENSE"), "ref": ref or "DEFAULT_BRANCH",
            "verification": "GITHUB_REPOSITORY_LICENSE_API"}


LICENSE_FILE_PATTERN = re.compile(r"^(?:LICENSE|LICENCE|COPYING)(?:[._-].*)?$", re.IGNORECASE)
SPDX_IDENTIFIER_PATTERN = re.compile(r"SPDX-License-Identifier:\s*([^\r\n]+)", re.IGNORECASE)


def verify_nested_licenses(
    tree: List[Dict[str, Any]], repo: str, commit: str, skill_path: str,
    root_license: Dict[str, str],
) -> List[Dict[str, str]]:
    """Fail closed on additional license files that can govern the selected Skill subtree."""
    root_license_path = root_license.get("path", "LICENSE")
    candidates = []
    for item in tree:
        if item.get("type") != "blob":
            continue
        path = item.get("path", "")
        parent = path.rpartition("/")[0]
        if not LICENSE_FILE_PATTERN.fullmatch(path.rsplit("/", 1)[-1]):
            continue
        applies_to_skill = (
            not parent
            or skill_path == parent
            or skill_path.startswith(parent + "/")
            or parent == skill_path
            or parent.startswith(skill_path + "/")
        )
        if applies_to_skill and path != root_license_path:
            candidates.append(item)

    if len(candidates) > MAX_NESTED_LICENSES:
        raise FetchError(
            f"Too many nested license files ({len(candidates)} > {MAX_NESTED_LICENSES}); refusing download"
        )

    verified = []
    for item in sorted(candidates, key=lambda entry: entry["path"]):
        path = item["path"]
        size = int(item.get("size", 0) or 0)
        if size > MAX_FILE_BYTES:
            raise FetchError(f"Nested license file too large: {path} ({size} bytes)")
        content = download_pinned(repo, commit, path)
        if git_blob_sha1(content) != item.get("sha"):
            raise FetchError(f"Nested license content mismatch at pinned commit: {path}")
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            raise FetchError(f"Nested license is not readable UTF-8; refusing Skill download: {path}") from None
        identifiers = [match.strip() for match in SPDX_IDENTIFIER_PATTERN.findall(text)]
        if len(identifiers) != 1 or identifiers[0] not in PERMISSIVE_LICENSES:
            raise FetchError(
                f"Nested license at {path} has no single approved permissive SPDX identifier; refusing download"
            )
        verified.append({"path": path, "spdx_id": identifiers[0], "verification": "PINNED_LICENSE_FILE_SPDX"})
    return verified


def download_pinned(repo: str, commit: str, path: str) -> bytes:
    """Download raw bytes at a validated pinned commit via CDN."""
    repo = validate_repo(repo)
    commit = validate_commit(commit)
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
    files = []
    seen_lower: set[str] = set()
    total_bytes = 0
    for item in tree:
        path = item.get("path", "")
        if path != skill_path and not path.startswith(prefix):
            continue
        mode = str(item.get("mode", ""))
        item_type = item.get("type", "")
        if mode == "120000":
            raise FetchError(f"Symlink entry rejected in skill tree: {path}")
        if mode == "160000" or item_type == "commit":
            raise FetchError(f"Submodule entry rejected in skill tree: {path}")
        if path == skill_path:
            continue
        if item_type != "blob":
            continue
        rel_path = path[len(prefix):]
        if PurePosixPath(rel_path).name == PROVENANCE_FILE:
            raise FetchError(f"Repository cannot supply reserved provenance file: {rel_path}")
        lower_rel = rel_path.lower()
        if lower_rel in seen_lower:
            raise FetchError(f"Case-insensitive file path collision in skill tree: {rel_path}")
        seen_lower.add(lower_rel)
        size = int(item.get("size", 0) or 0)
        if size > MAX_FILE_BYTES:
            raise FetchError(f"File too large: {rel_path} ({size} bytes)")
        total_bytes += size
        files.append({
            "path": rel_path,
            "repo_path": path,
            "git_blob_sha": item["sha"],
            "size": size,
        })
    if len(files) > MAX_FILES:
        raise FetchError(f"Skill has {len(files)} files (limit {MAX_FILES}); refusing.")
    if total_bytes > MAX_TOTAL_BYTES:
        raise FetchError(
            f"Skill total size {total_bytes} bytes exceeds limit ({MAX_TOTAL_BYTES} bytes); refusing."
        )
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

    repo = validate_repo(repo)
    commit = validate_commit(resolve_commit(repo, ref))
    license_info = get_repository_license(repo, ref=commit)
    tree = get_tree(repo, commit)
    skill_path = find_skill_dir(tree, skill_name, explicit_path)
    files = files_under(tree, skill_path)
    nested_licenses = verify_nested_licenses(tree, repo, commit, skill_path, license_info)

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(tempfile.mkdtemp(prefix=f".skill-staging-{skill_name}-", dir=str(target_dir.parent)))
    staging = staging_root / skill_name
    staging.mkdir()
    try:
        records = []
        downloaded_total = 0
        fetch_start = time.monotonic()
        for f in files:
            if time.monotonic() - fetch_start > OVERALL_FETCH_DEADLINE:
                raise FetchError(f"Overall fetch deadline ({OVERALL_FETCH_DEADLINE}s) exceeded")
            out = safe_join(staging, f["path"])
            data = download_pinned(repo, commit, f["repo_path"])
            downloaded_total += len(data)
            if downloaded_total > MAX_TOTAL_BYTES:
                raise FetchError(
                    f"Downloaded skill exceeds total size limit ({MAX_TOTAL_BYTES} bytes); refusing."
                )
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
        scan_status = scan.get("status", "UNKNOWN")
        if scan_status not in ("CLEAN", "WARNING", "FAIL"):
            raise FetchError(
                f"Security scanner unavailable or returned invalid status ({scan_status!r}); "
                "refusing installation (fail-closed)."
            )
        blocked = scan_status != "CLEAN"
        provenance = {
            "schema_version": SCHEMA_VERSION,
            "skill_name": skill_name,
            "source_repository": f"https://github.com/{repo}",
            "requested_ref": ref,
            "pinned_commit": commit,
            "skill_path": skill_path,
            "license": license_info,
            "nested_licenses": nested_licenses,
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
    source_repository = prov.get("source_repository", "")
    if not source_repository.startswith("https://github.com/"):
        return {"status": "ERROR", "problems": ["Invalid provenance repository URL"]}
    try:
        repo = validate_repo(source_repository[len("https://github.com/"):].strip("/"))
    except FetchError as exc:
        return {"status": "ERROR", "problems": [str(exc)]}
    commit, skill_path = prov["pinned_commit"], prov["skill_path"]
    try:
        pinned_tree = get_tree(repo, commit)
        pinned_license = get_repository_license(repo, ref=commit)
        if prov.get("license", {}).get("spdx_id") != pinned_license.get("spdx_id"):
            problems.append("recorded repository license differs from the pinned upstream license")
        pinned_files = {f["path"]: f for f in files_under(pinned_tree, skill_path)}
        pinned_nested_licenses = verify_nested_licenses(
            pinned_tree, repo, commit, skill_path, pinned_license
        )
        if prov.get("nested_licenses", []) != pinned_nested_licenses:
            problems.append("recorded nested license evidence differs from pinned upstream")
        if set(pinned_files) != set(recorded):
            problems.append("file list differs from upstream tree at pinned commit")
        for rel, rec in recorded.items():
            up = pinned_files.get(rel)
            if up and up["git_blob_sha"] != rec["git_blob_sha"]:
                problems.append(f"record mismatch vs upstream: {rel}")
        downloaded_total = 0
        for rel in sorted(set(recorded) & set(pinned_files)):
            data = download_pinned(repo, commit, pinned_files[rel]["repo_path"])
            downloaded_total += len(data)
            if downloaded_total > MAX_TOTAL_BYTES:
                raise FetchError(
                    f"Downloaded skill exceeds total size limit ({MAX_TOTAL_BYTES} bytes); refusing."
                )
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


def resolve_fetch_target_dir(
    target_dir: Optional[str],
    scope: str = "project",
    active_agent: Optional[str] = None,
    workspace: str = ".",
) -> Path:
    """Resolve destination skills directory from explicit --target-dir or --scope + --agent."""
    if target_dir is not None:
        return Path(target_dir)
    if active_agent is None and scope in ("project", "workspace") and workspace == ".":
        return Path(".agents/skills")
    from agent_adapter import AgentEnvironmentAdapter

    adapter = AgentEnvironmentAdapter(Path(workspace).resolve(), active_agent=active_agent)
    return adapter.resolve_target_install_directory(scope)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--repo", "-r", help="GitHub repository owner/name (e.g. mattpocock/skills)")
    parser.add_argument("--skill", "-s", help="Skill directory name to fetch (e.g. tdd)")
    parser.add_argument("--path", help="Exact skill directory path in the repo (disambiguates duplicates)")
    parser.add_argument("--ref", default="HEAD", help="Branch, tag, or commit to pin (default: default branch)")
    parser.add_argument("--target-dir", "-t", default=None, help="Explicit skills destination directory override")
    parser.add_argument(
        "--scope",
        choices=("project", "workspace", "user", "global"),
        default="project",
        help="Target installation scope: 'project'/'workspace' (project-level) or 'user'/'global' (user-level)",
    )
    parser.add_argument(
        "--agent", "--active-agent", dest="active_agent",
        choices=("gemini", "claude", "codex", "cursor", "copilot", "local"),
        default=None,
        help="Explicit active agent runtime identity used with --scope to resolve the skills directory",
    )
    parser.add_argument("--workspace", default=".", help="Workspace root directory when resolving project scope")
    parser.add_argument("--dry-run", action="store_true", help="Download, verify, and scan without installing")
    parser.add_argument("--force", action="store_true", help="Replace an existing install (keeps a backup)")
    parser.add_argument("--accept-findings", action="store_true", help="Install even if the scan is not CLEAN")
    parser.add_argument("--verify", metavar="SKILL", help="Verify an installed skill (name or directory)")
    parser.add_argument("--offline", action="store_true", help="With --verify: local check only, no network")
    parser.add_argument("--no-upstream-check", action="store_true", help="With --verify: skip newer-commit check")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    try:
        resolved_target_dir = resolve_fetch_target_dir(
            args.target_dir, scope=args.scope, active_agent=args.active_agent, workspace=args.workspace
        )
        if args.verify:
            skill_dir = Path(args.verify)
            if not skill_dir.is_dir():
                skill_dir = resolved_target_dir / args.verify
            res = verify_installed_skill(skill_dir, offline=args.offline,
                                         check_upstream=not args.no_upstream_check)
            print(json.dumps(res, indent=2)) if args.json else _print_verify(res)
            return 0 if res["status"].startswith("VERIFIED") or res["status"] == "LOCAL_MATCHES_RECORD_ONLY" else 1

        if not args.repo or not args.skill:
            parser.error("--repo and --skill are required (or use --verify)")
        res = fetch_skill(args.repo, args.skill, resolved_target_dir, ref=args.ref,
                          explicit_path=args.path, dry_run=args.dry_run, force=args.force,
                          accept_findings=args.accept_findings)
        print(json.dumps(res, indent=2, default=str)) if args.json else _print_fetch(res)
        return 0 if res["status"] in ("INSTALLED", "VERIFIED_DRY_RUN") else 1
    except FetchError as e:
        print(f"[FAILED] {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
