#!/usr/bin/env -S python3 -u
"""
init_clear.py - 작업 내역 클리어 스크립트

사용법: python3 init_clear.py <list|execute>

서브커맨드:
  list    - 삭제 대상 목록 및 크기 출력 (미리보기)
  execute - 실제 삭제 실행

삭제 대상:
  .workflow/  - 워크플로우 서브디렉토리 내용 (registry.json 보존)
  .prompt/    - 프롬프트 파일 (history.md, prompt.txt 등)
"""

import os
import shutil
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
_WORKFLOW_ROOT = os.path.join(_PROJECT_ROOT, ".workflow")


def _human_size(bytes_val):
    """바이트를 사람이 읽기 쉬운 형태로 변환."""
    if bytes_val >= 1073741824:
        return f"{bytes_val // 1073741824}G"
    elif bytes_val >= 1048576:
        return f"{bytes_val // 1048576}M"
    elif bytes_val >= 1024:
        return f"{bytes_val // 1024}K"
    else:
        return f"{bytes_val}B"


def _count_files(path):
    """디렉토리 내 파일 수 계산 (재귀)."""
    if not os.path.isdir(path):
        return 0
    count = 0
    for _root, _dirs, files in os.walk(path):
        count += len(files)
    return count


def _dir_size_bytes(path):
    """디렉토리 크기 계산 (바이트)."""
    if not os.path.isdir(path):
        return 0
    total = 0
    for _root, _dirs, files in os.walk(path):
        for f in files:
            fp = os.path.join(_root, f)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


# --- list 서브커맨드 ---

def cmd_list():
    total_files = 0
    total_bytes = 0
    has_content = False

    print("=== 삭제 대상 목록 ===")
    print()

    # 1. .workflow 날짜 디렉토리 (YYYYMMDD-* 패턴)
    print("[.workflow/]")
    if os.path.isdir(_WORKFLOW_ROOT):
        for entry in sorted(os.listdir(_WORKFLOW_ROOT)):
            entry_path = os.path.join(_WORKFLOW_ROOT, entry)
            if os.path.isdir(entry_path) and entry[0:1].isdigit():
                fcount = _count_files(entry_path)
                nbytes = _dir_size_bytes(entry_path)
                hsize = _human_size(nbytes)
                print(f"  .workflow/{entry}/  ({fcount}개 파일, {hsize})")
                total_files += fcount
                total_bytes += nbytes
                has_content = True

    # 1-1. .workflow/.history/ 아카이브 디렉토리
    print()
    print("[.workflow/.history/]")
    history_dir = os.path.join(_WORKFLOW_ROOT, ".history")
    if os.path.isdir(history_dir) and os.listdir(history_dir):
        fcount = _count_files(history_dir)
        nbytes = _dir_size_bytes(history_dir)
        hsize = _human_size(nbytes)
        print(f"  .workflow/.history/  ({fcount}개 파일, {hsize})")
        total_files += fcount
        total_bytes += nbytes
        has_content = True
    else:
        print("  (비어있음)")

    # 2. .prompt 디렉토리
    print()
    print("[.prompt/]")
    prompt_dir = os.path.join(_PROJECT_ROOT, ".prompt")
    if os.path.isdir(prompt_dir) and os.listdir(prompt_dir):
        fcount = _count_files(prompt_dir)
        nbytes = _dir_size_bytes(prompt_dir)
        hsize = _human_size(nbytes)
        print(f"  .prompt/  ({fcount}개 파일, {hsize})")
        # 개별 파일 나열
        for fname in sorted(os.listdir(prompt_dir)):
            fpath = os.path.join(prompt_dir, fname)
            if os.path.isfile(fpath):
                try:
                    fbytes = os.path.getsize(fpath)
                except OSError:
                    fbytes = 0
                fhsize = _human_size(fbytes)
                print(f"    - {fname} ({fhsize})")
        total_files += fcount
        total_bytes += nbytes
        has_content = True
    else:
        print("  (비어있음)")

    # 합계
    print()
    print("---")
    total_hsize = _human_size(total_bytes)
    print(f"합계: {total_files}개 파일, {total_hsize}")

    if not has_content:
        print()
        print("삭제할 내용이 없습니다.")


# --- execute 서브커맨드 ---

def cmd_execute():
    deleted_count = 0

    print("=== 작업 내역 삭제 실행 ===")
    print()

    # 1. .workflow 날짜 디렉토리 삭제 (YYYYMMDD-* 패턴)
    print("[.workflow/]")
    if os.path.isdir(_WORKFLOW_ROOT):
        for entry in sorted(os.listdir(_WORKFLOW_ROOT)):
            entry_path = os.path.join(_WORKFLOW_ROOT, entry)
            if os.path.isdir(entry_path) and entry[0:1].isdigit():
                shutil.rmtree(entry_path)
                print(f"  삭제 완료: .workflow/{entry}/")
                deleted_count += 1

    # 1-1. .workflow/.history/ 아카이브 디렉토리 삭제
    history_dir = os.path.join(_WORKFLOW_ROOT, ".history")
    if os.path.isdir(history_dir):
        for entry in os.listdir(history_dir):
            if entry[0:1].isdigit():
                entry_path = os.path.join(history_dir, entry)
                if os.path.isdir(entry_path):
                    shutil.rmtree(entry_path)
        print("  삭제 완료: .workflow/.history/[0-9]* (아카이브)")
        deleted_count += 1

    # 2. .prompt 파일 삭제 (history.md 보존)
    print()
    print("[.prompt/]")
    prompt_dir = os.path.join(_PROJECT_ROOT, ".prompt")
    if os.path.isdir(prompt_dir) and os.listdir(prompt_dir):
        # history.md 임시 백업
        history_path = os.path.join(prompt_dir, "history.md")
        history_backup = None
        if os.path.isfile(history_path):
            history_backup = os.path.join("/tmp", "_history_md_backup")
            shutil.copy2(history_path, history_backup)

        # 전체 삭제
        for item in os.listdir(prompt_dir):
            item_path = os.path.join(prompt_dir, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.unlink(item_path)

        # history.md 복원
        if history_backup and os.path.isfile(history_backup):
            shutil.move(history_backup, history_path)

        print("  삭제 완료: .prompt/* (history.md 보존)")
        deleted_count += 1
    else:
        print("  (비어있음, 스킵)")

    # 3. .workflow/registry.json 레지스트리 초기화
    print()
    print("[.workflow/registry.json]")
    registry_file = os.path.join(_PROJECT_ROOT, ".workflow", "registry.json")
    if os.path.isfile(registry_file):
        with open(registry_file, "w", encoding="utf-8") as f:
            f.write("{}\n")
        print("  초기화 완료: .workflow/registry.json ({})")
    else:
        os.makedirs(os.path.dirname(registry_file), exist_ok=True)
        with open(registry_file, "w", encoding="utf-8") as f:
            f.write("{}\n")
        print("  생성 완료: .workflow/registry.json ({})")

    print()
    print("---")
    print(f"삭제 완료: {deleted_count}개 디렉토리 정리됨")
    print()
    print("초기화된 파일:")
    print("  - .workflow/registry.json ({})")


# --- 메인 ---

def main():
    if len(sys.argv) < 2:
        print(f"사용법: {sys.argv[0]} <list|execute>")
        print()
        print("서브커맨드:")
        print("  list     삭제 대상 목록 및 크기 출력 (미리보기)")
        print("  execute  실제 삭제 실행")
        sys.exit(1)

    subcmd = sys.argv[1]

    if subcmd == "list":
        cmd_list()
    elif subcmd == "execute":
        cmd_execute()
    else:
        print(f"[ERROR] 알 수 없는 서브커맨드: {subcmd}")
        print(f"사용법: {sys.argv[0]} <list|execute>")
        sys.exit(1)


if __name__ == "__main__":
    main()
