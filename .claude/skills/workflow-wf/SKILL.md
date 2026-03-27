---
name: workflow-wf
description: "Workflow command skills for wf commands: implement, prompt, research, review, submit. Handles code implementation, prompt co-authoring, research/analysis, code review, and ticket submission workflows."
disable-model-invocation: true
skills:
  - research-prompt-engineering
license: "Apache-2.0"
---

# Workflow-WF Command Skills

워크플로우 `/wf` 명령어 5종(implement, prompt, research, review, submit)의 통합 스킬.
PLAN→WORK→REPORT→DONE FSM은 `workflow-orchestration/SKILL.md`를 따른다. prompt·submit은 FSM과 무관한 독립 명령어.

> **워크플로우 스킬 로드**: implement·research·review 실행 시작 전 `.claude/skills/workflow-orchestration/SKILL.md`를 Read로 로드하세요.

---

## Implement Command

코드 구현, 수정, 리팩토링을 수행하는 워크플로우 커맨드 스킬.

### 리팩토링 지원

#### 대상 결정

1. 요청에 리팩토링 대상이 명시된 경우 → 해당 대상
2. 요청에 대상이 불명확한 경우 → 최근 리뷰 대상 (`.workflow/<최신작업디렉토리>/report.md` 참조)

#### 키워드 기반 스킬 로드

작업 내용에 리팩토링 관련 키워드(`리팩토링`, `refactor`, `코드 개선`, `추출`, `extract`)가 포함되면 `review-code-quality` 스킬이 자동 로드되어 코드 품질 검사를 병행합니다.

### 아키텍처/다이어그램 지원

#### 키워드 기반 스킬 로드

작업 내용에 아키텍처 관련 키워드(`아키텍처`, `architecture`, `설계`, `architect`, `시스템 구조`, `컴포넌트`)가 포함되면 `design-architect` + `design-mermaid-diagrams` 스킬이 자동 로드됩니다.

#### 지원 기능

| 기능 | 설명 |
|------|------|
| 다이어그램 유형 선택 | 클래스, 시퀀스, ER, 컴포넌트, 상태, 플로우차트 6종 |
| Mermaid 코드 생성 | `.md` 파일로 Mermaid 코드 저장 |
| PNG 변환 | `mmdc -i <file>.md -o <file>.png` (mmdc CLI 사용) |

### 에셋 관리 (에이전트/스킬/커맨드)

사용자 요청에 에이전트, 스킬, 커맨드 관리가 포함된 경우 아래 키워드 매핑에 따라 적절한 Manager 스킬을 실행합니다.

#### 키워드 매핑

| 키워드 | 대상 | 실행할 스킬 |
|--------|------|-------------|
| 에이전트, agent | 에이전트 | management-agent |
| 스킬, skill | 스킬 | management-skill |
| 커맨드, command, 명령어 | 커맨드 | management-command |

#### 에셋 경로

| 에셋 | 경로 |
|------|------|
| 에이전트 | `.claude/agents/*.md` |
| 스킬 | `.claude/skills/<skill-name>/` |
| 커맨드 | `.claude/commands/wf.md` |

### 구현 완료 검증

`workflow-system` 스킬 연동. 구현 완료 후 아래 4단계 검증을 순서대로 수행한다.

1. **빌드/컴파일 확인**: 변경 파일 대상으로 빌드 또는 컴파일 오류가 없는지 확인
2. **테스트 실행**: 관련 테스트를 실행하여 모두 통과하는지 확인
3. **타입 체크**: 타입스크립트 등 정적 타입 언어의 경우 타입 체크 통과 확인
4. **재검증 루프**: 검증 실패 시 즉시 수정 후 해당 단계부터 재검증. 모든 단계 통과 후 완료 선언

### 동적 컨텍스트 (implement)

구현 시작 시 현재 작업 상태를 자동 파악하여 컨텍스트에 포함한다.

```
!git diff --name-only
!git status
```

### 프로젝트 플로우 연동 (implement)

REPORT 단계 완료 후 티켓 상태를 자동 전이한다.

```bash
flow-kanban move T-NNN review
```

티켓 번호는 `wf.md` Steps 3-1~3-4에서 파싱된 `#N` 인자를 사용한다. 티켓 파일 경로는 `.kanban/open/T-NNN.xml`이다.

- 구현이 완료된 티켓을 Review 상태로 전이한다
- `wf -s implement #N` 실행 시 `wf.md`가 이미 티켓 XML 내용을 파싱하여 전달하므로 별도 파싱은 불필요하다

> **Review 후속 흐름**: Review 전이 후 사용자가 `/wf -d N`으로 간단 검토 -> 완료/상세 review 분기를 진행한다. 워크플로우 완료 시점에서 자동 merge는 수행되지 않는다.

### cleanup 절차 (implement/research/review 공통)

워크플로우 완료 시 tmux 윈도우 자동 종료가 이중 안전장치로 동작한다:

- **1차 (finalization.py Step 5)**: `flow-finish` 실행 시 3초 지연 후 tmux 윈도우를 백그라운드(nohup+sleep)로 kill. `flow-claude end` 배너 출력이 보장된 후 종료
- **2차 (PostToolUse hook)**: `flow-claude end` Bash 호출 감지 시 5초 지연 후 tmux 윈도우를 추가로 kill. 1차 안전장치 실패 시 보완
- **비tmux 환경**: `TMUX_PANE` 미설정 시 양쪽 모두 자동 스킵 (멱등성 보장)

---

## Prompt Command (자유 대화형 프롬프트 공동 작성)

> **스킬 의존성**: `research-prompt-engineering` (frontmatter `skills:` 필드에 명시됨)

`.kanban/open/T-NNN.xml` 티켓 파일을 사용자와의 자유 대화를 통해 점진적으로 작성하거나 개선하는 워크플로우 커맨드 스킬. 워크플로우(FSM/가드/서브에이전트)와 무관한 독립 명령어.

티켓 파일은 XML 구조를 사용합니다:
- 루트 요소: `<ticket>`
- `<metadata>` 래퍼: `<number>`, `<title>`, `<datetime>`, `<status>`, `<current>` (현재 활성 subnumber는 `<current>` 값으로 결정)
- `<submit>` 래퍼: active subnumber 목록
- `<history>` 래퍼: 비활성(이전 사이클) subnumber 목록
- 작업 단위: `<subnumber id="N">` (직하에 `<command>` 태그, `<prompt>` 래퍼 내에 goal/target/constraints/criteria/context)

상세 실행 절차는 `.claude/commands/wf.md`를 참조한다.

### 스킬 의존성 (prompt)

실행 시작 전 `.claude/skills/research-prompt-engineering/SKILL.md`를 Read로 로드한다.

용도 키워드 기반으로 하위 references를 선택적으로 추가 로드한다:

| 용도 키워드 | 추가 로드 대상 |
|------------|---------------|
| 구현, 기능, 함수, 모듈, 버그, 오류, 에러, 수정 | `references/prompt-templates.md` |
| 리팩토링, 정리, 분리, 리뷰, 검토 | `references/prompt-templates.md` |
| 조사, 비교, 연구, 설계, 아키텍처, 시스템 | `references/prompt-templates.md` |
| 에이전트, 서브에이전트, 도구 | `references/claude-code-patterns.md` |
| 용도 불명확 | `references/prompt-templates.md` + `references/claude-code-patterns.md` 모두 |

### XML 티켓 처리 규칙

- `<command>` 태그는 `<subnumber id="N">` 직하(자식)에 위치. `<prompt>` 래퍼 밖에 배치됨. 잠금 판정은 XML `<status>` 요소(`Open`/`In Progress`/`Review`)로 판별
- `<goal>`, `<target>`, `<constraints>`, `<criteria>`, `<context>` 태그는 subnumber 내부의 `<prompt>` 래퍼 안에 위치
- 사용자 입력 갱신은 현재 활성 subnumber(`<current>` 값) 내부의 `<prompt>` 래퍼 자식 요소를 대상으로 함
- 기존 티켓 편집 시 원시 XML 대신 읽기 쉬운 구조화 형식으로 출력

### 웹검색/코드탐색 자율 수행

대화 루프의 매 턴에서 LLM이 자율 판단으로 웹검색/코드베이스 탐색을 수행한다. 수행 여부를 사용자에게 사전에 묻지 않으며, 탐색/검색 결과는 핵심을 요약하여 제안·선택지 형태로 제공한다.

예: "코드베이스를 확인한 결과 `src/auth/token.ts`에 유사한 패턴이 있습니다. 이 패턴을 참고할까요?"

| 감지 신호 | 수행 액션 | 사용 도구 |
|----------|----------|----------|
| 함수, 모듈, 파일, 클래스, 컴포넌트, 변수, 메서드 | 코드베이스 탐색 | Grep, Glob, Read |
| API, 프레임워크, 패키지, 버전, 라이브러리, SDK, 외부 서비스 | 웹검색 | WebSearch, WebFetch |
| 양쪽 신호 모두 감지 | 코드베이스 탐색 + 웹검색 모두 수행 | Grep, Glob, Read, WebSearch, WebFetch |

### 비워크플로우 독립 명령어 (prompt)

이 스킬은 워크플로우 FSM과 무관하게 독립 실행된다. 사용 가능 도구: Bash, Read, Write, AskUserQuestion, Glob, Grep, WebSearch, WebFetch. Task 도구 호출 금지. Bash는 Step D(티켓 종료), done 폴백 복원, Step 2 새 티켓 생성에서 허용.

이 스킬의 실행 절차는 대응 커맨드 파일(`.claude/commands/wf.md`)이 Single Source of Truth이다.

---

## Research Command

웹 검색 기반 연구/조사 및 내부 자산 분석을 수행하는 워크플로우 커맨드 스킬.

### 연구 절차

1. **주제 파악 및 범위 정의**
   - 연구 주제 파악 (기술 조사 / 개념 연구 / 비교 분석)
   - 조사 깊이, 범위, 시간 범위 정의
   - 비교 대상 확인 (해당 시)

2. **정보 수집**
   - WebSearch: 최신 정보, 문서, 블로그 등
   - WebFetch: 특정 페이지 상세 내용
   - Grep, Glob, Read: 코드베이스 탐색, 기존 사용 패턴

3. **분석 및 정리**
   - 핵심 개념 추출
   - 장단점 분석
   - 비교 분석 (해당 시)
   - 실제 적용 가능성 평가
   - 주의사항 및 제한사항

4. **리포트 작성**
   - 구조화된 문서 생성
   - 출처 명시
   - 리포트는 `.workflow/<YYYYMMDD-HHMMSS>/<작업명>/research/report.md`에 저장된다

리포트 템플릿, 주의사항 등 상세 절차는 research-general 스킬(`.claude/skills/research-general/SKILL.md`)을 참조한다.

### 코드 수정 금지 제약

> **WARNING**: 리서치 워크플로우에서 Edit/Write 도구로 소스 코드를 수정하는 행위는 절대 금지된다. research는 보고서만 산출하므로 코드 수정이 불필요하다.

| 구분 | 대상 | 허용 여부 |
|------|------|----------|
| 허용 | 보고서 파일(report.md, work/*.md) 읽기/쓰기 | O |
| 금지 | 소스 코드 파일(.js, .ts, .py, .css, .html 등) 수정 (Edit/Write 도구) | X |

이 제약은 `readonly_session_guard.py` PreToolUse 가드로 기술적으로 강제됨.

### 출처 검증 기준

| 등급 | 출처 유형 | 날짜 기준 |
|------|----------|----------|
| S | 공식 문서, RFC, 표준 규격 | 최신 버전 확인 필수 |
| A | 주요 오픈소스 저장소, 공인 기관 발행물 | 최근 1년 이내 권장 |
| B | 기술 블로그(검증된 저자), 컨퍼런스 발표 자료 | 최근 2년 이내 |
| C | 일반 블로그, 포럼, Q&A 사이트 | 교차 검증 필수 |
| D | 출처 불명, 비공개 자료 | 사용 자제, 사용 시 명시적 경고 |

### 분석 지원

연구/조사 외에 내부 자산 분석도 이 커맨드에서 수행한다.

#### 분석 유형

| 유형 | 스킬 | 키워드 |
|------|------|--------|
| 요구사항 분석 | analyze-srs | 요구사항, 명세서, 스펙, SRS, 기능 정의, requirement, spec |
| 코드베이스 분석 | analyze-codebase | 코드베이스, 아키텍처, 코드 구조, 의존성, 모듈, codebase, architecture |
| 데이터베이스 분석 | analyze-database | 데이터베이스, DB, 스키마, 테이블, ERD, 인덱스, database, schema |
| 데이터 분석 | analyze-data | 데이터 분석, 통계, 데이터셋, EDA, 시각화, data analysis, statistics |
| 기본값 | analyze-srs | (분석 키워드 있으나 유형 불명 시) |

#### 분석 유형 판단

1. 요청 문자열을 소문자로 변환
2. 각 유형의 키워드를 순서대로 확인
3. 첫 번째 매칭된 키워드의 유형 선택
4. 분석 키워드는 있으나 유형 불명이면 기본값: 요구사항 분석 (analyze-srs)

#### 스킬 로드

- analyze-srs: `.claude/skills/analyze-srs/SKILL.md`
- analyze-codebase: `.claude/skills/analyze-codebase/SKILL.md`
- analyze-database: `.claude/skills/analyze-database/SKILL.md`
- analyze-data: `.claude/skills/analyze-data/SKILL.md`

### 관련 스킬 (research)

- `.claude/skills/research-general/SKILL.md` - 연구/조사 워크플로우 상세 정의, 리포트 템플릿
- `.claude/skills/research-integrated/SKILL.md` - 웹+코드 통합 조사
- `.claude/skills/analyze-srs/SKILL.md` - 요구사항 분석 절차
- `.claude/skills/analyze-codebase/SKILL.md` - 코드베이스 분석 절차
- `.claude/skills/analyze-database/SKILL.md` - 데이터베이스 분석 절차
- `.claude/skills/analyze-data/SKILL.md` - 데이터 분석 절차

### 동적 컨텍스트 (research)

```
!git log --oneline -10
```

### 프로젝트 플로우 연동 (research)

REPORT 단계 완료 후 티켓 상태를 자동 전이한다.

```bash
flow-kanban move T-NNN review
```

티켓 번호는 `wf.md` Steps 3-1~3-4에서 파싱된 `#N` 인자를 사용한다. 티켓 파일 경로는 `.kanban/open/T-NNN.xml`이다.

- 연구/분석이 완료된 티켓을 Review 상태로 전이한다
- `wf -s research #N` 실행 시 `wf.md`가 이미 티켓 XML 내용을 파싱하여 전달하므로 별도 파싱은 불필요하다

> **Review 후속 흐름**: Review 전이 후 사용자가 `/wf -d N`으로 간단 검토 -> 완료/상세 review 분기를 진행한다. 워크플로우 완료 시점에서 자동 merge는 수행되지 않는다.

---

## Review Command

코드 리뷰를 수행하는 워크플로우 커맨드 스킬.

### 기본 리뷰 절차

1. **대상 파악** - 리뷰 대상 파일/디렉터리/PR을 식별하고 변경 범위를 확인한다
2. **코드 읽기** - 변경 내용을 맥락(의도, 설계, 의존성)과 함께 이해한다
3. **이슈 식별** - 버그, 보안, 성능, 아키텍처 문제를 탐지한다
4. **심각도 분류** - 식별된 이슈를 Critical/Important/Minor 기준으로 분류한다
5. **피드백 작성** - 구체적 개선안과 근거를 포함한 리뷰 코멘트를 생성한다.<br>코드 수정이 필요한 이슈를 발견한 경우 보고서에 수정 방안(파일, 위치, 변경 내용)을 기술하되 직접 수정하지 않는다.

### 코드 수정 금지 제약

> **WARNING**: 리뷰 워크플로우에서 Edit/Write 도구로 소스 코드를 수정하는 행위는 절대 금지된다. T-092 사고에서 리뷰 워커가 common.js, kanban.js, kanban.css를 직접 수정하여 Submit 컬럼을 잘못 추가한 월권이 발생하였다. 이 제약은 동일 사고 재발을 방지하기 위해 명문화된 것이다.

| 구분 | 대상 | 허용 여부 |
|------|------|----------|
| 허용 | 보고서 파일(report.md, work/*.md) 읽기/쓰기 | O |
| 금지 | 소스 코드 파일(.js, .ts, .py, .css, .html 등) 수정 (Edit/Write 도구) | X |

코드 수정이 필요한 경우 보고서에 수정 방안을 기술하고 별도 implement 사이클에서 처리한다.

이 제약은 `readonly_session_guard.py` PreToolUse 가드로 기술적으로 강제됨.

### 심각도 기준

| 심각도 | 기준 |
|--------|------|
| Critical | 즉시 수정 필요 - 보안, 데이터 손실, 기능 장애 |
| Important | 수정 권장 - 아키텍처, 성능, 잠재적 버그 |
| Minor | 개선 제안 - 스타일, 최적화, 문서 |

### 관련 스킬 (review)

| 스킬 | 용도 | 경로 |
|------|------|------|
| review-requesting | 리뷰 체크리스트 및 사전 검증 | `.claude/skills/review-requesting/SKILL.md` |
| review-code-quality | 기본 로드 - 정량적 품질 검사 | `.claude/skills/review-code-quality/SKILL.md` |
| review-security | 키워드 조건부 로드 - 보안 전문 리뷰 | `.claude/skills/review-security/SKILL.md` |
| review-architecture | 키워드 조건부 로드 - 아키텍처 전문 리뷰 | `.claude/skills/review-architecture/SKILL.md` |
| review-frontend | 키워드 조건부 로드 - 프론트엔드 전문 리뷰 | `.claude/skills/review-frontend/SKILL.md` |
| review-performance | 키워드 조건부 로드 - 성능 전문 리뷰 | `.claude/skills/review-performance/SKILL.md` |
| review-comprehensive | 키워드 조건부 로드 - 종합 리뷰 | `.claude/skills/review-comprehensive/SKILL.md` |
| review-feedback-handler | 키워드 조건부 로드 - 피드백 처리 | `.claude/skills/review-feedback-handler/SKILL.md` |
| review-pr-integration | 키워드 조건부 로드 - PR 리뷰 통합 | `.claude/skills/review-pr-integration/SKILL.md` |

### 스킬 우선순위 정책

| 상황 | 로드 스킬 | 비고 |
|------|----------|------|
| 종합 리뷰 키워드 | `review-comprehensive` 단독 | 다른 전문 스킬 비활성 |
| 전문 키워드 | 해당 전문 스킬 단독 | `review-comprehensive` 비활성 |
| 혼합 | `review-comprehensive` 우선 | 전문 스킬 추가 로드 생략 |

### 키워드-스킬 매핑

| 트리거 키워드 | 로드 스킬 |
|--------------|----------|
| 보안, security, 취약점, vulnerability, OWASP | review-security |
| 아키텍처, architecture, 구조, 설계, 레이어 | review-architecture |
| 프론트엔드, frontend, React, UI, 컴포넌트 | review-frontend |
| 성능, performance, 쿼리, DB, N+1 | review-performance |
| 종합, comprehensive, 전체, full review | review-comprehensive |
| 리뷰 반영, review feedback, 피드백 구현, 리뷰 수정, 리뷰 대응 | review-feedback-handler |
| PR 리뷰, pull request review, PR 검증, PR 체크 | review-pr-integration |

### 동적 컨텍스트 (review)

PR 번호가 인수로 전달된 경우:

```bash
gh pr diff <PR번호>
gh pr view <PR번호> --comments
```

파일 또는 디렉터리가 대상인 경우:

```bash
git diff HEAD -- <파일경로>
git log --oneline -5 -- <파일경로>
```

### 프로젝트 플로우 연동 (review)

REPORT 단계 완료 후 티켓 상태를 자동 전이한다.

```bash
flow-kanban move T-NNN review
```

티켓 파일은 `.kanban/open/T-NNN.xml`이다.

---

## Review Completion Flow

워크플로우 완료 후 Review 상태가 된 티켓의 검토 및 완료 처리 절차.

### 개요

implement/research 워크플로우 완료 시 finalization.py가 티켓을 Review 상태로 전이한다. 이후 사용자가 `/wf -d N`을 실행하면 아래 3-way 분기가 동작한다.

### 분기 흐름

| 분기 | 트리거 | 결과 |
|------|--------|------|
| 간단 검토 통과 + 완료 선택 | 검토 항목 전체 OK + 사용자 "1" 선택 | flow-merge 파이프라인 실행 -> Done |
| 간단 검토 경고 + 완료 선택 | 검토 항목 WARN + 사용자 "1" 선택 | flow-merge 파이프라인 실행 -> Done (경고 무시) |
| 상세 review 선택 | 사용자 "2" 선택 | review subnumber 추가 -> /wf -s N으로 review 워크플로우 실행 |
| 취소 | 사용자 "0" 선택 | Review 상태 유지 |

### 간단 검토 항목

| 항목 | 검증 방법 | 판정 기준 |
|------|----------|----------|
| 보고서-변경 파일 일치 | report.md 파일 목록 vs git diff --name-only | 불일치 0건 = OK, 1건 이상 = WARN |
| py_compile | python3 -m py_compile <변경된 .py 파일> | 실패 0건 = OK, 1건 이상 = WARN, .py 파일 없음 = N/A |
| 보고서 존재 | report.md 파일 존재 확인 | 존재 = OK, 미존재 = WARN |

### merge 실행 조건

> **CRITICAL**: merge는 반드시 사용자의 명시적 "완료" 선택 후에만 실행된다. 워크플로우 완료(DONE 전이) 시점에서는 kanban Review 전이만 수행하고, 커밋/merge/worktree 정리는 수행하지 않는다.

### 상세 review 연계

상세 review 선택 시 기존 review command 워크플로우를 재활용한다:
1. `flow-kanban add-subnumber T-NNN --command review`로 새 subnumber 추가
2. 사용자가 `/wf -s N`으로 review 워크플로우 실행
3. review 완료 후 다시 Review 상태로 돌아옴
4. 사용자가 `/wf -d N`으로 최종 완료 처리

### 관련 스크립트

| 스크립트 | 역할 |
|---------|------|
| flow-merge (merge_pipeline.py) | 커밋 -> merge -> worktree 정리 -> kanban done 파이프라인 |
| finalization.py | 워크플로우 완료 시 Review 전이 (자동 merge 금지) |

---

## Submit Command (티켓 제출)

상태별 디렉터리(`.kanban/open/`, `.kanban/progress/`, `.kanban/review/`)의 `T-NNN.xml` 티켓 파일의 `<command>` 태그를 읽어 해당 워크플로우를 자동 실행하는 커맨드 스킬.

상세 실행 절차는 `.claude/commands/wf.md`를 참조한다.

### 자동 라우팅 매핑

| `<command>` 값 | 실행 커맨드 |
|---------------|-----------|
| `implement` | `/wf -s #N` (implement 모드) |
| `research` | `/wf -s #N` (research 모드) |
| `review` | `/wf -s #N` (review 모드) |

### 티켓 파일 처리 규칙

- `#N` 지정 시: `.kanban/open/T-NNN.xml`, `.kanban/progress/T-NNN.xml`, `.kanban/review/T-NNN.xml` 순으로 탐색
- `#N` 미지정 시: `.kanban/open/` 디렉터리의 XML 파일을 스캔하여 Open 상태 티켓을 자동 선택
- `<current>` 값이 `0` 또는 미존재 시: 에러 출력 후 종료
- `<command>` 유효 값: `implement`, `research`, `review`

### 비워크플로우 독립 명령어 (submit)

이 스킬은 워크플로우 FSM과 무관하게 독립 실행된다. 사용 가능 도구: Bash, Glob, Read. Task 도구 호출 금지.

이 스킬의 실행 절차는 대응 커맨드 파일(`.claude/commands/wf.md`)이 Single Source of Truth이다.
