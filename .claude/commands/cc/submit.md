---
description: "티켓 제출. 티켓 파일의 <command> 태그를 읽어 해당 워크플로우를 자동 실행합니다."
argument-hint: "[#N] 제출할 티켓 번호"
---

## Step 1: #N 파싱 및 티켓 로드

`$ARGUMENTS`에서 `#N` 패턴(예: `#1`, `#12`, `#123`)을 파싱하여 티켓 번호를 추출합니다. 추출된 번호는 3자리 zero-padding하여 `.kanban/*-T-NNN.txt` glob 패턴으로 현재 상태 파일을 탐색합니다.

- `#N` 지정 시: `.kanban/*-T-NNN.txt` glob 패턴으로 티켓 파일을 탐색하여 로드
- `#N` 미지정 시: `.kanban/board.md`에서 Open 상태 티켓을 자동 선택
  - Open 티켓 1개: 해당 티켓 자동 선택
  - Open 티켓 복수: 목록을 출력하고 AskUserQuestion으로 사용자 선택 요청
  - Open 티켓 0개: 에러 출력 후 종료 (`Open 상태 티켓이 없습니다. 티켓 번호를 직접 지정하세요: /cc:submit #N`)

티켓 파일을 찾지 못한 경우 에러 출력 후 종료:
```
T-NNN 티켓 파일을 찾을 수 없습니다. (.kanban/*-T-NNN.txt)
```

## Step 2: `<command>` 태그 파싱

로드된 티켓 파일에서 `<command>XXX</command>` 패턴을 파싱합니다.

- 유효한 값: `implement`, `research`, `review`
- `<command>` 태그가 없는 경우: 에러 출력 후 종료
  ```
  T-NNN 티켓에 <command> 태그가 없습니다.
  /cc:prompt -p #N 으로 티켓 용도를 먼저 지정하세요.
  ```
- `<command>` 값이 유효하지 않은 경우 (`implement` / `research` / `review` 외): 에러 출력 후 종료
  ```
  T-NNN 티켓의 <command>XXX</command> 값이 유효하지 않습니다. (허용: implement, research, review)
  /cc:prompt -p #N 으로 티켓 용도를 다시 지정하세요.
  ```

## Step 3: 실행 안내

다음 형식으로 실행 안내 메시지를 출력합니다:

```
T-NNN 티켓을 cc:X로 실행합니다.
```

(예: `T-003 티켓을 cc:research로 실행합니다.`)

## Step 4: 워크플로우 실행

SlashCommand 또는 Skill 도구로 `/cc:X #N`을 호출합니다.

- 호출 가능 시: SlashCommand/Skill 도구로 `/cc:X #N` 실행
- 호출 불가 시 (폴백): 다음 커맨드 문자열을 출력하고 사용자가 직접 실행하도록 안내
  ```
  /cc:X #N
  ```
