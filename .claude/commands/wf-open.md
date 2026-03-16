# Step 1. `-o` 플래그: 티켓 생성 또는 열람

`$ARGUMENTS`에서 플래그와 티켓 번호 `N`의 유무를 확인하여 서브플로우를 분기합니다:

| 플래그 | 번호 유무 | 실행 흐름 |
|--------|---------|----------|
| `-o` | 없음 | Step 1-A-o: 새 티켓 생성 (채번+용도선택만, 편집 루프 미진입) |
| `-o` | 있음 | Step 1-B-o: 기존 티켓을 Open으로 전이 (즉시 실행, 편집 루프 미진입) |

---

## Step 1-A-o. `-o` 번호 없음: 새 티켓 생성 (채번+용도선택만)

> **칸반 전이**: (없음) → **Open**

새 티켓을 생성하고 채번 및 용도 선택까지만 수행합니다. 편집 루프에 진입하지 않습니다.

### 1-1. 빈 티켓 즉시 채번

Bash 도구로 아래 명령을 실행합니다:

```bash
flow-kanban create "" --command init
```

stdout에서 T-NNN을 파싱하고 채번 결과를 출력합니다:

```
`[T-NNN]` : `[WF -o]` 티켓 T-NNN을 생성했습니다.
```

### 1-2. 대화 맥락 감지 및 용도 결정

이전 대화에서 작업 요청이 감지된 경우 트랙 A, 그렇지 않은 경우 트랙 B를 실행합니다.

---

#### 트랙 A: 맥락 감지됨

이전 대화에서 작업 요청이 감지된 경우:

```
`[T-NNN]` : `[WF -o]` 이전 대화를 기반으로 다음과 같이 추론했습니다:

- 용도: <추론된 용도>
- goal: <추론된 목표>
- target: <추론된 대상>
- context: <이전 대화 핵심 요약>

`1.` 확인 -- 이 용도로 티켓을 생성합니다
`2.` 용도 직접 지정 -- 목적 선택 메뉴로 전환합니다
`0.` 취소 -- 생성하지 않고 종료합니다
```

선택지 처리:
- `1.` 확인: 추론된 용도에 해당하는 command 값으로 `flow-kanban add-subnumber` 호출 후 1-3으로 진행
- `2.` 용도 직접 지정: 트랙 B로 전환
- `0.` 취소: 티켓 생성 없이 종료

---

#### 트랙 B: 맥락 미감지 또는 fallback

Read 도구로 `.claude/prompt/prompt.txt`를 읽어 메뉴 항목을 로드한 뒤 출력합니다:

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

사용자가 번호를 선택하면 선택된 용도에 해당하는 command 값으로 `flow-kanban add-subnumber`를 호출합니다 (goal/target/constraints/criteria/context는 빈 값):

```bash
flow-kanban add-subnumber T-NNN --command <command값>
```

사용자가 "0. 완료"를 선택하면 티켓 생성 없이 종료합니다.

### 1-3. 완료 메시지 출력

```
T-NNN 티켓이 생성되었습니다. (파일: .kanban/T-NNN.xml)

프롬프트 작성을 시작하려면 `/wf -e N`을 실행하세요.

## 후속 커맨드 안내

| 목적 | 커맨드 | 설명 |
|------|--------|------|
| 편집 | `/wf -e N` | 프롬프트 작성 및 내용 편집 ← 권장 |
| 제출 | `/wf -s N` | <command> 태그에 따라 자동 라우팅 |
| 종료 | `/wf -d N` | 티켓을 Done 상태로 종료합니다 |
```

---

## Step 1-B-o. `-o` 번호 있음: 기존 티켓을 Open으로 전이

기존 티켓을 선택지 없이 즉시 Open 상태로 전이합니다. 편집 루프에 진입하지 않습니다.

### 1-B-o-1. 티켓 파일 로드

Glob 도구로 `.kanban/T-NNN.xml` 패턴을 검색합니다.

**상태 판별**: Read 도구로 로드한 XML에서 `<metadata>/<status>` 텍스트를 확인하여 아래 상태에 따라 분기합니다:

| 상태 | 분기 흐름 |
|------|----------|
| `Open` | 안내 메시지(`T-NNN은 이미 Open 상태입니다.`) 출력 후 1-B-o-2로 진행 |
| `In Progress` | `flow-kanban move T-NNN open --force` 즉시 실행 후 상태 변경 확인 메시지 출력, 1-B-o-2로 진행 |
| `Review` | `flow-kanban move T-NNN open --force` 즉시 실행 후 상태 변경 확인 메시지 출력, 1-B-o-2로 진행 |
| `Done` (.kanban/done/ 발견) | `.kanban/done/T-NNN.xml`을 `.kanban/T-NNN.xml`로 복원한 뒤 `flow-kanban move T-NNN open --force` 실행, 1-B-o-2로 진행 |
| 파일 미발견 | 에러 출력 후 종료: `T-NNN 티켓 파일을 찾을 수 없습니다.` |

**비-Open 상태(In Progress / Review) 처리:**

Bash 도구로 아래 명령을 실행한 뒤 상태 변경 확인 메시지를 출력합니다:

```bash
flow-kanban move T-NNN open --force
```

```
`[T-NNN]` : `[WF -o]` T-NNN 상태를 Open으로 변경했습니다.
```

### 1-B-o-2. 후속 안내 출력

```
`[T-NNN]` : `[WF -o]` T-NNN 티켓을 Open 상태로 전이했습니다.

## 후속 커맨드 안내

| 목적 | 커맨드 | 설명 |
|------|--------|------|
| 편집 | `/wf -e N` | 프롬프트 작성 및 내용 편집 |
| 제출 | `/wf -s N` | <command> 태그에 따라 자동 라우팅 |
| 종료 | `/wf -d N` | 티켓을 Done 상태로 종료합니다 |
```

