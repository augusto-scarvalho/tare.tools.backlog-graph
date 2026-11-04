from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from graph_backlog.grounding import encode_work_grounding, ground_work_item


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "fixtures" / "sample-backlog.json"


def test_ready_work_grounding_is_bounded_deterministic_and_identified() -> None:
    first = ground_work_item(SAMPLE, "TASK-02")
    second = ground_work_item(SAMPLE, "TASK-02")

    assert first == second
    assert first.schema == "tare.tools/work-grounding/1"
    assert first.status == "READY"
    assert first.authority == "NONE / READ_ONLY PROJECTION"
    assert first.work["title"] == "Build Core Business API"
    assert first.work["kind"] == "task"
    assert first.work["exit_criteria"] == [
        "Endpoints return 200 OK",
        "Contract tests pass",
    ]
    assert first.byte_count == len(encode_work_grounding(first))
    assert first.byte_count <= 8_192
    assert len(first.graph_sha256) == 64
    assert len(first.work_item_sha256) == 64
    assert len(first.execution_scope_sha256) == 64


def test_invalid_work_id_fails_with_a_bounded_input_error() -> None:
    with pytest.raises(ValueError, match="work_id must be a non-empty string"):
        ground_work_item(SAMPLE, 7)  # type: ignore[arg-type]


def test_grounding_report_is_immutable_and_encoding_is_canonical(
    tmp_path: Path,
) -> None:
    raw = json.loads(SAMPLE.read_text(encoding="utf-8"))
    raw["nodes"][1]["title"] = "Execução canônica"
    graph_path = tmp_path / "unicode.json"
    graph_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    report = ground_work_item(graph_path, "TASK-02")
    encoded = encode_work_grounding(report)

    with pytest.raises(FrozenInstanceError):
        report.status = "BLOCKED"  # type: ignore[misc]
    assert "Execução canônica".encode("utf-8") in encoded
    assert encoded.startswith(b'{"authority":')


def test_graph_revision_prefers_declared_projection_identity() -> None:
    report = ground_work_item(SAMPLE, "TASK-02")

    assert report.graph_revision == "proj-sample-001"


def test_budget_trims_optional_downstream_before_failing() -> None:
    full = ground_work_item(SAMPLE, "TASK-02")
    assert len(full.downstream) == 1

    trimmed = ground_work_item(SAMPLE, "TASK-02", max_bytes=full.byte_count - 1)

    assert trimmed.status == "READY"
    assert trimmed.byte_count <= full.byte_count - 1
    assert trimmed.downstream == ()
    assert trimmed.omitted_downstream == 1


def test_scope_fence_ignores_unrelated_metadata_but_detects_item_drift(
    tmp_path: Path,
) -> None:
    baseline = ground_work_item(SAMPLE, "TASK-02")
    raw = json.loads(SAMPLE.read_text(encoding="utf-8"))
    raw["meta"]["generated_at"] = "2099-01-01T00:00:00Z"
    metadata_only = tmp_path / "metadata-only.json"
    metadata_only.write_text(json.dumps(raw), encoding="utf-8")

    unchanged = ground_work_item(
        metadata_only,
        "TASK-02",
        expected_scope_sha256=baseline.execution_scope_sha256,
    )
    assert unchanged.status == "READY"
    assert unchanged.graph_sha256 != baseline.graph_sha256
    assert unchanged.execution_scope_sha256 == baseline.execution_scope_sha256

    raw["nodes"][1]["summary"] = "Changed canonical work scope"
    drifted_path = tmp_path / "drifted.json"
    drifted_path.write_text(json.dumps(raw), encoding="utf-8")
    drifted = ground_work_item(
        drifted_path,
        "TASK-02",
        expected_scope_sha256=baseline.execution_scope_sha256,
    )

    assert drifted.status == "DRIFT"
    assert drifted.reason_codes == ("EXECUTION_SCOPE_CHANGED",)


@pytest.mark.parametrize("edge_index", [0, 1])
def test_scope_fence_detects_inbound_and_outbound_edge_drift(
    tmp_path: Path,
    edge_index: int,
) -> None:
    baseline = ground_work_item(SAMPLE, "TASK-02")
    raw = json.loads(SAMPLE.read_text(encoding="utf-8"))
    raw["edges"][edge_index]["notes"].append("changed incident contract")
    changed_path = tmp_path / f"edge-{edge_index}.json"
    changed_path.write_text(json.dumps(raw), encoding="utf-8")

    changed = ground_work_item(
        changed_path,
        "TASK-02",
        expected_scope_sha256=baseline.execution_scope_sha256,
    )

    assert changed.status == "DRIFT"
    assert changed.reason_codes == ("EXECUTION_SCOPE_CHANGED",)


def test_scope_fence_detects_referenced_source_drift(tmp_path: Path) -> None:
    baseline = ground_work_item(SAMPLE, "TASK-02")
    raw = json.loads(SAMPLE.read_text(encoding="utf-8"))
    raw["sources"]["SRC-INIT"]["title"] = "Changed source contract"
    changed_path = tmp_path / "source.json"
    changed_path.write_text(json.dumps(raw), encoding="utf-8")

    changed = ground_work_item(
        changed_path,
        "TASK-02",
        expected_scope_sha256=baseline.execution_scope_sha256,
    )

    assert changed.status == "DRIFT"
    assert changed.reason_codes == ("EXECUTION_SCOPE_CHANGED",)


def test_work_grounding_projects_explicit_specgraph_selection(tmp_path: Path) -> None:
    raw = json.loads(SAMPLE.read_text(encoding="utf-8"))
    raw["nodes"][1].update(
        {
            "target_repositories": ["tare.tools.agent-runtime"],
            "grounding_refs": ["adr-agent-loop", "contract-turn-request"],
            "target_paths": ["src/tare_tools_agent_runtime/runtime.py"],
            "target_symbols": ["AgentRuntime.run"],
        }
    )
    graph_path = tmp_path / "work-selection.json"
    graph_path.write_text(json.dumps(raw), encoding="utf-8")

    report = ground_work_item(graph_path, "TASK-02")

    assert report.status == "READY"
    assert report.work["target_repositories"] == ["tare.tools.agent-runtime"]
    assert report.work["grounding_refs"] == [
        "adr-agent-loop",
        "contract-turn-request",
    ]
    assert report.work["target_paths"] == [
        "src/tare_tools_agent_runtime/runtime.py"
    ]
    assert report.work["target_symbols"] == ["AgentRuntime.run"]
    assert report.work["repository_scopes"] == [
        {
            "repository": "tare.tools.agent-runtime",
            "grounding_refs": ["adr-agent-loop", "contract-turn-request"],
            "target_paths": ["src/tare_tools_agent_runtime/runtime.py"],
            "target_symbols": ["AgentRuntime.run"],
        }
    ]


def test_multirepository_scope_is_explicit_and_deterministic(tmp_path: Path) -> None:
    raw = json.loads(SAMPLE.read_text(encoding="utf-8"))
    raw["nodes"][1]["repository_scopes"] = [
        {
            "repository": "repo-b",
            "grounding_refs": ["B"],
            "target_paths": ["src/b.py"],
            "target_symbols": [],
        },
        {
            "repository": "repo-a",
            "grounding_refs": ["A"],
            "target_paths": ["src/a.py"],
            "target_symbols": ["a"],
        },
    ]
    graph_path = tmp_path / "multi.json"
    graph_path.write_text(json.dumps(raw), encoding="utf-8")

    report = ground_work_item(graph_path, "TASK-02")

    assert report.status == "READY"
    assert report.work["target_repositories"] == ["repo-a", "repo-b"]
    assert [scope["repository"] for scope in report.work["repository_scopes"]] == [
        "repo-a",
        "repo-b",
    ]


@pytest.mark.parametrize(
    "selection",
    [
        {"target_repositories": ["repo-a", "repo-b"]},
        {
            "repository_scopes": [
                {
                    "repository": "repo-a",
                    "grounding_refs": [],
                    "target_paths": [],
                    "target_symbols": [],
                }
            ],
            "target_repositories": ["repo-a"],
        },
    ],
)
def test_ambiguous_multirepository_selection_fails_closed(
    tmp_path: Path, selection: dict[str, object]
) -> None:
    raw = json.loads(SAMPLE.read_text(encoding="utf-8"))
    raw["nodes"][1].update(selection)
    graph_path = tmp_path / "ambiguous.json"
    graph_path.write_text(json.dumps(raw), encoding="utf-8")

    report = ground_work_item(graph_path, "TASK-02")

    assert report.status == "SOURCE_INVALID"


def test_blocked_and_unbounded_items_fail_closed(tmp_path: Path) -> None:
    blocked = ground_work_item(SAMPLE, "TASK-03")
    assert blocked.status == "BLOCKED"

    raw = json.loads(SAMPLE.read_text(encoding="utf-8"))
    raw["nodes"][1]["exit_criteria"] = []
    unbounded_path = tmp_path / "unbounded.json"
    unbounded_path.write_text(json.dumps(raw), encoding="utf-8")
    unbounded = ground_work_item(unbounded_path, "TASK-02")

    assert unbounded.status == "UNBOUNDED_WORK"
    assert unbounded.reason_codes == ("EXIT_CRITERIA_MISSING",)


def test_cli_stdout_is_exact_declared_bytes() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "graph_backlog.cli",
            "--format",
            "json",
            "ground",
            "TASK-02",
            "--work-graph",
            str(SAMPLE),
        ],
        check=False,
        capture_output=True,
        cwd=ROOT,
    )
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["status"] == "READY"
    assert len(completed.stdout) == payload["byte_count"]
    assert not completed.stdout.endswith(b"\n")


def test_markdown_packet_contains_no_frozen_harness_directive() -> None:
    from graph_backlog.core import WorkGraph
    from graph_backlog.packet import format_packet_markdown, generate_packet

    graph = WorkGraph(json.loads(SAMPLE.read_text(encoding="utf-8")))
    rendered = format_packet_markdown(generate_packet(graph, "TASK-02"))

    assert "universal-agent-harness-prototype" not in rendered
    assert "MANDATORY IMPLEMENTATION DIRECTIVE" not in rendered
    assert "grants no Authority" in rendered
