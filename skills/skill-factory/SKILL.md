---
name: skill-factory
description: >-
  Context-aware workflow for discovering, evaluating, selecting, and composing
  agent skills, plugins, and tools for the user's actual task. Use when selecting
  AI capabilities, auditing available agent skills, resolving tool combinations,
  or deciding whether a repeated workflow should become a custom skill. Works
  across software, research, creative, operations, business, and hybrid workflows.
  Does not design or scaffold repository directories, manifests, or project source trees.
metadata:
  version: "4.8.11"
allowed-tools:
  - "Bash(python scripts/*)"
  - Read
  - Write
  - run_command
  - read_file
  - write_file
---

# Skill Factory

Select the smallest reliable set of AI capabilities and integrations-skills,
plugins, MCP servers, and relevant workflows-that fits the user's task,
project, environment, and constraints. This skill can also evaluate, compose,
and create project-specific AI skills when requested or justified by a repeated
workflow. It does not design or generate the project's source tree, manifests,
architecture, or engineering setup.

## Three-layer architecture

1. **Universal Capability Layer:** 10 abstract capability facets (Planning, Research, Design, Creation, Validation, Analysis, Orchestration, Security, Delivery, Learning) serving as a domain-agnostic vocabulary without hardcoded tool lists, canonical skill requirements, or fixed lifecycle steps.
2. **Dynamic Discovery Layer:** Discovers capabilities and tools by inspecting the actual execution environment, installed skills, and `SKILL.md` frontmatter/descriptions. Eliminates hardcoded catalogs and external skill dependencies.
3. **Adaptive Selection Layer:** Resolves task requirements dynamically through context-aware matching, lexical relevance ranking, explicit permission-declaration review, and negative trigger boundaries. Host/runtime permission enforcement is a separate control and must not be inferred from `allowed-tools` metadata or a static scan. The built-in AST security scanner (`security_scanner.py`) is the local baseline, with external tools like NVIDIA SkillSpector available as optional secondary verification. Development-only evaluations and release checks are maintained outside this installable skill package.

## Scope boundary

This skill owns the AI capability layer: discovering and recommending skills,
plugins, MCP servers, and agent workflows; evaluating extension fit, availability,
permissions, and trust; and creating or evolving AI skills.

It may inspect only the project evidence needed to fit AI capabilities to the
user's task. It does not design or generate project directories, source files,
manifests, architecture, or engineering setup. If a request includes both AI
tooling and project structure, keep those as separate workstreams and outputs;
this skill handles only the AI capability work requested of it. Do not invoke,
hand off to, or depend on a project-scaffolding skill.

## Skill maintenance boundary

Keep installable runtime scripts, metadata, and references inside this skill
directory. Keep maintainer-only tests, evaluation fixtures, and release tooling
outside the distributable package in the repository test suite. Never write
maintenance artifacts into the host project's source tree or another skill.
Keep the version field in this SKILL.md as the single source of truth (SSOT);
do not hardcode duplicate version strings in scripts, the maintainer evaluation
catalog, or reference documents, and increment that field whenever this skill
is modified.
When the user explicitly requests a project-specific AI skill, place that
skill only in the user-selected skill directory and keep changes outside that
destination out of scope.

## Operating principles

- [ ] Follow the user's request and the active repository's instructions first.
- [ ] Discover before recommending: inspect only relevant project evidence and
      available skills/tools. Separate observed facts from assumptions.
- [ ] Adapt to the project domain, lifecycle stage, deliverable, risk, team,
      platform, and existing conventions. Hybrid projects can use more than one
      domain profile.
- [ ] Use the capability taxonomy as optional facets. Select only capabilities
      required by this task; do not require all ten or assume planning/delivery are
      always needed.
- [ ] Prefer existing project tools, installed skills, and native capabilities
      that satisfy the need. Recommend an external skill/plugin only for a concrete
      gap, with evidence and a trust assessment.
- [ ] Report unavailable, unverified, or unsupported capabilities honestly.
      Do not claim a scan, test, market search, or delegation occurred unless it did.
- [ ] Treat `allowed-tools` as a permission declaration only. Verify host/runtime
      enforcement independently; if that evidence is unavailable, report it as
      unverified rather than claiming sandboxing or least-privilege enforcement.
- [ ] Never install, activate, publish, or grant access to a third-party tool
      without user authorization. Read-only discovery and local analysis are fine.
- [ ] Do not scaffold or change project infrastructure as a side effect of an
      audit. Present relevant gaps and proposed changes; act only when requested.

## Adaptive workflow

### 1. Establish the task frame

Identify from the request and only the project evidence needed to select AI
capabilities:

- [ ] Desired outcome and deliverable.
- [ ] Domain(s), platform(s), and relevant technology or artifact formats.
- [ ] Lifecycle stage: explore, plan, create, operate, validate, deliver, or
      improve.
- [ ] Constraints: existing standards, privacy, security, budget, offline needs,
      permissions, and required verification.
- [ ] Whether this is a one-off task or a reusable workflow.

Use repository instructions, manifests, representative files, and existing
workflows as evidence. If context is incomplete, proceed with the safest useful
assumption and label it; ask only when the missing fact changes the action.

### 2. Build a task-specific profile

Select one or more relevant profiles, then tailor them to the actual request:

| Profile                     | Inspect when relevant                                    | Candidate capability facets                           |
| --------------------------- | -------------------------------------------------------- | ----------------------------------------------------- |
| Software / systems          | Source, manifests, build, tests, CI, deployment          | design, creation, validation, analysis, security      |
| Data / research             | Sources, notebooks, datasets, methods, reproducibility   | research, analysis, validation, delivery              |
| Creative / media            | Brief, source assets, formats, review and export needs   | planning, design, creation, validation, delivery      |
| Business / operations       | Process, source records, controls, approvals, reporting  | planning, research, analysis, orchestration, delivery |
| Hardware / physical systems | Schematics, firmware, simulation, device access, safety  | design, creation, validation, security, orchestration |
| Hybrid / other              | Identify only the parts present; add a profile if needed | Derive from the requested outcome                     |

These are prompts for inspection, not mandatory checklists. Do not infer that a
repository is software merely because it contains files, or that every project
needs tests, a linter, Git hooks, an AI runbook, or a changelog.

### 3. Match capabilities and tools

Use the ten facets in `references/capability_taxonomy.md` as a shared vocabulary.
For each candidate, state the task need it addresses and its evidence. Rank by
fit, not by a universal score or canonical list. Prefer the fewest tools that
cover the required work without unnecessary overlap.

Check capabilities in this order:

1. Skills and integrations already available in this environment.
2. The project's existing AI workflow and native tools that are relevant to the
   requested work.
3. External candidates only when a real gap remains and discovery is available.

Project directories, architecture, and engineering configuration are outside
this skill's scope. Do not perform those tasks or invoke another skill for them.

Treat examples in references as examples, not endorsements or requirements.
Verify current availability, source, maintenance, permissions, and data handling
before making a current recommendation. If live discovery is unavailable, say so.

### 4. Check AI capability readiness only when useful

A capability audit is optional and should answer a user-relevant question about
whether the AI workflow has the needed skills, integrations, tools, permissions,
and verification support. Mark each selected item `evidenced`, `missing`,
`unknown`, or `not applicable`; explain the evidence and impact. Missing
project-level tests, CI, documentation, or other engineering controls are
outside this audit. Never turn a capability gap into an
unsolicited install, activation, permission grant, or project scaffold.

### 5. Evaluate security and trust proportionately

For a specific candidate skill/tool, inspect its source and requested
permissions when available. Apply the trust rubric in
`references/security_and_trust_rubric.md`. Distinguish static findings from
runtime guarantees. A scanner or SkillSpector is optional and only report it as
used when it was actually run and available. Missing scanner support means
unverified, not safe or malicious by default.

### 6. Synthesize or evolve skills only on request / clear need

When the user asks to create/update a skill, or a genuinely repeated workflow
justifies one, inspect existing skills and deduplicate before authoring. A
repeated pattern is a signal to evaluate, not an automatic trigger. Use the
authoring and lifecycle references. Keep the skill portable, self-contained,
and explicit about positive and negative triggers. Dry-run and scan with tools
that exist; disclose unavailable checks. Do not claim automatic activation or
approval.

### 7. Report a useful, contextual result

Summarize the task profile, evidence, selected capabilities/tools, relevant gaps,
trust or permission concerns, and verification performed. Omit irrelevant
capabilities. Provide actionable next steps only when they follow from the task;
use `- [ ]` checkboxes for actionable checklists. Do not pad the result to fill a
fixed taxonomy or readiness score.

## Local scripts & utilities

Deterministic helper scripts in `scripts/`:

- `scripts/scaffold_skill.py`: Universal lifecycle orchestrator (`--match`, `--scan`, `--compose`, `--synthesize`).
- `scripts/skill_synthesizer.py`: Staged skill synthesis with atomic directory replacement and backup-preserving rollback on restore failure; no absolute zero-data-loss guarantee is claimed.
- `scripts/deduplication_engine.py`: 4-Gate Anti-Sprawl engine (Semantic Overlap, Entity Ownership, Complexity/ROI, Negative Boundaries).
- `scripts/security_scanner.py`: AST data-flow threat scanner, source-to-sink credential tracking, syntax error detection, declared-tool inspection, and explicit excluded-file coverage reporting. It cannot prove host/runtime permission enforcement.
- `scripts/capability_matcher.py`: Context-aware capability resolution and negative context matching.
- `scripts/agent_adapter.py`: Multi-agent environment ports & adapters (Gemini, Codex, Claude Code, Cursor, Copilot, Local).
- `scripts/capability_composer.py`: Capability contract modeling & continuous workflow DAG composition.

Repository-maintainer evaluations, regression tests, and the release gate are kept outside the installable package; they are development-only assets, not runtime components.

## References

- Capability vocabulary: [`references/capability_taxonomy.md`](references/capability_taxonomy.md)
- Readiness by lifecycle and domain: [`references/lifecycle_taxonomy.md`](references/lifecycle_taxonomy.md)
- Tool discovery matrix: [`references/mcp_and_plugin_matrix.md`](references/mcp_and_plugin_matrix.md)
- Environment adapters: [`references/agent_environment_adapters.md`](references/agent_environment_adapters.md)
- Security and trust: [`references/security_and_trust_rubric.md`](references/security_and_trust_rubric.md)
- Skill lifecycle: [`references/skill_lifecycle_management.md`](references/skill_lifecycle_management.md)
- Deduplication: [`references/skill_deduplication_framework.md`](references/skill_deduplication_framework.md)
- Authoring: [`references/skill_authoring_best_practices.md`](references/skill_authoring_best_practices.md)
- Evaluator rubric: [`references/nvidia_skill_evaluator_rubric.md`](references/nvidia_skill_evaluator_rubric.md)
