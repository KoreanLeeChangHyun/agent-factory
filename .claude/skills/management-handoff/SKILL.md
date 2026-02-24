---
name: management-handoff
description: "Auto-generates/manages HANDOFF.md between sessions to ensure context continuity. Automatically summarizes current work status, completed/incomplete items, and next steps. Use for session continuity: (1) handoff document creation before session end, (2) state saving before context compaction, (3) task switching in large-scale work. Triggers: 'handoff', '핸드오프', '세션 저장', '인수인계'."
disable-model-invocation: true
license: "Apache-2.0"
---

# Handoff Management

세션 간 HANDOFF.md를 자동 생성/관리하여 컨텍스트 연속성을 보장한다.

## 개요

Claude Code 세션은 컨텍스트 윈도우 제한으로 인해 긴 작업을 여러 세션에 걸쳐 수행해야 할 수 있다. 이 스킬은 세션 전환 시 작업 상태를 자동으로 문서화하여 다음 세션에서 이어서 작업할 수 있도록 한다.

## 저장 위치

| 상황 | 경로 |
|------|------|
| 워크플로우 작업 중 | `.workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>/HANDOFF.md` |
| 범용 (워크플로우 외) | `.prompt/handoff.md` |

## HANDOFF.md 템플릿

```markdown
# Handoff Document

- 생성일: YYYY-MM-DD HH:MM:SS (KST)
- 작업 ID: <workId> (워크플로우 작업인 경우)
- 명령어: <command> (워크플로우 작업인 경우)

## 현재 상태 요약

[현재 작업의 전체 상태를 1-3문장으로 요약]

## 완료된 항목

- [x] <완료 항목 1>
- [x] <완료 항목 2>
- [x] <완료 항목 3>

## 미완료 항목

- [ ] <미완료 항목 1> - <현재 진행 상황 또는 차단 요인>
- [ ] <미완료 항목 2> - <현재 진행 상황>

## 다음 단계

1. <즉시 수행해야 할 작업>
2. <그 다음 작업>
3. <후속 작업>

## 핵심 결정 사항

| 결정 | 근거 | 영향 범위 |
|------|------|----------|
| <결정 1> | <근거> | <영향 범위> |
| <결정 2> | <근거> | <영향 범위> |

## 참조 파일

다음 세션에서 반드시 읽어야 할 파일:

| 파일 | 용도 |
|------|------|
| `<경로>` | <이 파일을 읽어야 하는 이유> |
| `<경로>` | <이 파일을 읽어야 하는 이유> |

## 주의사항

- <다음 세션에서 알아야 할 중요 정보>
- <가정/제약사항>

## 이전 핸드오프 참조

이전 핸드오프 문서: <경로 또는 "없음">
```

## 생성 시점

### 1. 수동 생성 (사용자 요청)

사용자가 명시적으로 핸드오프 문서 생성을 요청할 때:

```
"핸드오프 문서 만들어줘"
"세션 종료 전에 상태 저장해줘"
"인수인계 문서 생성"
```

### 2. 워크플로우 태스크 전환 시

대규모 작업에서 태스크 간 전환 시 자동 생성:

```
W01 완료 → HANDOFF.md 생성 → W02 시작 시 HANDOFF.md 참조
```

orchestrator가 다음 worker 호출 시 이전 HANDOFF.md 경로를 전달하면, worker가 이를 참조하여 컨텍스트를 복원할 수 있다.

### 3. 컨텍스트 컴팩션 전

컨텍스트 윈도우가 임계점에 도달하면 컴팩션 전에 핸드오프 문서를 생성한다. 이를 통해 컴팩션으로 인한 정보 손실을 방지한다.

## 워크플로우

```
1. 현재 상태 수집
   - 진행 중인 작업 파악
   - 완료/미완료 항목 분류
   - 변경된 파일 목록 수집
      ↓
2. 결정 사항 정리
   - 세션 중 내린 주요 결정 기록
   - 결정의 근거와 영향 범위 명시
      ↓
3. 다음 단계 정의
   - 즉시 수행해야 할 작업 목록
   - 우선순위 순서 정리
      ↓
4. 참조 파일 식별
   - 다음 세션에서 읽어야 할 핵심 파일 목록
   - 각 파일의 참조 이유 명시
      ↓
5. HANDOFF.md 생성/갱신
   - 템플릿에 맞춰 문서 생성
   - 기존 HANDOFF.md가 있으면 갱신
      ↓
6. 확인
   - 생성된 파일 경로 안내
```

## 세션 시작 시 핸드오프 참조

새 세션 시작 시 이전 핸드오프 문서를 자동으로 참조한다:

### 참조 우선순위

```
1. 워크플로우 작업 디렉토리의 HANDOFF.md
   (.workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>/HANDOFF.md)
      ↓
2. 범용 핸드오프 파일
   (.prompt/handoff.md)
```

### 참조 절차

1. 핸드오프 파일 존재 여부 확인
2. 존재하면 Read 도구로 내용 로드
3. "현재 상태 요약" 및 "다음 단계" 확인
4. "참조 파일" 목록의 파일들을 순차적으로 로드
5. 이전 세션의 맥락을 파악한 후 작업 재개

## 대규모 작업에서의 활용

대규모 작업에서 태스크 전환 시 핸드오프 문서 활용 예시:

```
[orchestrator]
  ├─ W01 (worker) → 작업 완료 → HANDOFF.md 생성
  │    저장: .workflow/.../HANDOFF.md
  │
  ├─ W02 (worker) → HANDOFF.md 참조 → 작업 수행 → HANDOFF.md 갱신
  │
  └─ W03 (worker) → HANDOFF.md 참조 → 작업 수행 → 최종 HANDOFF.md
```

각 worker는 이전 태스크의 결과물과 결정 사항을 핸드오프 문서를 통해 전달받는다.

## 핸드오프 문서 관리

### 갱신 정책

- 기존 HANDOFF.md가 있으면 덮어쓰기 (항상 최신 상태 유지)
- 이전 핸드오프 참조 링크를 "이전 핸드오프 참조" 섹션에 기록

### 정리 정책

- 워크플로우 작업 완료 시: REPORT 단계에서 HANDOFF.md의 정보를 보고서에 통합
- 범용 핸드오프: 새 핸드오프 생성 시 이전 파일 덮어쓰기

## 참고

- 태스크 기반 작업에서 태스크 간 컨텍스트 전달에 특히 유용
- orchestrator/SKILL.md에서 worker 호출 시 HANDOFF.md 경로를 전달 가능
- 컨텍스트 윈도우 효율성: 핵심 정보만 구조화하여 토큰 절약
