"""M11 runtime cleanup contracts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from engine.core.validation import link_validator


ROOT = Path(__file__).resolve().parents[3]
DIRECT_PATH_GUARD = ROOT / "engine" / "guards" / "direct_path_guard.py"


def test_link_validator_scans_report_html_and_plan_md(tmp_path: Path) -> None:
    run_dir = tmp_path / ".agent-factory" / "runs" / "20260520-120000"
    run_dir.mkdir(parents=True)
    (run_dir / "plan.md").write_text("[ok](artifact.txt)\n", encoding="utf-8")
    (run_dir / "report.html").write_text('<a href="artifact.txt">ok</a>', encoding="utf-8")
    (run_dir / "report.md").write_text("[stale](missing.txt)\n", encoding="utf-8")
    (run_dir / "artifact.txt").write_text("ok", encoding="utf-8")

    files = link_validator.scan_markdown_files(tmp_path)

    assert [path.name for path in files] == ["plan.md", "report.html"]


def test_link_validator_extracts_markdown_and_html_links() -> None:
    links = link_validator.extract_links(
        '[plan](plan/plan.md)\n<a href="report.html">Report</a>\n'
    )

    assert links == ["plan/plan.md", "report.html"]


def test_link_validator_skips_html_fragment_links() -> None:
    assert link_validator._is_skip_link("#summary")


def test_direct_path_guard_blocks_agent_factory_engine_direct_call() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": "python3 .agent-factory/engine/flow/conveyor.py list",
        },
    }
    env = os.environ.copy()
    env["HOOK_DIRECT_PATH_GUARD"] = "true"
    proc = subprocess.run(
        [sys.executable, "-u", str(DIRECT_PATH_GUARD)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )

    assert proc.returncode == 0
    body = json.loads(proc.stdout)
    hook_output = body["hookSpecificOutput"]
    assert hook_output["permissionDecision"] == "deny"
    assert "flow-conveyor" in hook_output["permissionDecisionReason"]


def test_direct_path_guard_no_longer_mentions_removed_v1_wrappers() -> None:
    from engine.guards.direct_path_guard import ALIAS_MAP

    assert "initialization.py" not in ALIAS_MAP
    assert "finalization.py" not in ALIAS_MAP
    assert "reload_prompt.py" not in ALIAS_MAP
    assert "skill_recommender.py" not in ALIAS_MAP


def test_direct_path_guard_maps_migrate_runs_cli() -> None:
    from engine.guards.direct_path_guard import ALIAS_MAP

    assert ALIAS_MAP["migrate_runs_fold.py"] == "flow-migrate-runs"
