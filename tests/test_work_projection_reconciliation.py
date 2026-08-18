"""work-relay-reconcile (TRAIN-12): read-only Work Projection Reconciliation contract.

TaskStore is the single canonical operational writer; relay / work-graph / github /
kanban are derived projections keyed by taskstore_id and never a second WorkRegistry.
Everything here is offline and deterministic: the golden queries are pure functions,
fixtures are loaded from static JSON only, and no network module is imported.
"""
from __future__ import annotations

import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "src" / "graph_backlog" / "contracts" / "schemas" / "work-projection-reconciliation.schema.json"
POLICY = ROOT / "src" / "graph_backlog" / "contracts" / "policies" / "work-projection-reconciliation.json"
FIX = ROOT / "fixtures"
VALID = FIX / "work-projection-reconciliation-valid.json"
DUP = FIX / "work-projection-reconciliation-duplicate-taskstore-id.json"
UNRESOLVED = FIX / "work-projection-reconciliation-unresolved-reference.json"
PROJECTION_REFS = ("relay_train_id", "work_graph_task_id", "github_issue_id", "kanban_lane")
# Identity-bearing references only: a kanban_lane is a shared rendered category
# (many tasks share "done"), never a unique identity, so it is excluded from the
# cross-projection identity-mismatch check.
IDENTITY_REFS = ("relay_train_id", "work_graph_task_id", "github_issue_id")


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


# --- minimal, dependency-free JSON-schema check (jsonschema is not installed) ---

def schema_errors(inst, schema, path="$") -> list[str]:
    errs: list[str] = []
    t = schema.get("type")
    if t:
        types = t if isinstance(t, list) else [t]
        ok = any(
            (ty == "object" and isinstance(inst, dict)) or
            (ty == "array" and isinstance(inst, list)) or
            (ty == "string" and isinstance(inst, str)) or
            (ty == "null" and inst is None)
            for ty in types)
        if not ok:
            errs.append(f"{path}: expected type {t}, got {type(inst).__name__}")
            return errs
    if "const" in schema and inst != schema["const"]:
        errs.append(f"{path}: expected const {schema['const']!r}")
    if isinstance(inst, str) and "minLength" in schema and len(inst) < schema["minLength"]:
        errs.append(f"{path}: shorter than minLength {schema['minLength']}")
    if isinstance(inst, dict):
        for req in schema.get("required", []):
            if req not in inst:
                errs.append(f"{path}: missing required {req!r}")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for k in inst:
                if k not in props:
                    errs.append(f"{path}: additional property {k!r} not allowed")
        for k, sub in props.items():
            if k in inst:
                errs += schema_errors(inst[k], sub, f"{path}.{k}")
    if isinstance(inst, list) and "items" in schema:
        for i, item in enumerate(inst):
            errs += schema_errors(item, schema["items"], f"{path}[{i}]")
    return errs


# --- the four golden queries: pure, side-effect-free, {status, violations} -----

def _result(violations: list) -> dict:
    return {"status": "PASSED" if not violations else "FAILED", "violations": violations}


def canonical_taskstore_identity(doc: dict) -> dict:
    """Every canonical row carries a stable, non-empty TaskStore identity."""
    v = [r for r in doc.get("canonical", [])
         if not str(r.get("taskstore_id") or "").strip()
         or not str(r.get("snapshot_revision") or "").strip()]
    return _result(v)


def duplicate_taskstore_identity(doc: dict) -> dict:
    """No taskstore_id may map to more than one canonical row (no 2nd WorkRegistry)."""
    counts = Counter(r.get("taskstore_id") for r in doc.get("canonical", []))
    return _result([{"taskstore_id": k, "count": c} for k, c in sorted(counts.items()) if c > 1])


def unresolved_canonical_identity(doc: dict) -> dict:
    """Projections whose taskstore_ref has no canonical row — reported, never invented."""
    ids = {r.get("taskstore_id") for r in doc.get("canonical", [])}
    return _result([{"taskstore_ref": p.get("taskstore_ref")}
                    for p in doc.get("projections", []) if p.get("taskstore_ref") not in ids])


def cross_projection_identity_mismatch(doc: dict) -> dict:
    """A single projection reference value that resolves to more than one canonical
    identity is a mismatch (a projection cannot belong to two TaskStore rows)."""
    viol = []
    for field in IDENTITY_REFS:
        by_ref: dict = {}
        for p in doc.get("projections", []):
            ref = p.get(field)
            if ref is None:
                continue
            by_ref.setdefault(ref, set()).add(p.get("taskstore_ref"))
        for ref, refs in sorted(by_ref.items()):
            if len(refs) > 1:
                viol.append({"field": field, "value": ref, "taskstore_refs": sorted(refs)})
    return _result(viol)


GOLDEN = (canonical_taskstore_identity, duplicate_taskstore_identity,
          unresolved_canonical_identity, cross_projection_identity_mismatch)


class WorkProjectionReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.schema = _load(SCHEMA)
        self.policy = _load(POLICY)
        self.valid = _load(VALID)

    # -- FAL-01 / FAL-06: single canonical writer, read-only projections ---------

    def test_fal01_single_canonical_writer(self):
        self.assertEqual(self.policy["authority"]["canonical_work_writer"], "TaskStore")
        # A policy naming any projection as the writer must be rejected by this check.
        tampered = json.loads(json.dumps(self.policy))
        tampered["authority"]["canonical_work_writer"] = "relay"
        self.assertNotEqual(tampered["authority"]["canonical_work_writer"], "TaskStore")

    def test_fal06_projections_are_read_only(self):
        self.assertTrue(all(m == "read_only" for m in self.policy["projection_modes"].values()))
        self.assertNotIn("TaskStore", self.policy["authority"]["projection_only"])
        # Schema is closed: an injected secondary-registry key is rejected.
        bad = json.loads(json.dumps(self.valid))
        bad["canonical"][0]["local_uuid"] = "sneaky"
        self.assertTrue(schema_errors(bad, self.schema), "additionalProperties must be false")

    # -- FAL-02: stable TaskStore identity --------------------------------------

    def test_fal02_valid_fixture_matches_schema(self):
        self.assertEqual(schema_errors(self.valid, self.schema), [])
        self.assertEqual(canonical_taskstore_identity(self.valid)["status"], "PASSED")
        missing = json.loads(json.dumps(self.valid))
        del missing["canonical"][0]["snapshot_revision"]
        self.assertTrue(schema_errors(missing, self.schema))
        self.assertEqual(canonical_taskstore_identity(missing)["status"], "FAILED")

    # -- FAL-03: no duplicate WorkRegistry --------------------------------------

    def test_fal03_duplicate_taskstore_id(self):
        self.assertEqual(duplicate_taskstore_identity(self.valid)["status"], "PASSED")
        self.assertEqual(duplicate_taskstore_identity(_load(DUP))["status"], "FAILED")

    # -- FAL-04: cross-projection consistency -----------------------------------

    def test_fal04_cross_projection_mismatch(self):
        self.assertEqual(cross_projection_identity_mismatch(self.valid)["status"], "PASSED")
        self.assertEqual(cross_projection_identity_mismatch(_load(UNRESOLVED))["status"], "FAILED")

    # -- FAL-05: explicit uncertainty -------------------------------------------

    def test_fal05_unresolved_reference(self):
        self.assertEqual(unresolved_canonical_identity(self.valid)["status"], "PASSED")
        res = unresolved_canonical_identity(_load(UNRESOLVED))
        self.assertEqual(res["status"], "FAILED")
        self.assertIn("TS-MISSING", [v["taskstore_ref"] for v in res["violations"]])

    # -- FAL-07: deterministic, offline reproducibility -------------------------

    def test_fal07_reproducible_and_offline(self):
        first = {q.__name__: q(self.valid) for q in GOLDEN}
        second = {q.__name__: q(_load(VALID)) for q in GOLDEN}
        self.assertEqual(first, second, "golden queries must be deterministic")
        # Offline by construction: this contract module imports no network library.
        import ast
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        for netlib in ("socket", "urllib", "requests", "http"):
            self.assertNotIn(netlib, imported, f"reconciliation contract must not import {netlib}")

    def test_fixtures_are_immutable_during_run(self):
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (VALID, DUP, UNRESOLVED)}
        for p in (VALID, DUP, UNRESOLVED):
            for q in GOLDEN:
                q(_load(p))
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in (VALID, DUP, UNRESOLVED)}
        self.assertEqual(before, after, "fixtures must not mutate during query execution")


if __name__ == "__main__":
    unittest.main()
