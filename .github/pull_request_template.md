## Summary

<!-- Describe what changed in skills, host adapters, scripts, or documentation. -->

Related Issue: #

## Change Classification

- [ ] `feat`: New skill, profile, provider, or adapter capability
- [ ] `fix`: Bug fix in skill instructions, helper scripts, or host manifests
- [ ] `docs`: Documentation, CHANGELOG, or governance updates
- [ ] `refactor`: Structural improvement without changing skill behavior
- [ ] `chore`: Maintenance, CI/release workflow, or metadata sync

## Contributor Checklist

- [ ] Edited `skills/<name>/` as the Single Source of Truth (kept host adapters thin).
- [ ] Verified JSON manifests (`plugin.json`, `gemini-extension.json`, `.claude-plugin/*.json`) are valid and version-synchronized if releasing.
- [ ] Verified helper Python scripts (`skills/*/scripts/`) compile and pass CLI smoke tests (`--help`).
- [ ] Preserved strict LF (`\n`) line endings and excluded `__pycache__/`, `.env`, or local build artifacts.
- [ ] Updated `CHANGELOG.md` under `## [Unreleased]` for user-visible changes.

## Reviewer Checklist

- [ ] Skill instructions and frontmatter remain clear, accurate, and non-duplicative.
- [ ] Host adapter files (`AGENTS.md`, `GEMINI.md`, `commands/*.toml`, `prompts/*.md`, `.claude-plugin/`) stay aligned with `skills/`.
- [ ] CI quality gate (`code-quality`, `test`, `package-check`, `summary`) passes cleanly.
