# NVIDIA SkillEvaluator & SkillSpector Framework (ACES Architecture)

Technical reference for evaluating and auditing Agent Skills based on NVIDIA's **ACES (Agentic Continuous Evaluation of Skills)** research and the **SkillEvaluator / SkillSpector** framework.

---

## 1. Core Philosophy

Agent Skills introduce specialized workflows and domain guidelines. Unvetted skills introduce operational hazards:

1. **Security Vulnerabilities:** Indirect prompt injection, arbitrary command execution, or sensitive data exfiltration.
2. **Context Pollution & Token Bloat:** Degrading model reasoning capacity by consuming context window with redundant instructions.
3. **Negative Skill Lift:** Causing model degradation, confusion, or regression compared to baseline model performance without the skill.

NVIDIA's framework enforces a **Three-Tier Evaluation Pipeline** before any skill is approved for deployment.

---

## 2. The Three-Tier Evaluation Pipeline

### Tier 1: SkillSpector (Security, Static Checks & Injection Defense)

Deterministic static analysis of `SKILL.md` and associated executable scripts:

- [ ] **Prompt Injection & Instruction Hijacking:**
  - Detects adversarial manipulation patterns or zero-width Unicode characters.
- [ ] **Data Exfiltration Vectors:**
  - Detects outbound network patterns and webhooks targeting untrusted endpoints.
  - Detects unauthorized access to sensitive local resources and credential files.
- [ ] **Obfuscated Code Execution:**
  - Blocks dynamic execution vectors and encoded string decoding.
- [ ] **Secrets & Credential Leaks:**
  - Scans for hardcoded API keys, JWT tokens, private certificates, and passwords.
- [ ] **Context Weight & Token Budget:**
  - `SKILL.md` must not exceed **500 lines** or **4,000 tokens**. Detailed references, schemas, and code must be offloaded to `references/` or `scripts/` following progressive disclosure.

---

### Tier 2: Distinctiveness & Deduplication (Conflict & Overlap Prevention)

Prevents skill catalog pollution and trigger ambiguity:

- [ ] **Trigger Collision Detection:**
  - Analyzes the `description` field against all existing installed skills.
  - Flags semantic overlap where two skills compete for the same user prompt, risking non-deterministic activation.
- [ ] **Guidance Deduplication:**
  - Identifies circular, contradictory, or redundant instructions within the skill body.

---

### Tier 3: Live Evaluation & "Skill Lift" Metric (Empirical Value)

A skill is only justified if it provides measurable, positive performance lift:

$$\text{Skill Lift} = \text{Performance}_{\text{with\_skill}} - \text{Performance}_{\text{without\_skill}}$$

- [ ] **Controlled A/B Benchmarking:**
  - Executes identical evaluation tasks across two conditions:
    1. Baseline run: Agent operates without the target skill.
    2. Test run: Agent operates with the target skill loaded into context.
- [ ] **Evaluation Dimensions:**
  - **Task Success Rate (%):** Improvement in goal completion rate.
  - **Tool Efficiency:** Reduction in unnecessary tool calls and round-trips.
  - **Token Efficiency:** Ratio of token consumption to performance gains.
- [ ] **Evaluation Verdicts:**
  - **PASS / CERTIFIED:** Skill Lift > 0% and 100% clean SkillSpector pass.
  - **ZERO LIFT (WARN):** Skill Lift = 0%. The base model resolves the task without the skill; skill introduces unnecessary context weight.
  - **NEGATIVE LIFT (REJECT):** Skill Lift < 0%. Skill instructions cause hallucinations, looping, or task failures.
