from __future__ import annotations
import copy
import unittest
from pathlib import Path

from graph_backlog.core import WorkGraph
from graph_backlog.diff import semantic_diff, validate_change, shadow_parity
from graph_backlog.ledger import GraphLedger
from graph_backlog.simulation import simulate_completions
from graph_backlog.jsonutil import load_json

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"

class DiffAndLedgerTests(unittest.TestCase):
    def test_full_diff_preserves_all_graph_fields(self) -> None:
        old = load_json(FIXTURES / "sample-backlog.json")
        before = copy.deepcopy(old)
        # Every existing root/node/source/edge field participates; no implicit volatility.
        targets = [old, old["meta"], *old["nodes"], *old["edges"], *old["sources"].values()]
        for target in targets:
            for key in target:
                with self.subTest(key=key):
                    changed = copy.deepcopy(old)
                    # Locate the same container in the copy without normalizing any fields.
                    if target is old:
                        container = changed
                    elif target is old["meta"]:
                        container = changed["meta"]
                    else:
                        container = None
                        for section in ("nodes", "edges", "sources"):
                            values = old[section]
                            entries = values.items() if isinstance(values, dict) else enumerate(values)
                            for index, value in entries:
                                if target is value:
                                    container = changed[section][index]
                        self.assertIsNotNone(container)
                    container[key] = {"changed_for_test": True}
                    self.assertTrue(semantic_diff(old, changed))
        self.assertEqual(old, before)

    def test_full_diff_includes_nested_history_sources_and_additions(self) -> None:
        old = {"revision": "r1", "sources": {"s": {"sha256": "original"}},
               "nodes": [{"id": "n", "superseded_by": "successor", "completion": {
                   "status": "SUPERSEDED", "original_outcome": "FAIL"}}],
               "meta": {"generated_at": "original-time", "unknown_nested": {"x": 1}}}
        new = copy.deepcopy(old)
        new["revision"] = "r2"
        new["sources"]["s"]["sha256"] = "changed"
        new["nodes"][0]["completion"]["original_outcome"] = "PASS"
        new["meta"]["generated_at"] = "later"
        del new["meta"]["unknown_nested"]
        new["additional"] = {"must_remain_visible": True}
        changes = semantic_diff(old, new)
        self.assertEqual({c["path"] for c in changes}, {
            "$.revision", "$.sources.s.sha256", "$.nodes[id=n].completion.original_outcome",
            "$.meta.generated_at", "$.meta.unknown_nested", "$.additional"})
        self.assertEqual(old["nodes"][0]["completion"]["original_outcome"], "FAIL")

    def test_ambiguous_list_ids_never_hide_changes(self) -> None:
        for ids in (["x", "x"], [None, None], [["x"], ["x"]], [1, "1"]):
            old = [{"id": ident, "value": 0} for ident in ids]
            new = copy.deepcopy(old)
            new[0]["value"] = 1
            self.assertTrue(semantic_diff(old, new))
        self.assertEqual(semantic_diff([{"id": "a"}, {"id": "b"}],
                                       [{"id": "b"}, {"id": "a"}]), [])
        self.assertTrue(semantic_diff({"a.volatile": 1}, {"a.volatile": 2}, {"volatile"}))
        self.assertEqual(semantic_diff({"volatile": 1}, {"volatile": 2}, {"volatile"}), [])

    def test_shadow_parity_requires_a_real_supplied_window(self) -> None:
        raw = load_json(FIXTURES / "sample-backlog.json")
        samples = [{"observed_at": time, "canonical": copy.deepcopy(raw), "shadow": copy.deepcopy(raw)}
                   for time in ("2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z")]
        before = copy.deepcopy(samples)
        report = shadow_parity(samples, 60)
        self.assertEqual(report["status"], "PASS")
        self.assertTrue(report["eligible_for_cutover_review"])
        self.assertFalse(report["cutover_performed"])
        self.assertEqual(samples, before)
        self.assertEqual(report["samples"][0]["canonical_sha256"], report["samples"][0]["shadow_sha256"])
        for invalid_time in ("2026-01-01T00:00:00", "not-a-date", samples[0]["observed_at"]):
            bad = copy.deepcopy(samples)
            bad[1]["observed_at"] = invalid_time
            self.assertEqual(shadow_parity(bad, 60)["status"], "FAIL")
        cases = [([], 60), (samples[:1], 60), (samples, 61), (samples[::-1], 60),
                 (samples, 0), (samples, float("nan")), ([{}], 60)]
        for bad, window in cases:
            self.assertEqual(shadow_parity(bad, window)["status"], "FAIL")
        changed = copy.deepcopy(samples)
        changed[1]["shadow"]["nodes"][0]["notes"].append("nonvolatile divergence")
        report = shadow_parity(changed, 60)
        self.assertIn("semantic_divergence", report["gaps"])
        self.assertFalse(report["eligible_for_cutover_review"])
        changed = copy.deepcopy(samples)
        changed[0]["canonical"] = {}
        self.assertIn("sample[0]:invalid_graph", shadow_parity(changed, 60)["gaps"])

    def test_semantic_diff_no_changes(self) -> None:
        data = load_json(FIXTURES / "sample-backlog.json")
        changes = semantic_diff(data, data)
        self.assertEqual(len(changes), 0)

    def test_semantic_diff_node_status_change(self) -> None:
        old = load_json(FIXTURES / "sample-backlog.json")
        new = copy.deepcopy(old)
        new["nodes"][1]["completion"]["status"] = "DONE"
        new["nodes"][1]["completion"]["dod_satisfied"] = True
        
        changes = semantic_diff(old, new)
        self.assertTrue(len(changes) > 0)
        
        vc = validate_change(old, new)
        self.assertEqual(vc["status"], "PASS")
        self.assertEqual(vc["change_count"], len(changes))

    def test_ledger_append_and_integrity(self) -> None:
        ledger = GraphLedger()
        ev1 = ledger.append_event("NODE_CREATED", "developer", {"id": "TASK-01", "title": "Setup"})
        ev2 = ledger.append_event("STATUS_UPDATED", "developer", {"id": "TASK-01", "status": "DONE"})
        
        self.assertEqual(len(ledger.events), 2)
        self.assertEqual(ev2["prev_hash"], ev1["event_hash"])
        
        integrity = ledger.verify_integrity()
        self.assertTrue(integrity["valid"])
        self.assertEqual(integrity["event_count"], 2)

    def test_simulation_overlay(self) -> None:
        graph = WorkGraph.from_file(FIXTURES / "sample-backlog.json")
        # In sample-backlog, TASK-02 is NOT_DONE, blocking TASK-03.
        # If we simulate completing TASK-02, TASK-03 should be newly unlocked!
        sim = simulate_completions(graph, ["TASK-02"])
        self.assertIn("TASK-03", sim["newly_unlocked_nodes"])

if __name__ == "__main__":
    unittest.main()
