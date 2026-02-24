# 클로드 코드 특화 패턴

Claude Code 환경에서 효과적인 프롬프트 작성을 위한 4가지 특화 패턴.

## 1. 에이전트 지시 패턴

서브에이전트 정의 및 역할 지시 시 효과적인 구조.

### 역할 정의 구조

```
You are a [전문 역할].
Your scope: [명확한 책임 범위].
When given a task:
1. [첫 번째 행동]
2. [두 번째 행동]
Always: [항상 준수할 규칙]
Never: [절대 하지 말아야 할 것]
```

### 도메인 전문성 선언

- 에이전트 역할의 범위를 **3개 이하의 도메인**으로 제한
- 권위 계층 명시: "공식 문서 > 코드베이스 > 추측" 순서
- 순차 결정 로직: 작업 유형 판별 -> 도구 선택 -> 실행 -> 검증

### 서브에이전트 frontmatter 패턴

```yaml
---
name: [에이전트명]
description: "[언제 이 에이전트를 사용하는지 트리거 조건 설명]"
tools: [Read, Grep, Glob, Bash, ...]
model: [opus|sonnet|haiku]
---
```

### 좋은 예

```
You are a security auditor for authentication modules.
Your scope: src/auth/ directory only.
When given a task:
1. Read all files in the target directory
2. Check for OWASP Top 10 vulnerabilities
3. Report findings with line numbers and severity
Always: Reference CWE IDs for each finding
Never: Modify code directly - report only
```

### 나쁜 예

```
코드를 보고 보안 문제가 있으면 알려줘
```

---

## 2. 도구 활용 힌트 패턴

Claude Code 내 도구 사용을 최적화하는 프롬프트 패턴.

### 병렬 도구 호출 극대화

독립적인 도구 호출은 반드시 병렬로 실행하도록 지시한다.

```
독립적인 파일 읽기는 병렬로 실행하시오.
예: 3개 파일 읽기 시 3개 Read를 동시에 실행.
단, 이전 호출 결과에 의존하는 경우에는 순차 실행.
```

### 탐색 전 분석 지시

코드 수정 전 기존 패턴 파악을 강제한다.

```
코드를 수정하기 전에:
1. [관련 파일 경로]를 Read로 읽고
2. [함수명]의 기존 패턴을 파악한 후
3. 변경 범위를 먼저 계획하고
4. 구현 시작
```

### 자기 검증 지시

구현 완료 후 검증을 자동 수행하도록 지시한다.

```
구현 완료 후:
- [테스트 명령]을 실행하고
- 실패한 테스트가 있으면 수정하고 재실행
- 모든 테스트 통과 확인 후 완료 보고
```

### 좋은 예

```
src/auth/session.ts와 src/auth/token.ts를 동시에 읽은 후,
세션 갱신 로직의 기존 패턴을 파악하시오.
파악 후 src/auth/refresh.ts에 토큰 갱신 함수를 구현하시오.
구현 후 npm test -- --grep "refresh" 실행하여 통과 확인하시오.
```

### 나쁜 예

```
토큰 갱신 기능 구현해줘
```

---

## 3. 컨텍스트 제공 패턴

Claude Code에 효과적으로 배경 정보를 전달하는 방법.

### @ 참조를 활용한 파일 컨텍스트

```
@src/auth/session.ts 파일의 패턴을 참고하여
@src/auth/ 디렉터리의 세션 관리 방식을 이해한 후
OAuth 연동 기능을 구현하시오.
```

### CLAUDE.md 컨텍스트 주입

CLAUDE.md에 포함해야 할 항목:

```markdown
# Code Style
- [언어별 import 방식, 명명 규칙 등 기존 관행과 다른 것만]

# Workflow
- [테스트 실행 명령, 린트 방법]
- [PR 컨벤션, 브랜치 명명 규칙]

# Architecture Notes
- [핵심 설계 결정 사항]
- [비자명한 패턴의 이유]
```

### CLAUDE.md 작성 원칙

- "이걸 제거해도 Claude가 실수할까?" 질문으로 각 줄 검토
- 코드에서 추론 가능한 내용 제외
- `IMPORTANT:` 또는 `YOU MUST:` 강조로 준수 강제
- 500줄 이하로 유지 (초과 시 Claude가 규칙을 무시하는 경향)

### Import 문법

```markdown
# CLAUDE.md
See @README.md for project overview and @package.json for available commands.

# Git workflow: @docs/git-instructions.md
```

### XML 태그를 활용한 지시 구조화

프로덕션 수준 프롬프트에서 XML 태그로 지시 구획화:

```xml
<role_definition>역할 정의</role_definition>
<development_directives>개발 원칙</development_directives>
<state_management>환경 컨텍스트</state_management>
```

### 스킬 description 작성 가이드

스킬 SKILL.md의 `description` 필드가 Claude의 스킬 선택 유일한 판단 기준.

- 트리거 조건(언제 사용하는지)을 description에 명확히 기술
- "Use when", "Triggers when" 패턴 활용
- 본문(body)에 "When to Use" 섹션을 넣어도 트리거에 영향 없음 (body는 트리거 후 로드)

---

## 4. 컨텍스트 창 관리 패턴

장시간 세션에서 성능 유지를 위한 프롬프트 패턴.

### 컨텍스트 압축 지시

```
When compacting, always preserve:
- 수정된 파일 전체 목록
- 테스트 실행 명령
- 핵심 설계 결정 사항
```

### 세션 재개 패턴

```
pwd를 실행하고, 이 디렉터리에서만 작업하시오.
progress.txt, tests.json, git log를 검토한 후
기본 통합 테스트를 실행하고 통과 확인 후 새 기능 구현 시작.
```

### 컨텍스트 오염 방지

- 무관한 작업 간 `/clear` 실행 지시 포함
- 서브에이전트로 탐색 위임하여 메인 컨텍스트 보호
- "2회 이상 같은 수정을 지시한 경우 `/clear` 후 새 프롬프트로 재시작" 안내

### Progressive Disclosure 원칙

- CLAUDE.md는 짧고 인간이 읽기 쉽게 유지 (500줄 이하)
- 도메인별 세부 규칙은 스킬(SKILL.md)로 분리
- 자주 변경되는 정보는 CLAUDE.md에서 제외
