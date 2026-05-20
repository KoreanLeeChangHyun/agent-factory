"""Pure helpers for deterministic code-check validation artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
HEAD_DIAGNOSTIC_LIMIT = 10
DEFAULT_TIMEOUT_SECONDS = 600


def detect_pytest_config(root: Path) -> bool:
    """Return True when pytest has an explicit config or discoverable tests."""
    for fname in ("pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini"):
        if (root / fname).is_file():
            return True
    return (root / "tests").is_dir()


def detect_ruff_config(root: Path) -> bool:
    """Return True when ruff configuration is present."""
    for fname in ("ruff.toml", ".ruff.toml"):
        if (root / fname).is_file():
            return True
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            return "[tool.ruff" in pyproject.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return False
    return False


def detect_mypy_config(root: Path) -> bool:
    """Return True when mypy configuration is present."""
    for fname in ("mypy.ini", ".mypy.ini"):
        if (root / fname).is_file():
            return True
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            return "[tool.mypy" in pyproject.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return False
    return False


def parse_pytest_summary(text: str) -> dict[str, int]:
    """Parse pytest summary counts from quiet output."""
    keywords = ("passed", "failed", "errors", "skipped", "xfailed", "xpassed")
    counts: dict[str, int] = {}
    for line in text.splitlines()[-20:]:
        tokens = line.replace(",", " ").split()
        for i, tok in enumerate(tokens):
            if tok.isdigit() and i + 1 < len(tokens) and tokens[i + 1] in keywords:
                counts[tokens[i + 1]] = int(tok)
    return counts


def parse_pytest_failed_nodes(text: str) -> list[str]:
    """Extract failed/error pytest node IDs from quiet output."""
    nodes: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("FAILED "):
            nodes.append(stripped[7:].split(" - ")[0].strip())
        elif stripped.startswith("ERROR "):
            nodes.append(stripped[6:].split(" - ")[0].strip())
    return nodes


def read_code_json(ctx: Any) -> dict[str, Any]:
    """Read ``validate/code.json`` from a workflow-like context."""
    path = ctx.validate_code_json_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def tool_result(code_payload: dict[str, Any], tool: str) -> dict[str, Any] | None:
    """Return one tool entry from a code-check payload."""
    for entry in code_payload.get("tools", []):
        if isinstance(entry, dict) and entry.get("tool") == tool:
            return entry
    return None


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "HEAD_DIAGNOSTIC_LIMIT",
    "SCHEMA_VERSION",
    "detect_mypy_config",
    "detect_pytest_config",
    "detect_ruff_config",
    "parse_pytest_failed_nodes",
    "parse_pytest_summary",
    "read_code_json",
    "tool_result",
]
