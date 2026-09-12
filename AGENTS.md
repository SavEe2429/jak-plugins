# Hybrid Code Review & Technical Defense

Read this when the user has to **explain or defend** a code change to someone else — a
reviewer, a tech lead, an examiner — or when they need to understand an unfamiliar diff
fast. Openings that mean this: "ต้องดีเฟนด์ PR นี้", "อธิบาย PR นี้ให้หน่อย",
"เตรียมตอบคำถามอาจารย์", "prep me to defend this branch", "what will they ask about
this PR".

It is not an approve/reject review.

**The method lives in `skills/hybrid-code-review/SKILL.md` next to this file. Read it
before starting and follow it in order.** This file only says when to reach for it.

Reviewing a diff to approve it and reviewing a diff to defend it are different jobs.
Approval asks "is this correct?". Defense asks "can I answer any question about this in
a room full of people who did not write it?" — five passes: intent, architecture map,
call chain, contracts and invariants, then the grilling with model answers.

Do not read the diff until you have mapped where the changed files sit. A diff read out
of context looks plausible even when it breaks a layering rule.
