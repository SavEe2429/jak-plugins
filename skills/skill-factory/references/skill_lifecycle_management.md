# Agent Skill Lifecycle Management

`skill-factory` manages the full lifecycle of agent capabilities across 6 stages:

```
[1. DISCOVER] --> [2. VET & AUDIT] --> [3. ORCHESTRATE]
       |
       v
[4. EVALUATE / SYNTHESIZE] --> [5. CERTIFY] --> [6. RETIRE / CONSOLIDATE]
```

---

## The 6 Lifecycle Stages

### 1. Discover

- Inspect task requirements using the 10 Universal Capabilities.
- Search installed workspace skills, global skills, and marketplace catalogs.
- Distinguish active agent runtimes from passive detected directories.

### 2. Vet & Audit

- Static AST and multi-line pattern inspection via `security_scanner.py`.
- Source-to-sink data-flow analysis to detect credential exfiltration.
- Optional external verification using NVIDIA `skillspector scan --no-llm` when available on PATH.
- Apply multidimensional trust rubric (authenticity, provenance, permissions, code quality).

### 3. Orchestrate

- Match the optimal skill or subagent to the active turn.
- Compose capability contracts into continuous workflow DAGs with verified data-flow handoffs.
- Recommend project setup or engineering tools only when the user requests project structural changes; Skill Factory focuses strictly on agent capability selection.

### 4. Evaluate / Synthesize (The 3-Repeat Signal)

- A repetitive workflow occurring $\ge 3$ times is a **signal to evaluate**, not an automatic mandate to synthesize.
- Run the 4-Gate Deduplication Filter to ensure high ROI, distinct domain entity, and clear negative boundaries.
- Staged Isolation: Synthesize inside a temporary staging directory first. Existing user files are 100% preserved if validation fails.

### 5. Certify

- Run multi-layer static AST and security audit on newly synthesized code.
- Execute repository-maintainer unit and evaluation benchmarks from `tests/skill_factory/`; these development assets are not shipped with the installable skill.
- Enforce `SKILL.md` (`metadata.version`) as the Single Source of Truth (SSOT) for skill versioning; never duplicate version numbers in scripts, `evals.json`, or references, and automatically bump `metadata.version` in `SKILL.md` whenever an existing skill is updated.
- Rollback cleanly if vulnerabilities or AST violations are detected without touching target directory.
- Request explicit user approval prior to activation.

### 6. Retire / Consolidate

- Detect obsolete or overlapping skills ($\ge 80\%$ overlap).
- Consolidate micro-skills into domain entity parent skills as subcommands.
