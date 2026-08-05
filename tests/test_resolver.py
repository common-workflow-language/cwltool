import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from cwltool.resolver import resolve_local


def test_resolve_local_finds_tool_in_commonwl_share(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    share = tmp_path / "share" / "commonwl"
    share.mkdir(parents=True)
    (share / "my-tool.cwl").write_text("cwlVersion: v1.2\n", encoding="utf-8")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    monkeypatch.setenv("XDG_DATA_DIRS", "/nonexistent-share/")
    os.chdir(tmp_path)

    resolved = resolve_local(Mock(), "my-tool.cwl")
    assert resolved == (share / "my-tool.cwl").as_uri()


def test_resolve_local_share_preserves_fragment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    share = tmp_path / "share" / "commonwl"
    share.mkdir(parents=True)
    (share / "my-tool.cwl").write_text("cwlVersion: v1.2\n", encoding="utf-8")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    monkeypatch.setenv("XDG_DATA_DIRS", "/nonexistent-share/")
    os.chdir(tmp_path)

    resolved = resolve_local(Mock(), "my-tool.cwl#main")
    assert resolved == f"{(share / 'my-tool.cwl').as_uri()}#main"


def test_resolve_local_share_with_cwl_extension(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    share = tmp_path / "share" / "commonwl"
    share.mkdir(parents=True)
    (share / "my-tool.cwl").write_text("cwlVersion: v1.2\n", encoding="utf-8")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    monkeypatch.setenv("XDG_DATA_DIRS", "/nonexistent-share/")
    os.chdir(tmp_path)

    resolved = resolve_local(Mock(), "my-tool")
    assert resolved == (share / "my-tool.cwl").as_uri()
