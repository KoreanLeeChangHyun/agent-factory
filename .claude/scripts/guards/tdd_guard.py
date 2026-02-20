#!/usr/bin/env -S python3 -u
"""
TDD Guard Hook 스크립트

PreToolUse(Write/Edit) 이벤트에서 소스 파일 수정 시 테스트 파일 존재 여부 확인.
테스트 미존재 시 경고 (차단하지 않음, strict 모드에서는 차단).

입력: stdin으로 JSON (tool_name, tool_input)
출력: strict 모드에서 차단 시 hookSpecificOutput JSON, 통과 시 빈 출력
      기본 모드에서 테스트 미존재 시 stderr 경고
"""

import json
import os
import re
import sys

# _utils 패키지 import 경로 설정
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from _utils.env_utils import read_env


def _deny(reason):
    """차단 JSON을 출력하고 종료."""
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


# 제외 대상 디렉터리 패턴
EXCLUDED_DIR_PATTERNS = [
    r"\.claude/",
    r"\.workflow/",
    r"\.prompt/",
]

# 테스트 파일 이름 패턴
TEST_FILE_PATTERNS = re.compile(r"(_test\.|\.test\.|_spec\.|\.spec\.|^test_)")

# 테스트 디렉터리 패턴
TEST_DIR_PATTERNS = re.compile(r"(tests?/|__tests__/|spec/)")

# 설정 파일 확장자
CONFIG_EXTENSIONS = {"json", "yaml", "yml", "toml", "ini", "cfg", "env", "lock"}

# 문서 파일 확장자
DOC_EXTENSIONS = {"md", "txt", "rst", "adoc", "doc", "docx"}

# 빌드/스크립트 파일 확장자
BUILD_EXTENSIONS = {"sh", "bat", "cmd", "ps1"}

# 빌드/스크립트 파일명
BUILD_FILENAMES = {"Makefile", "Dockerfile", "docker-compose.yml", "docker-compose.yaml"}

# 정적/스타일 파일 확장자
STATIC_EXTENSIONS = {
    "css", "scss", "less", "sass", "html", "htm", "svg",
    "png", "jpg", "jpeg", "gif", "ico", "woff", "woff2", "ttf", "eot",
}

# 패키지 관리 파일명
PACKAGE_FILENAMES = {
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "requirements.txt", "Pipfile", "Pipfile.lock",
    "Cargo.toml", "Cargo.lock", "go.mod", "go.sum",
    "Gemfile", "Gemfile.lock",
}

# 소스 파일 확장자
SOURCE_EXTENSIONS = {
    "js", "jsx", "ts", "tsx", "mjs", "cjs",
    "py", "rs", "go", "java", "c", "cpp", "h", "hpp", "rb", "php",
}


def _is_excluded(file_path, filename, extension):
    """제외 대상 파일인지 검사."""
    # 1. 제외 디렉터리
    for pattern in EXCLUDED_DIR_PATTERNS:
        if re.search(pattern, file_path):
            return True

    # 2. 테스트 파일 자체
    if TEST_FILE_PATTERNS.search(filename):
        return True

    # 3. 테스트 디렉터리 내 파일
    if TEST_DIR_PATTERNS.search(file_path):
        return True

    # 4. 설정 파일
    if extension in CONFIG_EXTENSIONS:
        return True

    # 5. 문서 파일
    if extension in DOC_EXTENSIONS:
        return True

    # 6. 빌드/스크립트 파일
    if extension in BUILD_EXTENSIONS:
        return True
    if filename in BUILD_FILENAMES:
        return True

    # 7. 정적/스타일 파일
    if extension in STATIC_EXTENSIONS:
        return True

    # 8. 패키지 관리 파일
    if filename in PACKAGE_FILENAMES:
        return True

    # 9. 타입 정의 파일
    if filename.endswith(".d.ts"):
        return True
    if re.search(r"(types|interfaces)\.", filename):
        return True

    return False


def _find_test_patterns(file_path, basename, extension, dirpath):
    """확장자별 테스트 파일 패턴 목록 생성."""
    patterns = []

    if extension in ("js", "jsx", "ts", "tsx", "mjs", "cjs"):
        patterns = [
            os.path.join(dirpath, f"{basename}.test.{extension}"),
            os.path.join(dirpath, f"{basename}.spec.{extension}"),
            os.path.join(dirpath, f"{basename}_test.{extension}"),
            os.path.join(dirpath, "__tests__", f"{basename}.test.{extension}"),
            os.path.join(dirpath, "__tests__", f"{basename}.spec.{extension}"),
        ]
        # .tsx -> .test.tsx, .test.ts 모두 체크
        if extension in ("tsx", "jsx"):
            base_ext = extension[:-1]  # tsx -> ts, jsx -> js
            patterns += [
                os.path.join(dirpath, f"{basename}.test.{base_ext}"),
                os.path.join(dirpath, f"{basename}.spec.{base_ext}"),
            ]

    elif extension == "py":
        patterns = [
            os.path.join(dirpath, f"test_{basename}.py"),
            os.path.join(dirpath, f"{basename}_test.py"),
            os.path.join(dirpath, "__tests__", f"test_{basename}.py"),
        ]
        # 프로젝트 루트의 tests/ 디렉토리도 확인
        rel_path = re.sub(r".*/src/", "", dirpath)
        if rel_path != dirpath:
            project_root = re.sub(r"/src/.*", "", dirpath)
            patterns += [
                os.path.join(project_root, "tests", rel_path, f"test_{basename}.py"),
                os.path.join(project_root, "tests", f"test_{basename}.py"),
            ]

    elif extension == "go":
        patterns = [
            os.path.join(dirpath, f"{basename}_test.go"),
        ]

    elif extension == "java":
        patterns = [
            os.path.join(dirpath, f"{basename}Test.java"),
            os.path.join(dirpath, f"{basename}Tests.java"),
        ]
        # src/main -> src/test 매핑
        test_dir = dirpath.replace("/src/main/", "/src/test/")
        if test_dir != dirpath:
            patterns += [
                os.path.join(test_dir, f"{basename}Test.java"),
                os.path.join(test_dir, f"{basename}Tests.java"),
            ]

    elif extension in ("c", "cpp", "h", "hpp"):
        patterns = [
            os.path.join(dirpath, f"{basename}_test.{extension}"),
            os.path.join(dirpath, f"test_{basename}.{extension}"),
        ]

    elif extension == "rb":
        patterns = [
            os.path.join(dirpath, f"{basename}_test.rb"),
            os.path.join(dirpath, f"{basename}_spec.rb"),
        ]
        spec_dir = dirpath.replace("/lib/", "/spec/")
        if spec_dir != dirpath:
            patterns.append(os.path.join(spec_dir, f"{basename}_spec.rb"))

    elif extension == "php":
        patterns = [
            os.path.join(dirpath, f"{basename}Test.php"),
        ]
        test_dir = dirpath.replace("/src/", "/tests/")
        if test_dir != dirpath:
            patterns.append(os.path.join(test_dir, f"{basename}Test.php"))

    return patterns


def main():
    # .claude.env에서 설정 로드
    hook_flag = os.environ.get("HOOK_TDD") or read_env("HOOK_TDD")

    # Hook disable check (false = disabled)
    if hook_flag in ("false", "0"):
        sys.exit(0)

    # stdin에서 JSON 읽기
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    # Write/Edit가 아니면 통과
    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # 파일명과 확장자 추출
    filename = os.path.basename(file_path)
    if "." in filename:
        extension = filename.rsplit(".", 1)[1]
        basename_no_ext = filename.rsplit(".", 1)[0]
    else:
        extension = ""
        basename_no_ext = filename
    dirpath = os.path.dirname(file_path)

    # 제외 대상 검사
    if _is_excluded(file_path, filename, extension):
        sys.exit(0)

    # 소스 파일 확인
    if extension not in SOURCE_EXTENSIONS:
        sys.exit(0)

    # Rust는 같은 파일 내 테스트가 일반적이므로 경고하지 않음
    if extension == "rs":
        sys.exit(0)

    # 테스트 파일 탐색
    test_patterns = _find_test_patterns(file_path, basename_no_ext, extension, dirpath)
    found_test = any(os.path.isfile(p) for p in test_patterns)

    # 테스트 미존재 시 처리
    if not found_test:
        # 상대 경로로 변환하여 표시
        try:
            cwd = os.getcwd()
            rel_file = os.path.relpath(file_path, cwd)
        except ValueError:
            rel_file = file_path

        if hook_flag == "strict":
            # strict 모드: deny
            _deny(
                f"[TDD-GUARD] {rel_file}에 대한 테스트 파일이 없습니다. "
                f"strict 모드에서 차단합니다."
            )
        else:
            # 기본 모드: stderr로 경고만 출력 (차단하지 않음)
            print(
                f"[TDD-GUARD] 경고: {rel_file}에 대한 테스트 파일이 없습니다. "
                f"테스트를 먼저 작성하는 것을 권장합니다.",
                file=sys.stderr,
            )

    sys.exit(0)


if __name__ == "__main__":
    main()
