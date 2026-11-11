# Generation Safety, Idempotency & Conflict Management

A senior-grade scaffolder must be **safe by default**. Running the scaffolder against an existing repository must never silently overwrite or destroy user work.

---

## 1. Core Safety Principles

1. **Dry-Run Mode (`--dry-run`):** Always support previewing changes without touching disk.
2. **Conflict Detection:** Check if target files already exist before writing. If identical (same content hash), skip cleanly. If different, mark as a conflict.
3. **Backup Before Overwrite:** If overwriting existing files is explicitly approved by the user, backup the previous version to `.backup/<timestamp>/`.
4. **Preserve by Default:** Config merging is not implemented yet. Preserve all differing existing files and stop the entire generation run rather than silently replace or partially generate around a conflict.
5. **Idempotent Generation:** Identical generated files are skipped. Running again with the same inputs should produce zero file writes.
6. **Constrain Writes:** Validate every generated relative path and reject absolute paths or traversal outside the target. Write through a temporary file in the destination directory and atomically replace the target.

---

## 2. Decision Tree for Existing Files

```text
Target File Exists?
       │
       ├── No  ──► Write File (LF Line Endings)
       │
       └── Yes ──► Compare Hash
                     │
                     ├── Same Hash ──► Skip (Clean Idempotency)
                     │
                     └── Differs ────► Conflict Detected!
                                         │
                                         ├── In Dry-Run: Report [CONFLICT], write nothing
                                         │
                                         └── In Live Run:
                                               1. Preserve and abort unless explicit --force authorization is supplied
                                               2. With --force: Create backup in .backup/<timestamp>/ then atomically write

`--force` is an authorization flag, not a recommendation. The caller must first
show the dry-run/conflict report and obtain approval for the specific overwrite.
The CLI does not perform an interactive approval conversation.
```

---

## 3. Logbook Integrity Rules

- **Never Fabricate Execution History:** The logbook must record _what actually happened_ during the session, not aspirational text.
- **Append-Only Active Log:** Always append to the bottom of `logbook/current.md`.
- **Immutable Archives:** Rotated logs (`YYYY-MM-DD_logbook.md`) must be treated as read-only historical records. Never edit, truncate, or reorder archived logs.
