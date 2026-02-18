#!/usr/bin/env -S python3 -u
"""
init_claude.py - Claude Code 사용자 환경 초기화 스크립트

사용법: python3 init_claude.py <subcommand> [args]

서브커맨드:
  check-alias          alias 존재 여부 체크 (JSON 출력)
  setup-alias          alias 추가 (~/.zshrc에)
  setup-statusline     StatusLine 전체 설정
  setup-slack <url>    Slack 환경변수 설정 (.claude.env에 추가)
  setup-git            Git global 설정 (.claude.env 읽어서 git config)
  verify               전체 설정 검증
"""

import json
import os
import re
import subprocess
import sys
import tempfile

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
sys.path.insert(0, _SCRIPTS_DIR)

from _utils.env_utils import read_env, set_env

_PROJECT_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
_ENV_FILE = os.path.join(_PROJECT_ROOT, ".claude.env")
_ZSHRC = os.path.join(os.environ.get("HOME", ""), ".zshrc")
_CLAUDE_SETTINGS = os.path.join(os.environ.get("HOME", ""), ".claude", "settings.json")
_STATUSLINE_SCRIPT = os.path.join(os.environ.get("HOME", ""), ".claude", "statusline.sh")

# 블록 마커 상수
_ALIAS_BLOCK_BEGIN = "# >>> Claude Code aliases"
_ALIAS_BLOCK_END = "# <<< Claude Code aliases"


def _json_escape(s):
    """JSON 문자열 이스케이프."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")


def _json_result(status, message, **kwargs):
    """JSON 결과 출력."""
    result = {"status": status, "message": message}
    result.update(kwargs)
    print(json.dumps(result, ensure_ascii=False))


# ---------- check-alias ----------

def cmd_check_alias():
    cc_exists = False
    ccc_exists = False
    cc_value = ""
    ccc_value = ""

    if os.path.isfile(_ZSHRC):
        with open(_ZSHRC, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("alias cc="):
                    cc_exists = True
                    if not cc_value:
                        cc_value = line.strip()
                if line.startswith("alias ccc="):
                    ccc_exists = True
                    if not ccc_value:
                        ccc_value = line.strip()

    result = {"status": "ok", "cc_exists": cc_exists, "ccc_exists": ccc_exists}
    if cc_value:
        result["cc_value"] = cc_value
    if ccc_value:
        result["ccc_value"] = ccc_value
    print(json.dumps(result, ensure_ascii=False))


# ---------- setup-alias ----------

def cmd_setup_alias():
    if not os.path.isfile(_ZSHRC):
        open(_ZSHRC, "a").close()

    with open(_ZSHRC, "r", encoding="utf-8") as f:
        content = f.read()

    changed = False

    # --- 1. 블록 마커 방식으로 기존 블록 제거 ---
    if _ALIAS_BLOCK_BEGIN in content:
        pattern = re.escape(_ALIAS_BLOCK_BEGIN) + r".*?" + re.escape(_ALIAS_BLOCK_END) + r"\n?"
        content = re.sub(pattern, "", content, flags=re.DOTALL)
        changed = True

    # --- 2. 레거시 패턴 호환 삭제 ---
    if re.search(r"^alias cc=", content, re.MULTILINE):
        content = re.sub(r"^alias cc=.*\n?", "", content, flags=re.MULTILINE)
        changed = True

    if re.search(r"^alias ccc=", content, re.MULTILINE):
        content = re.sub(r"^alias ccc=.*\n?", "", content, flags=re.MULTILINE)
        changed = True

    if re.search(r"^# Claude Code aliases$", content, re.MULTILINE):
        content = re.sub(r"^# Claude Code aliases\n?", "", content, flags=re.MULTILINE)

    # --- 3. 연속 빈 줄 정리 (2줄 이상 -> 1줄) ---
    content = re.sub(r"\n{3,}", "\n\n", content)

    # --- 4. 새 alias 블록 추가 ---
    block = (
        f"\n{_ALIAS_BLOCK_BEGIN}\n"
        'export PATH="$HOME/.local/bin:$PATH"\n'
        "alias cc='claude --dangerously-skip-permissions \"/init:workflow\"'\n"
        "alias ccc='claude --dangerously-skip-permissions --continue'\n"
        f"{_ALIAS_BLOCK_END}\n"
    )
    content += block

    with open(_ZSHRC, "w", encoding="utf-8") as f:
        f.write(content)

    if changed:
        _json_result("ok", "alias cc, ccc가 업데이트되었습니다.", action="updated")
    else:
        _json_result("ok", "alias cc, ccc가 추가되었습니다.", action="created")


# ---------- setup-statusline ----------

def cmd_setup_statusline():
    settings_updated = False
    script_created = False

    # --- 1. settings.json 설정 ---
    os.makedirs(os.path.dirname(_CLAUDE_SETTINGS), exist_ok=True)

    if not os.path.isfile(_CLAUDE_SETTINGS):
        with open(_CLAUDE_SETTINGS, "w", encoding="utf-8") as f:
            json.dump({
                "statusLine": {
                    "type": "command",
                    "command": "~/.claude/statusline.sh",
                    "padding": 0,
                }
            }, f, indent=2, ensure_ascii=False)
            f.write("\n")
        settings_updated = True
    else:
        with open(_CLAUDE_SETTINGS, "r", encoding="utf-8") as f:
            settings_content = f.read()
        if '"statusLine"' not in settings_content:
            try:
                data = json.loads(settings_content)
                data["statusLine"] = {
                    "type": "command",
                    "command": "~/.claude/statusline.sh",
                    "padding": 0,
                }
                with open(_CLAUDE_SETTINGS, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.write("\n")
                settings_updated = True
            except Exception as e:
                _json_result("error", "settings.json 병합 중 오류가 발생했습니다.",
                             settings_updated="false", script_created="false",
                             error_detail=str(e))
                sys.exit(1)

    # --- 2. statusline.sh 스크립트 생성 ---
    if not os.path.isfile(_STATUSLINE_SCRIPT):
        statusline_content = '''#!/usr/bin/env python3
import json, sys, subprocess

data = json.load(sys.stdin)

model = data.get("model", {}).get("display_name", "?")
added = data.get("cost", {}).get("total_lines_added", 0)
removed = data.get("cost", {}).get("total_lines_removed", 0)
ctx_size = data.get("context_window", {}).get("context_window_size", 0)
usage = data.get("context_window", {}).get("current_usage")
cwd = data.get("workspace", {}).get("current_dir", "")

pct = 0
if usage and ctx_size:
    tokens = (usage.get("input_tokens", 0)
              + usage.get("cache_creation_input_tokens", 0)
              + usage.get("cache_read_input_tokens", 0))
    pct = tokens * 100 // ctx_size

branch = ""
try:
    b = subprocess.check_output(
        ["git", "-C", cwd, "branch", "--show-current"],
        stderr=subprocess.DEVNULL, timeout=2
    ).decode().strip()
    if b:
        branch = f" \\033[33m{b}\\033[0m"
except Exception:
    pass

print(f"\\033[36m{model}\\033[0m{branch} \\033[35mctx:{pct}%\\033[0m \\033[32m+{added}\\033[0m/\\033[31m-{removed}\\033[0m")
'''
        with open(_STATUSLINE_SCRIPT, "w", encoding="utf-8") as f:
            f.write(statusline_content)
        os.chmod(_STATUSLINE_SCRIPT, 0o755)
        script_created = True

    result = {
        "status": "ok",
        "message": "StatusLine 설정 완료",
        "settings_updated": settings_updated,
        "script_created": script_created,
        "settings_path": _CLAUDE_SETTINGS,
        "script_path": _STATUSLINE_SCRIPT,
    }
    print(json.dumps(result, ensure_ascii=False))


# ---------- setup-slack ----------

def cmd_setup_slack(args):
    if not args:
        _json_result("error", "Slack Webhook URL이 필요합니다. 사용법: init_claude.py setup-slack <url>")
        sys.exit(1)

    url = args[0]

    if not re.match(r"^https?://", url):
        _json_result("error", f"올바른 URL 형식이 아닙니다: {url}")
        sys.exit(1)

    # .claude.env에 설정
    set_env("CLAUDE_CODE_SLACK_WEBHOOK_URL", url, env_file=_ENV_FILE)

    # ~/.zshrc에 export 추가 (중복 체크)
    if not os.path.isfile(_ZSHRC):
        open(_ZSHRC, "a").close()

    with open(_ZSHRC, "r", encoding="utf-8") as f:
        content = f.read()

    if re.search(r"^export CLAUDE_CODE_SLACK_WEBHOOK_URL=", content, re.MULTILINE):
        # 기존 값 업데이트 (라인 교체)
        lines = content.split("\n")
        new_lines = []
        for line in lines:
            if line.startswith("export CLAUDE_CODE_SLACK_WEBHOOK_URL="):
                new_lines.append(f'export CLAUDE_CODE_SLACK_WEBHOOK_URL="{url}"')
            else:
                new_lines.append(line)
        with open(_ZSHRC, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines))
        _json_result("ok", "CLAUDE_CODE_SLACK_WEBHOOK_URL이 업데이트되었습니다.", action="updated")
    else:
        with open(_ZSHRC, "a", encoding="utf-8") as f:
            if "# Slack Webhook for Claude Code" not in content:
                f.write("\n# Slack Webhook for Claude Code\n")
            f.write(f'export CLAUDE_CODE_SLACK_WEBHOOK_URL="{url}"\n')
        _json_result("ok", "CLAUDE_CODE_SLACK_WEBHOOK_URL이 추가되었습니다.", action="created")


# ---------- setup-git ----------

def cmd_setup_git():
    if not os.path.isfile(_ENV_FILE):
        # 템플릿 생성
        with open(_ENV_FILE, "w", encoding="utf-8") as f:
            f.write(
                "# ============================================\n"
                "# Claude Code 환경 변수\n"
                "# ============================================\n"
                "#\n"
                "# 이 파일은 Claude Code Hook 스크립트에서 사용하는 환경 변수를 정의합니다.\n"
                "# 형식: KEY=value (표준 .env 문법)\n"
                "# ============================================\n"
                "\n"
                "# ============================================\n"
                "# [REQUIRED] Git 설정\n"
                "# ============================================\n"
                "CLAUDE_CODE_GIT_USER_NAME=\n"
                "CLAUDE_CODE_GIT_USER_EMAIL=\n"
                "\n"
                "# ============================================\n"
                "# [REQUIRED] SSH 키\n"
                "# ============================================\n"
                "CLAUDE_CODE_SSH_KEY_GITHUB=\n"
                "\n"
                "# ============================================\n"
                "# [OPTIONAL] 추가 설정\n"
                "# ============================================\n"
                "# CLAUDE_CODE_GITHUB_USERNAME=\n"
                "# CLAUDE_CODE_SSH_CONFIG=\n"
            )
        _json_result("skip", ".claude.env 파일을 생성했습니다. 편집 후 다시 실행하세요.", env_path=_ENV_FILE)
        return

    git_user_name = read_env("CLAUDE_CODE_GIT_USER_NAME", env_file=_ENV_FILE)
    git_user_email = read_env("CLAUDE_CODE_GIT_USER_EMAIL", env_file=_ENV_FILE)
    ssh_key_github = read_env("CLAUDE_CODE_SSH_KEY_GITHUB", env_file=_ENV_FILE)

    if not git_user_name or not git_user_email:
        _json_result("error",
                      "CLAUDE_CODE_GIT_USER_NAME 또는 CLAUDE_CODE_GIT_USER_EMAIL이 설정되지 않았습니다.",
                      env_path=_ENV_FILE)
        sys.exit(1)

    # Before 상태 수집
    def _git_config(key):
        try:
            return subprocess.check_output(
                ["git", "config", "--global", key],
                stderr=subprocess.DEVNULL, timeout=5
            ).decode().strip()
        except Exception:
            return "(unset)"

    before_name = _git_config("user.name")
    before_email = _git_config("user.email")
    before_ssh = _git_config("core.sshCommand")

    # Git config 설정
    subprocess.run(["git", "config", "--global", "user.name", git_user_name],
                    check=True, timeout=5)
    subprocess.run(["git", "config", "--global", "user.email", git_user_email],
                    check=True, timeout=5)

    # SSH 키 설정
    ssh_configured = False
    ssh_key_warning = ""
    if ssh_key_github:
        if os.path.isfile(ssh_key_github):
            subprocess.run(
                ["git", "config", "--global", "core.sshCommand",
                 f'ssh -i "{ssh_key_github}" -o IdentitiesOnly=yes'],
                check=True, timeout=5)
            ssh_configured = True
        else:
            ssh_key_warning = f"파일 미존재: {ssh_key_github}"

    # After 상태 수집
    after_name = _git_config("user.name")
    after_email = _git_config("user.email")
    after_ssh = _git_config("core.sshCommand")

    result = {
        "status": "ok",
        "message": "Git global 설정 완료",
        "before": {"user_name": before_name, "user_email": before_email, "ssh_command": before_ssh},
        "after": {"user_name": after_name, "user_email": after_email, "ssh_command": after_ssh},
        "ssh_configured": ssh_configured,
    }
    if ssh_key_warning:
        result["ssh_key_warning"] = ssh_key_warning
    print(json.dumps(result, ensure_ascii=False))


# ---------- verify ----------

def cmd_verify():
    all_ok = True

    # 1. Shell alias 검증
    alias_cc = False
    alias_ccc = False
    if os.path.isfile(_ZSHRC):
        with open(_ZSHRC, "r", encoding="utf-8") as f:
            zshrc_content = f.read()
        alias_cc = bool(re.search(r"^alias cc=", zshrc_content, re.MULTILINE))
        alias_ccc = bool(re.search(r"^alias ccc=", zshrc_content, re.MULTILINE))
    if not alias_cc or not alias_ccc:
        all_ok = False

    # 2. StatusLine settings.json 검증
    statusline_settings = False
    if os.path.isfile(_CLAUDE_SETTINGS):
        try:
            with open(_CLAUDE_SETTINGS, "r", encoding="utf-8") as f:
                if '"statusLine"' in f.read():
                    statusline_settings = True
        except Exception:
            pass
    if not statusline_settings:
        all_ok = False

    # 3. StatusLine 스크립트 검증
    statusline_script = os.path.isfile(_STATUSLINE_SCRIPT) and os.access(_STATUSLINE_SCRIPT, os.X_OK)
    if not statusline_script:
        all_ok = False

    # 4. Slack 환경변수 검증 (선택사항)
    slack_env = False
    slack_source = ""
    if os.path.isfile(_ENV_FILE):
        try:
            env_content = open(_ENV_FILE, "r", encoding="utf-8").read()
            if re.search(r"^CLAUDE_CODE_SLACK_BOT_TOKEN=.+", env_content, re.MULTILINE):
                slack_env = True
                slack_source = "claude_env"
            elif re.search(r"^CLAUDE_CODE_SLACK_WEBHOOK_URL=.+", env_content, re.MULTILINE):
                slack_env = True
                slack_source = "claude_env"
        except Exception:
            pass
    if not slack_env and os.path.isfile(_ZSHRC):
        try:
            zshrc = open(_ZSHRC, "r", encoding="utf-8").read()
            if re.search(r"^export CLAUDE_CODE_SLACK_WEBHOOK_URL=.+", zshrc, re.MULTILINE):
                slack_env = True
                slack_source = "zshrc"
        except Exception:
            pass

    # 5. PATH에 ~/.local/bin 포함 여부 검증
    home = os.environ.get("HOME", "")
    local_bin = os.path.join(home, ".local", "bin")
    path_local_bin = local_bin in os.environ.get("PATH", "").split(":")
    path_local_bin_zshrc = False
    if os.path.isfile(_ZSHRC):
        try:
            zshrc = open(_ZSHRC, "r", encoding="utf-8").read()
            if re.search(r'export PATH=.*\$HOME/\.local/bin', zshrc):
                path_local_bin_zshrc = True
        except Exception:
            pass
    if not path_local_bin and not path_local_bin_zshrc:
        all_ok = False

    # 6. Git 설정 검증
    git_name = ""
    git_email = ""
    try:
        git_name = subprocess.check_output(
            ["git", "config", "--global", "user.name"],
            stderr=subprocess.DEVNULL, timeout=5
        ).decode().strip()
    except Exception:
        pass
    try:
        git_email = subprocess.check_output(
            ["git", "config", "--global", "user.email"],
            stderr=subprocess.DEVNULL, timeout=5
        ).decode().strip()
    except Exception:
        pass
    git_configured = bool(git_name and git_email)
    if not git_configured:
        all_ok = False

    result = {
        "status": "ok" if all_ok else "partial",
        "message": "전체 설정 검증 완료" if all_ok else "일부 설정이 누락되었습니다",
        "checks": {
            "alias_cc": alias_cc,
            "alias_ccc": alias_ccc,
            "statusline_settings": statusline_settings,
            "statusline_script": statusline_script,
            "slack_configured": slack_env,
            "path_local_bin": path_local_bin,
            "path_local_bin_zshrc": path_local_bin_zshrc,
            "git_configured": git_configured,
            "git_user_name": git_name,
            "git_user_email": git_email,
        },
    }
    if slack_source:
        result["checks"]["slack_source"] = slack_source
    print(json.dumps(result, ensure_ascii=False))


# ---------- 메인 디스패치 ----------

def main():
    subcmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    rest = sys.argv[2:]

    dispatch = {
        "check-alias": lambda: cmd_check_alias(),
        "setup-alias": lambda: cmd_setup_alias(),
        "setup-statusline": lambda: cmd_setup_statusline(),
        "setup-slack": lambda: cmd_setup_slack(rest),
        "setup-git": lambda: cmd_setup_git(),
        "verify": lambda: cmd_verify(),
    }

    if subcmd in ("help", "--help", "-h"):
        print("init_claude.py - Claude Code 사용자 환경 초기화 스크립트")
        print()
        print("사용법:")
        print("  python3 init_claude.py <subcommand> [args]")
        print()
        print("서브커맨드:")
        print("  check-alias          alias 존재 여부 체크 (JSON 출력)")
        print("  setup-alias          alias 추가 (~/.zshrc에)")
        print("  setup-statusline     StatusLine 전체 설정 (settings.json + statusline.sh)")
        print("  setup-slack <url>    Slack Webhook URL 설정 (.claude.env + ~/.zshrc에 추가)")
        print("  setup-git            Git global 설정 (.claude.env 읽어서 git config)")
        print("  verify               전체 설정 검증 (JSON 출력)")
        print("  help                 이 도움말 표시")
        return

    if subcmd in dispatch:
        dispatch[subcmd]()
    else:
        _json_result("error", f"알 수 없는 서브커맨드: {subcmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
