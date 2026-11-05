# Agent Skill Lifecycle Management

`skill-factory` manages the full lifecycle of agent capabilities across 6 stages with mandatory **Human-in-the-Loop (HIL)** checkpoints:

```
[1. DISCOVER (Web + Local)] --> [2. VET & PRESENT TOP 3 (HIL)] --> [3. ORCHESTRATE]
                                          |
                                          v (Only if >= 3 Repetitions + HIL Approved)
[4. EVALUATE / SYNTHESIZE] --> [5. CERTIFY (HIL)] --> [6. RETIRE / CONSOLIDATE]
```

---

## The 6 Lifecycle Stages

### 1. Discover (Dual-Track Agent-First Search)

- Inspect task requirements using the 10 Universal Capabilities.
- Search installed workspace skills, global skills, and marketplace catalogs (`search_marketplace`).
- **Dual-Track Online Search (`search_web`)**:
  - **Track A (Native Agent Skills & Registries)**: Search for packaged `SKILL.md` repositories, `npx skills add` packages, `skillsdirectory.com`, and GitHub agent skill ecosystems (e.g. `cathrynlavery/diagram-design`).
  - **Track B (Model Context Protocol)**: Search for MCP servers exposing structured JSON-RPC tool endpoints.
  - Avoid category confusion between standalone desktop applications and installable agent skills.
- Distinguish active agent runtimes from passive detected directories.

### 2. Vet & Present Top 3 Candidates (HIL Gate)

- Filter discovered online skills through the multidimensional trust rubric (authenticity, provenance, permissions, code quality).
- **List Top 3 Candidates**: Present the **top 3 matching skills/plugins** found online (including name, source URL, key capabilities, and trust rating).
- **Human-in-the-Loop (HIL) Checkpoint**: Stop and ask the user which of the 3 candidates they prefer to use/install, or how they wish to proceed. Never auto-install or skip directly to custom synthesis.

### 3. Orchestrate

- Match the user-approved skill or subagent to the active turn.
- Compose capability contracts into continuous workflow DAGs with verified data-flow handoffs.
- Recommend project setup or engineering tools only when the user requests project structural changes; Skill Factory focuses strictly on agent capability selection.

### 4. Evaluate / Synthesize (The 3-Repetition Rule + HIL)

- **Strict 3-Repetition Gate ($\ge 3$ Times)**: Custom skill synthesis from scratch is ONLY permitted when:
  1. Web search has been performed and the Top 3 external candidates were presented first, AND
  2. The target workflow has been repeated at least **3 times** ($\ge 3$ repetitions), OR the user explicitly commands custom synthesis in a **Human-in-the-Loop (HIL)** step after reviewing the external options.
- Run the 4-Gate Deduplication Filter to ensure high ROI, distinct domain entity, and clear negative boundaries.
- Staged Isolation: Synthesize inside a temporary staging directory first. Existing user files are 100% preserved if validation fails.

### 5. Certify (HIL Activation Gate)

- Run multi-layer static AST and security audit on newly synthesized code.
- Execute repository-maintainer unit and evaluation benchmarks from `tests/skill_factory/`; these development assets are not shipped with the installable skill.
- Enforce `SKILL.md` (`metadata.version`) as the Single Source of Truth (SSOT) for skill versioning; never duplicate version numbers in scripts, `evals.json`, or references, and automatically bump `metadata.version` in `SKILL.md` whenever an existing skill is updated.
- Rollback cleanly if vulnerabilities or AST violations are detected without touching target directory.
- **Human-in-the-Loop (HIL)**: Request explicit user approval prior to final skill activation.

### 6. Retire / Consolidate

- Detect obsolete or overlapping skills ($\ge 80\%$ overlap).
- Consolidate micro-skills into domain entity parent skills as subcommands (with HIL confirmation).
