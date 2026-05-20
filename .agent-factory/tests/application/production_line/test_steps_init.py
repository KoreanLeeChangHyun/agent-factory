"""test steps init.py — INIT Step Helper Unit Test.

Target (SPEC.md §9.1.1, Stage 3-D):
  -  parse ticket meta: kanban show output (command, title) extraction
  -  maybe create worktree: command=research review(None, None) return
  - init step (T-495 P2): V2 REGISTRY KEY env priority use (board pre-issued)

Integrated (worktree real creation) is valid for smoke cycles.
"""

from __future__ import annotations



from engine.apps.production_line.stations.init import _maybe_create_worktree, _parse_ticket_meta
from engine.apps.production_line.stations import init as init_mod


_KANBAN_DUMP_TEMPLATE = """## T-491: Sample Tickets

### Metadata
- Number: T-491
- Title: {title}
- Status: Review
- Command: {command}

### Relations
- derived-from: T-489

### Prompt
- Goal: Verification
"""


def test_parse_ticket_meta_implement() -> None:
    dump = _KANBAN_DUMP_TEMPLATE.format(command="implement", title="Automated Ticket Samples")
    command, title = _parse_ticket_meta(dump)
    assert command == "implement"
    assert title == "Automated Ticket Samples"


def test_parse_ticket_meta_research() -> None:
    dump = _KANBAN_DUMP_TEMPLATE.format(command="research", title="Home")
    command, title = _parse_ticket_meta(dump)
    assert command == "research"
    assert title == "Home"


def test_parse_ticket_meta_review() -> None:
    dump = _KANBAN_DUMP_TEMPLATE.format(command="review", title="Search")
    command, title = _parse_ticket_meta(dump)
    assert command == "review"
    assert title == "Search"


def test_parse_ticket_meta_unknown_command_fallback() -> None:
    """Unknown command is executed to fallback (safe default)."""
    dump = _KANBAN_DUMP_TEMPLATE.format(command="bogus", title="Title")
    command, _ = _parse_ticket_meta(dump)
    assert command == "implement"


def test_parse_ticket_meta_missing_command_default() -> None:
    """execute default when missing Command line."""
    dump = "################################################################################################################################################################################################################################################################"
    command, title = _parse_ticket_meta(dump)
    assert command == "implement"
    assert title == "Title"


def test_maybe_create_worktree_research_returns_none() -> None:
    """command=research → worktree creation X."""
    fb, wp = _maybe_create_worktree("T-491", "Company", "research")
    assert fb is None
    assert wp is None


def test_maybe_create_worktree_review_returns_none() -> None:
    """command=review → worktree creation X."""
    fb, wp = _maybe_create_worktree("T-491", "Browse By Tag", "review")
    assert fb is None
    assert wp is None


def test_init_step_writes_metadata_json(monkeypatch, tmp_path):
    """T-503 wire-up — init step → metadata.json (Ex .context.json/status.json also preserved)."""
    monkeypatch.delenv("V2_REGISTRY_KEY", raising=False)

    def fake_kanban_show(ticket_no):
        return (
            "## T-491: Validation of Metadata\\n## Metadata\\n"
            "- Number: T-491\n- Title: meta\n- Status: Open\n- Command: research\n"
        )

    monkeypatch.setattr(init_mod, "kanban_show", fake_kanban_show)
    monkeypatch.setattr(init_mod, "kanban_move", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "session_create", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "step_start", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "step_end", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "update_step", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "append_log", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "new_registry_key", lambda: "20260518-100000")

    def fake_make_work_dir(rk):
        d = tmp_path / "runs" / rk
        (d / "work").mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(init_mod, "make_work_dir", fake_make_work_dir)

    ctx = init_mod.init_step("T-491")

    metadata_path = ctx.metadata_json_path()
    assert metadata_path.exists(), "init_step must write metadata.json"
    import json as _json
    payload = _json.loads(metadata_path.read_text(encoding="utf-8"))
    assert payload["ticket_no"] == "T-491"
    assert payload["registry_key"] == "20260518-100000"
    assert payload["command"] == "research"
    assert payload["finalized_at"] is None
    assert payload["failure"] is None


def test_init_step_uses_v2_registry_key_env(monkeypatch, tmp_path):
    """T-495 P2 — V2 REGISTRY KEY env prior use. board pre-issued session id sum."""
    fake_key = "20260517-204200"
    monkeypatch.setenv("V2_REGISTRY_KEY", fake_key)

    captured = {}

    def fake_kanban_show(ticket_no):
        return (
            "## T-495: Sample Tickets\\n\\n## Metadata\\n"
            "- Number: T-495\n- Title: dummy\n- Status: Open\n- Command: research\n"
        )

    def fake_kanban_move(ticket_no, target):
        captured["kanban_move"] = (ticket_no, target)

    def fake_session_create(ctx):
        captured["session_id"] = ctx.wf_session_id
        captured["registry_key"] = ctx.registry_key

    def fake_step_start(ctx, step, **kw):
        captured["step_start"] = (step, kw.get("prev_step"))

    def fake_step_end(ctx, step, **kw):
        captured["step_end"] = (step, kw.get("outcome"))

    def fake_make_work_dir(registry_key):
        d = tmp_path / "runs" / registry_key
        (d / "work").mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(init_mod, "kanban_show", fake_kanban_show)
    monkeypatch.setattr(init_mod, "kanban_move", fake_kanban_move)
    monkeypatch.setattr(init_mod, "session_create", fake_session_create)
    monkeypatch.setattr(init_mod, "step_start", fake_step_start)
    monkeypatch.setattr(init_mod, "step_end", fake_step_end)
    monkeypatch.setattr(init_mod, "make_work_dir", fake_make_work_dir)
    # write status / write context / update step / append log
    monkeypatch.setattr(init_mod, "write_status", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "write_context", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "update_step", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "append_log", lambda *a, **k: None)
    # if new registry key is called, the env priority rule will be broken — check 0 calls
    new_key_called = {"n": 0}

    def fake_new_key():
        new_key_called["n"] += 1
        return "should-not-be-used"

    monkeypatch.setattr(init_mod, "new_registry_key", fake_new_key)

    ctx = init_mod.init_step("T-495")

    assert ctx.registry_key == fake_key
    assert ctx.wf_session_id == f"wf-T-495-{fake_key}"
    assert captured["session_id"] == f"wf-T-495-{fake_key}"
    assert captured["registry_key"] == fake_key
    assert new_key_called["n"] == 0  # new registry key


def test_init_step_falls_back_to_new_registry_key_when_env_missing(monkeypatch, tmp_path):
    """V2 REGISTRY KEY env Unset new registry key() Normal call."""
    monkeypatch.delenv("V2_REGISTRY_KEY", raising=False)

    def fake_kanban_show(ticket_no):
        return (
            "## T-495: Sample\\n\\n## Metadata\\n"
            "- Number: T-495\n- Title: dummy\n- Status: Open\n- Command: research\n"
        )

    monkeypatch.setattr(init_mod, "kanban_show", fake_kanban_show)
    monkeypatch.setattr(init_mod, "kanban_move", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "session_create", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "step_start", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "step_end", lambda *a, **k: None)
    monkeypatch.setattr(
        init_mod, "make_work_dir",
        lambda rk: ((tmp_path / "runs" / rk / "work").mkdir(parents=True, exist_ok=True)
                    or (tmp_path / "runs" / rk)),
    )
    monkeypatch.setattr(init_mod, "write_status", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "write_context", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "update_step", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "append_log", lambda *a, **k: None)

    monkeypatch.setattr(init_mod, "new_registry_key", lambda: "fresh-fallback-key")

    ctx = init_mod.init_step("T-495")

    assert ctx.registry_key == "fresh-fallback-key"
    assert ctx.wf_session_id == "wf-T-495-fresh-fallback-key"
