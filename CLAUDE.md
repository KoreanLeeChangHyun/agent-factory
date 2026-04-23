# CLAUDE.md

<!-- 프로젝트별 규칙을 여기에 작성하세요 -->
<!-- 워크플로우 시스템 규칙은 .claude/rules/workflow/ 에서 관리됩니다 -->

## 칸반 상태 흐름

### 5단계 FSM

```
To Do → Open → In Progress → Review → Done
```

- **To Do**: 미래에 할 백로그·아이디어 저장소 (박제 공간). 지금 당장 집중하지 않는 작업.
- **Open**: 지금 집중해야 하는 임박 작업. 워크플로우 실행(`/wf -s N`) 대상.
- **In Progress**: 워크플로우 실행 중인 상태.
- **Review**: 워크플로우 완료 후 사용자 리뷰 대기.
- **Done**: 완료.

### 전이 규칙

| 전이 | 방법 | 비고 |
|------|------|------|
| To Do → Open | `flow-kanban move T-NNN open` | 승격 |
| Open → To Do | `flow-kanban move T-NNN todo` | 강등 |
| Open → In Progress | `/wf -s N` | 워크플로우 실행 |
| In Progress → Review | 워크플로우 자동 전이 | |
| Review → Done | `/wf -d N` | |
| Review → Open | `/wf -e N` | 재작업 |

### 티켓 생성 규칙

티켓 생성 시 `--status todo` 또는 `--status open` 중 하나를 반드시 명시해야 한다 (MUST).

```bash
flow-kanban create "제목" --command implement --status todo   # 백로그 박제
flow-kanban create "제목" --command implement --status open   # 즉시 집중 대상
```

기본값(`--status` 미지정)은 에러를 반환한다.

