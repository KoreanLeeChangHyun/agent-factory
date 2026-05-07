#!/usr/bin/env python3
"""T-422 main_session_guard smoke test."""
import subprocess, json, os

GUARD = "/home/deus/workspace/claude/.claude-organic/worktrees/feat-T-422-Hook-가드-메모리-화이트리스트/.claude-organic/engine/guards/main_session_guard.py"

def run(tool_name, tool_input, env_extra=None):
    env = os.environ.copy()
    env["HOOK_MAIN_SESSION_GUARD"] = "true"
    # 메인 세션 시뮬레이션: _WF_SESSION_TYPE / TMUX_PANE 제거 → unknown 분기
    env.pop("_WF_SESSION_TYPE", None)
    env.pop("TMUX_PANE", None)
    env.pop("WORKFLOW_WORKTREE_PATH", None)
    env.pop("WORKFLOW_WORK_DIR", None)
    if env_extra:
        env.update(env_extra)
    payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
    r = subprocess.run(["python3", GUARD], input=payload, capture_output=True, text=True, env=env)
    out = r.stdout.strip()
    decision = None
    if out:
        try:
            d = json.loads(out)
            decision = d.get("hookSpecificOutput", {}).get("permissionDecision")
        except Exception:
            decision = f"(unparsed: {out[:60]})"
    return r.returncode, decision

results = []

# allow cases
rc, dec = run("Write", {"file_path": "/home/deus/.claude/projects/-home-deus-workspace-claude/memory/feedback/foo.md", "content": ""})
results.append(("allow Write memory abs path", rc == 0 and dec != "deny", f"rc={rc} dec={dec}"))

rc, dec = run("Edit", {"file_path": "/home/deus/.claude/projects/-home-deus-workspace-claude/memory/MEMORY.md", "old_string": "a", "new_string": "b"})
results.append(("allow Edit memory abs path", rc == 0 and dec != "deny", f"rc={rc} dec={dec}"))

rc, dec = run("Write", {"file_path": "~/.claude/projects/-home-deus-workspace-claude/memory/new.md", "content": ""})
results.append(("allow Write memory tilde path", rc == 0 and dec != "deny", f"rc={rc} dec={dec}"))

rc, dec = run("Bash", {"command": "cp /tmp/foo.md /home/deus/.claude/projects/-home-deus-workspace-claude/memory/bar.md"})
results.append(("allow Bash cp memory-only", rc == 0 and dec != "deny", f"rc={rc} dec={dec}"))

rc, dec = run("Bash", {"command": 'flow-kanban update-prompt T-422 --target "수정: ~/.claude/projects/-home-deus/memory/feedback/"'})
results.append(("allow Bash flow-kanban quoted memory text", rc == 0 and dec != "deny", f"rc={rc} dec={dec}"))

rc, dec = run("Write", {"file_path": ".claude-organic/engine/foo.py", "content": ""}, {"HOOK_MAIN_SESSION_GUARD": "false"})
results.append(("allow guard disabled", rc == 0 and dec != "deny", f"rc={rc} dec={dec}"))

# deny cases
rc, dec = run("Write", {"file_path": ".claude-organic/engine/guards/guard.py", "content": ""})
results.append(("deny Write engine path", dec == "deny", f"rc={rc} dec={dec}"))

rc, dec = run("Edit", {"file_path": ".claude-organic/board/server/app.py", "old_string": "a", "new_string": "b"})
results.append(("deny Edit board path", dec == "deny", f"rc={rc} dec={dec}"))

rc, dec = run("Bash", {"command": "sed -i 's/a/b/' engine/guards/guard.py"})
results.append(("deny Bash sed engine", dec == "deny", f"rc={rc} dec={dec}"))

rc, dec = run("Bash", {"command": "cp /home/deus/.claude/projects/-home-deus/memory/foo.md .claude-organic/engine/bar.md"})
results.append(("deny Bash cp memory+engine mixed", dec == "deny", f"rc={rc} dec={dec}"))

print("\n=== smoke test results ===")
all_pass = True
for label, passed, detail in results:
    status = "PASS" if passed else "FAIL"
    if not passed:
        all_pass = False
    print(f"  [{status}] {label} -- {detail}")
print(f"\n{'ALL PASS' if all_pass else 'SOME FAILED'}")
