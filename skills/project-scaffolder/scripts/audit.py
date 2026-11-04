#!/usr/bin/env python3
"""
audit.py - 20-Category Scaffolding Auditor CLI
Part of the 'project-scaffolder' skill.

Rule 1 & Rule 2 Compliance:
- Fully domain-agnostic.
- Delegates evaluation to core.audit_engine using active StackAdapter.
"""

import sys
from pathlib import Path
from typing import List

# Add parent directory for module imports
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from core.audit_engine import run_audit
from core.contract import AuditItemResult
from core.registry import AdapterRegistry
from discover import detect_3axis


def print_audit_report(
    results: List[AuditItemResult], domain: str, stack: str, topology: str
) -> bool:
    """Prints a structured, formatted markdown report of the 20-category audit."""
    print("================================================================================")
    print("             PROFILE-SCOPED 20-CATEGORY READINESS AUDIT                          ")
    print("================================================================================")
    print(f"Domain Archetype : {domain.upper()}")
    print(f"Technology Stack : {stack.upper()}")
    print(f"Topology Pattern : {topology.upper()}")
    print("--------------------------------------------------------------------------------")
    print(f"{'#':<3} | {'STATUS':<14} | {'CATEGORY':<35} | {'DETAILS'}")
    print("-" * 80)

    pass_count = 0
    fail_count = 0
    nv_count = 0
    na_count = 0

    current_pillar = ""
    for r in results:
        if r.pillar != current_pillar:
            current_pillar = r.pillar
            print(f"\n--- {current_pillar} ---")

        status_str = f"[{r.status}]"
        print(f"{r.num:02d}  | {status_str:<14} | {r.name:<35} | {r.details}")

        if r.status == "PASS":
            pass_count += 1
        elif r.status == "FAIL":
            fail_count += 1
        elif r.status == "NOT VERIFIED":
            nv_count += 1
        elif r.status == "NOT APPLICABLE":
            na_count += 1

    total_applicable = 20 - na_count
    score_pct = (pass_count / total_applicable * 100) if total_applicable > 0 else 100.0

    print("\n================================================================================")
    print("AUDIT SUMMARY:")
    print(f"  Passed Requirements : {pass_count}/{total_applicable} ({score_pct:.1f}%)")
    print(f"  Failed Requirements : {fail_count}")
    print(f"  Unverified (Env)    : {nv_count}")
    print(f"  Exempted (N/A)      : {na_count}")
    print("--------------------------------------------------------------------------------")

    if fail_count == 0 and nv_count == 0:
        print("STATUS: SCAFFOLDING COMPLETE (all mandatory checks verified)")
        print("Note  : Scaffolding Complete != Production Ready.")
        print("================================================================================\n")
        return True
    elif fail_count == 0:
        print("STATUS: INCOMPLETE (no failures reported, but required checks remain unverified)")
        print("Note  : A configured file or command is not evidence that it executed successfully.")
        print("================================================================================\n")
        return False
    else:
        print(f"STATUS: BLOCKED ({fail_count} requirement(s) failed)")
        print("================================================================================\n")
        return False


def main():
    target = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    registry = AdapterRegistry(profiles_dir=SKILL_ROOT / "profiles")
    domain, stack, topology, adapter = detect_3axis(target, registry=registry)

    if adapter.stack_id == "generic":
        print(
            f"AUDIT NOT RUN: {getattr(adapter, '_discovery_state', 'unknown')} stack discovery; no applicable profile was selected."
        )
        for error in getattr(adapter, "_profile_load_errors", []):
            print(f"Profile load error: {error['path']}: {error['error']}")
        print(
            "Clarify the project domain and toolchain, or add a profile with explicit audit criteria."
        )
        sys.exit(2)

    results = run_audit(target, adapter=adapter, topology=topology)
    success = print_audit_report(results, domain, stack, topology)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
