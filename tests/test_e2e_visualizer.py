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
            self.assertIn("Backlog", brand_pill)
            
            # 3. Check initial stats in status bar
            stat_total = page.locator("#statTotal").text_content()
            self.assertEqual(stat_total, "3")
            
            stat_ready = page.locator("#statReady").text_content()
            self.assertEqual(stat_ready, "1")  # TASK-02 is ready
            
            # 4. Check initial selected task in inspector drawer (default unselected)
            insp_id = page.locator("#inspId").text_content()
            self.assertEqual(insp_id, "Select a task")
            
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
            page.locator(".task-card:has-text('TASK-02')").first.click()
            page.check("#simToggle")
            
            # Now with TASK-02 simulated as DONE, TASK-03 should become READY in real time
            page.locator(".task-card:has-text('TASK-03')").first.click()
            sim_insp_state = page.locator("#inspState").text_content()
            self.assertIn("READY", sim_insp_state)
            
            # 10. Test Classic Kanban View (3rd View Mode)
            page.click("#tabKanbanBtn")
            self.assertTrue(page.locator("#kanbanView").is_visible())
            lanes_count = page.locator(".kanban-lane").count()
            self.assertEqual(lanes_count, 4)
            
            # Verify lane titles
            self.assertIn("Blocked Backlog", page.locator(".kanban-lane").nth(0).text_content())
            self.assertIn("Ready Frontier", page.locator(".kanban-lane").nth(1).text_content())
            self.assertIn("In Progress", page.locator(".kanban-lane").nth(2).text_content())
            self.assertIn("Done / Shipped", page.locator(".kanban-lane").nth(3).text_content())
            
            # Click card in Classic Kanban
            page.locator("#laneCards_DONE .task-card").first.click()
            self.assertEqual(page.locator("#inspId").text_content(), "TASK-01")
            
            # 11. Test Tab Switching to Interactive DAG Canvas
            page.click("#tabDagBtn")
            dag_svg = page.locator("#dagSvg")
            self.assertTrue(dag_svg.is_visible())
            svg_nodes = page.locator("#dagNodesLayer g").count()
            self.assertEqual(svg_nodes, 3)
            
            # 11. Test Filters in DAG Canvas view
            # Select cluster "api" (has TASK-02)
            page.select_option("#clusterFilter", "api")
            self.assertEqual(page.locator("#dagNodesLayer g").count(), 1)
            self.assertTrue(page.locator("#dagNode_TASK-02").is_visible())
            self.assertFalse(page.locator("#dagNode_TASK-01").is_visible())
            self.assertFalse(page.locator("#dagNode_TASK-03").is_visible())
            
            # Reset cluster filter
            page.select_option("#clusterFilter", "ALL")
            self.assertEqual(page.locator("#dagNodesLayer g").count(), 3)
            
            # Select status "FRONTIER"
            page.select_option("#statusFilter", "FRONTIER")
            # In simulation, TASK-03 became frontier when TASK-02 was simulated DONE
            self.assertEqual(page.locator("#dagNodesLayer g").count(), 1)
            self.assertTrue(page.locator("#dagNode_TASK-03").is_visible())
            
            # Reset filters
            page.click("#resetBtn")
            self.assertEqual(page.locator("#dagNodesLayer g").count(), 3)
            
            # Check DAG status colors (status rail and pips)
            # TASK-01 is DONE (#8B9173)
            self.assertEqual(page.locator("#dagNode_TASK-01 circle").get_attribute("fill"), "#8B9173")
            # TASK-02 is READY (#CBF23F)
            self.assertEqual(page.locator("#dagNode_TASK-02 circle").get_attribute("fill"), "#CBF23F")
            # TASK-03 is BLOCKED (#F2685C)
            self.assertEqual(page.locator("#dagNode_TASK-03 circle").get_attribute("fill"), "#F2685C")
            
            # 12. Test Drag and Drop of a Node in DAG Canvas
            node_box = page.locator("#dagNode_TASK-01").bounding_box()
            self.assertIsNotNone(node_box)
            
            initial_transform = page.locator("#dagNode_TASK-01").get_attribute("transform")
            initial_edge_d = page.locator("#dagEdge_TASK-01_TASK-02").get_attribute("d")
            
            # Drag node by 100px to the right and 50px down
            page.mouse.move(node_box["x"] + 20, node_box["y"] + 20)
            page.mouse.down()
            page.mouse.move(node_box["x"] + 120, node_box["y"] + 70, steps=5)
            page.mouse.up()
            
            # 13. Test Recursive Dependency Chain (Upstream only)
            # When TASK-02 is selected: upstream TASK-01 pulses, downstream TASK-03 is dimmed
            page.locator("#dagNode_TASK-02").click()
            self.assertEqual(page.locator("#inspId").text_content(), "TASK-02")
            self.assertEqual(page.locator("#dagEdge_TASK-01_TASK-02").get_attribute("class"), "edge-pulse-upstream")
            self.assertEqual(page.locator("#dagEdge_TASK-02_TASK-03").get_attribute("class"), "edge-dimmed")
            self.assertEqual(page.locator("#dagNode_TASK-03").get_attribute("class"), "dag-node-dimmed")
            
            # When TASK-03 is selected: both upstream edges pulse
            page.locator("#dagNode_TASK-03").click()
            self.assertEqual(page.locator("#inspId").text_content(), "TASK-03")
            self.assertEqual(page.locator("#dagEdge_TASK-01_TASK-02").get_attribute("class"), "edge-pulse-upstream")
            self.assertEqual(page.locator("#dagEdge_TASK-02_TASK-03").get_attribute("class"), "edge-pulse-upstream")
            
            # 14. Test ESC Key Deselect
            page.keyboard.press("Escape")
            self.assertEqual(page.locator("#inspId").text_content(), "Select a task")
            # Assert edges return to default (no pulse class)
            self.assertIsNone(page.locator("#dagEdge_TASK-01_TASK-02").get_attribute("class"))
            self.assertIsNone(page.locator("#dagEdge_TASK-02_TASK-03").get_attribute("class"))

            # 15. Test Full Reset Button Behavior
            # Mutate state: filter cluster, fill search, zoom in, select node
            page.select_option("#clusterFilter", "api")
            page.fill("#searchInput", "Core")
            page.click(".hud-btn:has-text('+')")
            self.assertNotEqual(page.locator("#zoomDisplay").text_content(), "100%")
            
            # Click Reset button
            page.click("#resetBtn")
            
            # Assert all inputs and canvas viewports are fully reset
            self.assertEqual(page.locator("#searchInput").input_value(), "")
            self.assertEqual(page.locator("#statusFilter").input_value(), "ALL")
            self.assertEqual(page.locator("#clusterFilter").input_value(), "ALL")
            self.assertEqual(page.locator("#zoomDisplay").text_content(), "100%")
            self.assertEqual(page.locator("#inspId").text_content(), "Select a task")
            self.assertEqual(page.locator("#dagNodesLayer g").count(), 3)

            # 16. Test In-UI Project Selector Switching
            # Switch to OmniAgent AI RAG CRM (27 tasks)
            page.select_option("#projectSelector", "rag")
            self.assertEqual(page.locator("#statTotal").text_content(), "27")
            self.assertIn("OmniAgent", page.locator("#projectTitleDisplay").text_content())
            
            # Switch to CloudPulse SaaS (33 tasks)
            page.select_option("#projectSelector", "saas")
            self.assertEqual(page.locator("#statTotal").text_content(), "33")
            self.assertIn("CloudPulse", page.locator("#projectTitleDisplay").text_content())

            # Switch back to Sample (3 tasks)
            page.select_option("#projectSelector", "sample")
            self.assertEqual(page.locator("#statTotal").text_content(), "3")

            # 17. Test ⚡ Graph Ops Station Modal & DAG Navigation
            page.click("#opsModalBtn")
            self.assertTrue(page.locator("#opsModalBackdrop").is_visible())
            
            # Tab 1: Doctor Audit
            self.assertIn("GRAPH TOPOLOGY HEALTHY", page.locator("#opsModalContent").text_content())
            
            # Tab 2: Action Queue & Path Finder
            page.click("#modalTabRanked")
            self.assertIn("TASK-02", page.locator("#opsModalContent").text_content())
            
            # Click Ranked task: must close modal and focus/select on DAG
            page.click(".report-card.pass:has-text('TASK-02')")
            self.assertFalse(page.locator("#opsModalBackdrop").is_visible())
            self.assertTrue(page.locator("#dagView").is_visible())
            self.assertEqual(page.locator("#inspId").text_content(), "TASK-02")
            
            # Re-open and test Shortest Path tracing to DAG
            page.click("#opsModalBtn")
            page.click("#modalTabRanked")
            page.select_option("#pathStartSelect", "TASK-01")
            page.select_option("#pathEndSelect", "TASK-03")
            page.click("#findPathBtn")
            self.assertIn("TASK-01 ➔ TASK-02 ➔ TASK-03", page.locator("#pathResultBox").text_content())
            
            # Click Trace on DAG: must close modal, switch to DAG, and activate path
            page.click("#traceOnDagBtn")
            self.assertFalse(page.locator("#opsModalBackdrop").is_visible())
            self.assertTrue(page.locator("#dagView").is_visible())
            self.assertEqual(page.locator("#inspId").text_content(), "TASK-03")
            self.assertEqual(page.locator("#dagEdge_TASK-01_TASK-02").get_attribute("class"), "edge-pulse-upstream")
            self.assertEqual(page.locator("#dagEdge_TASK-02_TASK-03").get_attribute("class"), "edge-pulse-upstream")
            
            # Tab 3: Export Station
            page.click("#opsModalBtn")
            page.click("#modalTabExport")
            self.assertTrue(page.locator("button:has-text('Download JSON')").is_visible())
            
            # Close modal via Escape
            page.keyboard.press("Escape")
            self.assertFalse(page.locator("#opsModalBackdrop").is_visible())

            browser.close()

if __name__ == "__main__":
    unittest.main()
