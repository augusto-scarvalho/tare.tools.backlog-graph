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

    def test_ranked_next(self) -> None:
        next_items = ranked_next(self.sample_graph, limit=5)
        self.assertTrue(len(next_items) > 0)
        self.assertEqual(next_items[0]["id"], "TASK-02")

if __name__ == "__main__":
    unittest.main()
