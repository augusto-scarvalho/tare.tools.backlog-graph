from __future__ import annotations
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "graph_ops.py"
FIXTURES = ROOT / "fixtures"

def run_cmd(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(SCRIPT)] + list(args)
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
    if check and res.returncode != 0:
        raise AssertionError(f"Command failed ({res.returncode}): {' '.join(cmd)}\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
    return res

class GraphOpsTests(unittest.TestCase):
    def test_v05_validates(self) -> None:
        p = FIXTURES / "work-graph-v0.5.json"
        res = run_cmd("--graph", str(p), "validate")
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "PASS")

    def test_sample_backlog_validates(self) -> None:
        p = FIXTURES / "sample-backlog.json"
        res = run_cmd("--graph", str(p), "validate")
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "PASS")

    def test_saas_backlog_validates(self) -> None:
        p = FIXTURES / "saas-backlog.json"
        res = run_cmd("--graph", str(p), "validate")
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "PASS")
        self.assertEqual(data["node_count"], 33)
        self.assertEqual(data["edge_count"], 50)

    def test_crm_rag_chatbot_backlog_validates(self) -> None:
        p = FIXTURES / "crm-rag-chatbot-backlog.json"
        res = run_cmd("--graph", str(p), "validate")
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "PASS")
        self.assertEqual(data["node_count"], 27)
        self.assertEqual(data["edge_count"], 37)

    def test_transmedia_epic_saga_backlog_validates(self) -> None:
        p = FIXTURES / "transmedia-book-comic-film-backlog.json"
        res = run_cmd("--graph", str(p), "validate")
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "PASS")
        self.assertEqual(data["node_count"], 42)
        self.assertEqual(data["edge_count"], 62)

    def test_validate_exit_code_is_one_for_invalid_graph(self) -> None:
        p = FIXTURES / "negative-invalid-status.json"
        res = run_cmd("--graph", str(p), "validate", check=False)
        self.assertEqual(res.returncode, 1)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "FAIL")

    def test_blocking_self_loop_detected(self) -> None:
        p = FIXTURES / "negative-blocking-self-loop.json"
        res = run_cmd("--graph", str(p), "validate", check=False)
        self.assertEqual(res.returncode, 1)
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "FAIL")
        codes = [e["code"] for e in data.get("errors", [])]
        self.assertIn("BLOCKING_CYCLE", codes)

    def test_format_after_subcommand(self) -> None:
        p = FIXTURES / "sample-backlog.json"
        res = run_cmd("--graph", str(p), "summary", "--format", "json")
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["nodes"], 3)
        self.assertEqual(data["edges"], 2)

    def test_frontier_computation(self) -> None:
        p = FIXTURES / "sample-backlog.json"
        res = run_cmd("--graph", str(p), "frontier", "--format", "ids")
        self.assertEqual(res.returncode, 0)
        lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
        # TASK-01 is DONE, so TASK-02 should be in frontier. TASK-03 depends on TASK-02 so it is blocked.
        self.assertIn("TASK-02", lines)
        self.assertNotIn("TASK-03", lines)

    def test_why_blockers(self) -> None:
        p = FIXTURES / "sample-backlog.json"
        res = run_cmd("--graph", str(p), "why", "TASK-03")
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertFalse(data["ready"])
        self.assertIn("unresolved_prerequisites", data["reasons"])

    def test_packet_generation(self) -> None:
        p = FIXTURES / "sample-backlog.json"
        res = run_cmd("--graph", str(p), "packet", "TASK-02", "--format", "md")
        self.assertEqual(res.returncode, 0)
        self.assertIn("# Implementation Packet: `TASK-02`", res.stdout)
        self.assertIn("Build Core Business API", res.stdout)

    def test_doctor_command(self) -> None:
        p = FIXTURES / "sample-backlog.json"
        res = run_cmd("--graph", str(p), "doctor")
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertIn(data["status"], ("PASS", "PASS_SHADOW_WITH_GAPS"))

if __name__ == "__main__":
    unittest.main()
