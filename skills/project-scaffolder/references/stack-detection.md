# Contextual Project Discovery Model

A project profile is evidence about supported toolchains, not an architecture
decision. Inspect distinct concerns and preserve uncertainty:

| Concern      | Question                                                     | Evidence                                                        |
| ------------ | ------------------------------------------------------------ | --------------------------------------------------------------- |
| Domain       | What problem, users, and operating context?                  | User requirements, product docs, representative source          |
| Stack        | Which runtimes, engines, and tools constrain implementation? | Stack-specific manifests, lockfiles, distinctive config content |
| Topology     | How are components packaged and deployed?                    | Workspace manifests, deploy definitions, explicit boundaries    |
| Architecture | How are responsibilities and dependencies organized?         | Requirements, domain seams, scale, lifecycle, constraints       |

Architecture is separate from stack detection. Use
[`architecture-decision.md`](architecture-decision.md) to compare options and
tradeoffs before selecting a layout.

## Stack marker evidence

Profiles may use exact files, glob patterns, or content markers in the form
`path:substring`. Specific manifest content is stronger evidence than generic
names. Generic files such as `main.py`, `app.py`, and `src/` receive low weight.
Profiles can define `marker_weights` and `match_threshold` where defaults do not
fit.

The registry reports candidates with matched markers and scores. It selects a
profile only when exactly one candidate reaches its threshold. Multiple credible
candidates are treated as hybrid/ambiguous and block generation until clarified.
It must never silently choose the first adapter in registry order.

Current profiles cover examples including Unity/Godot, PlatformIO/ESP-IDF,
Next.js/FastAPI, Rust/Go/Zig, Python data pipelines, and Python security tools.
These are known profiles, not an exhaustive supported-stack list.

## Topology evidence

- `monorepo`: explicit workspace configuration such as pnpm/Turborepo/Lerna or
  a Cargo workspace.
- `microservices`: explicit service deployment evidence, not simply several
  Dockerfiles or source folders.
- `modular_monolith`: explicit internal module boundaries such as assembly or
  package manifests, not merely multiple directories.
- `monolith`: use when one deployable unit is established by requirements or
  configuration.
- `unknown`: use when current evidence is insufficient.

The current topology detector recognizes only a limited set of markers. Treat
its result as a heuristic and report the evidence; do not claim that it verifies
dependency direction or architectural quality.

## Unknown or ambiguous projects

If the workspace is empty, markers are weak, or several candidates match:

1. Report the observed evidence and competing interpretations.
2. Ask about project purpose, users, scale, deployment, constraints, and desired
   deliverable.
3. Propose a proportionate architecture with tradeoffs.
4. Wait for the user to select or confirm the profile and layout before writing.

The current generic fallback is intentionally empty. It must not create a
fixed `src/`, `tests/`, `Docs/`, or `logbook/` structure, run unknown commands,
or report project readiness for an unrecognized stack.

The current implementation stops on multi-profile ambiguity. It does not yet
compose multiple stack adapters automatically; describe that limit and propose
a profile composition plan instead of pretending the feature exists.
