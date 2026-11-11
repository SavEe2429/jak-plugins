# Evidence-Based Verification Matrix

A senior engineering skill must never report a passing status based on file existence alone. Static file presence only proves that a file was _generated_; it does not prove that the system is _operational_.

---

## 1. The 4 Lifecycle Stages of Scaffolding

Every scaffolding item progresses through four distinct stages:

```text
[1. GENERATED] ──► [2. CONFIGURED] ──► [3. EXECUTED] ──► [4. VERIFIED]
(File written)     (Wired/Referenced)  (Command run)    (Exit 0 + Assertions pass)
```

1. **Generated:** The file or directory has been written to disk.
2. **Configured:** The file is wired into project settings, build scripts, or VCS configs.
3. **Executed:** The relevant compiler, linter, or test runner has been invoked.
4. **Verified:** The execution completed with exit code 0 and all output criteria were satisfied.

---

## 2. The 4 Audit Statuses

| Status                 | Meaning                                                                 | Required Evidence                                                                              |
| ---------------------- | ----------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| **`[PASS]`**           | Requirement is completely satisfied and verified.                       | Command line invoked, exit code `0`, and tangible verification output (e.g. test count > 0).   |
| **`[FAIL]`**           | Requirement was attempted but failed verification.                      | Command line invoked with non-zero exit code, compiler errors, or missing mandatory files.     |
| **`[NOT VERIFIED]`**   | Prerequisite files exist, but the execution environment is unavailable. | E.g. Unity License not activated, Python virtualenv not installed, or test runner not run yet. |
| **`[NOT APPLICABLE]`** | Requirement is irrelevant to this specific stack/domain.                | E.g. Unity Asset Pipeline is N/A for a Rust CLI tool. Does not penalize overall score.         |

---

## 3. Verification Criteria per Category

| Category                    | Verification Method                                                                                    | Pass Evidence                                                                                                                                                                                                    |
| --------------------------- | ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **07. Smoke Tests**         | Execute the actual test runner (`dotnet test`, `pytest`, `cargo test`, `Unity -runTests`).             | Exit code `0` and at least 1 real assertion passed.                                                                                                                                                              |
| **05. Modular Boundaries**  | Verify package layout (`src/<package_name>/`), clean root (no root entrypoints), and layer separation. | Clean root, encapsulated entry points, and valid layer dependencies.                                                                                                                                             |
| **10. Pre-commit Hooks**    | Execute `pre-commit run --all-files` (or invoke hook runner).                                          | Exit code `0` across all configured hooks.                                                                                                                                                                       |
| **12. CI Parity**           | Verify CI workflow executes the exact same commands as local hooks.                                    | Matching scripts and tool versions in `.github/workflows/ci.yml`.                                                                                                                                                |
| **13. Build Pipeline**      | Run build/compilation command or binary packaging script (`packaging/build.py`).                       | Exit code `0` and compilation/binary artifact in `out/<package_name>/`.                                                                                                                                          |
| **19. Security Hygiene**    | Run git tracking audit: verify `.env` and secrets are not tracked in git index.                        | `git ls-files` contains zero secret patterns.                                                                                                                                                                    |
| **15. Operational Logbook** | Confirm the log has entries and inspect evidence that prior entries cannot be overwritten or deleted.  | A non-empty `logbook/current.md` alone is only presence/content evidence; without an enforced append-only mechanism and preservation evidence, status must remain NOT VERIFIED. An empty or missing log is FAIL. |
| **20. Markdown Standards**  | Regex scan for Unicode emojis and verify all checklist items use `- [ ]`.                              | Zero emojis found and 100% of checklists formatted as `- [ ]`.                                                                                                                                                   |
