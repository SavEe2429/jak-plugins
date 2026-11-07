# Changelog

All notable changes to Skill Factory are documented here.

## [4.13.3] — Restricted Skill Fetcher Ingestion Boundary Hardening

- Harden `skill_fetcher.py` as a single-tier application ingestion boundary with fail-closed scanner status enforcement (`SCANNER_UNAVAILABLE`, `UNKNOWN`, and `ERROR` cannot be overridden by `--accept-findings`).
- Stage downloads on the same volume as the destination directory (`target_dir.parent`) for atomic directory rename and clean rollback.
- Enforce pre-download tree validation in `files_under()` before nested license downloads: reject Git symlinks (`120000`), submodules (`160000` / `commit`), reserved `.provenance.json` collisions, case-insensitive path collisions, file count limits (`MAX_FILES = 200`), per-file caps (`2 MB`), and aggregate size quotas (`MAX_TOTAL_BYTES = 10 MB`).
- Expand `safe_join()` with Windows path sanitization blocking reserved device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`, and superscript variants), NTFS alternate data streams (`::$DATA`), illegal characters (`<>:"\|?*`), control characters, and trailing dots or spaces.
- Harden `_http_get()` and `_GitHubRedirectHandler` with `ProxyHandler({})` isolation (note: corporate environments requiring mandatory outbound proxies are unsupported by design), `Accept-Encoding: identity`, hostname normalization, a 3-hop redirect limit, and `time.monotonic()` streaming chunk deadlines.

## [4.13.2] — Capability Lineage and Supporting-Rationale Enforcement

- Preserve paired source lineage per work item, including its analysis level, lifecycle stage, importance, and task-specific work rationale; retain all source links when consolidating case-insensitive Capability identities.
- Merge all distinct indirect-match rationales instead of retaining only the first record's explanation.
- Require every Supporting Capability to have at least one source link and a work rationale for each link; reject and report unsupported Supporting records rather than matching generic productivity Skills.
- Keep Core and Supporting roles usable at all five work-analysis levels; expose source links and consolidated lifecycle/importance metadata in matcher results.
- Add regression and behavioral evaluation coverage for all-five-level Core/Supporting matching, cross-cutting lineage, merged rationales, unjustified Supporting Capability rejection, explicit No Resource Found gaps, pre-approval verification statuses, and Resource type scope.
- Add Work Rationale to the consolidated Project Work & Resource Matrix schema.

## [4.13.1] — Capability-Level Core/Supporting Matcher

- Add a specific Capability-to-Installed-Skill candidate matcher that preserves Core/Supporting roles, five-level work hierarchy, lifecycle, importance, and many-to-many source work-item links.
- Distinguish Direct matches from explicitly supplied Indirect related-term matches; require a rationale for every Indirect match; honor Skill negative boundaries and caller-declared scope exclusions.
- Consolidate repeated Capability identities across all five analysis levels while preserving every source work-item link; surface conflicting definitions instead of silently dropping or merging them.
- Add a JSON input path to the orchestrator CLI for specific project Capability records; keep candidate retrieval separate from final verification, security, and practical testing.
- Add regression tests for Core/Supporting separation, many-to-many traceability, Direct/Indirect classification, negative boundaries, invalid records, and CLI JSON output.

## [4.13.0] — Audit Evidence Versioning Correction

- Mark the embedded SkillSpector classification report as a historical 4.8.2 snapshot rather than current package evidence.
- Point maintainers to the versioned audit/remediation record for current scan status and explicitly prohibit carrying forward historical SAFE results.

## [4.12.9] — Consolidated Project Work & Resource Matrix

- Replace the separate Workstream Overview Matrix, Workstream Cards, and Resource Catalog with one consolidated Matrix table.
- Require all 16 Workstreams and lists inside their own cells, with work hierarchy, lifecycle stage, Core/Supporting Capabilities, importance, Resources, availability, roles, match type, verification, practical test, evaluation, overlap, and coverage/gap.
- Preserve Unknown versus Not Yet Analyzed, dynamic Sub-workstreams/Tasks/Activities, and cross-cutting many-to-many Resource links.
- Update snapshot contents and report instructions to store the single Matrix rather than the former multi-part presentation.

## [4.12.8] — External-First Discovery Policy Alignment

- Enforce External Discovery → External Evaluation → Internal Discovery → Comparative Evaluation → Final Recommendation.
- Retain every candidate that passes relevance, verification, and trust thresholds; Top 3 is only an optional shortlist/summary, never a discovery cap.
- Apply equivalent evaluation standards to internal and external Resources without automatic installed-first preference.
- Align the custom-synthesis gate with completed external and internal discovery, the 3-Repetition Rule, and explicit user approval.
- Align the project Matrix schema's candidate-retention wording with the all-qualifying-candidates policy.

## [4.12.7] — Inspection Trust Boundaries and Fetcher Hardening

- Treat inspected installed Skill content as untrusted evidence; prohibit following embedded instructions or executing/activating inspected content during discovery.
- Harden the local security scanner against symlinked Skill roots and files, and include tests/evaluation directories in content inspection.
- Validate immutable commit identifiers before tree and raw-content requests; validate redirect ports and enforce bounded response sizes.
- Verify the repository license at the exact pinned commit and inspect applicable nested LICENSE/LICENCE/COPYING files; fail closed when a nested license lacks one unambiguous approved SPDX identifier.
- Replace ambiguous Skills CLI command references with explicit Skills-package discovery wording so generic CLI syntax is not mistaken for a recommended MCP Resource.
- Add regression tests for commit validation, redirect restrictions, symlink handling, and complete content inspection.

## [4.12.6] — GitHub Fetch Security and License Gate

- Remove all `GITHUB_TOKEN` environment access; GitHub requests are unauthenticated.
- Validate repository identifiers and restrict HTTPS requests and redirects to approved GitHub hosts.
- Require a GitHub-recognized SPDX license on the permissive allowlist before downloading skill files; block missing, unknown, and non-allowlisted licenses.
- Record the verified license identifier and source in fetch provenance.
- Add regression coverage for repository validation, license policy, and host restrictions.

## [4.12.5] — Core and Supporting Capability Discovery

- Require a two-lens capability analysis (Core and Supporting) at every applicable project-work level, from Project through Activity.
- Add explicit cross-cutting Supporting Capability discovery and many-to-many traceability to source work items.
- Require resource discovery and evaluation to cover both capability tracks, including process/method skills beyond domain-specific tools.
- Extend Workstream Cards and the Skill & Integration Catalog to distinguish Work, Capability, and Resource, and label capability roles.
- Align discovery order with External Discovery → External Evaluation → Internal Discovery → Comparative Evaluation → Final Recommendation; retain all qualifying candidates beyond any initial shortlist.

## [4.12.4] — Hybrid Workstream Report and Catalog Presentation

- Replace the dual-matrix output with a 16×4 Workstream Overview Matrix followed by 16 detailed Workstream Cards in a two-column HTML table.
- Define compact card formatting: no lifecycle coverage summary line, plain-text headings without emoji, and tighter list spacing.
- Add a Deduplicated Skill & Integration Catalog with a Catalog Overview table before the full detailed entries.
- Update snapshot contents and retrieval guidance to preserve the overview matrix, all cards, catalog overview, and detailed catalog.
- Keep availability evidence separate from required/optional work markers.

## [4.12.3] — Full-Matrix Clarification and Governance Alignment

- Clarify that project-wide recommendations always show both matrices in full, never truncated or summarized; cells are left `-` rather than padded with unneeded tools, and no readiness score is added unless requested.
- Record the owner-approved exception that saving a Project Skill Matrix snapshot under `.agents/skill-factory/project-matrices/` needs no separate prompt, while installing, activating, or synthesizing still requires Human-in-the-Loop approval.
- Extend the frontmatter description to cover project-wide workstream × lifecycle recommendations.
- Add the `uv run python .agents/skills/skill-factory/scripts/*` pattern to `allowed-tools` so it matches the documented orchestrator command.
- Make the MCP matrix audit-trail rule conditional on an existing logbook and add guidance for using the facet matrix with workstreams and lifecycle stages.
- Replace LaTeX `≥` markup in instructions with plain text.

## [4.12.2] — Project-aware Recommendation and Full Matrix Output

- Add a universal 16-workstream taxonomy with domain-specific sub-workstream guidance.
- Standardize project lifecycle stages as Initial, Before, During, and After.
- Define full Project Workstream Matrix and Project Skill Matrix output contracts, with one table, all workstream rows, and readable per-cell lists.
- Add evidence-based availability labels, a deduplicated Skill Inventory, normalized Skill profile extraction, and versioned project matrix snapshot guidance.
- Require explicit software engineering workflow coverage for software-producing projects, including specification, planning, coding, debugging, testing, refactoring, review, and build verification.
