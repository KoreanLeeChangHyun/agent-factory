#!/bin/bash
# hooks 디렉토리 자기 보호 가드 Hook 스크립트
# PreToolUse(Write|Edit) 이벤트에서 .claude/hooks/ 경로 파일 수정을 차단
#
# 입력: stdin으로 JSON (tool_name, tool_input)
# 출력: 차단 시 hookSpecificOutput JSON, 통과 시 빈 출력
#
# 우회: 환경변수 HOOKS_EDIT_ALLOWED=1 설정 시 차단 해제
#       (사용자가 명시적으로 수정을 요청한 경우 오케스트레이터가 설정)

# stdin에서 JSON 읽기
INPUT=$(cat)

# tool_name 확인 (Write 또는 Edit가 아니면 통과)
TOOL_NAME=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_name', ''))
except:
    print('')
" 2>/dev/null)

if [ "$TOOL_NAME" != "Write" ] && [ "$TOOL_NAME" != "Edit" ]; then
    exit 0
fi

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
