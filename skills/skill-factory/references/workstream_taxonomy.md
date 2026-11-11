# Universal Project Workstream Taxonomy

This taxonomy describes kinds of work a project may contain. It is independent
from both lifecycle stages and the ten Universal Capability facets:

- **Domain** identifies what kind of project is being built or studied.
- **Lifecycle** identifies when the work occurs.
- **Workstream** identifies the responsibility or kind of work.
- **Capability** identifies what the agent must be able to do.

Workstreams are selectable categories, not a mandatory checklist. Include only
those supported by the project scope. A project may use domain-specific
sub-workstreams without changing this universal taxonomy.

## The 16 universal workstreams

| ID | Workstream | Scope |
|---:|---|---|
| 1 | Product Strategy & Discovery | Ideation, opportunity discovery, product direction, value proposition, MVP definition |
| 2 | Research & Intelligence | Market, competitor, user, technical, scientific, and ecosystem research |
| 3 | Requirements & Domain Analysis | Problem analysis, domain concepts, requirements, specifications, acceptance criteria, traceability |
| 4 | Project & Program Management | Scope, roadmap, estimates, tasks, dependencies, schedule, resources, risks, coordination |
| 5 | UX/UI & Experience Design | User journeys, interaction design, interface design, accessibility, usability |
| 6 | System & Architecture Design | System boundaries, architecture, data models, interfaces, component and module design |
| 7 | Engineering & Implementation | Software, firmware, hardware, and system implementation; coding, integration, debugging, refactoring |
| 8 | Creative & Asset Production | Visual, audio, video, 3D, writing, and other creative asset production |
| 9 | Data & Information Management | Data modeling, acquisition, processing, storage, migration, quality, governance |
| 10 | Testing & Quality Assurance | Test strategy, unit/integration/system testing, playtesting, acceptance, quality verification |
| 11 | Security, Safety & Compliance | Threat/risk assessment, privacy, safety, compliance, secure design, audits |
| 12 | Infrastructure & Automation | Development environments, toolchains, CI, automation, infrastructure, build/test pipelines |
| 13 | Delivery & Release Management | Packaging, release planning, publishing, deployment, distribution, handover |
| 14 | Operations & Maintenance | Monitoring, support, incident response, maintenance, updates, live operations |
| 15 | Documentation & Communication | Specifications, technical documents, records, reports, guides, stakeholder communication |
| 16 | Evaluation & Continuous Improvement | Outcome evaluation, metrics, retrospectives, lessons learned, iterative improvement |

## Domain-specific sub-workstreams

Create sub-workstreams only when they materially improve recommendation
precision. Keep them nested under the closest universal workstream; do not
create a new universal row for every domain term.

Examples for game development:

| Universal workstream | Example game sub-workstreams |
|---|---|
| Product Strategy & Discovery | Game concept, genre positioning, core loop, MVP definition, monetization hypothesis |
| Research & Intelligence | Genre research, competitor/gameplay analysis, player research, platform research |
| Requirements & Domain Analysis | Game Design Document (GDD), gameplay specification, feature specification, acceptance criteria |
| Project & Program Management | Milestone planning, sprint/task planning, solo-developer workload management |
| UX/UI & Experience Design | HUD, menus, onboarding, input flow, accessibility, player experience |
| System & Architecture Design | Game architecture, scene structure, gameplay systems, event/state models, save architecture |
| Engineering & Implementation | C# programming, gameplay programming, AI, combat, physics, animation logic, networking, debugging, refactoring |
| Creative & Asset Production | Art direction, character art, sprites, animation, VFX, audio, music, 3D assets |
| Data & Information Management | ScriptableObjects, game balance data, progression/economy data, save data |
| Testing & Quality Assurance | EditMode/PlayMode tests, gameplay testing, compatibility, performance, balancing, regression |
| Security, Safety & Compliance | Privacy, anti-cheat, platform compliance, age ratings, third-party asset/license checks |
| Infrastructure & Automation | Unity tooling, version control, Git LFS, build automation, CI |
| Delivery & Release Management | PC build, packaging, store submission, release candidate, patch delivery |
| Operations & Maintenance | Crash triage, player support, patches, telemetry, community/live operations |
| Documentation & Communication | GDD, technical design, API/code docs, changelog, player guide |
| Evaluation & Continuous Improvement | Prototype evaluation, playtest analysis, KPI review, post-release evaluation |

Examples for other domains should be selected from the actual project context.
Do not force game-specific or software-specific sub-workstreams onto unrelated
projects.

## Software engineering coverage rule

For any project whose deliverable includes software, firmware, scripts, or
programmable behavior, explicitly consider the complete relevant engineering
workflow under **Engineering & Implementation** and its related workstreams:

1. Requirements and acceptance criteria.
2. Specification and traceability.
3. Implementation planning and task decomposition.
4. Architecture and interface design.
5. Coding and integration.
6. Debugging and root-cause analysis.
7. Testing (including test-first/TDD when appropriate).
8. Refactoring and code quality.
9. Code review and verification.
10. Build, packaging, and release verification.

Do not assume a domain-specific tool (for example, a game-engine editor skill)
covers general software engineering. Conversely, do not recommend every stage
for a one-line change or a task that does not need it. Map relevant stages to
the lifecycle and show the actual Skill, MCP, Plugin, native capability, or CLI
that covers each gap.

## Cross-cutting concerns

Security, safety, governance, documentation, and learning can span multiple
workstreams and lifecycle stages. Their presence as universal workstreams does
not mean they must be scheduled as a single isolated phase. Map them where
they materially affect the project.

## Selection rules

- Keep the 16 universal workstreams stable; tailor sub-workstreams to domain.
- Do not populate every cell just to make the matrix look complete.
- Use `-` for a lifecycle cell with no relevant work.
- A workstream can appear in several lifecycle stages.
- The same Skill may appear in multiple cells when it genuinely serves those
  stages; deduplicate it in the Skill Inventory.
- Distinguish a capability/activity from an installable Skill or integration.
  Do not present a generic activity such as "C# Coding" as an installed Skill.
