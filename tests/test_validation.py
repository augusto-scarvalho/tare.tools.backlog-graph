from __future__ import annotations
import subprocess
import sys
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
GRAPH_OPS = ROOT / "graph_ops.py"


def _codes(fixture: str) -> list[str]:
    res = validate_work_graph(load_json(FIXTURES / fixture))
    return [e["code"] for e in res["errors"]]


def _cli_exit(graph_path: Path) -> int:
    return subprocess.run([sys.executable, str(GRAPH_OPS), "--graph", str(graph_path),
                           "validate"], capture_output=True, text=True).returncode

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

    # -- TRAIN-11 falsifiers (FAL-01 .. FAL-07) --------------------------------

    def test_fal01_self_loop_named_code(self) -> None:
        codes = _codes("negative-self-loop.json")
        self.assertIn("SELF_LOOP", codes)

    def test_fal02_invalid_completion_enum(self) -> None:
        codes = _codes("negative-invalid-status.json")
        self.assertIn("COMPLETION_STATUS", codes)

    def test_fal03_missing_id(self) -> None:
        raw = {"meta": {}, "sources": {}, "nodes": [{"title": "no id here"}], "edges": []}
        codes = [e["code"] for e in structural_errors(raw)]
        self.assertIn("MISSING_ID", codes)

    def test_fal04_invalid_source_ref(self) -> None:
        raw = {"meta": {}, "sources": {"s1": {"kind": "doc", "title": "x",
                                              "recoverability": "UNRESOLVED_REFERENCE"}},
               "nodes": [{"id": "n1", "source_refs": ["ghost-ref"]}], "edges": []}
        codes = [e["code"] for e in structural_errors(raw)]
        self.assertIn("INVALID_SOURCE_REF", codes)

    def test_fal_unknown_relation_type(self) -> None:
        self.assertIn("RELATION_TAXONOMY", _codes("negative-unknown-relation.json"))

    def test_fal05_cli_exit_0_valid(self) -> None:
        self.assertEqual(_cli_exit(FIXTURES / "work-graph-v0.5.json"), 0)

    def test_fal06_cli_exit_1_invalid(self) -> None:
        self.assertEqual(_cli_exit(FIXTURES / "negative-self-loop.json"), 1)

    def test_fal07_cli_exit_2_malformed(self) -> None:
        self.assertEqual(_cli_exit(FIXTURES / "negative-malformed.json"), 2)
        self.assertEqual(_cli_exit(FIXTURES / "does-not-exist.json"), 2)

    def test_doctor_and_evidence(self) -> None:
        graph = WorkGraph.from_file(FIXTURES / "sample-backlog.json")
        ev = verify_evidence(graph)
        self.assertIn(ev["status"], ("PASS", "PASS_WITH_GAPS"))
        
        doc = doctor_check(graph)
        self.assertEqual(doc["validation"], "PASS")

if __name__ == "__main__":
    unittest.main()
