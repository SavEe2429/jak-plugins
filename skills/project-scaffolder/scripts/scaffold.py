#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = []
# ///
"""Context-aware CLI for declarative providers and legacy project profiles.

The capability route composes validated JSON providers through the shared safe
writer. Legacy stack profiles remain available during migration.
"""

import argparse
import json
import re
import sys
from dataclasses import asdict, replace
from pathlib import Path

# Add script folder to path for local imports
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from audit import main as audit_main
from contracts.models import ProjectContext, VerificationCheck
from core.capability_registry import CapabilityRegistry
from core.composition import apply_dependency_spec, apply_toolchain_versions, compose_plan
from core.engine import scaffold_composition_plan, scaffold_project
from core.license_evidence import inspect_license_evidence
from core.migration import build_migration_report
from core.policy_audit import (
    analyze_ci_parity,
    analyze_toolchain_ci_parity,
    audit_package_manager,
    audit_toolchains,
    run_package_audit,
    run_package_lock_check,
    scan_secret_indicators,
)
from core.registry import AdapterRegistry
from core.standards import resolve_standards
from core.verification import run_verification_checks
from discover import detect_3axis, discover_project_units
from verify import main as verify_main


def main():
    parser = argparse.ArgumentParser(
        description="Context-Aware Project Scaffolder (Capability Composition + Legacy Profiles)"
    )
    parser.add_argument("--target-dir", default=".", help="Target workspace directory")
    parser.add_argument("--name", default="", help="Project name")
    parser.add_argument(
        "--domain", help="Force domain (e.g. game, embedded, web, systems, ai_data, security)"
    )
    parser.add_argument(
        "--stack",
        help="Force tech stack (e.g. unity, godot, rust, nextjs, fastapi, go, platformio, esp_idf)",
    )
    parser.add_argument(
        "--topology",
        choices=["unknown", "monolith", "modular_monolith", "monorepo", "microservices"],
        help="Set topology when discovery is uncertain",
    )
    parser.add_argument("--architecture", help="Choose a profile-supported architecture layout")
    parser.add_argument(
        "--confirm-plan",
        action="store_true",
        help="Confirm the reviewed project/layout plan before writing",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview planned changes without writing to disk"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Explicitly authorize overwriting conflicting generated files (always backs them up)",
    )
    parser.add_argument("--audit", action="store_true", help="Run 20-category readiness audit")
    parser.add_argument(
        "--verify", action="store_true", help="Preview dynamic verification; execution requires --confirm-command-execution"
    )
    parser.add_argument(
        "--policy-audit",
        action="store_true",
        help="Read-only package manager, lockfile, CI parity, and secret indicator audit",
    )
    parser.add_argument(
        "--run-package-audit",
        action="store_true",
        help="Run the resolved manager's declared audit command (may access the network); raw output is withheld",
    )
    parser.add_argument(
        "--license-evidence",
        metavar="SBOM_PATH",
        help="Read license declarations and provenance from a local CycloneDX JSON SBOM inside the target project; does not judge compliance",
    )
    parser.add_argument(
        "--check-package-lock",
        action="store_true",
        help="Run the resolved manager's declared lock consistency check; network behavior is provider-declared",
    )
    parser.add_argument(
        "--discover-units",
        action="store_true",
        help="List nested project units supported by registered profile evidence",
    )
    parser.add_argument(
        "--migration-report",
        action="store_true",
        help="Report legacy profile template-bridge parity and remaining legacy-only capabilities",
    )
    parser.add_argument(
        "--provider",
        action="append",
        default=[],
        help="Select a declarative capability provider; may be repeated",
    )
    parser.add_argument(
        "--set-version",
        action="append",
        default=[],
        help="Set a user-chosen toolchain version as provider-id=version",
    )
    parser.add_argument(
        "--dependency-spec-json",
        help="Explicit dependency JSON object used only with a provider-declared manifest generator",
    )
    parser.add_argument(
        "--verify-provider",
        action="append",
        default=[],
        help="Preview declared checks for a provider; execution requires --confirm-command-execution",
    )
    parser.add_argument(
        "--omit-legacy-ci",
        action="store_true",
        help="Omit CI workflow contributions from legacy template providers",
    )
    parser.add_argument(
        "--confirm-command-execution",
        action="store_true",
        help="Confirm the displayed provider-declared command preview, including declared network and write effects",
    )

    args = parser.parse_args()
    target_path = Path(args.target_dir).resolve()
    if args.set_version and not args.provider:
        print("COMPOSITION BLOCKED: --set-version requires a selected --provider.")
        sys.exit(2)
    if args.dependency_spec_json and not args.provider:
        print(
            "COMPOSITION BLOCKED: --dependency-spec-json requires a selected package-manager --provider."
        )
        sys.exit(2)

    if args.policy_audit:
        capability_registry = CapabilityRegistry()
        capability_registry.load_directory(SKILL_ROOT / "providers")
        package_report = audit_package_manager(target_path, capability_registry)
        selected = capability_registry.get(package_report.get("provider", ""))
        toolchains = audit_toolchains(target_path, capability_registry)
        report = {
            "provider_catalog_errors": capability_registry.load_errors,
            "package_manager": package_report,
            "ci_parity": analyze_ci_parity(target_path, selected)
            if selected
            else {"status": "not-verified"},
            "toolchains": toolchains,
            "toolchain_ci_parity": analyze_toolchain_ci_parity(target_path, toolchains),
            "standards": resolve_standards(target_path, capability_registry),
            "secret_indicators": scan_secret_indicators(target_path),
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        return

    if args.run_package_audit:
        capability_registry = CapabilityRegistry()
        capability_registry.load_directory(SKILL_ROOT / "providers")
        package_report = audit_package_manager(target_path, capability_registry)
        provider = capability_registry.get(package_report.get("provider", ""))
        if provider is None:
            print(
                json.dumps(
                    {
                        "status": "not-verified",
                        "package_manager": package_report,
                        "message": "Resolve a single package manager before running its audit command.",
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            sys.exit(2)
        if not args.confirm_command_execution:
            print(json.dumps({
                "status": "NOT VERIFIED",
                "preview": provider.payload.get("audit", []),
                "network_policy": provider.payload.get("audit_network_policy", "not-declared"),
                "write_effects": provider.payload.get("audit_write_effects", []),
                "timeout_seconds": provider.payload.get("audit_timeout_seconds"),
                "output_limit": provider.payload.get("audit_output_limit"),
                "message": "Command execution requires a second explicit confirmation; no process was started. Re-run with --confirm-command-execution after reviewing this preview.",
            }, indent=2, sort_keys=True))
            sys.exit(2)
        report = run_package_audit(target_path, provider, confirmed=True)
        print(json.dumps(report, indent=2, sort_keys=True))
        if report["status"] == "not-verified":
            sys.exit(2)
        if report["status"] == "completed-nonzero":
            sys.exit(1)
        return

    if args.license_evidence:
        report = inspect_license_evidence(target_path, args.license_evidence)
        print(json.dumps(report, indent=2, sort_keys=True))
        if report["status"] != "parsed":
            sys.exit(2)
        return

    if args.check_package_lock:
        capability_registry = CapabilityRegistry()
        capability_registry.load_directory(SKILL_ROOT / "providers")
        package_report = audit_package_manager(target_path, capability_registry)
        provider = capability_registry.get(package_report.get("provider", ""))
        if provider is None:
            print(
                json.dumps(
                    {
                        "status": "not-verified",
                        "consistency": "not-verified",
                        "package_manager": package_report,
                        "message": "Resolve a single package manager before checking its lockfile.",
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            sys.exit(2)
        if not args.confirm_command_execution:
            lock_policy = provider.payload.get("lock_check", {})
            print(json.dumps({
                "status": "NOT VERIFIED",
                "preview": lock_policy.get("command", []),
                "network_policy": lock_policy.get("network_policy", "not-declared"),
                "write_effects": lock_policy.get("write_effects", []),
                "timeout_seconds": lock_policy.get("timeout_seconds"),
                "output_limit": lock_policy.get("output_limit"),
                "message": "Lock-check execution requires a second explicit confirmation; no process was started. Re-run with --confirm-command-execution after reviewing this preview.",
            }, indent=2, sort_keys=True))
            sys.exit(2)
        report = run_package_lock_check(target_path, provider, confirmed=True)
        print(json.dumps(report, indent=2, sort_keys=True))
        if report["status"] == "not-verified":
            sys.exit(2)
        if report["status"] in ("review-required", "not-run"):
            sys.exit(1)
        return

    if args.discover_units:
        registry = AdapterRegistry(profiles_dir=SKILL_ROOT / "profiles")
        report = {
            "root": str(target_path),
            **discover_project_units(target_path, registry),
            "profile_errors": registry.load_errors,
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        return

    if args.migration_report:
        registry = AdapterRegistry(profiles_dir=SKILL_ROOT / "profiles")
        report = build_migration_report(registry)
        report["profile_load_errors"] = registry.load_errors
        print(json.dumps(report, indent=2, sort_keys=True))
        return

    if args.verify_provider:
        capability_registry = CapabilityRegistry()
        capability_registry.load_directory(SKILL_ROOT / "providers")
        legacy_registry = AdapterRegistry(profiles_dir=SKILL_ROOT / "profiles")
        checks = []
        for provider_id in args.verify_provider:
            provider = capability_registry.get(provider_id)
            if provider is None and provider_id.startswith("legacy-profile."):
                profile_key = provider_id[len("legacy-profile.") :].split(".", 1)
                adapter = legacy_registry.get(*profile_key) if len(profile_key) == 2 else None
                if adapter is not None:
                    name = re.sub(
                        r"[^A-Za-z0-9_-]+", "_", args.name or target_path.name or "MyProject"
                    )[:64]
                    provider = adapter.to_template_provider(name, include_ci=False)
                    capability_registry.register_record(
                        {
                            "id": provider.id,
                            "kind": provider.kind,
                            "schema_version": provider.schema_version,
                            "capabilities": provider.capabilities,
                            "matches": provider.matches,
                            "payload": provider.payload,
                        },
                        provider.source,
                    )
                    provider = capability_registry.get(provider.id)
            if provider is None:
                print("Unknown verification provider: %s" % provider_id)
                sys.exit(2)
            declared_checks = provider.payload.get("checks", [])
            if not declared_checks:
                declared_checks = provider.payload.get("verification_checks", [])
            for item in declared_checks:
                checks.append(
                    VerificationCheck(
                        id=item["id"],
                        capability=provider.id,
                        command=item.get("command", []),
                        required=item.get("required", True),
                        expected_evidence=item.get("expected_evidence", {}),
                        execution_policy=item.get("execution_policy", {}),
                    )
                )
        if not checks:
            print(
                json.dumps(
                    {
                        "status": "NOT APPLICABLE",
                        "checks": [],
                        "message": "No executable check operations are declared by the selected providers.",
                    },
                    indent=2,
                )
            )
            return
        results = run_verification_checks(
            checks, target_path, confirmed=args.confirm_command_execution
        )
        report = {
            "status": "PASS"
            if all(
                not item.required or item.status in ("PASS", "NOT APPLICABLE") for item in results
            )
            and all(item.status != "FAIL" for item in results)
            else "INCOMPLETE",
            "checks": [asdict(item) for item in results],
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        if report["status"] != "PASS":
            sys.exit(2 if any(item.status == "NOT VERIFIED" for item in results) else 1)
        return

    if args.provider:
        capability_registry = CapabilityRegistry()
        capability_registry.load_directory(SKILL_ROOT / "providers")
        legacy_registry = AdapterRegistry(profiles_dir=SKILL_ROOT / "profiles")
        raw_name = args.name or target_path.name or "MyProject"
        project_name = re.sub(r"[^A-Za-z0-9_-]+", "_", raw_name).strip("_-") or "MyProject"
        if not project_name[0].isalpha() and project_name[0] != "_":
            project_name = "_" + project_name
        project_name = project_name[:64]
        providers = []
        legacy_runbook_sources = []
        for provider_id in args.provider:
            provider = capability_registry.get(provider_id)
            if provider is None and provider_id.startswith("legacy-profile."):
                profile_key = provider_id[len("legacy-profile.") :].split(".", 1)
                adapter = legacy_registry.get(*profile_key) if len(profile_key) == 2 else None
                if adapter is not None:
                    architectures = adapter.get_architecture_options()
                    if architectures and not args.architecture:
                        print(
                            "ARCHITECTURE DECISION REQUIRED: select one of: %s"
                            % ", ".join(architectures)
                        )
                        sys.exit(2)
                    if args.architecture and args.architecture not in architectures:
                        print(
                            "Unsupported architecture '%s' for profile '%s'"
                            % (args.architecture, adapter.stack_id)
                        )
                        sys.exit(2)
                    provider = adapter.to_template_provider(
                        project_name,
                        args.topology or "unknown",
                        args.architecture,
                        include_ci=not args.omit_legacy_ci,
                        include_runbook=False,
                    )
                    capability_registry.register_record(
                        {
                            "id": provider.id,
                            "kind": provider.kind,
                            "schema_version": provider.schema_version,
                            "capabilities": provider.capabilities,
                            "matches": provider.matches,
                            "payload": provider.payload,
                        },
                        provider.source,
                    )
                    provider = capability_registry.get(provider.id)
                    legacy_runbook_sources.append((len(providers), adapter))
            if provider is None:
                print("Unknown capability provider: %s" % provider_id)
                sys.exit(2)
            providers.append(provider)
        selected_files = [
            item for provider in providers for item in provider.payload.get("files", [])
        ]
        has_logbook = any(item.get("path") == "logbook/README.md" for item in selected_files)
        has_runbook = any(item.get("path") == "AGENTS.md" for item in selected_files)
        if has_logbook and not has_runbook and legacy_runbook_sources:
            source_index, source_adapter = legacy_runbook_sources[0]
            runbook = next(
                (
                    item
                    for item in source_adapter.get_supporting_files(
                        args.topology or "unknown", args.architecture, include_runbook=True
                    )
                    if item.rel_path == "AGENTS.md"
                ),
                None,
            )
            if runbook is not None:
                payload = dict(providers[source_index].payload)
                files = list(payload.get("files", []))
                files.append(
                    {
                        "path": runbook.rel_path,
                        "content": runbook.content,
                        "description": runbook.description,
                    }
                )
                payload["files"] = files
                providers[source_index] = replace(providers[source_index], payload=payload)
        try:
            providers = apply_toolchain_versions(providers, args.set_version)
            if args.dependency_spec_json:
                providers = apply_dependency_spec(providers, json.loads(args.dependency_spec_json))
        except ValueError as exc:
            print("COMPOSITION BLOCKED: %s" % exc)
            sys.exit(2)
        except json.JSONDecodeError as exc:
            print("COMPOSITION BLOCKED: --dependency-spec-json is not valid JSON: %s" % exc.msg)
            sys.exit(2)
        context = ProjectContext(root=target_path, purpose="explicit provider composition")
        plan = compose_plan(context, providers, registry=capability_registry)
        if plan.conflicts:
            print("COMPOSITION BLOCKED: " + "; ".join(plan.conflicts))
            sys.exit(2)
        if not args.dry_run and not args.confirm_plan:
            print(
                "PLAN CONFIRMATION REQUIRED: preview with --dry-run, then rerun with --confirm-plan."
            )
            sys.exit(2)
        result = scaffold_composition_plan(
            target_path, plan, dry_run=args.dry_run, force=args.force, project_name=project_name
        )
        print(
            json.dumps(
                {
                    "plan": {
                        "providers": plan.selected_provider_ids,
                        "directories": [item.rel_path for item in plan.directories],
                        "files": [item.rel_path for item in plan.files],
                        "file_details": [
                            {"path": item.rel_path, "description": item.description}
                            for item in plan.files
                        ],
                        "verification_checks": [item.id for item in plan.verification_checks],
                        "unresolved": plan.unresolved,
                        "conflicts": plan.conflicts,
                    },
                    "result": result,
                },
                indent=2,
                sort_keys=True,
            )
        )
        if result["blocked"]:
            sys.exit(2)
        return

    # Route: Audit
    if args.audit:
        sys.argv = [sys.argv[0], str(target_path)]
        audit_main()
        return

    # Route: Verify
    if args.verify:
        if not args.confirm_command_execution:
            registry = AdapterRegistry(profiles_dir=SKILL_ROOT / "profiles")
            domain, stack, topology, adapter = detect_3axis(target_path, registry=registry)
            if adapter.stack_id == "generic":
                preview = {"status": "NOT VERIFIED", "message": "VERIFICATION NOT RUN: no unambiguous profile; no commands can be previewed or executed."}
            else:
                preview = {
                    "status": "CONFIRMATION REQUIRED",
                    "target": str(target_path),
                    "provider": "legacy-profile.%s.%s" % (domain, stack),
                    "test_commands": adapter.get_test_commands(),
                    "build_commands": adapter.get_build_commands(),
                    "pre_commit": ["pre-commit", "run", "--all-files"] if (target_path / ".pre-commit-config.yaml").exists() else [],
                    "write_effects": ["test reports, build artifacts, caches, and tool-managed files may be written"],
                    "network_policy": "may-access-network",
                    "message": "No process was started. Review this preview and re-run with --confirm-command-execution.",
                }
            print(json.dumps(preview, indent=2, sort_keys=True))
            sys.exit(2)
        sys.argv = [sys.argv[0], str(target_path)]
        if args.confirm_command_execution:
            sys.argv.append("--confirm-command-execution")
        return verify_main()

    # Route: Scaffolding Generation
    registry = AdapterRegistry(profiles_dir=SKILL_ROOT / "profiles")
    detected_domain, detected_stack, detected_topology, detected_adapter = detect_3axis(
        target_path, registry=registry
    )

    # Determine domain, stack, and active adapter
    domain = args.domain or detected_domain
    stack = args.stack or detected_stack
    topology = args.topology or detected_topology
    raw_name = args.name or target_path.name or "MyProject"
    project_name = re.sub(r"[^A-Za-z0-9_-]+", "_", raw_name).strip("_-") or "MyProject"
    if not project_name[0].isalpha() and project_name[0] != "_":
        project_name = "_" + project_name
    project_name = project_name[:64]

    # Fetch adapter from registry if overridden or detected
    adapter = registry.get(domain, stack) if (args.domain or args.stack) else detected_adapter
    if not adapter or adapter.stack_id == "generic":
        print("DISCOVERY INCOMPLETE: no confident stack profile is available; nothing was written.")
        if getattr(detected_adapter, "_discovery_state", "unknown") == "ambiguous":
            print("Matching profile evidence is ambiguous:")
            for candidate in detected_adapter._discovery_candidates:
                print(
                    f"  - {candidate['domain']}/{candidate['stack']}: score {candidate['score']} ({candidate['matched']})"
                )
        for error in getattr(detected_adapter, "_profile_load_errors", []):
            print(f"Profile load error: {error['path']}: {error['error']}")
        print(
            "Clarify the project purpose, users, scale, constraints, existing boundaries, and verification needs."
        )
        print(
            "Then select an architecture and an available stack profile before running generation."
        )
        if args.domain or args.stack:
            print(f"No exact profile found for {domain}/{stack}.")
        sys.exit(2)

    architecture_options = (
        adapter.get_architecture_options() if hasattr(adapter, "get_architecture_options") else {}
    )
    if architecture_options and not args.architecture:
        print("ARCHITECTURE DECISION REQUIRED: no files were written.")
        print(
            "Choose from the profile-supported options after reviewing project size, domain boundaries, scale, and deployment needs:"
        )
        for key, directories in architecture_options.items():
            print(f"  - {key}: {', '.join(directories)}")
        print(
            "For an existing project, preserve and extend its established architecture unless asked to restructure it."
        )
        sys.exit(2)
    if args.architecture and args.architecture not in architecture_options:
        print(
            f"Architecture '{args.architecture}' is not supported by profile '{adapter.stack_id}'."
        )
        print(f"Available: {', '.join(architecture_options) or '[profile default only]'}")
        sys.exit(2)
    if not args.dry_run and not args.confirm_plan:
        print("PLAN CONFIRMATION REQUIRED: no files were written.")
        print(
            "Review the dry-run output, architecture, directories, and planned files; then rerun with --confirm-plan."
        )
        sys.exit(2)

    print("================================================================================")
    print("             CONTEXT-AWARE PROJECT SCAFFOLDER                                   ")
    print("================================================================================")
    print(f"Target Directory : {target_path}")
    print(f"Project Name     : {project_name}")
    print(f"Domain Archetype : {domain.upper()}")
    print(f"Technology Stack : {stack.upper()} ({adapter.display_name})")
    print(f"Project Topology : {topology.upper()}")
    print(f"Architecture     : {(args.architecture or 'profile default').upper()}")
    print(f"Execution Mode   : {'DRY-RUN (Preview)' if args.dry_run else 'LIVE EXECUTION'}")
    print("--------------------------------------------------------------------------------")

    try:
        results = scaffold_project(
            target_path=target_path,
            adapter=adapter,
            topology=topology,
            architecture=args.architecture,
            project_name=project_name,
            dry_run=args.dry_run,
            force=args.force,
        )
    except (OSError, ValueError) as exc:
        print(f"Scaffolding stopped safely: {exc}")
        sys.exit(2)

    item_mark = "[~]" if args.dry_run else "[x]"
    print(
        f"\n[1/4] {'Planned' if args.dry_run else 'Created'} Directory Hierarchy ({len(results['directories_created'])} directories)..."
    )
    for d in results["directories_created"]:
        print(f"  {item_mark} {d}/")

    if results["blocked"]:
        print(f"\n[BLOCKED] {len(results['conflicts'])} path conflict(s) preserved.")
        for conflict in results["conflicts"]:
            digest = conflict.get("existing_hash", "not a regular file")
            print(f"  [!] {conflict['path']} (existing SHA-256: {digest})")
        if any(item.get("existing_kind") != "file" for item in results["conflicts"]):
            print(
                "Resolve directory/path-type conflicts manually; --force cannot replace directories."
            )
        else:
            print(
                "Review the conflicting paths and hashes. Re-run with --force only after explicit overwrite approval."
            )
        sys.exit(2)

    action = "Planned" if args.dry_run else "Generated"
    planned_or_written = (
        results.get("planned_files", results["files_written"])
        if args.dry_run
        else results["files_written"]
    )
    print(
        f"\n[2/4] File {action} ({len(planned_or_written)} files; {len(results['identical'])} unchanged)..."
    )
    for f in planned_or_written:
        print(f"  {item_mark} {f}")

    if results["conflicts"]:
        print(
            f"\n[!] Overwrote {len(results['conflicts'])} explicitly approved conflicting file(s); backups were created."
        )

    print("\n[3/4] Repository Metadata and CI Profile Applied")
    ci_path = ".github/workflows/ci.yml"
    if (
        ci_path in planned_or_written
        or ci_path in results["files_written"]
        or ci_path in results["identical"]
    ):
        ci_mark = "[=]" if ci_path in results["identical"] else item_mark
        print(f"  {ci_mark} {ci_path}")
    else:
        print("  [ ] No CI workflow was declared by the active adapter")
    attr_mark = "[=]" if ".gitattributes" in results["identical"] else item_mark
    print(f"  {attr_mark} .gitattributes (LF normalization + LFS)")
    print("  [ ] Pre-commit configuration and hook installation are not generated by this version")

    print(f"\n[4/4] Scaffolding {'preview' if args.dry_run else 'sequence'} completed.")
    print("Next step: Run `python scripts/scaffold.py --audit` or `--verify` to inspect.")
    print("================================================================================\n")


if __name__ == "__main__":
    sys.exit(main())
