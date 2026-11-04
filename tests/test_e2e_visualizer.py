from __future__ import annotations
import json
import os
import tempfile
import unittest
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

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
        if sync_playwright is None:
            self.skipTest("playwright not installed")
            return
        try:
            p_cm = sync_playwright()
            p = p_cm.__enter__()
            try:
                browser = p.chromium.launch(headless=True)
            except Exception as exc:
                p_cm.__exit__(None, None, None)
                self.skipTest(f"Playwright chromium browser not available in this environment: {exc}")
                return
        except Exception as exc:
            self.skipTest(f"Playwright runtime not available: {exc}")
            return

        try:
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
            
            # 11.5 Test Critical Path Button Toggle & DAG Highlighting
            page.click("#criticalPathBtn")
            self.assertIn("active", page.locator("#criticalPathBtn").get_attribute("class"))
            # In Sample graph (TASK-01 -> TASK-02 -> TASK-03), all edges are on the critical path
            self.assertEqual(page.locator("#dagEdge_TASK-01_TASK-02").get_attribute("class"), "edge-pulse-upstream")
            self.assertEqual(page.locator("#dagEdge_TASK-02_TASK-03").get_attribute("class"), "edge-pulse-upstream")
            
            # Toggle Critical Path off
            page.click("#criticalPathBtn")
            self.assertNotIn("active", page.locator("#criticalPathBtn").get_attribute("class"))
            self.assertIsNone(page.locator("#dagEdge_TASK-01_TASK-02").get_attribute("class"))
            
            # Check DAG status colors (status rail and pips)
            # TASK-01 is DONE (#8B9173)
            self.assertEqual(page.locator("#dagNode_TASK-01 circle").get_attribute("fill"), "#8B9173")
            # TASK-02 is READY (#CBF23F)
            self.assertEqual(page.locator("#dagNode_TASK-02 circle").get_attribute("fill"), "#CBF23F")
            # TASK-03 is BLOCKED (#F2685C)
            self.assertEqual(page.locator("#dagNode_TASK-03 circle").get_attribute("fill"), "#F2685C")
            
            # 12. Test Drag and Drop of a Node in DAG Canvas with Critical Path Active
            page.click("#criticalPathBtn")
            self.assertEqual(page.locator("#dagEdge_TASK-01_TASK-02").get_attribute("class"), "edge-pulse-upstream")
            
            node_box = page.locator("#dagNode_TASK-03").bounding_box()
            self.assertIsNotNone(node_box)
            
            initial_transform = page.locator("#dagNode_TASK-03").get_attribute("transform")
            initial_edge_d = page.locator("#dagEdge_TASK-02_TASK-03").get_attribute("d")
            
            # Drag node by 100px to the right and 50px down
            page.mouse.move(node_box["x"] + 20, node_box["y"] + 20)
            page.mouse.down()
            page.mouse.move(node_box["x"] + 120, node_box["y"] + 70, steps=5)
            page.mouse.up()
            
            # Verify node transform moved and connected edge curve updated
            self.assertNotEqual(page.locator("#dagNode_TASK-03").get_attribute("transform"), initial_transform)
            self.assertNotEqual(page.locator("#dagEdge_TASK-02_TASK-03").get_attribute("d"), initial_edge_d)
            
            # CRITICAL ASSERTION: The critical path pulse highlight STILL persists after drag!
            self.assertEqual(page.locator("#dagEdge_TASK-01_TASK-02").get_attribute("class"), "edge-pulse-upstream")
            self.assertEqual(page.locator("#dagEdge_TASK-02_TASK-03").get_attribute("class"), "edge-pulse-upstream")
            
            # Toggle Critical Path off
            page.click("#criticalPathBtn")
            self.assertNotIn("active", page.locator("#criticalPathBtn").get_attribute("class"))
            
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
            
            # 14. Test ESC Key Deselect & Clearing Active Paths (e.g. Critical Path)
            page.click("#criticalPathBtn")
            self.assertIn("active", page.locator("#criticalPathBtn").get_attribute("class"))
            self.assertEqual(page.locator("#dagEdge_TASK-01_TASK-02").get_attribute("class"), "edge-pulse-upstream")
            
            # Press ESC: must clear critical path, reset button, and deselect
            page.keyboard.press("Escape")
            self.assertEqual(page.locator("#inspId").text_content(), "Select a task")
            self.assertNotIn("active", page.locator("#criticalPathBtn").get_attribute("class"))
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
            # Switch to Epic Transmedia Saga (42 tasks)
            page.select_option("#projectSelector", "transmedia")
            self.assertEqual(page.locator("#statTotal").text_content(), "42")
            self.assertIn("Aethelgard Saga", page.locator("#projectTitleDisplay").text_content())

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

            # 16.5 Test Hide/Show Synthetic Demos with LocalStorage Persistence
            self.assertEqual(page.locator("#projectSelector option[value='saas']").count(), 1)
            
            # Click Toggle Demos Button (hide demos)
            page.click("#toggleDemosBtn")
            self.assertEqual(page.locator("#projectSelector option[value='saas']").count(), 0)
            self.assertEqual(page.locator("#projectSelector option[value='transmedia']").count(), 0)
            
            # Verify localStorage value
            storage_val = page.evaluate("() => localStorage.getItem('SIGNAL_GRAPH_HIDE_DEMOS')")
            self.assertEqual(storage_val, "true")
            
            # Click Toggle Demos Button again (show demos)
            page.click("#toggleDemosBtn")
            self.assertEqual(page.locator("#projectSelector option[value='saas']").count(), 1)
            self.assertEqual(page.locator("#projectSelector option[value='transmedia']").count(), 1)
            storage_val = page.evaluate("() => localStorage.getItem('SIGNAL_GRAPH_HIDE_DEMOS')")
            self.assertEqual(storage_val, "false")

            # 16.6 Test Theme Engine Switching & LocalStorage Persistence
            self.assertEqual(page.locator("#themeSelector").input_value(), "signal")
            
            # Switch to Dracula
            page.select_option("#themeSelector", "dracula")
            dracula_bg = page.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--bg-base').trim()")
            self.assertEqual(dracula_bg, "#282a36")
            self.assertEqual(page.evaluate("() => localStorage.getItem('SIGNAL_GRAPH_THEME')"), "dracula")
            
            # Switch to Solar Paper (Light)
            page.select_option("#themeSelector", "light")
            light_bg = page.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--bg-base').trim()")
            self.assertEqual(light_bg, "#f8fafc")
            self.assertEqual(page.evaluate("() => document.documentElement.style.colorScheme"), "light")
            
            # Switch to Solarized Light
            page.select_option("#themeSelector", "solarized_light")
            solarized_bg = page.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--bg-base').trim()")
            self.assertEqual(solarized_bg, "#fdf6e3")
            self.assertEqual(page.evaluate("() => localStorage.getItem('SIGNAL_GRAPH_THEME')"), "solarized_light")

            # Switch to GitHub Light
            page.select_option("#themeSelector", "github_light")
            github_bg = page.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--bg-base').trim()")
            self.assertEqual(github_bg, "#ffffff")
            self.assertEqual(page.evaluate("() => localStorage.getItem('SIGNAL_GRAPH_THEME')"), "github_light")

            # Switch back to Signal Canonical Default
            page.select_option("#themeSelector", "signal")
            signal_bg = page.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--bg-base').trim()")
            self.assertEqual(signal_bg, "#0A0B08")
            self.assertEqual(page.evaluate("() => localStorage.getItem('SIGNAL_GRAPH_THEME')"), "signal")

            # 17. Test ⚡ Graph Ops Station Modal & DAG Navigation
            page.click("#opsModalBtn")
            self.assertTrue(page.locator("#opsModalBackdrop").is_visible())
            
            # Tab 1: Doctor Audit
            self.assertIn("GRAPH TOPOLOGY & INTEGRITY HEALTHY", page.locator("#opsModalContent").text_content())
            
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
            
            # Tab 3: Semantic Diff (Op 9)
            page.click("#opsModalBtn")
            page.click("#modalTabDiff")
            self.assertIn("Semantic Diff Engine", page.locator("#opsModalContent").text_content())
            
            # Tab 4: Cryptographic Ledger (Op 10)
            page.click("#modalTabLedger")
            self.assertIn("Verified SHA-256 Chain", page.locator("#opsModalContent").text_content())
            self.assertIn("INIT_GRAPH", page.locator("#opsModalContent").text_content())
            
            # Tab 5: Agent Implementation Packet (Op 11)
            page.click("#modalTabAgent")
            self.assertIn("Implementation Packet", page.locator("#agentPacketText").input_value())
            
            # Tab 6: Universal Export (Op 13)
            page.click("#modalTabExport")
            self.assertTrue(page.locator("button:has-text('JSON Graph')").is_visible())
            self.assertTrue(page.locator("button:has-text('Mermaid Flowchart')").is_visible())
            self.assertTrue(page.locator("button:has-text('Markdown Spec')").is_visible())
            self.assertTrue(page.locator("button:has-text('CSV Table')").is_visible())
            
            # Close modal via Escape
            page.keyboard.press("Escape")
            self.assertFalse(page.locator("#opsModalBackdrop").is_visible())

            # 18. Test Transitive Closure Buttons in Inspector (Op 6)
            page.click("#tabDagBtn")
            page.click("#dagNode_TASK-03")
            self.assertEqual(page.locator("#inspId").text_content(), "TASK-03")
            
            # Click Upstream Blockers Closure
            page.click("#traceAncestorsBtn")
            self.assertEqual(page.locator("#dagEdge_TASK-01_TASK-02").get_attribute("class"), "edge-pulse-upstream")
            self.assertEqual(page.locator("#dagEdge_TASK-02_TASK-03").get_attribute("class"), "edge-pulse-upstream")

            # 19. Test Microsoft 365 Copilot & Agentic Discovery Bridge
            # 19.1 Meta tags and In-DOM Manifest
            self.assertEqual(page.locator("meta[name='agentic-protocol']").get_attribute("content"), "tare.tools/graph-backlog/v1")
            self.assertEqual(page.locator("meta[name='agentic-runtime']").get_attribute("content"), "window.tareGraph")
            manifest_str = page.locator("#signal-agentic-manifest").text_content()
            manifest_json = json.loads(manifest_str)
            self.assertEqual(manifest_json["protocol"], "tare.tools/graph-backlog/v1")
            self.assertTrue(len(manifest_json["nodes"]) > 0)
            self.assertTrue(len(manifest_json["actionable_frontier_ids"]) > 0)

            # 19.2 Window Runtime API (window.tareGraph & window.__SIGNAL_AGENT_API__)
            api_summary = page.evaluate("() => window.tareGraph.getSummary()")
            self.assertEqual(api_summary["totalTasks"], 3)
            self.assertEqual(api_summary["activeTheme"], "signal")
            
            api_frontier = page.evaluate("() => window.tareGraph.getFrontier()")
            self.assertEqual(len(api_frontier), 1)
            self.assertEqual(api_frontier[0]["id"], "TASK-02")
            
            api_cp = page.evaluate("() => window.tareGraph.getCriticalPath()")
            self.assertEqual(api_cp["length"], 3)
            self.assertEqual(api_cp["path"], ["TASK-01", "TASK-02", "TASK-03"])
            
            api_audit = page.evaluate("() => window.tareGraph.getDoctorAudit()")
            self.assertTrue(api_audit["healthy"])
            
            api_ctx = page.evaluate("() => window.tareGraph.getCopilotContext()")
            self.assertIn("Work Graph Context", api_ctx)
            self.assertIn("Critical Path", api_ctx)

            # 19.3 Ephemeral Simulation via API
            sim_res = page.evaluate("() => window.tareGraph.simulate('TASK-02', true)")
            self.assertIn("TASK-02", sim_res["simulatedDone"])
            self.assertIn("TASK-03", sim_res["newFrontier"])
            page.evaluate("() => window.tareGraph.resetSimulation()")

            # 19.4 Copilot Bridge Subnav Button & Modal Tab
            page.click("#copilotBridgeBtn")
            self.assertTrue(page.locator("#opsModalBackdrop").is_visible())
            self.assertTrue(page.locator("#modalTabCopilot").evaluate("el => el.classList.contains('active')"))
            self.assertIn("Work Graph Context", page.locator("#copilotContextText").input_value())
            
            # Test Sandbox Runner
            page.click("button:has-text('tareGraph.getFrontier()')")
            self.assertIn("TASK-02", page.locator("#copilotSandboxOutput").text_content())

            page.keyboard.press("Escape")
            self.assertFalse(page.locator("#opsModalBackdrop").is_visible())
        finally:
            try:
                browser.close()
            except Exception:
                pass
            p_cm.__exit__(None, None, None)

if __name__ == "__main__":
    unittest.main()
