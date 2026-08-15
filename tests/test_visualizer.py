from __future__ import annotations
import tempfile
import unittest
from pathlib import Path

from graph_backlog.core import WorkGraph
from graph_backlog.visualizer import generate_html_viewer

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"

class VisualizerTests(unittest.TestCase):
    def test_generate_html_content(self) -> None:
        graph = WorkGraph.from_file(FIXTURES / "sample-backlog.json")
        html = generate_html_viewer(graph)
        self.assertIn("tare.tools — Graph Backlog Visualizer", html)
        self.assertIn("TASK-01", html)
        self.assertIn("TASK-02", html)

    def test_generate_html_file(self) -> None:
        graph = WorkGraph.from_file(FIXTURES / "sample-backlog.json")
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tf:
            outpath = tf.name
        try:
            generate_html_viewer(graph, outpath)
            content = Path(outpath).read_text(encoding="utf-8")
            self.assertIn("<!DOCTYPE html>", content)
            self.assertIn("TASK-01", content)
        finally:
            Path(outpath).unlink(missing_ok=True)

if __name__ == "__main__":
    unittest.main()
