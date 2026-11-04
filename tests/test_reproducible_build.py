"""Reproducible-build proof for graph-audit-reproducible-build (TRAIN-30).

Exit criterion 3: two clean builds are hash-identical for the deterministic
projections JSON / CSV / HTML / GraphML. Plus GraphML schema validity and an
XML-injection falsifier (FAL-03).

unittest.TestCase assertions only (no bare `assert`) so `python -O` preserves
coverage. In-memory + tempdir; zero canonical mutation (FAL-05).
"""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from graph_backlog.core import WorkGraph
from graph_backlog.adapters import CsvAdapter, GraphMLAdapter
from graph_backlog.visualizer import generate_html_viewer
from graph_backlog.jsonutil import stable_dict

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "sample-backlog.json"


def _projections(graph: WorkGraph) -> dict[str, bytes]:
    """All four canonical projections as UTF-8 bytes with '\\n' endings."""
    return {
        "json": (json.dumps(stable_dict(graph.to_dict()), ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        "nodes.csv": CsvAdapter.nodes_to_csv(graph).encode("utf-8"),
        "edges.csv": CsvAdapter.edges_to_csv(graph).encode("utf-8"),
        "html": generate_html_viewer(graph).encode("utf-8"),
        "graphml": GraphMLAdapter.to_graphml(graph).encode("utf-8"),
    }


class TestReproducibleBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = WorkGraph(json.loads(FIXTURE.read_text(encoding="utf-8")))

    def test_two_clean_builds_are_hash_identical(self) -> None:
        h1 = {k: hashlib.sha256(v).hexdigest() for k, v in _projections(self.graph).items()}
        # rebuild from a freshly loaded graph to catch shared-mutable-state drift
        g2 = WorkGraph(json.loads(FIXTURE.read_text(encoding="utf-8")))
        h2 = {k: hashlib.sha256(v).hexdigest() for k, v in _projections(g2).items()}
        self.assertEqual(h1, h2)

    def test_graphml_is_valid_xml(self) -> None:
        root = ET.fromstring(GraphMLAdapter.to_graphml(self.graph))
        self.assertTrue(root.tag.endswith("graphml"))

    def test_graphml_nodes_and_edges_sorted(self) -> None:
        xml = GraphMLAdapter.to_graphml(self.graph)
        ids = [line.split('id="', 1)[1].split('"', 1)[0]
               for line in xml.splitlines() if line.strip().startswith("<node ")]
        self.assertEqual(ids, sorted(ids))

    def test_graphml_escapes_xml_injection(self) -> None:
        """FAL-03: special chars in fields must escape and still parse."""
        raw = {
            "meta": {"title": "neg"},
            "nodes": [{"id": "n<1>", "title": 'a & b <script> "q" \'x\'',
                       "cluster": "c&c", "summary": "line1\nline2 < > &"}],
            "edges": [{"from": "n<1>", "to": "n<1>", "type": "BLOCKS & <x>"}],
        }
        xml = GraphMLAdapter.to_graphml(WorkGraph(raw))
        self.assertNotIn("<script>", xml)
        self.assertIn("&amp;", xml)
        # must remain parseable despite the injection vectors
        ET.fromstring(xml)


if __name__ == "__main__":
    unittest.main()
