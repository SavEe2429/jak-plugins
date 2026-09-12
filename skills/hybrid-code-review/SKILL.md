---
name: hybrid-code-review
description: Read a PR or diff in five passes — intent, architecture map, call chain, contracts and invariants, then a simulated technical-defense grilling with model answers. Use whenever the user has to explain, defend, or present a change to someone else — "ต้องดีเฟนด์ PR นี้", "อธิบาย PR นี้ให้หน่อย", "เตรียมตอบคำถามอาจารย์/หัวหน้า", "prep me to defend this branch", "what will they ask about this PR" — or whenever they want to understand a diff deeply rather than approve it. Also use when someone must onboard onto an unfamiliar change fast. Not for a pass/fail verdict — that is /scrutinize — and not for a diagram file — that is /diff-review.
---

# Hybrid Code Review & Technical Defense

Reviewing a diff to approve it and reviewing a diff to *defend* it are different jobs.
Approval asks "is this correct?". Defense asks "can I answer any question about this in
a room full of people who did not write it?". This skill is the second job.

Output language follows the user. Keep English technical terms verbatim — never
transliterate `useMemo`, `invalidateQueries`, or `RunRecord`, whatever language the
prose is in.

## Mental model

```text
Why    — intent          ← PR title, description, ticket
Where  — the city map    ← file-to-file map, blast radius
How    — the current     ← function-to-function call chain
What   — the contract    ← I/O contracts + invariants + edge cases
Defend — the grilling    ← simulated questions with model answers
```

Each phase feeds the next. Skipping ahead is the failure mode this skill exists to
prevent: reading a diff without knowing where those files sit produces a review that
catches typos and misses the architectural break.

## Three rules that survive every phase

1. **Map before diff.** Never read changed lines before you know which layer the file
   lives in and who calls it. A diff read out of context reads as plausible even when it
   violates a layering rule — the rule is invisible from inside the hunk.
2. **Every changed line answers "which invariant does this preserve?"** Syntax-correct
   code that quietly breaks a uniqueness guarantee or leaks a cache entry is the bug
   class that survives normal review and dies in defense.
3. **Cut the noise.** Only trace paths the PR actually touches. A complete map of an
   untouched subsystem costs attention and buys nothing.

---

## Gathering the material

Phases 1–3 are structural questions — which files, which callers, which call chain. A
code graph answers those in one call each; git and grep answer them in twenty. Take the
fast path when it exists, and fall back cleanly when it does not.

### Step 0 — is a graph available?

Check whether `code-review-graph` MCP tools are in your tool list.

**Available** → take the graph fast path below.

**Not available** → tell the user, once, and let them choose. Do not install anything on
your own; an MCP server is a process that reads their whole repo, and that is their call
to make:

> ไม่มี `code-review-graph` MCP บนเครื่องนี้ ถ้าติดตั้งจะได้ blast radius, call chain
> และ test gaps จาก graph จริงแทนการ grep เดาเอา (Phase 1–3 เร็วและแม่นขึ้น
> Phase 4–5 เหมือนเดิม)
>
> ติดตั้ง (ไม่ต้องลง global, `uvx` ดึงให้ตอนรัน):
>
> ```jsonc
> // .mcp.json ที่ repo root
> {
>   "mcpServers": {
>     "code-review-graph": {
>       "type": "stdio",
>       "command": "uvx",
>       "args": ["code-review-graph", "serve"],
>       "cwd": "<absolute path to repo root>"
>     }
>   }
> }
> ```
>
> แล้ว restart session + สั่ง `code-review-graph build` หนึ่งครั้ง
>
> ไม่อยากลงก็ได้ — เดินต่อด้วย git + grep ได้เลย แค่ Phase 2 จะเป็นการอนุมานจาก
> import ไม่ใช่ edge จริง

Whichever they pick, **do not stall**. If they decline, or do not answer, run the manual
path and carry on — the answer at the end is what matters, not the tooling.

### Graph fast path

Always open with `get_minimal_context` — it costs about 100 tokens, returns a risk
score, and self-reports staleness so you never have to guess whether the graph still
describes this branch.

| Phase | Tool | What it replaces |
| --- | --- | --- |
| 0 | `get_minimal_context` | the guess about whether the graph is usable |
| 1 | `detect_changes` | `git diff --stat` plus per-function risk and **test gaps** |
| 2 | `get_impact_radius` | grepping every importer of every changed module |
| 3 | `get_affected_flows` | hand-tracing the call chain |

Rules that keep this cheap and honest:

- Pass `detail_level: "minimal"` first. A standard-mode flow runs about 980 tokens
  against 18 for minimal; zoom into one flow only once you know which flow matters.
- If `get_minimal_context` returns `status: not_ready`, or `head_matches_build` is
  false, the graph describes a different commit. Either run the build it suggests, or
  drop to the manual path — reporting edges from a stale graph is worse than reporting
  none, because they look authoritative.
- The graph is structural. It knows `A` calls `B`; it has no idea that unit ids must
  stay unique. Phases 4 and 5 are read-the-code work either way, and no graph output
  substitutes for them.
- `detect_changes` returns test gaps. Feed those straight into Phase 5 — "this function
  has no test, so how do you know it works" is the question that lands hardest, and it
  is the one you cannot find by reading the diff.

### Manual path

```bash
gh pr view <n> --json title,body,files          # intent, if it is a GitHub PR
git log --oneline <base>..HEAD                  # intent, if it is a local branch
git diff --stat <base>...HEAD                   # touched files, with add/delete counts
git diff <base>...HEAD -- <path>                # one file at a time, in phase 4
```

For Phase 2, grep for imports of each changed module to reconstruct callers. Say out
loud in the output that the blast radius is inferred from imports rather than measured
— a reader who thinks it is exhaustive will trust a gap that is not there.

When intent is missing (no PR body, terse commit messages), say so instead of inventing
it, then reconstruct intent from the diff and label it as inference.

---

## Phase 1 — PR Intent & Delta Triage

Goal: in three lines, what was broken and what shape of fix this is.

```markdown
### [Phase 1] PR Intent
- **Issue/Problem:** <the pain, or the feature that did not exist>
- **Solution Strategy:** <the approach taken, in one clause>
- **Touched Files:**
  - Added: `path/to/new_file.ts`
  - Modified: `path/to/existing.tsx`
  - Deleted: `path/to/old.ts`
```

A strategy line naming *what* changed ("added a component") is wasted; it must name the
*approach* ("moved unit-id assignment out of render into a mutation so the row owns its
own pending state").

## Phase 2 — Macro Anchor (file to file)

Goal: pin the changed files onto the existing architecture and see the blast radius.

Draw the tree with the *unchanged* neighbours included — that is what makes it a map
rather than a re-listing of the diff. Mark the changed nodes.

```text
[Zone: Data & State]
├── src/api/types.ts                       (unchanged — the contract)
│     └──> [M] src/components/PendingUnitGroup.tsx
│            └──> [A] src/components/PendingUnitRow.tsx
```

Then answer the handoff checklist explicitly:

- Who hands work *to* the changed files?
- Where do their results go next?
- Does any changed file now import across a layer boundary the project forbids?

## Phase 3 — Dynamic Flow (function to function)

Goal: one trace you can run in your head, from trigger to settled state, through the
changed functions only.

```text
[Trigger: user clicks "Set Unit ID"]
  │
  ▼
<PendingUnitRow />: onSubmit()          [new]
  │
  ▼
<Library />: commitSetUnitId()          [modified]
  │
  ▼
api.setUnitId() ──► backend REST API
  │
  ▼ (on success)
queryClient.invalidateQueries() ──► refetch listLibrary()
```

Include the failure branch when one exists. A trace showing only the happy path is
exactly the trace that loses Phase 5.

## Phase 4 — Contracts & Invariants Deep Dive

Now, and only now, read the changed lines. Per changed or new function:

**I/O contract**
- Parameters and their types; what a caller must guarantee before calling.
- Return value — and whether the real product is the return value, a state mutation, or
  a side effect. Name which.

**Invariants**
- Which system rule must still hold after this runs? (unit ids stay unique; the cache
  never serves a deleted run; the state machine never sits outside its declared states)
- Point at the line that enforces it. An invariant nothing enforces is a bug you just
  found, not an invariant.

**Edge cases**
- Network fails mid-call; value is `undefined`/`None`; user double-clicks (race);
  empty list; concurrent writers. For each: what the code actually does — not what it
  ought to do.

**The "why" decision**
- For each non-obvious choice, the alternative the author rejected and the cost that
  made them reject it. `useMemo` over `useEffect`, factory over singleton, a new file
  over extending the old one. If you cannot reconstruct the reason, mark it as an open
  question for the author — that is a finding, not a gap in your notes.

## Phase 5 — Technical Defense Simulation

Put on the senior architect's hat and ask the questions that actually get asked. Three
to four, each aimed at a real soft spot found in phases 2–4 — a generic question list
teaches nothing.

Cover these angles:

1. **Architectural why** — "why a new file instead of extending the existing one?"
2. **Edge case / reliability** — "what happens if the request fails after the optimistic
   update?"
3. **Performance / leak** — "does this re-render on every keystroke? does the listener
   get cleaned up?"
4. **Coverage** — aimed at a real test gap, from `detect_changes` when you have it or
   from the test tree when you do not.
5. **The uncomfortable one** — the question you would least want asked. Ask it anyway.

Each question gets a model answer in this shape:

```markdown
**Q:** <question phrased the way a reviewer would phrase it>
**A:** <one-sentence direct answer>
   - **Why:** <the reasoning, or the alternative rejected>
   - **Evidence:** `path/to/file.ts:42` <the line that proves it>
   - **Honest limit:** <where the answer runs out, if it does>
```

The honest-limit line matters more than it looks. "We do not handle concurrent writers
yet; single-operator deployment makes that acceptable and it is tracked" defends better
than a confident answer a follow-up question dismantles.

## Output

One markdown document, the five phases in order, headings as shown above. Default to
writing it in chat. Save to a file only when the user asks, or when the review is big
enough that they will want it again — then `playground/review/<branch-or-pr>.md`, or
wherever that repo already keeps review artifacts.

Keep phases 1–3 compact; they are orientation. Weight goes to phases 4 and 5, where
defense is actually won.

## When a phase is empty

Say so in one line and move on. A PR touching one pure utility function has no
interesting call chain — inventing one to fill the template trains the reader to skim
the sections that do matter.
