# Universal Repository Governance & CI/CD Orchestration

Use this reference when designing or scaffolding repository governance, CI/CD pipelines, release orchestration, and contributor guidance across any programming language or technology stack. These principles are language-agnostic and adapt dynamically to the detected ecosystem.

---

## 1. Governance Architecture Overview

Every production-grade repository requires five pillars of governance, regardless of stack:

```text
.github/
├── actions/                         # Reusable composite actions
│   └── parse-release-version/       # Dynamic SemVer extraction & validation
├── scripts/                         # Deterministic POSIX/Bash/PWSH governance scripts
│   └── release/                     # Changelog promotion, release notes, release body
├── workflows/                       # GitHub Actions pipelines
│   ├── ci.yml                       # Multi-tier quality gate (lint, test, sec, build)
│   ├── release.yml                  # Automated release & tag orchestration
│   └── README.md                    # Self-documenting workflow runbook & local testing
├── copilot-instructions.md          # AI Assistant & Copilot domain/architecture rules
└── pull_request_template.md         # Contributor & Reviewer dual checklist
```

---

## 2. Multi-Tier CI Quality Gate (Stack-Agnostic Matrix)

Continuous Integration is organized into 4 standardized tiers plus an aggregated summary:

| Tier | Purpose | Python | Node / TypeScript | Go | Rust | C# / .NET |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Tier 1: Style & Linter** | Static analysis, format, import sorting | `ruff check`, `ruff format --check` | `eslint`, `prettier --check`, `biome` | `golangci-lint` | `cargo clippy`, `cargo fmt --check` | `dotnet format --verify-no-changes` |
| **Tier 2: Automated Tests** | Unit & integration tests with coverage | `pytest --cov` | `vitest`, `jest` | `go test -race ./...` | `cargo test` | `dotnet test` |
| **Tier 3: Security Scan** | Static security audit & vulnerability scan | `bandit`, `pip-audit` | `pnpm audit` | `govulncheck ./...` | `cargo audit` | `dotnet list package --vulnerable` |
| **Tier 4: Build Verification** | Package compilation & artifact validation | `uv build` | `pnpm build` | `go build ./...` | `cargo build --release` | `dotnet build -c Release` |
| **Summary: Step Metrics** | Aggregated run stats & LOC report | `cloc`, GitHub Step Summary | `cloc`, GitHub Step Summary | `cloc`, GitHub Step Summary | `cloc`, GitHub Step Summary | `cloc`, GitHub Step Summary |

### CI Dynamic Rules:
1. **Never bypass native runners:** Always invoke tools via the package manager runner (`uv run`, `pnpm exec`, `cargo`, `go`).
2. **Deterministic toolchain:** Pin toolchain versions via configuration files (`.python-version`, `package.json#packageManager`, `go.mod`, `rust-toolchain.toml`, `global.json`).
3. **No console errors / zero warnings:** Warnings must be treated as errors in CI (e.g. `-D warnings` in Rust, `--strict` in linters).
4. **Summary Aggregation:** Always write a job summary to `$GITHUB_STEP_SUMMARY` detailing passes, coverage, and build artifacts.

---

## 3. Generic SemVer Release Automation

Automate the entire release lifecycle without manual tag pushing. Human developers trigger a release simply by creating/pushing a release branch (`release/vX.Y.Z`).

### The 4-Stage Release Workflow:
1. **Validate & Parse Version:**
   - Detect branch name pattern `^release/v([0-9]+\.[0-9]+\.[0-9]+(-(alpha|beta|rc)\.[0-9]+)?)$`.
   - Extract `version` (e.g. `1.2.0`), `tag` (`v1.2.0`), and `date` (`YYYY-MM-DD`).
   - Block if branch naming does not comply with SemVer.
2. **Promote Changelog:**
   - Scan `CHANGELOG.md` following [Keep a Changelog](https://keepachangelog.com/).
   - Promote `## [Unreleased]` block into `## [vX.Y.Z] - YYYY-MM-DD`.
   - Fall back to GitHub PR/commit history only if `[Unreleased]` is empty.
3. **Generate Versioned Release Notes:**
   - Extract the newly promoted section into a standalone versioned doc (e.g. `docs/release-notes/vX.Y.Z.md`).
   - Update the release notes index table.
4. **Build, Tag & Publish:**
   - Execute the stack-specific release build (Tier 4).
   - Generate SHA-256 checksums (`sha256sum * > SHA256SUMS.txt`).
   - Merge release branch into `main` (or default branch).
   - Create immutable Git tag (`vX.Y.Z`).
   - Publish GitHub Release attaching binary artifacts, changelog notes, and checksums.

---

## 4. AI Assistant & Contributor Guidance (`copilot-instructions.md` & `AGENTS.md`)

Maintain synchronized runbooks for both AI tools and human contributors:

* **`AGENTS.md` (Operational Runbook):**
  - Commands to discover, build, test, lint, and run the project using native runners.
  - Append-only logbook rules (`logbook/current.md` rotation at 500 lines).
  - Explicit boundaries (what tools/APIs are permitted).
* **`.github/copilot-instructions.md` (Context-Aware AI Rules):**
  - **Project Overview & Purpose:** Clear problem statement and domain terminology.
  - **Technology Stack:** Pinned versions, core dependencies, and forbidden libraries.
  - **Architecture Boundaries:** Package encapsulation rules (entrypoints in `src/<package_name>/`, state in `data/`, no loose files in root).
  - **Code Quality Requirements:** Formatting tools, type annotations, error handling conventions, and test-driven design rules.

---

## 5. Structured PR Governance & Review Checklist

Provide `.github/pull_request_template.md` to enforce quality before merge:

1. **Change Classification:** Checkbox selection mapped directly to Conventional Commits:
   - `feat` (new feature)
   - `fix` (bug fix)
   - `refactor` (code reorganization without behavior change)
   - `perf` (performance optimization)
   - `test` (test suite updates)
   - `docs` (documentation updates)
   - `chore` (maintenance, build, or dependency updates)
2. **Dual-Role Verification Checklists:**
   - **Contributor Checklist:** Self-review completed, no redundant comments, linters/formatters pass, no compiler warnings, tests added, documentation/changelog updated.
   - **Reviewer Checklist:** Adheres to architecture and separation of concerns, test coverage verified, security posture preserved, backward compatibility checked.

---

## 6. Self-Documenting Workflows (`.github/workflows/README.md`)

Every project with GitHub Actions must include documentation explaining its pipelines:

* **Workflow Catalog:** Table listing each workflow file, its triggers (`push`, `pull_request`, `workflow_dispatch`), and permissions.
* **Secrets Reference:** Explicit table of required GitHub Secrets (e.g. `GITHUB_TOKEN`, registry API keys, signing certificates).
* **Branch Protection Policies:** Recommended rules for protected branches (`main`, `develop`).
* **Local Workflow Execution:** Actionable instructions on how to test workflows locally (e.g. using `act` or executing equivalent native commands).

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

When requested, scaffold a `templates/` folder in the project containing starter templates for the stack (e.g. `templates/python/script_template.py`, `templates/c_cpp/hdr_template.hpp`, `templates/c_sharp/MonoBehaviourTemplate.cs`).

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
- [ ] CI Quality Gate: `.github/workflows/ci.yml` (4 tiers: Lint, Test, Security, Build)
- [ ] Universal Release Actions & Scripts:
  - [ ] `.github/actions/parse-release-version/action.yml`
  - [ ] `.github/scripts/release/get-previous-tag.sh`
  - [ ] `.github/scripts/release/update-changelog-file.sh`
  - [ ] `.github/scripts/release/generate-release-notes-file.sh`
  - [ ] `.github/scripts/release/update-release-notes-index.sh`
  - [ ] `.github/scripts/release/build-github-release-body.sh`
  - [ ] `.github/workflows/release.yml`
- [ ] Workflow Documentation: `.github/workflows/README.md`
- [ ] Contributor & AI Governance: `README.md`, `CHANGELOG.md`, `AGENTS.md`, `.github/copilot-instructions.md`, `.github/pull_request_template.md`
- [ ] Operational Logbook: `logbook/README.md` & `logbook/current.md` (append-only)
```
