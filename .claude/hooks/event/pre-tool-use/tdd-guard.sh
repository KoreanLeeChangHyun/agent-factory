#!/bin/bash
# TDD Guard Hook 스크립트
# PreToolUse(Write/Edit) 이벤트에서 소스 파일 수정 시 테스트 파일 존재 여부 확인
# 테스트 미존재 시 경고 (차단하지 않음)
#
# 입력: stdin으로 JSON (tool_name, tool_input)
# 출력: 항상 빈 stdout (차단하지 않음), 경고는 stderr로 출력

# Guard disable check
if [ "$GUARD_TDD" = "0" ]; then exit 0; fi

# stdin에서 JSON 읽기
INPUT=$(cat)

# tool_name과 file_path 추출
PARSED=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tool_name = data.get('tool_name', '')
    tool_input = data.get('tool_input', {})
    file_path = tool_input.get('file_path', '')
    print(f'{tool_name}\n{file_path}')
except:
    print('\n')
" 2>/dev/null)

TOOL_NAME=$(echo "$PARSED" | sed -n '1p')
FILE_PATH=$(echo "$PARSED" | sed -n '2p')

# Write/Edit가 아니면 통과
if [ "$TOOL_NAME" != "Write" ] && [ "$TOOL_NAME" != "Edit" ]; then
    exit 0
fi

# file_path가 비어있으면 통과
if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# 파일명과 확장자 추출
FILENAME=$(basename "$FILE_PATH")
EXTENSION="${FILENAME##*.}"
BASENAME="${FILENAME%.*}"
DIRPATH=$(dirname "$FILE_PATH")

# === 제외 대상 검사 ===

# 1. .claude/ 디렉토리 (스킬, 에이전트, 설정 파일)
if echo "$FILE_PATH" | grep -q '\.claude/' 2>/dev/null; then
    exit 0
fi

# 2. .workflow/ 디렉토리 (워크플로우 문서)
if echo "$FILE_PATH" | grep -q '\.workflow/' 2>/dev/null; then
    exit 0
fi

# 3. .prompt/ 디렉토리
if echo "$FILE_PATH" | grep -q '\.prompt/' 2>/dev/null; then
    exit 0
fi

# 4. 테스트 파일 자체
if echo "$FILENAME" | grep -qP '(_test\.|\.test\.|_spec\.|\.spec\.|^test_)' 2>/dev/null; then
    exit 0
fi

# 5. 테스트 디렉토리 내 파일
if echo "$FILE_PATH" | grep -qP '(tests?/|__tests__/|spec/)' 2>/dev/null; then
    exit 0
fi

# 6. 설정 파일
case "$EXTENSION" in
    json|yaml|yml|toml|ini|cfg|env|lock)
        exit 0
        ;;
esac

# 7. 문서 파일
case "$EXTENSION" in
    md|txt|rst|adoc|doc|docx)
        exit 0
        ;;
esac

# 8. 빌드/스크립트 파일
case "$EXTENSION" in
    sh|bat|cmd|ps1)
        exit 0
        ;;
esac
case "$FILENAME" in
    Makefile|Dockerfile|docker-compose.yml|docker-compose.yaml)
        exit 0
        ;;
esac

# 9. 정적/스타일 파일
case "$EXTENSION" in
    css|scss|less|sass|html|htm|svg|png|jpg|jpeg|gif|ico|woff|woff2|ttf|eot)
        exit 0
        ;;
esac

# 10. 패키지 관리 파일
case "$FILENAME" in
    package.json|package-lock.json|yarn.lock|pnpm-lock.yaml|requirements.txt|Pipfile|Pipfile.lock|Cargo.toml|Cargo.lock|go.mod|go.sum|Gemfile|Gemfile.lock)
        exit 0
        ;;
esac

# 11. 타입 정의 파일
if echo "$FILENAME" | grep -qP '\.d\.ts$' 2>/dev/null; then
    exit 0
fi
if echo "$FILENAME" | grep -qP '(types|interfaces)\.' 2>/dev/null; then
    exit 0
fi

# === 소스 파일 확인 ===

# 소스 파일 확장자 목록
case "$EXTENSION" in
    js|jsx|ts|tsx|mjs|cjs|py|rs|go|java|c|cpp|h|hpp|rb|php)
        # 소스 파일 - 테스트 존재 여부 확인 진행
        ;;
    *)
        # 인식되지 않은 확장자 - 통과
        exit 0
        ;;
esac

# === 테스트 파일 탐색 ===

FOUND_TEST=false

# 확장자별 테스트 패턴 생성
# JavaScript/TypeScript: .test.ts, .spec.ts, _test.ts
# Python: test_*.py, *_test.py
# Go: _test.go
# Rust: (같은 파일 내 #[cfg(test)] 모듈 - 파일 레벨 검사 어려움, 통과)
# Java: *Test.java

# Rust는 같은 파일 내 테스트가 일반적이므로 경고하지 않음
if [ "$EXTENSION" = "rs" ]; then
    exit 0
fi

# 탐색할 테스트 파일 패턴 목록 생성
TEST_PATTERNS=()

case "$EXTENSION" in
    js|jsx|ts|tsx|mjs|cjs)
        TEST_PATTERNS=(
            "${DIRPATH}/${BASENAME}.test.${EXTENSION}"
            "${DIRPATH}/${BASENAME}.spec.${EXTENSION}"
            "${DIRPATH}/${BASENAME}_test.${EXTENSION}"
            "${DIRPATH}/__tests__/${BASENAME}.test.${EXTENSION}"
            "${DIRPATH}/__tests__/${BASENAME}.spec.${EXTENSION}"
        )
        # .tsx -> .test.tsx, .test.ts 모두 체크
        if [ "$EXTENSION" = "tsx" ] || [ "$EXTENSION" = "jsx" ]; then
            BASE_EXT="${EXTENSION%x}"
            TEST_PATTERNS+=(
                "${DIRPATH}/${BASENAME}.test.${BASE_EXT}"
                "${DIRPATH}/${BASENAME}.spec.${BASE_EXT}"
            )
        fi
        ;;
    py)
        TEST_PATTERNS=(
            "${DIRPATH}/test_${BASENAME}.py"
            "${DIRPATH}/${BASENAME}_test.py"
            "${DIRPATH}/__tests__/test_${BASENAME}.py"
        )
        # 프로젝트 루트의 tests/ 디렉토리도 확인
        # DIRPATH에서 src/ 이후 상대경로 추출 시도
        REL_PATH=$(echo "$DIRPATH" | sed 's|.*/src/||' 2>/dev/null)
        if [ -n "$REL_PATH" ] && [ "$REL_PATH" != "$DIRPATH" ]; then
            # 프로젝트 루트 추정 (src/ 상위)
            PROJECT_ROOT=$(echo "$DIRPATH" | sed 's|/src/.*||')
            TEST_PATTERNS+=(
                "${PROJECT_ROOT}/tests/${REL_PATH}/test_${BASENAME}.py"
                "${PROJECT_ROOT}/tests/test_${BASENAME}.py"
            )
        fi
        ;;
    go)
        TEST_PATTERNS=(
            "${DIRPATH}/${BASENAME}_test.go"
        )
        ;;
    java)
        TEST_PATTERNS=(
            "${DIRPATH}/${BASENAME}Test.java"
            "${DIRPATH}/${BASENAME}Tests.java"
        )
        # src/main -> src/test 매핑
        TEST_DIR=$(echo "$DIRPATH" | sed 's|/src/main/|/src/test/|')
        if [ "$TEST_DIR" != "$DIRPATH" ]; then
            TEST_PATTERNS+=(
                "${TEST_DIR}/${BASENAME}Test.java"
                "${TEST_DIR}/${BASENAME}Tests.java"
            )
        fi
        ;;
    c|cpp|h|hpp)
        TEST_PATTERNS=(
            "${DIRPATH}/${BASENAME}_test.${EXTENSION}"
            "${DIRPATH}/test_${BASENAME}.${EXTENSION}"
        )
        ;;
    rb)
        TEST_PATTERNS=(
            "${DIRPATH}/${BASENAME}_test.rb"
            "${DIRPATH}/${BASENAME}_spec.rb"
        )
        # spec/ 디렉토리 탐색
        SPEC_DIR=$(echo "$DIRPATH" | sed 's|/lib/|/spec/|' 2>/dev/null)
        if [ "$SPEC_DIR" != "$DIRPATH" ]; then
            TEST_PATTERNS+=(
                "${SPEC_DIR}/${BASENAME}_spec.rb"
            )
        fi
        ;;
    php)
        TEST_PATTERNS=(
            "${DIRPATH}/${BASENAME}Test.php"
        )
        TEST_DIR=$(echo "$DIRPATH" | sed 's|/src/|/tests/|' 2>/dev/null)
        if [ "$TEST_DIR" != "$DIRPATH" ]; then
            TEST_PATTERNS+=(
                "${TEST_DIR}/${BASENAME}Test.php"
            )
        fi
        ;;
esac

# 테스트 파일 존재 확인
for PATTERN in "${TEST_PATTERNS[@]}"; do
    if [ -f "$PATTERN" ]; then
        FOUND_TEST=true
        break
    fi
done

# 테스트 미존재 시 경고 (stderr로 출력, 차단하지 않음)
if [ "$FOUND_TEST" = false ]; then
    # 상대 경로로 변환하여 표시
    REL_FILE=$(echo "$FILE_PATH" | sed "s|$(pwd)/||" 2>/dev/null)
    if [ -z "$REL_FILE" ]; then
        REL_FILE="$FILE_PATH"
    fi
    echo "[TDD-GUARD] 경고: ${REL_FILE}에 대한 테스트 파일이 없습니다. 테스트를 먼저 작성하는 것을 권장합니다." >&2
fi

# 항상 통과 (차단하지 않음 - stdout은 비어있음)
exit 0
