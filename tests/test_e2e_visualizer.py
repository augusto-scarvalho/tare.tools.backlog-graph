from __future__ import annotations
import os
import tempfile
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

from graph_backlog.core import WorkGraph
from graph_backlog.visualizer import generate_html_viewer

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"

class VisualizerE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = WorkGraph.from_file(FIXTURES / "sample-backlog.json")
        cls.temp_file = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
        cls.html_path = cls.temp_file.name
        cls.temp_file.close()
        generate_html_viewer(cls.graph, cls.html_path)

    @classmethod
    def tearDownClass(cls) -> None:
        if os.path.exists(cls.html_path):
            try:
                os.unlink(cls.html_path)
            except OSError:
                pass

    def test_visualizer_e2e_headless(self) -> None:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # 1. Load the generated HTML page
            file_url = Path(self.html_path).as_uri()
            page.goto(file_url)
            
            # 2. Check title and brand
            self.assertIn("Graph Backlog", page.title())
            brand_pill = page.locator(".brand-pill").text_content()
            self.assertIn("SIGNAL", brand_pill)
            
            # 3. Check initial stats in status bar
            stat_total = page.locator("#statTotal").text_content()
            self.assertEqual(stat_total, "3")
            
            stat_ready = page.locator("#statReady").text_content()
            self.assertEqual(stat_ready, "1")  # TASK-02 is ready
            
            # 4. Check initial selected task in inspector drawer
            insp_id = page.locator("#inspId").text_content()
            self.assertEqual(insp_id, "TASK-01")
            
            # 5. Click on TASK-02 card and verify inspector updates
            page.locator(".task-card:has-text('TASK-02')").click()
            self.assertEqual(page.locator("#inspId").text_content(), "TASK-02")
            insp_state = page.locator("#inspState").text_content()
            self.assertIn("READY", insp_state)
            
            # 6. Test search filter input
            page.fill("#searchInput", "Dashboard")
            visible_cards = page.locator(".task-card").count()
            self.assertEqual(visible_cards, 1)
            self.assertIn("TASK-03", page.locator(".task-card").first.text_content())
            
            # 7. Reset filters
            page.click("#resetBtn")
            self.assertEqual(page.locator(".task-card").count(), 3)
            
            # 8. Test Status filter -> Frontier only
            page.select_option("#statusFilter", "FRONTIER")
            self.assertEqual(page.locator(".task-card").count(), 1)
            self.assertIn("TASK-02", page.locator(".task-card").first.text_content())
            
            page.select_option("#statusFilter", "ALL")
            
            # 9. Test Interactive What-If Simulation
            # TASK-03 is currently blocked by TASK-02.
            # Select TASK-02 and click simulation checkbox
            page.locator(".task-card:has-text('TASK-02')").click()
            page.check("#simToggle")
            
            # Now with TASK-02 simulated as DONE, TASK-03 should become READY in real time!
            page.locator(".task-card:has-text('TASK-03')").click()
            sim_insp_state = page.locator("#inspState").text_content()
            self.assertIn("READY", sim_insp_state)
            
            # 10. Test Tab Switching to Interactive DAG Canvas
            page.click("#tabDagBtn")
            dag_svg = page.locator("#dagSvg")
            self.assertTrue(dag_svg.is_visible())
            svg_nodes = page.locator("#dagSvg g rect").count()
            self.assertEqual(svg_nodes, 3)
            
            browser.close()

if __name__ == "__main__":
    unittest.main()
