from __future__ import annotations
import os
import time
import pytest
from pathlib import Path

from graph_backlog.jsonutil import (
    graph_lock,
    LockTimeoutError,
    RevisionMismatchError,
    canonical_json,
    sha256_canonical,
    compute_revision_hash
)
from graph_backlog.core import WorkGraph
from graph_backlog.algorithms import (
    compute_frontier,
    ranked_next,
    downstream_critical_depth,
    frontier_sort_key
)
from graph_backlog.mutations import (
    land_train_tasks,
    supersede_node_in_graph,
    add_node_to_graph
)

class TestNorthStarLockAndCanonicalHash:
    """Verifies BG-01 Lockfile and BG-02 JCS Canonical Digest invariants."""

    def test_graph_lock_acquisition_and_release(self, tmp_path: Path):
        graph_file = tmp_path / "work-graph.json"
        graph_file.write_text("{}", encoding="utf-8")
        lock_file = tmp_path / ".work-graph.json.lock"

        assert not lock_file.exists()
        with graph_lock(graph_file, timeout=2.0) as lock_info:
            assert lock_file.exists()
            assert lock_info["pid"] == os.getpid()
            assert "lease_token" in lock_info

        assert not lock_file.exists(), "Lockfile must be unlinked upon context exit"

    def test_graph_lock_contention_raises_timeout(self, tmp_path: Path):
        graph_file = tmp_path / "work-graph.json"
        graph_file.write_text("{}", encoding="utf-8")

        with graph_lock(graph_file, timeout=2.0):
            # Attempt concurrent acquisition on same file
            with pytest.raises(LockTimeoutError) as exc:
                with graph_lock(graph_file, timeout=0.2):
                    pass
            assert "Could not acquire exclusive lock" in str(exc.value)

    def test_graph_lock_stale_reclaim(self, tmp_path: Path):
        graph_file = tmp_path / "work-graph.json"
        graph_file.write_text("{}", encoding="utf-8")
        lock_file = tmp_path / ".work-graph.json.lock"

        # Create simulated stale lock from 100 seconds ago
        lock_file.write_text('{"pid": 999999, "lease_token": "old"}', encoding="utf-8")
        past_time = time.time() - 100
        os.utime(str(lock_file), (past_time, past_time))

        # Acquisition should safely reclaim the stale lock (>30s)
        with graph_lock(graph_file, timeout=1.0, stale_age_s=30.0) as lock_info:
            assert lock_info["pid"] == os.getpid()

        assert not lock_file.exists()

    def test_revision_hash_omits_revision_field(self):
        graph_v1 = {
            "schema_version": "2.0",
            "revision": "r0_initial_sha",
            "nodes": [{"id": "T1", "priority": "P0"}]
        }
        graph_v2 = {
            "schema_version": "2.0",
            "revision": "r1_different_revision_string",
            "nodes": [{"id": "T1", "priority": "P0"}]
        }

        # The content-addressed revision hash MUST be identical because the payload minus 'revision' is identical
        h1 = compute_revision_hash(graph_v1)
        h2 = compute_revision_hash(graph_v2)
        assert h1 == h2
        assert len(h1) == 64

    def test_jcs_canonical_dict_order_invariance(self):
        d1 = {"b": 2, "a": 1, "nested": {"z": 9, "m": 5}}
        d2 = {"nested": {"m": 5, "z": 9}, "a": 1, "b": 2}

        # Key ordering must produce byte-for-byte identical JCS JSON
        assert canonical_json(d1) == canonical_json(d2)
        assert sha256_canonical(d1) == sha256_canonical(d2)

class TestTotalOrderingFrontier:
    """Verifies BG-03 Total Ordering (Priority -> Depth -> ID) invariants."""

    def test_frontier_total_order_priority_depth_id(self):
        sample_graph = {
            "schema_version": "2.0",
            "nodes": [
                {
                    "id": "TASK-LOW-P2",
                    "title": "Low priority task",
                    "priority": "P2",
                    "kind": "task",
                    "completion": {"status": "NOT_DONE"}
                },
                {
                    "id": "TASK-P0-SHALLOW",
                    "title": "P0 with no downstream",
                    "priority": "P0",
                    "kind": "task",
                    "completion": {"status": "NOT_DONE"}
                },
                {
                    "id": "TASK-P0-DEEP",
                    "title": "P0 unlocking long downstream chain",
                    "priority": "P0",
                    "kind": "task",
                    "completion": {"status": "NOT_DONE"}
                },
                {
                    "id": "TASK-P1-ALPHA",
                    "title": "P1 task alpha",
                    "priority": "P1",
                    "kind": "task",
                    "completion": {"status": "NOT_DONE"}
                },
                {
                    "id": "TASK-DOWNSTREAM-1",
                    "title": "Downstream 1",
                    "priority": "P1",
                    "kind": "task",
                    "completion": {"status": "NOT_DONE"}
                },
                {
                    "id": "TASK-DOWNSTREAM-2",
                    "title": "Downstream 2",
                    "priority": "P1",
                    "kind": "task",
                    "completion": {"status": "NOT_DONE"}
                }
            ],
            "edges": [
                {"from": "TASK-P0-DEEP", "to": "TASK-DOWNSTREAM-1", "type": "BLOCKS", "semantic": True},
                {"from": "TASK-DOWNSTREAM-1", "to": "TASK-DOWNSTREAM-2", "type": "BLOCKS", "semantic": True}
            ]
        }

        wg = WorkGraph(sample_graph)
        frontier = compute_frontier(wg)
        frontier_ids = [n["id"] for n in frontier]

        # 1. TASK-P0-DEEP (P0 + depth 2) must be #1
        # 2. TASK-P0-SHALLOW (P0 + depth 0) must be #2
        # 3. TASK-P1-ALPHA (P1) must be #3
        # 4. TASK-LOW-P2 (P2) must be #4
        assert frontier_ids[0] == "TASK-P0-DEEP"
        assert frontier_ids[1] == "TASK-P0-SHALLOW"
        assert frontier_ids[2] == "TASK-P1-ALPHA"
        assert frontier_ids[3] == "TASK-LOW-P2"

class TestCASLandAndSupersede:
    """Verifies BG-04 Supersede and BG-05 CAS Land invariants."""

    def _base_valid_graph(self) -> WorkGraph:
        base = {
            "meta": {"schema": "work-graph-poc/0.5", "generated_at": "2026-08-17T00:00:00Z"},
            "nodes": [],
            "edges": []
        }
        return WorkGraph(base)

    def test_cas_landing_success_and_revision_update(self):
        wg = self._base_valid_graph()
        g1 = add_node_to_graph(wg, "TASK-01", "Task 1", priority="P0")
        wg1 = WorkGraph(g1)
        current_rev = compute_revision_hash(wg1.to_dict())

        # Land with exact matching expected revision
        landed_dict = land_train_tasks(
            wg1,
            train_id="TRAIN-01",
            task_ids=["TASK-01"],
            evidence_summary="Pytest 100% green",
            expected_rev=current_rev
        )

        landed_node = next(n for n in landed_dict["nodes"] if n["id"] == "TASK-01")
        assert landed_node["completion"]["status"] == "DONE"
        assert landed_node["completion"]["dod_satisfied"] is True
        assert landed_node["completion"]["landed_train"] == "TRAIN-01"
        assert "Landed in train TRAIN-01: Pytest 100% green" in landed_node["completion"]["dod_evidence"]

        # The new revision must be different from current_rev
        new_rev = landed_dict["revision"]
        assert new_rev != current_rev
        assert new_rev == compute_revision_hash(landed_dict)

    def test_cas_landing_mismatch_raises_revision_mismatch_error(self):
        wg = self._base_valid_graph()
        g1 = add_node_to_graph(wg, "TASK-01", "Task 1", priority="P0")
        wg1 = WorkGraph(g1)

        with pytest.raises(RevisionMismatchError) as exc:
            land_train_tasks(
                wg1,
                train_id="TRAIN-01",
                task_ids=["TASK-01"],
                expected_rev="stale_revision_hash_12345"
            )
        assert "CAS conflict during landing of train" in str(exc.value)

    def test_supersede_node_creates_acyclic_relation(self):
        wg = self._base_valid_graph()
        g1 = add_node_to_graph(wg, "TASK-OLD", "Legacy approach", priority="P1")
        g2 = add_node_to_graph(WorkGraph(g1), "TASK-NEW", "New approach", priority="P0")
        wg2 = WorkGraph(g2)

        superseded_dict = supersede_node_in_graph(
            wg2,
            node_id="TASK-OLD",
            superseded_by_id="TASK-NEW",
            reason="Architecture refactored in ADR-046"
        )

        old_node = next(n for n in superseded_dict["nodes"] if n["id"] == "TASK-OLD")
        assert old_node["completion"]["status"] == "SUPERSEDED"
        assert old_node["completion"]["superseded_by"] == "TASK-NEW"
        assert old_node["completion"]["supersession_reason"] == "Architecture refactored in ADR-046"

        edge = next(e for e in superseded_dict["edges"] if e["type"] == "SUPERSEDED_BY")
        assert edge["from"] == "TASK-OLD"
        assert edge["to"] == "TASK-NEW"

class TestDoctorRecoveryAndSchemaMigration:
    """Verifies BG-07 Doctor Recovery and BG-09 Schema Migration invariants."""

    def test_migrate_v05_to_v10(self):
        from graph_backlog.validation import migrate_v05_to_v10
        legacy = {
            "meta": {"schema": "work-graph-poc/0.5"},
            "nodes": [
                {
                    "id": "TASK-LEGACY",
                    "title": "Legacy task",
                    "completion": {"status": "DONE"}
                }
            ],
            "edges": []
        }
        migrated = migrate_v05_to_v10(legacy)
        assert migrated["schema_version"] == "1.0.0"
        assert migrated["meta"]["schema"] == "tare.tools/work-graph/1.0"
        assert migrated["nodes"][0]["completion"]["dod_satisfied"] is True
        assert "revision" in migrated
        assert migrated["revision"] == compute_revision_hash(migrated)

    def test_doctor_recovery_cleans_tmp_and_stabilizes_revision(self, tmp_path: Path):
        from graph_backlog.validation import doctor_recover
        graph_file = tmp_path / "work-graph.json"
        base_raw = {
            "meta": {"schema": "work-graph-poc/0.5"},
            "nodes": [],
            "edges": []
        }
        graph_file.write_text(canonical_json(base_raw), encoding="utf-8")

        # Simulate orphaned .tmp file from crashed write (>60s ago)
        stale_tmp = tmp_path / ".work-graph.json.tmp999"
        stale_tmp.write_text("crash artifact", encoding="utf-8")
        past = time.time() - 100
        os.utime(str(stale_tmp), (past, past))

        res = doctor_recover(graph_file)
        assert res["status"] in ("RECOVERED", "STABLE")
        assert not stale_tmp.exists(), "Doctor recover must remove orphaned tmp artifacts"
        assert res["revision"] is not None
