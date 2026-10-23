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
    def test_reconcile_exposes_identity_and_preserves_closed_history(self) -> None:
        import copy
        nodes = []
        for status in ("NOT_DONE", "PARTIAL", "DONE", "SUPERSEDED"):
            nodes.append({"id": status, "kind": "task", "completion": {"status": status},
                          "canonical_system": "owner", "canonical_id": "C-" + status,
                          "canonical_revision": "r7", "staleness_state": "STALE",
                          "observed_at": "2026-01-01T00:00:00Z", "projection_run_id": "p1"})
        raw = {"nodes": nodes, "sources": {}, "edges": []}
        before = copy.deepcopy(raw)
        report = reconcile(WorkGraph(raw))
        self.assertEqual(raw, before)
        self.assertEqual(report, reconcile(WorkGraph(raw)))
        self.assertEqual(report["status"], "SHADOW_ONLY")
        self.assertEqual(report["authority"], "NONE")
        self.assertEqual(report["execution_verification"], "NOT_PERFORMED")
        self.assertEqual({r["id"] for r in report["operational_divergences"]}, {"NOT_DONE", "PARTIAL"})
        self.assertEqual(len(report["rows"]), 4)
        for row in report["rows"]:
            self.assertEqual(row["canonical_id"], "C-" + row["id"])
            self.assertEqual(row["canonical_revision"], "r7")
            self.assertEqual(row["canonical_system"], "owner")
            self.assertEqual(row["observed_at"], nodes[0]["observed_at"])
            self.assertEqual(row["projection_run_id"], "p1")
            self.assertFalse(row["operational_ready"])
            self.assertIn("canonical_revision_or_freshness_unproven", row["operational"]["reasons"])
        self.assertTrue(next(r for r in report["rows"] if r["id"] == "NOT_DONE")["planning_ready"])

    def test_reconcile_missing_and_fresh_identity(self) -> None:
        node = {"id": "n", "kind": "task", "staleness_state": "UNKNOWN"}
        graph = WorkGraph({"nodes": [node], "edges": []})
        row = reconcile(graph)["rows"][0]
        self.assertIsNone(row["canonical_revision"])
        self.assertFalse(row["canonical_identity_complete"])
        self.assertIn("canonical_identity_missing", row["operational"]["reasons"])
        node.update(canonical_system="owner", canonical_id="n", canonical_revision="1", staleness_state="FRESH")
        report = reconcile(graph)
        self.assertTrue(report["rows"][0]["operational_ready"])
        self.assertEqual(report["operational_divergences"], [])
        self.assertEqual(report["execution_verification"], "NOT_PERFORMED")

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
        self.assertEqual(ev["status"], "FAIL")
        self.assertIn("COMPLETION_DOD_EVIDENCE_REQUIRED", {i["issue"] for i in ev["issues"]})
        
        doc = doctor_check(graph)
        self.assertEqual(doc["validation"], "PASS")

if __name__ == "__main__":
    unittest.main()
