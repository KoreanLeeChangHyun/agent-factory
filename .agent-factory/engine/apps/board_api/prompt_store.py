"""Prompt and quick-prompt storage for Board API endpoints."""

from __future__ import annotations

import json
import os
import re
import time


PROMPT_FILES_PATH: str = os.path.join(
    ".agent-factory", "board", "config", "prompt-files",
)
QUICK_PROMPTS_PATH: str = os.path.join(
    ".agent-factory", "board", "config", "quick-prompts.json",
)

_PROMPT_FILENAME_RE = re.compile(r"^[A-Za-z0-9_\-\.]+$")
_QUICK_PROMPT_ID_RE = re.compile(r"^[A-Za-z0-9_\-\.]+$")


def _prompt_files_dir(project_root: str) -> str:
    """internal helper — return the prompt-files directory."""
    return os.path.join(project_root, PROMPT_FILES_PATH)


def _validate_prompt_filename(filename: str) -> None:
    """internal helper — validate a prompt filename before file access."""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise ValueError(f"Invalid filename: {filename}")
    if not _PROMPT_FILENAME_RE.match(filename):
        raise ValueError(f"Invalid filename format: {filename}")


def _list_prompt_files(project_root: str) -> list[dict]:
    """internal helper — list prompt files for the Board API."""
    prompt_dir = _prompt_files_dir(project_root)
    if not os.path.isdir(prompt_dir):
        return []

    files: list[dict] = []
    try:
        for entry in os.scandir(prompt_dir):
            if not entry.is_file():
                continue
            if entry.name.startswith(".") or entry.name == "__pycache__":
                continue
            try:
                stat = entry.stat()
                files.append({
                    "name": entry.name,
                    "size": stat.st_size,
                    "mtime": time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime),
                    ),
                })
            except OSError:
                pass
    except OSError:
        return []

    files.sort(key=lambda f: f["name"])
    return files


def _read_prompt_file(project_root: str, filename: str) -> dict:
    """internal helper — read one prompt file."""
    _validate_prompt_filename(filename)
    filepath = os.path.join(_prompt_files_dir(project_root), filename)

    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Prompt file not found: {filename}")

    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    return {
        "name": filename,
        "content": content,
        "size": len(content.encode("utf-8")),
    }


def _write_prompt_file(project_root: str, filename: str, content: str) -> dict:
    """internal helper — create or update one prompt file."""
    _validate_prompt_filename(filename)
    prompt_dir = _prompt_files_dir(project_root)
    os.makedirs(prompt_dir, exist_ok=True)
    filepath = os.path.join(prompt_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return {"ok": True, "name": filename}


def _delete_prompt_file(project_root: str, filename: str) -> dict:
    """internal helper — delete one prompt file."""
    _validate_prompt_filename(filename)
    filepath = os.path.join(_prompt_files_dir(project_root), filename)

    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Prompt file not found: {filename}")

    os.remove(filepath)
    return {"ok": True}


def _validate_quick_prompt_id(prompt_id: str) -> None:
    """internal helper — validate a quick prompt id before file access."""
    if not isinstance(prompt_id, str) or not prompt_id:
        raise ValueError("Empty quick prompt id")
    if ".." in prompt_id or "/" in prompt_id or "\\" in prompt_id:
        raise ValueError(f"Invalid quick prompt id: {prompt_id}")
    if not _QUICK_PROMPT_ID_RE.match(prompt_id):
        raise ValueError(f"Invalid quick prompt id format: {prompt_id}")


def _quick_prompts_filepath(project_root: str) -> str:
    """internal helper — return the quick-prompts.json path."""
    return os.path.join(project_root, QUICK_PROMPTS_PATH)


def _read_quick_prompts(project_root: str) -> dict:
    """internal helper — read quick-prompts.json for the Board API."""
    filepath = _quick_prompts_filepath(project_root)
    if not os.path.isfile(filepath):
        return {"version": 1, "items": []}

    try:
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "items": []}

    if not isinstance(data, dict):
        return {"version": 1, "items": []}

    data.setdefault("version", 1)
    items = data.get("items")
    if not isinstance(items, list):
        items = []
    data["items"] = items
    return data


def _write_quick_prompt(project_root: str, prompt_id: str, fields: dict) -> dict:
    """internal helper — create or update one quick prompt."""
    _validate_quick_prompt_id(prompt_id)
    if not isinstance(fields, dict):
        raise ValueError("fields must be an object")

    prompt = fields.get("prompt")
    if not isinstance(prompt, str):
        raise ValueError('"prompt" must be a string')

    label = fields.get("label")
    if label is not None and not isinstance(label, str):
        raise ValueError('"label" must be a string')

    bind_to = fields.get("bindTo")
    if bind_to is not None and not isinstance(bind_to, str):
        raise ValueError('"bindTo" must be a string')

    description = fields.get("description")
    if description is not None and not isinstance(description, str):
        raise ValueError('"description" must be a string')

    data = _read_quick_prompts(project_root)
    items = data.get("items") or []

    found = False
    for item in items:
        if isinstance(item, dict) and item.get("id") == prompt_id:
            item["prompt"] = prompt
            if label is not None:
                item["label"] = label
            if bind_to is not None:
                item["bindTo"] = bind_to
            if description is not None:
                item["description"] = description
            found = True
            break

    if not found:
        new_item = {"id": prompt_id, "prompt": prompt}
        if label is not None:
            new_item["label"] = label
        if bind_to is not None:
            new_item["bindTo"] = bind_to
        if description is not None:
            new_item["description"] = description
        items.append(new_item)

    data["items"] = items

    filepath = _quick_prompts_filepath(project_root)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return {"ok": True, "id": prompt_id, "items": items}


def _delete_quick_prompt(project_root: str, prompt_id: str) -> dict:
    """internal helper — delete one quick prompt."""
    _validate_quick_prompt_id(prompt_id)
    data = _read_quick_prompts(project_root)
    items = data.get("items") or []

    new_items = [
        item for item in items
        if not (isinstance(item, dict) and item.get("id") == prompt_id)
    ]

    if len(new_items) == len(items):
        raise FileNotFoundError(f"Quick prompt not found: {prompt_id}")

    data["items"] = new_items
    filepath = _quick_prompts_filepath(project_root)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return {"ok": True, "id": prompt_id, "items": new_items}


__all__ = [
    "PROMPT_FILES_PATH",
    "QUICK_PROMPTS_PATH",
    "_delete_prompt_file",
    "_delete_quick_prompt",
    "_list_prompt_files",
    "_prompt_files_dir",
    "_quick_prompts_filepath",
    "_read_prompt_file",
    "_read_quick_prompts",
    "_validate_prompt_filename",
    "_validate_quick_prompt_id",
    "_write_prompt_file",
    "_write_quick_prompt",
]
