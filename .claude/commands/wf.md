---
description: "티켓 라이프사이클 통합 관리. -o(Open/열람), -e(Edit/편집), -oe(Open+Edit 단축), -s(Submit), -d(Done), -c(Cancel) 6개 플래그로 티켓 생성부터 완료까지 단일 진입점으로 제어합니다. Use when: 티켓 생성, 티켓 편집, 워크플로우 실행, 티켓 종료, 티켓 삭제를 한 번에 처리할 때"
argument-hint: "[-o|-e|-oe|-s|-d|-c] [N] (티켓 라이프사이클 통합 관리)"
---

# wf (Workflow 통합 명령어)

티켓 라이프사이클 전체를 단일 진입점으로 관리합니다. `-o`(Open/채번+용도선택만), `-e`(Edit/편집), `-oe`(Open+Edit 단축 별칭), `-s`(Submit), `-d`(Done), `-c`(Cancel/삭제) 6개 플래그로 생성부터 종료까지 제어합니다.

## Step 0. 플래그 파싱 및 라우팅

`$ARGUMENTS`에서 플래그와 티켓 번호를 파싱하여 실행 흐름을 결정합니다.

### 파싱 규칙

1. **플래그 추출**: `$ARGUMENTS`에서 `-oe`, `-o`, `-e`, `-s`, `-d`, `-c` 패턴을 순서대로 검색합니다 (`-oe`를 `-o`와 `-e`보다 먼저 검색하여 정확한 매칭 보장)
2. **티켓 번호 추출**: 숫자 `N`(예: `1`, `12`, `123`)을 파싱하여 3자리 zero-padding 적용 (예: `3` → `T-003`)
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

현재 칸반 상태를 확인하려면 `.kanban/` 디렉터리의 XML 티켓 파일을 참조하세요.
```

### 라우팅 규칙

| 조건 | 실행 흐름 |
|------|----------|
| `-o` 플래그 | wf-open.md (Open/생성 또는 열람, 채번+용도선택까지만) |
| `-e` 플래그 | wf-edit.md (Edit/편집, 편집 루프 진입) |
| `-oe` 플래그 | wf-edit.md (하위호환, `-e`와 동일 동작) |
| `-s` 플래그 | wf-submit.md (Submit/제출) |
| `-d` 플래그 | wf-done.md (Done/종료) |
| `-c` 플래그 | wf-cancel.md (Cancel/삭제) |
| 플래그 없음 | 도움말 메뉴 출력 후 종료 |

### 플래그별 처리 파일 로드

라우팅 규칙에 따라 해당 플래그의 처리 파일을 Read 도구로 로드하여 절차를 따릅니다:

| 플래그 | 로드할 파일 | 설명 |
|--------|-----------|------|
| `-o` | `.claude/commands/wf-open.md` | Open 처리 절차 |
| `-e` 또는 `-oe` | `.claude/commands/wf-edit.md` | Edit 처리 절차 (`-oe`는 `-e`의 단축 별칭) |
| `-s` | `.claude/commands/wf-submit.md` | Submit 처리 절차 |
| `-d` | `.claude/commands/wf-done.md` | Done 처리 절차 |
| `-c` | `.claude/commands/wf-cancel.md` | Cancel 처리 절차 |

Read 도구로 해당 파일을 로드한 후, 파일의 지침에 따라 절차를 실행합니다.

---

## 칸반 상태 전이 요약

| 플래그 | 실행 전 상태 | 실행 후 상태 | 전이 명령 |
|--------|------------|------------|---------|
| `-o` (번호 없음) | (없음) | Open | `flow-kanban create "" --command init` + `flow-kanban add-subnumber` (채번+용도선택만, 편집 루프 미진입) |
| `-e` (번호 없음) | (없음) | Open | `flow-kanban create "" --command init` + `flow-kanban add-subnumber` + 편집 루프 (`-oe`도 동일 동작) |
| `-o N` | Done | Open (복원) | `mv .kanban/done/T-NNN.xml .kanban/T-NNN.xml` + `flow-kanban move T-NNN open` (내용 표시만, 편집 루프 미진입) |
| `-o N` | Review/In Progress | Open (자동 복귀) | `flow-kanban move T-NNN open` (내용 표시만, 편집 루프 미진입) |
| `-o N` | Open | Open (유지) | — (내용 표시만, 편집 루프 미진입) |
| `-e N` | Done | Open (복원) | `mv .kanban/done/T-NNN.xml .kanban/T-NNN.xml` + `flow-kanban move T-NNN open` + 편집 루프 (`-oe N`도 동일 동작) |
| `-e N` | Review/In Progress | Open (자동 복귀) | `flow-kanban move T-NNN open` + 편집 루프 (`-oe N`도 동일 동작) |
| `-e N` | Open | Open (유지) | — (편집 루프 진입, `-oe N`도 동일 동작) |
| `-s` | Open | In Progress | `flow-tmux launch T-NNN '/wf -s N'` (LAUNCH: 새 윈도우 실행, INLINE: 인라인 실행, exit 1: 에러) |
| `-s` (완료 후) | In Progress | Review | `flow-kanban move T-NNN review` (workflow-wf-submit 처리) |
| `-d` | Any | Done | `flow-kanban done T-NNN` |
| `-c` | Any | (삭제) | `flow-tmux launch T-NNN '/wf -c N'` (LAUNCH: 새 윈도우 실행, INLINE: `flow-kanban delete T-NNN` 인라인 실행, exit 1: 에러) |

## subnumber 생명주기

티켓 XML 내부의 `<subnumber>` 요소는 워크플로우 실행 사이클마다 하나씩 추가됩니다. 전체 흐름은 다음과 같습니다:

| 단계 | 플래그 | subnumber 상태 | 수행 명령 |
|------|--------|---------------|---------|
| 티켓 생성 직후 | `-o` 또는 `-e`(또는 `-oe`) | `<current>0</current>` (subnumber 없음) | `flow-kanban create "" --command init` |
| 워크플로우 정의 | `-o` (채번+용도선택만) | subnumber N 추가(기본값), `<current>N</current>` 갱신 | `flow-kanban add-subnumber T-NNN --command ...` (goal/target 등 빈 값) |
| 워크플로우 정의 | `-e` 완료 또는 `-e NNN` (또는 `-oe`) | subnumber N 추가, `<current>N</current>` 갱신 | `flow-kanban add-subnumber T-NNN --command ... --goal ... --target ...` |
| 워크플로우 실행 완료 | `-s` 후처리 | subnumber N에 workflow 번호 기록 | `flow-kanban update-subnumber T-NNN --id N --workflow W-NNN` |
| 다음 사이클 시작 | `-e NNN` (추가 사이클, 또는 `-oe NNN`) | subnumber N+1 추가, `<current>N+1</current>` 갱신 | `flow-kanban add-subnumber T-NNN --command ... --goal ... --target ...` |
| 티켓 종료 | `-d` | 변경 없음 (히스토리 보존) | `flow-kanban done T-NNN` |

## 주의사항

1. **단일 진입점**: 티켓 라이프사이클 전체를 `/wf` 하나로 관리합니다. `/wf`가 유일한 티켓 관리 진입점입니다
2. **자동 Open 복귀**: `-o NNN`, `-e NNN` 또는 `-oe NNN` 플래그로 Review/In Progress 티켓에 접근 시 사용자 확인 없이 Open으로 자동 복귀합니다
3. **`<command>` 태그 정책**: `-o`/`-e` 생성 시 설정된 값을 기본 보존하되, `-e NNN`(또는 `-oe NNN`) 편집 시 명시적 변경이 허용됩니다
4. **Bash 도구 사용**: 칸반 상태 전이 및 파일 이동이 필요한 Step(1-1, 1-B-1, 1-B-2, 2-5, 3-2)에서 허용합니다
5. **AskUserQuestion 미사용**: 모든 사용자 입력은 텍스트 메뉴 출력 후 자유 입력으로 수신합니다. 접두사는 `` `[T-NNN]` : `[WF -플래그]` `` 형식을 사용합니다
6. **Task 도구 호출 금지**: 이 명령어는 비워크플로우 독립 명령어이므로 서브에이전트를 호출하지 않습니다
7. **wf 스킬 직접 로드**: `-s` 플래그 실행 시 SlashCommand/Skill 도구가 아닌 Read 도구로 해당 스킬 파일을 직접 로드하여 실행합니다
8. **독립 세션 실행**: `-s`와 `-c` 플래그는 `flow-tmux launch T-NNN '<command>'`로 새 윈도우 생성+폴링+명령전송을 위임합니다. stdout 접두사로 분기합니다: `LAUNCH:`=새 윈도우에서 실행 중, `INLINE:`=인라인 실행 필요(비tmux 환경 또는 재진입 감지), exit code 1=에러(타임아웃 등). 워크플로우 완료 시 finalization.py Step 5(1차, 3초 지연)와 PostToolUse hook(2차, 5초 지연)가 이중으로 tmux 윈도우를 자동 종료합니다. start_new_session+sleep 지연으로 flow-claude end 배너 출력이 보장됩니다. 중복 윈도우 체크, 재진입 방지, 폴링 타임아웃 등 상세는 flow-tmux 내부에서 처리합니다
9. **constraints/criteria 필수**: `0. 완료` 선택 시 constraints 또는 criteria가 누락이거나 10자 미만이면 완료를 거부하고 루프를 계속합니다. 이는 Step 1-4(신규 생성, `-e` 모드)와 Step 1-B-5(편집 루프, `-e N` 모드, 최초/추가 사이클 양쪽) 모두에 적용됩니다. `-oe`는 `-e`와 동일하게 적용됩니다. `-o` 단독 모드에서는 편집 루프에 진입하지 않으므로 이 검증이 적용되지 않습니다

## 자연어 매핑 가이드

사용자의 자연어 요청을 LLM이 해석하여 `-o` 또는 `-e` 모드를 자동 선택합니다. 아래 매핑 테이블을 참조하여 적절한 플래그를 결정하세요.

| 자연어 요청 예시 | 매핑 플래그 | 근거 |
|-----------------|-----------|------|
| "티켓만 열어", "채번해줘", "티켓 하나 만들어" | `-o` | 생성만 요청, 편집 의도 없음 |
| "티켓 만들고 편집할게", "프롬프트 작성하자", "티켓 열고 내용 채우자", "편집할게" | `-e` | 생성 + 편집 의도 명시 (`-oe`는 `-e`의 단축 별칭으로 동일 동작) |
| "기존 티켓 열어", "3번 티켓 보여줘" | `-o N` | 열람만 요청, 편집 의도 없음 |
| "3번 티켓 수정할게", "기존 티켓 편집하자" | `-e N` | 편집 의도 명시 (`-oe N`도 동일 동작) |
| (의도 불명확) | `-e` | 기존 동작 호환을 위해 편집 루프 포함 모드를 기본값으로 사용 |

> **판단 원칙**: 편집 의도가 명시적으로 없는 경우 `-o`(채번+용도선택만)를 선택합니다. 편집 의도가 있거나 불명확한 경우 `-e`(편집 루프 포함)를 선택하여 기존 동작과의 호환성을 유지합니다. `-oe`는 `-e`의 단축 별칭으로 동일한 동작을 수행합니다.
