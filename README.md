# hybrid-code-review

A five-pass read of a PR or diff that ends where normal review stops: the questions a
senior architect will actually ask, with model answers you can say out loud.

```text
Phase 1  PR Intent & Delta Triage      what was broken, what shape of fix
Phase 2  Macro Anchor (file to file)   where the change sits, blast radius
Phase 3  Dynamic Flow (func to func)   the call chain this PR touches
Phase 4  Contracts & Invariants        I/O, invariants, edge cases, the "why"
Phase 5  Technical Defense Simulation  the grilling, with model answers
```

Approval review asks "is this correct?". This asks "can I answer any question about it
in a room full of people who did not write it?".

## Single source of truth

`skills/hybrid-code-review/SKILL.md` holds the whole method. Every other file in this
repo is a thin host adapter that points at it. Edit the SKILL, not the adapters.

## Install — Claude Code

```bash
/plugin marketplace add /absolute/path/to/hybrid-code-review-plugin
/plugin install hybrid-code-review@hybrid-code-review-marketplace
```

The skill then triggers on its own from the description, or on demand via the Skill
tool. If you previously copied `SKILL.md` into a project's `.claude/skills/`, delete
that copy — two copies drift.

## Install — Gemini CLI

```bash
gemini extensions install /absolute/path/to/hybrid-code-review-plugin
```

`GEMINI.md` loads as context; `/hybrid-code-review [target]` runs it explicitly.

## Install — Codex CLI

Codex reads custom prompts from a fixed directory, so the prompt file needs an absolute
path baked in:

```bash
mkdir -p ~/.codex/prompts
sed "s|__PLUGIN_DIR__|$(pwd)|" prompts/hybrid-code-review.md \
  > ~/.codex/prompts/hybrid-code-review.md
```

Then `/hybrid-code-review <target>` in Codex. For a single repo you can instead append
`AGENTS.md` to that repo's own `AGENTS.md` and fix the relative path.

## Optional — code-review-graph

Phases 1–3 are structural questions. With the `code-review-graph` MCP server they take
one call each instead of twenty greps, and you additionally get per-function risk scores
and test gaps — the last of which feeds Phase 5's sharpest question ("no test covers
this, so how do you know it works?").

Deliberately **not** bundled in `gemini-extension.json`: the server needs a per-repo
`cwd` and it reads the whole tree, so installing it silently on every repo is the wrong
default. The skill detects its absence, offers this config once, and falls back to git
and grep if you decline:

```jsonc
// .mcp.json at the repo root
{
  "mcpServers": {
    "code-review-graph": {
      "type": "stdio",
      "command": "uvx",
      "args": ["code-review-graph", "serve"],
      "cwd": "<absolute path to repo root>"
    }
  }
}
```

Restart the session, run the build once, and the fast path turns itself on. Phases 4
and 5 are unchanged either way — a graph knows that `A` calls `B`, not that unit ids
must stay unique.
