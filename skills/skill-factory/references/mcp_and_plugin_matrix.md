# Illustrative MCP & Plugin Reference Matrix for Agent Capabilities

Reference guide for `skill-factory` to evaluate, discover, and adapt **MCP Servers** and **Plugins** mapped to the 10 Universal Capabilities.

> [!NOTE]
> This matrix is an illustrative reference guide, not a mandatory catalog or a guarantee of availability. Discover capabilities from the actual environment; do not assume external tools are installed or required.

---

## 1. Role of MCP Servers & Plugins

While **Skills** provide domain workflows, guidelines, and deterministic CLI scripts, **MCP Servers (Model Context Protocol)** and **Plugins** connect the AI agent to external processes, databases, browser runtimes, and live APIs.

`skill-factory` verifies that recommended MCP servers adhere to least-privilege scoping and zero-trust sandboxing.

---

## 2. MCP & Plugin Mapping to Universal Capabilities

| Capability           | Target Operational Need                                                       | Recommended MCP Server / Plugin                                                                                                                                                           | Benefit & Scope                                                                                                        |
| -------------------- | ----------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| **1. Planning**      | Specification drafting, backlog synchronization, issues tracking              | • **Linear MCP** (`linear`)<br>• **Jira / Atlassian TWG** (`atlassian-twg-cli`)                                                                                                           | Syncs user stories, acceptance criteria, and project milestones directly to task context.                              |
| **2. Research**      | Live API documentation, library specs, web exploration                        | • **Context7 MCP** (`@upstash/context7-mcp`)<br>• **Google Developer Knowledge**<br>• **Browserbase MCP** (`browse`)                                                                      | Fetches up-to-date SDK syntax and real-time framework documentation to eliminate deprecated code.                      |
| **3. Design**        | System topology, component design, schema models                              | • **Figma Plugin** (`figma`)<br>• **Canva Plugin** (`canva`)                                                                                                                              | Translates UI/UX designs into component tokens and architecture diagrams.                                              |
| **4. Creation**      | Task-specific authoring, asset creation, or project generation when requested | • An available skill or native tool matched to the requested artifact<br>• Verify stack fit and current availability before recommending                                                  | Select from the actual environment; this matrix is vocabulary, not a fixed catalog or a promise of availability.       |
| **5. Validation**    | Browser inspection, DOM layout, automated tests, acceptance checks            | • **Chrome DevTools Plugin** (`chrome-devtools-plugin`)<br>• **Playwright MCP** (`@playwright/mcp`)<br>• Browser / GUI test tools (e.g. Playwright, visual QA when available)             | Executes headless/headful browser tests, inspects DOM elements, checks console errors, and verifies layout boundaries. |
| **6. Analysis**      | Database inspection, SQL query validation, runtime logs                       | • **PostgreSQL MCP** (`@modelcontextprotocol/server-postgres`)<br>• **SQLite MCP** (`@modelcontextprotocol/server-sqlite`)<br>• **Databricks Plugin** (`databricks`)                      | Validates database migrations, inspects table schemas, and verifies query execution plans.                             |
| **7. Orchestration** | Subagent dispatch, team workflows, CI/CD triggering                           | • **GitHub MCP** (`@modelcontextprotocol/server-github`)<br>• **GitLab MCP** (`@modelcontextprotocol/server-gitlab`)<br>• **Docker MCP** (`@modelcontextprotocol/server-docker`)          | Inspects CI/CD build failures, triggers automated workflows, and coordinates multi-agent subtasks.                     |
| **8. Security**      | Static AST analysis, token exfiltration checks, secret scanning               | • **Security Scanner** (`security_scanner.py`, primary local baseline)<br>• **NVIDIA SkillSpector CLI** (`skillspector`, optional secondary verification)<br>• **Auth0 Plugin** (`auth0`) | Audits extensions for prompt injection, arbitrary command execution, and leaked credential tokens.                     |
| **9. Delivery**      | Cloud deployments, hosting, infrastructure provisioning                       | • **Vercel Plugin** (`vercel-plugin`)<br>• **Netlify Plugin** (`netlify`)<br>• **Railway Plugin** (`railway`)                                                                             | Deploys validated builds, manages preview environments, and tracks deployment logs.                                    |
| **10. Learning**     | Team knowledge management, persistent context, post-mortems                   | • **Memory MCP** (`@modelcontextprotocol/server-memory`)<br>• **Google Workspace Docs/Sheets** (`gdocs`, `gsheets`)                                                                       | Records cross-session architectural decisions, post-mortem findings, and operational logbooks.                         |

---

## 3. Implementation vs Agent Runtime Guidance

To ensure clear architectural boundaries, `skill-factory` distinguishes between what is implemented programmatically and what is guided at runtime:

1. **Implemented Local Discovery (`scripts/capability_matcher.py`):**
   - Automatically inspects standard local MCP configuration files (`~/.claude/claude_desktop_config.json`, `~/.gemini/antigravity/mcp_config.json`, `.cursor/mcp.json`, `mcp.json`).
   - Extracts configured MCP server definitions without making external network calls.
   - Dynamically parses `contract:` blocks and frontmatter from installed `SKILL.md` files.

2. **Agent Runtime External Search & Delegation:**
   - External marketplace catalog search (e.g., via agent `search_marketplace` tool) is triggered interactively when local capabilities do not satisfy a required facet.
   - In accordance with the Zero-Trust principle, external MCP servers or plugins are recommended with concrete rationales and risk tiers; they are never auto-installed or activated without explicit user authorization.

---

## 4. Least Privilege & Security Evaluation for MCP Servers

Before recommending any MCP server or plugin, `skill-factory` enforces:

- [ ] **Native Process Scoping:** Inspect if the MCP server requires raw shell or OS process execution permissions.
- [ ] **Credential Isolation:** Never expose persistent environment credentials in unencrypted or shared configurations.
- [ ] **Read vs Write Isolation:** Prefer read-only filesystem or database scopes when tasks only require inspection.
- [ ] **Audit Trail:** Maintain records of MCP server recommendations and their matching capabilities in `logbook/current.md` when the project already uses that logbook;
  otherwise record them in the project matrix snapshot.

---

## 5. Using this matrix with workstreams and lifecycle stages

This table is organized by capability facet only. For project-wide
recommendations, first resolve workstreams and lifecycle stages using
`workstream_taxonomy.md` and `project_matrix_schema.md`, then use the facet
rows here only as vocabulary for the kinds of integrations that may fill a
gap. Do not copy product names from this table into a matrix cell without
verifying current availability, source, and permissions.
