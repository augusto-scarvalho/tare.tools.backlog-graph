from __future__ import annotations
import json
from typing import Any

from .core import WorkGraph
from .algorithms import readiness, upstream_dependencies, downstream_reach

def generate_packet(graph: WorkGraph, node_id: str, profile: str = "planning") -> dict[str, Any]:
    """Generate an execution packet containing complete context, dependencies, provenance, and exit criteria."""
    if node_id not in graph.by_id:
        raise KeyError(f"Node '{node_id}' not found in graph")
        
    n = graph.by_id[node_id]
    c = n.get("completion") or {}
    
    return {
        "schema": "tare.tools/work-packet-projection/0.2",
        "authority": "NONE / READ_ONLY PROJECTION",
        "work": n,
        "feasibility": readiness(graph, n, profile),
        "prerequisites": upstream_dependencies(graph, node_id),
        "downstream": downstream_reach(graph, node_id),
        "provenance": {
            "source_refs": n.get("source_refs", []),
            "source_details": n.get("source_details", []),
            "source_claim_ids": n.get("source_claim_ids", []),
            "provenance": n.get("provenance", []),
            "dod_evidence": c.get("dod_evidence", [])
        },
        "canonical_identity": {
            "system": n.get("canonical_system"),
            "id": n.get("canonical_id"),
            "revision": n.get("canonical_revision"),
            "observed_at": n.get("observed_at"),
            "staleness_state": n.get("staleness_state")
        }
    }

def format_packet_markdown(packet_data: dict[str, Any]) -> str:
    """Format an implementation packet into rich GitHub-flavored Markdown for developer or agent prompts."""
    w = packet_data.get("work", {})
    node_id = w.get("id", "UNKNOWN")
    title = w.get("title", "")
    summary = w.get("summary", "")
    status = (w.get("completion") or {}).get("status", "NOT_DONE")
    priority = w.get("priority", "P1")
    horizon = w.get("horizon", "H1")
    cluster = w.get("cluster", "general")
    criticality = w.get("criticality", "MEDIUM")
    
    lines = [
        f"# Implementation Packet: `{node_id}`",
        "",
        f"**Title:** {title}  ",
        f"**Status:** `{status}` | **Priority:** `{priority}` | **Horizon:** `{horizon}` | **Cluster:** `{cluster}` | **Criticality:** `{criticality}`",
        "",
        "## Summary & Objective",
        summary or "No summary provided.",
        "",
        "## Definition of Done / Exit Criteria"
    ]
    
    exit_criteria = w.get("exit_criteria") or []
    if exit_criteria:
        for ec in exit_criteria:
            lines.append(f"- [ ] {ec}")
    else:
        lines.append("- [ ] Implementation complete and verified against test suite.")
        
    lines.extend([
        "",
        "## Feasibility & Readiness"
    ])
    feas = packet_data.get("feasibility", {})
    is_ready = feas.get("ready", False)
    badge = "READY" if is_ready else "BLOCKED"
    lines.append(f"- **State:** `{badge}`")
    if feas.get("reasons"):
        lines.append(f"- **Blocker Reasons:** {', '.join(feas['reasons'])}")
        
    prereqs = packet_data.get("prerequisites", [])
    lines.extend([
        "",
        "## Upstream Prerequisites"
    ])
    if prereqs:
        for p in prereqs:
            sat = "DONE" if p.get("satisfied") else p.get("completion", "NOT_DONE")
            lines.append(f"- `{p.get('id')}` (`{sat}`) — {p.get('title')} (via `{p.get('via')}`)")
    else:
        lines.append("_No upstream blocking prerequisites._")
        
    downstream = packet_data.get("downstream", [])
    lines.extend([
        "",
        "## Downstream Impact (Unlocks / Enables)"
    ])
    if downstream:
        for d in downstream:
            lines.append(f"- `{d.get('id')}` — {d.get('title')} (via `{d.get('via')}`)")
    else:
        lines.append("_No downstream dependents currently declared._")
        
    lines.extend([
        "",
        "## Provenance & Grounding"
    ])
    prov = packet_data.get("provenance", {})
    refs = prov.get("source_refs", [])
    if refs:
        lines.append(f"- **Source References:** {', '.join(map(str, refs))}")
    if prov.get("source_claim_ids"):
        lines.append(f"- **Source Claims:** {', '.join(map(str, prov['source_claim_ids']))}")
        
    return "\n".join(lines)
