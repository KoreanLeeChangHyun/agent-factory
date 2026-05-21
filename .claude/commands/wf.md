---
description: "WorkRequest 라이프사이클 통합 관리. -o(Accepted/열람), -e(Edit/편집), -oe(Accepted+Edit 단축), -s(Submit), -d(Complete), -c(Cancel) 6개 플래그로 WorkRequest 생성부터 종료까지 단일 진입점으로 제어합니다. Use when: WorkRequest 생성, WorkRequest 편집, 워크플로우 실행, WorkRequest 종료, WorkRequest 삭제를 한 번에 처리할 때"
argument-hint: "[-o|-e|-oe|-s|-d|-c] [N] (WorkRequest 라이프사이클 통합 관리)"
---

# wf (Workflow 통합 명령어)

WorkRequest 라이프사이클 전체를 단일 진입점으로 관리합니다. `-o`(Accepted/채번+용도선택만), `-e`(Edit/편집), `-oe`(Accepted+Edit 단축 별칭), `-s`(Submit), `-d`(Complete), `-c`(Cancel/삭제) 6개 플래그로 생성부터 종료까지 제어합니다.

## WorkRequest Ouroboros 작성 원칙

WorkRequest 작성은 실행 전 계약을 고정하는 단계입니다. `-e`, `-oe`, Board WorkRequest API의 create/refine/accept 흐름은 아래 우로보로스 루프를 기준으로 판단하고, 가능한 경우 WorkRequest XML의 `<ouroboros_history>`에 단계 기록을 남깁니다.

```text
DRAFT -> CLARIFY -> CRITIQUE -> REWRITE -> ACCEPT
```

| 단계 | 적용 기준 |
|------|----------|
| DRAFT | 사용자 요청, 제목, command, 초기 상태를 있는 그대로 채번합니다 |
| CLARIFY | goal/target/constraints/criteria/context 중 누락되거나 안전하게 추론 가능한 항목을 식별합니다 |
| CRITIQUE | 모호한 대상, 검증 불가능한 기준, 범위 확장 위험, 숨은 의존성을 점검합니다 |
| REWRITE | `flow-conveyor update-prompt`로 실행 가능한 prompt 필드를 갱신합니다 |
| ACCEPT | goal/target/constraints/criteria가 실행과 검증에 충분할 때 Accepted 상태로 받아들입니다 |

질문은 누락 필드를 안전하게 추론할 수 없을 때만 합니다. 추론한 제약, 가정, 위험은 `context` 또는 `constraints`에 명시합니다.

## Step 0. 플래그 파싱 및 라우팅

`$ARGUMENTS`에서 플래그와 WorkRequest 번호를 파싱하여 실행 흐름을 결정합니다.

### 파싱 규칙

1. **플래그 추출**: `$ARGUMENTS`에서 `-oe`, `-o`, `-e`, `-s`, `-d`, `-c` 패턴을 순서대로 검색합니다 (`-oe`를 `-o`와 `-e`보다 먼저 검색하여 정확한 매칭 보장)
2. **WorkRequest 번호 추출**: 숫자 `N`(예: `1`, `12`, `123`)을 파싱하여 3자리 zero-padding 적용 (예: `3` -> `WR-003`)
3. **플래그와 번호가 모두 없는 경우**: 아래 도움말 메뉴를 출력하고 종료합니다

### 도움말 메뉴 (플래그 미지정 시 출력)

```
`[WR-NNN]` : `[WF]` wf 통합 명령어 사용법

| 플래그 | 용도 | 예시 |
|--------|------|------|
| `/wf -o` | 새 WorkRequest 생성 (채번+용도선택만, Draft/Accepted 상태 선택) | `/wf -o` |
| `/wf -o N` | 기존 WorkRequest 열람 (Draft는 유지, 그 외는 Accepted 전이) | `/wf -o 3` |
| `/wf -e` | 새 WorkRequest 생성 + 프롬프트 편집 (Draft/Accepted 상태 선택) | `/wf -e` |
| `/wf -e N` | 기존 WorkRequest 편집 (Draft는 Accepted로 자동 승격) | `/wf -e 3` |
| `/wf -oe` | 새 WorkRequest 생성 + 편집 (`-o -e` 단축) | `/wf -oe` |
| `/wf -oe N` | 기존 WorkRequest Accepted + 편집 (`-o -e` 단축) | `/wf -oe 3` |
| `/wf -s N` | WorkRequest 제출 및 워크플로우 실행 (Draft 상태면 에러) | `/wf -s 3` |
| `/wf -d N` | WorkRequest 종료 (Complete 상태로 이동) | `/wf -d 3` |
| `/wf -c N` | WorkRequest 삭제 | `/wf -c 3` |

현재 Conveyor 상태를 확인하려면 `.agent-factory/work-requests/` 디렉터리(draft/accepted/executing/verifying/complete)의 XML WorkRequest 파일을 참조하세요.
```

### 라우팅 규칙

| 조건 | 실행 흐름 |
|------|----------|
| `-o` 플래그 | [## -o](#-o) (Accepted/생성 또는 열람, 채번+용도선택까지만) |
| `-e` 플래그 | [## -e](#-e) (Edit/편집, 편집 루프 진입) |
| `-oe` 플래그 | [## -e](#-e) (하위호환, `-e`와 동일 동작) |
| `-s` 플래그 | [## -s](#-s) (Submit/제출) |
| `-d` 플래그 | [## -d](#-d) (Complete/종료) |
| `-c` 플래그 | [## -c](#-c) (Cancel/삭제) |
| 플래그 없음 | 도움말 메뉴 출력 후 종료 |

---

## -o

### WorkRequest 생성 또는 열람

`$ARGUMENTS`에서 WorkRequest 번호 `N`의 유무를 확인하여 서브플로우를 분기합니다:

| 번호 유무 | 실행 흐름 |
|---------|----------|
| 없음 | Step 1-A-o: 새 WorkRequest 생성 (채번+용도선택만, 편집 루프 미진입) |
| 있음 | Step 1-B-o: 기존 WorkRequest를 Accepted로 전이 (즉시 실행, 편집 루프 미진입) |

### Step 1-A-o. 번호 없음: 새 WorkRequest 생성 (채번+용도선택만)

> **Conveyor 전이**: (없음) -> **Draft** 또는 **Accepted** (사용자 선택)

#### 1-0. 초기 상태 선택 (Draft vs Accepted)

사용자 발화에서 상태 신호를 감지하여 기본값을 추천하되, 반드시 번호 메뉴로 확인합니다:

| 발화 패턴 | 추천 상태 |
|----------|---------|
| "WorkRequest 생성", "나중에", "언젠가", "백로그" | Draft |
| "지금", "바로", "이번에", "집중" | Accepted |
| 무맥락 | (추천 없음) |

번호 메뉴 출력:
```
`[WR-NNN]` : `[WF -o]` 이 WorkRequest를 어디에 둘까요?

`1.` Draft -- 미래에 할 백로그·WorkRequest 생성 공간
`2.` Accepted -- 지금 집중해야 하는 임박 작업
```

사용자 선택에 따라 `--status draft` 또는 `--status accepted`을 결정합니다. 사용자가 발화에서 이미 상태를 명시("Accepted로 만들어줘" 등)한 경우에만 질의를 생략합니다.

> **예외**: AskUserQuestion 도구는 Board 터미널에서 미지원되므로 반드시 텍스트 번호 메뉴로 질의합니다.

#### 1-1. 빈 WorkRequest 즉시 채번

선택된 상태에 따라 아래 중 하나를 실행합니다:

```bash
flow-conveyor create "" --command init --status draft
# 또는
flow-conveyor create "" --command init --status accepted
```

stdout에서 WR-NNN을 파싱하고 채번 결과를 출력합니다:
```
`[WR-NNN]` : `[WF -o]` WorkRequest WR-NNN을 생성했습니다. (상태: <선택된 상태>)
```

#### 1-2. 대화 맥락 감지 및 용도 결정

이전 대화에서 작업 요청이 감지된 경우 트랙 A, 그렇지 않은 경우 트랙 B를 실행합니다.

**트랙 A: 맥락 감지됨** -- 이전 대화에서 작업 요청이 감지된 경우:

> **맥락 충분성 판단**: goal/target/constraints/criteria 4개 항목 모두 추론 가능(각 10자 이상)한 경우 "맥락 충분"으로 간주합니다. constraints 또는 criteria 중 하나라도 추론 불가이면 "맥락 부분"으로 간주합니다.

```
`[WR-NNN]` : `[WF -o]` 이전 대화를 기반으로 다음과 같이 추론했습니다:

- 용도: <추론된 용도>
- goal: <추론된 목표>
- target: <추론된 대상>
- constraints: <추론된 제약 조건> (추론 불가 시 "미상")
- criteria: <추론된 완료 기준> (추론 불가 시 "미상")
- context: <이전 대화 핵심 요약>

`1.` 확인 -- 이 용도로 WorkRequest를 생성합니다
`2.` 용도 직접 지정 -- 목적 선택 메뉴로 전환합니다
`0.` 취소 -- 생성하지 않고 종료합니다
```

- `1.` 확인: 맥락 충분성에 따라 분기합니다:
  - **맥락 충분** (constraints/criteria 모두 추론 성공): `flow-conveyor update-prompt WR-NNN --command <command값> --goal "<추론된 goal>" --target "<추론된 target>" --constraints "<추론된 constraints>" --criteria "<추론된 criteria>" --context "<추론된 context>" --skip-validation` 호출 후 1-3으로 진행
  - **맥락 부분** (constraints 또는 criteria 추론 불가): `flow-conveyor update-prompt WR-NNN --command <command값> --goal "<추론된 goal>" --target "<추론된 target>" --skip-validation` 호출 후 1-3으로 진행
  - (`-o` 모드는 편집 루프 미진입이므로 품질 검증을 건너뜁니다)
- `2.` 용도 직접 지정: 트랙 B로 전환
- `0.` 취소: WorkRequest 생성 없이 종료

**트랙 B: 맥락 미감지 또는 fallback** -- Read 도구로 `.agent-factory/board/config/prompt-files/prompt.txt`를 읽어 메뉴 항목을 로드한 뒤 출력합니다:

```
`[WR-NNN]` : `[WF -o]` 어떤 목적의 WorkRequest를 생성할까요?

1. <항목 1>
2. <항목 2>
...
0. 완료 -- 생성하지 않고 종료합니다

번호 또는 자유 텍스트를 입력하세요:
```

**용도->command 매핑**: 연구=`research`, 구현/버그수정/리팩토링/아키텍처설계=`implement`, 리뷰=`review`

사용자가 번호를 선택하면 해당 command 값으로 `flow-conveyor update-prompt WR-NNN --command <command값> --goal "(미정)" --target "(미정)" --skip-validation`을 호출합니다 (`--goal`/`--target`은 CLI 필수 인자이므로 placeholder를 전달하고, `-o` 모드는 편집 루프 미진입이므로 `--skip-validation`으로 품질 검증을 건너뜁니다). "0. 완료" 선택 시 종료합니다.

#### 1-3. 완료 메시지 출력

```
WR-NNN WorkRequest이 생성되었습니다. (파일: .agent-factory/work-requests/<선택된 상태>/WR-NNN.xml)
```

> 선택된 상태가 `draft`이면 `.agent-factory/work-requests/draft/WR-NNN.xml`, `accepted`이면 `.agent-factory/work-requests/accepted/WR-NNN.xml`에 저장됩니다.

**맥락 충분 시** (트랙 A에서 constraints/criteria 모두 추론 성공):

## 후속 커맨드 안내

| 목적 | 커맨드 | 설명 |
|------|--------|------|
| 편집 | `/wf -e N` | 프롬프트 내용을 추가로 수정합니다 |
| 제출 | `/wf -s N` | <command> 태그에 따라 자동 라우팅 <- 권장 |
| 종료 | `/wf -d N` | WorkRequest를 Complete 상태로 종료합니다 |

**맥락 부분 시** (constraints 또는 criteria 추론 불가):

## 후속 커맨드 안내

| 목적 | 커맨드 | 설명 |
|------|--------|------|
| 편집 | `/wf -e N` | 프롬프트 작성 및 내용 편집 <- 권장 |
| 제출 | `/wf -s N` | <command> 태그에 따라 자동 라우팅 |
| 종료 | `/wf -d N` | WorkRequest를 Complete 상태로 종료합니다 |

### Step 1-B-o. 번호 있음: 기존 WorkRequest 내용 표시 (편집 루프 미진입)

편집 루프에 진입하지 않습니다. Draft 상태 WorkRequest은 상태를 유지한 채 내용만 표시합니다.

#### 1-B-o-1. WorkRequest 파일 로드

Glob 도구로 `.agent-factory/work-requests/draft/WR-NNN.xml`, `.agent-factory/work-requests/accepted/WR-NNN.xml`, `.agent-factory/work-requests/executing/WR-NNN.xml`, `.agent-factory/work-requests/verifying/WR-NNN.xml` 패턴을 순서대로 검색합니다. Read 도구로 XML의 `<metadata>/<status>`를 확인하여 분기합니다:

| 상태 | 분기 흐름 |
|------|----------|
| `Draft` | 상태 유지. WorkRequest 내용 표시 후 1-B-o-2로 진행 (Accepted로 전이하지 않음) |
| `Accepted` | 안내 메시지(`WR-NNN은 이미 Accepted 상태입니다.`) 출력 후 1-B-o-2로 진행 |
| `Executing` / `Verifying` | `flow-conveyor move WR-NNN accepted --force` 즉시 실행 후 상태 변경 확인 메시지 출력, 1-B-o-2로 진행 |
| `Complete` (.agent-factory/work-requests/complete/ 발견) | `flow-conveyor move WR-NNN accepted --force` 실행, 1-B-o-2로 진행 |
| 파일 미발견 | 에러 출력 후 종료: `WR-NNN WorkRequest 파일을 찾을 수 없습니다.` |

#### 1-B-o-2. 후속 안내 출력

**Draft 상태 유지 시:**
```
`[WR-NNN]` : `[WF -o]` WR-NNN WorkRequest 내용을 표시했습니다. (현재 상태: Draft)

## 후속 커맨드 안내

| 목적 | 커맨드 | 설명 |
|------|--------|------|
| 편집 | `/wf -e N` | Accepted로 승격 후 프롬프트 편집 |
| 종료 | `/wf -d N` | WorkRequest를 Complete 상태로 종료합니다 |
```

**Accepted 상태로 전이한 경우:**
```
`[WR-NNN]` : `[WF -o]` WR-NNN WorkRequest를 Accepted 상태로 전이했습니다.

## 후속 커맨드 안내

| 목적 | 커맨드 | 설명 |
|------|--------|------|
| 편집 | `/wf -e N` | 프롬프트 작성 및 내용 편집 |
| 제출 | `/wf -s N` | <command> 태그에 따라 자동 라우팅 |
| 종료 | `/wf -d N` | WorkRequest를 Complete 상태로 종료합니다 |
```

---

## -e

### WorkRequest 생성 + 편집 또는 기존 WorkRequest 편집

`-oe`는 `-e`의 단축 별칭으로 동일 로직을 실행합니다.

| 번호 유무 | 실행 흐름 |
|---------|----------|
| 없음 | Step 1-A-e: 새 WorkRequest 생성 + 프롬프트 편집 루프 |
| 있음 | Step 1-B-e: 기존 WorkRequest 편집 루프 |

### Step 1-A-e. 번호 없음: 새 WorkRequest 생성 + 프롬프트 편집 루프

> **Conveyor 전이**: (없음) -> **Draft** 또는 **Accepted** (사용자 선택)

#### 1-0. 초기 상태 선택 (Draft vs Accepted)

사용자 발화에서 상태 신호를 감지하여 기본값을 추천하되, 반드시 번호 메뉴로 확인합니다:

| 발화 패턴 | 추천 상태 |
|----------|---------|
| "WorkRequest 생성", "나중에", "언젠가", "백로그" | Draft |
| "지금", "바로", "이번에", "집중" | Accepted |
| 무맥락 | (추천 없음) |

번호 메뉴 출력:
```
`[WR-NNN]` : `[WF -e]` 이 WorkRequest를 어디에 둘까요?

`1.` Draft -- 미래에 할 백로그·WorkRequest 생성 공간
`2.` Accepted -- 지금 집중해야 하는 임박 작업
```

사용자 선택에 따라 `--status draft` 또는 `--status accepted`을 결정합니다. 사용자가 발화에서 이미 상태를 명시("Accepted로 만들어줘" 등)한 경우에만 질의를 생략합니다.

#### 1-1. 빈 WorkRequest 즉시 채번

선택된 상태에 따라 아래 중 하나를 실행합니다:

```bash
flow-conveyor create "" --command init --status draft
# 또는
flow-conveyor create "" --command init --status accepted
```

stdout에서 WR-NNN을 파싱하고 채번 결과를 출력합니다:
```
`[WR-NNN]` : `[WF -e]` WorkRequest WR-NNN을 생성했습니다. (상태: <선택된 상태>)
```

#### 1-2. 스킬 로드

Read 도구로 `.claude/skills/research-prompt-engineering/SKILL.md`를 읽어 프롬프트 작성 지침을 로드합니다.

#### 1-3. 대화 맥락 감지 및 용도 결정

**트랙 A: 맥락 감지됨** -- 이전 대화에서 작업 요청이 감지된 경우:

> **맥락 충분성 판단**: goal/target/constraints/criteria 4개 항목 모두 추론 가능(각 10자 이상)한 경우 "맥락 충분"으로 간주합니다. constraints 또는 criteria 중 하나라도 추론 불가이면 "맥락 부분"으로 간주합니다.

```
`[WR-NNN]` : `[WF -e]` 이전 대화를 기반으로 다음과 같이 추론했습니다:

- 용도: <추론된 용도>
- goal: <추론된 목표>
- target: <추론된 대상>
- constraints: <추론된 제약 조건> (추론 불가 시 "미상")
- criteria: <추론된 완료 기준> (추론 불가 시 "미상")
- context: <이전 대화 핵심 요약>

`1.` 확인 -- 이 내용으로 진행합니다
`2.` 용도 직접 지정 -- 목적 선택 메뉴로 전환합니다
`0.` 취소 -- 생성하지 않고 종료합니다
```

- `1.` 확인: 추론된 용도/goal/target/context를 Step 1-4의 초기값으로 전달
- `2.` 용도 직접 지정: 트랙 B로 전환
- `0.` 취소: WorkRequest 생성 없이 종료

**트랙 B: 맥락 미감지 또는 fallback** -- Read 도구로 `.agent-factory/board/config/prompt-files/prompt.txt`를 읽어 메뉴 항목을 로드합니다.

**용도->command 매핑**: 연구=`research`, 구현/버그수정/리팩토링/아키텍처설계=`implement`, 리뷰=`review`

"0. 완료" 선택 시 종료합니다.

#### 1-4. 대화형 프롬프트 작성 루프

선택한 용도에 해당하는 프롬프트 템플릿을 Read 도구로 로드합니다:

**용도->템플릿 섹션 매핑**:

| 용도 | 로드할 파일 | 해당 섹션 |
|------|-----------|---------|
| 구현, 아키텍처설계 | `.claude/skills/research-prompt-engineering/references/prompt-templates.md` | `## 1. 기능 구현` 또는 `## 6. 아키텍처 설계` |
| 버그수정 | 동일 파일 | `## 2. 버그 수정` |
| 리팩토링 | 동일 파일 | `## 3. 리팩토링` |
| 리뷰 | 동일 파일 | `## 4. 코드 리뷰` |
| 연구 | 동일 파일 | `## 5. 연구 조사` |

로드한 템플릿의 XML 태그 버전(`<goal>`, `<target>`, `<constraints>`, `<criteria>`, `<context>`)을 구조화된 질문 형태로 사용자에게 제시합니다. 루프의 목적은 "정보 수집"이 아닌 **"프롬프트 개선"**입니다.

매 턴 아래 순서로 처리합니다:

**1단계 - 사용자 입력 수신 및 안내:** 현재 프롬프트 상태를 반영한 안내와 개선 제안을 출력합니다 (접두사: `` `[WR-NNN]` : `[WF -e]` ``). 사용자 입력을 기반으로 goal, target, constraints, criteria, context 정보를 개선합니다.

**2단계 - 내부 모호성 분석 (사용자에게 노출하지 않음):** 로드한 `research-prompt-engineering` 스킬의 모호성 분석 체크리스트 5항목과 자가 점검 체크리스트 7항목을 내부적으로 재평가합니다.

**3단계 - 웹검색/코드탐색 자율 수행:**

| 감지 신호 | 수행 액션 | 사용 도구 |
|----------|----------|----------|
| 함수, 모듈, 파일, 클래스, 컴포넌트, 변수, 메서드 | 코드베이스 탐색 | Grep, Glob, Read |
| API, 프레임워크, 패키지, 버전, 라이브러리, SDK, 외부 서비스 | 웹검색 | WebSearch, WebFetch |
| 양쪽 신호 모두 감지 | 코드베이스 탐색 + 웹검색 모두 수행 | Grep, Glob, Read, WebSearch, WebFetch |

**4단계 - G1~G4 게이트 평가 및 동적 선택지 출력:** G1~G4 게이트 조건 충족 시 완료를 제안합니다. 매 턴 종료 시 아래 구조로 동적 선택지를 반드시 출력합니다:

1. **헤더**: 접두사(`` `[WR-NNN]` : `[WF -e]` ``) + 제목
2. **간단 요약**: 현재 프롬프트 진행 상태를 1-2문장으로 요약
3. **동적 선택지**: 대화 맥락을 분석하여 `1.`~`5.` (최대 5개) + `0.` 완료를 생성
4. **안내 문구**: "자유 텍스트 입력도 가능합니다." 문구를 선택지 아래에 출력

- 사용자 "0. 완료" 선택 시 아래 순서로 처리:
  0. **constraints/criteria 필수 검증**: constraints 또는 criteria가 누락이거나 10자 미만이면 아래 메시지를 출력하고 루프를 계속합니다 (이하 단계를 실행하지 않음):
     ```
     `[WR-NNN]` : `[WF -e]` constraints 또는 criteria가 누락되었거나 내용이 부족합니다(10자 이상 필요). 보강 후 다시 완료를 선택하세요.
     ```
  1. 대화 내용을 기반으로 WorkRequest 제목을 자동 생성합니다 (20자 이내, 한국어, 동사형)
  2. `flow-conveyor update-prompt WR-NNN --command <command값> --goal "<goal>" --target "<target>" --constraints "<constraints>" --criteria "<criteria>" --context "<context>"` (context 없으면 생략)
  3. Read 도구로 갱신된 XML 파일을 읽어 prompt 내용 확인 후 Step 1-5로 진행

#### 1-5. 완료 메시지 출력

```
WR-NNN WorkRequest이 생성되었습니다. (파일: .agent-factory/work-requests/<선택된 상태>/WR-NNN.xml)

## 후속 커맨드 안내

| 목적 | 커맨드 | 설명 |
|------|--------|------|
| 제출 | `/wf -s N` | <command> 태그에 따라 자동 라우팅 <- 권장 |
| 편집 | `/wf -e N` | WorkRequest 내용을 추가로 수정합니다 |
| 종료 | `/wf -d N` | WorkRequest를 Complete 상태로 종료합니다 |

> 참고: 선택된 상태가 `draft`이면 `/wf -s N` 실행 전에 `/wf -e N`으로 Accepted 승격이 필요합니다. v2 driver 는 단일 command 만 지원합니다 (체인 `research>implement>review` 는 Phase 4 후속 트랙, SPEC.md §14 참조).
```

### Step 1-B-e. 번호 있음: 기존 WorkRequest 편집 루프

> **Conveyor 전이**: Draft -> **Accepted** (승격) / Complete -> **Accepted** (복원) / Verifying/Executing -> **Accepted** (자동 복귀) / Accepted -> Accepted (유지)

#### 1-B-1. WorkRequest 파일 로드

Glob 도구로 `.agent-factory/work-requests/draft/WR-NNN.xml`, `.agent-factory/work-requests/accepted/WR-NNN.xml`, `.agent-factory/work-requests/executing/WR-NNN.xml`, `.agent-factory/work-requests/verifying/WR-NNN.xml` 패턴을 순서대로 검색합니다.

**파일 발견 시**: XML `<status>` 요소에서 현재 Conveyor 상태를 판별합니다.

**파일 미발견 시**: `.agent-factory/work-requests/complete/WR-NNN.xml`을 확인합니다:
- 존재하면: `flow-conveyor move WR-NNN accepted` 실행 (파일 이동 처리는 conveyor_cli.py가 담당)
- 어디에서도 찾지 못한 경우: 에러 출력 후 종료 (`WR-NNN WorkRequest 파일을 찾을 수 없습니다.`)

#### 1-B-2. Draft / Verifying / Executing 상태 자동 Accepted 복귀

현재 상태가 `Draft`, `Executing`, 또는 `Verifying`인 경우, 사용자 확인 없이 즉시 Accepted로 전이합니다:
```bash
flow-conveyor move WR-NNN accepted
```

- `Draft` -> `Accepted`: 승격 (편집 의도이므로 즉시 집중 대상으로 전환)
- `Executing` / `Verifying` -> `Accepted`: 자동 복귀
- `Accepted`: 상태 변경 없이 즉시 편집 루프로 진입

#### 1-B-3. 현재 WorkRequest 내용 표시

```
## 현재 WR-NNN.xml 내용

<WorkRequest 파일 내용 전체>
```

#### 1-B-4. 스킬 로드

Read 도구로 `.claude/skills/research-prompt-engineering/SKILL.md`를 읽어 프롬프트 작성 지침을 로드합니다.

#### 1-B-5. 대화형 편집 루프

WorkRequest XML에서 `<result>` 요소의 상태를 확인하여 분기를 결정합니다. 대화 루프의 매 턴은 Step 1-4와 동일한 처리 순서(1단계~4단계)를 따릅니다.

**분기 A -- `<result />` self-closing 또는 `<result>` 미존재 (미실행): 기존 프롬프트 수정**
- 현재 `<prompt>` 내용을 표시하여 작업 맥락을 제공합니다
- "0. 완료" 선택 시 constraints/criteria 필수 검증 후 `flow-conveyor update-prompt WR-NNN --command <command값> --goal "<goal>" --target "<target>" --constraints "<constraints>" --criteria "<criteria>" --context "<context>"`

**분기 B -- `<result>` 내용 있음 (실행 완료): 새 WorkRequest 생성 + link**
- 이미 실행이 완료된 WorkRequest이므로, 추가 작업이 필요한 경우 새 WorkRequest를 생성하도록 안내합니다
- "0. 완료" 선택 시 constraints/criteria 필수 검증 후:
  1. `flow-conveyor create "<새 제목>" --command <command값> --status accepted` 로 새 WorkRequest WR-MMM 생성 (파생 WorkRequest은 즉시 집중 대상이므로 기본 Accepted)
  2. `flow-conveyor update-prompt WR-MMM --goal "<goal>" --target "<target>" --constraints "<constraints>" --criteria "<criteria>" --context "<context>"`
  3. `flow-conveyor link WR-MMM --derived-from WR-NNN` 로 관계 링크 설정
  4. 안내: `WR-MMM WorkRequest이 WR-NNN에서 파생되어 생성되었습니다. /wf -s MMM 으로 제출하세요.`

> **constraints/criteria 필수 검증**: 모든 사이클에서 "0. 완료" 선택 시 constraints 또는 criteria가 누락이거나 10자 미만이면 메시지를 출력하고 루프를 계속합니다.

> **`<command>` 태그 갱신 정책**: `-e NNN` 편집 시 `<command>` 갱신이 허용됩니다. `update-prompt`의 `--command` 인자로 직접 변경할 수 있습니다.

> `context` 값이 없는 경우 해당 인자를 생략합니다.

#### 1-B-6. 완료 메시지 출력

```
WR-NNN WorkRequest이 업데이트되었습니다.

## 후속 커맨드 안내

| 목적 | 커맨드 | 설명 |
|------|--------|------|
| 제출 | `/wf -s N` | <command> 태그에 따라 자동 라우팅 <- 권장 |
| 종료 | `/wf -d N` | WorkRequest를 Complete 상태로 종료합니다 |
```

---

## -s

### WorkRequest 제출 및 워크플로우 실행 (v2 driver)

> **Conveyor 전이**: Accepted -> **Executing** (v2 driver 초기화 중 `flow-conveyor move WR-NNN executing` 자동 수행) -> **Verifying** (driver 완료 단계에서 자동 전이).
>
> **v2 라우팅 (T-489 Stage 3-A)**: 본 분기는 `.agent-factory/bin/flow-wf submit WR-NNN` 단일 진입점으로 단순화되었습니다. v1 의 `flow-launcher launch` / `LAUNCH/INLINE` 분기 / `.claude/skills/workflow-wf/SKILL.md` 메인 세션 직접 로드 흐름은 폐지되었습니다.
>
> driver 가 6 Step (INIT / PLAN / WORK / VERIFY / REPORT / COMPLETE) 을 룰베이스로 순차 진행하며, PLAN/WORK/VERIFY/REPORT 4 Step 은 `claude -p` subprocess 로 격리 실행됩니다 (메인 세션 컨텍스트 0 영향). 명세 SSOT = `.agent-factory/engine/v2/SPEC.md`.

#### 2-1. WorkRequest 번호 검증

`$ARGUMENTS`에서 숫자 `N`을 파싱합니다. 없으면 에러 출력 후 종료:
```
-s 플래그는 WorkRequest 번호(N)를 반드시 지정해야 합니다. 예: /wf -s 3
```

#### 2-2. WorkRequest 파일 로드 및 상태 검증

Glob 도구로 `.agent-factory/work-requests/draft/WR-NNN.xml`, `.agent-factory/work-requests/accepted/WR-NNN.xml`, `.agent-factory/work-requests/executing/WR-NNN.xml`, `.agent-factory/work-requests/verifying/WR-NNN.xml` 패턴을 순서대로 검색합니다. 미발견 시 에러 출력 후 종료.

Read 도구로 XML의 `<status>` 요소를 확인합니다. 값이 `Draft`이면 아래 메시지를 출력하고 종료합니다:
```
`[WR-NNN]` : `[WF -s]` WR-NNN은 Draft 상태입니다. 먼저 `/wf -e N`으로 Accepted 승격 후 다시 제출하세요.
```

#### 2-3. `<command>` 태그 검증

XML에서 `<prompt>` 요소 존재 여부를 확인합니다:
- `<prompt>` 미존재 또는 `<goal>` 내용 없음: 에러 출력 후 종료 (`워크플로우가 정의되지 않았습니다. /wf -e N으로 먼저 작성하세요.`)
- `<prompt>` 존재: `<metadata>` 직하 `<command>` 요소를 읽습니다

**단일 command 검증**: `<command>` 값이 `implement`, `research`, `review` 중 하나여야 합니다. 그 외 값이면 에러 출력 후 종료.

**체인 command 차단**: `<command>` 값에 `>` 구분자가 포함된 경우 (예: `research>implement>review`) v2 driver 는 아직 체인을 지원하지 않으므로 아래 메시지를 출력하고 종료합니다:
```
`[WR-NNN]` : `[WF -s]` v2 driver 는 단일 command 만 지원합니다 (체인 `research>implement>review` 미지원). `/wf -e N` 으로 `<command>` 값을 단일 command 로 갱신 후 다시 제출하세요.
```

> 체인 command 지원은 v2 Phase 4 후속 트랙입니다 (SPEC.md §14 잔여 트랙 참조).

#### 2-4. v2 driver 발사 (background)

`.agent-factory/bin/flow-wf submit WR-NNN` 을 Bash 도구의 `run_in_background: true` 옵션으로 호출합니다. stdout 은 NDJSON event stream (step.start / step.end / phase.start / phase.end / workflow.finish) 이며, stderr 는 driver 진단 로그입니다.

```bash
.agent-factory/bin/flow-wf submit WR-NNN
```

driver 의 일반 사이클은 4 spawn × claude -p 약 5분 (T-490 검증 기준 5분 14초). 메인 세션은 background 실행 동안 사용자와 자유 대화 가능합니다.

#### 2-5. 진행 안내 출력

```
`[WR-NNN]` : `[WF -s]` WR-NNN WorkRequest를 <command> 워크플로우로 실행합니다 (v2 driver background).

## 진행 추적

| 산출물 | 경로 |
|--------|------|
| 산출물 디렉터리 | `.agent-factory/runs/<registryKey>/` (driver 가 INIT 단계에서 생성) |
| 실시간 로그 | `.agent-factory/runs/<registryKey>/workflow.log` |
| 이벤트 stream | driver stdout (NDJSON, BashOutput 으로 확인) |
| 상태 조회 | `.agent-factory/bin/flow-conveyor show WR-NNN` |

driver 가 6 Step (INIT / PLAN / WORK / VERIFY / REPORT / COMPLETE) 을 통째 진행한 후 자동으로 `flow-conveyor move WR-NNN verifying` 를 수행합니다. 12 advisory 룰 평가 결과는 `.agent-factory/runs/<registryKey>/validate-rules.json` 에 기록됩니다.
```

> **v1 호환 미보존**: 본 patch 는 v1 인프라 (`flow-launcher`, `_handle_conveyor_submit`, `.claude/skills/workflow-wf/SKILL.md` 메인 세션 로드, 체인 command) 호환을 보존하지 않습니다. Board UI DnD (Accepted → Executing) 도 결국 새 세션에서 `/wf -s N` 슬래시 발화로 귀결되므로 본 patch 만으로 자동 흡수됩니다. Board UI 의 실시간 진행 표시 (workflow-bar SSE) 통합은 v2 Stage 3-B 후속 트랙입니다.

---

## -d

### WorkRequest 종료

> **Conveyor 전이**: Verifying -> **Complete** (간단검토 후 완료 선택 시) / Verifying -> **Verifying** (상세 검토 선택 시) / Accepted,Executing -> **Complete** (즉시 처리)
>
> **Verifying 단계 의미**: 워크플로우 완료 후 보고서 검토 + Verifying 카드 4행 토글로 feature 브랜치를 활성화하여 사용자가 직접 테스트 + 사용자 리뷰. (카드 토글 ON: feature 브랜치로 git switch, OFF: develop으로 복귀)
>
> **Complete 의미**: 머지 + 사용자 직접 테스트 통과 후의 진짜 종결. 코드 변경 + 사용자 검증 양쪽이 끝난 상태만 Complete로 처리한다.

#### 3-1. WorkRequest 번호 검증

`$ARGUMENTS`에서 숫자 `N`을 파싱합니다. 없으면 에러 출력 후 종료:
```
-d 플래그는 WorkRequest 번호(N)를 반드시 지정해야 합니다. 예: /wf -d 3
```

#### 3-2. WorkRequest 상태 확인 및 분기

Glob 도구로 `.agent-factory/work-requests/draft/WR-NNN.xml`, `.agent-factory/work-requests/accepted/WR-NNN.xml`, `.agent-factory/work-requests/executing/WR-NNN.xml`, `.agent-factory/work-requests/verifying/WR-NNN.xml` 패턴을 순서대로 탐색하고 Read 도구로 `<status>` 요소를 확인하여 분기합니다:

| 현재 상태 | 실행 흐름 |
|----------|----------|
| `Verifying` | 3-A. Verifying 간단 검토 흐름 |
| 그 외 (Draft, Accepted, Executing 등) | 3-B. 즉시 Complete 처리 (기존 로직) |

#### 3-A. Verifying 간단 검토 흐름

##### 3-A-1. 최근 워크플로우 산출물 탐색

`.agent-factory/runs/` 하위에서 해당 WorkRequest의 가장 최근 워크플로우 디렉터리를 탐색합니다:
- Glob 도구로 `.agent-factory/runs/*/report.md` (새 구조 우선) 또는 `.agent-factory/runs/*/WR-NNN*/*/report.md` / `.agent-factory/runs/*/*/implement/report.md` (기존 `.history/` 호환) 등을 검색합니다
- WorkRequest XML의 `<result>` 요소의 `<workdir>` 값을 확인하여 정확한 워크플로우 디렉터리를 특정합니다
- `<workdir>` 값이 없으면 `.agent-factory/runs/` 하위에서 최신 타임스탬프 디렉터리를 탐색합니다

##### 3-A-2. 간단 검토 수행

아래 3가지 검증을 수행하여 결과를 구조화된 테이블로 출력합니다:

**(a) 보고서 vs 실제 변경 파일 대조:**
- `report.md`에서 "수정 대상 파일" 또는 "변경 파일" 관련 섹션을 추출합니다
- worktree가 활성화된 경우: 해당 worktree의 feature 브랜치에서 `git diff develop...HEAD --name-only`로 실제 변경 파일 목록을 취득합니다
- worktree가 비활성인 경우: `git diff` 또는 `git log`로 최근 변경 파일을 확인합니다
- 보고서에 기록된 파일과 실제 변경 파일의 일치/불일치를 비교합니다

**(b) py_compile 검증 (Python 파일 대상):**
- 변경된 `.py` 파일에 대해 `python3 -m py_compile <file>` 실행
- 통과/실패 여부를 기록합니다

**(c) 검증 결과 요약 출력:**
```
`[WR-NNN]` : `[WF -d]` Verifying 간단 검토 결과

| 항목 | 결과 | 상세 |
|------|------|------|
| 보고서-변경 파일 일치 | OK / WARN | 일치 N개, 불일치 N개 |
| py_compile | OK / WARN / N/A | 통과 N개, 실패 N개 |
| 보고서 존재 | OK / WARN | report.md 경로 |
```

##### 3-A-3. 검토 결과 기반 선택지 제시

| 조건 | 제시 선택지 |
|------|-----------|
| 전항목 OK | 1. 완료 -- 커밋, merge, worktree 정리, Complete 전이를 실행합니다 / 2. 상세 검토 -- review 워크플로우를 제출합니다 / 0. 취소 |
| WARN 1개 이상 | 1. 완료 (경고 무시) -- 커밋, merge, worktree 정리, Complete 전이를 실행합니다 / 2. 상세 검토 -- review 워크플로우를 제출합니다 (권장) / 0. 취소 |

##### 3-A-4. 선택지 처리

**"1. 완료" 선택 시:**
```bash
flow-merge WR-NNN --force
```
`flow-merge`의 5단계 파이프라인(자동 커밋 -> merge -> worktree 정리 -> Conveyor complete -> 브랜치 삭제)을 실행합니다. 실패 시 에러 메시지 출력 후 종료합니다.

성공 시 종료 메시지:
```
`[WR-NNN]` : `[WF -d]` WR-NNN WorkRequest이 Complete 상태로 종료되었습니다. (파일: .agent-factory/work-requests/complete/WR-NNN.xml)
```

**"2. 상세 검토" 선택 시:**
- 기존 WorkRequest의 `<command>` 값을 확인합니다
- 새 review WorkRequest를 생성하고 원본 WorkRequest와 link합니다:
  1. `flow-conveyor create "WR-NNN 상세 리뷰" --command review --status accepted` 로 새 WorkRequest WR-MMM 생성 (상세 리뷰는 즉시 집중 대상)
  2. `flow-conveyor update-prompt WR-MMM --goal "WR-NNN 구현 결과 상세 리뷰" --target "<보고서 경로>" --constraints "간단 검토에서 발견된 경고 항목을 중점 검토" --criteria "모든 WARN 항목이 해소되거나 수용 근거가 명시됨" --context "간단 검토에서 경고 발견" --skip-validation`
  3. `flow-conveyor link WR-MMM --derived-from WR-NNN`
- 안내 메시지를 출력합니다:
```
`[WR-NNN]` : `[WF -d]` 상세 검토 WorkRequest WR-MMM을 생성했습니다. (WR-NNN에서 파생)

| 목적 | 커맨드 | 설명 |
|------|--------|------|
| 제출 | `/wf -s MMM` | review 워크플로우 실행 <- 권장 |
| 편집 | `/wf -e MMM` | review 프롬프트를 먼저 편집합니다 |
```

**"0. 취소" 선택 시:**
안내 메시지 출력 후 종료:
```
`[WR-NNN]` : `[WF -d]` 취소되었습니다. WorkRequest은 Verifying 상태를 유지합니다.
```

#### 3-B. 즉시 Complete 처리

Verifying 이외 상태(Accepted, Executing 등)의 WorkRequest은 기존과 동일하게 즉시 Complete 처리합니다.

```bash
flow-conveyor complete WR-NNN
```

- exit code 1, "찾을 수 없습니다": 에러 출력 후 종료
- exit code 1, "이미 Complete": 안내 출력 후 종료
- exit code 0: 종료 메시지 출력

> `flow-conveyor complete`은 상태 갱신과 파일 이동(상태별 디렉터리(`draft/`, `accepted/`, `executing/`, `verifying/`) -> `.agent-factory/work-requests/complete/WR-NNN.xml`)을 내부적으로 처리합니다.

종료 메시지:
```
WR-NNN WorkRequest이 Complete 상태로 종료되었습니다. (파일: .agent-factory/work-requests/complete/WR-NNN.xml)
```

---

## -c

### WorkRequest 삭제

> **Conveyor 전이**: Any -> **(삭제)**

`-d`(Complete)와 달리 히스토리를 보존하지 않습니다.

#### 4-1. WorkRequest 번호 검증

`$ARGUMENTS`에서 숫자 `N`을 파싱합니다. 없으면 에러 출력 후 종료:
```
-c 플래그는 WorkRequest 번호(N)를 반드시 지정해야 합니다. 예: /wf -c 3
```

#### 4-2. WorkRequest 파일 탐색

Glob 도구로 `.agent-factory/work-requests/draft/WR-NNN.xml`, `.agent-factory/work-requests/accepted/WR-NNN.xml`, `.agent-factory/work-requests/executing/WR-NNN.xml`, `.agent-factory/work-requests/verifying/WR-NNN.xml` 패턴을 순서대로 검색합니다. 미발견 시 `.agent-factory/work-requests/complete/WR-NNN.xml`도 확인합니다. 어디에서도 찾지 못한 경우 에러 출력 후 종료.

#### 4-3. 삭제 실행

```bash
flow-launcher launch WR-NNN '/wf -c N'
```

- **`LAUNCH:`**: 복귀 메시지(`WR-NNN WorkRequest 삭제를 새 세션에서 실행합니다.`) 출력 후 종료
- **`INLINE:`**: `flow-conveyor delete WR-NNN` 인라인 실행 후 4-4로 진행
- **exit code 1**: 에러 메시지 출력 후 종료

#### 4-4. 삭제 메시지 출력

```
WR-NNN WorkRequest이 삭제되었습니다.
```

---

## Conveyor 상태 전이 요약

| 플래그 | 실행 전 상태 | 실행 후 상태 | 전이 명령 |
|--------|------------|------------|---------|
| `-o` (번호 없음) | (없음) | Draft 또는 Accepted (사용자 선택) | 번호 메뉴 질의 후 `flow-conveyor create "" --command init --status <draft|accepted>` + `flow-conveyor update-prompt --skip-validation` (채번+용도선택만, 편집 루프 미진입) |
| `-e` (번호 없음) | (없음) | Draft 또는 Accepted (사용자 선택) | 번호 메뉴 질의 후 `flow-conveyor create "" --command init --status <draft|accepted>` + `flow-conveyor update-prompt` + 편집 루프 (`-oe`도 동일 동작) |
| `-o N` | Draft | Draft (유지) | -- (내용 표시만, 편집 루프 미진입. 상태 유지) |
| `-o N` | Complete | Accepted (복원) | `flow-conveyor move WR-NNN accepted` (complete/ -> accepted/ 이동 처리는 conveyor_cli.py 내부 처리, 내용 표시만, 편집 루프 미진입) |
| `-o N` | Verifying/Executing | Accepted (즉시 전환) | `flow-conveyor move WR-NNN accepted --force` (내용 표시만, 편집 루프 미진입) |
| `-o N` | Accepted | Accepted (유지) | -- (내용 표시만, 편집 루프 미진입) |
| `-e N` | Draft | Accepted (승격) | `flow-conveyor move WR-NNN accepted` + 편집 루프 (편집 의도이므로 즉시 집중 대상으로 승격) |
| `-e N` | Complete | Accepted (복원) | `flow-conveyor move WR-NNN accepted` (complete/ -> accepted/ 이동 처리는 conveyor_cli.py 내부 처리) + 편집 루프 (`-oe N`도 동일 동작) |
| `-e N` | Verifying/Executing | Accepted (자동 복귀) | `flow-conveyor move WR-NNN accepted` + 편집 루프 (`-oe N`도 동일 동작) |
| `-e N` | Accepted | Accepted (유지) | -- (편집 루프 진입, `-oe N`도 동일 동작) |
| `-s` | Draft | (에러 종료) | "먼저 /wf -e N으로 Accepted 승격 후 다시 제출" 안내 출력 후 종료 |
| `-s` | Accepted | Executing | `.agent-factory/bin/flow-wf submit WR-NNN` (v2 driver background, SPEC.md §12.1) |
| `-s` (완료 후) | Executing | Verifying | driver 완료 단계에서 `flow-conveyor move WR-NNN verifying` 자동 처리 |
| `-d` | Verifying | Complete (간단검토 후 완료 선택 시) | 간단검토 -> `flow-merge WR-NNN --force`. **Complete = 머지 + 사용자 직접 테스트 통과 후의 진짜 종결** |
| `-d` | Verifying | Verifying (상세 검토 선택 시) | 새 review WorkRequest 생성 + `flow-conveyor link WR-MMM --derived-from WR-NNN` |
| `-d` | Draft/Accepted/Executing | Complete | `flow-conveyor complete WR-NNN` (기존 동작) |
| `-c` | Any | (삭제) | `flow-launcher launch WR-NNN '/wf -c N'` (LAUNCH/INLINE/에러 분기) |

## WorkRequest 프롬프트 생명주기

| 단계 | 플래그 | WorkRequest 상태 | 수행 명령 |
|------|--------|----------|---------|
| WorkRequest 생성 직후 | `-o` 또는 `-e`(또는 `-oe`) | `<prompt>` 미존재, `<result />` self-closing | `flow-conveyor create "" --command init --status <draft|accepted>` (`--status`는 사용자 선택 필수) |
| 프롬프트 작성 | `-o` (채번+용도선택만) | `<prompt>` 생성 (기본값) | `flow-conveyor update-prompt WR-NNN --command ... --goal "..." --target "..." --skip-validation` (품질 검증 건너뜀) |
| 프롬프트 작성 | `-e` 완료 또는 `-e NNN` (또는 `-oe`) | `<prompt>` 생성/갱신 | `flow-conveyor update-prompt WR-NNN --command ... --goal ... --target ...` |
| 워크플로우 실행 완료 | `-s` 후처리 | `<result>` 내용 기록 | `flow-conveyor update-result WR-NNN --registrykey ... --workdir ...` |
| 후속 작업 필요 | `-e NNN` (실행 완료 후 편집) | 새 WorkRequest 생성 + link | `flow-conveyor create --status accepted` + `flow-conveyor update-prompt WR-MMM` + `flow-conveyor link WR-MMM --derived-from WR-NNN` |
| WorkRequest 종료 | `-d` | 변경 없음 (히스토리 보존) | Verifying: 간단검토 -> `flow-merge WR-NNN --force` / 그 외: `flow-conveyor complete WR-NNN` |

## 주의사항

1. **단일 진입점**: WorkRequest 라이프사이클 전체를 `/wf` 하나로 관리합니다. `/wf`가 유일한 WorkRequest 관리 진입점입니다
2. **Accepted 복귀 동작**: `-o NNN`으로 Verifying/Executing WorkRequest에 접근 시 즉시 Accepted 전환합니다. `-e NNN` 또는 `-oe NNN`은 사용자 확인 없이 Accepted로 자동 복귀합니다
3. **`<command>` 태그 정책**: `-o`/`-e` 생성 시 설정된 값을 기본 보존하되, `-e NNN`(또는 `-oe NNN`) 편집 시 명시적 변경이 허용됩니다
4. **Bash 도구 사용**: Conveyor 상태 전이 및 파일 이동이 필요한 Step에서 허용합니다
5. **AskUserQuestion 미사용**: 모든 사용자 입력은 텍스트 메뉴 출력 후 자유 입력으로 수신합니다. 접두사는 `` `[WR-NNN]` : `[WF -플래그]` `` 형식을 사용합니다
6. **Task 도구 호출 금지**: 이 명령어는 비워크플로우 독립 명령어이므로 서브에이전트를 호출하지 않습니다
7. **wf 스킬 직접 로드**: `-s` 플래그 실행 시 SlashCommand/Skill 도구가 아닌 Read 도구로 해당 스킬 파일을 직접 로드하여 실행합니다
8. **워크플로우 발사 (v2 driver)**: `-s` 플래그는 `.agent-factory/bin/flow-wf submit WR-NNN` 단일 진입점으로 v2 driver 를 background 발사합니다 (T-489 Stage 3-A). driver 가 INIT 단계에서 `flow-conveyor move WR-NNN executing` 를 자동 수행하며, COMPLETE 단계에서 `flow-conveyor move WR-NNN verifying` 로 자동 전이합니다. PLAN/WORK/VERIFY/REPORT 4 Step 은 `claude -p` subprocess 로 격리 실행되므로 메인 세션 컨텍스트는 영향받지 않습니다. v1 의 `flow-launcher` / `LAUNCH/INLINE` 분기 / `_handle_conveyor_submit` 흐름은 폐지되었습니다. `-c` 플래그는 별도로 `flow-launcher` 를 계속 사용합니다 (Stage 3-A 범위 외).
9. **constraints/criteria 필수**: `0. 완료` 선택 시 constraints 또는 criteria가 누락이거나 10자 미만이면 완료를 거부하고 루프를 계속합니다. Step 1-4(신규 생성)와 Step 1-B-5(편집 루프, 최초/추가 사이클 양쪽) 모두에 적용됩니다. `-o` 단독 모드에서는 편집 루프에 진입하지 않으므로 이 검증이 적용되지 않습니다
10. **Verifying 분기 흐름**: `-d` 플래그 실행 시 Verifying 상태 WorkRequest은 간단 검토를 먼저 수행합니다. merge는 사용자의 명시적 "완료" 선택 후에만 실행됩니다. Verifying 이외 상태에서는 기존과 동일하게 즉시 Complete 처리됩니다
11. **품질 검증 (prompt_validator)**: `flow-conveyor update-prompt` 호출 시 `prompt_validator.py`가 자동으로 품질 점수를 계산합니다. 검증 대상 태그는 `goal`, `target`, `constraints`, `criteria` 4개이며 공식은 `score = (존재_태그수/4) × 0.6 + (유효_태그수/4) × 0.4`입니다 (유효 = 10자 이상 & `TODO:` 미시작). 임계값은 `QUALITY_THRESHOLD = 0.6`이며 미달 시 프롬프트가 자동 롤백되고 exit code 1로 종료됩니다. `--skip-validation` 플래그를 추가하면 품질 검증을 건너뜁니다. `-o` 모드(채번+용도선택만)와 `-d` 상세 검토 생성 시에는 편집 루프를 거치지 않으므로 `--skip-validation`을 사용합니다. `-e` 모드의 편집 루프에서는 constraints/criteria 10자 이상 검증이 선행되므로 품질 검증을 통과할 수 있습니다
12. **Draft 상태 정책**: `-o`/`-e` 생성 시 반드시 `--status draft` 또는 `--status accepted`을 지정해야 합니다 (T-385 이후 `--status` 필수화). 사용자 발화에 상태가 명시되지 않았으면 번호 메뉴로 질의합니다 (AskUserQuestion 미사용, 텍스트 번호 메뉴 사용). Draft 상태 WorkRequest에 `-s`를 시도하면 에러로 종료되므로, 먼저 `-e N`으로 Accepted 승격이 필요합니다. `-o N`은 Draft 상태를 유지한 채 내용만 표시합니다. `-e N`은 편집 의도이므로 Draft를 Accepted로 자동 승격합니다

## WorkRequest 관계 링크 가이드

이관 또는 후속 작업으로 새 WorkRequest를 생성한 경우 `flow-conveyor link` 명령으로 두 WorkRequest 간 관계를 기록합니다. 관계는 양방향으로 기록됩니다 (원본 WorkRequest와 대상 WorkRequest 양쪽에 자동 반영).

### 언제 사용하나

- 이전 WorkRequest(예: verifying)에서 이관하여 새 WorkRequest(예: implement)을 생성한 경우
- 선행 작업 완료 후 후속 WorkRequest를 새로 만든 경우

### 관계 유형 및 명령 예시

| 관계 유형 | 명령 | 설명 |
|----------|------|------|
| 이관 (derived-from) | `flow-conveyor link WR-135 --derived-from WR-130` | WR-135가 WR-130에서 파생된 WorkRequest |
| 선행 의존 (depends-on) | `flow-conveyor link WR-135 --depends-on WR-130` | WR-135가 WR-130 완료 후 진행 |
| 후행 차단 (blocks) | `flow-conveyor link WR-135 --blocks WR-140` | WR-135가 완료되어야 WR-140 진행 가능 |

### 관계 제거

```bash
flow-conveyor unlink WR-135 --derived-from WR-130
```

> 참고: 관계는 양방향으로 기록됩니다. `link` 실행 시 원본 WorkRequest와 대상 WorkRequest 양쪽 XML이 자동으로 업데이트됩니다.

---

## 자연어 매핑 가이드

| 자연어 요청 예시 | 매핑 플래그 | 상태 추천 | 근거 |
|-----------------|-----------|----------|------|
| "WorkRequest만 열어", "채번해줘", "WorkRequest 하나 만들어" | `-o` | (질의) | 생성만 요청, 편집 의도 없음 |
| "이거 WorkRequest 생성해줘", "나중에 할 거야", "언젠가 할 일", "백로그에 넣어" | `-o` 또는 `-e` | Draft | 미래 작업 의도 명시 |
| "지금 바로 할래", "이번에 집중할 거야", "당장 진행" | `-o` 또는 `-e` | Accepted | 즉시 집중 대상 의도 명시 |
| "WorkRequest 만들고 편집할게", "프롬프트 작성하자", "편집할게" | `-e` | (질의) | 생성 + 편집 의도 명시 (`-oe`는 `-e`의 단축 별칭) |
| "기존 WorkRequest 열어", "3번 WorkRequest 보여줘" | `-o N` | 상태 유지 | 열람만 요청, 편집 의도 없음 |
| "3번 WorkRequest 수정할게", "기존 WorkRequest 편집하자" | `-e N` | Draft -> Accepted 승격 | 편집 의도 명시 (`-oe N`도 동일 동작) |
| (이전 대화에서 goal/target/constraints/criteria 모두 추론 가능) | `-oe` | (질의) | 맥락 충분 → 생성+편집 즉시 처리 |
| (의도 불명확) | `-e` | (질의) | 기존 동작 호환을 위해 편집 루프 포함 모드를 기본값으로 사용 |

> **판단 원칙**:
> (1) 이전 대화에서 goal/target/constraints/criteria 모두 추론 가능한 경우 → `-oe` (생성+편집 즉시 처리)
> (2) 편집 의도가 명시되었으나 맥락이 부분적인 경우 → `-e` (편집 루프 포함)
> (3) 채번만 필요하거나 편집 의도가 없는 경우 → `-o` (채번+용도선택만)
> (4) **상태 선택**: "WorkRequest 생성/나중에/언젠가/백로그" -> Draft 추천, "지금/바로/이번에/집중" -> Accepted 추천, 무맥락이면 번호 메뉴로 질의
