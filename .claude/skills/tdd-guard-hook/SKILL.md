---
name: tdd-guard-hook
description: "TDD (Test-Driven Development) principle violation monitor via PreToolUse hooks. Warns when attempting to modify source files without corresponding tests. Use for TDD enforcement: (1) verifying test file existence when modifying source files, (2) warning on code modification without tests, (3) naturally improving test coverage. Triggers: '테스트', 'test', 'TDD', '테스트 주도 개발'."
license: "Apache-2.0"
---

# TDD Guard Hook

TDD(Test-Driven Development) 원칙 준수를 모니터링하는 PreToolUse Hook 스킬입니다.
소스 파일을 수정할 때 관련 테스트 파일이 존재하는지 확인하고, 없으면 경고를 표시합니다.

## 목적

- TDD 원칙(테스트 먼저 작성) 위반을 모니터링
- 테스트 없이 소스 코드를 수정하려는 시도에 경고
- 테스트 커버리지를 자연스럽게 향상
- **차단하지 않고 경고만** (개발 흐름을 방해하지 않음)
- **strict 모드**: `GUARD_TDD=strict` 환경변수 설정 시 테스트 미존재 파일의 Write/Edit를 차단 (stdout에 차단 메시지 출력, exit 0)

## 동작 방식

### Hook 이벤트

- **이벤트**: `PreToolUse`
- **매처**: `Write`, `Edit`
- **스크립트**: `.claude/hooks/event/pre-tool-use/tdd-guard.sh`

### 판단 로직

```
파일 경로 입력
    |
    v
[제외 대상인가?] --YES--> 통과 (경고 없음)
    |NO
    v
[소스 파일인가?] --NO---> 통과 (경고 없음)
    |YES
    v
[테스트 파일 존재?] --YES--> 통과 (경고 없음)
    |NO
    v
[strict 모드?] --YES--> 차단 메시지 출력 (stdout)
    |NO
    v
경고 메시지 출력 (stderr, 차단하지 않음)
```

### 제외 대상 (경고하지 않는 파일)

| 카테고리 | 패턴 | 이유 |
|----------|------|------|
| 테스트 파일 | `*_test.*`, `*.test.*`, `*_spec.*`, `*.spec.*`, `test_*.*` | 테스트 파일 자체 |
| 테스트 디렉토리 | `tests/`, `__tests__/`, `test/`, `spec/` | 테스트 디렉토리 내 파일 |
| 설정 파일 | `*.json`, `*.yaml`, `*.yml`, `*.toml`, `*.ini`, `*.cfg`, `*.env` | 설정 파일 |
| 문서 파일 | `*.md`, `*.txt`, `*.rst`, `*.adoc` | 문서 파일 |
| 빌드 파일 | `Makefile`, `Dockerfile`, `*.sh`, `*.bat` | 빌드/스크립트 파일 |
| 워크플로우 | `.workflow/**` | 워크플로우 문서 |
| 스킬/에이전트 | `.claude/**` | Claude Code 설정 파일 |
| 정적 파일 | `*.css`, `*.scss`, `*.less`, `*.html`, `*.svg` | 스타일/마크업 |
| 패키지 관리 | `package.json`, `package-lock.json`, `requirements.txt`, `Cargo.toml` | 패키지 파일 |
| 타입 정의 | `*.d.ts`, `*types.*`, `*interfaces.*` | 타입 선언 파일 |

### 소스 파일 인식

다음 확장자를 소스 파일로 인식합니다:
- **JavaScript/TypeScript**: `.js`, `.jsx`, `.ts`, `.tsx`, `.mjs`, `.cjs`
- **Python**: `.py`
- **Rust**: `.rs`
- **Go**: `.go`
- **Java**: `.java`
- **C/C++**: `.c`, `.cpp`, `.h`, `.hpp`
- **Ruby**: `.rb`
- **PHP**: `.php`

### 테스트 파일 탐색 패턴

소스 파일 `src/utils/helper.ts`에 대해 다음 위치에서 테스트 파일을 탐색합니다:

```
1. 같은 디렉토리:
   - src/utils/helper.test.ts
   - src/utils/helper.spec.ts
   - src/utils/helper_test.ts

2. __tests__ 디렉토리:
   - src/utils/__tests__/helper.test.ts
   - src/utils/__tests__/helper.spec.ts

3. tests/ 디렉토리 (프로젝트 루트):
   - tests/utils/helper.test.ts
   - tests/utils/test_helper.ts

4. test/ 디렉토리:
   - test/utils/helper.test.ts
   - test/utils/helper_test.ts

5. Python 패턴:
   - tests/test_helper.py
   - src/utils/test_helper.py
```

## Hook 스크립트

**경로**: `.claude/hooks/event/pre-tool-use/tdd-guard.sh`

### 입력 (stdin JSON)

```json
{
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/home/user/project/src/utils/helper.ts",
    "content": "..."
  }
}
```

또는:

```json
{
  "tool_name": "Edit",
  "tool_input": {
    "file_path": "/home/user/project/src/utils/helper.ts",
    "old_string": "...",
    "new_string": "..."
  }
}
```

### 출력

**테스트 미존재 시 (경고):**
빈 출력이지만 stderr에 경고 메시지를 출력합니다.
```
[TDD-GUARD] 경고: src/utils/helper.ts에 대한 테스트 파일이 없습니다. 테스트를 먼저 작성하는 것을 권장합니다.
```

**참고**: 기본 모드에서는 경고만 하고 차단하지 않습니다. 따라서 stdout에는 아무것도 출력하지 않으며 (통과), stderr로 경고 메시지만 전달합니다.

**테스트 미존재 시 (strict 모드 - 차단):**
stdout에 차단 JSON을 출력합니다.
```json
{"decision": "block", "reason": "[TDD-GUARD] src/utils/helper.ts에 대한 테스트 파일이 없습니다. strict 모드에서 차단합니다."}
```

**통과 시:**
빈 출력 (stdout에 아무것도 출력하지 않음)

## settings.json 등록

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/event/pre-tool-use/tdd-guard.sh",
            "statusMessage": "TDD 가드 검사 중..."
          }
        ]
      }
    ]
  }
}
```

## strict 모드 활성화

### 환경변수 설정

```bash
export GUARD_TDD=strict
```

`GUARD_TDD` 환경변수를 `strict`로 설정하면 테스트 파일이 없는 소스 파일에 대한 Write/Edit를 차단합니다. 미설정 또는 다른 값일 경우 기존 경고 전용 모드로 동작합니다.

| 환경변수 값 | 동작 |
|------------|------|
| 미설정 | 경고 모드 (stderr 경고, 차단하지 않음) |
| `0` | Hook 비활성화 (검사하지 않음) |
| `strict` | strict 모드 (stdout JSON 출력으로 차단) |

### 사용 시나리오

- **implement 명령어의 Level 3+ 품질 레벨에서 권장**: 코드 품질 기준이 높은 작업에서 테스트 없는 코드 작성을 사전에 차단
- **TDD 원칙을 엄격히 적용해야 하는 프로젝트**: Red-Green-Refactor 사이클을 강제하여 테스트 선행 작성을 보장
- **CI/CD 파이프라인 연동 시**: 빌드 전 테스트 커버리지 보장을 위한 게이트로 활용

## 적용 단계

- **WORK**: implement, refactor 명령어에서 코드 작성/수정 시 자동 실행
- 모든 Write/Edit 도구 호출에서 동작

## 참고

- Hook 스크립트: `.claude/hooks/event/pre-tool-use/tdd-guard.sh`
- 설정 파일: `.claude/settings.json`
- 관련: TDD Red-Green-Refactor 사이클
