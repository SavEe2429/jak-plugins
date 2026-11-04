# Evidence-Based Trust, Safety & Security Rubric for Agent Skills

Evaluation rubric used by `skill-factory` to vet third-party **Skills**, **Plugins**, and **MCP Servers** prior to installation or recommendation.

---

## 1. Threat Model for Agent Extensions

1. **MCP Servers (Highest Risk - Native Process Execution & Credentials):**
   - Native OS process access with potential to execute arbitrary shell commands or exfiltrate environment variables.
2. **Skills & Bundled Scripts (Arbitrary Execution Scope):**
   - Executable scripts in `scripts/` run with the user's host shell privileges.
   - `SKILL.md` can induce model behavior modification or prompt injection.
3. **Plugins & Hooks (Lifecycle Interception):**
   - Capable of intercepting tool execution events via `hooks.json`.

---

## 2. Multidimensional Evidence-Based Trust Evaluation

Trust is not awarded merely because of a vendor name or repository popularity. `skill-factory` evaluates extensions across six empirical dimensions:

| Dimension                            | Verification Evidence                           | High Trust Indicator                                                                        | Critical Risk Indicator                                                |
| ------------------------------------ | ----------------------------------------------- | ------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| **1. Publisher Authenticity**        | Vendor identity and cryptographic signatures    | Maintained by verified official vendors (Anthropic, Google, MCP, Microsoft, NVIDIA, Vercel) | Anonymous author, unverified fork, or typosquatting identity           |
| **2. Source Provenance**             | Public source history and license               | Public repository, verifiable commit history, standard permissive license (MIT, Apache 2.0) | Closed-source binary, unpinned remote git URL, missing license         |
| **3. Code Quality & Static AST**     | AST parsing of executable scripts               | Zero unreviewed dynamic calls (`eval`, `exec`), no `shell=True` subprocesses                | Obfuscated Base64 execution, dynamic code strings, syntax errors       |
| **4. Permission Risk & Sandboxing**  | Declared tools plus independently verified host policy | Minimal, task-scoped declaration and separate evidence that the host enforces it            | Wildcard declarations or claims of enforcement without host evidence   |
| **5. Runtime Behavior & Data-Flow**  | Source-to-sink data-flow analysis               | Clean separation of credentials from outbound network requests                              | Accessing `sensitive local configuration` / API tokens and transmitting to external sinks |
| **6. Maintenance & Vulnerabilities** | Dependency security & CVE history               | Active commits in last 6 months, clean vulnerability audits                                 | Abandoned repository, unpinned pipe-to-shell downloads (`unsafe remote-script execution idioms`)  |

---

## 3. Dynamic Evidence-Based Trust Tiers

| Trust Classification                 | Empirical Evidence Required                                                                               | Operational Policy                                                                  |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| **Tier 1: Verified Publisher**       | Maintained by verified vendor, clean AST scan, least-privilege declarations, independently evidenced host enforcement, and zero data exfiltration sinks. | **RECOMMENDED**: Trusted for recommendation with publisher attribution.             |
| **Tier 2: Audited Open Source**      | Public source repo, verified commit history, permissive license, clean AST/data-flow scan, and reviewed permission declarations. | **AUDITED PASS**: Reusable with maintainer attribution and clear scope declaration. |
| **Tier 3: Unverified / Third-Party** | Unknown author, unpinned repository, missing license, or unreviewed scripts.                              | **MANUAL AUDIT REQUIRED**: Line-by-line inspection required before execution.       |
| **Tier 4: Malicious / Blocked**      | Obfuscated code, shell pipes, credential exfiltration patterns, prompt injections, or reverse shells.     | **STRICTLY BLOCKED**: Execution prohibited; immediate security notification.        |

---

## 4. The 3 Security Inspection Gates

Every skill must pass three inspection gates:

- [ ] **Gate 1: Static AST, Multi-line & Data-Flow Analysis:**
  - Zero dynamic code evaluations (`eval`, `exec`).
  - Zero unpinned remote-script download-and-execute pipelines.
  - Zero raw subprocess execution with `shell=True`.
  - Zero hardcoded credential tokens.
  - Zero source-to-sink credential exfiltration (`sensitive local configuration` -> network sink).
- [ ] **Gate 2: Optional External Audit (NVIDIA SkillSpector):**
  - Execute `skillspector scan <skill-path> --no-llm` when available on PATH.
  - If unavailable, report `NOT VERIFIED (SkillSpector not on PATH)`. Never falsely claim full external certification.
- [ ] **Gate 3: Least Privilege & Sandboxing:**
  - Inspect the `allowed-tools` frontmatter declaration for missing, duplicate, malformed, or wildcard entries.
  - Treat the declaration as metadata describing requested agent tools, not as proof of enforcement.
  - Verify host/runtime enforcement separately from authoritative platform documentation or runtime tests.
  - Do not claim filesystem, environment, shell, or network confinement from a manifest declaration or static scan alone.
  - Review access to environment variables and credential stores in executable code.

## 5. Incident Response Evidence Workflow

For suspected credential exposure or unauthorized outbound activity:

1. Preserve evidence before changing files or rewriting history; record source paths, timestamps, command output, and scanner versions.
2. Reconstruct an event timeline from logs, process output, repository history, and available provider audit records.
3. Trace the suspected credential from its source to any file, process, or network sink. Distinguish observed transmission from mere credential access.
4. Identify the affected credential and service, then recommend revocation or rotation through the service owner. Do not print or copy secret values into reports.
5. If repository history contains exposed secrets, assess history rewriting with tools such as `git-filter-repo` only after containment and coordination with collaborators.
6. Record root cause, scope, evidence gaps, containment, recovery, and follow-up controls in a post-incident report.
