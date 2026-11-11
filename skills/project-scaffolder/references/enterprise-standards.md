# Enterprise Engineering Standards & Scaffolding Guidelines

Use this reference when designing, scaffolding, or auditing enterprise-grade repositories. Enterprise scaffolding ensures that projects are born production-ready, secure, observable, maintainable, and aligned with team-scale governance.

---

## 1. Dual-Tier Documentation Portal Architecture

Enterprise documentation separates internal engineering/operational knowledge from public user-facing documentation to prevent IP/security leakage while remaining export-ready for static site generation.

```text
docs/
├── internal/                          # Internal Engineering & Project Management
│   ├── design/                        # Architecture design (PRDs, flowcharts, RFCs)
│   ├── development/                   # Step-by-step developer onboarding (Numbered)
│   │   ├── 01.getting_started.md
│   │   ├── 02.environment.md
│   │   ├── 03.architecture.md
│   │   ├── 04.testing.md
│   │   ├── 05.deployment.md
│   │   └── 06.troubleshooting.md
│   └── pm/                            # Delivery governance (Roadmap, milestones, sprints, SLA)
└── public/                            # User-Facing & Customer Documentation
    ├── manual/                        # End-user guides & operational manuals
    ├── release-notes/                 # Immutable versioned release notes (vX.Y.Z.md)
    └── index.md                       # Documentation portal homepage
mkdocs.yml                             # Static site generator configuration (Material for MkDocs)
```

> **API Specs Policy:** API Specifications (`docs/public/api/` or OpenAPI/Swagger definitions) are **conditional/optional**. Only generate API documentation when the deliverable explicitly provides an external HTTP, gRPC, or public library API. Standalone CLIs, desktop apps, games, or internal data pipelines omit API specs.

---

## 2. Containerization & Developer Environments

Ensure 100% reproducible execution across local machines, CI runners, and cloud infrastructure:

### Multi-Stage `Dockerfile`

- **Builder Stage:** Compiles code and downloads dependencies.
- **Runtime Stage:**
  - Uses minimal base images (Distroless, Alpine, or Debian-slim).
  - Enforces an unprivileged non-root user (`USER appuser`, UID 10001).
  - Contains strictly runtime artifacts (no compilers, test runners, or dev dependencies).
  - Explicit health check instruction (`HEALTHCHECK`).

### `.dockerignore`

Excludes build caches, virtual environments, VCS metadata, tests, documentation, and local state:

```text
.git
.github
.venv
.pytest_cache
__pycache__
tests/
docs/
data/*.db
logs/*.log
.env*
!.env.example
```

### `.devcontainer/devcontainer.json`

Provides a zero-friction, containerized development environment for VS Code and GitHub Codespaces with pre-installed linters, extensions, and pinned runtimes.

---

## 3. Observability & Structured Logging

Enterprise applications must emit telemetry that is machine-parseable by centralized log collectors (ELK, Datadog, Grafana Loki, CloudWatch):

1. **Structured JSON Logging:**
   - Log messages must format as structured JSON on production runtimes with required fields:
     `{"timestamp": "2026-11-03T12:00:00Z", "level": "INFO", "service": "my-service", "trace_id": "...", "message": "...", "context": {}}`
   - Disallow unstructured stdout `print()` or plain text logs in service entrypoints.
2. **Service Health Probes (Microservices / Web Services):**
   - Provide standard probe endpoints:
     - `/healthz` (Liveness probe: verifies process is running and not deadlocked).
     - `/readyz` (Readiness probe: verifies dependencies like database/cache are reachable before taking traffic).

---

## 4. Supply Chain Security & Repository Compliance

Protect the repository against malicious dependencies, credentials leakage, and vulnerability drift:

1. **`SECURITY.md`:**
   - Declares the project's Vulnerability Disclosure Policy, supported release versions, response SLAs, and dedicated security contact.
2. **`.github/dependabot.yml`:**
   - Schedules automated weekly vulnerability scans and dependency version bumps for package manifests and GitHub Actions workflows with cooldown periods (e.g. 7 days).
3. **Secret Leak Prevention (`.gitleaks.toml` & TruffleHog):**
   - Configures pre-commit and CI scans with Gitleaks / detect-private-key.
   - For CI secret verification, use TruffleHog OSS (`trufflesecurity/trufflehog`) with `fetch-depth: 0` and `--results=verified` to eliminate noisy unverified false positives.
4. **GitHub Actions Workflow Static Security Analysis (`.github/workflows/zizmor.yml`):**
   - Runs `zizmorcore/zizmor-action` on PRs and main pushes to statically analyze GitHub Actions workflows for token leaks, code injection vulnerabilities, unpinned third-party actions, and permission escalation risks.
5. **Scheduled Vulnerability Drift Detection (`.github/workflows/osv-scanner.yml`):**
   - Uses `google/osv-scanner-action` on a weekly schedule (`cron: "30 12 * * 1"`) to scan locked dependency trees (`uv.lock`, `package-lock.json`, `pnpm-lock.yaml`, `Cargo.lock`, `go.sum`). Uploads SARIF results to GitHub Code Scanning so newly disclosed CVEs surface without requiring code commits.
6. **OpenSSF Scorecard Supply-Chain Audit (`.github/workflows/scorecard.yml`):**
   - Runs weekly OpenSSF Scorecard analysis to track branch protection health, dangerous workflow patterns, token permissions, and maintenance signals; publishes results using OIDC.
7. **Containerized Multi-Language SAST Scanning (Semgrep):**
   - Runs Semgrep CE inside official Docker container images (`semgrep/semgrep`) with default community rulesets (`p/default`). Applied advisory-first (`continue-on-error: true`) until a clean baseline is confirmed.
8. **Build Provenance & Cryptographic Attestation (SLSA / Sigstore):**
   - In production release workflows, generate cryptographic build attestations for release assets using `actions/attest-build-provenance` backed by GitHub's Sigstore OIDC infrastructure, guaranteeing artifact provenance and tampering resistance.

---

## 5. Team Governance & Access Control

Enable smooth collaboration across multi-developer and multi-team organizations:

1. **`.github/CODEOWNERS`:**
   - Automates review requests based on domain boundaries:

     ```text
     *                   @engineering-team
     /.github/           @devops-team
     /docs/              @tech-writers
     /src/core/          @architect-team
     ```

2. **`.github/ISSUE_TEMPLATE/` (GitHub Issue Forms YAML):**
   - Prefer structured **GitHub Issue Forms (`.yml`)** over plain Markdown (`.md`) templates so GitHub renders interactive UI controls (`dropdown`, `input`, `textarea` with `render: shell`, `checkboxes`) and enforces server-side required fields (`validations: required: true`):
     - `bug_report.yml` (Component dropdown, version/OS inputs, steps to reproduce, expected vs actual behavior, auto-formatted shell logs, pre-submission checkboxes).
     - `feature_request.yml` (Problem statement, proposed solution, target component dropdown, alternative designs).
     - `config.yml` (Controls `blank_issues_enabled` and adds `contact_links` directing security reports to `SECURITY.md` or user support to documentation/Discussions).

---

## 6. Multi-Environment SSOT Configuration

Adhere to 12-Factor App methodology for application configuration:

1. **Layered Configuration Files:**
   - `.env.example`: Public template declaring all required variables and documentation.
   - `.env.development`: Safe local development defaults.
   - `.env.production`: Production skeleton requiring external secret injection (vault/environment).
2. **Strict Resolution Hierarchy (SSOT):**
   1. Explicit Command-line arguments / flags
   2. System Environment Variables (`os.environ`)
   3. Loaded `.env` file for the active environment
   4. Typed schema defaults in `core/config.py` (or ecosystem equivalent)
