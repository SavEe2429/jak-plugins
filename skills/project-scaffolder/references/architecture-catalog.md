# Architecture Pattern Catalog

This is an illustrative architecture decision catalog, not a list of layouts the
generator can automatically build. Select a pattern from project requirements
and tradeoffs; then verify that the active profile explicitly supports the
layout. The current tool does not analyze dependency graphs or validate
architecture quality.

---

## 1. Modular Monolith

- **Best Suited For:** Game Development (Unity, Godot), Desktop Applications, Enterprise APIs, Systems Tools.
- **Key Characteristics:**
  - Single deployable unit with strictly enforced internal module boundaries.
  - In Unity/C#: Boundaries enforced via Assembly Definitions (`.asmdef`).
  - In Rust: Workspaces and internal crates (`crates/core`, `crates/ui`).
  - In TypeScript/Node: Monorepo packages or domain modules (`packages/core`, `packages/api`).
  - No circular dependencies between modules.
- **Directory Pattern:**

  ```text
  src/ or Assets/Scripts/
  ├── Core/          (Data models, pure business logic, zero engine dependency)
  ├── Gameplay/      (Domain features, systems, mechanics)
  ├── Presentation/  (UI, ViewControllers, Renderers, Input adapters)
  ├── Infrastructure/(Save/Load, Networking, Storage adapters)
  └── Tests/         (EditMode/PlayMode or Unit/Integration)
  ```

---

## 2. Clean / Hexagonal Architecture (Ports and Adapters)

- **Best Suited For:** Web Backends (FastAPI, Go, Node.js), Financial/Transaction Systems, Security Scanners.
- **Key Characteristics:**
  - Pure domain entities and use-cases at the center.
  - Inbound and Outbound Ports (Interfaces).
  - External adapters (Database, HTTP, Message queues, CLI) depend inward on ports.
  - Extreme testability: Domain logic tested with pure in-memory mocks without external services.
- **Directory Pattern:**

  ```text
  src/
  ├── domain/        (Entities, Value Objects, Domain Exceptions)
  ├── application/   (Use Cases, DTOs, Inbound/Outbound Port Interfaces)
  ├── infrastructure/(DB repositories, External API clients, File adapters)
  └── presentation/  (HTTP routes, CLI commands, GraphQL resolvers)
  ```

---

## 3. Layered (N-Tier) Architecture

- **Best Suited For:** Standard CRUD Web APIs, Internal Tooling, Microservices.
- **Key Characteristics:**
  - Clear vertical flow of control: Presentation -> Service / Business -> Data Access -> Database.
  - Low cognitive overhead; ideal for rapid development and straightforward requirements.
- **Directory Pattern:**

  ```text
  src/
  ├── controllers/   (or routes/ - HTTP request/response handling)
  ├── services/      (Business logic and transaction orchestration)
  ├── repositories/  (or models/ - Database access, ORM queries)
  └── utils/         (Cross-cutting helpers, logging, error formatters)
  ```

---

## 4. Data-Oriented Design (DOD / ECS)

- **Best Suited For:** High-Performance Game Engines (Unity DOTS, Bevy, custom C/C++ engines), Real-Time Simulations.
- **Key Characteristics:**
  - Separation of Data (Components: pure structs) from Logic (Systems: iteration loops) and Identity (Entities: IDs).
  - Memory layout optimized for CPU cache lines and SIMD vectorization.
  - Strictly Zero GC and predictable frame budgets.
- **Directory Pattern:**

  ```text
  src/ or Assets/Scripts/
  ├── Components/    (Blittable unmanaged structs, zero methods)
  ├── Systems/       (Execution queries, burst-compiled jobs)
  ├── Authoring/     (Editor conversion baking scripts)
  └── Singletons/    (Global configuration and state components)
  ```

---

## 5. Event-Driven Architecture

- **Best Suited For:** IoT / Embedded Firmware (ESP32, FreeRTOS), Real-Time Chat/Multiplayer, Reactive UI.
- **Key Characteristics:**
  - Producers emit events to an event bus or ring buffer; consumers subscribe asynchronously.
  - Loose coupling between producer and consumer lifecycles.
  - Safe queue handling to prevent buffer overruns in memory-constrained environments.
- **Directory Pattern:**

  ```text
  src/
  ├── events/        (Event structs, event IDs)
  ├── bus/           (Queue manager, publish/subscribe dispatcher)
  ├── producers/     (Sensors, network packets, input listeners)
  └── consumers/     (Actuators, display managers, state machines)
  ```

---

## 6. Canonical Package Structure and Encapsulated Entry Points

- **Rule: No Root Entry Points & No Loose Root UI:**
  Do not place executable entrypoint files (`main.py`, `cli.py`, `app.py`, `index.js`) or loose UI asset directories in the root repository directory. The root directory is strictly reserved for repository configuration (`pyproject.toml`, `.gitignore`), documentation (`README.md`, `Docs/`, `AGENTS.md`), tests (`tests/`), logbook (`logbook/`), and build tooling (`packaging/`).

- **Canonical Source Root (`src/<package_name>/` or `code/<package_name>/`):**
  All executable entry points, application logic, and user interfaces must reside within the canonical package namespace.

- **Component Layering (Clean Architecture and Ports/Adapters Alignment):**
  Within `src/<package_name>/`, partition code cleanly by architectural responsibility:

  ```text
  src/<package_name>/
  ├── __init__.py      (Package export and version metadata)
  ├── __main__.py      (Enables `uv run python -m <package_name>` execution)
  ├── cli.py           (Command-line entrypoint for [project.scripts])
  ├── core/            (Core domain logic, configuration, state management, constants)
  ├── models/          (Data structures, domain entities, Pydantic schemas, DTOs)
  ├── interfaces/      (Ports, protocols, and presentation interfaces)
  │   ├── ui/          (Web dashboard / frontend assets: index.html, static assets)
  │   ├── api/         (HTTP / REST controllers and routes)
  │   └── ports/       (Abstract base classes, protocols, contracts)
  └── components/      (or tools/ / services/ - Concrete adapters, tools, integrations)
  ```

- **Execution Conventions via Native Toolchain Runners:**
  1. **Native Runner Exclusivity**: All commands and runbooks must use the package manager's native runner (e.g. `uv run <command>`, `pnpm exec <command>`, `cargo run`). Never invoke virtualenv interpreter binaries through platform-dependent paths like `.venv/Scripts/python.exe`.
  2. **Console Scripts**: Register commands in `pyproject.toml` under `[project.scripts]` (e.g. `my-app = "<package_name>.cli:main"`), run via `uv run my-app`.
  3. **Direct Module Run**: Support module execution via `uv run python -m <package_name>`.
  4. **Binary Packaging**: `packaging/build.py` compiles `src/<package_name>/cli.py` and bundles embedded `interfaces/ui/` assets, emitting binaries to `out/<package_name>/`.
  5. **Modern Build Backend (PEP 517 / PEP 621)**: Python projects must declare a standardized modern build backend in `pyproject.toml` (e.g. `[build-system] requires = ["hatchling"] build-backend = "hatchling.build"`) to ensure clean builds and prevent legacy setuptools `*.egg-info` directories from polluting `src/`.

---

## 7. AI Agent and Model Context Protocol (MCP) Architecture Pattern

- **Best Suited For:** Model Context Protocol (MCP) Servers, AI Agent Tooling Gateways, LLM Integration Services (Python, TypeScript, Go, Rust).
- **Core Engineering Principles:**
  1. **Stdio Transport Purity:** When communicating via standard input/output (`stdio`), `stdout` is reserved exclusively for JSON-RPC 2.0 frames. All runtime logging, debugging traces, and banner messages must be routed strictly to `stderr` or rotating log files. Polluting `stdout` with unstructured text immediately breaks protocol deserialization on host clients (Claude Code, Antigravity, Cursor).
  2. **Tool Sandboxing & Working Directory Confinement:** All tools performing filesystem or shell operations must enforce strict path confinement. Resolve canonical paths using `os.path.realpath` / canonical path APIs, verify that target paths reside within authorized workspace boundaries via `.relative_to(authorized_root)`, and reject path traversal attempts (`..`, escaped symlinks, or junction points).
  3. **Deterministic Schema Boundaries:** Define explicit parameter schemas (using Pydantic v2 in Python or Zod in TypeScript) with strict type hints, bounds, and clear descriptions. Tool outputs must return structured JSON or text payloads without unhandled exception tracebacks leaking to the client.
  4. **Process Lifecycle & Graceful Shutdown:** Listen for `SIGINT` and `SIGTERM` signals to cleanly drain pending requests, flush buffers, and terminate spawned subprocess trees. Never leave orphaned child processes running when the host client disconnects.
  5. **Zero Ambient State:** Configure tools via an explicit SSOT settings module (e.g., `pydantic-settings` or environment schema). Avoid relying on implicit global state or ambient working directory context.
- **Directory Pattern:**

  ```text
  src/<package_name>/
  ├── __init__.py        (Package version metadata and public exports)
  ├── __main__.py        (CLI runner: `uv run python -m <package_name>`)
  ├── server.py          (MCP server initialization, transport setup, and signal handling)
  ├── config.py          (SSOT configuration, environment variables, authorized paths)
  ├── tools/             (Discrete tool definitions and action handlers)
  │   ├── __init__.py    (Tool registration and dispatcher)
  │   ├── safe_path.py   (Canonical path confinement guard)
  │   └── operations.py  (Domain tools with explicit schema validation)
  ├── resources/         (Dynamic data providers and URI template routers)
  ├── prompts/           (Reusable prompt templates and workflow recipes)
  └── utils/
      └── logging.py     (Stderr-only logger configuration)
  ```
