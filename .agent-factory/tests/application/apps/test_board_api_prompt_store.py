"""Board API prompt store tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from board.factory_sources import prompts as compat_prompts
from engine.apps.board_api import prompt_store


def test_prompt_file_lifecycle_and_compat_exports(tmp_path) -> None:
    assert compat_prompts._write_prompt_file is prompt_store._write_prompt_file

    result = prompt_store._write_prompt_file(str(tmp_path), "review.txt", "검토 기준")

    assert result == {"ok": True, "name": "review.txt"}
    assert prompt_store._read_prompt_file(str(tmp_path), "review.txt") == {
        "name": "review.txt",
        "content": "검토 기준",
        "size": len("검토 기준".encode("utf-8")),
    }
    assert [item["name"] for item in prompt_store._list_prompt_files(str(tmp_path))] == [
        "review.txt",
    ]

    assert prompt_store._delete_prompt_file(str(tmp_path), "review.txt") == {"ok": True}


@pytest.mark.parametrize("filename", ["../x.txt", "nested/x.txt", "bad name.txt"])
def test_prompt_filename_rejects_path_escape(filename: str) -> None:
    with pytest.raises(ValueError):
        prompt_store._validate_prompt_filename(filename)


def test_quick_prompt_lifecycle(tmp_path) -> None:
    created = prompt_store._write_quick_prompt(
        str(tmp_path),
        "review.default",
        {
            "label": "Review",
            "prompt": "검토해줘",
            "bindTo": "review",
            "description": "default review prompt",
        },
    )

    assert created["ok"] is True
    assert created["items"] == [{
        "id": "review.default",
        "prompt": "검토해줘",
        "label": "Review",
        "bindTo": "review",
        "description": "default review prompt",
    }]
    path = prompt_store._quick_prompts_filepath(str(tmp_path))
    assert json.loads(Path(path).read_text(encoding="utf-8"))["items"][0]["id"] == "review.default"

    updated = prompt_store._write_quick_prompt(
        str(tmp_path),
        "review.default",
        {"prompt": "다시 검토해줘"},
    )
    assert updated["items"][0]["prompt"] == "다시 검토해줘"
    assert updated["items"][0]["label"] == "Review"

    deleted = prompt_store._delete_quick_prompt(str(tmp_path), "review.default")
    assert deleted == {"ok": True, "id": "review.default", "items": []}


def test_quick_prompt_reader_normalizes_missing_or_invalid_files(tmp_path) -> None:
    assert prompt_store._read_quick_prompts(str(tmp_path)) == {"version": 1, "items": []}

    path = prompt_store._quick_prompts_filepath(str(tmp_path))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("{not json", encoding="utf-8")

    assert prompt_store._read_quick_prompts(str(tmp_path)) == {"version": 1, "items": []}


def test_quick_prompt_rejects_invalid_payload(tmp_path) -> None:
    with pytest.raises(ValueError):
        prompt_store._write_quick_prompt(str(tmp_path), "../bad", {"prompt": "x"})
    with pytest.raises(ValueError):
        prompt_store._write_quick_prompt(str(tmp_path), "ok", {"prompt": 1})
