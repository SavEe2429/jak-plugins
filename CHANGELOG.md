# Changelog

All notable changes to `jak-plugins` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Two-level installation scope selection (`--scope project|workspace|user|global`) in `skill-factory` (`v4.15.0`) across `SKILL.md`, `agent_adapter.py`, `scaffold_skill.py`, and `skill_fetcher.py`, allowing users to choose between Project-level (`.agents/skills/`, `.claude/skills/`, etc.) and User-level (`~/.gemini/skills/`, `~/.agents/skills/`, `~/.claude/skills/`, etc.) skill loading/installation.

### Changed

- Bumped bundled `skill-factory` skill from `v4.14.0` to `v4.15.0`.

## [1.1.0] - 2026-11-11

### Added

- Official Actions Only and Zero Third-Party Actions Policy in CI/CD workflows and repository governance (`SKILL.md`, `references/repository-governance.md`).
- Mandatory version bumping rule (requiring version increments across all changes, even for 1-line modifications) documented in `.agents/skills-dev/README.md`.
- Gitleaks capability provider (`providers/standards/gitleaks.json`) defining `.gitleaks.toml` configuration, pre-commit hook, and CI workflow standards.
- Gitleaks binary allowlist support and subcommand validation (`detect`, `protect`, `version`) in `scripts/core/safe_executor.py`.
- Concrete `.gitleaks.toml`, Pre-commit hook, and GitHub Actions workflow templates in `project-scaffolder/references/enterprise-standards.md`.
- Architecture Reference pattern for AI Agent and Model Context Protocol (MCP) services in `project-scaffolder/references/architecture-catalog.md` (covering Stdio transport purity, graceful shutdown lifecycles, path confinement guards, deterministic Pydantic/Zod schemas, and canonical server layouts).
- Multi-purpose binary subcommand inspection in `scripts/core/safe_executor.py` blocking arbitrary code execution or mutable operations via `git` (`push`, `clone`, `-c`, `-C`), `npm`/`pnpm`/`yarn` (`exec`, `publish`), `cargo` (`install`, `publish`), and `make` (`-e`, `--eval`).
- Regression and unit tests for command security, working directory boundary enforcement, and dangerous subcommand rejection.

### Changed

- Bumped bundled `project-scaffolder` skill from `v3.15.0` to `v3.16.1`.
- Replaced third-party `softprops/action-gh-release@v3` in `.github/workflows/release.yml` with native official GitHub CLI (`gh release create`).
- Hardened `scripts/core/safe_executor.py` working directory confinement using canonical `os.path.realpath` resolution, blocking unconfined parent path traversals (`..`), symlink escapes, and Windows junction redirects.
- Updated `execute_safe_command` and `execute_safe_tokens` to require explicit `authorized_root` scopes without falling back to self-authorizing untrusted `cwd`.
- Normalized whitespace assertions in capability contract tests (`test_capability_contracts.py`) to prevent false-negative test failures caused by automated Markdown prose wrapping.

### Security

- Enforced strict project root confinement and deny-by-default subcommand checks for multi-purpose development binaries in Tier-1 Restricted Executor (`safe_executor.py`).

## [1.0.0] - 2026-11-11

### Added

- Specialized Issue Form (`.github/ISSUE_TEMPLATE/skill_gap.yml`) for reporting AI agent guidance drift, prompt gaps, and ecosystem mismatches.
- Markdown Reference Link validation script (`.github/scripts/validate_reference_links.py`) integrated into CI `code-quality` and pre-commit hooks.
- Hermetic Claude Code Plugin validation and installation smoke test job (`plugin-validation`) in `.github/workflows/ci.yml`.
- Automated default branch merge and ephemeral release branch deletion in `.github/workflows/release.yml`.
- Standardized AI Skill & Plugin Repository Archetype guidelines in `project-scaffolder/references/repository-governance.md`.
- Cryptographic artifact attestation (SLSA / Sigstore) and advanced supply-chain security guidelines in `project-scaffolder/references/enterprise-standards.md`.

### Changed

- Renamed `.github/scripts/release/release_ops.py` to `.github/scripts/release_manager.py` and consolidated all release operations into direct Python invocations.
- Standardized all repository governance actions, templates, and scripts on snake_case (`_`).
- Delineated boundaries in `.github/ISSUE_TEMPLATE/bug_report.yml` and `skill_gap.yml` to eliminate user confusion between code crashes and prompt guidance issues.
- Added description field to `.claude-plugin/marketplace.json` to satisfy Claude Plugin validator guidelines.

### Removed

- Redundant shell script wrappers in `.github/scripts/release/` (`build_github_release_body.sh`, `generate_release_notes_file.sh`, `get_previous_tag.sh`, `update_changelog_file.sh`, `update_release_notes_index.sh`).

## [1.0.0] - 2026-11-10

### Added

- Multi-host skill bundle supporting Claude Code (`.claude-plugin/`), OpenAI Codex CLI (`AGENTS.md`, `prompts/`), Antigravity (`plugin.json`), and Gemini CLI (`gemini-extension.json`, `GEMINI.md`, `commands/`).
- Bundled `project-scaffolder` (`v3.15.0`) with generic multi-job DAG CI templates, SSOT toolchain pins, dynamic LTS/Latest Stable policy, YAML Issue Forms guidance, and frozen binary path separation standards.
- Bundled `skill-factory` (`v4.14.0`) for capability discovery, evaluation, selection, and composition.
- GitHub Issue Forms (`.github/ISSUE_TEMPLATE/bug_report.yml`, `feature_request.yml`, `config.yml`) and structured PR template (`.github/pull_request_template.md`).
- Multi-job CI quality gate (`.github/workflows/ci.yml`) with manifest validation, Python CLI smoke tests, bundle packaging checks, and dual-audience summary gate.
- Automated SemVer release pipeline (`.github/workflows/release.yml`, composite SemVer parser action, manifest version sync, `CHANGELOG.md` promotion, and SHA-256 checksum generation).
- Repository hygiene, MIT license (`LICENSE`), security disclosure policy (`SECURITY.md`), `.gitignore`, `.gitattributes`, and `docs/release-notes/`.
