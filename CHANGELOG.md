# Changelog

All notable changes to `jak-plugins` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-11-10

### Added

- Multi-host skill bundle supporting Claude Code (`.claude-plugin/`), OpenAI Codex CLI (`AGENTS.md`, `prompts/`), Antigravity (`plugin.json`), and Gemini CLI (`gemini-extension.json`, `GEMINI.md`, `commands/`).
- Bundled `project-scaffolder` (`v3.15.0`) with generic multi-job DAG CI templates, SSOT toolchain pins, dynamic LTS/Latest Stable policy, YAML Issue Forms guidance, and frozen binary path separation standards.
- Bundled `skill-factory` (`v4.14.0`) for capability discovery, evaluation, selection, and composition.
- GitHub Issue Forms (`.github/ISSUE_TEMPLATE/bug_report.yml`, `feature_request.yml`, `config.yml`) and structured PR template (`.github/pull_request_template.md`).
- Multi-job CI quality gate (`.github/workflows/ci.yml`) with manifest validation, Python CLI smoke tests, bundle packaging checks, and dual-audience summary gate.
- Automated SemVer release pipeline (`.github/workflows/release.yml`, composite SemVer parser action, manifest version sync, `CHANGELOG.md` promotion, and SHA-256 checksum generation).
- Repository hygiene, MIT license (`LICENSE`), security disclosure policy (`SECURITY.md`), `.gitignore`, `.gitattributes`, and `docs/release-notes/`.
