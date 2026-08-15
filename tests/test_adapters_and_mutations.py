from __future__ import annotations
import tempfile
import unittest
from pathlib import Path

from graph_backlog.core import WorkGraph
from graph_backlog.adapters import MarkdownAdapter, MermaidAdapter, CsvAdapter
from graph_backlog.mutations import add_node_to_graph, complete_node_in_graph
from graph_backlog.validation import validate_work_graph
from graph_backlog.jsonutil import load_json

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"

class AdaptersAndMutationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = WorkGraph.from_file(FIXTURES / "sample-backlog.json")

    def test_markdown_export_and_import(self) -> None:
        md_text = MarkdownAdapter.to_markdown(self.graph)
        self.assertIn("- [x] TASK-01", md_text)
        self.assertIn("- [ ] TASK-02", md_text)

        imported = MarkdownAdapter.from_markdown(md_text)
        self.assertEqual(len(imported["nodes"]), 3)
        self.assertEqual(len(imported["edges"]), 2)
        val = validate_work_graph(imported)
        self.assertEqual(val["status"], "PASS")

    def test_mermaid_export(self) -> None:
        mermaid_text = MermaidAdapter.to_mermaid(self.graph)
        self.assertIn("flowchart TD", mermaid_text)
        self.assertIn("TASK_01 -->|unlocks| TASK_02", mermaid_text)
        self.assertIn("classDef done", mermaid_text)

    def test_csv_export(self) -> None:
        nodes_csv = CsvAdapter.nodes_to_csv(self.graph)
        self.assertIn("TASK-01", nodes_csv)
        self.assertIn("TASK-02", nodes_csv)

        edges_csv = CsvAdapter.edges_to_csv(self.graph)
        self.assertIn("TASK-01,TASK-02,UNLOCKS,True", edges_csv)

    def test_add_node_mutation(self) -> None:
        new_graph_raw = add_node_to_graph(
            self.graph,
            node_id="TASK-04",
            title="Deploy to Production",
            cluster="ops",
            depends_on=["TASK-03"]
        )
        val = validate_work_graph(new_graph_raw)
        self.assertEqual(val["status"], "PASS")
        self.assertEqual(len(new_graph_raw["nodes"]), 4)
        self.assertEqual(len(new_graph_raw["edges"]), 3)

    def test_complete_node_mutation(self) -> None:
        new_graph_raw = complete_node_in_graph(
            self.graph,
            node_id="TASK-02",
            evidence_summary="Integration tests passed with 100% assertions green."
        )
        val = validate_work_graph(new_graph_raw)
        self.assertEqual(val["status"], "PASS")
        updated_node = next(n for n in new_graph_raw["nodes"] if n["id"] == "TASK-02")
        self.assertEqual(updated_node["completion"]["status"], "DONE")
        self.assertTrue(updated_node["completion"]["dod_satisfied"])

if __name__ == "__main__":
    unittest.main()
