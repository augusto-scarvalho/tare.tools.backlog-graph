"""Bounded, read-only work grounding for managed agent execution."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .algorithms import downstream_reach, readiness
from .core import WorkGraph, load_default_policy, load_default_taxonomy
from .jsonutil import canonical_json, load_json, sha256_canonical
from .validation import validate_work_graph


MAX_GRAPH_BYTES = 32 * 1024 * 1024
MIN_OUTPUT_BYTES = 1_024
MAX_OUTPUT_BYTES = 65_536
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class WorkGroundingReport:
    schema: str
    status: str
    reason_codes: tuple[str, ...]
    authority: str
    work_id: str
    profile: str
    graph_sha256: str
    graph_revision: str
    work_item_sha256: str
    execution_scope_sha256: str
    work: dict[str, Any]
    feasibility: dict[str, Any]
    downstream: tuple[dict[str, Any], ...]
    provenance: dict[str, Any]
    omitted_downstream: int
    byte_count: int

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["reason_codes"] = list(self.reason_codes)
        data["downstream"] = list(self.downstream)
        return data


def ground_work_item(
    graph_path: str | Path,
    work_id: str,
    *,
    profile: str = "operational",
    max_bytes: int = 8_192,
    expected_scope_sha256: str | None = None,
    policy_path: str | Path | None = None,
    taxonomy_path: str | Path | None = None,
) -> WorkGroundingReport:
    """Project one work item and its execution fence from an explicit graph."""

    node_id = _bounded_text(work_id, "work_id", 256)
    if profile not in {"planning", "operational"}:
        raise ValueError("profile must be planning or operational")
    if not MIN_OUTPUT_BYTES <= max_bytes <= MAX_OUTPUT_BYTES:
        raise ValueError(
            f"max_bytes must be between {MIN_OUTPUT_BYTES} and {MAX_OUTPUT_BYTES}"
        )
    if expected_scope_sha256 is not None and not _SHA256.fullmatch(
        expected_scope_sha256
    ):
        raise ValueError("expected_scope_sha256 must be a lowercase SHA-256 digest")

    path = Path(graph_path).expanduser().resolve()
    try:
        if path.stat().st_size > MAX_GRAPH_BYTES:
            return _empty_report("SOURCE_INVALID", "GRAPH_TOO_LARGE", node_id, profile)
        raw_bytes = path.read_bytes()
    except OSError:
        return _empty_report("UNAVAILABLE", "GRAPH_UNAVAILABLE", node_id, profile)

    graph_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    try:
        raw = json.loads(raw_bytes.decode("utf-8-sig"))
        policy = load_json(policy_path) if policy_path else load_default_policy()
        taxonomy = load_json(taxonomy_path) if taxonomy_path else load_default_taxonomy()
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError, OSError):
        return _empty_report(
            "SOURCE_INVALID",
            "INVALID_GRAPH_CONTRACT",
            node_id,
            profile,
            graph_sha256=graph_sha256,
        )

    validation = validate_work_graph(raw, policy, taxonomy)
    if validation.get("status") != "PASS":
        return _empty_report(
            "SOURCE_INVALID",
            "INVALID_GRAPH_CONTRACT",
            node_id,
            profile,
            graph_sha256=graph_sha256,
        )

    graph = WorkGraph(raw, policy, taxonomy)
    node = graph.get_node(node_id)
    if node is None:
        return _empty_report(
            "NOT_FOUND",
            "WORK_ITEM_NOT_FOUND",
            node_id,
            profile,
            graph_sha256=graph_sha256,
            graph_revision=_graph_revision(graph),
        )

    feasibility = readiness(graph, node, profile)
    exit_criteria = tuple(
        _bounded_text(item, "exit criterion", 2_048)
        for item in _bounded_string_list(node.get("exit_criteria"), "exit_criteria", 64)
    )
    execution_scope_sha256 = _execution_scope_sha256(graph, node)
    reason_codes: list[str] = []
    status = "READY"
    if (
        expected_scope_sha256 is not None
        and expected_scope_sha256 != execution_scope_sha256
    ):
        status = "DRIFT"
        reason_codes.append("EXECUTION_SCOPE_CHANGED")
    elif node.get("staleness_state") != "FRESH":
        status = "STALE"
        reason_codes.append("WORK_ITEM_NOT_FRESH")
    elif not exit_criteria:
        status = "UNBOUNDED_WORK"
        reason_codes.append("EXIT_CRITERIA_MISSING")
    elif not feasibility.get("ready"):
        status = "BLOCKED"
        reason_codes.extend(str(item) for item in feasibility.get("reasons", []))
    else:
        reason_codes.append("READY_FOR_MANAGED_EXECUTION")

    work = {
        "id": node_id,
        "title": _bounded_text(node.get("title"), "title", 2_048),
        "summary": _optional_bounded_text(node.get("summary"), "summary", 8_192),
        "kind": _optional_bounded_text(node.get("kind"), "kind", 256),
        "cluster": _optional_bounded_text(node.get("cluster"), "cluster", 512),
        "priority": _optional_bounded_text(node.get("priority"), "priority", 64),
        "horizon": _optional_bounded_text(node.get("horizon"), "horizon", 64),
        "criticality": _optional_bounded_text(
            node.get("criticality"), "criticality", 64
        ),
        "bounded_contexts": list(
            _bounded_string_list(node.get("bounded_contexts"), "bounded_contexts", 64)
        ),
        "target_repositories": list(
            _bounded_string_list(
                node.get("target_repositories"), "target_repositories", 16
            )
        ),
        "grounding_refs": list(
            _bounded_string_list(node.get("grounding_refs"), "grounding_refs", 128)
        ),
        "target_paths": list(
            _bounded_string_list(node.get("target_paths"), "target_paths", 256)
        ),
        "target_symbols": list(
            _bounded_string_list(node.get("target_symbols"), "target_symbols", 256)
        ),
        "exit_criteria": list(exit_criteria),
        "evidence_required": list(
            _bounded_string_list(node.get("evidence_required"), "evidence_required", 64)
        ),
        "canonical_system": node.get("canonical_system"),
        "canonical_id": node.get("canonical_id"),
        "canonical_revision": node.get("canonical_revision"),
        "staleness_state": node.get("staleness_state"),
    }
    compact_feasibility = {
        "ready": bool(feasibility.get("ready")),
        "reasons": list(feasibility.get("reasons", [])),
        "unresolved_prerequisites": list(
            feasibility.get("unresolved_prerequisites", [])
        ),
    }
    provenance = {
        "source_refs": list(
            _bounded_string_list(node.get("source_refs"), "source_refs", 128)
        ),
        "source_claim_ids": list(
            _bounded_string_list(
                node.get("source_claim_ids"), "source_claim_ids", 128
            )
        ),
    }
    downstream = tuple(_narrow_downstream(item) for item in downstream_reach(graph, node_id))

    report = _finalize(
        status=status,
        reason_codes=tuple(reason_codes),
        work_id=node_id,
        profile=profile,
        graph_sha256=graph_sha256,
        graph_revision=_graph_revision(graph),
        work_item_sha256=sha256_canonical(node),
        execution_scope_sha256=execution_scope_sha256,
        work=work,
        feasibility=compact_feasibility,
        downstream=downstream,
        provenance=provenance,
        omitted_downstream=0,
    )
    if report.byte_count <= max_bytes:
        return report

    included = list(downstream)
    while included:
        included.pop()
        candidate = _finalize(
            status=status,
            reason_codes=tuple(reason_codes),
            work_id=node_id,
            profile=profile,
            graph_sha256=graph_sha256,
            graph_revision=_graph_revision(graph),
            work_item_sha256=sha256_canonical(node),
            execution_scope_sha256=execution_scope_sha256,
            work=work,
            feasibility=compact_feasibility,
            downstream=tuple(included),
            provenance=provenance,
            omitted_downstream=len(downstream) - len(included),
        )
        if candidate.byte_count <= max_bytes:
            return candidate

    return _empty_report(
        "WORK_CONTEXT_TOO_LARGE",
        "MANDATORY_CONTEXT_EXCEEDS_BUDGET",
        node_id,
        profile,
        graph_sha256=graph_sha256,
        graph_revision=_graph_revision(graph),
        work_item_sha256=sha256_canonical(node),
        execution_scope_sha256=execution_scope_sha256,
    )


def encode_work_grounding(report: WorkGroundingReport) -> bytes:
    return json.dumps(
        report.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _execution_scope_sha256(graph: WorkGraph, node: dict[str, Any]) -> str:
    node_id = str(node["id"])
    incident_edges = [
        edge
        for edge in graph.edges
        if edge.get("from") == node_id or edge.get("to") == node_id
    ]
    prerequisite_ids = sorted(
        {prerequisite_id for _edge, prerequisite_id in graph.block_in.get(node_id, [])}
    )
    sources = {
        source_ref: graph.sources.get(source_ref)
        for source_ref in sorted(node.get("source_refs") or [])
    }
    scope = {
        "work": node,
        "incident_edges": sorted(
            incident_edges,
            key=lambda edge: (
                str(edge.get("from", "")),
                str(edge.get("to", "")),
                str(edge.get("type", "")),
            ),
        ),
        "prerequisites": [graph.by_id[item] for item in prerequisite_ids],
        "sources": sources,
    }
    return hashlib.sha256(canonical_json(scope).encode("utf-8")).hexdigest()


def _graph_revision(graph: WorkGraph) -> str:
    value = graph.raw.get("revision") or graph.meta.get("projection_run_id")
    return str(value or graph.canonical_hash())


def _narrow_downstream(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _bounded_text(item.get("id"), "downstream id", 256),
        "title": _optional_bounded_text(item.get("title"), "downstream title", 2_048),
        "via": _optional_bounded_text(item.get("via"), "downstream relation", 128),
    }


def _bounded_string_list(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f"{field} must be a bounded string list")
    return tuple(_bounded_text(item, field, 2_048) for item in value)


def _bounded_text(value: Any, field: str, max_bytes: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    normalized = value.strip()
    if len(normalized.encode("utf-8")) > max_bytes:
        raise ValueError(f"{field} exceeds {max_bytes} bytes")
    return normalized


def _optional_bounded_text(value: Any, field: str, max_bytes: int) -> str:
    if value in (None, ""):
        return ""
    return _bounded_text(value, field, max_bytes)


def _empty_report(
    status: str,
    reason_code: str,
    work_id: str,
    profile: str,
    *,
    graph_sha256: str = "",
    graph_revision: str = "",
    work_item_sha256: str = "",
    execution_scope_sha256: str = "",
) -> WorkGroundingReport:
    return _finalize(
        status=status,
        reason_codes=(reason_code,),
        work_id=work_id,
        profile=profile,
        graph_sha256=graph_sha256,
        graph_revision=graph_revision,
        work_item_sha256=work_item_sha256,
        execution_scope_sha256=execution_scope_sha256,
        work={},
        feasibility={},
        downstream=(),
        provenance={},
        omitted_downstream=0,
    )


def _finalize(
    *,
    status: str,
    reason_codes: tuple[str, ...],
    work_id: str,
    profile: str,
    graph_sha256: str,
    graph_revision: str,
    work_item_sha256: str,
    execution_scope_sha256: str,
    work: dict[str, Any],
    feasibility: dict[str, Any],
    downstream: tuple[dict[str, Any], ...],
    provenance: dict[str, Any],
    omitted_downstream: int,
) -> WorkGroundingReport:
    byte_count = 0
    for _ in range(8):
        report = WorkGroundingReport(
            schema="tare.tools/work-grounding/1",
            status=status,
            reason_codes=reason_codes,
            authority="NONE / READ_ONLY PROJECTION",
            work_id=work_id,
            profile=profile,
            graph_sha256=graph_sha256,
            graph_revision=graph_revision,
            work_item_sha256=work_item_sha256,
            execution_scope_sha256=execution_scope_sha256,
            work=work,
            feasibility=feasibility,
            downstream=downstream,
            provenance=provenance,
            omitted_downstream=omitted_downstream,
            byte_count=byte_count,
        )
        measured = len(encode_work_grounding(report))
        if measured == byte_count:
            return report
        byte_count = measured
    raise RuntimeError("work grounding byte_count did not converge")
