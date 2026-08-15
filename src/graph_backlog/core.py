from __future__ import annotations
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator

from .jsonutil import UsageError, GraphInvalid, load_json, canonical_json, sha256_canonical

VALID_STATUSES = {"NOT_DONE", "PARTIAL", "DONE", "SUPERSEDED"}
VALID_STALENESS = {"FRESH", "STALE", "UNKNOWN", "NOT_APPLICABLE"}
EVIDENCE_ORDER = {None: -1, "": -1, "D": 0, "C": 1, "B": 2, "A": 3}

DEFAULT_POLICIES_DIR = Path(__file__).parent / "contracts" / "policies"
DEFAULT_SCHEMAS_DIR = Path(__file__).parent / "contracts" / "schemas"

def normalize_key(v: Any) -> str:
    """Normalize string keys for lookup (lower, kebab-cased)."""
    return re.sub(r"[-_\s]+", "-", str(v or "").strip().lower())

def load_default_policy() -> dict[str, Any]:
    policy_file = DEFAULT_POLICIES_DIR / "graph-ops-policy.json"
    if policy_file.exists():
        return load_json(policy_file)
    return {
        "graph_schema": "tare.tools/work-graph/0.5",
        "actionability": {"actionable_kinds": ["task", "spike", "work_item", "implementation", "ticket"]},
        "completion": {"default_hidden": ["DONE", "SUPERSEDED"]},
        "ranking": {
            "priority": {"P0": 100, "P1": 50, "P2": 20, "P3": 0},
            "horizon": {"H0": 30, "H1": 20, "H2": 10, "H3": 0},
            "criticality": {"CRITICAL": 50, "HIGH": 30, "MEDIUM": 10, "LOW": 0},
            "unlock_score_multiplier": 10.0,
            "partial_penalty": 5.0,
            "authority_penalty": 20.0
        }
    }

def load_default_taxonomy() -> dict[str, Any]:
    tax_file = DEFAULT_POLICIES_DIR / "relation-taxonomy.json"
    if tax_file.exists():
        return load_json(tax_file)
    return {
        "schema": "tare.tools/relation-taxonomy/0.1",
        "relations": {
            "UNLOCKS": {"dependency_effect": "prerequisite", "prerequisite_role": "source"},
            "DEPENDS_ON": {"dependency_effect": "prerequisite", "prerequisite_role": "target"},
            "ENABLES": {"dependency_effect": "prerequisite", "prerequisite_role": "source"},
            "BLOCKS": {"dependency_effect": "prerequisite", "prerequisite_role": "source"},
            "SUPERSEDED_BY": {"dependency_effect": "successor", "prerequisite_role": "target"},
            "RELATION_TO": {"dependency_effect": "informational", "prerequisite_role": "none"}
        }
    }

class WorkGraph:
    """Core in-memory representation of a DAG-based Work Graph backlog."""
    
    def __init__(
        self,
        raw: dict[str, Any],
        policy: dict[str, Any] | None = None,
        taxonomy: dict[str, Any] | None = None
    ) -> None:
        self.raw = raw
        self.policy = policy or load_default_policy()
        self.taxonomy = taxonomy or load_default_taxonomy()
        
        self.meta: dict[str, Any] = raw.get("meta", {})
        self.sources: dict[str, Any] = raw.get("sources", {})
        self.nodes: list[dict[str, Any]] = raw.get("nodes", [])
        self.edges: list[dict[str, Any]] = raw.get("edges", [])
        
        self.by_id: dict[str, dict[str, Any]] = {n["id"]: n for n in self.nodes if isinstance(n, dict) and "id" in n}
        
        # Adjacency maps
        self.in_edges: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.out_edges: dict[str, list[dict[str, Any]]] = defaultdict(list)
        
        # Blocking prerequisite maps: block_in[dependent] = list of (edge, prerequisite_id)
        # block_out[prerequisite] = list of (edge, dependent_id)
        self.block_in: dict[str, list[tuple[dict[str, Any], str]]] = defaultdict(list)
        self.block_out: dict[str, list[tuple[dict[str, Any], str]]] = defaultdict(list)
        
        for e in self.edges:
            if not isinstance(e, dict):
                continue
            src, dst = e.get("from"), e.get("to")
            rel_type = e.get("type", "")
            if src:
                self.out_edges[src].append(e)
            if dst:
                self.in_edges[dst].append(e)
            
            rs = self.relation_spec(rel_type)
            if e.get("semantic", True) and rs.get("dependency_effect") == "prerequisite":
                role = rs.get("prerequisite_role", "source")
                pre = src if role == "source" else dst
                dep = dst if pre == src else src
                if pre and dep:
                    self.block_in[dep].append((e, pre))
                    self.block_out[pre].append((e, dep))
        
        self.hidden_statuses = set(self.policy.get("completion", {}).get("default_hidden", ["DONE", "SUPERSEDED"]))
        self.actionable_kinds = set(self.policy.get("actionability", {}).get("actionable_kinds", []))

    @classmethod
    def from_file(cls, path: str | Path, policy_path: str | Path | None = None, taxonomy_path: str | Path | None = None) -> WorkGraph:
        raw = load_json(path)
        policy = load_json(policy_path) if policy_path else None
        taxonomy = load_json(taxonomy_path) if taxonomy_path else None
        return cls(raw, policy, taxonomy)

    def relation_spec(self, rel_type: str) -> dict[str, Any]:
        return self.taxonomy.get("relations", {}).get(rel_type, {})

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        return self.by_id.get(node_id)

    def status_of(self, node_or_id: str | dict[str, Any]) -> str:
        n = node_or_id if isinstance(node_or_id, dict) else self.by_id.get(node_or_id, {})
        return (n.get("completion") or {}).get("status", "NOT_DONE")

    def successors_of(self, node_id: str) -> list[str]:
        return [
            e["to"] for e in self.out_edges.get(node_id, [])
            if e.get("semantic", True) and e.get("type") == "SUPERSEDED_BY" and "to" in e
        ]

    def is_satisfied(self, node_id: str, seen: set[str] | None = None) -> bool:
        """Evaluate whether a node is satisfied (completed with DoD, or superseded by satisfied successors)."""
        n = self.by_id.get(node_id)
        if not n:
            return False
        st = self.status_of(n)
        if st == "DONE":
            return bool((n.get("completion") or {}).get("dod_satisfied"))
        if st == "SUPERSEDED":
            seen = set(seen or ())
            if node_id in seen:
                return False
            seen.add(node_id)
            succ = self.successors_of(node_id)
            return bool(succ) and all(self.is_satisfied(x, seen) for x in succ)
        return False

    def prerequisite_satisfies(self, prereq_id: str, edge: dict[str, Any]) -> bool:
        """Check whether a prerequisite node satisfies all criteria demanded by the edge requirements."""
        if not self.is_satisfied(prereq_id):
            return False
        n = self.by_id.get(prereq_id, {})
        c = n.get("completion") or {}
        req = edge.get("requirements") or {}
        rs = self.relation_spec(edge.get("type", ""))
        
        accepted = rs.get("accepted_terminal_status") or []
        st = self.status_of(n)
        if accepted and st not in accepted and st != "SUPERSEDED":
            return False
        
        scope = req.get("materialization_scope")
        if scope:
            scopes = scope if isinstance(scope, list) else [scope]
            if c.get("materialization_scope") not in scopes:
                return False
        
        grade = req.get("minimum_evidence_grade")
        if grade and EVIDENCE_ORDER.get(c.get("evidence_grade"), -1) < EVIDENCE_ORDER.get(grade, 99):
            return False
        
        rev = req.get("canonical_revision")
        if rev and n.get("canonical_revision") != rev:
            return False
        
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": self.meta,
            "sources": self.sources,
            "nodes": self.nodes,
            "edges": self.edges
        }

    def canonical_hash(self) -> str:
        return sha256_canonical(self.to_dict())
