from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology" / "domain_ontology.yaml"


def _concept_blocks(text: str) -> list[str]:
    marker = "\n  - id: "
    return [marker + block for block in text.split(marker)[1:]]


def test_repository_ontology_has_complete_unique_concepts() -> None:
    text = ONTOLOGY.read_text(encoding="utf-8")
    assert text.startswith('version: "1.0.0"\n')
    assert '\ngovernance: "ADR-001"\n' in text

    blocks = _concept_blocks(text)
    assert len(blocks) == 4
    ids = []
    required_fields = (
        '\n    name: "',
        '\n    domain: "',
        '\n    governing_adr: "ADR-001"',
        '\n    governing_spec: "SPEC-BACKLOG-001"',
        '\n    definition: "',
        "\n    invariants:\n",
        "\n    relationships:\n",
    )
    for block in blocks:
        first_line = block.splitlines()[1]
        concept_id = first_line.removeprefix('  - id: "').removesuffix('"')
        assert concept_id
        ids.append(concept_id)
        assert all(field in block for field in required_fields)

    assert len(ids) == len(set(ids))
    assert ids == [
        "DeterministicExecutionFrontier",
        "TypedDependencySemantics",
        "CasLeasedGraphMutation",
        "AtomicReopenCascade",
    ]
