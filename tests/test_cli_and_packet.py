from __future__ import annotations
import tempfile
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

        # doctor
        ret = main(["--graph", self.graph_file, "doctor"])
        self.assertEqual(ret, 0)

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
        ret = main([
            "--graph", self.graph_file,
            "mutation-test",
            "--target", "src/graph_backlog/simulation.py",
            "--max-mutants", "5",
            "--test-module", "tests.test_diff_and_ledger"
        ])
        self.assertEqual(ret, 0)

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
