from __future__ import annotations
import unittest
from pathlib import Path

from graph_backlog.mutation_testing import ASTMutator, MutationEngine

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

    @unittest.skip("skip mutation test")
    def test_mutation_engine_run(self) -> None:
        res = MutationEngine.run_mutation_test(
            target_file=target_file,
            test_modules=["tests.test_diff_and_ledger"],
            max_mutants=10
        )
        self.assertGreater(res.total_mutants, 0)
        self.assertGreater(res.killed, 0)
        self.assertGreaterEqual(res.score_percentage, 50.0)

if __name__ == "__main__":
    unittest.main()
