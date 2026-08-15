from __future__ import annotations
import unittest
from pathlib import Path

from graph_backlog.core import WorkGraph
from graph_backlog.algorithms import (
    compute_frontier,
    find_cycles_scc,
    shortest_path,
    critical_path,
    readiness,
    unresolved_prereqs,
    upstream_dependencies,
    downstream_reach,
    ranked_next
)

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"

class AlgorithmsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_graph = WorkGraph.from_file(FIXTURES / "sample-backlog.json")

    def test_frontier_and_readiness(self) -> None:
        frontier = compute_frontier(self.sample_graph)
        frontier_ids = [n["id"] for n in frontier]
        self.assertIn("TASK-02", frontier_ids)
        self.assertNotIn("TASK-01", frontier_ids)  # TASK-01 is DONE
        self.assertNotIn("TASK-03", frontier_ids)  # TASK-03 is blocked by TASK-02

    def test_unresolved_prereqs(self) -> None:
        blockers = unresolved_prereqs(self.sample_graph, "TASK-03")
        self.assertEqual(len(blockers), 1)
        self.assertEqual(blockers[0]["id"], "TASK-02")
        self.assertEqual(blockers[0]["completion"], "NOT_DONE")

    def test_upstream_and_downstream(self) -> None:
        deps = upstream_dependencies(self.sample_graph, "TASK-03")
        dep_ids = [d["id"] for d in deps]
        self.assertIn("TASK-02", dep_ids)
        self.assertIn("TASK-01", dep_ids)

        downstream = downstream_reach(self.sample_graph, "TASK-01")
        down_ids = [d["id"] for d in downstream]
        self.assertIn("TASK-02", down_ids)
        self.assertIn("TASK-03", down_ids)

    def test_shortest_path(self) -> None:
        path = shortest_path(self.sample_graph, "TASK-01", "TASK-03")
        self.assertIsNotNone(path)
        self.assertEqual(len(path), 2)
        self.assertEqual(path[0]["from"], "TASK-01")
        self.assertEqual(path[0]["to"], "TASK-02")
        self.assertEqual(path[1]["from"], "TASK-02")
        self.assertEqual(path[1]["to"], "TASK-03")

    def test_critical_path(self) -> None:
        cp = critical_path(self.sample_graph)
        self.assertEqual(cp["status"], "PASS")
        self.assertEqual(cp["edge_length"], 2)

    def test_operational_readiness_profiles(self) -> None:
        node2 = self.sample_graph.by_id["TASK-02"]
        # Planning profile
        res_plan = readiness(self.sample_graph, node2, profile="planning")
        self.assertTrue(res_plan["ready"])

        # Operational profile with missing identity
        bad_node = dict(node2)
        bad_node["canonical_system"] = None
        res_op1 = readiness(self.sample_graph, bad_node, profile="operational")
        self.assertFalse(res_op1["ready"])
        self.assertIn("canonical_identity_missing", res_op1["reasons"])

        # Stale state
        stale_node = dict(node2)
        stale_node["staleness_state"] = "STALE"
        res_op2 = readiness(self.sample_graph, stale_node, profile="operational")
        self.assertFalse(res_op2["ready"])
        self.assertIn("canonical_revision_or_freshness_unproven", res_op2["reasons"])

        # Insufficient materialization scope
        scoped_node = dict(node2)
        scoped_node["readiness"] = {"required_materialization_scopes": ["prod_deploy"]}
        scoped_node["completion"] = {"materialization_scope": "local"}
        res_op3 = readiness(self.sample_graph, scoped_node, profile="operational")
        self.assertFalse(res_op3["ready"])
        self.assertIn("materialization_scope_insufficient", res_op3["reasons"])

        # Insufficient evidence grade
        grade_node = dict(node2)
        grade_node["readiness"] = {"minimum_evidence_grade": "A"}
        grade_node["completion"] = {"evidence_grade": "D"}
        res_op4 = readiness(self.sample_graph, grade_node, profile="operational")
        self.assertFalse(res_op4["ready"])
        self.assertIn("evidence_grade_insufficient", res_op4["reasons"])

    def test_ranked_next(self) -> None:
        next_items = ranked_next(self.sample_graph, limit=5)
        self.assertTrue(len(next_items) > 0)
        self.assertEqual(next_items[0]["id"], "TASK-02")

if __name__ == "__main__":
    unittest.main()
