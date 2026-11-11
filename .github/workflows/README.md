# GitHub Actions Workflows

This directory defines automated Continuous Integration and Release pipelines for `jak-plugins`.

## Workflow Catalog

| Workflow File | Trigger Events                             | Permissions       | Purpose                                                                                                                                                                                                   |
| :------------ | :----------------------------------------- | :---------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ci.yml`      | `push` / `pull_request` (`main`)           | `contents: read`  | Validates JSON manifests, Python script compilation, LF hygiene, CLI smoke tests, bundle archive packaging, and enforces the `CI Summary & Gate` status check.                                            |
| `release.yml` | `push` (`release/v*`), `workflow_dispatch` | `contents: write` | Parses SemVer, synchronizes all 3 plugin manifests, promotes `CHANGELOG.md`, generates `docs/release-notes/vX.Y.Z.md`, builds `.zip` + `SHA256SUMS.txt`, tags `vX.Y.Z`, and publishes the GitHub Release. |

## Secrets Reference

| Secret         | Used By       | Scope                       | Notes                                                                            |
| :------------- | :------------ | :-------------------------- | :------------------------------------------------------------------------------- |
| `GITHUB_TOKEN` | `release.yml` | Automatic repo-scoped token | Used to push release metadata commits, create tags, and publish GitHub Releases. |

## Recommended Branch Protection (`main`)

- Require pull requests before merging.
- Require the **`CI Summary & Gate`** status check (`summary` job) to pass before merge.

## Local Verification Commands

```bash
python3 .github/scripts/release/release_ops.py check-manifests
python3 -B skills/project-scaffolder/scripts/scaffold.py --help
python3 .github/scripts/release/release_ops.py build-archive 1.0.0 --out-dir dist
```
