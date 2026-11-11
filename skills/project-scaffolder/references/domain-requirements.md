# Contextual Readiness Requirements

This guide helps choose project checks without assuming every repository needs
the same 20 controls. Domain examples are candidate concerns; the user’s
requirements, repository rules, delivery model, and risks decide the actual
scope.

## Select audit categories

Profiles declare default `mandatory_categories` and `na_categories`. Treat these
as profile starting points, then adapt them to the project’s stated purpose and
constraints before presenting a readiness plan. The audit script honors those
lists; a category outside the selected mandatory scope is excluded from the
readiness score. An explicit N/A exemption takes precedence.

| Category                               | Candidate evidence                                                                | Common reasons to select                                          | Common reasons to omit or defer                                     |
| -------------------------------------- | --------------------------------------------------------------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| 01. Domain and stack profile match     | Unique profile markers and user-confirmed project context                         | Any project using a supported profile                             | Unknown or ambiguous profile must stop discovery                    |
| 02. Project configuration              | Validated manifest, engine config, or toolchain file                              | Buildable or deployable projects                                  | Informal artifacts without a runtime/build system                   |
| 03. Asset and resource management      | LFS rules, artifact storage, data provenance, or device resource controls         | Large binary assets, models, firmware artifacts                   | No managed binary/resource pipeline                                 |
| 04. Separation of concerns             | Reviewed module responsibilities and dependency direction                         | Projects with multiple responsibilities or teams                  | Tiny single-purpose artifact; may remain unverified if not reviewed |
| 05. Module boundaries                  | Package layout (src/<package_name>/), encapsulated entry points, clean root check | Modular systems, monorepos, multi-team code                       | Single package with no meaningful internal boundary                 |
| 06. Coding standards                   | Project-approved lint, format, or review rules                                    | Shared codebases and enforced contribution rules                  | Exploratory work where conventions are intentionally deferred       |
| 07. Smoke test execution               | Test runner output with a non-zero assertion count                                | Software, models, hardware simulation, repeatable analysis        | Deliverables that are not executable or testable by automation      |
| 08. Test strategy                      | Selected unit, integration, hardware, data, or acceptance checks                  | Work with meaningful regression or safety risk                    | One-off low-risk artifact; validate by appropriate review instead   |
| 09. Error handling and logging         | Runtime behavior, observable failures, or operating guidance                      | Long-running, user-facing, embedded, or production systems        | Static documents and non-operational artifacts                      |
| 10. Pre-commit hooks                   | Configured and executed hooks                                                     | Teams choosing local enforcement                                  | Projects using another quality gate or no Git workflow              |
| 11. Repository hygiene                 | Line-ending scan, ignore rules, tracked-file inspection                           | Git-managed source or binary artifacts                            | Source control is intentionally absent                              |
| 12. CI parity                          | Comparison of CI and local verification commands                                  | Team repositories with CI                                         | Solo/local projects or non-CI delivery                              |
| 13. Build and deployment               | Build/deploy result; binary packaging via packaging/ to out/<package_name>/       | Compiled or packaged deliverables                                 | No build/deployment step                                            |
| 14. Project runbook                    | Accurate, project-specific operating instructions                                 | Repositories with recurring contributors or non-obvious workflows | Simple artifacts with clear native conventions                      |
| 15. Operational logbook                | Active log and append/rotation policy                                             | Projects requiring session or operational history                 | No record-keeping requirement                                       |
| 16. Changelog                          | Maintained change history                                                         | Versioned or released products                                    | Ephemeral or unversioned deliverables                               |
| 17. Tailored documentation             | Relevant design, API, data, hardware, or user docs                                | Complexity, risk, maintenance, or handoff justifies documentation | No separate documentation need                                      |
| 18. Performance and resource profiling | Measurements against stated budgets                                               | Real-time, embedded, high-throughput, or cost-sensitive systems   | No meaningful resource constraint                                   |
| 19. Security and secret hygiene        | Index inspection plus appropriate secret/dependency scans                         | Any sensitive, networked, or deployable system                    | Security risk is minimal; still state scope and evidence limits     |
| 20. Documentation format rules         | Explicit project style policy and a matching static check                         | Repository defines checklist, language, or style requirements     | No such policy; do not import another project’s editorial rules     |

## Interpret evidence accurately

- `PASS`: The selected criterion has direct evidence meeting its verification
  rule. File presence alone is not enough for execution, architecture quality,
  security, or parity claims.
- `FAIL`: A required criterion is demonstrably absent or a required check ran
  and failed.
- `NOT VERIFIED`: Evidence is incomplete, a check was not executed, or the
  available static heuristic cannot establish the claim.
- `NOT APPLICABLE`: The project/profile explicitly excludes the criterion from
  this audit scope.

The current auditor supports only a subset of deep checks. In particular, it
does not analyze dependency graphs, prove architecture quality, compare CI and
hook commands, or scan file contents for secrets. Report those limits as
`NOT VERIFIED`; do not award a passing score based on folder names or keywords.
For standardized, language-agnostic CI/CD pipelines, release orchestration, AI instructions,
and PR governance across categories 12, 13, 14, 16, and 17, see
[`references/repository-governance.md`](repository-governance.md).
