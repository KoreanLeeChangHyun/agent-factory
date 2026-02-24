# Frontmatter 상세 가이드

SKILL.md의 YAML frontmatter 필드 상세 설명입니다.

## 필수/권장 필드

### name
```yaml
name: my-command
```
- 타입: string
- 기본값: 디렉토리 이름
- 규칙: 소문자, 숫자, 하이픈만 허용 (최대 64자)
- 용도: `/name`으로 명령어 호출

### description
```yaml
description: 코드 리뷰 수행. PR 생성 전이나 "리뷰해줘"라고 할 때 사용
```
- 타입: string
- **강력 권장**: Claude가 언제 이 명령어를 사용할지 판단하는 기준
- 포함할 내용:
  - 명령어가 하는 일
  - 언제 사용해야 하는지 (트리거 조건)
  - 키워드나 상황 예시

## 호출 제어 필드

### disable-model-invocation
```yaml
disable-model-invocation: true
```
- 타입: boolean
- 기본값: false
- 용도: Claude가 자동으로 이 명령어를 호출하는 것을 방지
- 사용 예: `/deploy`, `/commit`, `/send-email` 등 부작용이 있는 명령어

### user-invocable
```yaml
user-invocable: false
```
- 타입: boolean
- 기본값: true
- 용도: `/` 메뉴에서 숨김 (Claude만 호출 가능)
- 사용 예: 백그라운드 지식, 컨텍스트 정보

## 도구/권한 필드

### allowed-tools
```yaml
allowed-tools: Read, Grep, Glob, Bash
```
- 타입: comma-separated string
- 용도: 이 명령어 실행 중 사용 가능한 도구 제한
- 사용 예: 읽기 전용 명령어에 `Read, Grep, Glob`만 허용

### model
```yaml
model: sonnet
```
- 타입: string (sonnet | opus | haiku)
- 용도: 이 명령어 실행시 사용할 모델 지정
- 사용 예: 빠른 응답이 필요한 명령어에 `haiku`

## 서브에이전트 실행 필드

### context
```yaml
context: fork
```
- 타입: string
- 값: `fork`
- 용도: 명령어를 격리된 서브에이전트 컨텍스트에서 실행
- 주의: 대화 히스토리에 접근 불가

### agent
```yaml
agent: Explore
```
- 타입: string
- 기본값: general-purpose
- 조건: `context: fork`일 때만 유효
- 값: `Explore`, `Plan`, `general-purpose`, 또는 커스텀 에이전트 이름
- 용도: 서브에이전트 타입 지정

## UI 힌트 필드

### argument-hint
```yaml
argument-hint: "[issue-number]"
```
- 타입: string
- 용도: 자동완성시 인수 힌트 표시
- 예시: `[filename] [format]`, `[branch-name]`

## 훅 필드

### hooks
```yaml
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./validate.sh"
```
- 타입: object
- 용도: 명령어 라이프사이클에 훅 연결
- 참조: hooks 문서

## 조합 예시

### 읽기 전용 탐색 명령어
```yaml
---
name: explore-codebase
description: 코드베이스 구조 탐색. "구조 알려줘", "파일 찾아줘" 등에 반응
allowed-tools: Read, Grep, Glob
model: haiku
---
```

### 배포 명령어 (사용자만 호출)
```yaml
---
name: deploy
description: 프로덕션 배포 수행
disable-model-invocation: true
context: fork
allowed-tools: Bash, Read
---
```

### 서브에이전트로 실행되는 리서치 명령어
```yaml
---
name: research-deep
description: 주제에 대한 심층 조사
context: fork
agent: Explore
---
```

### 백그라운드 지식 (사용자 호출 불가)
```yaml
---
name: legacy-system-context
description: 레거시 시스템 동작 방식 설명. 관련 작업시 자동 로드
user-invocable: false
---
```
