# Hybrid Code Review & Technical Defense

This extension carries one method: a five-pass read of a PR or diff that ends in a
simulated technical-defense grilling.

Use it when the user has to **explain or defend** a change to someone else — a reviewer,
a lead, an examiner — or when they need to understand an unfamiliar diff fast. Typical
openings: "ต้องดีเฟนด์ PR นี้", "อธิบาย PR นี้ให้หน่อย", "เตรียมตอบคำถามอาจารย์",
"prep me to defend this branch", "what will they ask about this PR".

It is not an approve/reject review and it does not produce diagrams as files.

**The method lives in `skills/hybrid-code-review/SKILL.md` inside this extension
directory. Read that file before starting, and follow it in order.** It is the single
source of truth; this file only says when to reach for it.

The one rule worth repeating here, because it is the one most easily skipped: do not
read the diff until you have mapped where the changed files sit in the architecture. A
diff read out of context looks plausible even when it breaks a layering rule.
