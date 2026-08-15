from __future__ import annotations
import unittest
from pathlib import Path

from graph_backlog.core import WorkGraph
from graph_backlog.validation import (
    validate_work_graph,
    structural_errors,
    verify_evidence,
    reconcile,
    doctor_check
)
from graph_backlog.jsonutil import load_json

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"

class ValidationTests(unittest.TestCase):
    def test_structural_errors_on_empty(self) -> None:
        errs = structural_errors({})
        self.assertTrue(len(errs) > 0)

    def test_valid_graphs_pass(self) -> None:
        for fname in ("sample-backlog.json", "work-graph-v0.5.json"):
            data = load_json(FIXTURES / fname)
            res = validate_work_graph(data)
            self.assertEqual(res["status"], "PASS", f"Failed for {fname}: {res.get('errors')}")

    def test_negative_dangling_edge(self) -> None:
        data = load_json(FIXTURES / "negative-dangling-edge.json")
        res = validate_work_graph(data)
        self.assertEqual(res["status"], "FAIL")
        codes = [e["code"] for e in res["errors"]]
        self.assertTrue("EDGE_SOURCE" in codes or "EDGE_TARGET" in codes)

    def test_negative_invalid_status(self) -> None:
        data = load_json(FIXTURES / "negative-invalid-status.json")
        res = validate_work_graph(data)
        self.assertEqual(res["status"], "FAIL")
        codes = [e["code"] for e in res["errors"]]
        self.assertIn("COMPLETION_STATUS", codes)

    def test_doctor_and_evidence(self) -> None:
        graph = WorkGraph.from_file(FIXTURES / "sample-backlog.json")
        ev = verify_evidence(graph)
        self.assertIn(ev["status"], ("PASS", "PASS_WITH_GAPS"))
        
        doc = doctor_check(graph)
        self.assertEqual(doc["validation"], "PASS")

if __name__ == "__main__":
    unittest.main()
