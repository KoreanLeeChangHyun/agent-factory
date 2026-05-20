"""Architecture boundary checks for the Agent Factory core."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "engine"


def _python_files(*parts: str) -> list[Path]:
    base = ENGINE.joinpath(*parts)
    return sorted(path for path in base.rglob("*.py") if "__pycache__" not in path.parts)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def _assert_no_forbidden_imports(paths: list[Path], forbidden_prefixes: tuple[str, ...]) -> None:
    violations: list[str] = []
    for path in paths:
        for imported in sorted(_imports(path)):
            if imported == "__future__":
                continue
            if imported in forbidden_prefixes or imported.startswith(
                tuple(prefix + "." for prefix in forbidden_prefixes)
            ):
                rel = path.relative_to(ROOT)
                violations.append(f"{rel}: {imported}")
    assert not violations, "Forbidden architecture imports:\n" + "\n".join(violations)


def test_core_has_no_runtime_or_provider_imports() -> None:
    _assert_no_forbidden_imports(
        _python_files("core"),
        (
            "board",
            "subprocess",
            "engine.adapters",
            "engine.application",
            "engine.flow",
            "engine.v2",
        ),
    )


def test_application_does_not_import_provider_or_board_implementations() -> None:
    _assert_no_forbidden_imports(
        _python_files("application"),
        (
            "board",
            "subprocess",
            "engine.adapters",
            "engine.flow",
            "engine.v2",
        ),
    )
