from __future__ import annotations
import copy
import unittest
from pathlib import Path

from graph_backlog.core import WorkGraph
from graph_backlog.diff import semantic_diff, validate_change
from graph_backlog.ledger import GraphLedger
from graph_backlog.simulation import simulate_completions
from graph_backlog.jsonutil import load_json

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"

class DiffAndLedgerTests(unittest.TestCase):
    def test_semantic_diff_no_changes(self) -> None:
        data = load_json(FIXTURES / "sample-backlog.json")
        changes = semantic_diff(data, data)
        self.assertEqual(len(changes), 0)

    def test_semantic_diff_node_status_change(self) -> None:
        old = load_json(FIXTURES / "sample-backlog.json")
        new = copy.deepcopy(old)
        new["nodes"][1]["completion"]["status"] = "DONE"
        new["nodes"][1]["completion"]["dod_satisfied"] = True
        
        changes = semantic_diff(old, new)
        self.assertTrue(len(changes) > 0)
        
        vc = validate_change(old, new)
        self.assertEqual(vc["status"], "PASS")
        self.assertEqual(vc["change_count"], len(changes))

    def test_ledger_append_and_integrity(self) -> None:
        ledger = GraphLedger()
        ev1 = ledger.append_event("NODE_CREATED", "developer", {"id": "TASK-01", "title": "Setup"})
        ev2 = ledger.append_event("STATUS_UPDATED", "developer", {"id": "TASK-01", "status": "DONE"})
        
        self.assertEqual(len(ledger.events), 2)
        self.assertEqual(ev2["prev_hash"], ev1["event_hash"])
        
        integrity = ledger.verify_integrity()
        self.assertTrue(integrity["valid"])
        self.assertEqual(integrity["event_count"], 2)

    def test_simulation_overlay(self) -> None:
        graph = WorkGraph.from_file(FIXTURES / "sample-backlog.json")
        # In sample-backlog, TASK-02 is NOT_DONE, blocking TASK-03.
        # If we simulate completing TASK-02, TASK-03 should be newly unlocked!
        sim = simulate_completions(graph, ["TASK-02"])
        self.assertIn("TASK-03", sim["newly_unlocked_nodes"])

if __name__ == "__main__":
    unittest.main()
