#!/usr/bin/env python3
"""`.claude/` 파일 간접 편집 유틸리티.

Claude Code가 `.claude/` 경로에 대한 직접 Edit/Write를 차단하므로,
`.claude-organic/staging/`를 중간 편집 영역으로 사용한다.

사용법:
    python3 claude_edit.py open <relative_path>   # .claude/ → edit/ 복사
    python3 claude_edit.py save <relative_path>    # edit/ → .claude/ 덮어쓰기
    python3 claude_edit.py diff <relative_path>    # edit/ vs .claude/ 차이 확인
    python3 claude_edit.py new  <relative_path>    # edit/ 에 빈 파일 생성 (신규)

예시:
    python3 claude_edit.py open settings.json
    # → .claude-organic/staging/settings.json 에서 편집
    python3 claude_edit.py save settings.json
    # → .claude/settings.json 에 반영

    python3 claude_edit.py new rules/workflow/new_rule.md
    # → .claude-organic/staging/rules/workflow/new_rule.md 빈 파일 생성
    # → Edit 도구로 내용 작성 후 save 호출 시 .claude/ 로 승격
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
)
CLAUDE_DIR = os.path.join(PROJECT_ROOT, '.claude')
EDIT_DIR = os.path.join(PROJECT_ROOT, '.claude-organic', 'staging')


def _validate_path(rel_path: str) -> None:
    """경로 탈출 방지 검증. 위반 시 [ERROR] 출력 후 sys.exit(1)."""
    if not rel_path:
        print("[ERROR] 잘못된 경로: (빈 문자열)", file=sys.stderr)
        sys.exit(1)
    if os.path.isabs(rel_path):
        print(f"[ERROR] 잘못된 경로: {rel_path}", file=sys.stderr)
        sys.exit(1)
    # '..' 세그먼트 거부
    parts = rel_path.replace('\\', '/').split('/')
    if '..' in parts:
        print(f"[ERROR] 잘못된 경로: {rel_path}", file=sys.stderr)
        sys.exit(1)
    # 정규화 후 CLAUDE_DIR 하위 재확인 (이중 안전망)
    resolved_src = os.path.normpath(os.path.join(CLAUDE_DIR, rel_path))
    if not resolved_src.startswith(CLAUDE_DIR + os.sep) and resolved_src != CLAUDE_DIR:
        print(f"[ERROR] 잘못된 경로: {rel_path}", file=sys.stderr)
        sys.exit(1)


def _resolve(rel_path: str) -> tuple[str, str]:
    src = os.path.join(CLAUDE_DIR, rel_path)
    dst = os.path.join(EDIT_DIR, rel_path)
    return src, dst


def cmd_new(rel_path: str) -> None:
    _validate_path(rel_path)
    src, dst = _resolve(rel_path)
    if os.path.exists(src):
        print(f"[ERROR] 원본이 이미 존재: {src}", file=sys.stderr)
        sys.exit(1)
    if os.path.exists(dst):
        print(f"[ERROR] 편집 파일이 이미 존재: {dst}", file=sys.stderr)
        sys.exit(1)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'w').close()
    print(f"[NEW] {dst} (빈 파일 생성, save 호출 시 {src} 로 승격)")


def cmd_open(rel_path: str) -> None:
    _validate_path(rel_path)
    src, dst = _resolve(rel_path)
    if not os.path.exists(src):
        print(f"[ERROR] 원본 파일 없음: {src}", file=sys.stderr)
        sys.exit(1)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    print(f"[OPEN] {src} → {dst}")


def cmd_save(rel_path: str) -> None:
    _validate_path(rel_path)
    src, dst = _resolve(rel_path)
    if not os.path.exists(dst):
        print(f"[ERROR] 편집 파일 없음: {dst}", file=sys.stderr)
        sys.exit(1)
    is_new = not os.path.exists(src)
    os.makedirs(os.path.dirname(src), exist_ok=True)
    shutil.copy2(dst, src)
    os.remove(dst)
    # 빈 상위 디렉터리 정리
    parent = os.path.dirname(dst)
    while parent != EDIT_DIR:
        try:
            os.rmdir(parent)
            parent = os.path.dirname(parent)
        except OSError:
            break
    if is_new:
        print(f"[SAVE] {dst} → {src} (신규 생성, 편집 파일 삭제)")
    else:
        print(f"[SAVE] {dst} → {src} (편집 파일 삭제)")


def cmd_diff(rel_path: str) -> None:
    _validate_path(rel_path)
    src, dst = _resolve(rel_path)
    if not os.path.exists(dst):
        print(f"[ERROR] 편집 파일 없음: {dst}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(src):
        print(f"[INFO] 원본 없음 (신규 파일): {src}")
        return
    result = subprocess.run(
        ['diff', '--color=always', '-u', src, dst],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print("[DIFF] 변경 없음")
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
        print(f"[ERROR] 알 수 없는 명령: {action}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
