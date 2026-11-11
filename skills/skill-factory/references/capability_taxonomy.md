# Universal Capability Taxonomy for AI Agents

`skill-factory` uses these ten capability facets as a shared vocabulary across domains. They are broad labels, not a complete capability model, fixed lifecycle, or tool catalog. First identify the specific ability the Agent needs; then map it to one or more facets. For every applicable work item, analyze both `Core` and `Supporting` capabilities at Project, Workstream, Sub-workstream, Task, and Activity levels. This two-lens analysis is mandatory, but a capability is included only when the work context justifies it.

---

## The 10 Universal Capabilities

```
+------------------------------------------------------------------------+
|                   10 UNIVERSAL AGENT CAPABILITIES                      |
+--------------------------+---------------------------------------------+
| 1. Planning              | Requirements grilling, PRD, task breakdown  |
| 2. Research              | Codebase survey, web search, API docs       |
| 3. Design                | System diagrams, wireframes, schema models  |
| 4. Creation              | Code authoring, skill synthesis, content generation|
| 5. Validation            | Automated tests, smoke test, visual/functional checks|
| 6. Analysis              | Code review, memory profiling, metrics      |
| 7. Orchestration         | Subagent delegation, batch pipelines, CI    |
| 8. Security              | Vulnerability scan, secret audit, sandbox   |
| 9. Delivery              | Changelogs, release notes, documentation    |
| 10. Learning             | Post-mortems, 3-repeat rule, deduplication  |
+--------------------------+---------------------------------------------+
```

---

## Core and Supporting Capability Model

Every specific capability must have one of these roles:

- **Core** — directly performs or materially produces the work outcome or deliverable.
- **Supporting** — improves the quality, efficiency, clarity, safety, or reliability of Core work through a method, workflow, reasoning approach, review practice, decision process, or coordination ability.

Analyze both roles at every applicable level:

| Level | Core capability question | Supporting capability question |
|---|---|---|
| Project | What must the Agent be able to do to help achieve the project outcome? | What cross-cutting methods help frame, plan, decide, coordinate, and improve the project? |
| Workstream | What abilities produce this workstream's outcomes? | What practices improve the workstream across its sub-workstreams and tasks? |
| Sub-workstream | What abilities produce this group's outputs? | What methods help organize, reason about, review, or coordinate this group of work? |
| Task | What must the Agent do to complete this task? | What method makes the task better specified, planned, executed, reviewed, or verified? |
| Activity | What ability is needed for this concrete activity? | What technique or review/decision aid improves this activity? |

Examples of Supporting Capabilities include requirements grilling, brainstorming,
option comparison, task breakdown, decision facilitation, design critique,
architecture review, pragmatic/minimalist engineering, risk review, debugging
strategy, accessibility review, and retrospectives. These are illustrative
capability concepts, not a mandatory checklist or endorsements of named Skills.

A Supporting Capability may serve multiple work items or levels. Analyze it in
context first, then consolidate semantically equivalent capabilities and keep
all source-work links. Every Supporting Capability must include a task-specific
work rationale linked to at least one originating work item; a generic label
such as "brainstorming" or "planning" without an explained connection to the
deliverable, decision, constraint, or work method is not eligible for matching.
For a cross-cutting capability, preserve the work-item-to-level relationship
for every source link. Keep `work_rationale` (why this capability supports the
work) distinct from `related_rationale` (why a Resource is an indirect match).
A broad facet such as `planning` is not sufficiently specific by itself; use a
concrete statement such as `decompose the approved feature scope into ordered
tasks with acceptance criteria`.

---

## Illustrative domain examples

These examples show possible mappings, not canonical or mandatory recommendations. Inspect the actual project and task before selecting tools. Do not infer that an example skill is installed, trustworthy, or available.

### 1. Game Development (e.g., Unity / Godot)

- **Project-level Core:** game concept/design, gameplay systems, content production, implementation, and release as required by scope.
- **Project-level Supporting:** product discovery, brainstorming, requirements grilling, scope/prioritization, roadmap and milestone planning, and cross-workstream decision facilitation where justified.
- **UI workstream Core:** UX/UI design and interface implementation.
- **UI workstream Supporting:** user-flow analysis, design critique, accessibility review, and visual consistency checks.
- **Gameplay task Core:** implement the requested gameplay mechanic.
- **Gameplay task Supporting:** task breakdown, option comparison, pragmatic engineering, debugging strategy, and code/design review where they improve the task.
- Map these specific abilities to the broad facets (for example, Planning, Design, Creation, Analysis, or Validation) only after identifying them. These are examples, not a required bundle.

### 2. Data Science & Machine Learning

- **Possible Capabilities:** Research, Analysis, Creation, or Validation depending on whether the task concerns literature, data, modeling, or reproducibility.
- _Excluded (N/A):_ Graphics rendering inspection, UI wireframing.

### 3. Business & Financial Analysis

- **Possible Capabilities:** Planning, Research, Analysis, or Delivery depending on the decision and requested artifact.
- _Excluded (N/A):_ Test-Driven Development, Compilers, LFS game assets.

### 4. Incident Response & Security Assessment

- **Primary Capabilities:** Security (`security_scanner`, Bandit, Semgrep), Research (CVE search, logs survey), Analysis (Root cause timeline), Delivery (Post-mortem incident report).
