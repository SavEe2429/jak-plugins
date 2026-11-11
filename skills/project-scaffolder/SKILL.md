---
name: project-scaffolder
description: >-
  Start or scaffold a new application or project, plan its engineering foundation,
  or audit existing project structure. Also use when the user asks to build the
  first program in a new or nearly empty target. Select project-specific templates
  from evidence and requirements, then verify every planned deliverable; stop on
  material ambiguity instead of silently omitting required setup.
metadata:
  version: "3.15.0"
allowed-tools:
  - run_command
  - write_file
  - edit_file
  - read_file
  - ask_question
---

# Context-Aware Project Scaffolding

## Operating model

This package is an Agent Skill. The Agent interprets the request and repository,
decides when evidence is sufficient, presents trade-offs, and asks for approval
when needed. Scripts under `scripts/` are short-lived deterministic tools the
Agent may invoke for discovery, validation, planning, safe file writes, and
verification. They do not replace the Agent's decisions and do not run as a
separate service. A CLI is available for explicit operations, but it is an
interface to these helpers rather than the product boundary.

## Skill maintenance boundary

When this skill is being created, updated, reviewed, tested, or released, keep
all changes, fixtures, evaluations, and maintenance logs inside this skill's
own directory. Do not write skill-maintenance artifacts into the host project's
source tree, project logbook, or other skills. This boundary applies to the
skill package, not to normal scaffolding assignments: when the user explicitly
asks this skill to scaffold or update a project, write only the project files
shown in the reviewed plan and only at the user-selected target.

## Scope boundary

This skill owns project discovery, architecture and directory planning, project
files and configuration, engineering workflows, and project-level verification.
It adapts these to the project's domain, stack, topology, lifecycle, and
constraints. It does not discover or recommend AI skills, plugins, MCP servers,
or agent workflow extensions; it does not evaluate those extensions' trust or
permissions or author AI skills.

Files such as `AGENTS.md` are in scope only as project-specific instructions
for building, testing, and operating this repository. If a request includes
both project structure and AI tooling, keep those as independent workstreams
and outputs. Do not invoke or depend on another skill for AI capability work.

## Overview

Plans and generates a starting structure from the user's requirements, existing repository conventions, and explicitly selected profile/capability providers. The compatibility path writes legacy profile-declared directories, `.gitattributes`, entry points, smoke tests, and optional CI. The composition path combines declared provider file/directory contributions through the same safe writer. The pnpm and Unity UPM providers can render a manifest from an explicit dependency specification; the skill does not generate lockfiles, install tools, infer domain modules, or validate architecture boundaries automatically. Never promise those actions unless implementation is added and verified.

Profiles provide stack-specific capabilities and constraints. They are not
complete architecture decisions. Architecture selection requires project
context, and profile layouts must be selected explicitly when multiple options
are available. See [`references/architecture-decision.md`](references/architecture-decision.md).

For the `ai_data/python_pipeline` profile, declared output templates include a
uv `pyproject.toml`, development and ML dependency groups, Ruff and pytest
settings, pre-commit hooks for repository hygiene/Ruff/Markdown/Conventional
Commits, `.markdownlint-cli2.yaml`, `.editorconfig`, `.gitignore`, README,
AGENTS runbook, CONTRIBUTING guide, GitHub pull request template, and CI checks.
This list applies to that profile only. Inspect the selected profile's actual
`entry_points`, `smoke_tests`, and CI template before planning; metadata such as
`config_manifests` alone does not mean a file will be generated.

The current migration release also supports versioned declarative capability
providers under `providers/`. Use `--policy-audit` for a read-only standards,
toolchain declaration and Local/CI pin evidence, package-manager/lockfile,
package-manager CI parity, and secret-indicator report. CI parity is textual
configuration evidence only; it does not prove that CI ran or passed. Use
`--run-package-audit` only when an actual dependency audit is requested; this
may access the network. Review its command/network/write preview, then repeat
with `--confirm-command-execution` before any process is started. Its report
records command execution evidence but withholds raw output and parses findings
only for providers with a declared bounded parser; unsupported formats remain
`not-interpreted`. Use
`--check-package-lock` for the selected
provider's native lock check. It refuses missing inputs, declares whether the
check may access the network, and requires a visible preview plus
`--confirm-command-execution` before starting. It withholds raw output and
reports ambiguous non-zero results as requiring review. See
[`references/package-manager-checks.md`](references/package-manager-checks.md).
Package-manager policy reports may also include a bounded read-only lockfile
inventory for registered managers when their providers declare a parser. Treat
this as names/versions evidence only; it does not establish vulnerability or
license status, and formats that do not encode dependency edges are not
classified as direct or transitive. `--run-package-audit` uses bounded parsers
for uv, pnpm, cargo-audit, and govulncheck. Findings summarize only data reported
by the selected tool/database; `no-findings-reported` is not a safety guarantee,
and malformed or truncated output is `not-verified`. Audit reports include the
declared network policy where available. Unity UPM currently has no audit tool.
Use `--license-evidence <relative-path>` to extract declared licenses, package
identity, source references, SBOM path, and SBOM SHA-256 from a local
CycloneDX JSON document. This is provenance-bearing declaration evidence only:
the skill does not independently verify upstream claims, decide legal
acceptability, or apply an allow/deny policy. Missing license declarations are
reported as `unknown`.
Use
`--discover-units` to list nested project roots matched by registered profiles;
unknown folders are not treated as project units. Architecture providers can
contribute layout declarations. When a selected template declares compatibility
metadata, the composition planner rejects mismatches and blocks generation when
compatibility is unknown. Use `--migration-report` to inspect template-bridge
parity and whether profile policy/verification data is backed by versioned
verification providers. Layout and discovery declarations remain on the
compatibility adapter. Use
repeatable `--provider <id>` arguments to compose declared providers;
legacy profiles are exposed as `legacy-profile.<domain>.<stack>` template
providers. Their checks use IDs such as `verification.profile.systems.go`;
inspect the matching record under `providers/verification/`. Inspect the plan with `--dry-run` and pass
`--confirm-plan` before writing. Built-in package-manager records are policy
metadata; pnpm and Unity UPM additionally support manifest generation from
`--dependency-spec-json`. Review that manifest with `--dry-run`; the native
manager remains responsible for resolving and writing its lockfile. `NOT VERIFIED`
means evidence is insufficient and must not be reported as a pass.
For supported toolchains, `--set-version <provider-id>=<version>` creates a
version file only from a user-specified, provider-validated version.
Use `--verify-provider <id>` to preview that provider's exact-argv command
policy, working-directory scope, network behavior, and write effects. Commands
that may access the network or write files require a second explicit invocation
with `--confirm-command-execution`. The executor rejects argv that differs
from the provider's declared operation and rejects working directories outside
the authorized project root. Test checks require positive test-run evidence,
and reports omit raw command output. The restricted executor remains a command
policy boundary, not an OS sandbox.
Maintainers run repository-only release validation from the source checkout
with `python -B scripts/release_gate.py --package <package-directory> --eval`.
Use `--validate-only` for source-contract inspection without running tests.
The release gate reports source validation, package validation, regression tests,
behavioral evaluations, SkillSpector, human attestation, cross-platform
verification, and capability metrics independently; any required PENDING or
FAIL dimension blocks release. Every SkillSpector scan and baseline generation
must use `--no-llm`; this project has no external model API and uses static
analysis only. Do not configure, call, or require an LLM service for release
validation. The gate reads the maintainer evaluation
catalog, regression tests, and source evidence matrix; those files are
deliberately excluded from the installable Skill package. Build and smoke
test the installable package from the source checkout with
`python -B tools/build_package.py --output <directory-outside-this-skill>`.
The installed-package smoke test runs the CLI in isolated Python mode, loads the
profile/provider catalogs, and previews a dry-run against an empty temporary
workspace. After building, pass the output directory to
`python -B scripts/release_gate.py --package <package-directory>` to verify the
allowlisted file set, package metadata, and per-file SHA-256 hashes. The source
evidence matrix currently records AI-assisted review;
independent human attestation remains pending until a human reviewer completes
the review. After personally inspecting all 164 expectation mappings and the 46
shared test references, the human reviewer may record the attestation with
`python -B tools/record_human_attestation.py --reviewer "<human reviewer>" --reviewed-at YYYY-MM-DD --confirm-all-mappings-reviewed --confirm-shared-references-reviewed`.
This command records the current test-source hashes; any later source change
invalidates the attestation. Never run it on behalf of a human reviewer. A host
repository CI can invoke the source release gate; this nested Skill does not
add a host workflow.

### Fundamental Distinction: Verified Setup vs Production Ready

To prevent false confidence during early development, this skill strictly distinguishes two milestones:

1. **Verified Setup:** Only selected mandatory requirements have evidence-backed passing results. The current generator does not create or verify every possible foundation item; report its actual scope.
2. **Production Ready:** The application/game software is fully implemented, feature-complete, extensively playtested/QAed, profiled for real-world hardware, balanced, and certified for end-user deployment.

Passing applicable, selected checks does not claim the product is production ready. Keep unverified checks visible in the summary.

---

## When to Use

- A new project (or a new package/app inside an existing monorepo) needs its initial structure, and nothing meaningful exists yet.
- The user asks to "scaffold a project", "set up a new [stack] project", "bootstrap this repo", "create initial structure for", or similar.
- The user asks to create the first application/program in a new or nearly empty target, even if they do not use the word "scaffold". Use this skill for the project foundation and include requested application behavior in scope; do not stop after empty folders when the user asked for a working program.
- The user asks to "audit", "verify", or "check readiness" of an existing project scaffolding (`python scripts/scaffold.py --audit` or `--verify`).
- NOT when the user only wants recommendations or evaluation of AI skills, plugins, MCP servers, or agent tooling; that is outside this skill's scope.
- NOT when the project already has real code and structure — that is an existing codebase, not a scaffold; inspect, audit, or discover with existing code instead.
- NOT when what to build is completely undefined — scaffolding establishes _how_ code is organized, not _what_ features to invent from scratch; clarify high-level requirements first.

---

## Optional 20-Category Readiness Catalog

The 20 categories are a catalog, not a universal gate. Profiles select
`mandatory_categories` and `na_categories`; evaluate only the selected scope.
An audit is evidence-based and may report `NOT VERIFIED`. Configuration presence
does not prove successful execution. Do not claim scaffolding complete while a
mandatory check remains unverified.

```
┌────────────────────────────────────────────────────────────────────────┐
│              OPTIONAL 20-CATEGORY READINESS CATALOG                    │
├────────────────────────────┬───────────────────────────────────────────┤
│ A. Project Foundation      │ 1. Domain & Stack Alignment               │
│                            │ 2. Project & Engine Configuration         │
│                            │ 3. Asset & Resource Management            │
├────────────────────────────┼───────────────────────────────────────────┤
│ B. Architecture            │ 4. Separation of Concerns                 │
│                            │ 5. Modular Assembly / Package Boundaries  │
│                            │ 6. Architecture & Coding Standards        │
├────────────────────────────┼───────────────────────────────────────────┤
│ C. Quality Assurance       │ 7. Smoke Tests (Test Runner Verification) │
│                            │ 8. Test Coverage & Multi-Tier QA Strategy │
│                            │ 9. Error Handling & Runtime Logging       │
├────────────────────────────┼───────────────────────────────────────────┤
│ D. Development Workflow    │ 10. Pre-commit Hooks                      │
│                            │ 11. Git Hygiene & Normalization           │
│                            │ 12. GitHub Community & CI Parity          │
│                            │ 13. Build & Deployment Pipeline           │
├────────────────────────────┼───────────────────────────────────────────┤
│ E. Project Contributor Ops │ 14. Project Runbook (AGENTS.md)           │
│                            │ 15. Project Logbook (Append-Only)         │
├────────────────────────────┼───────────────────────────────────────────┤
│ F. Project Management      │ 16. Changelog Tracking (Keep-a-Changelog) │
│                            │ 17. Tailored Documentation Suite (Docs/)  │
├────────────────────────────┼───────────────────────────────────────────┤
│ G. Performance & Security  │ 18. Scoped Performance & Resource Profiling │
│                            │ 19. Security & Repository Hygiene         │
├────────────────────────────┼───────────────────────────────────────────┤
│ H. Documentation Standards │ 20. Project-Specific Documentation Rules  │
└────────────────────────────┴───────────────────────────────────────────┘
```

---

## Architecture and adapter boundaries

To support different domains without overclaiming, apply these 13 architecture and evidence rules:

1. **Domain-Agnostic Core:** Generic contracts, registry, resolver, composer, and writer must not branch on stack names.
2. **Provider Data:** Built-in capability providers are declarative JSON and validated before selection. Do not load executable provider code.
3. **Compatibility Adapter:** `StackAdapter` and existing profiles remain supported while profile migration is incomplete.
4. **Evidence-Based Discovery:** Score provider/profile markers; do not select the first match. Weak or ambiguous evidence blocks automatic selection.
5. **Separate Architecture from Stack:** Choose layouts from requirements and user-confirmed tradeoffs. A framework name alone does not choose architecture.
6. **Honest Scope:** A declared check or policy is not a passed check. Report `NOT VERIFIED` when execution or semantic comparison is unavailable.
7. **Encapsulated Entry Points & Interfaces:** Application entry points (`cli.py`, `main.py`, `__main__.py`) and user interfaces (HTML/CSS/JS frontend assets under `interfaces/ui/`) must reside within the canonical package namespace (`src/<package_name>/` or language-equivalent `code/<package_name>/`). Never place executable entrypoint scripts or loose UI folders in the project root.
8. **Native Package-Manager Runner:** When a project uses a modern package manager (e.g. uv, pnpm, cargo), execute all development, testing, linting, and build commands through the manager's native runner (`uv run`, `pnpm exec`, `cargo run`). Never call virtual-environment binaries directly through platform-dependent paths (such as `.venv/Scripts/python.exe`).
9. **Runtime State & Database Isolation:** Runtime databases (e.g. SQLite `*.db` files), caches, and state logs must never sit loose in the project root. They must be placed in a dedicated data directory (e.g. `data/`) or platform user-state directory that is explicitly excluded from version control in `.gitignore`.
10. **Single Source of Truth (SSOT) for Attributes and Configuration:** Shared configuration, system attributes, environment variables, and filesystem anchors must be centralized in a dedicated configuration module/struct (e.g. `core/config.py`, `src/config/`, `internal/config/`). Components must never read environment variables directly or duplicate hardcoded attributes across multiple files. The package manifest is the SSOT for project version and metadata.
11. **Test Suite Partitioning & Hermetic Isolation:** Automated test suites must not be monolithic or flat. Test directories must be partitioned into `tests/unit/` (pure logic, mocked, sub-second execution) and `tests/integration/` (multi-component, I/O, database, or external service lifecycles). Tests must be hermetically isolated: test executions must never write persistent test artifacts or databases into the repository tree; they must use ephemeral temporary directories (e.g. `tmp_path`, `t.TempDir()`) or in-memory fixtures.
12. **Granular Exception Handling & Explicit Error Boundaries:** Domain logic, data parsing, and I/O subroutines must never use blind catch-all exceptions (`except Exception:`, `catch (e: any)`). They must catch specific, granular exception types (e.g. `OSError`, `FileNotFoundError`, `PermissionError`, `TimeoutError`, `ValueError`). Catch-all handlers are permitted exclusively at outer system boundaries (e.g. top-level CLI loop, ASGI global exception middleware) to format client responses and record structured crash telemetry with full tracebacks. Root causes must be preserved using standard exception chaining.
13. **Clean Shutdown & Graceful Resource Lifecycle:** Long-running services, daemons, and application controllers must register signal traps for OS termination events (`SIGINT`, `SIGTERM`). Entry points must provide clean lifecycle hooks or context managers to release resources (close database connection pools, flush log buffers, terminate child processes, release file locks) before exiting, preventing corrupted state and zombie processes.
14. **Dynamic LTS / Latest Stable Version Policy & Multi-Job CI Gate:** Never hardcode memorized or stale version numbers for runtimes, dependencies, linters, or CI Actions. Resolve active **LTS (Long-Term Support)** or **Latest Stable** releases dynamically at scaffolding/audit time, and configure CI workflows to read toolchain versions directly from the repository's SSOT manifest or version-pin files (`pyproject.toml`, `.python-version`, `go.mod`, `.nvmrc`, `rust-toolchain.toml`, `global.json`). Structure CI pipelines as a multi-job DAG (`code-quality`, `test`, `build`, `summary`) ending with a dual-audience summary gate (`$GITHUB_STEP_SUMMARY` table for humans + `exit 1` failure enforcement for branch protection).

---

## Modular Skill Architecture

The skill is cleanly partitioned into a Domain-Agnostic Core, an Adapter Layer, Declarative Profiles, and Deep Reference Guides:

```text
project-scaffolder/
├── SKILL.md                          # Main instruction runbook
├── manifest.json                     # Skill identity and version metadata
├── CHANGELOG.md                      # Release history
├── providers/                        # Versioned declarative capability records
│   ├── package_manager/              # uv, pnpm, Cargo, Go Modules, Unity UPM
│   ├── standards/                    # Applicable standard metadata
│   ├── toolchain/                    # Runtime version declaration metadata
│   └── verification/                 # Profile-backed checks and readiness policy
├── references/                       # Deep architectural references
│   ├── architecture-catalog.md       # Modular Monolith, Clean, Layered, DOD/ECS
│   ├── architecture-decision.md      # Requirement-led pattern selection and tradeoffs
│   ├── domain-requirements.md        # 20-category conditional matrix & N/A rules
│   ├── enterprise-standards.md       # Dual-tier docs, Docker/Devcontainer, Observability, CODEOWNERS
│   ├── repository-governance.md      # Multi-tier CI, SemVer release automation, PR & AI guidance
│   ├── release-packaging.md          # Distribution targets, packaging/ & out/ standards
│   ├── stack-detection.md            # 3-Axis discovery model (Domain x Stack x Topology)
│   ├── verification-matrix.md        # Evidence-based verification rules
│   └── generation-safety.md          # Dry-run, conflict detection, backup, idempotency
├── scripts/
│   ├── core/                         # GENERIC CORE ENGINE (100% Domain-Agnostic)
│   │   ├── contract.py               # StackAdapter ABC & data models
│   │   ├── capability_registry.py    # Versioned declarative provider catalog
│   │   ├── capability_resolver.py    # Evidence scores and ambiguity handling
│   │   ├── composition.py            # Provider contributions to CompositionPlan
│   │   ├── policy_audit.py           # Read-only package/toolchain/security checks
│   │   ├── verification.py           # Provider-declared evidence checks
│   │   ├── engine.py                 # Core scaffolding orchestrator
│   │   ├── registry.py               # Dynamic adapter/profile loader
│   │   ├── safe_executor.py          # Allowlisted commands with bounded output
│   │   ├── io_utils.py               # Strict LF, safe backup, file hashing
│   │   └── audit_engine.py           # 20-category contract evaluator
│   ├── adapters/                     # EXTENSIBLE ADAPTER LAYER
│   │   └── profile_adapter.py        # Generic Profile-to-Adapter bridge
│   ├── contracts/                    # Versioned models, ports, and validation
│   ├── discover.py                   # 3-Axis discovery CLI
│   ├── scaffold.py                   # Master scaffolding CLI
│   ├── audit.py                      # 20-category readiness auditor CLI
│   ├── verify.py                     # Dynamic evidence-based test runner CLI
│   └── release_gate.py               # Package/eval validation and regression gate
├── profiles/                         # Compatibility layout and discovery declarations
│   ├── game/ (unity.json, godot.json)
│   ├── embedded/ (platformio.json, esp_idf.json)
│   ├── web/ (nextjs.json, fastapi.json)
│   ├── systems/ (rust.json, go.json, zig.json)
│   ├── ai_data/ (python_pipeline.json)
│   └── security/ (python_tooling.json)
└── evals/                            # Comprehensive multi-stack test matrix
    └── evals.json                    # Evaluation fixtures
```

---

## 4 Critical Engineering Nuances

1. **Smoke Tests $\neq$ Full Coverage:**
   - Passing smoke tests only confirms that the test harness, compiler, and build system work. It is _not_ a substitute for comprehensive test coverage.
2. **Pre-commit + CI Parity:**
   - When both are configured, compare their actual commands. The current generator does not create pre-commit configuration and the auditor does not prove parity.
3. **Logbook Immutability:**
   - `logbook/current.md` rotates to `YYYY-MM-DD_logbook.md` when exceeding 500 lines. Rotated historical logs are **strictly immutable archives** and must never be altered retroactively. File presence or non-empty content does not prove append-only behavior; Category 15 remains `NOT VERIFIED` until enforcement and preservation evidence are inspected, while an empty or missing log is `FAIL`.
4. **Scoped Performance & Resource Profiling:**
   - Strict resource constraints (e.g. Zero GC in game loops, no heap allocation in interrupt service routines, low-latency async in backend endpoints) are enforced where applicable; standard or small utility projects mark this category as `NOT APPLICABLE` without readiness penalty.

---

## The 4 Audit Statuses

- **`[PASS]`**: Requirement verified with tangible evidence (command exit code 0 or validated artifact).
- **`[FAIL]`**: Requirement failed verification, threw compiler errors, or is missing.
- **`[NOT VERIFIED]`**: Prerequisite files exist, but the execution environment/tool is unavailable.
- **`[NOT APPLICABLE]` (N/A)**: Requirement is irrelevant to this specific domain/stack (does not penalize readiness score).

## Evaluation Evidence Contract

Every behavioral expectation in `evals/evals.json` must have exactly one explicit
`expectation_evidence` mapping keyed by the full expectation text. Evidence order
must never determine which expectation passes. Each mapping must contain non-empty
references and `reviewed: true` only after a human has checked that the referenced
test assertions actually prove that expectation. A migrated or generated mapping
must remain `reviewed: false` until that review is complete.

The runner fails closed for missing, duplicate, invalid, unreviewed, or reused
evidence unless reuse is explicitly justified with `allow_shared_evidence: true`.
Declaration/file-presence anchors are structural references only and cannot prove
runtime behavior. Test references must resolve to Python files inside `tests/`.
The release gate rejects unreviewed mappings and unresolved evidence references.
Do not report an evaluation pass rate as meaningful until all mappings are reviewed
and the adversarial evaluation-runner tests pass.

---

## Step-by-Step Execution Process

### Required Project Checklist

For a new project or initial scaffold, copy this checklist into the reviewed
plan with all applicable tasks unchecked. Mark an item `[x]` only after its
deliverable is created and verified. Keep an inapplicable item as a standard
unchecked box with a reason, for example `- [ ] N/A: project has no GitHub
remote, so no GitHub PR template is generated`. Never silently omit an
applicable item or mark it complete based only on a profile declaration;
verify the planned file exists and contains the expected configuration after
generation.

- [ ] User goal, domain, language/stack, target path, and requested behavior are captured; explicit user choices take precedence over unrelated parent-repository markers.
- [ ] Matching profile/provider and its real generated files are inspected; every relevant template is included in the output plan.
- [ ] Project structure and architecture are proportionate to the stated requirements; unresolved choices are surfaced rather than guessed.
- [ ] Package manager, runtime, manifest, dependency groups, and lockfile plan are explicit; Python packages declare modern build backends (e.g. hatchling) to keep the source tree clean from legacy metadata; dependencies are not installed unless requested.
- [ ] A test runner and at least one meaningful project-specific test are planned when the request requires runnable code.
- [ ] Applicable formatter/linter, pre-commit hooks (.pre-commit-config.yaml with detect-private-key, conventional-commits, and LF enforcement), Markdown lint (.markdownlint.yaml), and code formatter (.prettierrc.yaml with proseWrap) are planned; follow references/repository-governance.md.
- [ ] CI runs the declared tests and quality checks with the selected package manager, reads toolchain versions from the repository's SSOT manifest/version file, and uses verified LTS or Latest Stable Action/toolchain versions; report textual parity separately from an executed CI result. Follow references/repository-governance.md for multi-job DAG quality gates (`code-quality`, `test`, `build`, `summary` with `$GITHUB_STEP_SUMMARY` + `Enforce Overall Gate`) and self-documenting workflow README (.github/workflows/README.md).
- [ ] Universal GitHub Release actions and scripts are planned across all stacks (.github/actions/parse-release-version/action.yml, .github/scripts/release/*.sh, and .github/workflows/release.yml) for SemVer branch parsing, changelog promotion, and checksum generation.
- [ ] Starter code and module templates follow the standardized 9-section template layout (imports, constants, enums, classes, public/private functions, main execution); when requested, plan a `templates/` directory containing pure skeleton templates without dummy runtime classes.
- [ ] GitHub projects receive a PR template (.github/pull_request_template.md with dual contributor/reviewer checklists), AI developer instructions (.github/copilot-instructions.md aligned with AGENTS.md), and team governance (.github/CODEOWNERS and structured YAML Issue Forms in .github/ISSUE_TEMPLATE/); Git projects receive a documented commit convention and a matching commit-message check when the selected profile supports it.
- [ ] Enterprise documentation architecture (references/enterprise-standards.md) is planned with dual-tier hierarchy (docs/internal/ for design/dev/PM, docs/public/ for user manuals and release notes) and portal configuration (mkdocs.yml); public API specifications are omitted unless the project explicitly exposes external API endpoints.
- [ ] Containerization and reproducible development environments (references/enterprise-standards.md) are planned when applicable: multi-stage Dockerfile with non-root appuser, .dockerignore, and .devcontainer/devcontainer.json.
- [ ] Enterprise observability and logging standards (references/enterprise-standards.md) are planned: structured JSON logging on production runtimes and liveness/readiness health probes (/healthz, /readyz) for service workloads.
- [ ] Supply chain security and repository compliance (references/enterprise-standards.md) are planned: SECURITY.md policy, automated dependency updates (.github/dependabot.yml), and secret leak scanning (.gitleaks.toml).
- [ ] Configuration adheres to 12-Factor multi-environment SSOT: provide a non-secret environment example and inject deployment secrets through the platform's environment/secret manager; never generate or commit real deployment environment files.
- [ ] Entry points and presentation interfaces are encapsulated within the package namespace (e.g. src/<package_name>/cli.py, interfaces/ui/); the project root contains no executable entrypoint scripts or loose UI asset folders.
- [ ] Runtime state and databases (e.g. SQLite *.db files) reside in dedicated directories (e.g. data/) and are explicitly ignored in .gitignore; the project root contains no runtime databases.
- [ ] Configuration, system attributes, runtime paths, and environment variables are centralized in a Single Source of Truth (SSOT) config module/struct; components do not read raw environment variables or scatter hardcoded settings across multiple files.
- [ ] Test suites are partitioned into dedicated categories (e.g. tests/unit/ and tests/integration/) and execute within hermetic, ephemeral temporary environments without polluting the repository tree.
- [ ] Subroutines and business logic practice granular exception handling without blind catch-alls; top-level outer boundaries capture unhandled exceptions with full tracebacks and preserve root-cause chains.
- [ ] Long-running entry points and service controllers incorporate graceful shutdown handlers for OS termination signals (SIGINT, SIGTERM) and cleanly release shared resources.
- [ ] Toolchain execution uses the selected package manager's native runner (e.g. uv run, pnpm exec, cargo run); commands and runbooks do not invoke virtualenv binaries via hardcoded filesystem paths.
- [ ] README or runbook explains setup, test, quality, and data/artifact handling commands.
- [ ] Release packaging and SemVer release orchestration are classified as applicable, undecided, or N/A; when automated releases are planned, follow references/repository-governance.md for branch triggers, changelog promotion, and artifact checksums. For binary deliverables (e.g. PyInstaller, native executables), build definitions reside in `packaging/`, outputs target `out/<package_name>/`, and the user selects between `onedir` and `onefile`.
- [ ] If `logbook/` is planned, `logbook/README.md` and `logbook/current.md` exist; generated or tailored root `AGENTS.md` points future agents to the logbook instructions.
- [ ] Generated artifacts, private/raw data, secrets, and model outputs have explicit ignore/retention rules where applicable.
- [ ] Dry-run output, actual generated file list, conflicts, and post-generation verification are compared; every planned deliverable has a final status.

If the selected profile lacks an applicable template, add a tailored file to
the reviewed plan when requirements are sufficient. Otherwise mark it
`NOT VERIFIED` with the reason or ask the user when a missing decision changes
the structure. Do not silently substitute hand-written application code for
the profile's engineering templates, or vice versa.

When a selected profile includes a `logbook/` directory, the compatibility
adapter generates `logbook/README.md` and `logbook/current.md`, plus a root
`AGENTS.md` pointer when the profile does not already provide one. Existing
profile runbook templates receive the pointer as well. The guide defines
append-only entries, required evidence, the 500-line rotation rule, and
immutable archives. For an existing project with a conflicting root runbook,
include a safe tailored merge in the reviewed plan; never overwrite it
silently. A logbook directory alone is not an operating instruction.

Plan release packaging only after classifying the intended distribution. A
Unity game build, a reusable Unity UPM package, and a package for another
registry need different layouts and release workflows. For binary deliverables
(e.g., PyInstaller, native executables), place all build scripts, spec files,
and icon/version assets in `packaging/`, configure the output destination at
`out/<package_name>/`, prompt the user to select between `onedir` and `onefile`
packaging modes, and ensure `out/` and `build/` are excluded in `.gitignore`.
Follow [`references/release-packaging.md`](references/release-packaging.md). Package
manager manifests and lockfiles do not by themselves provide release
packaging. Do not create publish workflows, signing steps, or release
directories when distribution is out of scope or undecided.

### Step 1: Requirement and Repository Discovery

- Run discovery: `python scripts/discover.py <target-dir>`
- Inspect project purpose, users, domain boundaries, scale, lifecycle, deployment, safety/security constraints, and existing conventions.
- Inspect matched marker evidence and profile confidence. If unknown, weak, conflicting, or multi-stack, stop and ask for clarification; do not use the generic fallback to invent `src/`, `tests/`, `Docs/`, or `logbook/`.
- Distinguish repository topology (monorepo) from application architecture (layered, modular monolith, etc.). Treat topology as `unknown` if evidence is insufficient.
- Use `references/architecture-decision.md` to propose a proportionate architecture with tradeoffs. Ask the user to select or confirm before generating when the choice materially changes layout.
- Keep discovery focused on project structure and engineering needs. Do not
  inventory, recommend, or evaluate AI extensions as part of this workflow.
- If marker files are absent, use explicit user requirements to select the domain/stack; absence of markers alone is not ambiguity. Ask only when both requirements and target evidence leave a material decision unresolved.
- Inspect the selected profile's file-producing fields (`entry_points`, `smoke_tests`, CI/template contributions) and map each applicable checklist item to a concrete file or a stated N/A.
- Classify distribution lifecycle before planning release paths: app/game binary, reusable package/library, plugin/asset package, or no release packaging in scope. When binary packaging is chosen, prompt the user to select between `onedir` (directory bundle) and `onefile` (single standalone binary). Surface a decision when the release target changes the layout.
- Inspect potential file conflicts.

### Step 2: Confirm Plan with User

- Present the planned directory layout and an actionable checkbox list of concrete config/templates, tests, quality checks, CI, documentation, PR, and commit-convention outputs. State which items will be generated by the profile and which need a tailored contribution.
- Include a conditional release-package layout and workflow when the distribution target is known; identify deliverables not generated by the selected profile/provider as tailored or NOT VERIFIED.
- Wait for user confirmation before writing to disk.

### Step 3: Safe Generation & Scaffolding

- Review the generation plan first: `python scripts/scaffold.py --target-dir <dir> --dry-run`.
- Generate only after the user confirms the architecture/layout plan; pass `--confirm-plan` so the CLI records that approval gate.
- Existing differing files are preserved and block the run. Use `--force` only after explicit overwrite approval; conflicting files are backed up before replacement. Identical files are skipped.
- Generated paths are constrained to the target directory and files are replaced atomically.
- The compatibility route writes profile-declared directories, `.gitattributes`, entry points, smoke-test source files, append-only logbook instructions and a runbook pointer when `logbook/` is declared, and optional CI. The provider route writes only files declared by selected template providers. Neither route installs dependencies or creates the full documentation, pre-commit, or changelog suite by default.
- After writing, inspect the target tree against the reviewed checkbox plan. A successful CLI exit does not prove that all requested templates were included; report missing or unverified items explicitly and complete applicable tailored files before handoff.

### Step 4: Verification & Audit

1. Run static audit: `python scripts/scaffold.py --audit --target-dir <dir>`
   - Evaluates profile-selected categories and reports `NOT VERIFIED` where command execution or stronger evidence is required.
2. Preview dynamic verification: `python scripts/scaffold.py --verify --target-dir <dir>`
   - Shows the selected profile's test/build commands and declared side effects without starting a process. After reviewing the preview, repeat with `--confirm-command-execution` to run it.
   - The confirmed run executes line-ending checks, pre-commit hooks, stack test runner, and configured build checks. CLI exit codes are `0 = PASS`, `1 = FAIL`, and `2 = INCOMPLETE`; a test summary must report at least one passing test, and zero-test output is not assertion evidence.
3. Run read-only capability policy review: `python scripts/scaffold.py --policy-audit --target-dir <dir>`
   - Reports package-manager ambiguity, lockfile state, declared toolchains, supported CI evidence, applicable standards, and secret indicators. It does not install or update tools. Incomplete comparisons stay `NOT VERIFIED`.
4. Run provider-declared verification when required: `python scripts/scaffold.py --verify-provider <provider-id> --target-dir <dir>`
   - Executes only allowlisted binaries, requires declared evidence, and reports structured status without raw output.
   - The Safe Executor is a command-policy boundary, not an OS sandbox: child processes inherit the current user's privileges. Do not run untrusted code or profiles; use an OS/container sandbox with least privilege for that threat model.
   - Timeout and output-limit termination target the child process tree (POSIX process group; Windows taskkill /T when available). Temporary-file spool size is monitored and can overshoot between polling intervals; it is not an OS-enforced disk quota.
   - Interpreter inline-code flags are rejected, and output is spooled to temporary files before bounded excerpts are returned.

### Step 5: Hand Off & Logbook Recording

- Append honest execution summary to `logbook/current.md`.
- Present verified, failed, unverified, and not-applicable counts separately. Never label incomplete evidence as `Scaffolding Complete`.

---

## Red Flags

- [ ] Declaring "Production Ready" when only scaffolding infrastructure is complete.
- [ ] Counting file presence as evidence of passing smoke tests without running the test runner.
- [ ] Overwriting existing files without dry-run, backup, or explicit user approval.
- [ ] Forcing Unity directory structures onto Godot or other engines.
- [ ] Fabricating test execution history in `logbook/current.md`.
- [ ] Missing Pre-commit + CI parity.
- [ ] Emojis present in any generated technical markdown document.
- [ ] Dogmatically enforcing Zero GC on cold paths like UI opening or startup configs.
