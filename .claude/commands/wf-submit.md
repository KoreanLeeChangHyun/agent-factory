# wf-submit.md — Step 2: `-s` 플래그 처리

`/wf -s N` 플래그 실행 시 이 파일을 Read 도구로 로드하여 아래 절차를 따릅니다.

> **칸반 전이**: Open → **In Progress** (wf 내부에서 워크플로우 스킬 로드 후 처리)

티켓의 `<command>` 태그를 읽어 해당하는 `workflow-wf-*` 스킬을 직접 로드하고 워크플로우를 실행합니다.

---

## tmux 환경 분기

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

## 2-1. 티켓 번호 검증

`$ARGUMENTS`에서 숫자 `N`을 파싱합니다. 티켓 번호가 없으면 아래 에러를 출력하고 종료합니다:

```
-s 플래그는 티켓 번호(N)를 반드시 지정해야 합니다. 예: /wf -s 3
```

## 2-2. 티켓 파일 로드

Glob 도구로 `.kanban/T-NNN.xml` 패턴을 검색하여 현재 상태 파일을 탐색합니다.

파일을 찾지 못한 경우 에러 출력 후 종료:
```
T-NNN 티켓 파일을 찾을 수 없습니다. (.kanban/T-NNN.xml)
```

## 2-3. `<command>` 태그 파싱

로드된 티켓 XML 파일을 XML 파서로 읽어 `<metadata>` 내부의 `<current>` 요소 값을 먼저 확인합니다.

- `<current>` 값이 `0` 또는 존재하지 않는 경우 (subnumber 없음): 에러 출력 후 종료
  ```
  T-NNN 티켓에 워크플로우가 정의되지 않았습니다. /wf -e N으로 먼저 작성하세요.
  ```

`<current>` 값이 1 이상인 경우, 해당 ID의 `<subnumber id="N">` 요소를 찾아 직하의 `<command>` 자식 요소를 읽습니다. `<command>`는 `<prompt>` 래퍼 밖 subnumber 직하에 위치합니다.

**체인 command 파싱**: `<command>` 값에 `>` 구분자가 포함된 경우 체인 표기(`research>implement>review`)로 처리합니다.

- `>` 기준으로 split하여 각 세그먼트를 추출합니다
- 첫 번째 세그먼트를 현재 실행할 command로 사용합니다
- 각 세그먼트가 유효한 command인지 모두 검증합니다 (`implement`, `research`, `review`)
- 유효하지 않은 세그먼트가 하나라도 있으면 에러 출력 후 종료:
  ```
  T-NNN 티켓의 <command> 체인에 유효하지 않은 세그먼트가 있습니다: XXX (허용: implement, research, review)
  /wf -e N 으로 티켓 용도를 다시 지정하세요.
  ```
- 단일 command(`implement`)는 기존 동작과 동일하게 처리합니다 (하위 호환)

**단일 command 검증** (`>` 구분자 없는 경우):

- 유효한 값: `implement`, `research`, `review`
- `<command>` 요소가 없는 경우:
  ```
  T-NNN 티켓에 <command> 태그가 없습니다.
  /wf -e N 으로 티켓 용도를 먼저 지정하세요.
  ```
- `<command>` 값이 유효하지 않은 경우:
  ```
  T-NNN 티켓의 <command>XXX</command> 값이 유효하지 않습니다. (허용: implement, research, review)
  /wf -e N 으로 티켓 용도를 다시 지정하세요.
  ```

## 2-4. 실행 안내 출력

단일 command인 경우:
```
T-NNN 티켓을 <command> 워크플로우로 실행합니다.
```

체인 command인 경우 (예: `research>implement>review`의 1번째 스테이지 실행 시):
```
T-NNN 티켓을 <첫번째 세그먼트> 워크플로우로 실행합니다. (체인: research > implement > review, 1/3 스테이지)
```

## 2-5. 워크플로우 스킬 로드 및 실행

Read 도구로 현재 실행할 command(체인인 경우 **첫 번째 세그먼트**)에 해당하는 wf 스킬을 직접 로드한 뒤 해당 스킬의 지침을 따라 워크플로우를 실행합니다. 체인 여부와 무관하게 기존 라우팅 매핑 테이블을 그대로 사용합니다.

**자동 라우팅 매핑**:

| `<command>` 값 (또는 체인의 첫 번째 세그먼트) | 로드할 스킬 파일 |
|---------------|----------------|
| `implement` | `.claude/skills/workflow-wf-implement/SKILL.md` |
| `research` | `.claude/skills/workflow-wf-research/SKILL.md` |
| `review` | `.claude/skills/workflow-wf-review/SKILL.md` |

> **참고**: 워크플로우 완료 후 `flow-kanban move T-NNN review`로 자동 전이됩니다 (`workflow-wf-submit` 스킬 지침에서 처리). 다음 사이클을 실행하려면 `/wf -e N`으로 프롬프트를 수정하거나 `/wf -d N`으로 티켓을 종료하세요. 체인 command인 경우 finalization.py가 완료 후 자동으로 다음 스테이지를 새 tmux 세션에서 실행합니다.
