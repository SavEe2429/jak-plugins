# Agent Skill Authoring Best Practices Guide

Engineering guidelines for designing, authoring, and benchmarking **Agent Skills** according to industry standards (Anthropic, NVIDIA ACES, OpenClaw).

---

## 1. Five-Tier Standards Framework

To eliminate rigid dogmatism while ensuring safety and portability, standards are categorized into five distinct operational tiers:

### Tier 1: Mandatory Standards (Non-Negotiable)

- [ ] **Kebab-Case Naming:** Skill directory and identifier must adhere to `^[a-z0-9]+(-[a-z0-9]+)*$` (3-50 chars).
- [ ] **Security Screening:** Must pass static AST and pattern analysis. Zero unreviewed `eval()`, `exec()`, or credential exfiltration sinks.
- [ ] **Explicit Scope & Allowed Tools:** Frontmatter must explicitly declare `allowed-tools`, scoped as narrowly as the host's syntax allows. Treat the field as a declaration of the tools the skill requests, not as sandboxing: in Claude Code it pre-approves the listed tools for the invoking turn and does not restrict other tools. Real restriction needs host controls such as `disallowed-tools` or permission deny rules, and tool names are host-specific (names a host does not recognize have no effect there).
- [ ] **Isolated Staging on Synthesis:** New or updated skills must be staged in an isolated temporary directory; rollback must preserve existing files without data loss.

### Tier 2: Recommended Standards (Strongly Advised)

- [ ] **Progressive Disclosure:** Keep `SKILL.md` under 500 lines for core operational rules; offload heavy specifications to `references/` and deterministic logic to `scripts/`.
- [ ] **Deterministic Script Offloading:** Use Python scripts for reproducible transformations and file generation rather than consuming reasoning tokens on boilerplate.
- [ ] **Explicit Triggers:** Declare both positive activation phrases and negative boundaries (`when not to use`) to prevent model routing collisions.

### Tier 3: Contextual Standards (Apply When Appropriate)

- [ ] **Dependency Management via `uv`:**
  - _When External Packages Needed:_ Use `uv` with PEP 723 inline script metadata (`# /// script ... ///`) or `uv.lock`. Avoid unpinned `requirements.txt`.
  - _When Standard Library Only:_ Pure Python standard library scripts need no external dependency manager. Do not force unnecessary tooling into lean environments.
- [ ] **Line Endings:** Use strict LF line endings (`eol=lf`) for Git-versioned cross-platform repositories.

### Tier 4: Project-Specific Standards (Repository Governed)

- [ ] **Actionable Checkboxes:** Use `- [ ]` for actionable acceptance criteria and workflows when enforced by project conventions.
- [ ] **Documentation Tone:** Zero emojis in technical documentation and code manifests if specified by repository policy.
- [ ] **Custom Conventions:** Follow domain-specific guidelines defined in project root `AGENTS.md`.

### Tier 5: Optional Practices (Advisory)

- [ ] **Visual Workflow Diagrams:** Include Mermaid flowcharts (`flowchart TD`) for complex multi-step state progressions.
- [ ] **Evaluation Harnesses:** Define scenario benchmarks in `evals/evals.json` for continuous validation.

---

## 2. Progressive Disclosure Architecture

To protect the agent's context window while preserving deep technical depth:

```text
[Skill Knowledge Root]
       |
       +-> SKILL.md (< 500 lines)  : Core workflow, non-negotiables, trigger index
       |
       +-> references/             : In-depth domain specifications, formulas, schemas
       |
       +-> scripts/                : Deterministic executable utilities returning lean summaries
       |
       +-> tests/                  : Unit tests and automated failure-injection harnesses
       |
       +-> evals/                  : Scenario benchmarks and evaluation definitions
```

---

## 3. Trigger Engineering & Description Optimization

The `description` field in frontmatter governs whether the agent loads the skill into context:

```yaml
---
name: my-specialized-skill
description: >-
  [WHAT IT DOES: Concise summary of capability] - [WHEN TO USE: Explicit phrases and contexts]
  - [WHEN NOT TO USE: Explicit boundaries to prevent trigger collision].
allowed-tools:
  - "Bash(python scripts/*)"
  - Read
  - run_command
  - read_file
---
```

- [ ] **Explicit Positive Triggers:** List specific user phrases, commands, and project states that warrant invocation.
- [ ] **Explicit Negative Boundaries:** Define what the skill does NOT do (e.g. "NOT when the codebase already exists") to prevent stealing context from other skills.
- [ ] **Avoid Generic Wording:** Do not write broad phrases like "Helps with coding", which cause over-triggering and context bloat.

---

## 4. Anti-Sprawl & Skill Deduplication (4-Gate Filter)

To prevent skill bloat and routing collisions under **The 3-Repeat Rule**, all candidates must pass the 4-gate deduplication filter detailed in `references/skill_deduplication_framework.md`:

- [ ] **Gate 1: Semantic Overlap Analysis:** Discard candidate if intent overlap $\ge 80\%$ with an existing skill.
- [ ] **Gate 2: Entity Lifecycle Ownership:** If an existing skill owns the resource/domain entity ($50\% - 79\%$ overlap), extend it with subcommands or scripts rather than creating a micro-skill.
- [ ] **Gate 3: Complexity & Return on Investment (ROI):** Reject one-liner shell commands or trivial zero-shot LLM tasks. Require deterministic multi-step workflows ($\ge 3$ steps).
- [ ] **Gate 4: Negative Trigger Boundary:** Explicitly define positive triggers and negative boundaries to eliminate routing conflict.
- [ ] **Knowledge vs Action Separation (YAGNI):** Do not write speculative code for unencountered problems. Document potential downstream risks and engine gotchas in `references/`, while keeping scripts lean and focused on verified fixes.
