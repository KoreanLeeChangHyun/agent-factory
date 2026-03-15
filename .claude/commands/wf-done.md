# wf-done.md — Step 3: `-d` 플래그 처리

`/wf -d N` 플래그 실행 시 이 파일을 Read 도구로 로드하여 아래 절차를 따릅니다.

> **칸반 전이**: Any → **Done**

지정한 티켓을 Done 상태로 종료합니다. `-d`는 티켓을 히스토리에 보존하며 삭제하지 않습니다.

---

## 3-1. 티켓 번호 검증

`$ARGUMENTS`에서 숫자 `N`을 파싱합니다. 티켓 번호가 없으면 아래 에러를 출력하고 종료합니다:

```
-d 플래그는 티켓 번호(N)를 반드시 지정해야 합니다. 예: /wf -d 3
```

## 3-2. Done 처리 실행

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

## 3-3. 완료 메시지 출력

```
T-NNN 티켓이 Done 상태로 종료되었습니다. (파일: .kanban/done/T-NNN.xml)
```
