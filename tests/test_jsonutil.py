from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import graph_backlog.jsonutil as jsonutil
from graph_backlog.jsonutil import (
    LockTimeoutError,
    UsageError,
    atomic_write,
    canonical_json,
    dump_formatted,
    graph_lock,
    is_pid_alive,
    to_markdown,
)


def test_canonical_json_preserves_utf8_and_exact_key_order() -> None:
    assert canonical_json({"z": 1, "a": "ação"}) == '{"a":"ação","z":1}'


def test_dump_formatted_contracts_are_distinct_and_unicode_safe(capsys: pytest.CaptureFixture[str]) -> None:
    rows = [{"id": "T-1", "title": "Ação"}]

    dump_formatted(rows, "json")
    json_output = capsys.readouterr().out
    assert json.loads(json_output) == rows
    assert "Ação" in json_output
    assert "\\u00e7" not in json_output

    dump_formatted(rows, "jsonl")
    jsonl = capsys.readouterr().out
    assert jsonl == '{"id": "T-1", "title": "Ação"}\n'

    dump_formatted(rows, "ids")
    assert capsys.readouterr().out == "T-1\n"

    dump_formatted(rows, "md")
    assert capsys.readouterr().out == "- **`T-1`**: Ação\n"

    with pytest.raises(UsageError, match="Unsupported format"):
        dump_formatted(rows, "xml")


def test_markdown_includes_status_cluster_and_unicode() -> None:
    rendered = to_markdown(
        [
            {
                "id": "T-1",
                "title": "Ação",
                "cluster": "núcleo",
                "completion": {"status": "DONE"},
            }
        ]
    )

    assert rendered == "- **`T-1`** `[DONE]` `(núcleo)`: Ação"
    assert "Ação" in to_markdown({"title": "Ação"})


def test_atomic_write_creates_nested_path_and_overwrites_by_default(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "deeper" / "state.json"
    atomic_write(target, "first\n")
    atomic_write(target, "second\n")

    assert target.read_text(encoding="utf-8") == "second\n"

    with pytest.raises(UsageError, match="overwrite=False"):
        atomic_write(target, "third\n", overwrite=False)


def test_atomic_write_retries_a_transient_replace_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "state.json"
    real_replace = jsonutil.os.replace
    attempts = 0

    def flaky_replace(source: str, destination: Path | str) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise PermissionError("transient")
        real_replace(source, destination)

    monkeypatch.setattr(jsonutil.os, "replace", flaky_replace)
    monkeypatch.setattr(jsonutil.time, "sleep", lambda _seconds: None)

    atomic_write(target, "durable\n")

    assert attempts == 2
    assert target.read_text(encoding="utf-8") == "durable\n"


def test_pid_liveness_rejects_non_positive_and_accepts_current_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.name == "nt":
        def reject_posix_probe(pid: int, signal: int) -> None:
            raise AssertionError(
                f"Windows PID liveness must not call os.kill({pid}, {signal})"
            )

        monkeypatch.setattr(jsonutil.os, "kill", reject_posix_probe)

    assert is_pid_alive(0) is False
    assert is_pid_alive(os.getpid()) is True


def test_pid_liveness_uses_non_inheritable_windows_query_handle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, ...]] = []

    class Kernel32:
        @staticmethod
        def OpenProcess(access: int, inherit_handle: bool, pid: int) -> int:
            calls.append(("open", access, inherit_handle, pid))
            return 123

        @staticmethod
        def CloseHandle(handle: int) -> None:
            calls.append(("close", handle))

    monkeypatch.setattr(jsonutil, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(
        jsonutil.ctypes,
        "windll",
        SimpleNamespace(kernel32=Kernel32()),
        raising=False,
    )

    assert is_pid_alive(42) is True
    assert calls == [("open", 0x1000, False, 42), ("close", 123)]


@pytest.mark.parametrize(("last_error", "expected"), [(5, True), (87, False)])
def test_pid_liveness_windows_open_failure_classification(
    monkeypatch: pytest.MonkeyPatch,
    last_error: int,
    expected: bool,
) -> None:
    class Kernel32:
        @staticmethod
        def OpenProcess(access: int, inherit_handle: bool, pid: int) -> int:
            assert (access, inherit_handle, pid) == (0x1000, False, 42)
            return 0

    monkeypatch.setattr(jsonutil, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(
        jsonutil.ctypes,
        "windll",
        SimpleNamespace(kernel32=Kernel32()),
        raising=False,
    )
    monkeypatch.setattr(jsonutil.ctypes, "GetLastError", lambda: last_error, raising=False)

    assert is_pid_alive(42) is expected


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (None, True),
        (PermissionError("denied"), True),
        (ProcessLookupError("missing"), False),
    ],
)
def test_pid_liveness_posix_outcomes(
    monkeypatch: pytest.MonkeyPatch,
    failure: BaseException | None,
    expected: bool,
) -> None:
    def probe(pid: int, signal: int) -> None:
        assert (pid, signal) == (42, 0)
        if failure is not None:
            raise failure

    monkeypatch.setattr(jsonutil, "os", SimpleNamespace(name="posix", kill=probe))

    assert is_pid_alive(42) is expected


def test_graph_lock_creates_nested_parent_and_preserves_utf8_metadata(tmp_path: Path) -> None:
    target = tmp_path / "ação" / "nested" / "graph.json"
    lock_file = target.parent / ".graph.json.lock"

    with graph_lock(target, timeout=1.0) as lock_info:
        assert lock_file.exists()
        raw = lock_file.read_text(encoding="utf-8")
        assert "ação" in raw
        assert json.loads(raw)["lease_token"] == lock_info["lease_token"]

    assert not lock_file.exists()


def test_graph_lock_accepts_an_existing_parent_directory(tmp_path: Path) -> None:
    target = tmp_path / "existing" / "graph.json"
    target.parent.mkdir()

    with graph_lock(target, timeout=1.0):
        assert (target.parent / ".graph.json.lock").exists()


def test_graph_lock_fails_closed_when_lock_already_exists(tmp_path: Path) -> None:
    target = tmp_path / "graph.json"
    lock_file = tmp_path / ".graph.json.lock"
    lock_file.write_text('{"lease_token":"other"}', encoding="utf-8")

    with pytest.raises(LockTimeoutError):
        with graph_lock(target, timeout=0.01):
            pass

    assert lock_file.exists()
