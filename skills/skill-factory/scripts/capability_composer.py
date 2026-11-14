#!/usr/bin/env python3
"""
capability_composer.py - True DAG Capability Composition Engine
Part of the 'skill-factory' meta-skill.

Capabilities:
1. Formal Capability Contracts:
   - Explicit inputs, outputs, preconditions, permissions, and verification criteria.
2. True Directed Acyclic Graph (DAG) Composition:
   - Multi-dependency resolution (many-to-many input/output handoffs).
   - Dynamic auto-bridging of missing input providers from registered capabilities.
   - Mechanism to accept initial user/environment inputs before workflow begins.
   - Topological sorting with cycle detection (Kahn's algorithm).
   - Branching and converging execution pipelines (e.g. parallel analysis + security converging at validation).
3. Dynamic Contract Extraction from SKILL.md:
   - Reads formal YAML contract blocks or infers capability boundaries from frontmatter tools and triggers.
4. Precondition & Tool Permission Verification.
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Ensure local imports work
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from capability_matcher import UNIVERSAL_CAPABILITIES

# -----------------------------------------------------------------------------
# Standardized Lifecycle Statuses
# -----------------------------------------------------------------------------
# 1. Composition / Input Readiness Statuses (Planning Phase)
STATUS_READY = "READY"  # Inputs satisfied; ready to run
STATUS_INPUT_GAP = "INPUT_GAP"  # Missing root input from caller or environment
STATUS_BLOCKED = "BLOCKED"  # Blocked because upstream producer stage has not satisfied outputs

# 2. Actual Execution & Verification Statuses (Execution Phase)
EXECUTION_STATUS_PENDING = "PENDING"  # Not yet started
EXECUTION_STATUS_RUNNING = "RUNNING"  # In execution
EXECUTION_STATUS_COMPLETED = "COMPLETED"  # Finished execution; outputs produced
EXECUTION_STATUS_VERIFIED = "VERIFIED"  # Outputs independently verified against contract criteria
EXECUTION_STATUS_FAILED = "FAILED"  # Execution or verification failed


@dataclass
class CapabilityContract:
    id: str
    name: str
    facet: str
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    verification: str = ""
    failure_modes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "facet": self.facet,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "preconditions": self.preconditions,
            "permissions": self.permissions,
            "verification": self.verification,
            "failure_modes": self.failure_modes,
        }


# Canonical Registry of Standard Agent Capability Contracts across Domains
CANONICAL_CONTRACTS: Dict[str, CapabilityContract] = {
    # -------------------------------------------------------------------------
    # Software & Systems Engineering Contracts
    # -------------------------------------------------------------------------
    "code-discovery": CapabilityContract(
        id="code-discovery",
        name="Source Code & File Discovery",
        facet="research",
        inputs=["workspace_path"],
        outputs=["file_manifest", "project_evidence"],
        preconditions=["Target workspace path exists and is readable"],
        permissions=["read_file"],
        verification="File manifest contains non-zero validated file paths",
        failure_modes=["Permission denied", "Empty directory"],
    ),
    "test-fixture-discovery": CapabilityContract(
        id="test-fixture-discovery",
        name="Test Suite & Fixtures Discovery",
        facet="research",
        inputs=["workspace_path"],
        outputs=["test_fixtures"],
        preconditions=["Workspace path readable"],
        permissions=["read_file"],
        verification="Identified test files or test runner configuration",
        failure_modes=["No test files found"],
    ),
    "static-analysis": CapabilityContract(
        id="static-analysis",
        name="Static Code & AST Analysis",
        facet="analysis",
        inputs=["file_manifest"],
        outputs=["code_quality_findings"],
        preconditions=["file_manifest must be populated"],
        permissions=["read_file"],
        verification="AST parser and linter output generated",
        failure_modes=["Unparseable syntax", "Missing compiler/linter"],
    ),
    "security-audit": CapabilityContract(
        id="security-audit",
        name="Security & Threat Audit",
        facet="security",
        inputs=["file_manifest"],
        outputs=["security_findings", "trust_tier"],
        preconditions=["file_manifest must be populated"],
        permissions=["read_file"],
        verification="Zero unreviewed CRITICAL vulnerabilities",
        failure_modes=["External scanner unavailable", "Obfuscated payload"],
    ),
    "test-runner": CapabilityContract(
        id="test-runner",
        name="Automated Test Execution",
        facet="validation",
        inputs=["file_manifest", "test_fixtures"],
        outputs=["test_results", "coverage_metrics"],
        preconditions=["Test runner and fixtures installed"],
        permissions=["run_command", "read_file"],
        verification="All assertions pass with exit code 0",
        failure_modes=["Test assertions failed", "Runner timeout"],
    ),
    "result-validation": CapabilityContract(
        id="result-validation",
        name="Result Validation & Deduplication",
        facet="validation",
        inputs=["code_quality_findings"],
        outputs=["verified_findings"],
        preconditions=["At least one upstream findings report provided"],
        permissions=["read_file"],
        verification="Zero unverified speculative assumptions in findings",
        failure_modes=["Conflicting findings between analyzers"],
    ),
    "report-generation": CapabilityContract(
        id="report-generation",
        name="Executive Markdown Report Delivery",
        facet="delivery",
        inputs=["verified_findings"],
        outputs=["executive_report_md"],
        preconditions=["verified_findings must be finalized"],
        permissions=["write_file"],
        verification="Report generated with strict LF and structured findings",
        failure_modes=["Output path unwriteable"],
    ),
    # -------------------------------------------------------------------------
    # Domain-Agnostic, Knowledge & Content Creation Contracts
    # -------------------------------------------------------------------------
    "task-scoping": CapabilityContract(
        id="task-scoping",
        name="Task Scoping & Specification",
        facet="planning",
        inputs=["task_prompt"],
        outputs=["specification_brief", "content_payload"],
        preconditions=["User task prompt provided"],
        permissions=[],
        verification="Specification brief contains clear goals and constraints",
        failure_modes=["Vague requirements"],
    ),
    "literature-research": CapabilityContract(
        id="literature-research",
        name="Literature & Contextual Research",
        facet="research",
        inputs=["task_prompt"],
        outputs=["research_brief", "source_evidence", "content_payload"],
        preconditions=["Task prompt or domain topic provided"],
        permissions=["web_search", "read_file"],
        verification="Research brief contains verified findings and references",
        failure_modes=["Search unreachable", "No relevant references"],
    ),
    "content-authoring": CapabilityContract(
        id="content-authoring",
        name="Content & Creative Authoring",
        facet="creation",
        inputs=["task_prompt"],
        outputs=["draft_content", "content_payload"],
        preconditions=["Task prompt or research brief provided"],
        permissions=["write_file"],
        verification="Content artifact created and non-empty",
        failure_modes=["Synthesis error"],
    ),
    "content-analysis": CapabilityContract(
        id="content-analysis",
        name="Content & Quantitative Analysis",
        facet="analysis",
        inputs=["content_payload"],
        outputs=["analytical_findings", "content_payload"],
        preconditions=["Draft content, research brief, or metrics provided"],
        permissions=["read_file"],
        verification="Analysis metrics and findings populated",
        failure_modes=["Invalid data format"],
    ),
    "content-verification": CapabilityContract(
        id="content-verification",
        name="Consistency & Quality Verification",
        facet="validation",
        inputs=["content_payload"],
        outputs=["verified_content", "content_payload"],
        preconditions=["Draft or analyzed content provided"],
        permissions=["read_file"],
        verification="Passed consistency and constraint checks",
        failure_modes=["Constraint violation"],
    ),
    "document-delivery": CapabilityContract(
        id="document-delivery",
        name="Document & Deliverable Publishing",
        facet="delivery",
        inputs=["content_payload"],
        outputs=["final_delivery"],
        preconditions=["Draft, verified content, or analytical brief available"],
        permissions=["write_file"],
        verification="Final delivery formatted and confirmed",
        failure_modes=["Delivery write failure"],
    ),
    "creative-design": CapabilityContract(
        id="creative-design",
        name="Creative Architecture & Design",
        facet="design",
        inputs=["task_prompt"],
        outputs=["design_spec", "content_payload"],
        preconditions=["User task prompt provided"],
        permissions=[],
        verification="Design specification details structure or visual layout",
        failure_modes=["Unclear creative requirements"],
    ),
    "workflow-orchestration": CapabilityContract(
        id="workflow-orchestration",
        name="Cross-Domain Workflow Orchestration",
        facet="orchestration",
        inputs=["content_payload"],
        outputs=["orchestration_plan", "content_payload"],
        preconditions=["Upstream content payload provided"],
        permissions=[],
        verification="Orchestration plan outlines milestone sequence",
        failure_modes=["Unresolved dependencies"],
    ),
    "feedback-learning": CapabilityContract(
        id="feedback-learning",
        name="Feedback Integration & Continuous Learning",
        facet="learning",
        inputs=["content_payload"],
        outputs=["learning_insights"],
        preconditions=["Evaluated deliverable available"],
        permissions=[],
        verification="Feedback integrated into guidelines",
        failure_modes=["No feedback data"],
    ),
}


def extract_contract_from_skill_md(skill_md_path: Path) -> Optional[CapabilityContract]:
    """
    Extracts formal CapabilityContract from a SKILL.md file.
    1. Checks for explicit YAML `contract:` block in frontmatter.
    2. Infers contract boundaries dynamically from frontmatter name, description,
       and allowed-tools.
    """
    if not skill_md_path.exists():
        return None
    try:
        content = skill_md_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    # Parse frontmatter
    fm_match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not fm_match:
        return None
    fm_text = fm_match.group(1)

    skill_name = skill_md_path.parent.name
    name_m = re.search(r"^name:\s*(.+)$", fm_text, re.MULTILINE)
    if name_m:
        skill_name = name_m.group(1).strip()

    desc = ""
    desc_m = re.search(
        r"^description:\s*>?-?\s*\n?(.*?)(?:\n[a-z\-]+:|\Z)", fm_text, re.MULTILINE | re.DOTALL
    )
    if desc_m:
        desc = desc_m.group(1).strip()

    allowed_tools = []
    tools_m = re.search(r"allowed-tools:\s*\n((?:\s*-\s*[^\n]+\n?)+)", fm_text)
    if tools_m:
        for raw_line in tools_m.group(1).splitlines():
            stripped = raw_line.strip()
            if stripped.startswith("-"):
                val = stripped[1:].strip().strip("'\"")
                if val:
                    allowed_tools.append(val)

    # 1. Check for explicit contract block in frontmatter
    contract_m = re.search(r"^contract:\s*\n((?:\s+[a-z\-]+:[^\n]*\n?)+)", fm_text, re.MULTILINE)
    if contract_m:
        c_block = contract_m.group(1)
        c_id = re.search(r"id:\s*([a-zA-Z0-9_\-]+)", c_block)
        c_name = re.search(r"name:\s*(.+)$", c_block, re.MULTILINE)
        c_facet = re.search(r"facet:\s*([a-zA-Z0-9_\-]+)", c_block)
        inputs_m = re.search(r"inputs:\s*\[(.*?)\]", c_block)
        outputs_m = re.search(r"outputs:\s*\[(.*?)\]", c_block)

        inputs = (
            [i.strip() for i in inputs_m.group(1).split(",") if i.strip()]
            if inputs_m
            else ["task_prompt"]
        )
        outputs = (
            [o.strip() for o in outputs_m.group(1).split(",") if o.strip()]
            if outputs_m
            else [f"{skill_name}_output"]
        )

        return CapabilityContract(
            id=c_id.group(1) if c_id else skill_name,
            name=c_name.group(1).strip() if c_name else skill_name.replace("-", " ").title(),
            facet=c_facet.group(1) if c_facet else "creation",
            inputs=inputs,
            outputs=outputs,
            preconditions=[],
            permissions=allowed_tools,
            verification="Contract execution verified",
            failure_modes=[],
        )

    # 2. Inferred contract from frontmatter metadata
    combined_desc = f"{skill_name} {desc}".lower()
    inferred_facet = "creation"
    for facet_id, cap_data in UNIVERSAL_CAPABILITIES.items():
        if any(kw in combined_desc for kw in cap_data.get("keywords", [])):
            inferred_facet = facet_id
            break

    if inferred_facet in ("research", "planning"):
        inputs = ["task_prompt"]
        outputs = [f"{skill_name}_evidence", "content_payload"]
    elif inferred_facet in ("creation", "analysis"):
        inputs = ["task_prompt", "content_payload"]
        outputs = [f"{skill_name}_output", "content_payload"]
    elif inferred_facet == "delivery":
        inputs = ["content_payload"]
        outputs = ["final_delivery"]
    else:
        inputs = ["workspace_path"]
        outputs = [f"{skill_name}_output"]

    return CapabilityContract(
        id=skill_name,
        name=skill_name.replace("-", " ").title(),
        facet=inferred_facet,
        inputs=inputs,
        outputs=outputs,
        preconditions=[f"Skill {skill_name} installed"],
        permissions=allowed_tools,
        verification=f"Execution of {skill_name} completed cleanly",
        failure_modes=["Execution failure"],
    )


class CapabilityCompositionEngine:
    """
    DAG-based capability composer.
    Assembles multi-stage workflows, resolves input/output dependencies,
    detects cycles, and ensures complete continuity across handoffs.
    Supports dynamic contract extraction from SKILL.md.
    """

    def __init__(self, registry: Optional[Dict[str, CapabilityContract]] = None):
        self.registry = registry or dict(CANONICAL_CONTRACTS)

    def load_discovered_contracts(
        self, search_paths: Optional[List[Path]] = None
    ) -> Dict[str, CapabilityContract]:
        """
        Dynamically extracts and registers CapabilityContracts from discovered SKILL.md files.
        Enables dynamic composition from skills installed in the environment.
        """
        discovered: Dict[str, CapabilityContract] = {}
        paths_to_search: List[Path] = []
        if search_paths:
            paths_to_search = search_paths
        else:
            try:
                from agent_adapter import AgentEnvironmentAdapter

                adapter = AgentEnvironmentAdapter()
                paths_to_search = adapter.get_all_discovery_paths()
            except Exception:
                pass

        for sp in paths_to_search:
            if not sp.exists() or not sp.is_dir():
                continue
            for skill_dir in sp.iterdir():
                if skill_dir.is_dir():
                    skill_md = skill_dir / "SKILL.md"
                    if skill_md.exists():
                        contract = extract_contract_from_skill_md(skill_md)
                        if contract:
                            discovered[contract.id] = contract
                            self.registry[contract.id] = contract
        return discovered

    def topological_sort(
        self, contracts: List[CapabilityContract]
    ) -> Tuple[List[CapabilityContract], bool]:
        """
        Sorts contracts in topological order based on input/output data flow.
        Detects circular dependencies. Returns (sorted_list, has_cycle).
        """
        FACET_ORDER = [
            "planning",
            "research",
            "design",
            "creation",
            "analysis",
            "security",
            "validation",
            "orchestration",
            "delivery",
            "learning",
        ]
        facet_rank = {f: i for i, f in enumerate(FACET_ORDER)}

        contract_map = {c.id: c for c in contracts}
        in_degree: Dict[str, int] = {c.id: 0 for c in contracts}
        adj_list: Dict[str, List[str]] = {c.id: [] for c in contracts}

        # Build DAG edges: contract A -> contract B if A produces an input required by B
        for a in contracts:
            for b in contracts:
                if a.id != b.id:
                    # If A's outputs satisfy any of B's inputs
                    shared = set(a.outputs).intersection(set(b.inputs))
                    if shared:
                        # Prevent artificial cycles from generic pass-through tokens (e.g. content_payload)
                        # by respecting canonical lifecycle facet order
                        if shared == {"content_payload"} and facet_rank.get(
                            a.facet, 4
                        ) >= facet_rank.get(b.facet, 4):
                            continue
                        adj_list[a.id].append(b.id)
                        in_degree[b.id] += 1

        # Kahn's algorithm for topological sorting
        queue = [cid for cid, deg in in_degree.items() if deg == 0]
        sorted_ids = []

        while queue:
            # Deterministic ordering by lifecycle facet rank, then contract id
            queue.sort(key=lambda cid: (facet_rank.get(contract_map[cid].facet, 4), cid))
            curr = queue.pop(0)
            sorted_ids.append(curr)

            for neighbor in adj_list[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        has_cycle = len(sorted_ids) != len(contracts)
        sorted_contracts = [contract_map[cid] for cid in sorted_ids if cid in contract_map]

        return sorted_contracts, has_cycle

    def compose_workflow_for_task(
        self,
        requested_capabilities: List[str],
        initial_inputs: Optional[Union[List[str], Set[str]]] = None,
        domain: str = "auto",
        task_context: str = "",
    ) -> Dict[str, Any]:
        """
        Builds a true DAG workflow chain matching requested capability facets.
        Resolves input/output dependencies dynamically across branching stages.
        Accepts initial user/environment inputs.
        """
        selected_contracts: List[CapabilityContract] = []
        has_analysis = "analysis" in requested_capabilities
        has_security = "security" in requested_capabilities
        has_task_context = bool(task_context and task_context.strip())

        # Auto-detect domain if needed: software, general (non-software), or unknown
        if domain == "auto":
            non_sw_contract_ids = {
                "task-scoping",
                "literature-research",
                "content-authoring",
                "content-analysis",
                "content-verification",
                "document-delivery",
                "creative-design",
                "workflow-orchestration",
                "feedback-learning",
            }
            sw_contract_ids = {
                "code-discovery",
                "test-fixture-discovery",
                "static-analysis",
                "security-audit",
                "test-runner",
                "result-validation",
                "report-generation",
            }
            if has_task_context:
                from capability_matcher import classify_domain_class

                dom_class = classify_domain_class(task_context)
                if dom_class == "software":
                    domain = "software"
                elif dom_class == "non_software":
                    domain = "general"
                else:
                    domain = "unknown"
            elif any(c in sw_contract_ids for c in requested_capabilities) or (
                initial_inputs and "workspace_path" in initial_inputs
            ):
                domain = "software"
            elif any(c in non_sw_contract_ids for c in requested_capabilities):
                domain = "general"
            elif (
                initial_inputs
                and "task_prompt" in initial_inputs
                and "workspace_path" not in initial_inputs
            ):
                domain = "general"
            else:
                # With zero context, no software inputs, and only abstract facets:
                # Default strictly to "unknown", NEVER assume software!
                domain = "unknown"

        # Setup initial inputs
        if initial_inputs is not None:
            available_inputs = set(initial_inputs)
        else:
            available_inputs = set()
            if domain == "software":
                available_inputs.add("workspace_path")
            if has_task_context or domain == "general":
                available_inputs.add("task_prompt")

        # Context-aware contract selection
        for facet in requested_capabilities:
            # 1. Exact contract ID match in registry
            if facet in self.registry:
                cand = self.registry[facet]
                # In non-software or unknown domain, exclude software-only contracts
                if (
                    domain != "software"
                    and "workspace_path" in cand.inputs
                    and "task_prompt" not in cand.inputs
                ):
                    continue
                if cand not in selected_contracts:
                    selected_contracts.append(cand)
                continue

            # 2. Domain-appropriate facet selection for non-software / content / unknown tasks
            if domain in ("general", "unknown"):
                general_facet_map = {
                    "planning": "task-scoping",
                    "research": "literature-research",
                    "design": "creative-design",
                    "creation": "content-authoring",
                    "analysis": "content-analysis",
                    "validation": "content-verification",
                    "orchestration": "workflow-orchestration",
                    "delivery": "document-delivery",
                    "learning": "feedback-learning",
                }
                cid = general_facet_map.get(facet)
                if cid and cid in self.registry and self.registry[cid] not in selected_contracts:
                    selected_contracts.append(self.registry[cid])
                    continue
                elif facet == "security":
                    # Non-software / unknown tasks map security to content verification instead of code scanning
                    if (
                        "content-verification" in self.registry
                        and self.registry["content-verification"] not in selected_contracts
                    ):
                        selected_contracts.append(self.registry["content-verification"])
                    continue

            # 3. Software domain facet selection
            if facet == "validation":
                # If upstream is analysis/security, select result-validation
                if (
                    (has_analysis or has_security)
                    and "result-validation" in self.registry
                    and not any(c.id == "result-validation" for c in selected_contracts)
                ):
                    selected_contracts.append(self.registry["result-validation"])
                elif "test-runner" in self.registry and not any(
                    c.id == "test-runner" for c in selected_contracts
                ):
                    selected_contracts.append(self.registry["test-runner"])
            else:
                matching = [c for c in self.registry.values() if c.facet == facet or c.id == facet]
                matched_any = False
                for m in matching:
                    if (
                        domain != "software"
                        and "workspace_path" in m.inputs
                        and "task_prompt" not in m.inputs
                    ):
                        continue
                    matched_any = True
                    if m not in selected_contracts:
                        selected_contracts.append(m)
                        break
                if (
                    not matched_any
                    and facet
                    and not any(c.facet == facet or c.id == facet for c in selected_contracts)
                ):
                    custom_slug = re.sub(r"[^a-z0-9-]+", "-", facet.lower()).strip("-") or "custom-facet"
                    custom_inputs = ["workspace_path"] if domain == "software" else ["task_prompt"]
                    selected_contracts.append(
                        CapabilityContract(
                            id=f"custom-{custom_slug}",
                            name=facet.replace("_", " ").replace("-", " ").title(),
                            facet=facet,
                            inputs=custom_inputs,
                            outputs=[f"{facet}_output", "content_payload"],
                            preconditions=["Open-domain facet requested via explicit --facets"],
                            permissions=[],
                            verification=f"Validate {facet} deliverable completeness",
                            failure_modes=[f"Incomplete {facet} output"],
                        )
                    )

        # Dynamic Dependency Resolution:
        # If any selected contract needs an input not yet provided,
        # search the registry for a provider capability contract and bridge it.
        added_new = True
        while added_new:
            added_new = False
            needed_inputs = set()
            for sc in selected_contracts:
                provided_by_others = set(available_inputs)
                for other in selected_contracts:
                    if other != sc:
                        provided_by_others.update(other.outputs)
                for inp in sc.inputs:
                    if inp not in provided_by_others:
                        needed_inputs.add(inp)

            for needed in needed_inputs:
                for cand_id, cand_contract in self.registry.items():
                    # For non-software / unknown domains, strictly prohibit bridging software contracts
                    if (
                        domain != "software"
                        and "workspace_path" in cand_contract.inputs
                        and "task_prompt" not in cand_contract.inputs
                    ):
                        continue
                    if cand_contract not in selected_contracts and needed in cand_contract.outputs:
                        selected_contracts.append(cand_contract)
                        added_new = True
                        break

        # Run DAG Topological Sort & Cycle Detection
        sorted_contracts, has_cycle = self.topological_sort(selected_contracts)

        # Verify contract continuity
        running_outputs: Set[str] = set(available_inputs)
        missing_inputs: List[Dict[str, Any]] = []
        execution_stages: List[Dict[str, Any]] = []

        for stage_idx, contract in enumerate(sorted_contracts, 1):
            unmet = [inp for inp in contract.inputs if inp not in running_outputs]
            if unmet:
                # Distinguish between root unmet inputs (e.g. task_prompt from caller)
                # and cascading blocked inputs (upstream stage failed to produce them)
                upstream_declared = {
                    out for prev_c in sorted_contracts[: stage_idx - 1] for out in prev_c.outputs
                }
                is_upstream_blocked = any(inp in upstream_declared for inp in unmet)
                stage_status = STATUS_BLOCKED if is_upstream_blocked else STATUS_INPUT_GAP

                missing_inputs.append(
                    {
                        "stage": stage_idx,
                        "contract": contract.id,
                        "unmet_inputs": unmet,
                        "status": stage_status,
                    }
                )
            else:
                stage_status = STATUS_READY
                # Only ready stages can forward outputs to downstream stages
                running_outputs.update(contract.outputs)

            execution_stages.append(
                {
                    "stage": stage_idx,
                    "contract_id": contract.id,
                    "name": contract.name,
                    "facet": contract.facet,
                    "inputs": contract.inputs,
                    "outputs": contract.outputs,
                    "permissions": contract.permissions,
                    "verification": contract.verification,
                    "readiness_status": stage_status,
                    "status": stage_status,
                    "execution_status": EXECUTION_STATUS_PENDING,
                    "execution_evidence": None,
                }
            )

        # Build Mermaid Workflow DAG Diagram
        mermaid_facet_rank = {
            f: i
            for i, f in enumerate(
                [
                    "planning",
                    "research",
                    "design",
                    "creation",
                    "analysis",
                    "security",
                    "validation",
                    "orchestration",
                    "delivery",
                    "learning",
                ]
            )
        }
        mermaid_lines = ["flowchart TD"]
        for c in sorted_contracts:
            mermaid_lines.append(f'    {c.id.replace("-", "_")}["{c.name} ({c.facet.upper()})"]')

        for u in sorted_contracts:
            for v in sorted_contracts:
                if u.id == v.id:
                    continue
                shared = set(u.outputs).intersection(set(v.inputs))
                if shared:
                    if shared == {"content_payload"} and mermaid_facet_rank.get(
                        u.facet, 4
                    ) >= mermaid_facet_rank.get(v.facet, 4):
                        continue
                    label = sorted(shared)[0]
                    mermaid_lines.append(
                        f"    {u.id.replace('-', '_')} -->|{label}| {v.id.replace('-', '_')}"
                    )

        # Compute parallel execution batches (concurrency groups)
        # Batch 0: stages whose inputs are satisfied by initial inputs
        # Batch k: stages whose inputs are satisfied by running outputs up to batch k-1
        parallel_batches: List[List[str]] = []
        assigned_cids: Set[str] = set()
        current_available = set(available_inputs)
        selected_by_id = {c.id: c for c in sorted_contracts}

        while len(assigned_cids) < len(sorted_contracts):
            current_batch = []
            for c in sorted_contracts:
                if c.id not in assigned_cids:
                    if all(inp in current_available for inp in c.inputs):
                        current_batch.append(c.id)
            if not current_batch:
                # Unmet dependencies or cycle fallback: group remaining
                remaining = [c.id for c in sorted_contracts if c.id not in assigned_cids]
                if remaining:
                    parallel_batches.append(remaining)
                break
            parallel_batches.append(current_batch)
            for cid in current_batch:
                assigned_cids.add(cid)
                contract_obj = selected_by_id.get(cid) or self.registry.get(cid)
                if contract_obj:
                    current_available.update(contract_obj.outputs)

        # Task Intent Alignment Check
        # Evaluates whether the generated workflow covers key intent facets signaled by task context
        intent_alignment: Dict[str, Any] = {
            "aligned": True,
            "detected_intent_facets": [],
            "covered_facets": list({c.facet for c in sorted_contracts}),
            "warnings": [],
        }
        if has_task_context:
            try:
                from capability_matcher import ContextAwareCapabilityResolver

                tc_lower = ContextAwareCapabilityResolver(task_context).positive_task.lower()
            except Exception:
                tc_lower = task_context.lower()
            facet_signals = {
                "security": [
                    "security",
                    "threat",
                    "vulnerability",
                    "audit security",
                    "cve",
                    "secret leak",
                    "leak",
                ],
                "research": [
                    "research",
                    "survey",
                    "literature",
                    "paper",
                    "investigate",
                    "history",
                    "\u0e04\u0e49\u0e19\u0e04\u0e27\u0e49\u0e32",
                    "\u0e1b\u0e23\u0e30\u0e27\u0e31\u0e15\u0e34",
                ],
                "validation": [
                    "test",
                    "verify",
                    "benchmark",
                    "assertion",
                    "unit test",
                    "integration test",
                    "spec",
                ],
                "delivery": [
                    "report",
                    "deliverable",
                    "summary",
                    "article",
                    "publish",
                    "\u0e1a\u0e17\u0e04\u0e27\u0e32\u0e21",
                    "\u0e23\u0e32\u0e22\u0e07\u0e32\u0e19",
                ],
                "analysis": [
                    "analyze",
                    "analysis",
                    "profile",
                    "metrics",
                    "financial",
                    "\u0e07\u0e1a\u0e01\u0e32\u0e23\u0e40\u0e07\u0e34\u0e19",
                    "\u0e01\u0e32\u0e23\u0e40\u0e07\u0e34\u0e19",
                ],
            }
            detected = []
            for facet_name, keywords in facet_signals.items():
                if any(kw in tc_lower for kw in keywords):
                    detected.append(facet_name)
            intent_alignment["detected_intent_facets"] = detected

            covered = set(intent_alignment["covered_facets"])
            missing_facets = [f for f in detected if f not in covered]
            if missing_facets:
                intent_alignment["aligned"] = False
                intent_alignment["warnings"].append(
                    f"Task context strongly signals requirement for '{', '.join(missing_facets)}', but workflow does not contain these facets."
                )

        # Evaluate contextual completeness:
        # Separate "No task context provided (requires more info)" from
        # "Context provided but domain is unknown".
        if has_task_context:
            task_context_status = "PROVIDED"
        elif initial_inputs is not None and len(initial_inputs) > 0:
            task_context_status = "EXTERNAL"
        elif domain == "software" and "workspace_path" in available_inputs:
            task_context_status = "WORKSPACE_EVIDENCED"
        else:
            task_context_status = "MISSING"

        # Check whether any unmet inputs are external/root inputs that cannot be produced
        # by any registered stage in the pipeline (i.e. must come from user context or caller)
        all_stage_outputs = {out for c in sorted_contracts for out in c.outputs}
        has_root_missing_inputs = any(
            any(
                inp not in all_stage_outputs or inp in ("task_prompt", "workspace_path")
                for inp in m["unmet_inputs"]
            )
            for m in missing_inputs
        )
        requires_more_info = (task_context_status == "MISSING") or has_root_missing_inputs
        is_continuous = len(missing_inputs) == 0 and not has_cycle and not requires_more_info

        flow_result = {
            "domain": domain,
            "task_context_status": task_context_status,
            "requires_more_info": requires_more_info,
            "stages_count": len(execution_stages),
            "is_continuous": is_continuous,
            "has_cycle": has_cycle,
            "missing_inputs": missing_inputs,
            "parallel_batches": parallel_batches,
            "intent_alignment": intent_alignment,
            "stages": execution_stages,
            "mermaid_diagram": "\n".join(mermaid_lines),
        }
        if requires_more_info:
            flow_result["guidance"] = (
                "Task context is missing. Please provide a task description or user goal to supply "
                "required inputs and validate the capability workflow."
            )
        return flow_result

    def execute_workflow_simulation(self, flow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulates workflow execution, strictly distinguishing Input Readiness (READY)
        from Execution and Verification (COMPLETED / VERIFIED).
        Stages with INPUT_GAP or BLOCKED cannot execute and will be marked FAILED / BLOCKED.
        """
        sim_result = dict(flow)
        sim_stages = []
        all_ok = True

        for s in flow.get("stages", []):
            st = dict(s)
            if s.get("status") != STATUS_READY:
                st["execution_status"] = EXECUTION_STATUS_FAILED
                st["execution_evidence"] = {
                    "passed": False,
                    "error": f"Cannot execute stage '{s['contract_id']}': input readiness status is {s.get('status')}",
                }
                all_ok = False
            else:
                # Stage executes cleanly and gets independently verified
                st["execution_status"] = EXECUTION_STATUS_VERIFIED
                st["execution_evidence"] = {
                    "passed": True,
                    "verification_criterion": s.get("verification", ""),
                    "verification_evidence": f"Simulated verification passed against contract criterion: {s.get('verification', '')}",
                }
            sim_stages.append(st)

        sim_result["stages"] = sim_stages
        sim_result["execution_verified"] = all_ok
        sim_result["overall_execution_status"] = (
            EXECUTION_STATUS_VERIFIED if all_ok else EXECUTION_STATUS_FAILED
        )
        return sim_result


def main():
    parser = argparse.ArgumentParser(description="DAG Capability Composition Engine")
    parser.add_argument(
        "--facets", type=str, default="", help="Comma-separated capability facets or contract IDs"
    )
    parser.add_argument(
        "--inputs", type=str, default="", help="Comma-separated initial input tokens"
    )
    parser.add_argument(
        "--task", type=str, default="", help="Optional task description to infer capabilities from"
    )
    parser.add_argument(
        "--domain",
        type=str,
        default="auto",
        choices=["auto", "software", "general"],
        help="Task domain",
    )
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    args = parser.parse_args()

    composer = CapabilityCompositionEngine()

    explicit_facets = [f.strip() for f in args.facets.split(",") if f.strip()] if args.facets else []
    facets: List[str] = []
    initial_inputs: Set[str] = set()
    if args.inputs:
        initial_inputs = set(inp.strip() for inp in args.inputs.split(",") if inp.strip())

    domain = args.domain

    if args.task:
        from capability_matcher import (
            is_non_software_context,
            match_capabilities_for_context,
        )

        matched = match_capabilities_for_context(
            args.task,
            explicit_facets=explicit_facets or None,
        )
        facets = [c["facet"] for c in matched]
        for ef in explicit_facets:
            if ef not in facets:
                facets.append(ef)

        if is_non_software_context(args.task):
            if domain == "auto":
                domain = "general"
            if not initial_inputs:
                initial_inputs = {"task_prompt"}
        else:
            if not initial_inputs:
                initial_inputs = {"workspace_path"}
    elif explicit_facets:
        facets = explicit_facets
        if not initial_inputs:
            initial_inputs = {"task_prompt"} if domain == "general" else {"workspace_path"}
    else:
        facets = ["research", "analysis", "security", "validation", "delivery"]
        if not initial_inputs:
            initial_inputs = {"task_prompt"} if domain == "general" else {"workspace_path"}

    flow = composer.compose_workflow_for_task(
        facets, initial_inputs=initial_inputs, domain=domain, task_context=args.task
    )

    if args.json:
        import json

        print(json.dumps(flow, indent=2))
        return

    print("================================================================================")
    print("      TRUE DAG CAPABILITY COMPOSITION ENGINE (TOPOLOGICAL ORDERING)             ")
    print("================================================================================")
    print(f"Target Facets / IDs : {facets}")
    print(f"Initial Inputs      : {list(initial_inputs)}")
    print(f"Workflow Continuous : {flow['is_continuous']}")
    print(f"Has Circular Cycles : {flow['has_cycle']}")
    print(f"Stages Executed     : {flow['stages_count']}")
    print(f"Unmet Inputs Count  : {len(flow['missing_inputs'])}")

    print("\nExecution Stages:")
    for s in flow["stages"]:
        inps = ", ".join(s["inputs"]) if s["inputs"] else "(none)"
        outs = ", ".join(s["outputs"]) if s["outputs"] else "(none)"
        print(f"  Stage {s['stage']} [{s['status']}] {s['name']} ({s['facet']})")
        print(f"     <- Inputs : [{inps}]")
        print(f"     -> Outputs: [{outs}]")

    if flow["missing_inputs"]:
        print("\nMissing Input Dependencies:")
        for m in flow["missing_inputs"]:
            print(f"  Stage {m['stage']} ({m['contract']}) missing: {m['unmet_inputs']}")

    print("\nGenerated Mermaid Flowchart:")
    print(flow["mermaid_diagram"])
    print("================================================================================")


if __name__ == "__main__":
    main()
