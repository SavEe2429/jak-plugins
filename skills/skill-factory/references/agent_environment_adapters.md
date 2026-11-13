# Multi-Agent Environment Adapters

`skill-factory` is machine-independent and agent-agnostic. It adapts dynamically to the host AI environment rather than hardcoding vendor-specific paths.

---

## Supported Agent Environments

| Agent Environment                   | Global Skills Directory                                      | Workspace Skills Directory                            | CLI identity               |
| ----------------------------------- | ------------------------------------------------------------ | ----------------------------------------------------- | -------------------------- |
| **Google Antigravity / Gemini CLI** | `~/.gemini/skills/` (then `~/.agents/skills/` for discovery) | `.agents/skills/` (preferred), then `.gemini/skills/` | `--agent gemini`           |
| **OpenAI Codex CLI / IDE**          | `~/.agents/skills/`                                          | `.agents/skills/`                                     | `--agent codex`            |
| **Anthropic Claude Code**           | `~/.claude/skills/`                                          | `.claude/skills/`                                     | `--agent claude`           |
| **Cursor Editor**                   | No global path declared by this adapter                      | `.cursor/skills/` and `.cursor/rules/`                | `--agent cursor`           |
| **GitHub Copilot**                  | No global path declared by this adapter                      | `.github/skills/`                                     | `--agent copilot`          |
| **Local fallback**                  | No global path                                               | `.agents/skills/` and `.skills/`                      | `--agent local` or omitted |
| **Custom override**                 | N/A                                                          | Explicit directory                                    | `--skills-dir <path>`      |

Gemini's `.agents/skills/` path is the preferred shared workspace location; the adapter also discovers `.gemini/skills/` for compatibility. Claude Code uses its native `.claude/skills/` path. Codex uses `.agents/skills/`.

---

## Runtime identity & Installation Scopes (`project` vs `user`)

The CLI does not infer the active host from installed executables or passive workspace files. Pass the runtime identity explicitly with `--agent` (or `--active-agent`) and choose the target installation scope with `--scope`:

- **Project / Workspace Scope (`--scope project` or `--scope workspace`):** Installs into the repository-local skills directory (e.g. `.agents/skills/`, `.claude/skills/`, `.cursor/skills/`, `.github/skills/`). Ideal for project-specific workflows or team version-control sharing.
- **User / Global Scope (`--scope user` or `--scope global`):** Installs into the user's home configuration directory (e.g. `~/.gemini/skills/`, `~/.agents/skills/`, `~/.claude/skills/`, `~/.cursor/skills/`). Ideal for reusable personal skills across all projects on the machine.

For example:

```bash
# Project-level (workspace) synthesis or fetch
python scripts/scaffold_skill.py --agent gemini --scope project --synthesize --name example --desc "Example workflow" --dry-run
python scripts/skill_fetcher.py --repo owner/repo --skill example --agent claude --scope project --dry-run

# User-level (global) synthesis or fetch
python scripts/scaffold_skill.py --agent gemini --scope user --synthesize --name example --desc "Example workflow" --dry-run
python scripts/skill_fetcher.py --repo owner/repo --skill example --agent codex --scope user --dry-run
```

If no identity is supplied, installation target selection uses the local fallback adapter (`.agents/skills/` for `project`/`workspace`, or `~/.agents/skills/` for `user`/`global`). Use `--skills-dir` (or `--target-dir` in `skill_fetcher.py`) to explicitly override the install and discovery directory.

---

## Discovery path priority

The orchestrator resolves roots in this order:

1. **Explicit custom override:** existing path passed via `--skills-dir`.
2. **Active Agent workspace paths:** every existing workspace discovery path returned by the explicitly selected adapter.
3. **Other detected workspace paths:** every existing workspace path returned by the other adapters.
4. **Global and built-in paths:** every existing global or built-in path returned by the adapters.

Duplicate paths are included only once. Within Gemini, workspace order is `.agents/skills/` then `.gemini/skills/`; global order is `~/.gemini/skills/`, then `~/.agents/skills/`, followed by Antigravity built-in skills.

## Web-hosted skill deployment

Web products expose their own skill or instruction-management surfaces. They are not filesystem paths and are not selected by the local CLI's `--agent` argument. This repository does not automate browser uploads or account-level activation.

| Web product                | Native capability                                                                                                                                                                                    | Deployment path and boundary                                                                                                                                                                            |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ChatGPT Web**            | Skills can be uploaded and installed for eligible ChatGPT workspaces/plans.                                                                                                                          | In ChatGPT, open Plugins > Plugin Directory > Skills > Create > Upload from computer. Availability and permissions depend on plan and workspace settings. The local CLI does not upload or activate it. |
| **Gemini Web**             | Gemini Apps supports importing a skill from a `SKILL.md`, folder, or ZIP containing the root `SKILL.md`.                                                                                             | In gemini.google.com, open Customize > Skills > Create/Upload. Scripts that require internet access are not supported by the current upload workflow.                                                   |
| **Claude Web (claude.ai)** | The reviewed official help material documents Projects with project instructions and uploaded knowledge files, but does not establish a native Agent Skills / `SKILL.md` upload-and-install surface. | Use Project instructions and project knowledge as a manual adaptation only; do not claim parity with Claude Code Skills or automatic skill activation.                                                  |

For ChatGPT and Gemini Web, the package may be uploaded through the product UI after review. This is a user-controlled deployment step, not an Adapter install target. Claude Code remains supported separately through `.claude/skills/`.

Official product references (availability and UI may change):

- [Skills in ChatGPT](https://help.openai.com/en/articles/20001066-skills-in-chatgpt)
- [Create and manage skills for Gemini Apps](https://support.google.com/gemini/answer/17094296?hl=en)
- [Claude Projects and project knowledge](https://support.anthropic.com/en/articles/9519177-how-can-i-create-and-manage-projects)
