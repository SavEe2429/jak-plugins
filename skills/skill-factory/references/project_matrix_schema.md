# Project Matrix and Skill Profile Output Schema

This reference defines the standard output for project-aware recommendations.
It is a presentation and reasoning contract, not a requirement to install
Resources or populate every detail cell.

## 1. Project profile

Normalize only information supplied by the user or evidenced by project
inspection:

- Project name/working title.
- Domain and relevant subdomains.
- Goal and deliverable.
- Platform(s), engine/framework, language, and target environment.
- Team size/working model.
- Scope (prototype, MVP, production, maintenance, research, etc.).
- Constraints (budget, timeline, offline, privacy, permissions, quality).
- Unknowns and assumptions.

Use `Unknown` instead of guessing. Ask a question only when the missing fact
would materially change recommendations or an action.

## 2. Lifecycle model

Use exactly these four lifecycle stages in project-aware output:

| Stage | Meaning |
|---|---|
| Initial | Explore the problem/opportunity, ideate, research, compare options, test feasibility, decide whether and what to build |
| Before | Prepare execution: define scope and requirements, write specifications, plan tasks, design architecture, prepare assets and environment |
| During | Execute and operate the project: design, implement, produce, integrate, test continuously, secure, document, and maintain |
| After | Complete and assess the current delivery: final QA, release, publish, hand over, review outcomes, maintain, and capture lessons |

Lifecycle stages are revisitable, not a one-way waterfall. Testing, research,
security, and documentation may occur in multiple stages. A project can omit
stages that do not apply.

## 3. Consolidated Project Work & Resource Matrix

The project-specific analysis must use one consolidated Matrix table as its
single structured work-and-resource view. Do not create a separate 16×4
overview matrix, Workstream Cards, or a separate Resource Catalog.

Use exactly these columns, in this order:

| Column | Required content |
|---|---|
| Workstream | One of the 16 universal Workstreams, in taxonomy order. All 16 must appear, including unrelated or unresolved Workstreams. |
| Sub-workstream | Dynamic domain-specific breakdown; use a concise list within the cell. |
| Task / Activity | Work needed to produce the project's deliverables; stop at capability-oriented granularity, not click-by-click instructions. |
| Lifecycle Stage | Initial, Before, During, or After; stages are revisitable and may be omitted when irrelevant. |
| Capability | Specific Agent ability required; label each item Core or Supporting. |
| Work Rationale | Why the Capability is needed for its linked work item; mandatory for Supporting Capabilities. |
| Importance | Required, Optional, or Conditional, with a short rationale where not obvious. |
| Resource | Exact Agent Skill, MCP Server, or Plugin name; include type in the same item. Do not recommend general infrastructure/developer tools as Resources. |
| Availability | Installed, Connected, Available Externally, Missing, Unknown, Native, CLI, or Platform; use only when supported by evidence. |
| Recommendation Role | Primary, Alternative, or Complementary for the specific Capability. |
| Match Type | Direct or Indirect. Explain the mechanism for every Indirect match. |
| Verification | Verified, Partially Verified, or Unverified, with concise evidence/source. |
| Practical Test | Passed, Failed, Not Tested, or Not Applicable. |
| Evaluation | Evidence-based criteria scores/status; use concise values such as 4/5 or Insufficient Evidence. |
| Overlap | Full Overlap, Partial Overlap, Complementary, or None Identified. |
| Coverage / Gap | Covered, Partially Covered, No Resource Found, Insufficient Coverage, Unmet Capability, Unknown, or Not Yet Analyzed, as applicable. |

Render the Matrix as one Markdown table. Use lists inside each cell when a
Workstream contains multiple sub-workstreams, work items, Capabilities, or
Resources; do not split those lists into cards or separate tables. Keep
cross-cutting Resources traceable across every Workstream they support, using
the same stable Resource identity where practical.

**Cell formatting rules for maximum readability:**
- Separate distinct items or statements inside cells with <br>•  instead of semicolons (;) in a single running paragraph.
- For Capability and Work Rationale cells, explicitly separate Core and Supporting blocks on distinct lines: **Core:** ...<br>**Supporting:** ....
- For Resource and Recommendation Role, put each distinct Resource on its own bullet line with its exact type or role prefix: • [Primary] ...<br>• [Supporting] ....
- For status columns (Verification, Evaluation, Coverage / Gap), keep the primary status tag at the start (e.g. **Partially Verified**) followed by <br>•  for concise supporting rationale.

Do not mark work required merely because it is common in the domain. Preserve
evidence, rationale, and the relationship between work, Capability, and
Resource.

## 4. Matrix population and cell rules

- Always show all 16 Workstreams in the agreed taxonomy order.
- For a Workstream unrelated to the project, leave its detail cells empty and
  mark its coverage as Not Applicable or leave it blank, according to the
  output context.
- Use Unknown when available evidence is insufficient to determine relevance.
  Use Not Yet Analyzed when a Workstream is relevant or may be relevant but
  its work breakdown has not yet been analyzed.
- Workstreams may contain dynamically generated Sub-workstreams, Tasks, and
  Activities. Do not force every project into a fixed depth or a fixed list of
  domain categories.
- Stop decomposing when the work is sufficiently clear to identify the Agent
  Capability, expected work product/decision, lifecycle stage, and Resources
  that may support it. Avoid click-by-click or implementation micro-steps.
- Examine Core and Supporting Capabilities at Project, Workstream,
  Sub-workstream, Task, and Activity levels. Supporting Capabilities are
  mandatory to consider, but do not invent one where there is no meaningful
  connection to a deliverable, decision, constraint, or work method.
- Keep Capability identity stable while preserving many-to-many links to all
  source work items. Cross-cutting Supporting Capabilities may support several
  Workstreams and Tasks.
- Keep multiple entries as lists inside their own table cells. Use the same
  Resource identity when it appears in multiple Workstreams.
- Preserve every candidate that passes relevance, verification, and trust
  thresholds. Do not cap discovery or the Matrix at Top 3.
- Do not recommend general infrastructure/developer tools as Resources.
  Native capabilities and out-of-scope tools may be mentioned as context only
  when needed to explain a gap or an existing workflow.

## 5. Summary and analysis notes outside the Matrix

The Matrix is the only structured work/resource table. Do not replace it with
cards, a second overview matrix, or a separate catalog table.

When useful, add concise prose summaries outside the Matrix:
- A **Quick Decision & Actionable Starting Plan** (Roadmap) upfront, organizing recommended skills into distinct lifecycle phases (e.g. Phase 1: Prototype MVP & Scoping, Phase 2: Daily Production & Micro-Workflows, Phase 3: Release & Operations).
- **Normalized Resource Notes** grouped by functional categories (e.g. Foundational Coding & Micro-Workflows, Game Prototyping, Engine & Data, UI/Audio/Feel, Build/Release Automation, Optional Plugins) rather than dumped as a single repository list.
- **Sources** grouped consistently with the functional categories.
- A brief summary after each Workstream analysis, stating understood work,
  Core/Supporting Capabilities, grounded inferences, unresolved questions,
  and Required/Optional/Deferred exit criteria.
- A project-level summary after all Workstreams, stating the overall work
  model, confirmed facts, evidence-backed inferences, unknowns, and remaining
  gaps.
- Keep the summaries concise and do not duplicate the entire Matrix.

## 6. Normalized Skill Profile

When reading a Skill, inspect its actual content rather than relying on its
name. Extract the following fields when evidence exists:

- Identity: name, description, source, version, author/maintainer.
- Domains and subdomains.
- Supported workstreams and lifecycle stages.
- Universal capabilities.
- Positive triggers and negative boundaries/exclusions.
- Inputs, outputs, artifacts, and contracts.
- Workflow steps and dependencies.
- Tools, MCP/Plugin dependencies, CLI dependencies.
- Permissions, network/data access, side effects.
- Validation/test approach and limitations.
- Evidence quality and extraction confidence.

Use `Unknown` for unsupported fields. Keep extracted facts separate from
inferences. A Skill may support multiple workstreams and stages; represent
many-to-many relationships instead of forcing one category.

## 7. Snapshot and retrieval

For a project-wide recommendation that produces the consolidated Project
Work & Resource Matrix, persist a snapshot by default when workspace write
access is available, unless the user asks not to save it. If writing is
unavailable, say clearly that the report was displayed but not saved.

Use this default location:

`skill-matrix/<project-slug>/`

Keep an `index.md` for browsing and the latest revision, plus immutable,
dated snapshot files such as `matrix-YYYYMMDDTHHmmssZ-rNN.md`. Each snapshot
must contain:

- Project profile and assumptions.
- The complete consolidated Project Work & Resource Matrix, including all
  16 Workstreams and the lists in their corresponding cells.
- Concise Workstream and project-level analysis summaries when applicable.
- Sources and verification date for external candidates.
- Snapshot identifier and revision metadata.

Use a stable project slug and never silently overwrite a previous snapshot.
On a later request to show or continue a saved matrix/report, search this
location first and report its identifier/date. Update by creating a new
revision while preserving the previous one. Do not claim persistence unless
the file was actually written and verified.

## 8. Anti-overrecommendation rules

- Recommend the smallest coherent capability set that covers the actual scope.
- Do not force a Skill into every Workstream or lifecycle stage.
- Evaluate internal and external Resources with the same evidence and trust
  criteria; do not automatically prefer installed/connected Resources.
- Avoid overlapping Skills unless their roles are complementary and explained.
- Distinguish a work activity from a tool that performs or supports it.
- If no Skill is needed for a task, say that native capability is sufficient.
- Keep all 16 Workstreams represented in the single Matrix table. Include
  lifecycle stage information in the relevant work-item descriptions or fields;
  leave irrelevant Workstream detail cells empty.
