"""Maintenance CLI app placement coverage."""

from __future__ import annotations

from pathlib import Path


def test_maintenance_cli_modules_import_from_app_boundary() -> None:
    from engine.apps.cli import fix_board_links, migrate_runs_fold

    assert fix_board_links.PATTERN.search(
        "runs/20260101-010101/work/implement/report.md"
    )
    assert callable(migrate_runs_fold.main)


def test_flow_migrate_runs_wrapper_points_to_app_cli() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    wrapper = repo_root / ".agent-factory" / "bin" / "flow-migrate-runs"

    assert "engine/apps/cli/migrate_runs_fold.py" in wrapper.read_text(encoding="utf-8")


def test_migrate_runs_default_root_points_to_runtime_history(capsys) -> None:
    from engine.apps.cli import migrate_runs_fold

    try:
        migrate_runs_fold.main(["--help"])
    except SystemExit:
        pass

    assert ".agent-factory/runs/.history" in capsys.readouterr().out
