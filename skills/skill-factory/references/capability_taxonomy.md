# Universal Capability Taxonomy for AI Agents

`skill-factory` uses these ten capability facets as a shared vocabulary across domains. They are optional labels for reasoning about a particular task, not a required checklist, fixed lifecycle, or tool catalog. Select only facets supported by the user's goal and available evidence. A task may need one facet, several, or none beyond the agent's basic abilities.

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

## Illustrative domain examples

These examples show possible mappings, not canonical or mandatory recommendations. Inspect the actual project and task before selecting tools. Do not infer that an example skill is installed, trustworthy, or available.

### 1. Game Development (e.g., Unity / Godot)

- **Possible Capabilities:** Creation, Validation, Analysis, Design, or Delivery depending on the requested work and engine.

### 2. Data Science & Machine Learning

- **Possible Capabilities:** Research, Analysis, Creation, or Validation depending on whether the task concerns literature, data, modeling, or reproducibility.
- _Excluded (N/A):_ Graphics rendering inspection, UI wireframing.

### 3. Business & Financial Analysis

- **Possible Capabilities:** Planning, Research, Analysis, or Delivery depending on the decision and requested artifact.
- _Excluded (N/A):_ Test-Driven Development, Compilers, LFS game assets.

### 4. Incident Response & Security Assessment

- **Primary Capabilities:** Security (`security_scanner`, Bandit, Semgrep), Research (CVE search, logs survey), Analysis (Root cause timeline), Delivery (Post-mortem incident report).
