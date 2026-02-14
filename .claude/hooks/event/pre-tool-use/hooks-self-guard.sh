#!/bin/bash
# hooks 디렉토리 자기 보호 가드 Hook 스크립트
# PreToolUse(Write|Edit|Bash) 이벤트에서 .claude/hooks/ 경로 파일 수정을 차단
#
# 입력: stdin으로 JSON (tool_name, tool_input)
# 출력: 차단 시 hookSpecificOutput JSON, 통과 시 빈 출력
#
# 우회: 환경변수 HOOKS_EDIT_ALLOWED=1 설정 시 차단 해제
#       (사용자가 명시적으로 수정을 요청한 경우 오케스트레이터가 설정)

# stdin에서 JSON 읽기
INPUT=$(cat)

# tool_name 확인 (Write, Edit, Bash가 아니면 통과)
TOOL_NAME=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_name', ''))
except:
    print('')
" 2>/dev/null)

if [ "$TOOL_NAME" != "Write" ] && [ "$TOOL_NAME" != "Edit" ] && [ "$TOOL_NAME" != "Bash" ]; then
    exit 0
fi

# --- Bash 도구 분기 ---
if [ "$TOOL_NAME" = "Bash" ]; then
    # command 필드 추출
    BASH_CMD=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tool_input = data.get('tool_input', {})
    print(tool_input.get('command', ''))
except:
    print('')
" 2>/dev/null)

    # command에 .claude/hooks/ 경로가 없으면 통과
    if ! echo "$BASH_CMD" | grep -q '\.claude/hooks/' 2>/dev/null; then
        exit 0
    fi

    # 환경변수 우회 검사
    if [ "$HOOKS_EDIT_ALLOWED" = "1" ]; then
        exit 0
    fi

    # 읽기 전용 명령 화이트리스트 검사
    # .claude/hooks/ 를 인자로 사용하되 수정하지 않는 명령은 통과
    IS_READONLY=$(echo "$BASH_CMD" | python3 -c "
import sys, re

cmd = sys.stdin.read().strip()

# 읽기 전용 명령 패턴 화이트리스트
# 이 명령들이 .claude/hooks/ 경로를 참조하더라도 파일을 수정하지 않으므로 통과
readonly_patterns = [
    r'^\s*git\s',
    r'^\s*python3?\s',
    r'^\s*node\s',
    r'^\s*cat\s',
    r'^\s*ls\b',
    r'^\s*head\s',
    r'^\s*tail\s',
    r'^\s*wc\s',
    r'^\s*grep\s',
    r'^\s*file\s',
    r'^\s*stat\s',
    r'^\s*diff\s',
    r'^\s*bash\s',
    r'^\s*sh\s',
    r'^\s*source\s',
    r'^\s*\.\s',
    r'^\s*exec\s',
    r'^\s*env\s',
    r'^(?:\s*\w+=\S*\s+)*(?:bash|sh|python3?|node)\s',
    r'^\s*less\s',
    r'^\s*more\s',
    r'^\s*find\s',
    r'^\s*tree\b',
    r'^\s*realpath\s',
    r'^\s*readlink\s',
    r'^\s*sha256sum\s',
    r'^\s*md5sum\s',
    r'^\s*test\s',
    r'^\s*\[\s',
]

# 파이프라인/연결 명령 분리: &&, ||, ;, | 등으로 분할하여 각 서브커맨드 검사
subcmds = re.split(r'\s*(?:&&|\|\||[;|])\s*', cmd)
# \$() 와 backtick 내부 명령도 추출
subcmds += re.findall(r'\$\(([^)]+)\)', cmd)
subcmds += re.findall(r'\x60([^\x60]+)\x60', cmd)

# 수정 가능 패턴 (이 패턴이 .claude/hooks/ 를 타겟으로 하면 차단)
modify_patterns = [
    r'sed\s+.*-i',
    r'sed\s+-i',
    r'\bcp\b',
    r'\bmv\b',
    r'echo\s.*>\s*',
    r'echo\s.*>>\s*',
    r'printf\s.*>\s*',
    r'printf\s.*>>\s*',
    r'\btee\b',
    r'cat\s.*>\s*',
    r'cat\s.*>>\s*',
    r'\bdd\b',
    r'\binstall\b',
    r'\brsync\b',
    r'\bchmod\b',
    r'\bchown\b',
    r'ln\s+-sf?\b',
    r'rm\s+-rf?\b',
    r'rm\s+-f\b',
    r'\btouch\b',
    r'\bmkdir\b',
    r'\brmdir\b',
    r'>\s*\S',
    r'>>\s*\S',
]

hooks_path_re = re.compile(r'\.claude/hooks/')

for sc in subcmds:
    sc = sc.strip()
    if not sc:
        continue
    # 이 서브커맨드가 .claude/hooks/ 를 참조하는지
    if not hooks_path_re.search(sc):
        continue
    # 읽기 전용 명령인지 검사
    is_ro = False
    for ro_pat in readonly_patterns:
        if re.match(ro_pat, sc):
            is_ro = True
            break
    if is_ro:
        continue
    # 수정 패턴 검사
    for mod_pat in modify_patterns:
        if re.search(mod_pat, sc):
            print('MODIFY')
            sys.exit(0)
    # 명시적 수정 패턴에 매칭되지 않아도,
    # 읽기 전용 화이트리스트에도 없으면 안전 차단 (보수적 접근)
    print('MODIFY')
    sys.exit(0)

# 모든 서브커맨드가 읽기 전용이거나 .claude/hooks/ 를 참조하지 않음
print('READONLY')
" 2>/dev/null)

    if [ "$IS_READONLY" = "READONLY" ]; then
        exit 0
    fi

    # 차단
    python3 -c "
import json
reason = 'Bash를 통한 hooks 디렉토리 파일 수정이 차단되었습니다. 사용자의 명시적 수정 요청이 필요합니다.'
result = {
    'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'deny',
        'permissionDecisionReason': reason
    }
}
print(json.dumps(result, ensure_ascii=False))
" 2>/dev/null
    exit 0
fi

# --- Write / Edit 도구 분기 ---
# file_path 필드 추출
FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tool_input = data.get('tool_input', {})
    print(tool_input.get('file_path', ''))
except:
    print('')
" 2>/dev/null)

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# .claude/hooks/ 경로 포함 여부 검사
if echo "$FILE_PATH" | grep -q '\.claude/hooks/' 2>/dev/null; then
    # 환경변수 우회 검사
    if [ "$HOOKS_EDIT_ALLOWED" = "1" ]; then
        exit 0
    fi

    # 차단
    python3 -c "
import json
reason = 'hooks 디렉토리 파일 수정이 차단되었습니다. 사용자의 명시적 수정 요청이 필요합니다.'
result = {
    'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'deny',
        'permissionDecisionReason': reason
    }
}
print(json.dumps(result, ensure_ascii=False))
" 2>/dev/null
    exit 0
fi

# .claude/hooks/ 경로 미매칭 시 빈 출력 (통과)
exit 0
