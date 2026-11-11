# Package Manager Consistency Checks

The default `--policy-audit` only inspects declarations and file metadata. It
never runs a resolver. `--check-package-lock` is an explicit operation because
some native consistency checks may contact registries, read local caches, or
resolve the dependency graph. It refuses to run when the provider's declared
manifest or lockfile is missing.

`--run-package-audit` is also opt-in. It checks provider-declared manifest and
lockfile inputs before execution; missing lockfiles block the command unless a
provider explicitly allows their absence. This prevents audit tools that can
create a lockfile from changing project files as a side effect.

Provider commands are selected from validated declarative metadata. The runner
uses the allowlisted command executor, withholds raw output, records the command,
exit code, tool version, and check time, and reports non-zero exits as
`review-required`. Non-zero can mean lock drift, missing cached data, network
failure, or another tool error; it is never automatically labeled a lockfile
failure. Unsupported managers return `not-applicable`/`NOT VERIFIED`.

## Initial provider checks

| Provider   | Command shape                                                               | Network policy     | Scope                                                                                                                                                                                     |
| ---------- | --------------------------------------------------------------------------- | ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| uv         | `uv lock --check`                                                           | May access network | Confirms lock state against project metadata without writing the lockfile.                                                                                                                |
| pnpm       | `pnpm install --lockfile-only --frozen-lockfile --offline --ignore-scripts` | Offline required   | Validates using local store metadata; frozen mode blocks lockfile updates and lockfile-only avoids `node_modules`.                                                                        |
| Cargo      | `cargo metadata --format-version 1 --locked --offline`                      | Offline required   | Resolves machine-readable metadata while forbidding lock changes and network access.                                                                                                      |
| Go Modules | `go mod tidy -diff`                                                         | May access network | Reports whether `go.mod`/`go.sum` need source-graph changes without writing those files. `go.sum` may be absent when there are no dependencies, so its absence does not block this check. |
| Unity UPM  | Not declared                                                                | Unsupported        | Static presence only; no native lock check is claimed.                                                                                                                                    |

Manifest generation is available for the five registered managers and requires
an explicit dependency specification plus plan confirmation. It writes only the
declared manifest; lockfiles must be produced using the selected manager's
documented workflow.

Bounded read-only inventory is available for `uv.lock`, `pnpm-lock.yaml` v9,
`Cargo.lock`, Go `go.sum`, and Unity UPM's `Packages/packages-lock.json`.
uv/Cargo/pnpm entries report names and versions without direct/transitive
classification; Unity UPM preserves declared depth. Go output is explicitly
checksum-record evidence rather than a complete resolved dependency graph.
Inventory does not classify security or license findings. `go.sum` is checksum
evidence, not a conventional resolved lockfile; the Go check therefore reports
the tidy consistency result only.

The registered audit parsers are provider-specific and bounded:

| Provider   | Output format                       | Parsed evidence                                                                               | Important limits                                                                           |
| ---------- | ----------------------------------- | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| uv         | Preview JSON                        | Audited package, vulnerability, and adverse-status counts                                     | Preview schema; no severity/license claim; current parser is count-only                    |
| pnpm       | `pnpm audit --json` report          | Advisory ID, affected package/version, severity, patched versions, and registry report counts | Results reflect the configured registry and its ignore/filter behavior; no license verdict |
| Cargo      | `cargo audit --json` RustSec report | Advisory ID, crate/version, severity, patched versions, and warning counts                    | Database follows cargo-audit configuration; no license verdict                             |
| Go Modules | govulncheck JSON message stream     | OSV ID/aliases, affected module/package, fixed versions, and call-trace evidence              | No severity/license field; repeated findings are deduplicated                              |
| Unity UPM  | None                                | Not applicable                                                                                | No provider-declared vulnerability audit command                                           |

An audit result separates command execution from parser status. Malformed,
truncated, inconsistent, and over-limit output is `not-verified`. A parsed zero
count is `no-findings-reported`, not a guarantee that the project is safe:
provider filters, registry coverage, database freshness, and tool limitations
may affect what was reported. The result includes the provider-declared network
policy. Raw output is withheld. Re-check schemas against the upstream sources
below when changing provider commands or parser behavior.

`--license-evidence <relative-path>` reads a user-selected CycloneDX JSON SBOM
inside the target project. It extracts each component's declared license,
package identity, selected package-origin references, JSON pointer, and the
SBOM's SHA-256. URL query/fragment values and credential-bearing URLs are
withheld. A missing declaration is `unknown`; multiple declarations are
preserved as published and are not treated as a conflict because they may
represent SPDX alternatives. The result records `decision: not-evaluated`:
SBOM content is a declaration from its generator, not independently verified
upstream evidence, and no license allow/deny policy is applied. Input is capped
at 5 MiB and 10,000 components. This does not replace an ecosystem-native
license scan or legal review. The current reader accepts CycloneDX JSON
specification versions 1.4 through 1.7 and validates the fields it consumes;
it is not a full CycloneDX schema validator.

## Maintainer references

- [uv project locking and checking](https://docs.astral.sh/uv/concepts/projects/sync/)
- [pnpm install options](https://pnpm.io/cli/install)
- [Cargo metadata command](https://doc.rust-lang.org/cargo/commands/cargo-metadata.html)
- [Go Modules Reference](https://go.dev/ref/mod)
- [uv CLI reference](https://docs.astral.sh/uv/reference/cli/)
- [uv upstream audit tests](https://github.com/astral-sh/uv/blob/main/crates/uv/tests/build/audit.rs)
- [pnpm audit command](https://pnpm.io/cli/audit)
- [pnpm audit report type](https://raw.githubusercontent.com/pnpm/pnpm/main/pnpm11/deps/compliance/audit/src/types.ts)
- [cargo-audit JSON presenter](https://docs.rs/cargo-audit/latest/src/cargo_audit/presenter.rs.html)
- [RustSec report structure](https://docs.rs/rustsec/latest/rustsec/report/struct.Report.html)
- [RustSec vulnerability structure](https://docs.rs/rustsec/latest/rustsec/vulnerability/struct.Vulnerability.html)
- [govulncheck command reference](https://pkg.go.dev/golang.org/x/vuln/cmd/govulncheck)
- [govulncheck JSON message types](https://pkg.go.dev/golang.org/x/vuln/internal/govulncheck)
- [CycloneDX JSON 1.7 reference: licenses and external references](https://cyclonedx.org/docs/1.7/json/)
