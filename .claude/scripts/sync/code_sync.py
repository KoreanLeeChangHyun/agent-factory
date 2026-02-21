#!/usr/bin/env -S python3 -u
"""
code_sync.py - .claude 디렉토리 원격 동기화 스크립트

원격 리포(https://github.com/KoreanLeeChangHyun/claude-workflow.git)에서
.claude 디렉토리를 가져와 현재 프로젝트에 rsync --delete로 덮어쓰기합니다.
.claude.env 파일은 보존됩니다.

사용법: python3 code_sync.py [--dry-run]
"""

import atexit
import os
import shutil
import subprocess
import sys
import tempfile

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", "..", ".."))

_REMOTE_REPO = "https://github.com/KoreanLeeChangHyun/claude-workflow.git"
_ENV_FILE = os.path.join(_PROJECT_ROOT, ".claude.env")

_TEMP_DIR = tempfile.mkdtemp(prefix="claude-sync-")
_CLONE_DIR = os.path.join(_TEMP_DIR, "claude-remote")
_BACKUP_DIR = os.path.join(_TEMP_DIR, "sync-backup")

_sync_success = False
_dry_run = False


def _cleanup():
    """정리 함수 (에러 시에도 임시 파일 제거)."""
    if _sync_success:
        shutil.rmtree(_TEMP_DIR, ignore_errors=True)
    else:
        shutil.rmtree(_CLONE_DIR, ignore_errors=True)
        if not _dry_run and os.path.isdir(_BACKUP_DIR):
            print(f"[WARN] 에러 발생으로 백업이 유지됩니다: {_BACKUP_DIR}", file=sys.stderr)


atexit.register(_cleanup)


def main():
    global _sync_success, _dry_run

    # --- 인자 파싱 ---
    for arg in sys.argv[1:]:
        if arg == "--dry-run":
            _dry_run = True
        elif arg in ("-h", "--help"):
            print(f"사용법: {os.path.basename(sys.argv[0])} [--dry-run]")
            print()
            print("원격 리포에서 .claude 디렉토리를 동기화합니다.")
            print()
            print("옵션:")
            print("  --dry-run    실제 동기화 없이 변경 사항만 미리보기")
            print("  -h, --help   도움말 출력")
            sys.exit(0)
        else:
            print(f"[ERROR] 알 수 없는 옵션: {arg}", file=sys.stderr)
            print(f"사용법: {os.path.basename(sys.argv[0])} [--dry-run]")
            sys.exit(1)

    # --- 1. 사전 확인 ---
    print("=== .claude 동기화 시작 ===")
    print()

    local_env_exists = os.path.isfile(_ENV_FILE)
    if local_env_exists:
        print("[INFO] .claude.env 파일 감지 - 동기화 시 보존됩니다.")
    else:
        print("[INFO] .claude.env 파일 없음 - 보존 대상 없음.")
    print()

    # --- 2. 로컬 보존 파일 임시 저장 ---
    if not _dry_run and local_env_exists:
        os.makedirs(_BACKUP_DIR, exist_ok=True)
        shutil.copy2(_ENV_FILE, os.path.join(_BACKUP_DIR, ".env"))
        print(f"[BACKUP] .claude.env -> {_BACKUP_DIR}/.env")

    # --- 3. 원격 리포지토리 클론 ---
    print(f"[CLONE] {_REMOTE_REPO} (shallow clone)...")
    if os.path.isdir(_CLONE_DIR):
        shutil.rmtree(_CLONE_DIR)

    result = subprocess.run(
        ["git", "clone", "--depth", "1", _REMOTE_REPO, _CLONE_DIR],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        print()
        print("[ERROR] git clone 실패.")
        print("  - 네트워크 연결을 확인하세요.")
        print(f"  - 리포지토리 URL을 확인하세요: {_REMOTE_REPO}")
        print()
        print("  HTTPS 접속이 차단되어 있다면 네트워크 환경(프록시, 방화벽 등)을 확인하세요.")
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        sys.exit(1)
    print("[CLONE] 완료.")
    print()

    # 원격에 .claude 디렉토리가 있는지 확인
    if not os.path.isdir(os.path.join(_CLONE_DIR, ".claude")):
        print("[ERROR] 원격 리포지토리에 .claude 디렉토리가 없습니다.", file=sys.stderr)
        sys.exit(1)

    # --- 4. .claude 디렉토리 동기화 ---
    src = os.path.join(_CLONE_DIR, ".claude") + "/"
    dst = os.path.join(_PROJECT_ROOT, ".claude") + "/"

    if _dry_run:
        print("[DRY-RUN] 변경 사항 미리보기:")
        print("---")
        subprocess.run(
            ["rsync", "-av", "--delete", "--dry-run", "--exclude=/.env", src, dst],
            timeout=60
        )
        print("---")
        print()
        print("[DRY-RUN] 위 내용은 미리보기입니다. 실제 변경은 수행되지 않았습니다.")
    else:
        # 삭제 대상 파일 사전 확인
        result = subprocess.run(
            ["rsync", "-av", "--delete", "--dry-run", "--exclude=/.env", src, dst],
            capture_output=True, text=True, timeout=60
        )
        delete_preview = "\n".join(
            line for line in result.stdout.split("\n") if line.startswith("deleting ")
        )
        if delete_preview:
            print("[WARN] 다음 파일이 삭제됩니다:")
            print(delete_preview)
            print()

        print("[SYNC] rsync --delete 실행 중...")
        sync_result = subprocess.run(
            ["rsync", "-av", "--delete", "--exclude=/.env", src, dst],
            timeout=120
        )
        if sync_result.returncode != 0:
            print()
            print("[ERROR] rsync 동기화 실패.")
            print("  - 디스크 공간을 확인하세요.")
            print(f"  - 대상 디렉토리 쓰기 권한을 확인하세요: {dst}")
            sys.exit(1)
        print("[SYNC] 완료.")
        print()

        # --- 5. 보존 파일 복원 ---
        backup_env = os.path.join(_BACKUP_DIR, ".env")
        if os.path.isfile(backup_env):
            try:
                shutil.copy2(backup_env, _ENV_FILE)
                print("[RESTORE] .claude.env 복원 완료.")
            except Exception:
                print()
                print("[ERROR] .claude.env 복원 실패.")
                print(f"  - 백업 파일 경로: {backup_env}")
                print(f'  - 수동으로 복원하세요: cp "{backup_env}" "{_ENV_FILE}"')
                sys.exit(1)

    _sync_success = True

    # --- 6. 결과 출력 ---
    print()
    print("=== .claude 동기화 완료 ===")
    print()
    print(f"[소스] {_REMOTE_REPO}")
    print("[대상] .claude/")
    print("[방식] 덮어쓰기 (rsync --delete)")
    print("[보존] .claude.env")
    if _dry_run:
        print("[모드] dry-run (미리보기만 수행)")

    # --- 7. 버전 출력 ---
    version_file = os.path.join(_PROJECT_ROOT, ".claude", ".version")
    if os.path.isfile(version_file):
        try:
            version = open(version_file, "r").read().strip()
            print(f"[VERSION] v{version}")
        except Exception:
            pass

    print()
    print("다음 단계:")
    print("  - /init:workflow 로 워크플로우를 재초기화하세요")


if __name__ == "__main__":
    main()
