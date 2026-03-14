---
description: "티켓 라이프사이클 통합 관리. -o(생성/편집), -s(제출), -d(종료), -c(삭제) 플래그로 티켓 생성부터 완료까지 단일 진입점으로 제어합니다. Use when: 티켓 생성, 티켓 편집, 워크플로우 실행, 티켓 종료, 티켓 삭제를 한 번에 처리할 때"
argument-hint: "[-o|-s|-d|-c] [N] (티켓 라이프사이클 통합 관리)"
---

# wf (Workflow 통합 명령어)

티켓 라이프사이클 전체를 단일 진입점으로 관리합니다. `-o`(Open/생성·편집), `-s`(Submit), `-d`(Done), `-c`(Cancel/삭제) 4개 플래그로 생성부터 종료까지 제어합니다.

## Step 0. 플래그 파싱 및 라우팅

`$ARGUMENTS`에서 플래그와 티켓 번호를 파싱하여 실행 흐름을 결정합니다.

### 파싱 규칙

1. **플래그 추출**: `$ARGUMENTS`에서 `-o`, `-s`, `-d`, `-c` 패턴을 순서대로 검색합니다
2. **티켓 번호 추출**: 숫자 `N`(예: `1`, `12`, `123`)을 파싱하여 3자리 zero-padding 적용 (예: `3` → `T-003`)
3. **플래그와 번호가 모두 없는 경우**: 아래 도움말 메뉴를 출력하고 종료합니다

### 도움말 메뉴 (플래그 미지정 시 출력)

```
`[T-NNN]` : `[WF]` wf 통합 명령어 사용법

| 플래그 | 용도 | 예시 |
|--------|------|------|
| `/wf -o` | 새 티켓 생성 + 프롬프트 작성 | `/wf -o` |
| `/wf -o N` | 기존 티켓 Open + 프롬프트 편집 | `/wf -o 3` |
| `/wf -s N` | 티켓 제출 및 워크플로우 실행 | `/wf -s 3` |
| `/wf -d N` | 티켓 종료 (Done 상태로 이동) | `/wf -d 3` |
| `/wf -c N` | 티켓 삭제 | `/wf -c 3` |

현재 칸반 상태를 확인하려면 `.kanban/` 디렉터리의 XML 티켓 파일을 참조하세요.
```

### 라우팅 규칙

| 조건 | 실행 흐름 |
|------|----------|
| `-o` 플래그 | Step 1 (Open/생성 또는 편집) |
| `-s` 플래그 | Step 2 (Submit/제출) |
| `-d` 플래그 | Step 3 (Done/종료) |
| `-c` 플래그 | Step 4 (Cancel/삭제) |
| 플래그 없음 | 도움말 메뉴 출력 후 종료 |

---

## Step 1. `-o` 플래그: 티켓 생성 또는 편집

`$ARGUMENTS`에서 티켓 번호 `N`의 유무를 확인하여 서브플로우를 분기합니다:

- **번호 없음** (`/wf -o`): Step 1-A (새 티켓 생성) 실행
- **번호 있음** (`/wf -o N`): Step 1-B (기존 티켓 편집) 실행

---

### Step 1-A. 번호 없음: 새 티켓 생성 + 프롬프트 작성

> **칸반 전이**: (없음) → **Open**

새 티켓을 생성하고 대화형으로 프롬프트를 작성합니다. `workflow-wf-prompt` 스킬의 프롬프트 작성 지침을 로드하여 실행합니다.

### 1-1. 빈 티켓 즉시 채번

Bash 도구로 아래 명령을 실행하여 채번 및 빈 제목의 티켓 XML 파일 생성을 처리합니다:

```bash
flow-kanban create "" --command init
```

`flow-kanban create`는 `.kanban/T-NNN.xml` XML 파일을 생성합니다. 생성된 XML은 `<metadata>` 래퍼(number/title/datetime/status/current 포함)와 `<submit>` 래퍼(빈 상태), `<history>` 래퍼(빈 상태)로 구성됩니다. `<current>`는 `<metadata>` 내부에 위치하며 초기값은 0이므로 subnumber는 아직 없는 상태입니다. `--command init`은 초기 생성 용도로 사용되며, 실제 command 값은 용도 선택 후 `flow-kanban add-subnumber`의 `--command` 인자로 결정된다.

빈 제목으로 생성하는 이유: 프롬프트 완료 후 대화 내용을 기반으로 제목을 자동 생성하여 XML `<title>` 요소를 갱신합니다.

stdout에서 T-NNN을 파싱하고 채번 결과를 출력합니다:

```
`[T-NNN]` : `[WF -o]` 티켓 T-NNN을 생성했습니다.
```

### 1-2. 스킬 로드

Read 도구로 `.claude/skills/research-prompt-engineering/SKILL.md`를 읽어 프롬프트 작성 지침을 로드합니다.

### 1-3. 대화 맥락 감지 및 용도 결정

채번은 이미 완료된 상태입니다. 이전 대화 내역에 구체적인 작업 요청(구현 대상, 버그 내용, 리팩토링 목표, 조사 주제 등)이 포함되어 있는지 LLM이 자율적으로 판단한다. 키워드 매칭이 아닌 대화 흐름의 의미적 맥락을 기준으로 한다.

---

#### 트랙 A: 맥락 감지됨

이전 대화에서 작업 요청이 감지된 경우, 아래 추론 요약 블록을 출력합니다:

```
`[T-NNN]` : `[WF -o]` 이전 대화를 기반으로 다음과 같이 추론했습니다:

- 용도: <추론된 용도>
- goal: <추론된 목표>
- target: <추론된 대상>
- context: <이전 대화 핵심 요약>

`1.` 확인 -- 이 내용으로 진행합니다
`2.` 용도 직접 지정 -- 목적 선택 메뉴로 전환합니다
`0.` 취소 -- 생성하지 않고 종료합니다
```

**선택지 처리**:

- `1.` 확인: 추론된 용도·goal·target·context를 Step 1-4의 초기값으로 전달하여 진행합니다. 채번은 이미 완료된 상태이며, 추론된 용도에 해당하는 command 값을 `flow-kanban add-subnumber`의 `--command` 인자로 사용합니다. Step 1-4 루프 진입 시 goal/target/context가 이미 채워진 상태로 시작합니다
- `2.` 용도 직접 지정: 트랙 B(목적 선택 메뉴)로 전환합니다
- `0.` 취소: 티켓 생성 없이 종료합니다

---

#### 트랙 B: 맥락 미감지 또는 fallback

이전 대화에서 작업 요청이 감지되지 않은 경우, 또는 트랙 A에서 `2.` 용도 직접 지정을 선택한 경우:

Read 도구로 `.claude/scripts/data/prompt.txt`를 읽어 메뉴 항목을 로드한 뒤, 각 항목 앞에 번호를 붙여 출력합니다. "0. 완료"는 항상 선택지 맨 마지막에 배치합니다:

```
`[T-NNN]` : `[WF -o]` 어떤 목적의 티켓을 생성할까요?

1. <항목 1>
2. <항목 2>
...
0. 완료 — 생성하지 않고 종료합니다

번호 또는 자유 텍스트를 입력하세요:
```

**용도→command 매핑**:

| 용도 | command 값 |
|------|-----------|
| 연구 | `research` |
| 구현 | `implement` |
| 버그수정 | `implement` |
| 리팩토링 | `implement` |
| 아키텍처설계 | `implement` |
| 리뷰 | `review` |

사용자가 번호를 선택하면 용도가 결정됩니다. 채번은 이미 완료된 상태이며, 선택된 용도에 해당하는 command 값을 `flow-kanban add-subnumber`의 `--command` 인자로 사용합니다. 사용자가 "0. 완료"를 선택하면 티켓 생성 없이 종료합니다.

### 1-4. 대화형 프롬프트 작성 루프

선택한 용도에 해당하는 프롬프트 템플릿을 Read 도구로 로드합니다:

**용도→템플릿 섹션 매핑**:

| 용도 | 로드할 파일 | 해당 섹션 |
|------|-----------|---------|
| 구현, 아키텍처설계 | `.claude/skills/research-prompt-engineering/references/prompt-templates.md` | `## 1. 기능 구현` 또는 `## 6. 아키텍처 설계` |
| 버그수정 | `.claude/skills/research-prompt-engineering/references/prompt-templates.md` | `## 2. 버그 수정` |
| 리팩토링 | `.claude/skills/research-prompt-engineering/references/prompt-templates.md` | `## 3. 리팩토링` |
| 리뷰 | `.claude/skills/research-prompt-engineering/references/prompt-templates.md` | `## 4. 코드 리뷰` |
| 연구 | `.claude/skills/research-prompt-engineering/references/prompt-templates.md` | `## 5. 연구 조사` |

로드한 템플릿의 XML 태그 버전(`<goal>`, `<target>`, `<constraints>`, `<criteria>`, `<context>`)을 구조화된 질문 형태로 사용자에게 제시합니다. 루프의 목적은 "정보 수집"이 아닌 **"프롬프트 개선"**입니다 — 이미 생성된 티켓의 프롬프트 내용을 반복적으로 다듬어 완성도를 높입니다.

매 턴 아래 순서로 처리합니다:

**1단계 - 사용자 입력 수신 및 안내:**

현재 프롬프트 상태를 반영한 안내와 개선 제안을 출력합니다 (접두사: `[T-NNN]` : `[WF -o]`). 사용자 입력을 기반으로 goal, target, constraints, criteria, context 정보를 개선합니다.

**2단계 - 내부 모호성 분석 (사용자에게 노출하지 않음):**

로드한 `research-prompt-engineering` 스킬의 모호성 분석 체크리스트 5항목과 자가 점검 체크리스트 7항목을 내부적으로 재평가합니다. 분석 결과는 다음 턴의 대화 방향 결정에만 사용하며, 체크리스트 항목이나 점수를 사용자에게 직접 출력하지 않습니다.

**3단계 - 웹검색/코드탐색 자율 수행:**

대화 맥락에서 코드베이스 탐색이나 웹검색이 도움된다고 판단하면 자율적으로 수행합니다. 수행 여부를 사용자에게 사전에 묻지 않습니다. 수행 결과는 대화 중 자연스럽게 요약하여 prompt 개선에 반영합니다.

| 감지 신호 | 수행 액션 | 사용 도구 |
|----------|----------|----------|
| 함수, 모듈, 파일, 클래스, 컴포넌트, 변수, 메서드 | 코드베이스 탐색 | Grep, Glob, Read |
| API, 프레임워크, 패키지, 버전, 라이브러리, SDK, 외부 서비스 | 웹검색 | WebSearch, WebFetch |
| 양쪽 신호 모두 감지 | 코드베이스 탐색 + 웹검색 모두 수행 | Grep, Glob, Read, WebSearch, WebFetch |

> 탐색/검색 결과는 사용자에게 핵심을 요약하여 제안·선택지 형태로 제공합니다. 예: "코드베이스를 확인한 결과 `src/auth/token.ts`에 유사한 패턴이 있습니다. 이 패턴을 참고할까요?"

**4단계 - G1~G4 게이트 평가 및 동적 선택지 출력:**

G1~G4 게이트 조건 충족 시 완료를 제안합니다. 매 턴 종료 시 아래 순서로 동적 선택지를 반드시 출력합니다:

1. **헤더**: 접두사(`` `[T-NNN]` : `[WF -o]` ``) + 제목
2. **간단 요약**: 현재 프롬프트 진행 상태를 1-2문장으로 요약
3. **동적 선택지**: 대화 맥락을 분석하여 `1.`~`5.` (최대 5개) + `0.` 완료를 생성. 백틱은 선택지 번호(`1.`~`5.`)와 `0.`에만 사용하고 나머지 문구에는 백틱을 사용하지 않는다. `0.` 완료는 항상 선택지 맨 마지막에 배치한다
4. **안내 문구**: "자유 텍스트 입력도 가능합니다." 문구를 선택지 아래에 출력한다

**동적 선택지 생성 원칙**: 선택지는 현재 프롬프트의 미흡한 부분, 개선 가능한 영역, 추가 정보가 필요한 항목 등을 대화 맥락에서 판단하여 매 턴 새롭게 구성한다. goal/target/constraints/criteria/context 필드명을 선택지 텍스트로 직접 노출하지 않는다.

**출력 예시**:
```
`[T-NNN]` : `[WF -o]` 로그인 리다이렉트 버그 수정

에러 핸들링에서 early return 후 리다이렉트가 누락된 상태입니다.

`1.` login.ts의 에러 핸들링에 리다이렉트 추가
`2.` 리다이렉트 전용 미들웨어로 분리
`0.` 완료 — 현재 내용으로 티켓을 완성합니다

자유 텍스트 입력도 가능합니다.
```

- 사용자 "0. 완료" 선택 시 아래 순서로 처리:
  0. **constraints/criteria 필수 검증**: constraints 또는 criteria가 누락이거나 10자 미만이면 아래 메시지를 출력하고 루프를 계속합니다 (이하 단계를 실행하지 않음):
     ```
     `[T-NNN]` : `[WF -o]` constraints 또는 criteria가 누락되었거나 내용이 부족합니다(10자 이상 필요). 보강 후 다시 완료를 선택하세요.
     ```
  1. 대화 내용을 기반으로 티켓 제목을 자동 생성합니다 (20자 이내, 한국어, 동사형). 예: "로그인 리다이렉트 버그 수정", "비동기 HTTP 클라이언트 비교"
  2. Bash 도구로 `flow-kanban add-subnumber` 호출하여 subnumber 추가:
     ```bash
     flow-kanban add-subnumber T-NNN --command <command값> --goal "<goal>" --target "<target>" --constraints "<constraints>" --criteria "<criteria>" --context "<context>"
     ```
     `--command` 인자는 subnumber 직하(`<prompt>` 래퍼 밖)의 `<command>` 태그에 저장됩니다. subnumber는 `<submit>` 래퍼(active=true) 또는 `<history>` 래퍼(비활성) 내부에 위치합니다. `--goal`, `--target`, `--constraints`, `--criteria`, `--context` 인자는 subnumber 내부의 `<prompt>` 래퍼 안 태그에 저장됩니다.
  4. Read 도구로 갱신된 XML 파일을 읽어 subnumber 내용 확인 후 Step 1-5로 진행

> `<command>` 값은 1-3에서 결정된 용도에 해당하는 값을 사용합니다. `flow-kanban add-subnumber`의 `--command` 인자에 동일 값을 전달합니다. context 값이 없는 경우 해당 인자를 생략합니다.

### 1-5. 완료 메시지 출력

```
T-NNN 티켓이 생성되었습니다. (파일: .kanban/T-NNN.xml)

## 후속 커맨드 안내

| 목적 | 커맨드 | 설명 |
|------|--------|------|
| 제출 | `/wf -s N` | <command> 태그에 따라 자동 라우팅 ← 권장 |
| 편집 | `/wf -o N` | 티켓 내용을 추가로 수정합니다 |
| 종료 | `/wf -d N` | 티켓을 Done 상태로 종료합니다 |

> 참고: 여러 워크플로우를 순차 실행하려면 `<command>` 태그에 `research>implement>review` 형식으로 체인을 지정할 수 있습니다.
```

---

### Step 1-B. 번호 있음: 기존 티켓 편집

> **칸반 전이**: Done → **Open** (복원) / Review/In Progress → **Open** (자동 복귀) / Open → Open (유지) → 편집 완료 후 Open 유지

기존 티켓 파일을 로드하여 대화형으로 내용을 편집합니다. `workflow-wf-prompt` 스킬의 편집 지침을 따릅니다. `<command>` 태그 갱신이 허용됩니다.

### 1-B-1. 티켓 파일 로드

Glob 도구로 `.kanban/T-NNN.xml` 패턴을 검색하여 현재 상태 파일을 탐색합니다.

**파일 발견 시**: XML `<status>` 요소에서 현재 칸반 상태를 판별합니다:

| `<status>` 값 | 칸반 상태 |
|--------------|---------|
| `Open` | Open |
| `In Progress` | In Progress |
| `Review` | Review |

**파일 미발견 시**: `.kanban/done/T-NNN.xml`을 확인합니다:
- 존재하면: Bash로 `mv ".kanban/done/T-NNN.xml" ".kanban/T-NNN.xml"` 실행 후 `flow-kanban move T-NNN open` 실행하여 Open으로 복원
- 복원 완료 후 안내 메시지 출력:
  ```
  `[T-NNN]` : `[WF -o]` T-NNN 티켓을 Done에서 Open으로 복원했습니다.
  ```
- 어디에서도 찾지 못한 경우: 에러 출력 후 종료
  ```
  T-NNN 티켓 파일을 찾을 수 없습니다.
  ```

### 1-B-2. Review/In Progress 상태 자동 Open 복귀

현재 상태가 `In Progress` 또는 `Review`인 경우, 사용자 확인 없이 즉시 Open 복귀를 수행합니다:

```bash
flow-kanban move T-NNN open
```

파일은 `.kanban/T-NNN.xml`로 고정되어 있으므로 파일 이동은 불필요합니다.

복귀 완료 후 안내 메시지를 출력합니다:

```
`[T-NNN]` : `[WF -o]` T-NNN 티켓을 Open으로 되돌렸습니다. (이전 상태: <In Progress|Review>)
```

Open 상태이면 상태 변경 없이 즉시 편집 루프로 진입합니다.

### 1-B-3. 현재 티켓 내용 표시

```
## 현재 T-NNN.xml 내용

<티켓 파일 내용 전체>
```

### 1-B-4. 스킬 로드

Read 도구로 `.claude/skills/research-prompt-engineering/SKILL.md`를 읽어 프롬프트 작성 지침을 로드합니다.

### 1-B-5. 대화형 편집 루프

티켓 XML에서 `<current>` 값을 확인하여 사이클 분기를 결정합니다. 대화 루프의 매 턴은 Step 1-4와 동일한 처리 순서(1단계~4단계)를 따릅니다:

- **1단계**: 사용자 입력 수신 및 안내 (접두사: `[T-NNN]` : `[WF -o]`)
- **2단계**: 내부 모호성 분석 (사용자에게 비노출)
- **3단계**: 웹검색/코드탐색 자율 수행 (Step 1-4의 감지 신호 테이블 참조)
- **4단계**: G1~G4 게이트 평가 및 동적 선택지 출력 — Step 1-4와 동일한 구조(헤더, 간단 요약, 동적 선택지 `1.`~`5.` + `0.` 완료, 안내 문구)를 따르되 접두사는 `[T-NNN]` : `[WF -o]`를 사용한다

**최초 사이클 (`<current>` 값이 0인 경우)**:
- 아직 subnumber가 없으므로 새 워크플로우를 정의하는 대화를 진행합니다
- 사용자 "0. 완료" 선택 시 constraints/criteria 필수 검증 후 `flow-kanban add-subnumber` 호출하여 첫 번째 subnumber를 생성합니다:
  - **constraints/criteria 필수 검증**: constraints 또는 criteria가 누락이거나 10자 미만이면 아래 메시지를 출력하고 루프를 계속합니다 (add-subnumber를 실행하지 않음):
    ```
    `[T-NNN]` : `[WF -o]` constraints 또는 criteria가 누락되었거나 내용이 부족합니다(10자 이상 필요). 보강 후 다시 완료를 선택하세요.
    ```
  - 검증 통과 시:
    ```bash
    flow-kanban add-subnumber T-NNN --command <command값> --goal "<goal>" --target "<target>" --constraints "<constraints>" --criteria "<criteria>" --context "<context>"
    ```

**추가 사이클 (`<current>` 값이 1 이상인 경우)**:
- 이전 사이클이 완료된 후 새 사이클을 시작하는 상황입니다
- 현재 `<subnumber id="N">` 내용을 표시하여 이전 작업 맥락을 제공합니다
- 새 사이클의 goal, target, constraints, criteria, context를 수집하는 대화를 진행합니다
- 사용자 "0. 완료" 선택 시 constraints/criteria 필수 검증 후 `flow-kanban add-subnumber` 호출하여 다음 subnumber를 추가합니다:
  - **constraints/criteria 필수 검증**: constraints 또는 criteria가 누락이거나 10자 미만이면 아래 메시지를 출력하고 루프를 계속합니다 (add-subnumber를 실행하지 않음):
    ```
    `[T-NNN]` : `[WF -o]` constraints 또는 criteria가 누락되었거나 내용이 부족합니다(10자 이상 필요). 보강 후 다시 완료를 선택하세요.
    ```
  - 검증 통과 시:
    ```bash
    flow-kanban add-subnumber T-NNN --command <command값> --goal "<goal>" --target "<target>" --constraints "<constraints>" --criteria "<criteria>" --context "<context>"
    ```

**`<command>` 태그 갱신 정책**: `-o NNN` 편집 시 `<command>` 갱신이 허용됩니다. 사용자가 명시적으로 용도를 변경하려는 경우 `flow-kanban add-subnumber`의 `--command` 인자에 새 값을 전달합니다.

> `context` 값이 없는 경우 해당 인자를 생략합니다.

### 1-B-6. 완료 메시지 출력

```
T-NNN 티켓이 업데이트되었습니다.

## 후속 커맨드 안내

| 목적 | 커맨드 | 설명 |
|------|--------|------|
| 제출 | `/wf -s N` | <command> 태그에 따라 자동 라우팅 ← 권장 |
| 종료 | `/wf -d N` | 티켓을 Done 상태로 종료합니다 |
```

---

## Step 2. `-s` 플래그: 티켓 제출 및 워크플로우 실행

> **칸반 전이**: Open → **In Progress** (wf 내부에서 워크플로우 스킬 로드 후 처리)

티켓의 `<command>` 태그를 읽어 해당하는 `workflow-wf-*` 스킬을 직접 로드하고 워크플로우를 실행합니다.

### tmux 환경 분기

Bash 도구로 아래 명령을 실행합니다:

```bash
flow-tmux launch T-NNN '/wf -s N'
```

**stdout 접두사별 분기**:

- **`LAUNCH:`** (새 윈도우에서 실행 중): 복귀 메시지를 출력합니다 (2-1 이후 로직을 실행하지 않음):
  ```
  T-NNN 워크플로우를 새 tmux 윈도우에서 실행합니다.
  ```
- **`INLINE:`** (인라인 실행 필요 — 비tmux 환경 또는 재진입 감지): **아래 2-1~2-5 로직을 그대로 실행합니다**
- **exit code 1** (에러 — 타임아웃 등): 에러 메시지를 출력하고 종료합니다:
  ```
  T-NNN 워크플로우 실행 실패. (flow-tmux 에러)
  ```

### 2-1. 티켓 번호 검증

`$ARGUMENTS`에서 숫자 `N`을 파싱합니다. 티켓 번호가 없으면 아래 에러를 출력하고 종료합니다:

```
-s 플래그는 티켓 번호(N)를 반드시 지정해야 합니다. 예: /wf -s 3
```

### 2-2. 티켓 파일 로드

Glob 도구로 `.kanban/T-NNN.xml` 패턴을 검색하여 현재 상태 파일을 탐색합니다.

파일을 찾지 못한 경우 에러 출력 후 종료:
```
T-NNN 티켓 파일을 찾을 수 없습니다. (.kanban/T-NNN.xml)
```

### 2-3. `<command>` 태그 파싱

로드된 티켓 XML 파일을 XML 파서로 읽어 `<metadata>` 내부의 `<current>` 요소 값을 먼저 확인합니다.

- `<current>` 값이 `0` 또는 존재하지 않는 경우 (subnumber 없음): 에러 출력 후 종료
  ```
  T-NNN 티켓에 워크플로우가 정의되지 않았습니다. /wf -o N으로 먼저 작성하세요.
  ```

`<current>` 값이 1 이상인 경우, 해당 ID의 `<subnumber id="N">` 요소를 찾아 직하의 `<command>` 자식 요소를 읽습니다. `<command>`는 `<prompt>` 래퍼 밖 subnumber 직하에 위치합니다.

**체인 command 파싱**: `<command>` 값에 `>` 구분자가 포함된 경우 체인 표기(`research>implement>review`)로 처리합니다.

- `>` 기준으로 split하여 각 세그먼트를 추출합니다
- 첫 번째 세그먼트를 현재 실행할 command로 사용합니다
- 각 세그먼트가 유효한 command인지 모두 검증합니다 (`implement`, `research`, `review`)
- 유효하지 않은 세그먼트가 하나라도 있으면 에러 출력 후 종료:
  ```
  T-NNN 티켓의 <command> 체인에 유효하지 않은 세그먼트가 있습니다: XXX (허용: implement, research, review)
  /wf -o N 으로 티켓 용도를 다시 지정하세요.
  ```
- 단일 command(`implement`)는 기존 동작과 동일하게 처리합니다 (하위 호환)

**단일 command 검증** (`>` 구분자 없는 경우):

- 유효한 값: `implement`, `research`, `review`
- `<command>` 요소가 없는 경우:
  ```
  T-NNN 티켓에 <command> 태그가 없습니다.
  /wf -o N 으로 티켓 용도를 먼저 지정하세요.
  ```
- `<command>` 값이 유효하지 않은 경우:
  ```
  T-NNN 티켓의 <command>XXX</command> 값이 유효하지 않습니다. (허용: implement, research, review)
  /wf -o N 으로 티켓 용도를 다시 지정하세요.
  ```

### 2-4. 실행 안내 출력

단일 command인 경우:
```
T-NNN 티켓을 <command> 워크플로우로 실행합니다.
```

체인 command인 경우 (예: `research>implement>review`의 1번째 스테이지 실행 시):
```
T-NNN 티켓을 <첫번째 세그먼트> 워크플로우로 실행합니다. (체인: research > implement > review, 1/3 스테이지)
```

### 2-5. 워크플로우 스킬 로드 및 실행

Read 도구로 현재 실행할 command(체인인 경우 **첫 번째 세그먼트**)에 해당하는 wf 스킬을 직접 로드한 뒤 해당 스킬의 지침을 따라 워크플로우를 실행합니다. 체인 여부와 무관하게 기존 라우팅 매핑 테이블을 그대로 사용합니다.

**자동 라우팅 매핑**:

| `<command>` 값 (또는 체인의 첫 번째 세그먼트) | 로드할 스킬 파일 |
|---------------|----------------|
| `implement` | `.claude/skills/workflow-wf-implement/SKILL.md` |
| `research` | `.claude/skills/workflow-wf-research/SKILL.md` |
| `review` | `.claude/skills/workflow-wf-review/SKILL.md` |

> **참고**: 워크플로우 완료 후 `flow-kanban move T-NNN review`로 자동 전이됩니다 (`workflow-wf-submit` 스킬 지침에서 처리). 다음 사이클을 실행하려면 `/wf -o N`으로 프롬프트를 수정하거나 `/wf -d N`으로 티켓을 종료하세요. 체인 command인 경우 finalization.py가 완료 후 자동으로 다음 스테이지를 새 tmux 세션에서 실행합니다.

---

## Step 3. `-d` 플래그: 티켓 종료

> **칸반 전이**: Any → **Done**

지정한 티켓을 Done 상태로 종료합니다.

### 3-1. 티켓 번호 검증

`$ARGUMENTS`에서 숫자 `N`을 파싱합니다. 티켓 번호가 없으면 아래 에러를 출력하고 종료합니다:

```
-d 플래그는 티켓 번호(N)를 반드시 지정해야 합니다. 예: /wf -d 3
```

### 3-2. Done 처리 실행

Bash 도구로 아래 명령을 실행합니다:

```bash
flow-kanban done T-NNN
```

**exit code별 처리**:

- **exit code 1, "찾을 수 없습니다" 메시지**: 에러 출력 후 종료
  ```
  T-NNN 티켓을 찾을 수 없습니다.
  ```
- **exit code 1, "이미 Done" 메시지**: 안내 출력 후 종료
  ```
  T-NNN은 이미 Done 상태입니다.
  ```
- **exit code 0**: 파일 이동이 완료된 것이므로 3-3으로 진행합니다

> `flow-kanban done`은 티켓 XML의 상태 갱신과 파일 이동(`.kanban/T-NNN.xml` → `.kanban/done/T-NNN.xml`)을 내부적으로 처리합니다. 별도의 Write 또는 mv 명령이 필요하지 않습니다.

### 3-3. 완료 메시지 출력

```
T-NNN 티켓이 Done 상태로 종료되었습니다. (파일: .kanban/done/T-NNN.xml)
```

---

## Step 4. `-c` 플래그: 티켓 삭제

> **칸반 전이**: Any → **(삭제)**

지정한 티켓 XML 파일을 완전히 삭제합니다. `-d`(Done)와 달리 히스토리를 보존하지 않습니다.

### 4-1. 티켓 번호 검증

`$ARGUMENTS`에서 숫자 `N`을 파싱합니다. 티켓 번호가 없으면 아래 에러를 출력하고 종료합니다:

```
-c 플래그는 티켓 번호(N)를 반드시 지정해야 합니다. 예: /wf -c 3
```

### 4-2. 티켓 파일 탐색

Glob 도구로 `.kanban/T-NNN.xml` 패턴을 검색합니다. 파일 미발견 시 `.kanban/done/T-NNN.xml`도 확인합니다.

어디에서도 찾지 못한 경우:
```
T-NNN 티켓 파일을 찾을 수 없습니다.
```

### 4-3. 삭제 실행

Bash 도구로 아래 명령을 실행합니다:

```bash
flow-tmux launch T-NNN '/wf -c N'
```

**stdout 접두사별 분기**:

- **`LAUNCH:`** (새 윈도우에서 실행 중): 복귀 메시지를 출력하고 종료합니다 (4-4 이후 로직을 실행하지 않음):
  ```
  T-NNN 티켓 삭제를 새 tmux 윈도우에서 실행합니다.
  ```
- **`INLINE:`** (인라인 실행 필요 — 비tmux 환경 또는 재진입 감지): Bash 도구로 `flow-kanban delete T-NNN`을 직접 실행한 뒤 4-4로 진행합니다
- **exit code 1** (에러 — 타임아웃 등): 에러 메시지를 출력하고 종료합니다:
  ```
  T-NNN 티켓 삭제 실행 실패. (flow-tmux 에러)
  ```

### 4-4. 완료 메시지 출력

인라인 실행(비tmux 환경 또는 T-* 윈도우 재진입)인 경우 삭제 결과를 직접 출력합니다:

```
T-NNN 티켓이 삭제되었습니다.
```

---

## 칸반 상태 전이 요약

| 플래그 | 실행 전 상태 | 실행 후 상태 | 전이 명령 |
|--------|------------|------------|---------|
| `-o` (번호 없음) | (없음) | Open | `flow-kanban create "" --command init` |
| `-o N` | Done | Open (복원) | `mv .kanban/done/T-NNN.xml .kanban/T-NNN.xml` + `flow-kanban move T-NNN open` |
| `-o N` | Review/In Progress | Open (자동 복귀) | `flow-kanban move T-NNN open` |
| `-o N` | Open | Open (유지) | — |
| `-s` | Open | In Progress | `flow-tmux launch T-NNN '/wf -s N'` (LAUNCH: 새 윈도우 실행, INLINE: 인라인 실행, exit 1: 에러) |
| `-s` (완료 후) | In Progress | Review | `flow-kanban move T-NNN review` (workflow-wf-submit 처리) |
| `-d` | Any | Done | `flow-kanban done T-NNN` |
| `-c` | Any | (삭제) | `flow-tmux launch T-NNN '/wf -c N'` (LAUNCH: 새 윈도우 실행, INLINE: `flow-kanban delete T-NNN` 인라인 실행, exit 1: 에러) |

## subnumber 생명주기

티켓 XML 내부의 `<subnumber>` 요소는 워크플로우 실행 사이클마다 하나씩 추가됩니다. 전체 흐름은 다음과 같습니다:

| 단계 | 플래그 | subnumber 상태 | 수행 명령 |
|------|--------|---------------|---------|
| 티켓 생성 직후 | `-o` | `<current>0</current>` (subnumber 없음) | `flow-kanban create "" --command init` |
| 워크플로우 정의 | `-o` 완료 또는 `-o NNN` | subnumber N 추가, `<current>N</current>` 갱신 | `flow-kanban add-subnumber T-NNN --command ... --goal ... --target ...` |
| 워크플로우 실행 완료 | `-s` 후처리 | subnumber N에 workdir/plan/work/report 기록 | `flow-kanban update-subnumber T-NNN --id N --workdir ... --plan ... --work ... --report ...` |
| 다음 사이클 시작 | `-o NNN` (추가 사이클) | subnumber N+1 추가, `<current>N+1</current>` 갱신 | `flow-kanban add-subnumber T-NNN --command ... --goal ... --target ...` |
| 티켓 종료 | `-d` | 변경 없음 (히스토리 보존) | `flow-kanban done T-NNN` |

## 주의사항

1. **단일 진입점**: 티켓 라이프사이클 전체를 `/wf` 하나로 관리합니다. `/wf`가 유일한 티켓 관리 진입점입니다
2. **자동 Open 복귀**: `-o NNN` 플래그로 Review/In Progress 티켓에 접근 시 사용자 확인 없이 Open으로 자동 복귀합니다
3. **`<command>` 태그 정책**: `-o` 생성 시 설정된 값을 기본 보존하되, `-o NNN` 편집 시 명시적 변경이 허용됩니다
4. **Bash 도구 사용**: 칸반 상태 전이 및 파일 이동이 필요한 Step(1-1, 1-B-1, 1-B-2, 2-5, 3-2)에서 허용합니다
5. **AskUserQuestion 미사용**: 모든 사용자 입력은 텍스트 메뉴 출력 후 자유 입력으로 수신합니다. 접두사는 `` `[T-NNN]` : `[WF -플래그]` `` 형식을 사용합니다
6. **Task 도구 호출 금지**: 이 명령어는 비워크플로우 독립 명령어이므로 서브에이전트를 호출하지 않습니다
7. **wf 스킬 직접 로드**: `-s` 플래그 실행 시 SlashCommand/Skill 도구가 아닌 Read 도구로 해당 스킬 파일을 직접 로드하여 실행합니다
8. **독립 세션 실행**: `-s`와 `-c` 플래그는 `flow-tmux launch T-NNN '<command>'`로 새 윈도우 생성+폴링+명령전송을 위임합니다. stdout 접두사로 분기합니다: `LAUNCH:`=새 윈도우에서 실행 중, `INLINE:`=인라인 실행 필요(비tmux 환경 또는 재진입 감지), exit code 1=에러(타임아웃 등). 워크플로우 완료 시 finalization.py Step 5(1차, 3초 지연)와 PostToolUse hook(2차, 5초 지연)가 이중으로 tmux 윈도우를 자동 종료합니다. start_new_session+sleep 지연으로 flow-claude end 배너 출력이 보장됩니다. 중복 윈도우 체크, 재진입 방지, 폴링 타임아웃 등 상세는 flow-tmux 내부에서 처리합니다
9. **constraints/criteria 필수**: `0. 완료` 선택 시 constraints 또는 criteria가 누락이거나 10자 미만이면 완료를 거부하고 루프를 계속합니다. 이는 Step 1-4(신규 생성)와 Step 1-B-5(편집 루프, 최초/추가 사이클 양쪽) 모두에 적용됩니다
