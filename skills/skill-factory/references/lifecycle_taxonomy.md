# Contextual readiness and lifecycle guide

Use this guide to choose relevant checks for the current task. It is not a
universal project checklist, maturity score, or setup mandate. The project owner
may have valid reasons to omit any item.

## Select the scope first

Identify the deliverable, domain, lifecycle stage, constraints, and risks. Look
at existing project instructions and workflows before proposing new ones. For
hybrid work, combine only the relevant parts of multiple profiles.

Possible lifecycle stages:

- Explore and decide: clarify goals, gather evidence, compare options.
- Plan and design: define scope, model the solution, resolve dependencies.
- Create and operate: produce or run the artifact in its intended environment.
- Validate and review: check the outcome against appropriate acceptance
  criteria, safety controls, and quality needs.
- Deliver and improve: package, communicate, maintain, or learn from the result.

Stages can be skipped or revisited when the request does not need them.

## Skill artifact lifecycle evidence

For generated agent skills, keep these claims separate:

- `Generated`: files were created; functional behavior is not established.
- `Validated`: static checks and declared metadata checks passed. This does not prove the generated workflow works in its host.
- `Tested`: functional tests were executed against the generated workflow and passed.
- `Verified`: functional tests, the required dry-run, and security checks all passed with recorded evidence; where the host uses tool permissions, runtime enforcement must also be independently verified.

A successful static scan alone must never promote a generated skill to `Verified`.
A generated execution skeleton is not a working implementation; it must report
that it is unimplemented and must not exit with a success code for normal execution.
The `dry_run_verified` metadata emitted by the synthesizer describes the
synthesis no-write dry-run, not functional execution of the generated workflow.

## Choose checks by domain and risk

| Work context                | Candidate evidence to inspect                                                                                | Use when                                               |
| --------------------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------ |
| Software / systems          | Build/run instructions, dependency reproducibility, automated checks, source control, security, release path | The task changes or delivers software                  |
| Data / research             | Source provenance, data permissions, methods, environment capture, reproducibility, review                   | Results depend on data or research claims              |
| Creative / media            | Brief, source/asset rights, working files, target formats, review and export workflow                        | The task creates or transforms creative assets         |
| Business / operations       | Source-of-truth records, calculation controls, approvals, access boundaries, reporting                       | Decisions or operations depend on records and controls |
| Hardware / physical systems | Design constraints, simulation, test fixtures, device access, safety and deployment controls                 | Work affects firmware, devices, or physical processes  |
| Other / hybrid              | Identify domain-specific evidence from the requested outcome                                                 | Existing profiles do not fit or multiple domains apply |

For each selected check, report one status:

- `evidenced`: inspected evidence supports that the control exists or works.
- `missing`: the control is relevant and evidence shows it is absent.
- `unknown`: available evidence is insufficient; absence was not established.
- `not applicable`: explain why the check does not affect this task.

File existence alone rarely proves that a control works. Do not treat an
untracked recommendation as a defect, and do not assign a numeric readiness
score unless the user asks for one and the scoring rules are defined.

## Map lifecycle needs to capabilities

The ten capability facets in `capability_taxonomy.md` are reusable labels, not
required phases or slots. Select only those that materially help this task.

Examples:

- A one-off factual lookup may need research only.
- A software bug fix may need analysis, creation, and focused validation.
- A financial model review may need research, analysis, and validation, with no
  compiler, linter, or software test harness.
- A media export may need creation and format validation, without Git or CI.
- A device deployment may need validation, security, and operational controls
  that a generic web application checklist would miss.

## Recommend changes carefully

For any proposed gap, connect it to a concrete failure mode in this task and
describe the smallest useful next step. Do not install packages, create files,
change policy, or delegate setup automatically. If the user asks for an audit,
report findings first; if the user asks for setup, adapt changes to the
project's conventions and verify using its documented workflow.
