# Context-Aware Architecture Decision

Stack identifies available tools and constraints. Architecture describes how
responsibilities and boundaries are organized. Never infer the latter solely
from the former.

## Discover before selecting

For a new project, establish only the requirements that can change the layout:

- [ ] Product purpose, primary users, and core workflows.
- [ ] Domain boundaries, data ownership, and external integrations.
- [ ] Expected scale, latency, availability, and resource constraints.
- [ ] Deployment units, team ownership, and independent release needs.
- [ ] Security, privacy, safety, and compliance constraints.
- [ ] Expected lifetime and likely sources of change.
- [ ] Stack constraints and required verification.

For an existing project, inspect current package boundaries, dependency
direction, deployment model, and conventions first. Extend the current design
unless the user asks for a redesign or evidence shows a concrete problem.

If important requirements are unknown or conflict, record the uncertainty and
present a short set of architecture options with tradeoffs. Do not generate a
layout until the user selects or confirms an option.

## Choose the simplest architecture that meets requirements

| Pattern                 | Consider when                                                                      | Cost / risk to explain                                                           |
| ----------------------- | ---------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Small service / minimal | Few workflows, one deployable, limited domain complexity                           | Boundaries may need to emerge as the project grows                               |
| Layered                 | Request flow and responsibilities are stable and straightforward                   | Layers can become pass-through abstractions                                      |
| Modular monolith        | Several cohesive domain areas need enforceable boundaries but share one deployment | Requires module ownership and dependency rules                                   |
| Clean / hexagonal       | Core business rules must stay independent of frameworks or external services       | More interfaces and indirection to maintain                                      |
| Event-driven            | Producers and consumers need temporal or deployment decoupling                     | Delivery order, duplication, retries, and observability become explicit concerns |
| Data-oriented / ECS     | Measured throughput or memory layout requirements justify data-centric processing  | More specialized concepts and authoring workflow                                 |
| Microservices           | Independent deployment, scaling, or ownership is a real requirement                | Network failures, operations, data consistency, and deployment complexity        |

These are prompts for reasoning, not a universal allow-list. Combine patterns
only when separate requirements justify the added boundaries. A monorepo is a
repository topology, not an application architecture.

## Canonical Package Layout and Clean Root Policy

Regardless of the chosen architectural pattern:

1. **Clean Root Policy:** Never place executable entrypoint scripts (`main.py`, `cli.py`, `app.py`) or loose UI asset directories in the root directory. The project root is reserved for manifests, repository configuration, documentation, tests, and build tooling.
2. **Canonical Package Root (`src/<package_name>/` or `code/<package_name>/`):** All application logic, executable entry points, and presentation assets must be encapsulated within the package namespace.
3. **Layer Separation (Clean Architecture Alignment):**
   - `core/`: Core business logic, configuration, runtime state, domain rules.
   - `models/`: Data entities, schemas, DTOs, value objects.
   - `interfaces/`: Presentation interfaces, UI assets (`interfaces/ui/`), API routes (`interfaces/api/`), abstract protocols, and contracts.
   - `components/` (or `tools/` / `services/`): Concrete adapters, tool implementations, and infrastructure integrations.
   - Entry points: `cli.py` (CLI entry point for console scripts), `__main__.py` (module execution via `uv run python -m <package_name>`), `app.py` / `main.py` (HTTP/Service application factory).
4. **Native Toolchain Runner Exclusivity:** Always invoke tools via the package manager's runner (`uv run`, `pnpm exec`, `cargo run`). Never reference virtual-environment interpreter paths directly.
5. **Binary Release Packaging Alignment:** Build tooling resides in `packaging/`, compiles the encapsulated entrypoint (`src/<package_name>/cli.py`) with embedded `interfaces/ui/` assets, and emits binary outputs to `out/<package_name>/` based on the user-selected mode (`onedir` or `onefile`).
6. **Runtime State and Database Isolation:** Runtime databases (e.g. SQLite `*.db` files), caches, and ephemeral state must never reside in the project root. They must be stored in a dedicated data directory (e.g. `data/`) or platform user-state directory that is explicitly excluded from version control in `.gitignore`. Paths to runtime state must be anchored to the project root or configurable via environment variables, never hardcoded as naive relative strings.
7. **Modern Build Backend (PEP 517 / PEP 621):** Python packages using `pyproject.toml` must declare a modern build backend (such as Hatchling: `[build-system] requires = ["hatchling"] build-backend = "hatchling.build"`). Without an explicit build system, build invocations default to legacy setuptools which pollutes `src/` with `*.egg-info` directories.
8. **Single Source of Truth (SSOT) for Attributes and Configuration:** Shared configuration, system attributes, environment variables, and filesystem anchors must be centralized in a dedicated configuration module/struct (e.g. `core/config.py`, `src/config/`, `internal/config/`). Components must never read environment variables directly or duplicate hardcoded attributes across multiple files. The package manifest (`pyproject.toml`, `package.json`, `Cargo.toml`) serves as the SSOT for project version and metadata.
9. **Test Suite Partitioning & Hermetic Isolation:** Automated test suites must not be monolithic or flat. Test directories must be partitioned into `tests/unit/` (pure logic, mocked, sub-second execution) and `tests/integration/` (multi-component, I/O, database, or external service lifecycles). Tests must be hermetically isolated: test executions must never write persistent test artifacts or databases into the repository tree; they must use ephemeral temporary directories (e.g. `tmp_path`, `t.TempDir()`) or in-memory fixtures.
10. **Granular Exception Handling & Explicit Error Boundaries:** Domain logic, data parsing, and I/O subroutines must never use blind catch-all exceptions (`except Exception:`, `catch (e: any)`). They must catch specific, granular exception types (e.g. `OSError`, `FileNotFoundError`, `PermissionError`, `TimeoutError`, `ValueError`). Catch-all handlers are permitted exclusively at outer system boundaries (e.g. top-level CLI loop, ASGI global exception middleware) to format client responses and record structured crash telemetry with full tracebacks. Root causes must be preserved using standard exception chaining.
11. **Clean Shutdown & Graceful Resource Lifecycle:** Long-running services, daemons, and application controllers must register signal traps for OS termination events (`SIGINT`, `SIGTERM`). Entry points must provide clean lifecycle hooks or context managers to release resources (close database connection pools, flush log buffers, terminate child processes, release file locks) before exiting, preventing corrupted state and zombie processes.

### Single Source of Truth (SSOT) Architecture Pattern

To prevent attribute duplication, drift, and shotgun surgery when changing settings:

| Layer | SSOT Mechanism | Anti-Pattern to Avoid |
| :--- | :--- | :--- |
| **Runtime Attributes & Settings** | Central typed schema/struct (e.g., Pydantic `BaseSettings`, Zod config, Serde `Config`, Go `struct`) loaded once at startup. | Scattered `os.environ.get()` calls or hardcoded constants in handlers/submodules. |
| **Project Identity & Version** | The package manifest (`pyproject.toml`, `package.json`, `Cargo.toml`) is the authoritative source. CLI flags (`--version`) and docs read dynamically from package metadata. | Hardcoded version strings duplicated across code files, docs, and CLI runners. |
| **Filesystem & State Anchors** | Application root anchor resolved dynamically (`Path(__file__).resolve().parent...`); `data/`, `logs/`, and `config/` paths derived relative to this anchor. | Naive relative paths (`./data.db`) that break when executed from different working directories. |
| **Ecosystem Mappings** | • **Python:** `core/config.py` using `pydantic-settings`<br>• **Node/TS:** `src/config/index.ts` using `zod`<br>• **Go:** `internal/config/config.go`<br>• **Rust:** `src/config.rs` using `serde`<br>• **.NET:** `IOptions<AppSettings>` bound to `appsettings.json` | Re-reading config files or environment variables on every request or inside library functions. |

### Test Topology & Hermetic Isolation Pattern

A well-architected repository separates fast-feedback unit tests from resource-heavy integration suites:

| Test Tier | Directory | Scope & Dependencies | Execution Target | Isolation Rule |
| :--- | :--- | :--- | :--- | :--- |
| **Unit Tests** | `tests/unit/` | Pure business logic, algorithmic models, mock-based protocol contracts. | Sub-second runtime. Run on every local change and PR quick-gate. | 100% memory/mocked. Zero real disk I/O, zero network calls. |
| **Integration Tests** | `tests/integration/` | End-to-end HTTP/CLI flows, real SQLite/database fixtures, process lifecycles. | Comprehensive verification before merge/release. | Ephemeral sandboxing (`tmp_path`, `t.TempDir()`). Never write into repository tree. |

### Granular Exception Handling & Error Boundaries Pattern

To prevent masking programmer bugs (e.g. `NameError`, `TypeError`, typo assertions) and ensure actionable error recovery:

| Layer | Permitted Handling | Forbidden Anti-Patterns | Rationale |
| :--- | :--- | :--- | :--- |
| **Subroutines & I/O** | Specific catch: `OSError`, `FileNotFoundError`, `PermissionError`, `ValueError`, `TimeoutError`. | Blind catch-alls: `except Exception:`, `catch (e: any)`, or empty `pass`. | Callers and handlers must understand exactly why an operation failed to perform valid recovery. |
| **Exception Chaining** | Preserve root cause: `raise DomainError(...) from err` or `fmt.Errorf("...: %w", err)`. | Swallowing inner traceback: `raise DomainError(str(err))` without chaining. | Preserves full diagnostic stack traces for root-cause analysis. |
| **Outer System Boundary** | Catch-all permitted **only** at outer gateway/entrypoint (e.g. ASGI middleware, CLI root runner). | Catch-alls buried in core business logic or utility helpers. | Centralizes structured crash logging (`exc_info=True`) and user-facing error formatting. |

### Graceful Lifecycle and Signal Termination Pattern

Long-running services must clean up safely upon receiving OS termination signals (`SIGINT`, `SIGTERM`):

| Ecosystem | Lifecycle Mechanism | Cleanup Responsibilities |
| :--- | :--- | :--- |
| **Python** | `lifespan` async context manager (FastAPI/Starlette) or `signal.signal(signal.SIGTERM, ...)`. | Close database pools, complete pending tasks, flush log handlers. |
| **Node / TypeScript** | `process.on('SIGTERM', async () => { ... })`. | Close HTTP server listeners, disconnect ORM/database clients, exit cleanly. |
| **Go** | `signal.NotifyContext(ctx, os.Interrupt, syscall.SIGTERM)`. | Cancel context, wait on `sync.WaitGroup`, release lockfiles. |
| **Rust** | `tokio::signal::ctrl_c()` or `signal_hook`. | Drop shared locks, flush disk buffers, shut down task runners. |

## Compose architecture with stack capabilities

The stack profile should state toolchain constraints, supported manifests,
commands, and verification capabilities. Architecture layouts should be
separate profile options that the user can choose after discovery. Domain
requirements may add or remove needs; topology may change repository boundaries.
Do not let a stack name silently select Clean Architecture, microservices, or a
large directory tree.

The current generator composes only profile-declared directories and files. It
does not infer business modules, dependency direction, or a complete architecture
from requirements. Treat its output as a reviewed starting point, not an
architecture validation result.

## Discovery confidence

Report matched markers and their strength. A generic file such as `main.py` is
weak evidence; stack-specific manifest content is stronger. If the best
candidates are close or multiple stacks are present, report ambiguity and stop
generation. Ask the user which profile applies or propose a deliberate
multi-profile composition. Never silently select the first adapter in registry
order.
