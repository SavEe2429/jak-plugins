# Universal Repository Governance & CI/CD Orchestration

Use this reference when designing or scaffolding repository governance, CI/CD pipelines, release orchestration, and contributor guidance across any programming language or technology stack. These principles are language-agnostic and adapt dynamically to the detected ecosystem.

---

## 1. Governance Architecture Overview

Every production-grade repository requires five pillars of governance, regardless of stack:

```text
changelog.d/                         # Towncrier-style release fragments (<pr-or-issue>.<type>.md)
.github/
├── ISSUE_TEMPLATE/                  # GitHub Issue Forms (.yml) & chooser config
│   ├── bug_report.yml               # Technical bug report (crashes, exceptions, CLI & manifest errors)
│   ├── skill_gap.yml                # AI prompt & guidance gap report (hallucinations, stack mismatch)
│   ├── feature_request.yml          # Structured feature proposal form
│   └── config.yml                   # Issue chooser settings & security advisory link
├── actions/                         # Reusable composite actions
│   └── parse_release_version/       # Dynamic SemVer extraction & validation
├── scripts/                         # Deterministic release & manifest sync scripts
│   ├── release_manager.py           # Multi-manifest sync, changelog promotion & bundle packager
│   ├── prepare_release.py           # Towncrier compiler & multi-manifest lockstep version bumper
│   ├── read_manifest_version.py     # Safe non-inline manifest version reader
│   └── validate_reference_links.py  # Markdown reference links integrity scanner
├── workflows/                       # GitHub Actions pipelines
│   ├── ci.yml                       # Multi-job DAG quality gate (code-quality, test, build, summary)
│   ├── changelog_guard.yml          # PR gate: enforces changelog.d fragments & blocks CHANGELOG.md edits
│   ├── prepare_release.yml          # Manual dispatch: compiles fragments, bumps versions, opens PR
│   ├── tag_release.yml              # Verified tag creation on merge of release PR to main
│   ├── release.yml                  # Automated release build, packaging, checksums, and publish
│   └── README.md                    # Self-documenting workflow runbook & local testing
├── copilot-instructions.md          # AI Assistant & Copilot domain, architecture & vendor rules
└── pull_request_template.md         # Contributor/Reviewer checklists, Agent disclosure, COI statement
```

---

## 2. Multi-Tier CI Quality Gate (Stack-Agnostic Matrix)

Continuous Integration is organized into 4 standardized tiers plus an aggregated summary:

| Tier                           | Purpose                                    | Python                              | Node / TypeScript                     | Go                          | Rust                                | C# / .NET                           |
| :----------------------------- | :----------------------------------------- | :---------------------------------- | :------------------------------------ | :-------------------------- | :---------------------------------- | :---------------------------------- |
| **Tier 1: Style & Linter**     | Static analysis, format, import sorting    | `ruff check`, `ruff format --check` | `eslint`, `prettier --check`, `biome` | `golangci-lint`             | `cargo clippy`, `cargo fmt --check` | `dotnet format --verify-no-changes` |
| **Tier 2: Automated Tests**    | Unit & integration tests with coverage     | `pytest --cov`                      | `vitest`, `jest`                      | `go test -race ./...`       | `cargo test`                        | `dotnet test`                       |
| **Tier 3: Security Scan**      | Static security audit & vulnerability scan | `bandit`, `pip-audit`               | `pnpm audit`                          | `govulncheck ./...`         | `cargo audit`                       | `dotnet list package --vulnerable`  |
| **Tier 4: Build Verification** | Package compilation & artifact validation  | `uv build`                          | `pnpm build`                          | `go build ./...`            | `cargo build --release`             | `dotnet build -c Release`           |
| **Summary: Step Metrics**      | Aggregated run stats & LOC report          | `cloc`, GitHub Step Summary         | `cloc`, GitHub Step Summary           | `cloc`, GitHub Step Summary | `cloc`, GitHub Step Summary         | `cloc`, GitHub Step Summary         |

### CI Dynamic Rules

1. **Never bypass native runners:** Always invoke tools via the package manager runner (`uv run`, `pnpm exec`, `cargo`, `go`).
2. **SSOT Toolchain Pinning (Zero Duplicate Version Strings):** Pin toolchain versions in a single canonical file (`.python-version` / `pyproject.toml`, `package.json` / `.nvmrc`, `go.mod`, `rust-toolchain.toml`, `global.json`) and configure CI actions to read directly from that file (`python-version-file`, `go-version-file`, `node-version-file`, `rust-toolchain.toml`) rather than hardcoding duplicate version numbers inside `.github/workflows/ci.yml`.
3. **No console errors / zero warnings:** Warnings must be treated as errors in CI (e.g. `-D warnings` in Rust, `--strict` in linters).
4. **Dynamic LTS / Latest Stable Version Policy & Full-SHA Pinning:**
   - Never rely on memorized or hardcoded version numbers for runtimes, dependencies, pre-commit hooks, or GitHub Actions. Always resolve active **LTS** or **Latest Stable** versions.
   - **Full-SHA Action Pinning:** In production repositories, pin third-party GitHub Actions to immutable full commit SHAs with a trailing human-readable SemVer comment (e.g. `uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`), complying with OpenSSF Scorecard and SLSA Level 3 supply-chain standards.
5. **Zero-Trust Token Permissions & Hygiene:**
   - Set top-level `permissions: {}` at the root of every workflow to disable default write tokens.
   - Declare minimal, least-privilege permissions per job (e.g. `contents: read`, `pull-requests: read`).
   - Use `persist-credentials: false` in `actions/checkout` so tokens are not retained in the runner's local Git configuration.
6. **Cross-Platform Verification & Subprocess Isolation:**
   - When project code executes external processes, handles OS signals, or manages filesystem paths, include a dedicated `windows-latest` or matrix job (e.g. `windows-process-tree`) to verify process tree termination and signal handling parity across POSIX and Windows.
7. **Multi-Job DAG Architecture (`code-quality`, `test`, `build`, `summary`):**
   - Separate CI into distinct jobs connected via `needs:` so `code-quality` and `test` run in parallel and `build` runs only after upstream checks pass (`needs: [code-quality, test]`).
   - The `build` job must execute the project's declared build/packaging command and configured mode (matching the Single Source of Truth in the repository's build script or manifest).
8. **Dual-Audience `summary` Gate Job (`$GITHUB_STEP_SUMMARY` + `Enforce Overall Gate`):**
   - Always include a final `summary` job with `needs: [code-quality, test, build]` (or all active upstream jobs) and `if: always()` containing two distinct steps for two audiences:
     - **Step 1 — `Write Workflow Summary` (for Humans):** Appends a Markdown table of job results to `$GITHUB_STEP_SUMMARY` so developers and reviewers see a visual summary table on the GitHub Actions run page.
     - **Step 2 — `Enforce Overall Gate` (for GitHub Branch Protection / Machine Gate):** Because `if: always()` causes the `summary` job to execute even when an upstream job fails or is cancelled, explicitly verify that every upstream `needs.<job>.result == "success"` and execute `exit 1` otherwise. This allows branch protection rulesets to require a single `CI Summary & Gate` status check to block broken PR merges.

```yaml
summary:
  name: CI Summary & Gate
  needs: [code-quality, test, build]
  if: always()
  runs-on: ubuntu-latest
  steps:
    - name: Write Workflow Summary
      run: |
        echo "### CI Quality Gate Summary" >> $GITHUB_STEP_SUMMARY
        echo "" >> $GITHUB_STEP_SUMMARY
        echo "| Job | Result |" >> $GITHUB_STEP_SUMMARY
        echo "| :--- | :--- |" >> $GITHUB_STEP_SUMMARY
        echo "| code-quality | ${{ needs.code-quality.result }} |" >> $GITHUB_STEP_SUMMARY
        echo "| test | ${{ needs.test.result }} |" >> $GITHUB_STEP_SUMMARY
        echo "| build | ${{ needs.build.result }} |" >> $GITHUB_STEP_SUMMARY

    - name: Enforce Overall Gate
      run: |
        if [[ "${{ needs.code-quality.result }}" != "success" || "${{ needs.test.result }}" != "success" || "${{ needs.build.result }}" != "success" ]]; then
          echo "One or more CI jobs failed."
          exit 1
        fi
```

---

## 3. Generic SemVer Release Automation

Automate the release lifecycle safely. Projects can select between two release architectures based on team scale and contributor model:

### Option A: Decoupled 3-Stage Release Automation (Recommended for Teams & Multi-Agent Swarms)

In active multi-contributor or multi-agent repositories, concurrent edits to `CHANGELOG.md` create constant merge conflicts. The **Towncrier / Fragment Pattern** with a decoupled 3-stage release avoids conflicts and prevents unauthorized version bumps:

```text
PR Workflow:
  Contributor adds changelog.d/<pr-number>.<type>.md (types: added, changed, fixed, removed, deprecated, security)
  changelog-guard.yml blocks direct edits to CHANGELOG.md and blocks non-release version bumps

Stage 1: Prepare Release (prepare_release.yml)
  - Triggered via workflow_dispatch with SemVer bump type (patch, minor, major) or explicit version
  - Runs .github/scripts/prepare_release.py to compile changelog.d/ fragments into CHANGELOG.md
  - Updates all version manifests in lockstep (pyproject.toml, SKILL.md, plugin.json, etc.)
  - Opens a release branch (release/vX.Y.Z) and PR with label 'release'

Stage 2: Tag Release (tag_release.yml)
  - Triggered when a commit matching 'chore(release): bump version to X.Y.Z' merges to main
  - Verifies that the merged PR carries the repository-controlled 'release' label (security gate preventing spoofing)
  - Verifies commit message version matches manifest SSOT
  - Creates and pushes annotated Git tag vX.Y.Z
  - Dispatches release.yml

Stage 3: Build & Publish Release (release.yml)
  - Triggered by workflow_dispatch with tag parameter from tag_release.yml
  - Verifies Git tag locally (gh release create --verify-tag)
  - Executes multi-platform matrix builds (e.g. cross-compiling binaries, packaging bundles)
  - Computes SHA-256 checksums
  - Publishes GitHub Release with auto-generated release notes and attached distribution assets
```

#### Changelog Guard Gate (`changelog_guard.yml`)

Enforces release discipline across all feature PRs:

1. **Blocks Direct CHANGELOG Edits:** Fails if `CHANGELOG.md` is modified directly in a feature PR (requires `changelog.d/` fragment).
2. **Enforces Version Lockstep:** Fails if any manifest version is changed outside an authorized release PR.
3. **Exemptions:** Bypasses checks if PR has label `release`, label `skip-changelog`, or is authored by `dependabot[bot]`.

#### Manifest Version Helpers (`.github/scripts/`)

- `read_manifest_version.py`: Standalone CLI helper to extract SemVer strings across heterogeneous formats (TOML, JSON, YAML frontmatter) without brittle inline Python scripts in Actions YAML.
- `prepare_release.py`: Deterministic compiler that consumes `changelog.d/` fragments, prepends the new release section to `CHANGELOG.md`, and updates all manifest versions simultaneously.

---

### Option B: Ephemeral Branch-Triggered 5-Stage Release Workflow (Auto-Merge & Self-Cleaning)

Suitable for smaller or single-maintainer repositories that want a fully automated release triggered simply by creating and pushing a release branch (`release/vX.Y.Z`). The workflow builds the release, mints the tag, merges updates back to the default branch, and cleans up the temporary release branch automatically:

```text
Developer Action:
  git checkout -b release/v1.1.0 && git push origin release/v1.1.0

Workflow Execution (.github/workflows/release.yml):
  Stage 1: Parse SemVer & Verify Quality Gate
    - Extracts version (1.1.0), tag (v1.1.0), and release date via .github/actions/parse_release_version
    - Runs linting and line-ending checks (CRLF check)

  Stage 2: Synchronize Manifests & Promote Changelog
    - Syncs version across all manifest files (release_manager.py sync-manifests)
    - Promotes [Unreleased] to [1.1.0] - YYYY-MM-DD in CHANGELOG.md
    - Extracts standalone release notes to docs/release-notes/v1.1.0.md and indexes in README.md

  Stage 3: Package Distribution Bundle & Generate Checksums
    - Packages distributable zip archive into dist/ (release_manager.py build-archive)
    - Computes SHA-256 hashes (sha256sum * > SHA256SUMS.txt)
    - Formats combined release body (release_manager.py build-body)

  Stage 4: Commit Updates, Tag & Publish GitHub Release
    - Commits manifest/changelog/docs changes to release branch with [skip ci]
    - Creates immutable annotated Git tag (git tag -fa v1.1.0 -m "Release v1.1.0") and pushes tag
    - Publishes GitHub Release attaching the distributable archives and SHA256SUMS.txt

  Stage 5: Auto-Merge Back to Default Branch & Self-Clean Branch
    - Merges the release commit back into main to ensure CHANGELOG.md and manifests stay in sync:
        git fetch origin main:main
        git checkout main
        git merge --ff-only origin/release/v1.1.0 || git merge -m "chore(release): merge v1.1.0 back into main [skip ci]" origin/release/v1.1.0
        git push origin main
    - Deletes the ephemeral release branch from origin (git push origin --delete release/v1.1.0)
    - Deletion Guard: Strictly guarded with `if: startsWith(github.ref, 'refs/heads/release/')` to prevent accidental deletion when invoked via manual workflow_dispatch on default branches.

Branch Protection Governance:
  - When repository branch protection requires pull request reviews on 'main', use Option A (Decoupled 3-Stage with PR) OR add github-actions[bot] to the branch protection bypass list for direct release merges.

---

## 4. AI Assistant & Contributor Guidance (`copilot-instructions.md` & `AGENTS.md`)

Maintain synchronized runbooks for both AI tools and human contributors:

- **`AGENTS.md` (Operational Runbook):**
  - Commands to discover, build, test, lint, and run the project using native runners.
  - Append-only logbook rules (`logbook/current.md` rotation at 500 lines).
  - Explicit boundaries (what tools/APIs are permitted).
- **`.github/copilot-instructions.md` (Context-Aware AI Rules):**
  - **Project Overview & Purpose:** Clear problem statement and domain terminology.
  - **Technology Stack:** Pinned versions, core dependencies, and forbidden libraries.
  - **Architecture Boundaries:** Package encapsulation rules (entrypoints in `src/<package_name>/`, state in `data/`, no loose files in root).
  - **Vendor Exclusion Zones:** Explicitly define no-touch vendor directories (e.g. `Never suggest changes to vendor/ or third-party subtrees`).
  - **Safe Local CLI Examples:** When suggesting CLI usage for testing, default to safe flags (e.g. `--mock`, `--dry-run`, `--emit=compact`).
  - **Code Quality Requirements:** Formatting tools, type annotations, error handling conventions, and test-driven design rules.

---

## 5. Structured PR Governance & Review Checklist

Provide `.github/pull_request_template.md` to enforce quality before merge:

1. **Change Classification:** Checkbox selection mapped directly to Conventional Commits (`feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `chore`).
2. **Changelog Fragment Enforcement:**
   - Require adding `changelog.d/<pr-number>.<type>.md` (types: `added`, `changed`, `fixed`, `removed`, `deprecated`, `security`).
   - Or explicitly selecting `[ ] Skip changelog — chore/internal only` (with `skip-changelog` label).
   - Strict reminder: **Do NOT edit `CHANGELOG.md` directly in feature PRs.**
3. **Agent Disclosure & AI Review Summary:**
   - Require author to summarize any AI coding agent review performed: tools used, main risks evaluated, flagged issues, and changes verified.
4. **Security Risk Assessment:**
   - Explicit review of input validation, shell command execution, path traversal, auth, secrets handling, or dependency additions.
5. **Relationship & Conflict of Interest (COI) Disclosure:**
   - Require disclosure of employment, contracting, equity, or commercial ties to any third-party company/service added or promoted by the PR.
6. **Dual-Role Verification Checklists:**
   - **Contributor Checklist:** Self-review completed, no redundant comments, linters/formatters pass, no compiler warnings, tests added, documentation updated.
   - **Reviewer Checklist:** Adheres to architecture and separation of concerns, test coverage verified, security posture preserved, backward compatibility checked.

---

## 6. Self-Documenting Workflows (`.github/workflows/README.md`)

Every project with GitHub Actions must include documentation explaining its pipelines:

- **Workflow Catalog:** Table listing each workflow file, its triggers (`push`, `pull_request`, `workflow_dispatch`), and permissions.
- **Secrets Reference:** Explicit table of required GitHub Secrets (e.g. `GITHUB_TOKEN`, registry API keys, signing certificates).
- **Branch Protection Policies:** Recommended rules for protected branches (`main`, `develop`).
- **Local Workflow Execution:** Actionable instructions on how to test workflows locally (e.g. using `act` or executing equivalent native commands).

---

## 7. Standardized 9-Section Source Code Template Architecture

To ensure code consistency across all developers and AI agents, all generated source files must follow the 9-section modular structure:

```python
"""Module docstring explaining responsibility, interfaces, and usage."""

## ---------- (01) STANDARD LIBRARY IMPORTS ----------------------------------------- ##
## ---------- (02) THIRD-PARTY IMPORTS ---------------------------------------------- ##
## ---------- (03) LOCAL APPLICATION/LIBRARY-SPECIFIC IMPORTS ----------------------- ##
## ---------- (04) CONSTANTS -------------------------------------------------------- ##
## ---------- (05) ENUMS ------------------------------------------------------------ ##
## ---------- (06) CLASS DEFINITIONS ------------------------------------------------ ##
## ---------- (07) PUBLIC FUNCTIONS ------------------------------------------------- ##
## ---------- (08) PRIVATE FUNCTIONS ------------------------------------------------ ##
## ---------- (09) MAIN EXECUTION --------------------------------------------------- ##
```

When requested, scaffold a `templates/` folder in the project containing starter templates for the stack (e.g. `templates/python/script_template.py`, `templates/c_cpp/hdr_template.hpp`, `templates/c_sharp/MonoBehaviourTemplate.cs`). Keep starter files in `templates/` as **pure skeleton templates** (module docstring, the 9 section headers with brief inline guidance comments, and a minimal `main()` stub) without dummy classes, sample business logic, or unused imports.

---

## 8. Enterprise Tooling Presets & Hygiene Configuration

Every repository must declare explicit linters, formatters, and git hygiene controls:

1. **`.pre-commit-config.yaml`:**
   - **Security:** `detect-private-key` (prevent credential leaks), `bandit` (Python security scan).
   - **Git Governance:** `conventional-pre-commit` on `commit-msg` stage.
   - **Hygiene:** `mixed-line-ending` (`--fix=lf`), `trailing-whitespace`, `end-of-file-fixer`, `check-merge-conflict`, `check-yaml`, `check-toml`, `check-json`.
   - **Formatters:** Native linter/formatter (`ruff --fix` for Python, `eslint`/`prettier` for Node, `dotnet format` for C#), `yamlfmt`, `markdownlint-cli2`.
   - **Windows Safety:** `check-added-large-files` and path length verification.
   - **CI Optimization:** `ci.skip` declared for slow or network-bound checks.
2. **`.prettierrc.yaml`:**
   - `printWidth: 100`, `proseWrap: "always"` (hard-wraps markdown text at 100 chars for clean git diffs), `tabWidth: 4` (with `tabWidth: 2` override for `*.md`).
3. **`.markdownlint.yaml`:**
   - Explicit `indent: 2` for lists, consistent header styles, and code block formatting.
4. **Comprehensive `.gitignore` Matrix:**
   - **Build & Distribution:** `build/`, `dist/`, `out/`, `bin/`, `obj/`, `Library/`, `Temp/`.
   - **Caches & Runtimes:** `.venv/`, `node_modules/`, `__pycache__/`, `*.cache`, `*.pyc`.
   - **Runtime State & Databases:** `data/*.db`, `logs/*.log`, `state/`, `temp/`.
   - **Environment & Secrets:** `.env`, `.secrets`, `*.pem`, `*.key`.
   - **OS & IDE Metadata:** `.DS_Store`, `Thumbs.db`, `.vscode/*.json` (except shared settings), `.idea/`.
5. **`.env.example` & `.secrets.example`:**
   - Authoritative list of all environment variables and secrets required by the application, with safe placeholder values (supporting SSOT).

---

## 9. Universal Deliverables Manifest & Checkbox Matrix

When scaffolding, evaluate and deliver the complete set of standard files:

```markdown
- [ ] Project Manifest: `pyproject.toml` | `package.json` | `Cargo.toml` | `ProjectSettings/ProjectVersion.txt`
- [ ] Toolchain Pinning: `.python-version` | `rust-toolchain.toml` | `go.mod` | `global.json`
- [ ] SSOT Configuration: `core/config.py` | `src/config/` | `GameConfig.cs` AND `.env.example`
- [ ] Source Entrypoints: Encapsulated in package namespace (`src/<pkg>/cli.py` or `Assets/Scripts/Core/`)
- [ ] 9-Section Templates: Code template in `templates/` following standard 9-section structure
- [ ] Repository Hygiene: `.gitignore`, `.gitattributes` (LF + Git LFS), `.editorconfig`
- [ ] Pre-commit & Linter Config: `.pre-commit-config.yaml`, `.markdownlint.yaml`, `.prettierrc.yaml`
- [ ] Test Harness: Unit test suite with verified assertion (`tests/unit/` or `Assets/Tests/EditMode/`)
- [ ] CI Quality Gate: `.github/workflows/ci.yml` (Multi-job DAG: `code-quality`, `test`, `build`, and `summary` gate with `$GITHUB_STEP_SUMMARY` + `Enforce Overall Gate`)
- [ ] Issue Forms & Governance: `.github/ISSUE_TEMPLATE/bug_report.yml`, `.github/ISSUE_TEMPLATE/feature_request.yml`, `.github/ISSUE_TEMPLATE/config.yml`
- [ ] Universal Release Actions & Scripts (Option A: Decoupled 3-Stage OR Option B: Branch-Triggered):
  - [ ] `changelog.d/` fragment directory with `changelog.d/README.md`
  - [ ] `.github/workflows/changelog_guard.yml` (PR fragment enforcement & version lock)
  - [ ] `.github/workflows/prepare_release.yml` (Towncrier compilation & lockstep bumps)
  - [ ] `.github/workflows/tag_release.yml` (Verified tag minting on main merge)
  - [ ] `.github/scripts/prepare_release.py` & `.github/scripts/read_manifest_version.py`
  - [ ] `.github/actions/parse_release_version/action.yml` (for Option B)
  - [ ] `.github/scripts/release_manager.py` (Cross-platform Python release manager for Option B)
  - [ ] `.github/workflows/release.yml` (Build, bundle, checksum, and GitHub release)
- [ ] Workflow Documentation: `.github/workflows/README.md`
- [ ] Contributor & AI Governance: `README.md`, `CHANGELOG.md`, `AGENTS.md`, `.github/copilot-instructions.md` (with vendor exclusions), `.github/pull_request_template.md` (with Agent & COI disclosure)
- [ ] AI Skill & Plugin Governance (when applicable):
  - [ ] `.github/ISSUE_TEMPLATE/skill_gap.yml` (Prompt feedback & instruction gap reporting)
  - [ ] `.github/scripts/validate_reference_links.py` (Markdown reference links integrity check)
  - [ ] Plugin validation & install smoke test job in `.github/workflows/ci.yml` (`claude plugin validate .` & local marketplace install)
- [ ] Operational Logbook: `logbook/README.md` & `logbook/current.md` (append-only)
```

---

## 10. AI Agent Skill & Plugin Repository Archetype

When the target project is an **Agent Skill, Plugin, or MCP Server bundle** (e.g. for Claude Code, Antigravity, Gemini CLI, Cursor, or Codex), standard software templates must be augmented with AI-specific governance and validation:

### 1. Specialized Issue Template: `skill_gap.yml`

Standard bug reports asking for stacktraces and step-by-step reproduction fail to capture the primary failure mode of AI skills: **instruction drift, ambiguous guidelines, hallucination, or ecosystem mismatch**.

Include `.github/ISSUE_TEMPLATE/skill_gap.yml` with:

- **Affected skill dropdown:** Pinpoints which skill prompt produced unexpected behavior.
- **Relevant instruction or excerpt:** The exact passage in `SKILL.md` or `references/*.md` that misled the agent.
- **Target project context:** Language, build tool, package manager, and OS where the issue occurred.
- **Failure explanation:** What the agent did when following the guidance (e.g. insisted on npm in a Go/Maven repo).
- **Workaround:** How the human/agent got unblocked (crucial for prompt tuning).

### 2. Markdown Reference Links Integrity Gate

In agent skills, documentation *is* code. A broken relative link inside `SKILL.md` to `references/*.md` causes agent tool calls (`read_file`) to fail, throwing the agent into an unrecoverable error loop.

- Provide `.github/scripts/validate_reference_links.py` to statically verify all relative Markdown links across `skills/` and `docs/`.
- Wire into the CI `code-quality` tier to block broken documentation links before merge.

### 3. Plugin Manifest Validation & Hermetic Install Smoke Test

Agent plugins must be validated using the host ecosystem's native CLI tools:

- **Manifest Lint:** Run `claude plugin validate .` to check marketplace and plugin manifest schemas, permissions, and metadata.
- **Hermetic Install Smoke Test:** In CI, register a local marketplace (`claude plugin marketplace add ./`) and execute a test install (`claude plugin install <plugin> --scope user`) to prove the bundle installs cleanly without schema or network errors.
