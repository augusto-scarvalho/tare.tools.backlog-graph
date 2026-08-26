from __future__ import annotations

import json
from pathlib import Path

import pytest

from graph_backlog.delivery_evidence import EvidencePolicyError, classify_delivery, main


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "policies" / "delivery-evidence.json"


def test_mixed_diff_uses_highest_floor_and_observes_underclassification() -> None:
    receipt = classify_delivery(
        MANIFEST,
        ["README.md", "src/graph_backlog/jsonutil.py"],
        "E1_LOCAL_BEHAVIOR",
        graph_status="READY_TRUNCATED",
    )
    assert receipt["effective_class"] == "E3_CRITICAL"
    assert receipt["would_hold"] is True
    assert receipt["delivery_state"] == "HELD"
    assert receipt["evidence_gaps"] == ["specgraph_output_truncated"]
    assert receipt["graph_evidence"]["admission_authority"] is False
    assert receipt["admission_enforced"] is False


def test_parent_manifest_prevents_in_band_floor_reduction(tmp_path: Path) -> None:
    candidate = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for surface in candidate["surfaces"]:
        if surface["id"] == "canonical-identity-ledger-recovery":
            surface["class"] = "E0_NON_EXECUTABLE"
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

    receipt = classify_delivery(
        candidate_path,
        ["src/graph_backlog/jsonutil.py"],
        "E0_NON_EXECUTABLE",
        parent_manifest_path=MANIFEST,
    )
    assert receipt["manifest_basis"] == "parent"
    assert receipt["effective_class"] == "E3_CRITICAL"
    assert receipt["would_hold"] is True


def test_named_critical_floor_survives_an_already_weakened_parent(tmp_path: Path) -> None:
    weakened = json.loads(MANIFEST.read_text(encoding="utf-8"))
    weakened["surfaces"] = [surface for surface in weakened["surfaces"] if surface["id"] != "canonical-identity-ledger-recovery"]
    weakened_path = tmp_path / "weakened-parent.json"
    weakened_path.write_text(json.dumps(weakened), encoding="utf-8")

    receipt = classify_delivery(
        MANIFEST,
        ["src/graph_backlog/jsonutil.py"],
        "E0_NON_EXECUTABLE",
        parent_manifest_path=weakened_path,
    )
    assert receipt["effective_class"] == "E3_CRITICAL"
    assert receipt["paths"][0]["rules"] == [{"rule": "builtin_named_e3_floor", "class": "E3_CRITICAL"}]


def test_manifest_has_a_builtin_e3_floor() -> None:
    receipt = classify_delivery(MANIFEST, ["policies/delivery-evidence.json"], "E2_OPERATIONAL")
    assert receipt["effective_class"] == "E3_CRITICAL"
    assert receipt["paths"][0]["rules"][0]["rule"] == "builtin_manifest_authority"
    assert receipt["manifest_basis"] == "bootstrap_candidate"


def test_classifier_code_is_part_of_classification_authority() -> None:
    receipt = classify_delivery(MANIFEST, ["src/graph_backlog/delivery_evidence.py"], "E2_OPERATIONAL")
    assert receipt["effective_class"] == "E3_CRITICAL"
    assert receipt["would_hold"] is True


@pytest.mark.parametrize("path", ["scripts/new_helper.py", "scripts/new_helper.psm1", "scripts/new_helper"])
def test_unmapped_executable_is_never_e0(path: str) -> None:
    receipt = classify_delivery(MANIFEST, [path], "E0_NON_EXECUTABLE")
    assert receipt["effective_class"] == "E1_LOCAL_BEHAVIOR"
    assert receipt["would_hold"] is True


def test_case_alias_cannot_bypass_a_named_e3_floor() -> None:
    receipt = classify_delivery(MANIFEST, ["SRC/graph_backlog/jsonutil.py"], "E1_LOCAL_BEHAVIOR")
    assert receipt["effective_class"] == "E3_CRITICAL"
    assert receipt["would_hold"] is True


def test_missing_repository_mapping_remains_a_visible_gap() -> None:
    receipt = classify_delivery(MANIFEST, ["README.md"], "E0_NON_EXECUTABLE", graph_status="NOT_MAPPED")
    assert receipt["effective_class"] == "E0_NON_EXECUTABLE"
    assert receipt["evidence_gaps"] == ["specgraph_repository_not_mapped"]
    assert receipt["would_hold"] is False


def test_cli_receipt_is_canonical_and_deterministic(capsys: pytest.CaptureFixture[str]) -> None:
    args = ["--manifest", str(MANIFEST), "--declared", "E0_NON_EXECUTABLE", "--path", "README.md", "--graph-status", "READY"]
    assert main(args) == 0
    first = capsys.readouterr().out
    assert main(args) == 0
    second = capsys.readouterr().out
    assert first == second
    assert json.loads(first)["delivery_state"] == "PREPARED"


@pytest.mark.parametrize("path", ["../escape.py", "/absolute.py", "C:\\escape.py", "C:/escape.py", "\\\\server\\share\\escape.py", ""])
def test_invalid_paths_fail_closed(path: str) -> None:
    with pytest.raises(EvidencePolicyError):
        classify_delivery(MANIFEST, [path], "E1_LOCAL_BEHAVIOR")
