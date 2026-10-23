from __future__ import annotations
import tempfile
import contextlib
import copy
import io
import json
import unittest
from pathlib import Path

from graph_backlog.core import WorkGraph
from graph_backlog.cli import main
from graph_backlog.packet import generate_packet, format_packet_markdown

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"

class CliAndPacketTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph_file = str(FIXTURES / "sample-backlog.json")

    def test_cli_in_process_commands(self) -> None:
        # validate
        ret = main(["--graph", self.graph_file, "validate"])
        self.assertEqual(ret, 0)

        # The legacy fixture remains structurally valid but its old A closure
        # has no explicit grade reason or DoD references.
        ret = main(["--graph", self.graph_file, "doctor"])
        self.assertEqual(ret, 1)

        # summary
        ret = main(["--graph", self.graph_file, "summary"])
        self.assertEqual(ret, 0)

        # frontier
        ret = main(["--graph", self.graph_file, "frontier"])
        self.assertEqual(ret, 0)

        # next
        ret = main(["--graph", self.graph_file, "next"])
        self.assertEqual(ret, 0)

        # why
        ret = main(["--graph", self.graph_file, "why", "TASK-03"])
        self.assertEqual(ret, 0)

        # diff against self
        ret = main(["--graph", self.graph_file, "diff", self.graph_file])
        self.assertEqual(ret, 0)

        # packet
        ret = main(["--graph", self.graph_file, "packet", "TASK-02", "--format", "json"])
        self.assertEqual(ret, 0)

        # mutation-test
        target_ops = str(ROOT / "graph_ops.py")
        ret = main([
            "--graph", self.graph_file,
            "mutation-test",
            "--target", target_ops,
            "--max-mutants", "5",
            "--test-module", "tests.test_diff_and_ledger"
        ])
        self.assertEqual(ret, 0)

    def test_audit_commands_are_read_only_and_disclose_gaps(self) -> None:
        from graph_backlog.jsonutil import load_json, compute_revision_hash
        raw = load_json(self.graph_file)
        node = raw["nodes"][0]
        raw["sources"]["missing"] = {"kind": "doc", "title": "Unresolved bytes",
                                      "recoverability": "UNRESOLVED_REFERENCE"}
        node["source_refs"] = ["missing"]
        node["source_claim_ids"] = ["missing:c1", "unattached:c2"]
        raw["revision"] = compute_revision_hash(raw)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "graph.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            before = path.read_bytes()
            def run(*args):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = main(["--graph", str(path), *args])
                return code, json.loads(output.getvalue())
            code, trace = run("trace", node["id"])
            self.assertEqual(code, 0)
            self.assertEqual(trace["node"], node)
            self.assertEqual(trace["source_claim_ids"], node["source_claim_ids"])
            self.assertEqual(trace["sources"][0]["source"], raw["sources"]["missing"])
            self.assertTrue(trace["gaps"])
            for key in ("content_verification", "anchor_verification", "execution_verification"):
                self.assertEqual(trace[key], "NOT_PERFORMED")
            code, report = run("reconcile")
            self.assertEqual(code, 0)
            self.assertEqual(report["checked"], len(raw["nodes"]))
            self.assertNotIn(node["id"], [r["id"] for r in report["operational_divergences"]])
            code, diff = run("diff", str(path), "--full")
            self.assertEqual(code, 0)
            self.assertTrue(diff["full_semantic"])
            self.assertEqual(diff["changes"], [])
            code, diff = run("diff", str(path), "--ignore-field", "notes")
            self.assertFalse(diff["full_semantic"])
            self.assertEqual(diff["ignored_fields"], ["notes"])
            self.assertEqual(path.read_bytes(), before)
            # Truly dangling references remain rejected by the owner validator.
            del raw["sources"]["missing"]
            raw["revision"] = compute_revision_hash(raw)
            path.write_text(json.dumps(raw), encoding="utf-8")
            code, invalid = run("trace", node["id"])
            self.assertEqual(code, 1)
            self.assertEqual(invalid["status"], "FAIL")
            self.assertIn("INVALID_SOURCE_REF", {e["code"] for e in invalid["errors"]})

    def test_shadow_parity_cli_gate_does_not_claim_cutover(self) -> None:
        from graph_backlog.jsonutil import load_json
        raw = load_json(self.graph_file)
        samples = [{"observed_at": time, "canonical": raw, "shadow": copy.deepcopy(raw)}
                   for time in ("2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z")]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "observations.json"
            for diverge, expected in ((False, 0), (True, 1)):
                if diverge:
                    samples[1]["shadow"]["nodes"][0]["notes"].append("drift")
                path.write_text(json.dumps(samples), encoding="utf-8")
                before = path.read_bytes()
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = main(["--graph", self.graph_file, "shadow-parity", str(path),
                                 "--min-window-seconds", "60"])
                report = json.loads(output.getvalue())
                self.assertEqual(code, expected)
                self.assertEqual(report["eligible_for_cutover_review"], not diverge)
                self.assertFalse(report["cutover_performed"])
                self.assertEqual(path.read_bytes(), before)

    def test_packet_generation_details(self) -> None:
        graph = WorkGraph.from_file(self.graph_file)
        packet_obj = generate_packet(graph, "TASK-02")
        self.assertEqual(packet_obj["work"]["id"], "TASK-02")
        self.assertIn("prerequisites", packet_obj)
        self.assertIn("downstream", packet_obj)

        md_prompt = format_packet_markdown(packet_obj)
        self.assertIn("TASK-02", md_prompt)
        self.assertIn("Definition of Done", md_prompt)

if __name__ == "__main__":
    unittest.main()
