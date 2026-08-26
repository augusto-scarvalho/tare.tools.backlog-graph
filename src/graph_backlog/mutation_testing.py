from __future__ import annotations

import ast
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
                    mutant_ast=node,
                ))
                new_ops.append(target_op if self.target_mutation_index == cand_id else op)
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
                mutant_ast=node,
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
                mutant_ast=node,
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
    timed_out: int
    errored: int
    score_percentage: float
    details: list[dict[str, Any]]


@dataclass
class _TestRun:
    status: str
    duration_sec: float
    output: str


class MutationRunError(RuntimeError):
    """Raised when a mutation run cannot produce trustworthy results."""


class MutationEngine:
    """Discover and evaluate Python mutants in an isolated shadow copy."""

    @staticmethod
    def discover_mutations(source_code: str, filename: str = "<source>") -> list[MutationCandidate]:
        tree = ast.parse(source_code, filename=filename)
        mutator = ASTMutator()
        mutator.filename = filename
        mutator.visit(tree)
        return mutator.candidates

    @staticmethod
    def _repository_root(target_path: Path) -> Path:
        for parent in (target_path.parent, *target_path.parents):
            if (parent / "pyproject.toml").is_file() and (parent / "src" / "graph_backlog").is_dir():
                return parent
        raise MutationRunError(f"Could not find backlog-graph repository root for {target_path}")

    @staticmethod
    def _pytest_targets(test_modules: list[str], repository_root: Path) -> list[str]:
        if not test_modules:
            raise MutationRunError("At least one test module is required")

        targets: list[str] = []
        for value in test_modules:
            selector = ""
            module_or_path = value
            if "::" in value:
                module_or_path, selector = value.split("::", 1)
                selector = f"::{selector}"
            if module_or_path.startswith("tests."):
                module_or_path = module_or_path.replace(".", "/") + ".py"
            candidate = Path(module_or_path)
            if candidate.suffix == ".py":
                test_path = candidate if candidate.is_absolute() else repository_root / candidate
                try:
                    relative = test_path.resolve().relative_to(repository_root)
                except ValueError as exc:
                    raise MutationRunError(f"Test target escapes repository root: {value}") from exc
                if not test_path.is_file():
                    raise MutationRunError(f"Test target does not exist: {value}")
                targets.append(relative.as_posix() + selector)
            else:
                targets.append(value)
        return targets

    @staticmethod
    def _copy_shadow(repository_root: Path, shadow_root: Path) -> None:
        ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")
        for dirname in ("src", "tests", "fixtures", "policies"):
            source = repository_root / dirname
            if source.exists():
                shutil.copytree(source, shadow_root / dirname, ignore=ignore)
        for entrypoint in repository_root.glob("*.py"):
            shutil.copy2(entrypoint, shadow_root / entrypoint.name)
        shutil.copy2(repository_root / "pyproject.toml", shadow_root / "pyproject.toml")

    @staticmethod
    def _run_pytest(
        shadow_root: Path,
        pytest_targets: list[str],
        timeout_seconds: float,
    ) -> _TestRun:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(shadow_root / "src")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONHASHSEED"] = "0"
        command = [sys.executable, "-m", "pytest", *pytest_targets, "-q", "--tb=short"]
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                cwd=shadow_root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            output = exc.stdout or ""
            if isinstance(output, bytes):
                output = output.decode(errors="replace")
            return _TestRun("TIMEOUT", time.monotonic() - started, output)

        if completed.returncode == 0:
            status = "PASS"
        elif completed.returncode == 1:
            status = "KILLED"
        else:
            status = "ERROR"
        return _TestRun(status, time.monotonic() - started, completed.stdout)

    @staticmethod
    def run_mutation_test(
        target_file: Path | str,
        test_modules: list[str],
        max_mutants: int = 40,
        *,
        mutation_ids: list[int] | None = None,
        timeout_seconds: float = 15.0,
    ) -> MutationResult:
        target_path = Path(target_file).resolve()
        if not target_path.is_file() or target_path.suffix != ".py":
            raise MutationRunError(f"Mutation target must be an existing Python file: {target_path}")
        if max_mutants < 0:
            raise MutationRunError("max_mutants cannot be negative")
        if timeout_seconds <= 0:
            raise MutationRunError("timeout_seconds must be positive")

        repository_root = MutationEngine._repository_root(target_path)
        try:
            relative_target = target_path.relative_to(repository_root)
        except ValueError as exc:
            raise MutationRunError("Mutation target must be inside the backlog-graph repository") from exc

        source_bytes = target_path.read_bytes()
        source_hash = hashlib.sha256(source_bytes).hexdigest()
        source_code = source_bytes.decode("utf-8")
        candidates = MutationEngine.discover_mutations(source_code, filename=str(target_path))
        by_id = {candidate.id: candidate for candidate in candidates}

        if mutation_ids is None:
            selected = candidates[:max_mutants]
        else:
            missing = sorted(set(mutation_ids) - set(by_id))
            if missing:
                raise MutationRunError(f"Unknown mutation ids: {missing}")
            selected = [by_id[mutation_id] for mutation_id in mutation_ids[:max_mutants]]

        pytest_targets = MutationEngine._pytest_targets(test_modules, repository_root)
        killed = survived = timed_out = errored = 0
        details: list[dict[str, Any]] = []

        with tempfile.TemporaryDirectory(prefix="backlog-mutants-") as temp_dir:
            shadow_root = Path(temp_dir)
            MutationEngine._copy_shadow(repository_root, shadow_root)
            shadow_target = shadow_root / relative_target
            if not shadow_target.exists():
                shadow_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target_path, shadow_target)

            baseline = MutationEngine._run_pytest(shadow_root, pytest_targets, timeout_seconds)
            if baseline.status != "PASS":
                tail = baseline.output[-2000:].strip()
                raise MutationRunError(
                    f"Mutation baseline did not pass ({baseline.status}).\n{tail}"
                )

            for candidate in selected:
                tree = ast.parse(source_code, filename=str(target_path))
                mutator = ASTMutator(target_mutation_index=candidate.id)
                mutator.filename = str(target_path)
                mutated_tree = mutator.visit(tree)
                ast.fix_missing_locations(mutated_tree)
                mutated_code = ast.unparse(mutated_tree)
                compile(mutated_code, str(shadow_target), "exec")
                shadow_target.write_text(mutated_code, encoding="utf-8")

                run = MutationEngine._run_pytest(shadow_root, pytest_targets, timeout_seconds)
                if run.status == "PASS":
                    survived += 1
                    status = "SURVIVED"
                elif run.status == "KILLED":
                    killed += 1
                    status = "KILLED"
                elif run.status == "TIMEOUT":
                    timed_out += 1
                    status = "TIMEOUT"
                else:
                    errored += 1
                    status = "ERROR"

                detail: dict[str, Any] = {
                    "id": candidate.id,
                    "line": candidate.lineno,
                    "status": status,
                    "description": candidate.description,
                    "duration_sec": round(run.duration_sec, 3),
                }
                if status in {"TIMEOUT", "ERROR"}:
                    detail["output_tail"] = run.output[-2000:].strip()
                details.append(detail)
                shadow_target.write_bytes(source_bytes)

        if hashlib.sha256(target_path.read_bytes()).hexdigest() != source_hash:
            raise MutationRunError(f"Source integrity check failed for {target_path}")

        total = len(selected)
        score = (killed / total * 100.0) if total else 100.0
        return MutationResult(
            total_mutants=total,
            killed=killed,
            survived=survived,
            timed_out=timed_out,
            errored=errored,
            score_percentage=round(score, 1),
            details=details,
        )
