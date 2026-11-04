# jak-plugins

A skill bundle for **Claude** (Claude Code), **GPT** (OpenAI Codex CLI) and
**Gemini** (Antigravity and Gemini CLI).
One `skills/` folder, thin adapters for each host.

| Skill | What it does |
|---|---|
| `project-scaffolder` | Scaffold a new project or audit an existing one, using evidence-selected profiles (web, game, embedded, systems, AI/data, security). |
| `skill-factory` | Discover, evaluate, select and compose skills, plugins, MCP servers and tools for a task. |

## Layout

```text
skills/<name>/SKILL.md                              single source of truth (Agent Skills format)
.claude-plugin/                                     Claude Code plugin + marketplace manifests
plugin.json                                         Antigravity plugin manifest
AGENTS.md, prompts/*.md                             OpenAI Codex CLI
gemini-extension.json, GEMINI.md, commands/*.toml   Gemini CLI extension
```

Edit the skills, not the adapters.

## Claude Code

```bash
/plugin marketplace add SavEe2429/jak-plugins
/plugin install jak-plugins@jak-plugins-marketplace
```

Skills trigger automatically from their descriptions.

## OpenAI Codex CLI (GPT)

Copy the skills into Codex's skills folder:

```bash
mkdir -p ~/.codex/skills && cp -r skills/* ~/.codex/skills/
```

Optional slash commands `/project-scaffolder` and `/skill-factory` (absolute path baked in):

```bash
mkdir -p ~/.codex/prompts
for f in prompts/*.md; do
  sed "s|__PLUGIN_DIR__|$(pwd)|g" "$f" > ~/.codex/prompts/$(basename "$f")
done
```

For a single repo you can instead append `AGENTS.md` to that repo's own `AGENTS.md`
and fix the relative paths.

## Antigravity (Gemini)

```bash
git clone https://github.com/SavEe2429/jak-plugins ~/.gemini/config/plugins/jak-plugins
```

Restart Antigravity. `plugin.json` registers the bundle and `skills/` is picked up
automatically. If the same skills also sit in `~/.gemini/config/skills/`, delete those
copies so they do not load twice.

## Gemini CLI

```bash
gemini extensions install https://github.com/SavEe2429/jak-plugins
```

`GEMINI.md` loads the skill index as context. Slash commands:
`/project-scaffolder`, `/skill-factory`.

## Requirements

Both skills ship Python helper scripts (`scripts/`). Python 3.10+ is assumed.
