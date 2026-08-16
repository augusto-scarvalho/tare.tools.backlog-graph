from __future__ import annotations
import json
import unittest
from pathlib import Path

from graph_backlog.validation import diagnose_graph
from graph_backlog.core import WorkGraph

class DiagnosticsAndCycleBreakerTests(unittest.TestCase):
    def test_diagnose_graph_clean(self):
        sample_path = Path(__file__).parent.parent / "fixtures" / "work-graph-v0.5.json"
        if not sample_path.exists():
            return
        data = json.loads(sample_path.read_text(encoding="utf-8"))
        res = diagnose_graph(data)
        self.assertIn("summary", res)
        self.assertIn("health_status", res["summary"])
        self.assertIn("total_nodes", res["summary"])

    def test_cycle_breaker_execution(self):
        from scripts.cycle_breaker import break_graph_cycles
        sample_path = Path(__file__).parent.parent / "fixtures" / "work-graph-v0.5.json"
        if not sample_path.exists():
            return
        res = break_graph_cycles(str(sample_path), save=False)
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(res["remaining_cycles_count"], 0)

if __name__ == "__main__":
    unittest.main()
