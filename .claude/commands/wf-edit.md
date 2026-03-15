# wf-edit.md — Step 1: -e / -oe 플래그 처리

`-oe`는 `-e`의 단축 별칭으로 동일 로직을 실행합니다. 두 플래그는 완전히 동일한 처리 흐름을 따르며, `-oe`는 하위호환을 위해 유지됩니다.

`$ARGUMENTS`에서 플래그와 티켓 번호 `N`의 유무를 확인하여 서브플로우를 분기합니다:

| 플래그 | 번호 유무 | 실행 흐름 |
|--------|---------|----------|
| `-e` | 없음 | Step 1-A-e: 새 티켓 생성 + 프롬프트 편집 루프 |
| `-e` | 있음 | Step 1-B-e: 기존 티켓 편집 루프 |
| `-oe` | 없음 | Step 1-A-e와 동일 (하위호환) |
| `-oe` | 있음 | Step 1-B-e와 동일 (하위호환) |

---

## Step 1-A-e. `-e` 번호 없음: 새 티켓 생성 + 프롬프트 편집 루프

> **칸반 전이**: (없음) → **Open**

새 티켓을 생성하고 대화형으로 프롬프트를 작성합니다.

### 1-1. 빈 티켓 즉시 채번

Bash 도구로 아래 명령을 실행합니다:

```bash
flow-kanban create "" --command init
```

`flow-kanban create`는 `.kanban/T-NNN.xml` XML 파일을 생성합니다. `--command init`은 초기 생성 용도로 사용되며, 실제 command 값은 용도 선택 후 `flow-kanban add-subnumber`의 `--command` 인자로 결정됩니다.

stdout에서 T-NNN을 파싱하고 채번 결과를 출력합니다:

```
`[T-NNN]` : `[WF -e]` 티켓 T-NNN을 생성했습니다.
```

### 1-2. 스킬 로드

Read 도구로 `.claude/skills/research-prompt-engineering/SKILL.md`를 읽어 프롬프트 작성 지침을 로드합니다.

### 1-3. 대화 맥락 감지 및 용도 결정

채번은 이미 완료된 상태입니다. 이전 대화 내역에 구체적인 작업 요청이 포함되어 있는지 LLM이 자율적으로 판단합니다.

---

#### 트랙 A: 맥락 감지됨

이전 대화에서 작업 요청이 감지된 경우:

```
`[T-NNN]` : `[WF -e]` 이전 대화를 기반으로 다음과 같이 추론했습니다:

- 용도: <추론된 용도>
- goal: <추론된 목표>
- target: <추론된 대상>
- context: <이전 대화 핵심 요약>

`1.` 확인 -- 이 내용으로 진행합니다
`2.` 용도 직접 지정 -- 목적 선택 메뉴로 전환합니다
`0.` 취소 -- 생성하지 않고 종료합니다
```

**선택지 처리**:

- `1.` 확인: 추론된 용도·goal·target·context를 Step 1-4의 초기값으로 전달하여 진행합니다
- `2.` 용도 직접 지정: 트랙 B(목적 선택 메뉴)로 전환합니다
- `0.` 취소: 티켓 생성 없이 종료합니다

---

#### 트랙 B: 맥락 미감지 또는 fallback

Read 도구로 `.claude/prompt/prompt.txt`를 읽어 메뉴 항목을 로드한 뒤 출력합니다:

```
`[T-NNN]` : `[WF -e]` 어떤 목적의 티켓을 생성할까요?

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

사용자가 번호를 선택하면 용도가 결정됩니다. 사용자가 "0. 완료"를 선택하면 티켓 생성 없이 종료합니다.

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

로드한 템플릿의 XML 태그 버전(`<goal>`, `<target>`, `<constraints>`, `<criteria>`, `<context>`)을 구조화된 질문 형태로 사용자에게 제시합니다. 루프의 목적은 "정보 수집"이 아닌 **"프롬프트 개선"**입니다.

매 턴 아래 순서로 처리합니다:

**1단계 - 사용자 입력 수신 및 안내:**

현재 프롬프트 상태를 반영한 안내와 개선 제안을 출력합니다 (접두사: `[T-NNN]` : `[WF -e]`). 사용자 입력을 기반으로 goal, target, constraints, criteria, context 정보를 개선합니다.

**2단계 - 내부 모호성 분석 (사용자에게 노출하지 않음):**

로드한 `research-prompt-engineering` 스킬의 모호성 분석 체크리스트 5항목과 자가 점검 체크리스트 7항목을 내부적으로 재평가합니다.

**3단계 - 웹검색/코드탐색 자율 수행:**

| 감지 신호 | 수행 액션 | 사용 도구 |
|----------|----------|----------|
| 함수, 모듈, 파일, 클래스, 컴포넌트, 변수, 메서드 | 코드베이스 탐색 | Grep, Glob, Read |
| API, 프레임워크, 패키지, 버전, 라이브러리, SDK, 외부 서비스 | 웹검색 | WebSearch, WebFetch |
| 양쪽 신호 모두 감지 | 코드베이스 탐색 + 웹검색 모두 수행 | Grep, Glob, Read, WebSearch, WebFetch |

**4단계 - G1~G4 게이트 평가 및 동적 선택지 출력:**

G1~G4 게이트 조건 충족 시 완료를 제안합니다. 매 턴 종료 시 아래 순서로 동적 선택지를 반드시 출력합니다:

1. **헤더**: 접두사(`` `[T-NNN]` : `[WF -e]` ``) + 제목
2. **간단 요약**: 현재 프롬프트 진행 상태를 1-2문장으로 요약
3. **동적 선택지**: 대화 맥락을 분석하여 `1.`~`5.` (최대 5개) + `0.` 완료를 생성
4. **안내 문구**: "자유 텍스트 입력도 가능합니다." 문구를 선택지 아래에 출력

**출력 예시**:
```
`[T-NNN]` : `[WF -e]` 로그인 리다이렉트 버그 수정

에러 핸들링에서 early return 후 리다이렉트가 누락된 상태입니다.

`1.` login.ts의 에러 핸들링에 리다이렉트 추가
`2.` 리다이렉트 전용 미들웨어로 분리
`0.` 완료 — 현재 내용으로 티켓을 완성합니다

자유 텍스트 입력도 가능합니다.
```

- 사용자 "0. 완료" 선택 시 아래 순서로 처리:
  0. **constraints/criteria 필수 검증**: constraints 또는 criteria가 누락이거나 10자 미만이면 아래 메시지를 출력하고 루프를 계속합니다 (이하 단계를 실행하지 않음):
     ```
     `[T-NNN]` : `[WF -e]` constraints 또는 criteria가 누락되었거나 내용이 부족합니다(10자 이상 필요). 보강 후 다시 완료를 선택하세요.
     ```
  1. 대화 내용을 기반으로 티켓 제목을 자동 생성합니다 (20자 이내, 한국어, 동사형)
  2. Bash 도구로 `flow-kanban add-subnumber` 호출하여 subnumber 추가:
     ```bash
     flow-kanban add-subnumber T-NNN --command <command값> --goal "<goal>" --target "<target>" --constraints "<constraints>" --criteria "<criteria>" --context "<context>"
     ```
  3. Read 도구로 갱신된 XML 파일을 읽어 subnumber 내용 확인 후 Step 1-5로 진행

> context 값이 없는 경우 해당 인자를 생략합니다.

### 1-5. 완료 메시지 출력

```
T-NNN 티켓이 생성되었습니다. (파일: .kanban/T-NNN.xml)

## 후속 커맨드 안내

| 목적 | 커맨드 | 설명 |
|------|--------|------|
| 제출 | `/wf -s N` | <command> 태그에 따라 자동 라우팅 ← 권장 |
| 편집 | `/wf -e N` | 티켓 내용을 추가로 수정합니다 |
| 종료 | `/wf -d N` | 티켓을 Done 상태로 종료합니다 |

> 참고: 여러 워크플로우를 순차 실행하려면 `<command>` 태그에 `research>implement>review` 형식으로 체인을 지정할 수 있습니다.
```

---

## Step 1-B-e. `-e` 번호 있음: 기존 티켓 편집 루프

> **칸반 전이**: Done → **Open** (복원) / Review/In Progress → **Open** (자동 복귀) / Open → Open (유지)

기존 티켓 파일을 로드하여 대화형으로 내용을 편집합니다.

### 1-B-1. 티켓 파일 로드

Glob 도구로 `.kanban/T-NNN.xml` 패턴을 검색합니다.

**파일 발견 시**: XML `<status>` 요소에서 현재 칸반 상태를 판별합니다.

**파일 미발견 시**: `.kanban/done/T-NNN.xml`을 확인합니다:
- 존재하면: Bash로 `mv ".kanban/done/T-NNN.xml" ".kanban/T-NNN.xml"` 실행 후 `flow-kanban move T-NNN open` 실행:
  ```
  `[T-NNN]` : `[WF -e]` T-NNN 티켓을 Done에서 Open으로 복원했습니다.
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

복귀 완료 후 안내 메시지를 출력합니다:

```
`[T-NNN]` : `[WF -e]` T-NNN 티켓을 Open으로 되돌렸습니다. (이전 상태: <In Progress|Review>)
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

- **1단계**: 사용자 입력 수신 및 안내 (접두사: `[T-NNN]` : `[WF -e]`)
- **2단계**: 내부 모호성 분석 (사용자에게 비노출)
- **3단계**: 웹검색/코드탐색 자율 수행 (Step 1-4의 감지 신호 테이블 참조)
- **4단계**: G1~G4 게이트 평가 및 동적 선택지 출력 — Step 1-4와 동일한 구조(헤더, 간단 요약, 동적 선택지 `1.`~`5.` + `0.` 완료, 안내 문구)를 따르되 접두사는 `[T-NNN]` : `[WF -e]`를 사용한다

**최초 사이클 (`<current>` 값이 0인 경우)**:
- 아직 subnumber가 없으므로 새 워크플로우를 정의하는 대화를 진행합니다
- 사용자 "0. 완료" 선택 시 constraints/criteria 필수 검증 후 `flow-kanban add-subnumber` 호출하여 첫 번째 subnumber를 생성합니다:
  - **constraints/criteria 필수 검증**: constraints 또는 criteria가 누락이거나 10자 미만이면 아래 메시지를 출력하고 루프를 계속합니다 (add-subnumber를 실행하지 않음):
    ```
    `[T-NNN]` : `[WF -e]` constraints 또는 criteria가 누락되었거나 내용이 부족합니다(10자 이상 필요). 보강 후 다시 완료를 선택하세요.
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
    `[T-NNN]` : `[WF -e]` constraints 또는 criteria가 누락되었거나 내용이 부족합니다(10자 이상 필요). 보강 후 다시 완료를 선택하세요.
    ```
  - 검증 통과 시:
    ```bash
    flow-kanban add-subnumber T-NNN --command <command값> --goal "<goal>" --target "<target>" --constraints "<constraints>" --criteria "<criteria>" --context "<context>"
    ```

**`<command>` 태그 갱신 정책**: `-e NNN` 편집 시 `<command>` 갱신이 허용됩니다. 사용자가 명시적으로 용도를 변경하려는 경우 `flow-kanban add-subnumber`의 `--command` 인자에 새 값을 전달합니다.

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
