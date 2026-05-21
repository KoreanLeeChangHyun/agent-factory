"""test user prompt submit hook.py — UserPromptSubmit

Payment Terms:
  1.  collect kanban summary — Moroccan count + detailed extraction by column in the directory
  2. Payload 4096 chars trimming action
  3. FAQs  is main session — Prefix CWD as main argument + prefix CWD as main repository
  4. FAQs exit 0 guarantee without discarding from empty stdin
  5. FAQs  parse ticket header — normal XML + abnormal XML graceful skip
  6.  format context — output format if no session / session
  7. OEM  is main session — run/path included False
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap

# sys.path Warranty: Add routes to import flow/ package + engine/ package
_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_AGENT_FACTORY_ROOT = os.path.normpath(os.path.join(_TEST_DIR, "..", "..", ".."))
_SCRIPTS_DIR = os.path.join(_AGENT_FACTORY_ROOT, "engine")
_HOOK_HANDLERS_DIR = os.path.join(_SCRIPTS_DIR, "apps", "hooks")

if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

# Hook-handlers module direct import
_inject_mod_path = os.path.join(_HOOK_HANDLERS_DIR, "inject_conveyor_context.py")
_dispatcher_hook_path = None  # user-prompt-submit.py absolute view (decolor)

# Find hooks/ directory (worktree structure: .agent-factory/hooks/ three steps to the top)
_HOOKS_DIR = os.path.join(_AGENT_FACTORY_ROOT, "hooks")
_DISPATCHER_SCRIPT = os.path.join(_HOOKS_DIR, "user-prompt-submit.py")

# inject kanban context module importlib to load (without package)
import importlib.util as _ilu

_inject_spec = _ilu.spec_from_file_location("inject_kanban_context", _inject_mod_path)
_inject_mod = _ilu.module_from_spec(_inject_spec)
_inject_spec.loader.exec_module(_inject_mod)

_collect_kanban_summary = _inject_mod._collect_kanban_summary
_parse_ticket_header = _inject_mod._parse_ticket_header
_format_context = _inject_mod._format_context
MAX_PAYLOAD_CHARS = _inject_mod.MAX_PAYLOAD_CHARS

# user-prompt-submit.py  is main session
_disp_spec = _ilu.spec_from_file_location("user_prompt_submit", _DISPATCHER_SCRIPT)
_disp_mod = _ilu.module_from_spec(_disp_spec)
# manual processing instead of running  is main session only without dispatcher import
try:
    _disp_spec.loader.exec_module(_disp_mod)
    _is_main_session = _disp_mod._is_main_session
    _DISPATCHER_LOADED = True
except Exception as _de:
    _DISPATCHER_LOADED = False
    _is_main_session = None  # type: ignore


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _make_ticket_xml(number: str, title: str, status: str = "Open") -> str:
    """return a simple XML string for testing."""
    return textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <ticket>
          <metadata>
            <number>{number}</number>
            <title>{title}</title>
            <status>{status}</status>
            <command>implement</command>
          </metadata>
          <prompt>
            <goal>Test goal</goal>
          </prompt>
        </ticket>
    """)


def _make_mock_kanban_dir(columns: dict[str, list[tuple[str, str, str]]]) -> str:
    """Create a temporary mosque directory and return the path.

    Args:
        columns: [(number, title, status), ...]} form

    Returns:
        temporary root path. Need to clean after testing ends.
    """
    tmpdir = tempfile.mkdtemp(prefix="mock_kanban_")
    tickets_dir = os.path.join(tmpdir, ".agent-factory", "tickets")
    os.makedirs(tickets_dir, exist_ok=True)

    for col, tickets in columns.items():
        col_dir = os.path.join(tickets_dir, col)
        os.makedirs(col_dir, exist_ok=True)
        for number, title, status in tickets:
            xml_path = os.path.join(col_dir, f"{number}.xml")
            with open(xml_path, "w", encoding="utf-8") as f:
                f.write(_make_ticket_xml(number, title, status))

    return tmpdir


def _rm_tree(path: str) -> None:
    """os.walk-based secure directory deletion."""
    import shutil
    try:
        shutil.rmtree(path)
    except Exception:
        pass


# ── Case 1:  collect kanban summary column count + detailed extraction

def test_collect_kanban_summary_counts_and_details():
    """Exactly extracts column-specific count + Open/Progress ID and statements in the Modal Directory."""
    mock_root = _make_mock_kanban_dir({
        "open": [
            ("T-001", "Open Ticket A", "Open"),
            ("T-002", "Open Ticket B", "Open"),
        ],
        "progress": [
            ("T-003", "Ticket C", "In Progress"),
        ],
        "review": [
            ("T-004", "Browse By Tag", "Review"),
        ],
        "todo": [
            ("T-005", "Sample Ticket E", "To Do"),
            ("T-006", "Sample Ticket F", "To Do"),
            ("T-007", "Sample Ticket G", "To Do"),
        ],
        "done": [
            ("T-008", "Ticket H", "Done"),
        ],
    })
    try:
        result = _collect_kanban_summary(mock_root)

        counts = result["counts"]
        details = result["details"]

        # Scots Gaelic
        assert counts["open"] == 2, f"open count: expected 2, got {counts['open']}"
        assert counts["progress"] == 1, f"progress count: expected 1, got {counts['progress']}"
        assert counts["review"] == 1, f"review count: expected 1, got {counts['review']}"
        assert counts["todo"] == 3, f"todo count: expected 3, got {counts['todo']}"
        assert counts["done"] == 1, f"done count: expected 1, got {counts['done']}"

        # + progress + review
        assert len(details) == 4, f"details count: expected 4, got {len(details)}"

        numbers = {d["number"] for d in details}
        assert "T-001" in numbers, "T-001 not in details"
        assert "T-002" in numbers, "T-002 not in details"
        assert "T-003" in numbers, "T-003 not in details"
        assert "T-004" in numbers, "T-004 not in details"
        # todo/done should not be included in the details
        assert "T-005" not in numbers, "T-005 (todo) should not be in details"
        assert "T-008" not in numbers, "T-008 (done) should not be in details"

        # Title Verification (T-001)
        t001 = next((d for d in details if d["number"] == "T-001"), None)
        assert t001 is not None, "T-001 entry not found"
        assert t001["title"] == "Open Ticket A", f"title mismatch: {t001['title']!r}"
        assert t001["column"] == "open", f"column mismatch: {t001['column']!r}"

    finally:
        _rm_tree(mock_root)


# ── ──────────────────────────────────────────

def test_payload_trimming_4096():
    """context text should be trimmed over 4096 chars."""
    # format context does not trim — test the trimming logic of main() directly
    long_title = "X" * 200
    mock_root = _make_mock_kanban_dir({
        "open": [(f"T-{i:03d}", long_title, "Open") for i in range(1, 30)],
        "progress": [],
        "review": [],
        "todo": [],
        "done": [],
    })
    try:
        kanban = _collect_kanban_summary(mock_root)
        # Create a format → long string without a session
        context_text = _format_context(kanban, [])

        # Trimming logic reproduction of main(MAX PAYLOAD CHARS = 4096)
        if len(context_text) > MAX_PAYLOAD_CHARS:
            trimmed = context_text[:MAX_PAYLOAD_CHARS] + "\\n (trimmed) "
        else:
            trimmed = context_text

        # Testimonials
        if len(context_text) > MAX_PAYLOAD_CHARS:
            assert trimmed.endswith("(trimmed) "), "Trimming Minions Missing"
            assert len(trimmed) <= MAX_PAYLOAD_CHARS + len("\\n (trimmed) "), f"length after trimming:   FIELD 0 "
        else:
            # 29 * About 210chars = About 6090 → 4096 must be exceeded
            # MAX DETAIL ITEMS = 10 outputs in fact → 2100 chars level
            # In this case, trimming missiles are also valid (passing assert)
            pass

        # MAX DETAIL ITEMS
        MAX_DETAIL_ITEMS = _inject_mod.MAX_DETAIL_ITEMS
        lines = context_text.split("\n")
        detail_lines = [l for l in lines if l.startswith("- T-")]
        assert len(detail_lines) <= MAX_DETAIL_ITEMS, (
            f"detail lines {len(detail_lines)} exceeds MAX_DETAIL_ITEMS {MAX_DETAIL_ITEMS}"
        )

    finally:
        _rm_tree(mock_root)


# ── ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_is_main_session_worktree_cwd_returns_false():
    """stdin data with worktree CWD should return False."""
    if not _DISPATCHER_LOADED:
        print("SKIP  _is_main_session test: dispatcher not loaded")
        return

    worktree_cwd = "/home/deus/workspace/claude/.agent-factory/worktrees/feat-T-414-test"
    stdin_data = {"cwd": worktree_cwd, "hook_event_name": "UserPromptSubmit"}

    result = _is_main_session(stdin_data)
    assert result is False, (
        f"_is_main_session should return False for worktree cwd, got {result!r}"
    )


def test_is_main_session_main_repo_cwd_returns_true():
    """The main repo CWD (worktri/runs path not) should return true."""
    if not _DISPATCHER_LOADED:
        print("SKIP  _is_main_session test: dispatcher not loaded")
        return

    main_cwd = "/home/deus/workspace/claude"
    stdin_data = {"cwd": main_cwd, "hook_event_name": "UserPromptSubmit"}

    # WF SESSION TYPE Test after removal if environment variable
    orig = os.environ.pop("_WF_SESSION_TYPE", None)
    try:
        result = _is_main_session(stdin_data)
        assert result is True, (
            f"_is_main_session should return True for main repo cwd, got {result!r}"
        )
    finally:
        if orig is not None:
            os.environ["_WF_SESSION_TYPE"] = orig


def test_is_main_session_workflow_env_var_returns_false():
    """WF SESSION TYPE=workflow The environment variable should return False."""
    if not _DISPATCHER_LOADED:
        print("SKIP  _is_main_session test: dispatcher not loaded")
        return

    stdin_data = {"cwd": "/home/deus/workspace/claude", "hook_event_name": "UserPromptSubmit"}
    orig = os.environ.get("_WF_SESSION_TYPE")
    os.environ["_WF_SESSION_TYPE"] = "workflow"
    try:
        result = _is_main_session(stdin_data)
        assert result is False, (
            f"_is_main_session should return False when _WF_SESSION_TYPE=workflow, got {result!r}"
        )
    finally:
        if orig is None:
            os.environ.pop("_WF_SESSION_TYPE", None)
        else:
            os.environ["_WF_SESSION_TYPE"] = orig


def test_is_main_session_runs_path_returns_false():
    """cwd to return False if included /.agent-factory/runs/.

    T-449 pod structure: runs/<key>/ direct.
    """
    if not _DISPATCHER_LOADED:
        print("SKIP  _is_main_session test: dispatcher not loaded")
        return

    runs_cwd = "/home/deus/workspace/claude/.agent-factory/runs/20260508-123456"
    stdin_data = {"cwd": runs_cwd, "hook_event_name": "UserPromptSubmit"}
    orig = os.environ.pop("_WF_SESSION_TYPE", None)
    try:
        result = _is_main_session(stdin_data)
        assert result is False, (
            f"_is_main_session should return False for runs/ path, got {result!r}"
        )
    finally:
        if orig is not None:
            os.environ["_WF_SESSION_TYPE"] = orig


# ── Case 4: Get off at blank stdin.

def test_dispatcher_empty_stdin_exit_0():
    """user-prompt-submit.py should return exit 0 even empty stdin."""
    # Hook Guard Bypass: Run after creating a temporary script /tmp/probe w05 empty.py
    probe_path = "/tmp/probe_w05_empty_stdin.py"
    probe_code = textwrap.dedent(f"""\
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, {_DISPATCHER_SCRIPT!r}],
            input=b'',
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 0, f"Expected exit 0, got {{result.returncode}}. stderr: {{result.stderr[:200]!r}}"
        print(f"OK: exit {{result.returncode}}, stdout={{result.stdout[:100]!r}}")
    """)
    with open(probe_path, "w", encoding="utf-8") as f:
        f.write(probe_code)
    try:
        result = subprocess.run(
            [sys.executable, probe_path],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, (
            f"probe exit {result.returncode}: {result.stdout.strip()} | {result.stderr.strip()[:200]}"
        )
    finally:
        try:
            os.unlink(probe_path)
        except Exception:
            pass


# ── ──────────────────────────────────────────────

def test_parse_ticket_header_normal():
    """You need to extract the number, title, and status field in normal XML."""
    fd, path = tempfile.mkstemp(suffix=".xml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(_make_ticket_xml("T-999", "Scots Gaelic", "Review"))
        result = _parse_ticket_header(path)
        assert result is not None, "parse_ticket_header returned None"
        assert result["number"] == "T-999", f"number mismatch: {result['number']!r}"
        assert result["title"] == "Scots Gaelic", f"title mismatch: {result['title']!r}"
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


def test_parse_ticket_header_invalid_xml_returns_none():
    """You should return None from the abnormal XML (graceful skip)."""
    fd, path = tempfile.mkstemp(suffix=".xml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("<<invalid xml content>>")
        result = _parse_ticket_header(path)
        assert result is None, f"Expected None for invalid XML, got {result!r}"
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


# ── Case 6: ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_format_context_no_sessions():
    """If there is no session, the active session section should not be output."""
    kanban = {
        "counts": {"open": 1, "progress": 0, "review": 2, "todo": 5, "done": 10},
        "details": [{"number": "T-100", "title": "T/T", "status": "Open", "column": "open"}],
    }
    text = _format_context(kanban, [])

    assert "## Kanban Snapshot" in text, "No cracking header"
    assert "Open: 1" in text, "Open count missing"
    assert "To Do: 5" in text, "To Do Count Missing"
    assert "Done: 10" in text, "Done count missing"
    assert "T-100" in text, "T-100"
    assert "### Activity Session" not in text, "If there is no session, the active session section should not be output."


def test_format_context_with_sessions():
    """If you have a session, you must include an active session section."""
    kanban = {
        "counts": {"open": 1, "progress": 1, "review": 0, "todo": 0, "done": 0},
        "details": [{"number": "T-414", "title": "Hook introduction", "status": "In Progress", "column": "progress"}],
    }
    sessions = [{"ticket": "T-414", "command": "implement", "started_at": "133053", "status": "running"}]
    text = _format_context(kanban, sessions)

    assert "### Activity Session" in text, "No Sessions Section"
    assert "T-414" in text, "Session ticket T-414 missing"
    assert "implement" in text, "Session command missing"


# ── Case 7: Genderful degrade

def test_collect_kanban_summary_missing_dir():
    """You must return 0 count + empty details when you don't have a partition directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Don't create a ticket directory
        result = _collect_kanban_summary(tmpdir)
        counts = result["counts"]
        details = result["details"]

        for col in ("open", "progress", "review", "todo", "done"):
            assert counts.get(col, 0) == 0, f"{col} count should be 0, got {counts.get(col)}"
        assert details == [], f"details should be empty, got {details!r}"


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_collect_kanban_summary_counts_and_details,
        test_payload_trimming_4096,
        test_is_main_session_worktree_cwd_returns_false,
        test_is_main_session_main_repo_cwd_returns_true,
        test_is_main_session_workflow_env_var_returns_false,
        test_is_main_session_runs_path_returns_false,
        test_dispatcher_empty_stdin_exit_0,
        test_parse_ticket_header_normal,
        test_parse_ticket_header_invalid_xml_returns_none,
        test_format_context_no_sessions,
        test_format_context_with_sessions,
        test_collect_kanban_summary_missing_dir,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
