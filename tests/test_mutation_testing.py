from __future__ import annotations

import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from graph_backlog.mutation_testing import MutationEngine

ROOT = Path(__file__).resolve().parent.parent

class MutationTestingTests(unittest.TestCase):
    def test_discover_mutations_ast(self) -> None:
        sample_code = """
def is_valid(x: int, flag: bool) -> bool:
    if x > 10 and flag == True:
        return True
    return False
"""
        candidates = MutationEngine.discover_mutations(sample_code, filename="test_sample.py")
        self.assertGreater(len(candidates), 0)
        # Should have found comparison, boolean op, and boolean constants
        descriptions = [c.description for c in candidates]
        self.assertTrue(any("comparison" in d.lower() for d in descriptions))
        self.assertTrue(any("boolean operator" in d.lower() for d in descriptions))
        self.assertTrue(any("boolean constant" in d.lower() for d in descriptions))

    def test_curated_mutation_canaries_are_killed_without_touching_sources(self) -> None:
        source_files = sorted((ROOT / "src" / "graph_backlog").rglob("*.py"))
        hashes_before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in source_files
        }

        res = MutationEngine.run_mutation_test(
            target_file=ROOT / "src" / "graph_backlog" / "algorithms.py",
            test_modules=["tests.test_algorithms"],
            mutation_ids=[0, 1, 2, 3, 4],
            max_mutants=5,
            timeout_seconds=10,
        )
        hashes_after = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in source_files
        }

        self.assertEqual(res.total_mutants, 5)
        self.assertEqual(res.killed, 5)
        self.assertEqual(res.survived, 0)
        self.assertEqual(res.timed_out, 0)
        self.assertEqual(res.errored, 0)
        self.assertEqual(res.score_percentage, 100.0)
        self.assertEqual({detail["status"] for detail in res.details}, {"KILLED"})
        self.assertEqual(hashes_after, hashes_before)

    def test_curated_validation_mutation_canaries_are_killed(self) -> None:
        res = MutationEngine.run_mutation_test(
            target_file=ROOT / "src" / "graph_backlog" / "validation.py",
            test_modules=["tests.test_validation"],
            mutation_ids=[0, 1, 34, 47, 61],
            max_mutants=5,
            timeout_seconds=10,
        )

        self.assertEqual(res.total_mutants, 5)
        self.assertEqual(res.killed, 5)
        self.assertEqual(res.survived, 0)
        self.assertEqual(res.timed_out, 0)
        self.assertEqual(res.errored, 0)
        self.assertEqual(res.score_percentage, 100.0)
        self.assertEqual({detail["status"] for detail in res.details}, {"KILLED"})

    def test_curated_core_mutation_canaries_are_killed(self) -> None:
        res = MutationEngine.run_mutation_test(
            target_file=ROOT / "src" / "graph_backlog" / "core.py",
            test_modules=["tests.test_relations"],
            mutation_ids=[5, 7, 12, 16, 33, 35, 38],
            max_mutants=7,
            timeout_seconds=10,
        )

        self.assertEqual(res.total_mutants, 7)
        self.assertEqual(res.killed, 7)
        self.assertEqual(res.survived, 0)
        self.assertEqual(res.timed_out, 0)
        self.assertEqual(res.errored, 0)
        self.assertEqual(res.score_percentage, 100.0)
        self.assertEqual({detail["status"] for detail in res.details}, {"KILLED"})

    def test_curated_grounding_mutation_canaries_are_killed(self) -> None:
        res = MutationEngine.run_mutation_test(
            target_file=ROOT / "src" / "graph_backlog" / "grounding.py",
            test_modules=["tests.test_grounding"],
            mutation_ids=[3, 5, 10, 14, 19, 20, 21, 30, 32],
            max_mutants=9,
            timeout_seconds=10,
        )

        self.assertEqual(res.total_mutants, 9)
        self.assertEqual(res.killed, 9)
        self.assertEqual(res.survived, 0)
        self.assertEqual(res.timed_out, 0)
        self.assertEqual(res.errored, 0)
        self.assertEqual(res.score_percentage, 100.0)
        self.assertEqual({detail["status"] for detail in res.details}, {"KILLED"})

    def test_curated_graph_mutation_canaries_are_killed(self) -> None:
        res = MutationEngine.run_mutation_test(
            target_file=ROOT / "src" / "graph_backlog" / "mutations.py",
            test_modules=[
                "tests.test_adapters_and_mutations::"
                "AdaptersAndMutationsTests::test_add_node_mutation",
                "tests.test_north_star_invariants::"
                "TestCASLandAndSupersede::"
                "test_transaction_defaults_to_atomic_persistence_with_matching_cas",
                "tests.test_north_star_invariants::"
                "TestCASLandAndSupersede::test_supersede_node_creates_acyclic_relation",
            ],
            mutation_ids=[0, 4, 6, 7, 16, 33],
            max_mutants=6,
            timeout_seconds=10,
        )

        self.assertEqual(res.total_mutants, 6)
        self.assertEqual(res.killed, 6)
        self.assertEqual(res.survived, 0)
        self.assertEqual(res.timed_out, 0)
        self.assertEqual(res.errored, 0)
        self.assertEqual(res.score_percentage, 100.0)
        self.assertEqual({detail["status"] for detail in res.details}, {"KILLED"})

    def test_curated_jsonutil_mutation_canaries_are_killed(self) -> None:
        res = MutationEngine.run_mutation_test(
            target_file=ROOT / "src" / "graph_backlog" / "jsonutil.py",
            test_modules=["tests.test_jsonutil"],
            mutation_ids=[4, 21, 22, 24, 26, 27, 28, 31, 32],
            max_mutants=9,
            timeout_seconds=10,
        )

        self.assertEqual(res.total_mutants, 9)
        self.assertEqual(res.killed, 9)
        self.assertEqual(res.survived, 0)
        self.assertEqual(res.timed_out, 0)
        self.assertEqual(res.errored, 0)
        self.assertEqual(res.score_percentage, 100.0)
        self.assertEqual({detail["status"] for detail in res.details}, {"KILLED"})

    def test_pytest_outcomes_are_classified_honestly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch("graph_backlog.mutation_testing.subprocess.run") as run:
                run.return_value = subprocess.CompletedProcess([], 1, stdout="failed")
                killed = MutationEngine._run_pytest(root, ["tests/test_x.py"], 1)
                run.return_value = subprocess.CompletedProcess([], 2, stdout="collection error")
                errored = MutationEngine._run_pytest(root, ["tests/test_x.py"], 1)
                run.side_effect = subprocess.TimeoutExpired([], 1, output="slow")
                timed_out = MutationEngine._run_pytest(root, ["tests/test_x.py"], 1)

        self.assertEqual(killed.status, "KILLED")
        self.assertEqual(errored.status, "ERROR")
        self.assertEqual(timed_out.status, "TIMEOUT")

if __name__ == "__main__":
    unittest.main()
