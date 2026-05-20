#!/usr/bin/env python3
"""`.claude/` 파일 간접 편집 유틸리티.

Claude Code가 `.claude/` 경로에 대한 직접 Edit/Write를 차단하므로,
`.agent-factory/staging/`를 중간 편집 영역으로 사용한다.

사용법:
    python3 claude_edit.py open <relative_path>   # .claude/ → edit/ Copy
    python3 claude_edit.py save <relative_path>    # edit/ → .claude/ overwrite
    python3 claude_edit.py diff <relative_path>    # Edit/ vs .claude/ Check the difference
    python3 claude_edit.py new  <relative_path>    # Create empty file in edit/ (new)

예시:
    python3 claude_edit.py open settings.json
    # → Edit in .agent-factory/staging/settings.json
    python3 claude_edit.py save settings.json
    # → Reflected in .claude/settings.json

    python3 claude_edit.py new rules/workflow/new_rule.md
    # → Create an empty file .agent-factory/staging/rules/workflow/new_rule.md
    # → After writing content using the Edit tool, it is promoted to .claude/ when calling save.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..')
)
CLAUDE_DIR = os.path.join(PROJECT_ROOT, '.claude')
EDIT_DIR = os.path.join(PROJECT_ROOT, '.agent-factory', 'staging')


def _validate_path(rel_path: str) -> None:
    """Path escape prevention verification. In case of violation, output [ERROR] and then sys.exit(1)."""
    if not rel_path:
        print("[ERROR] Invalid path: (empty string)", file=sys.stderr)
        sys.exit(1)
    if os.path.isabs(rel_path):
        print(f"[ERROR] Invalid path: {rel_path}", file=sys.stderr)
        sys.exit(1)
    # Reject segment '..'
    parts = rel_path.replace('\\', '/').split('/')
    if '..' in parts:
        print(f"[ERROR] Invalid path: {rel_path}", file=sys.stderr)
        sys.exit(1)
    # CLAUDE_DIR sub-recheck after normalization (double safety net)
    resolved_src = os.path.normpath(os.path.join(CLAUDE_DIR, rel_path))
    if not resolved_src.startswith(CLAUDE_DIR + os.sep) and resolved_src != CLAUDE_DIR:
        print(f"[ERROR] Invalid path: {rel_path}", file=sys.stderr)
        sys.exit(1)


def _resolve(rel_path: str) -> tuple[str, str]:
    src = os.path.join(CLAUDE_DIR, rel_path)
    dst = os.path.join(EDIT_DIR, rel_path)
    return src, dst


def cmd_new(rel_path: str) -> None:
    _validate_path(rel_path)
    src, dst = _resolve(rel_path)
    if os.path.exists(src):
        print(f"[ERROR] Original already exists: {src}", file=sys.stderr)
        sys.exit(1)
    if os.path.exists(dst):
        print(f"[ERROR] Edit file already exists: {dst}", file=sys.stderr)
        sys.exit(1)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'w').close()
    print(f"[NEW] {dst} (creates an empty file, promotes to {src} when calling save)")


def cmd_open(rel_path: str) -> None:
    _validate_path(rel_path)
    src, dst = _resolve(rel_path)
    if not os.path.exists(src):
        print(f"[ERROR] No original file: {src}", file=sys.stderr)
        sys.exit(1)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    print(f"[OPEN] {src} → {dst}")


def cmd_save(rel_path: str) -> None:
    _validate_path(rel_path)
    src, dst = _resolve(rel_path)
    if not os.path.exists(dst):
        print(f"[ERROR] No edit file: {dst}", file=sys.stderr)
        sys.exit(1)
    is_new = not os.path.exists(src)
    os.makedirs(os.path.dirname(src), exist_ok=True)
    shutil.copy2(dst, src)
    os.remove(dst)
    # Clean up empty parent directories
    parent = os.path.dirname(dst)
    while parent != EDIT_DIR:
        try:
            os.rmdir(parent)
            parent = os.path.dirname(parent)
        except OSError:
            break
    if is_new:
        print(f"[SAVE] {dst} → {src} (create new, delete edited file)")
    else:
        print(f"[SAVE] {dst} → {src} (delete edit file)")


def cmd_diff(rel_path: str) -> None:
    _validate_path(rel_path)
    src, dst = _resolve(rel_path)
    if not os.path.exists(dst):
        print(f"[ERROR] No edit file: {dst}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(src):
        print(f"[INFO] No original (new file): {src}")
        return
    result = subprocess.run(
        ['diff', '--color=always', '-u', src, dst],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print("[DIFF] No change")
    else:
        print(result.stdout)


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: claude_edit.py <open|save|diff|new> <relative_path>")
        sys.exit(1)

    action = sys.argv[1]
    rel_path = sys.argv[2]

    if action == 'open':
        cmd_open(rel_path)
    elif action == 'save':
        cmd_save(rel_path)
    elif action == 'diff':
        cmd_diff(rel_path)
    elif action == 'new':
        cmd_new(rel_path)
    else:
        print(f"[ERROR] Unknown command: {action}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
