# Anti-Sprawl & Skill Deduplication Framework

Engineering guidelines for evaluating, deduplicating, and synthesizing skills under **The 3-Repeat Rule** to eliminate skill bloat and routing collisions.

---

## 1. Overview & Objective

When an AI agent detects that a workflow or error-handling pattern has repeated $\ge 3$ times, it treats this as a **signal to evaluate** whether to synthesize a permanent skill (not an automatic trigger). Without strict deduplication gates, repetitive workflows lead to **Skill Sprawl**:

- **Semantic Overlap:** Multiple skills addressing the same root problem under slightly different phrasing.
- **Routing Collisions:** The model hesitates or flips coins between overlapping skills, degrading inference quality.
- **Context Bloat:** Excessively narrow micro-skills consume reasoning tokens without providing deterministic value.

This framework enforces the **4-Gate Deduplication Architecture** and the **Knowledge vs Action Separation Protocol** before invoking `skill-creator`.

---

## 2. The 4-Gate Deduplication Architecture

```
[Workflow / Fix Pattern Repeated >= 3 Times]
                     |
                     v
       [Web Research & Root Cause Protocol]
  (Verify Symptom vs Root Cause & Cascading Risks)
                     |
                     v
      [Gate 1: Semantic Overlap Analysis]
                     |
         +-----------+-----------+
         | Overlap >= 80%        | Overlap 50% - 79%
         v                       v
    [DISCARD / REJECT]      [EXTEND / MERGE]
 (Use existing skill)    (Add script/flag to existing)
         |
         | Overlap < 50%
         v
      [Gate 2: Entity Lifecycle Ownership]
                     |
         +-----------------------+
         | Entity Already Owned  | New Distinct Entity
         v                       v
      [MERGE]                 [Gate 3: Complexity & ROI]
 (Consolidate into owner)        |
                                 +-----------------------+
                                 | Trivial / One-liner   | Multi-step / Deterministic
                                 v                       v
                              [SKIP]                  [Gate 4: Negative Trigger Boundary]
                       (Keep in AGENTS.md)               |
                                                         +-----------------------+
                                                         | Ambiguous Triggers    | Explicit Boundary
                                                         v                       v
                                                     [RESOLVE]               [PASS -> SYNTHESIZE]
                                              (Disambiguate scope)    (Invoke skill-creator)
```

---

### Gate 1: Lexical Token & Intent Overlap Analysis

Evaluate lexical token and intent overlap (via Jaccard keyword similarity and containment coefficient) between the candidate workflow and all installed skills:

- [ ] **Overlap $\ge 80\%$ (Redundant / Subsumed):**
  - The capability already exists under an equivalent or broader skill.
  - _Action:_ **DISCARD**. Guide the agent to use the existing skill directly.
  - _Example:_ Attempting to create `docker-builder` when `container-build-pipeline` is already present.
- [ ] **Overlap $50\% - 79\%$ (Extension Candidate):**
  - The workflow targets the same functional area or extends an existing capability.
  - _Action:_ **EXTEND**. Prohibit creating a new directory. Add a sub-command, flag, or script to the existing skill.
  - _Example:_ Adding a schema validation flag to an existing `api-client` skill instead of creating an independent `api-validator` skill.
- [ ] **Overlap $< 50\%$ (Distinct Capability):**
  - The workflow represents a fundamentally distinct operational capability.
  - _Action:_ **PROCEED** to Gate 2.

---

### Gate 2: Entity Lifecycle Ownership (Anthropic Standard)

Consolidate operations around **Domain Entities and Resources** rather than splitting by action verbs.

- [ ] **Anti-Pattern (Action-Verb Sprawl):**
  - `create-user`, `update-user`, `delete-user`, `inspect-user`
  - `start-instance`, `stop-instance`, `restart-instance`
- [ ] **Recommended Pattern (Lifecycle Consolidation):**
  - Single skill: `user-lifecycle-manager` or `compute-instance-manager`
  - Controlled via explicit subcommands or script parameters:
    ```bash
    python scripts/manage_user.py --action create --id user_01
    python scripts/manage_user.py --action update --id user_01
    ```
- [ ] **Ownership Check:** If an existing skill already owns the target entity or domain, the new logic must merge into that skill's lifecycle script.

---

### Gate 3: Complexity & Return on Investment (ROI)

Prevent polluting the skill registry with trivial commands or volatile ad-hoc workflows.

- [ ] **Trivial Shell Commands:** One-line commands (e.g. `git status`, `npm test`, `tree`) must never become skills.
- [ ] **Zero-Shot LLM Reasoning:** Generic prompts and formatting tasks that the base LLM reliably handles zero-shot do not qualify.
- [ ] **Deterministic Multi-Step Workflows:** Workflows qualify if they require:
  - $\ge 3$ deterministic steps with precise order of operations.
  - Custom local CLI utilities or scripts in `scripts/`.
  - Non-trivial validation, file transformation, or schema compliance.

---

### Gate 4: Negative Trigger Boundary (NVIDIA Tier 2 Standard)

Eliminate routing ambiguity by defining explicit positive and negative activation conditions in `SKILL.md` frontmatter:

- [ ] **Positive Triggers:** Specify exact phrases, tool states, and project events where this skill must activate.
- [ ] **Negative Triggers:** Explicitly declare situations where this skill **MUST NOT** activate and state which tool or skill to delegate to instead.
- [ ] **No Overlap Guarantee:** If a user request could reasonably trigger both Skill A and Skill B, the boundary must be refined before publishing.

---

## 3. Web Research & Root Cause Protocol

When an error pattern or workflow repeats 3 times, perform structured web research before synthesizing any skill:

```
[Candidate Pattern] --> [Web Search] --> [Verify Root Cause vs Symptom]
                                    --> [Identify Cascading Pitfalls / Breaking Changes]
                                    --> [Separate Knowledge vs Action (YAGNI)]
```

### 3.1. Symptom vs Root Cause Verification

- Do not automate a workaround. Verify whether the repeated issue is an underlying architectural flaw, a misconfigured flag, or standard engine behavior.
- Use official documentation and primary issue trackers (e.g. GitHub Issues, official project trackers, RFCs) rather than unverified blog workarounds.

### 3.2. Cascading Failure & Pitfall Detection

- Identify whether fixing or automating this issue introduces side-effects (e.g. modifying an environment flag that breaks cross-platform builds).
- Document all known downstream impacts before finalizing the workflow.

### 3.3. Knowledge vs Action Separation (YAGNI Principle)

To prevent speculative over-engineering:

| Category                                      | Storage Location                | Rule                                                                                                             |
| --------------------------------------------- | ------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| **Deterministic Fix for Real Issues**         | `scripts/` and `SKILL.md`       | Implement only what has been tested and verified in this environment. Keep scripts lean.                         |
| **Potential Future Traps / Cascading Issues** | `references/troubleshooting.md` | Document as checklists and gotchas for agent awareness. **Do NOT write speculative code for unobserved issues.** |
| **Official Engine / Tool Standards**          | `references/`                   | Reference official API docs and configuration specifications.                                                    |

---

## 4. Deduplication Decision Matrix

| Evaluation Outcome                                 | Action Required    | Storage / Destination                             |
| -------------------------------------------------- | ------------------ | ------------------------------------------------- |
| Semantic Overlap $\ge 80\%$                        | **Discard**        | Guide agent to existing skill                     |
| Entity Already Owned ($50\% - 79\%$)               | **Extend / Merge** | Add subcommand or script to existing skill folder |
| Trivial / Single-command                           | **Skip**           | Document in `AGENTS.md` if project-specific       |
| Distinct Entity + High Complexity + Clear Boundary | **Synthesize**     | Proceed to `skill-creator`                        |
