"""Golden relation-taxonomy + frontier-readiness semantics (TRAIN-29).

Proves the three exit criteria of graph-audit-frontier-semantics:
  1. A golden blocking test for every prerequisite relation in the taxonomy.
  2. source-truth-p0-first-batch stays blocked while exact-byte acquisition
     is incomplete (canonical work-graph.json integration).
  3. The planning frontier is never presented as Authority / execution
     eligibility (immutable non-authority invariant on every payload).

All in-memory; zero disk mutation (FAL-05). The optional canonical integration
test reads only ``BACKLOG_GRAPH_CANONICAL_GRAPH``. It never walks above this
repository and accidentally turns a parent checkout into fixture authority.
"""
from __future__ import annotations
import os
import unittest
from pathlib import Path
from typing import Any

from graph_backlog.core import WorkGraph, load_default_taxonomy, normalize_key
from graph_backlog.algorithms import compute_frontier, readiness, ranked_next, unresolved_prereqs

# Prerequisite relations that MUST block their dependent (prerequisite_role=source: A -> B).
PREREQUISITE_RELATIONS = [
    "BLOCKS",
    "BLOCKS_STRONGER_AUTOMATION",
    "DEPENDS_ON",
    "ENABLES",
    "REQUIRES_AUDIT",
    "UNBLOCKS",
    "UNLOCKS",
]
# Relations that must NOT block.
NON_BLOCKING_RELATIONS = ["INFORMS", "EVIDENCE_FOR", "CAN_RUN_PARALLEL_WITH"]


def _node(node_id: str, status: str = "NOT_DONE", dod: bool = False) -> dict[str, Any]:
    return {
        "id": node_id,
        "title": node_id,
        "kind": "task",
        "staleness_state": "FRESH",
        "completion": {"status": status, "dod_satisfied": dod, "evidence_grade": "A"},
    }


def _two_node_graph(rel_type: str, a_status: str, a_dod: bool = False) -> WorkGraph:
    """Minimal A --[rel_type]--> B graph; A is the prerequisite, B the dependent."""
    raw = {
        "meta": {},
        "nodes": [_node("A", a_status, a_dod), _node("B")],
        "edges": [{"from": "A", "to": "B", "type": rel_type, "semantic": True}],
    }
    return WorkGraph(raw)


class BlockingRelationGoldenTests(unittest.TestCase):
    def test_normalize_key_preserves_words_and_normalizes_separators(self) -> None:
        self.assertEqual(normalize_key(" Critical_Path "), "critical-path")
        self.assertEqual(normalize_key(None), "")

    def test_missing_semantic_flag_defaults_to_blocking(self) -> None:
        raw = {
            "meta": {},
            "nodes": [_node("A", "NOT_DONE"), _node("B")],
            "edges": [{"from": "A", "to": "B", "type": "BLOCKS"}],
        }
        graph = WorkGraph(raw)

        self.assertFalse(readiness(graph, graph.by_id["B"])["ready"])

    def test_every_prerequisite_relation_blocks_then_unblocks(self) -> None:
        for rel in PREREQUISITE_RELATIONS:
            with self.subTest(relation=rel):
                # A incomplete -> B blocked, not on frontier.
                g = _two_node_graph(rel, "NOT_DONE")
                rd = readiness(g, g.by_id["B"])
                self.assertFalse(rd["ready"], f"{rel}: B should be blocked")
                self.assertIn("unresolved_prerequisites", rd["reasons"])
                self.assertEqual([b["id"] for b in rd["unresolved_prerequisites"]], ["A"])
                self.assertEqual(rd["unresolved_prerequisites"][0]["edge_type"], rel)
                self.assertNotIn("B", [n["id"] for n in compute_frontier(g)])

                # A completed with DoD -> B enters the frontier.
                g2 = _two_node_graph(rel, "DONE", a_dod=True)
                self.assertTrue(readiness(g2, g2.by_id["B"])["ready"], f"{rel}: B should unblock")
                self.assertIn("B", [n["id"] for n in compute_frontier(g2)])

    def test_done_without_dod_still_blocks(self) -> None:
        # Falsifier: DONE but dod_satisfied=false must NOT satisfy the prerequisite.
        g = _two_node_graph("BLOCKS", "DONE", a_dod=False)
        self.assertFalse(readiness(g, g.by_id["B"])["ready"])

    def test_non_blocking_relations_do_not_block(self) -> None:
        for rel in NON_BLOCKING_RELATIONS:
            with self.subTest(relation=rel):
                g = _two_node_graph(rel, "NOT_DONE")
                self.assertTrue(readiness(g, g.by_id["B"])["ready"], f"{rel} must not block")
                self.assertIn("B", [n["id"] for n in compute_frontier(g)])
                self.assertFalse(g.block_in, f"{rel} must not create reverse blockers")
                self.assertFalse(g.block_out, f"{rel} must not create reverse blockers")

    def test_taxonomy_declares_all_prerequisite_relations(self) -> None:
        # Falsifier: guards against silent taxonomy drift dropping a blocking type.
        rels = load_default_taxonomy()["relations"]
        for rel in PREREQUISITE_RELATIONS:
            self.assertEqual(rels[rel]["dependency_effect"], "prerequisite", rel)
            self.assertEqual(rels[rel]["prerequisite_role"], "source", rel)


class PrerequisiteRequirementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = _two_node_graph("BLOCKS", "DONE", a_dod=True)
        self.prerequisite = self.graph.by_id["A"]

    @staticmethod
    def _edge(**requirements: Any) -> dict[str, Any]:
        return {"type": "BLOCKS", "requirements": requirements}

    def test_materialization_scope_must_match(self) -> None:
        self.prerequisite["completion"]["materialization_scope"] = "local"

        self.assertTrue(
            self.graph.prerequisite_satisfies("A", self._edge(materialization_scope="local"))
        )
        self.assertFalse(
            self.graph.prerequisite_satisfies("A", self._edge(materialization_scope="production"))
        )

    def test_minimum_evidence_grade_accepts_boundary_and_rejects_lower_grade(self) -> None:
        self.prerequisite["completion"]["evidence_grade"] = "B"

        self.assertTrue(
            self.graph.prerequisite_satisfies("A", self._edge(minimum_evidence_grade="B"))
        )
        self.assertFalse(
            self.graph.prerequisite_satisfies("A", self._edge(minimum_evidence_grade="A"))
        )

    def test_canonical_revision_must_match(self) -> None:
        self.prerequisite["canonical_revision"] = "revision-1"

        self.assertTrue(
            self.graph.prerequisite_satisfies("A", self._edge(canonical_revision="revision-1"))
        )
        self.assertFalse(
            self.graph.prerequisite_satisfies("A", self._edge(canonical_revision="revision-2"))
        )


class SupersededResolutionTests(unittest.TestCase):
    def _graph(self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> WorkGraph:
        return WorkGraph({"meta": {}, "nodes": nodes, "edges": edges})

    def test_superseded_requires_completed_successor(self) -> None:
        # A SUPERSEDED by B; B not done -> A NOT satisfied -> dependent C blocked.
        g = self._graph(
            [_node("A", "SUPERSEDED"), _node("B", "NOT_DONE"), _node("C")],
            [
                {"from": "A", "to": "B", "type": "SUPERSEDED_BY", "semantic": True},
                {"from": "A", "to": "C", "type": "BLOCKS", "semantic": True},
            ],
        )
        self.assertFalse(g.is_satisfied("A"))
        self.assertFalse(readiness(g, g.by_id["C"])["ready"])

        # Once B completes with DoD, A is transitively satisfied and C unblocks.
        g.by_id["B"]["completion"] = {"status": "DONE", "dod_satisfied": True}
        self.assertTrue(g.is_satisfied("A"))
        self.assertTrue(readiness(g, g.by_id["C"])["ready"])

    def test_superseded_with_no_successor_fails_closed(self) -> None:
        g = self._graph([_node("A", "SUPERSEDED")], [])
        self.assertFalse(g.is_satisfied("A"))

    def test_unknown_node_is_not_satisfied(self) -> None:
        g = self._graph([], [])
        self.assertFalse(g.is_satisfied("missing"))

    def test_supersession_defaults_to_semantic(self) -> None:
        g = self._graph(
            [_node("A", "SUPERSEDED"), _node("B", "DONE", dod=True)],
            [{"from": "A", "to": "B", "type": "SUPERSEDED_BY"}],
        )
        self.assertTrue(g.is_satisfied("A"))

    def test_superseded_cycle_fails_closed(self) -> None:
        g = self._graph(
            [_node("A", "SUPERSEDED"), _node("B", "SUPERSEDED")],
            [
                {"from": "A", "to": "B", "type": "SUPERSEDED_BY", "semantic": True},
                {"from": "B", "to": "A", "type": "SUPERSEDED_BY", "semantic": True},
            ],
        )
        self.assertFalse(g.is_satisfied("A"))
        self.assertFalse(g.is_satisfied("B"))


class NonAuthorityInvariantTests(unittest.TestCase):
    def test_readiness_payload_disclaims_authority(self) -> None:
        g = _two_node_graph("BLOCKS", "DONE", a_dod=True)
        rd = readiness(g, g.by_id["B"])
        self.assertIs(rd["authority_granted_by_graph"], False)
        self.assertIn("projection feasibility only", rd["note"])

    def test_ranked_next_disclaims_authority(self) -> None:
        g = _two_node_graph("BLOCKS", "DONE", a_dod=True)
        rows = ranked_next(g)
        self.assertTrue(rows)
        self.assertTrue(all(r["authority_granted_by_graph"] is False for r in rows))


def _find_canonical_graph() -> Path | None:
    configured = os.environ.get("BACKLOG_GRAPH_CANONICAL_GRAPH")
    if not configured:
        return None
    candidate = Path(configured).expanduser().resolve()
    if not candidate.is_file():
        raise RuntimeError(
            "BACKLOG_GRAPH_CANONICAL_GRAPH must identify an existing regular file"
        )
    return candidate


class CanonicalBlockerIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        path = _find_canonical_graph()
        if path is None:
            self.skipTest("BACKLOG_GRAPH_CANONICAL_GRAPH not configured")
        self.graph = WorkGraph.from_file(path)

    def test_p0_first_batch_blocked_by_exact_byte_acquisition(self) -> None:
        node = self.graph.by_id.get("source-truth-p0-first-batch")
        self.assertIsNotNone(node, "source-truth-p0-first-batch missing from canonical graph")

        rd = readiness(self.graph, node)
        self.assertFalse(rd["ready"])
        self.assertIn("unresolved_prerequisites", rd["reasons"])

        blockers = {b["id"]: b for b in rd["unresolved_prerequisites"]}
        self.assertIn("source-truth-exact-byte-acquisition", blockers)
        self.assertEqual(blockers["source-truth-exact-byte-acquisition"]["edge_type"], "BLOCKS")

        # Same result via the shared unresolved_prereqs helper (single source of truth).
        self.assertIn(
            "source-truth-exact-byte-acquisition",
            [b["id"] for b in unresolved_prereqs(self.graph, "source-truth-p0-first-batch")],
        )

    def test_p0_first_batch_absent_from_planning_frontier(self) -> None:
        frontier_ids = [n["id"] for n in compute_frontier(self.graph, profile="planning")]
        self.assertNotIn("source-truth-p0-first-batch", frontier_ids)


if __name__ == "__main__":
    unittest.main()
