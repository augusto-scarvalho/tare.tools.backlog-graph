from __future__ import annotations
import ast
import copy
import importlib
import io
import os
import sys
import tempfile
import time
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

@dataclass
class MutationCandidate:
    id: int
    filename: str
    lineno: int
    col_offset: int
    description: str
    original_op: str
    mutated_op: str
    mutant_ast: ast.AST

class ASTMutator(ast.NodeTransformer):
    """AST transformer that generates mutation candidates for Python code."""
    
    COMP_MAP = {
        ast.Eq: ast.NotEq,
        ast.NotEq: ast.Eq,
        ast.Lt: ast.GtE,
        ast.Gt: ast.LtE,
        ast.LtE: ast.Gt,
        ast.GtE: ast.Lt,
        ast.Is: ast.IsNot,
        ast.IsNot: ast.Is,
        ast.In: ast.NotIn,
        ast.NotIn: ast.In,
    }

    BOOL_MAP = {
        ast.And: ast.Or,
        ast.Or: ast.And,
    }

    BIN_MAP = {
        ast.Add: ast.Sub,
        ast.Sub: ast.Add,
        ast.Mult: ast.FloorDiv,
    }

    def __init__(self, target_mutation_index: int | None = None) -> None:
        super().__init__()
        self.target_mutation_index = target_mutation_index
        self.current_index = 0
        self.candidates: list[MutationCandidate] = []
        self.filename = "<string>"

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        self.generic_visit(node)
        new_ops = []
        for op in node.ops:
            op_type = type(op)
            if op_type in self.COMP_MAP:
                cand_id = self.current_index
                target_op = self.COMP_MAP[op_type]()
                self.candidates.append(MutationCandidate(
                    id=cand_id,
                    filename=self.filename,
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                    description=f"Change comparison {op_type.__name__} to {type(target_op).__name__}",
                    original_op=op_type.__name__,
                    mutated_op=type(target_op).__name__,
                    mutant_ast=node
                ))
                if self.target_mutation_index == cand_id:
                    new_ops.append(target_op)
                else:
                    new_ops.append(op)
                self.current_index += 1
            else:
                new_ops.append(op)
        node.ops = new_ops
        return node

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        self.generic_visit(node)
        op_type = type(node.op)
        if op_type in self.BOOL_MAP:
            cand_id = self.current_index
            target_op = self.BOOL_MAP[op_type]()
            self.candidates.append(MutationCandidate(
                id=cand_id,
                filename=self.filename,
                lineno=node.lineno,
                col_offset=node.col_offset,
                description=f"Change boolean operator {op_type.__name__} to {type(target_op).__name__}",
                original_op=op_type.__name__,
                mutated_op=type(target_op).__name__,
                mutant_ast=node
            ))
            if self.target_mutation_index == cand_id:
                node.op = target_op
            self.current_index += 1
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if isinstance(node.value, bool):
            cand_id = self.current_index
            new_val = not node.value
            self.candidates.append(MutationCandidate(
                id=cand_id,
                filename=self.filename,
                lineno=node.lineno,
                col_offset=node.col_offset,
                description=f"Invert boolean constant {node.value} -> {new_val}",
                original_op=str(node.value),
                mutated_op=str(new_val),
                mutant_ast=node
            ))
            if self.target_mutation_index == cand_id:
                node.value = new_val
            self.current_index += 1
        return node

@dataclass
class MutationResult:
    total_mutants: int
    killed: int
    survived: int
    errored: int
    score_percentage: float
    details: list[dict[str, Any]]

class MutationEngine:
    """Engine to discover, inject, and evaluate mutations against unit tests."""

    @staticmethod
    def discover_mutations(source_code: str, filename: str = "<source>") -> list[MutationCandidate]:
        tree = ast.parse(source_code, filename=filename)
        mutator = ASTMutator()
        mutator.filename = filename
        mutator.visit(tree)
        return mutator.candidates

    @staticmethod
    def run_tests_on_module(test_modules: list[str]) -> bool:
        """Run unittest suite and return True if all pass, False if any fail."""
        for mod in list(sys.modules.keys()):
            if mod.startswith("graph_backlog") or mod.startswith("tests"):
                del sys.modules[mod]

        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        for mod in test_modules:
            try:
                suite.addTests(loader.loadTestsFromName(mod))
            except Exception:
                return False
        
        stream = io.StringIO()
        runner = unittest.TextTestRunner(stream=stream, verbosity=0)
        result = runner.run(suite)
        return result.wasSuccessful()

    @staticmethod
    def run_mutation_test(
        target_file: Path | str,
        test_modules: list[str],
        max_mutants: int = 40
    ) -> MutationResult:
        target_path = Path(target_file).resolve()
        source_code = target_path.read_text(encoding="utf-8")
        candidates = MutationEngine.discover_mutations(source_code, filename=str(target_path))
        
        total = min(len(candidates), max_mutants)
        killed = 0
        survived = 0
        errored = 0
        details = []

        # Backup original content
        original_bytes = target_path.read_bytes()

        try:
            for idx in range(total):
                cand = candidates[idx]
                # Generate mutated AST
                tree = ast.parse(source_code, filename=str(target_path))
                mutator = ASTMutator(target_mutation_index=idx)
                mutator.filename = str(target_path)
                mutated_tree = mutator.visit(tree)
                ast.fix_missing_locations(mutated_tree)

                mutated_code = ast.unparse(mutated_tree)
                target_path.write_text(mutated_code, encoding="utf-8")

                # Invalidate import caches and reload module
                importlib.invalidate_caches()
                for mname, mobj in list(sys.modules.items()):
                    if hasattr(mobj, "__file__") and mobj.__file__:
                        try:
                            if Path(mobj.__file__).resolve() == target_path:
                                importlib.reload(mobj)
                        except Exception:
                            pass

                # Run test suite
                t0 = time.time()
                passed = MutationEngine.run_tests_on_module(test_modules)
                dt = time.time() - t0

                if passed:
                    # Mutant survived -> test didn't catch the bug
                    survived += 1
                    status = "SURVIVED"
                else:
                    # Mutant killed -> test caught the bug!
                    killed += 1
                    status = "KILLED"

                details.append({
                    "id": cand.id,
                    "line": cand.lineno,
                    "status": status,
                    "description": cand.description,
                    "duration_sec": round(dt, 3)
                })
        finally:
            # Restore original code
            target_path.write_bytes(original_bytes)
            importlib.invalidate_caches()
            for mname, mobj in list(sys.modules.items()):
                if hasattr(mobj, "__file__") and mobj.__file__:
                    try:
                        if Path(mobj.__file__).resolve() == target_path:
                            importlib.reload(mobj)
                    except Exception:
                        pass

        score = (killed / total * 100.0) if total > 0 else 100.0
        return MutationResult(
            total_mutants=total,
            killed=killed,
            survived=survived,
            errored=errored,
            score_percentage=round(score, 1),
            details=details
        )
