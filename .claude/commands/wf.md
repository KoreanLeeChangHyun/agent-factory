---
description: "티켓 라이프사이클 통합 관리. -o(Open/열람), -e(Edit/편집), -oe(Open+Edit 단축), -s(Submit), -d(Done), -c(Cancel) 6개 플래그로 티켓 생성부터 종료까지 단일 진입점으로 제어합니다. Use when: 티켓 생성, 티켓 편집, 워크플로우 실행, 티켓 종료, 티켓 삭제를 한 번에 처리할 때"
argument-hint: "[-o|-e|-oe|-s|-d|-c] [N] (티켓 라이프사이클 통합 관리)"
---

# wf (Workflow 통합 명령어)

티켓 라이프사이클 전체를 단일 진입점으로 관리합니다. `-o`(Open/채번+용도선택만), `-e`(Edit/편집), `-oe`(Open+Edit 단축 별칭), `-s`(Submit), `-d`(Done), `-c`(Cancel/삭제) 6개 플래그로 생성부터 종료까지 제어합니다.

## Step 0. 플래그 파싱 및 라우팅

`$ARGUMENTS`에서 플래그와 티켓 번호를 파싱하여 실행 흐름을 결정합니다.

### 파싱 규칙

1. **플래그 추출**: `$ARGUMENTS`에서 `-oe`, `-o`, `-e`, `-s`, `-d`, `-c` 패턴을 순서대로 검색합니다 (`-oe`를 `-o`와 `-e`보다 먼저 검색하여 정확한 매칭 보장)
2. **티켓 번호 추출**: 숫자 `N`(예: `1`, `12`, `123`)을 파싱하여 3자리 zero-padding 적용 (예: `3` -> `T-003`)
3. **플래그와 번호가 모두 없는 경우**: 아래 도움말 메뉴를 출력하고 종료합니다

### 도움말 메뉴 (플래그 미지정 시 출력)

```
`[T-NNN]` : `[WF]` wf 통합 명령어 사용법

| 플래그 | 용도 | 예시 |
|--------|------|------|
| `/wf -o` | 새 티켓 생성 (채번+용도선택만) | `/wf -o` |
| `/wf -o N` | 기존 티켓 Open (내용 표시만) | `/wf -o 3` |
| `/wf -e` | 새 티켓 생성 + 프롬프트 편집 | `/wf -e` |
| `/wf -e N` | 기존 티켓 편집 | `/wf -e 3` |
| `/wf -oe` | 새 티켓 생성 + 편집 (`-o -e` 단축) | `/wf -oe` |
| `/wf -oe N` | 기존 티켓 Open + 편집 (`-o -e` 단축) | `/wf -oe 3` |
| `/wf -s N` | 티켓 제출 및 워크플로우 실행 | `/wf -s 3` |
| `/wf -d N` | 티켓 종료 (Done 상태로 이동) | `/wf -d 3` |
| `/wf -c N` | 티켓 삭제 | `/wf -c 3` |

현재 칸반 상태를 확인하려면 `.claude-organic/tickets/` 디렉터리의 XML 티켓 파일을 참조하세요.
```

### 라우팅 규칙

| 조건 | 실행 흐름 |
|------|----------|
| `-o` 플래그 | [## -o](#-o) (Open/생성 또는 열람, 채번+용도선택까지만) |
| `-e` 플래그 | [## -e](#-e) (Edit/편집, 편집 루프 진입) |
| `-oe` 플래그 | [## -e](#-e) (하위호환, `-e`와 동일 동작) |
| `-s` 플래그 | [## -s](#-s) (Submit/제출) |
| `-d` 플래그 | [## -d](#-d) (Done/종료) |
| `-c` 플래그 | [## -c](#-c) (Cancel/삭제) |
| 플래그 없음 | 도움말 메뉴 출력 후 종료 |

---

## -o

### 티켓 생성 또는 열람

`$ARGUMENTS`에서 티켓 번호 `N`의 유무를 확인하여 서브플로우를 분기합니다:

| 번호 유무 | 실행 흐름 |
|---------|----------|
| 없음 | Step 1-A-o: 새 티켓 생성 (채번+용도선택만, 편집 루프 미진입) |
| 있음 | Step 1-B-o: 기존 티켓을 Open으로 전이 (즉시 실행, 편집 루프 미진입) |

### Step 1-A-o. 번호 없음: 새 티켓 생성 (채번+용도선택만)

> **칸반 전이**: (없음) -> **Open**

#### 1-1. 빈 티켓 즉시 채번

```bash
flow-kanban create "" --command init
```

stdout에서 T-NNN을 파싱하고 채번 결과를 출력합니다:
```
`[T-NNN]` : `[WF -o]` 티켓 T-NNN을 생성했습니다.
```

#### 1-2. 대화 맥락 감지 및 용도 결정

이전 대화에서 작업 요청이 감지된 경우 트랙 A, 그렇지 않은 경우 트랙 B를 실행합니다.

**트랙 A: 맥락 감지됨** -- 이전 대화에서 작업 요청이 감지된 경우:

> **맥락 충분성 판단**: goal/target/constraints/criteria 4개 항목 모두 추론 가능(각 10자 이상)한 경우 "맥락 충분"으로 간주합니다. constraints 또는 criteria 중 하나라도 추론 불가이면 "맥락 부분"으로 간주합니다.

```
`[T-NNN]` : `[WF -o]` 이전 대화를 기반으로 다음과 같이 추론했습니다:

- 용도: <추론된 용도>
- goal: <추론된 목표>
- target: <추론된 대상>
- constraints: <추론된 제약 조건> (추론 불가 시 "미상")
- criteria: <추론된 완료 기준> (추론 불가 시 "미상")
- context: <이전 대화 핵심 요약>

`1.` 확인 -- 이 용도로 티켓을 생성합니다
`2.` 용도 직접 지정 -- 목적 선택 메뉴로 전환합니다
`0.` 취소 -- 생성하지 않고 종료합니다
```

- `1.` 확인: 맥락 충분성에 따라 분기합니다:
  - **맥락 충분** (constraints/criteria 모두 추론 성공): `flow-kanban update-prompt T-NNN --command <command값> --goal "<추론된 goal>" --target "<추론된 target>" --constraints "<추론된 constraints>" --criteria "<추론된 criteria>" --context "<추론된 context>" --skip-validation` 호출 후 1-3으로 진행
  - **맥락 부분** (constraints 또는 criteria 추론 불가): `flow-kanban update-prompt T-NNN --command <command값> --goal "<추론된 goal>" --target "<추론된 target>" --skip-validation` 호출 후 1-3으로 진행
  - (`-o` 모드는 편집 루프 미진입이므로 품질 검증을 건너뜁니다)
- `2.` 용도 직접 지정: 트랙 B로 전환
- `0.` 취소: 티켓 생성 없이 종료

**트랙 B: 맥락 미감지 또는 fallback** -- Read 도구로 `.claude-organic/prompts/prompt.txt`를 읽어 메뉴 항목을 로드한 뒤 출력합니다:

```
`[T-NNN]` : `[WF -o]` 어떤 목적의 티켓을 생성할까요?

1. <항목 1>
2. <항목 2>
...
0. 완료 -- 생성하지 않고 종료합니다

번호 또는 자유 텍스트를 입력하세요:
```

**용도->command 매핑**: 연구=`research`, 구현/버그수정/리팩토링/아키텍처설계=`implement`, 리뷰=`review`

사용자가 번호를 선택하면 해당 command 값으로 `flow-kanban update-prompt T-NNN --command <command값> --goal "(미정)" --target "(미정)" --skip-validation`을 호출합니다 (`--goal`/`--target`은 CLI 필수 인자이므로 placeholder를 전달하고, `-o` 모드는 편집 루프 미진입이므로 `--skip-validation`으로 품질 검증을 건너뜁니다). "0. 완료" 선택 시 종료합니다.

#### 1-3. 완료 메시지 출력

```
T-NNN 티켓이 생성되었습니다. (파일: .claude-organic/tickets/open/T-NNN.xml)
```

**맥락 충분 시** (트랙 A에서 constraints/criteria 모두 추론 성공):

## 후속 커맨드 안내

| 목적 | 커맨드 | 설명 |
|------|--------|------|
| 편집 | `/wf -e N` | 프롬프트 내용을 추가로 수정합니다 |
| 제출 | `/wf -s N` | <command> 태그에 따라 자동 라우팅 <- 권장 |
| 종료 | `/wf -d N` | 티켓을 Done 상태로 종료합니다 |

**맥락 부분 시** (constraints 또는 criteria 추론 불가):

## 후속 커맨드 안내

| 목적 | 커맨드 | 설명 |
|------|--------|------|
| 편집 | `/wf -e N` | 프롬프트 작성 및 내용 편집 <- 권장 |
| 제출 | `/wf -s N` | <command> 태그에 따라 자동 라우팅 |
| 종료 | `/wf -d N` | 티켓을 Done 상태로 종료합니다 |

### Step 1-B-o. 번호 있음: 기존 티켓을 Open으로 전이

편집 루프에 진입하지 않습니다.

#### 1-B-o-1. 티켓 파일 로드

Glob 도구로 `.claude-organic/tickets/open/T-NNN.xml`, `.claude-organic/tickets/progress/T-NNN.xml`, `.claude-organic/tickets/review/T-NNN.xml` 패턴을 순서대로 검색합니다. Read 도구로 XML의 `<metadata>/<status>`를 확인하여 분기합니다:

| 상태 | 분기 흐름 |
|------|----------|
| `Open` | 안내 메시지(`T-NNN은 이미 Open 상태입니다.`) 출력 후 1-B-o-2로 진행 |
| `In Progress` / `Review` | `flow-kanban move T-NNN open --force` 즉시 실행 후 상태 변경 확인 메시지 출력, 1-B-o-2로 진행 |
| `Done` (.claude-organic/tickets/done/ 발견) | `flow-kanban move T-NNN open --force` 실행, 1-B-o-2로 진행 |
| 파일 미발견 | 에러 출력 후 종료: `T-NNN 티켓 파일을 찾을 수 없습니다.` |

#### 1-B-o-2. 후속 안내 출력

```
`[T-NNN]` : `[WF -o]` T-NNN 티켓을 Open 상태로 전이했습니다.

## 후속 커맨드 안내

| 목적 | 커맨드 | 설명 |
|------|--------|------|
| 편집 | `/wf -e N` | 프롬프트 작성 및 내용 편집 |
| 제출 | `/wf -s N` | <command> 태그에 따라 자동 라우팅 |
| 종료 | `/wf -d N` | 티켓을 Done 상태로 종료합니다 |
```

---

## -e

### 티켓 생성 + 편집 또는 기존 티켓 편집

`-oe`는 `-e`의 단축 별칭으로 동일 로직을 실행합니다.

| 번호 유무 | 실행 흐름 |
|---------|----------|
| 없음 | Step 1-A-e: 새 티켓 생성 + 프롬프트 편집 루프 |
| 있음 | Step 1-B-e: 기존 티켓 편집 루프 |

### Step 1-A-e. 번호 없음: 새 티켓 생성 + 프롬프트 편집 루프

> **칸반 전이**: (없음) -> **Open**

#### 1-1. 빈 티켓 즉시 채번

```bash
flow-kanban create "" --command init
```

stdout에서 T-NNN을 파싱하고 채번 결과를 출력합니다:
```
`[T-NNN]` : `[WF -e]` 티켓 T-NNN을 생성했습니다.
```

#### 1-2. 스킬 로드

Read 도구로 `.claude/skills/research-prompt-engineering/SKILL.md`를 읽어 프롬프트 작성 지침을 로드합니다.

#### 1-3. 대화 맥락 감지 및 용도 결정

**트랙 A: 맥락 감지됨** -- 이전 대화에서 작업 요청이 감지된 경우:

> **맥락 충분성 판단**: goal/target/constraints/criteria 4개 항목 모두 추론 가능(각 10자 이상)한 경우 "맥락 충분"으로 간주합니다. constraints 또는 criteria 중 하나라도 추론 불가이면 "맥락 부분"으로 간주합니다.

```
`[T-NNN]` : `[WF -e]` 이전 대화를 기반으로 다음과 같이 추론했습니다:

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
- `0.` 취소: 티켓 생성 없이 종료

**트랙 B: 맥락 미감지 또는 fallback** -- Read 도구로 `.claude-organic/prompts/prompt.txt`를 읽어 메뉴 항목을 로드합니다.

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

**1단계 - 사용자 입력 수신 및 안내:** 현재 프롬프트 상태를 반영한 안내와 개선 제안을 출력합니다 (접두사: `` `[T-NNN]` : `[WF -e]` ``). 사용자 입력을 기반으로 goal, target, constraints, criteria, context 정보를 개선합니다.

**2단계 - 내부 모호성 분석 (사용자에게 노출하지 않음):** 로드한 `research-prompt-engineering` 스킬의 모호성 분석 체크리스트 5항목과 자가 점검 체크리스트 7항목을 내부적으로 재평가합니다.

**3단계 - 웹검색/코드탐색 자율 수행:**

| 감지 신호 | 수행 액션 | 사용 도구 |
|----------|----------|----------|
| 함수, 모듈, 파일, 클래스, 컴포넌트, 변수, 메서드 | 코드베이스 탐색 | Grep, Glob, Read |
| API, 프레임워크, 패키지, 버전, 라이브러리, SDK, 외부 서비스 | 웹검색 | WebSearch, WebFetch |
| 양쪽 신호 모두 감지 | 코드베이스 탐색 + 웹검색 모두 수행 | Grep, Glob, Read, WebSearch, WebFetch |

**4단계 - G1~G4 게이트 평가 및 동적 선택지 출력:** G1~G4 게이트 조건 충족 시 완료를 제안합니다. 매 턴 종료 시 아래 구조로 동적 선택지를 반드시 출력합니다:

1. **헤더**: 접두사(`` `[T-NNN]` : `[WF -e]` ``) + 제목
2. **간단 요약**: 현재 프롬프트 진행 상태를 1-2문장으로 요약
3. **동적 선택지**: 대화 맥락을 분석하여 `1.`~`5.` (최대 5개) + `0.` 완료를 생성
4. **안내 문구**: "자유 텍스트 입력도 가능합니다." 문구를 선택지 아래에 출력

- 사용자 "0. 완료" 선택 시 아래 순서로 처리:
  0. **constraints/criteria 필수 검증**: constraints 또는 criteria가 누락이거나 10자 미만이면 아래 메시지를 출력하고 루프를 계속합니다 (이하 단계를 실행하지 않음):
     ```
     `[T-NNN]` : `[WF -e]` constraints 또는 criteria가 누락되었거나 내용이 부족합니다(10자 이상 필요). 보강 후 다시 완료를 선택하세요.
     ```
  1. 대화 내용을 기반으로 티켓 제목을 자동 생성합니다 (20자 이내, 한국어, 동사형)
  2. `flow-kanban update-prompt T-NNN --command <command값> --goal "<goal>" --target "<target>" --constraints "<constraints>" --criteria "<criteria>" --context "<context>"` (context 없으면 생략)
  3. Read 도구로 갱신된 XML 파일을 읽어 prompt 내용 확인 후 Step 1-5로 진행

#### 1-5. 완료 메시지 출력

```
T-NNN 티켓이 생성되었습니다. (파일: .claude-organic/tickets/open/T-NNN.xml)

## 후속 커맨드 안내

| 목적 | 커맨드 | 설명 |
|------|--------|------|
| 제출 | `/wf -s N` | <command> 태그에 따라 자동 라우팅 <- 권장 |
| 편집 | `/wf -e N` | 티켓 내용을 추가로 수정합니다 |
| 종료 | `/wf -d N` | 티켓을 Done 상태로 종료합니다 |

> 참고: 여러 워크플로우를 순차 실행하려면 `<command>` 태그에 `research>implement>review` 형식으로 체인을 지정할 수 있습니다.
```

### Step 1-B-e. 번호 있음: 기존 티켓 편집 루프

> **칸반 전이**: Done -> **Open** (복원) / Review/In Progress -> **Open** (자동 복귀) / Open -> Open (유지)

#### 1-B-1. 티켓 파일 로드

Glob 도구로 `.claude-organic/tickets/open/T-NNN.xml`, `.claude-organic/tickets/progress/T-NNN.xml`, `.claude-organic/tickets/review/T-NNN.xml` 패턴을 순서대로 검색합니다.

**파일 발견 시**: XML `<status>` 요소에서 현재 칸반 상태를 판별합니다.

**파일 미발견 시**: `.claude-organic/tickets/done/T-NNN.xml`을 확인합니다:
- 존재하면: `flow-kanban move T-NNN open` 실행 (파일 이동 처리는 kanban_cli.py가 담당)
- 어디에서도 찾지 못한 경우: 에러 출력 후 종료 (`T-NNN 티켓 파일을 찾을 수 없습니다.`)

#### 1-B-2. Review/In Progress 상태 자동 Open 복귀

현재 상태가 `In Progress` 또는 `Review`인 경우, 사용자 확인 없이 즉시 Open 복귀:
```bash
flow-kanban move T-NNN open
```

Open 상태이면 상태 변경 없이 즉시 편집 루프로 진입합니다.

#### 1-B-3. 현재 티켓 내용 표시

```
## 현재 T-NNN.xml 내용

<티켓 파일 내용 전체>
```

#### 1-B-4. 스킬 로드

Read 도구로 `.claude/skills/research-prompt-engineering/SKILL.md`를 읽어 프롬프트 작성 지침을 로드합니다.

#### 1-B-5. 대화형 편집 루프

티켓 XML에서 `<result>` 요소의 상태를 확인하여 분기를 결정합니다. 대화 루프의 매 턴은 Step 1-4와 동일한 처리 순서(1단계~4단계)를 따릅니다.

**분기 A -- `<result />` self-closing 또는 `<result>` 미존재 (미실행): 기존 프롬프트 수정**
- 현재 `<prompt>` 내용을 표시하여 작업 맥락을 제공합니다
- "0. 완료" 선택 시 constraints/criteria 필수 검증 후 `flow-kanban update-prompt T-NNN --command <command값> --goal "<goal>" --target "<target>" --constraints "<constraints>" --criteria "<criteria>" --context "<context>"`

**분기 B -- `<result>` 내용 있음 (실행 완료): 새 티켓 생성 + link**
- 이미 실행이 완료된 티켓이므로, 추가 작업이 필요한 경우 새 티켓을 생성하도록 안내합니다
- "0. 완료" 선택 시 constraints/criteria 필수 검증 후:
  1. `flow-kanban create "<새 제목>" --command <command값>` 로 새 티켓 T-MMM 생성
  2. `flow-kanban update-prompt T-MMM --goal "<goal>" --target "<target>" --constraints "<constraints>" --criteria "<criteria>" --context "<context>"`
  3. `flow-kanban link T-MMM --derived-from T-NNN` 로 관계 링크 설정
  4. 안내: `T-MMM 티켓이 T-NNN에서 파생되어 생성되었습니다. /wf -s MMM 으로 제출하세요.`

> **constraints/criteria 필수 검증**: 모든 사이클에서 "0. 완료" 선택 시 constraints 또는 criteria가 누락이거나 10자 미만이면 메시지를 출력하고 루프를 계속합니다.

> **`<command>` 태그 갱신 정책**: `-e NNN` 편집 시 `<command>` 갱신이 허용됩니다. `update-prompt`의 `--command` 인자로 직접 변경할 수 있습니다.

> `context` 값이 없는 경우 해당 인자를 생략합니다.

#### 1-B-6. 완료 메시지 출력

```
T-NNN 티켓이 업데이트되었습니다.

## 후속 커맨드 안내

| 목적 | 커맨드 | 설명 |
|------|--------|------|
| 제출 | `/wf -s N` | <command> 태그에 따라 자동 라우팅 <- 권장 |
| 종료 | `/wf -d N` | 티켓을 Done 상태로 종료합니다 |
```

---

## -s

### 티켓 제출 및 워크플로우 실행

> **칸반 전이**: Open -> **Submit** -> **In Progress** (Submit 전환은 즉시, In Progress 전환은 flow-init 실행 시)

#### 칸반 상태 전환

```bash
flow-kanban move T-NNN submit
```

실패(exit code 1) 시 경고 메시지를 출력하되 워크플로우 실행은 계속 진행합니다 (비차단).

> **INLINE 모드 참고**: `flow-launcher`가 `INLINE:` 응답을 반환한 경우, 메인 세션에서 이미 `move submit`이 실행된 상태입니다. `kanban_cli.py`의 멱등성이 보장되므로 재실행해도 빈 파일이 생성되지 않습니다 (T-252).

#### 실행 환경 분기

```bash
flow-launcher launch T-NNN '/wf -s N'
```

- **`LAUNCH:`**: 복귀 메시지(`T-NNN 워크플로우를 새 세션에서 실행합니다.`) 출력 (이후 로직 미실행)
- **`INLINE:`**: 아래 2-1~2-5 로직을 그대로 실행
- **exit code 1**: 에러 메시지 출력 후 종료

#### 2-1. 티켓 번호 검증

`$ARGUMENTS`에서 숫자 `N`을 파싱합니다. 없으면 에러 출력 후 종료:
```
-s 플래그는 티켓 번호(N)를 반드시 지정해야 합니다. 예: /wf -s 3
```

#### 2-2. 티켓 파일 로드

Glob 도구로 `.claude-organic/tickets/open/T-NNN.xml`, `.claude-organic/tickets/progress/T-NNN.xml`, `.claude-organic/tickets/review/T-NNN.xml` 패턴을 순서대로 검색합니다. 미발견 시 에러 출력 후 종료.

#### 2-3. `<command>` 태그 파싱

XML에서 `<prompt>` 요소 존재 여부를 확인합니다:
- `<prompt>` 미존재 또는 `<goal>` 내용 없음: 에러 출력 후 종료 (`워크플로우가 정의되지 않았습니다. /wf -e N으로 먼저 작성하세요.`)
- `<prompt>` 존재: `<metadata>` 직하 `<command>` 요소를 읽습니다

**체인 command 파싱**: `<command>` 값에 `>` 구분자가 포함된 경우 (예: `research>implement>review`):
- `>` 기준으로 split, 첫 번째 세그먼트를 현재 실행할 command로 사용
- 각 세그먼트가 유효한 command인지 검증 (`implement`, `research`, `review`)
- 유효하지 않은 세그먼트가 있으면 에러 출력 후 종료

**단일 command 검증**: `<command>` 요소 미존재 또는 유효하지 않은 값이면 에러 출력 후 종료.

#### 2-4. 실행 안내 출력

단일 command: `T-NNN 티켓을 <command> 워크플로우로 실행합니다.`
체인 command: `T-NNN 티켓을 <첫번째 세그먼트> 워크플로우로 실행합니다. (체인: research > implement > review, 1/3 스테이지)`

#### 2-5. 워크플로우 스킬 로드 및 실행

Read 도구로 현재 실행할 command에 해당하는 스킬을 직접 로드합니다:

| `<command>` 값 | 로드할 스킬 파일 |
|----------------|----------------|
| `implement` | `.claude/skills/workflow-wf/SKILL.md` |
| `research` | `.claude/skills/workflow-wf/SKILL.md` |
| `review` | `.claude/skills/workflow-wf/SKILL.md` |

> **체인 command 전달 규칙**: 오케스트레이터가 step-init의 `flow-init <command>` 호출 시, 체인인 경우 전체 문자열(예: `research>implement`)을 `<command>` 인자로 전달해야 합니다. initialization.py가 `>` 구분자를 감지하여 첫 세그먼트를 실제 실행 command로, 전체 문자열을 `.context.json`의 `command` 필드에 기록합니다.

> 워크플로우 완료 후 `flow-kanban move T-NNN review`로 자동 전이됩니다. 체인 command인 경우 finalization.py가 완료 후 자동으로 다음 스테이지를 새 세션에서 실행합니다.

---

## -d

### 티켓 종료

> **칸반 전이**: Review -> **Done** (간단검토 후 완료 선택 시) / Review -> **Review** (상세 review 선택 시) / Open,In Progress -> **Done** (즉시 처리)

#### 3-1. 티켓 번호 검증

`$ARGUMENTS`에서 숫자 `N`을 파싱합니다. 없으면 에러 출력 후 종료:
```
-d 플래그는 티켓 번호(N)를 반드시 지정해야 합니다. 예: /wf -d 3
```

#### 3-2. 티켓 상태 확인 및 분기

Glob 도구로 `.claude-organic/tickets/open/T-NNN.xml`, `.claude-organic/tickets/progress/T-NNN.xml`, `.claude-organic/tickets/review/T-NNN.xml` 패턴을 순서대로 탐색하고 Read 도구로 `<status>` 요소를 확인하여 분기합니다:

| 현재 상태 | 실행 흐름 |
|----------|----------|
| `Review` | 3-A. Review 간단 검토 흐름 |
| 그 외 (Open, In Progress 등) | 3-B. 즉시 Done 처리 (기존 로직) |

#### 3-A. Review 간단 검토 흐름

##### 3-A-1. 최근 워크플로우 산출물 탐색

`.claude-organic/runs/` 하위에서 해당 티켓의 가장 최근 워크플로우 디렉터리를 탐색합니다:
- Glob 도구로 `.claude-organic/runs/*/T-NNN*/*/report.md` 또는 `.claude-organic/runs/*/*/implement/report.md` 등을 검색합니다
- 티켓 XML의 `<result>` 요소의 `<workdir>` 값을 확인하여 정확한 워크플로우 디렉터리를 특정합니다
- `<workdir>` 값이 없으면 `.claude-organic/runs/` 하위에서 최신 타임스탬프 디렉터리를 탐색합니다

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
`[T-NNN]` : `[WF -d]` Review 간단 검토 결과

| 항목 | 결과 | 상세 |
|------|------|------|
| 보고서-변경 파일 일치 | OK / WARN | 일치 N개, 불일치 N개 |
| py_compile | OK / WARN / N/A | 통과 N개, 실패 N개 |
| 보고서 존재 | OK / WARN | report.md 경로 |
```

##### 3-A-3. 검토 결과 기반 선택지 제시

| 조건 | 제시 선택지 |
|------|-----------|
| 전항목 OK | 1. 완료 -- 커밋, merge, worktree 정리, Done 전이를 실행합니다 / 2. 상세 review -- review 워크플로우를 제출합니다 / 0. 취소 |
| WARN 1개 이상 | 1. 완료 (경고 무시) -- 커밋, merge, worktree 정리, Done 전이를 실행합니다 / 2. 상세 review -- review 워크플로우를 제출합니다 (권장) / 0. 취소 |

##### 3-A-4. 선택지 처리

**"1. 완료" 선택 시:**
```bash
flow-merge T-NNN --force
```
`flow-merge`의 5단계 파이프라인(자동 커밋 -> merge -> worktree 정리 -> kanban done -> 브랜치 삭제)을 실행합니다. 실패 시 에러 메시지 출력 후 종료합니다.

성공 시 종료 메시지:
```
`[T-NNN]` : `[WF -d]` T-NNN 티켓이 Done 상태로 종료되었습니다. (파일: .claude-organic/tickets/done/T-NNN.xml)
```

**"2. 상세 review" 선택 시:**
- 기존 티켓의 `<command>` 값을 확인합니다
- 새 review 티켓을 생성하고 원본 티켓과 link합니다:
  1. `flow-kanban create "T-NNN 상세 리뷰" --command review` 로 새 티켓 T-MMM 생성
  2. `flow-kanban update-prompt T-MMM --goal "T-NNN 구현 결과 상세 리뷰" --target "<보고서 경로>" --constraints "간단 검토에서 발견된 경고 항목을 중점 검토" --criteria "모든 WARN 항목이 해소되거나 수용 근거가 명시됨" --context "간단 검토에서 경고 발견" --skip-validation`
  3. `flow-kanban link T-MMM --derived-from T-NNN`
- 안내 메시지를 출력합니다:
```
`[T-NNN]` : `[WF -d]` 상세 review 티켓 T-MMM을 생성했습니다. (T-NNN에서 파생)

| 목적 | 커맨드 | 설명 |
|------|--------|------|
| 제출 | `/wf -s MMM` | review 워크플로우 실행 <- 권장 |
| 편집 | `/wf -e MMM` | review 프롬프트를 먼저 편집합니다 |
```

**"0. 취소" 선택 시:**
안내 메시지 출력 후 종료:
```
`[T-NNN]` : `[WF -d]` 취소되었습니다. 티켓은 Review 상태를 유지합니다.
```

#### 3-B. 즉시 Done 처리

Review 이외 상태(Open, In Progress 등)의 티켓은 기존과 동일하게 즉시 Done 처리합니다.

```bash
flow-kanban done T-NNN
```

- exit code 1, "찾을 수 없습니다": 에러 출력 후 종료
- exit code 1, "이미 Done": 안내 출력 후 종료
- exit code 0: 종료 메시지 출력

> `flow-kanban done`은 상태 갱신과 파일 이동(상태별 디렉터리(`open/`, `progress/`, `review/`) -> `.claude-organic/tickets/done/T-NNN.xml`)을 내부적으로 처리합니다.

종료 메시지:
```
T-NNN 티켓이 Done 상태로 종료되었습니다. (파일: .claude-organic/tickets/done/T-NNN.xml)
```

---

## -c

### 티켓 삭제

> **칸반 전이**: Any -> **(삭제)**

`-d`(Done)와 달리 히스토리를 보존하지 않습니다.

#### 4-1. 티켓 번호 검증

`$ARGUMENTS`에서 숫자 `N`을 파싱합니다. 없으면 에러 출력 후 종료:
```
-c 플래그는 티켓 번호(N)를 반드시 지정해야 합니다. 예: /wf -c 3
```

#### 4-2. 티켓 파일 탐색

Glob 도구로 `.claude-organic/tickets/open/T-NNN.xml`, `.claude-organic/tickets/progress/T-NNN.xml`, `.claude-organic/tickets/review/T-NNN.xml` 패턴을 순서대로 검색합니다. 미발견 시 `.claude-organic/tickets/done/T-NNN.xml`도 확인합니다. 어디에서도 찾지 못한 경우 에러 출력 후 종료.

#### 4-3. 삭제 실행

```bash
flow-launcher launch T-NNN '/wf -c N'
```

- **`LAUNCH:`**: 복귀 메시지(`T-NNN 티켓 삭제를 새 세션에서 실행합니다.`) 출력 후 종료
- **`INLINE:`**: `flow-kanban delete T-NNN` 인라인 실행 후 4-4로 진행
- **exit code 1**: 에러 메시지 출력 후 종료

#### 4-4. 삭제 메시지 출력

```
T-NNN 티켓이 삭제되었습니다.
```

---

## 칸반 상태 전이 요약

| 플래그 | 실행 전 상태 | 실행 후 상태 | 전이 명령 |
|--------|------------|------------|---------|
| `-o` (번호 없음) | (없음) | Open | `flow-kanban create "" --command init` + `flow-kanban update-prompt --skip-validation` (채번+용도선택만, 편집 루프 미진입) |
| `-e` (번호 없음) | (없음) | Open | `flow-kanban create "" --command init` + `flow-kanban update-prompt` + 편집 루프 (`-oe`도 동일 동작) |
| `-o N` | Done | Open (복원) | `flow-kanban move T-NNN open` (done/ -> open/ 이동 처리는 kanban_cli.py 내부 처리, 내용 표시만, 편집 루프 미진입) |
| `-o N` | Review/In Progress | Open (즉시 전환) | `flow-kanban move T-NNN open --force` (내용 표시만, 편집 루프 미진입) |
| `-o N` | Open | Open (유지) | -- (내용 표시만, 편집 루프 미진입) |
| `-e N` | Done | Open (복원) | `flow-kanban move T-NNN open` (done/ -> open/ 이동 처리는 kanban_cli.py 내부 처리) + 편집 루프 (`-oe N`도 동일 동작) |
| `-e N` | Review/In Progress | Open (자동 복귀) | `flow-kanban move T-NNN open` + 편집 루프 (`-oe N`도 동일 동작) |
| `-e N` | Open | Open (유지) | -- (편집 루프 진입, `-oe N`도 동일 동작) |
| `-s` | Open | In Progress | `flow-launcher launch T-NNN '/wf -s N'` (LAUNCH/INLINE/에러 분기) |
| `-s` (완료 후) | In Progress | Review | `flow-kanban move T-NNN review` (workflow-wf submit 처리) |
| `-d` | Review | Done (간단검토 후 완료 선택 시) | 간단검토 -> `flow-merge T-NNN --force` |
| `-d` | Review | Review (상세 review 선택 시) | 새 review 티켓 생성 + `flow-kanban link T-MMM --derived-from T-NNN` |
| `-d` | Open/In Progress | Done | `flow-kanban done T-NNN` (기존 동작) |
| `-c` | Any | (삭제) | `flow-launcher launch T-NNN '/wf -c N'` (LAUNCH/INLINE/에러 분기) |

## 티켓 프롬프트 생명주기

| 단계 | 플래그 | 티켓 상태 | 수행 명령 |
|------|--------|----------|---------|
| 티켓 생성 직후 | `-o` 또는 `-e`(또는 `-oe`) | `<prompt>` 미존재, `<result />` self-closing | `flow-kanban create "" --command init` |
| 프롬프트 작성 | `-o` (채번+용도선택만) | `<prompt>` 생성 (기본값) | `flow-kanban update-prompt T-NNN --command ... --goal "..." --target "..." --skip-validation` (품질 검증 건너뜀) |
| 프롬프트 작성 | `-e` 완료 또는 `-e NNN` (또는 `-oe`) | `<prompt>` 생성/갱신 | `flow-kanban update-prompt T-NNN --command ... --goal ... --target ...` |
| 워크플로우 실행 완료 | `-s` 후처리 | `<result>` 내용 기록 | `flow-kanban update-result T-NNN --registrykey ... --workdir ...` |
| 후속 작업 필요 | `-e NNN` (실행 완료 후 편집) | 새 티켓 생성 + link | `flow-kanban create` + `flow-kanban update-prompt T-MMM` + `flow-kanban link T-MMM --derived-from T-NNN` |
| 티켓 종료 | `-d` | 변경 없음 (히스토리 보존) | Review: 간단검토 -> `flow-merge T-NNN --force` / 그 외: `flow-kanban done T-NNN` |

## 주의사항

1. **단일 진입점**: 티켓 라이프사이클 전체를 `/wf` 하나로 관리합니다. `/wf`가 유일한 티켓 관리 진입점입니다
2. **Open 복귀 동작**: `-o NNN`으로 Review/In Progress 티켓에 접근 시 즉시 Open 전환합니다. `-e NNN` 또는 `-oe NNN`은 사용자 확인 없이 Open으로 자동 복귀합니다
3. **`<command>` 태그 정책**: `-o`/`-e` 생성 시 설정된 값을 기본 보존하되, `-e NNN`(또는 `-oe NNN`) 편집 시 명시적 변경이 허용됩니다
4. **Bash 도구 사용**: 칸반 상태 전이 및 파일 이동이 필요한 Step에서 허용합니다
5. **AskUserQuestion 미사용**: 모든 사용자 입력은 텍스트 메뉴 출력 후 자유 입력으로 수신합니다. 접두사는 `` `[T-NNN]` : `[WF -플래그]` `` 형식을 사용합니다
6. **Task 도구 호출 금지**: 이 명령어는 비워크플로우 독립 명령어이므로 서브에이전트를 호출하지 않습니다
7. **wf 스킬 직접 로드**: `-s` 플래그 실행 시 SlashCommand/Skill 도구가 아닌 Read 도구로 해당 스킬 파일을 직접 로드하여 실행합니다
8. **독립 세션 실행**: `-s`와 `-c` 플래그는 `flow-launcher launch T-NNN '<command>'`로 HTTP API 기반 세션 시작을 위임합니다. stdout 접두사로 분기합니다: `LAUNCH:`=새 세션에서 실행 중, `INLINE:`=인라인 실행 필요(서버 미기동 또는 재진입 감지), exit code 1=에러. 워크플로우 완료 시 finalization.py(1차, 3초 지연)와 PostToolUse hook(2차, 5초 지연)가 이중으로 HTTP API를 통해 세션을 자동 종료합니다
9. **constraints/criteria 필수**: `0. 완료` 선택 시 constraints 또는 criteria가 누락이거나 10자 미만이면 완료를 거부하고 루프를 계속합니다. Step 1-4(신규 생성)와 Step 1-B-5(편집 루프, 최초/추가 사이클 양쪽) 모두에 적용됩니다. `-o` 단독 모드에서는 편집 루프에 진입하지 않으므로 이 검증이 적용되지 않습니다
10. **Review 분기 흐름**: `-d` 플래그 실행 시 Review 상태 티켓은 간단 검토를 먼저 수행합니다. merge는 사용자의 명시적 "완료" 선택 후에만 실행됩니다. Review 이외 상태에서는 기존과 동일하게 즉시 Done 처리됩니다
11. **품질 검증 (prompt_validator)**: `flow-kanban update-prompt` 호출 시 `prompt_validator.py`가 자동으로 품질 점수를 계산합니다. 검증 대상 태그는 `goal`, `target`, `constraints`, `criteria` 4개이며 공식은 `score = (존재_태그수/4) × 0.6 + (유효_태그수/4) × 0.4`입니다 (유효 = 10자 이상 & `TODO:` 미시작). 임계값은 `QUALITY_THRESHOLD = 0.6`이며 미달 시 프롬프트가 자동 롤백되고 exit code 1로 종료됩니다. `--skip-validation` 플래그를 추가하면 품질 검증을 건너뜁니다. `-o` 모드(채번+용도선택만)와 `-d` 상세 review 생성 시에는 편집 루프를 거치지 않으므로 `--skip-validation`을 사용합니다. `-e` 모드의 편집 루프에서는 constraints/criteria 10자 이상 검증이 선행되므로 품질 검증을 통과할 수 있습니다

## 티켓 관계 링크 가이드

이관 또는 후속 작업으로 새 티켓을 생성한 경우 `flow-kanban link` 명령으로 두 티켓 간 관계를 기록합니다. 관계는 양방향으로 기록됩니다 (원본 티켓과 대상 티켓 양쪽에 자동 반영).

### 언제 사용하나

- 이전 티켓(예: review)에서 이관하여 새 티켓(예: implement)을 생성한 경우
- 선행 작업 완료 후 후속 티켓을 새로 만든 경우

### 관계 유형 및 명령 예시

| 관계 유형 | 명령 | 설명 |
|----------|------|------|
| 이관 (derived-from) | `flow-kanban link T-135 --derived-from T-130` | T-135가 T-130에서 파생된 티켓 |
| 선행 의존 (depends-on) | `flow-kanban link T-135 --depends-on T-130` | T-135가 T-130 완료 후 진행 |
| 후행 차단 (blocks) | `flow-kanban link T-135 --blocks T-140` | T-135가 완료되어야 T-140 진행 가능 |

### 관계 제거

```bash
flow-kanban unlink T-135 --derived-from T-130
```

> 참고: 관계는 양방향으로 기록됩니다. `link` 실행 시 원본 티켓과 대상 티켓 양쪽 XML이 자동으로 업데이트됩니다.

---

## 자연어 매핑 가이드

| 자연어 요청 예시 | 매핑 플래그 | 근거 |
|-----------------|-----------|------|
| "티켓만 열어", "채번해줘", "티켓 하나 만들어" | `-o` | 생성만 요청, 편집 의도 없음 |
| "티켓 만들고 편집할게", "프롬프트 작성하자", "편집할게" | `-e` | 생성 + 편집 의도 명시 (`-oe`는 `-e`의 단축 별칭) |
| "기존 티켓 열어", "3번 티켓 보여줘" | `-o N` | 열람만 요청, 편집 의도 없음 |
| "3번 티켓 수정할게", "기존 티켓 편집하자" | `-e N` | 편집 의도 명시 (`-oe N`도 동일 동작) |
| (이전 대화에서 goal/target/constraints/criteria 모두 추론 가능) | `-oe` | 맥락 충분 → 생성+편집 즉시 처리 |
| (의도 불명확) | `-e` | 기존 동작 호환을 위해 편집 루프 포함 모드를 기본값으로 사용 |

> **판단 원칙**:
> (1) 이전 대화에서 goal/target/constraints/criteria 모두 추론 가능한 경우 → `-oe` (생성+편집 즉시 처리)
> (2) 편집 의도가 명시되었으나 맥락이 부분적인 경우 → `-e` (편집 루프 포함)
> (3) 채번만 필요하거나 편집 의도가 없는 경우 → `-o` (채번+용도선택만)
