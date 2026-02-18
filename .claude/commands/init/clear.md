---
description: 작업 내역 클리어. .workflow/* 디렉토리의 모든 문서를 삭제합니다.
---
# Clear Work History

이전 작업 내역을 정리합니다.

## 스크립트

`.claude/scripts/init/init-clear.sh` - 서브커맨드: list, execute

## 오케스트레이션 흐름

### Step 1. 삭제 대상 확인

Bash 도구로 실행:

```bash
wf-clear list
```

스크립트가 삭제 대상 목록과 크기를 출력합니다. 출력 결과를 사용자에게 표시합니다.

**삭제 대상:**
- `.workflow/` - 워크플로우 날짜 디렉토리 내용 삭제 (registry.json은 보존 후 `{}` 초기화)
- `.prompt/` - 프롬프트 파일 (history.md, prompt.txt 등)

### Step 2. 사용자 확인 (대화형)

**AskUserQuestion** 으로 삭제 확인:
- 질문: "위 내용을 삭제하시겠습니까? [yes/no]"
- `yes` -> Step 3
- `no` -> 취소 메시지 출력 후 종료

> **주의**: 기존 보고서가 필요한 경우 백업 후 실행하세요.

### Step 3. 삭제 실행

Bash 도구로 실행:

```bash
wf-clear execute
```

삭제 결과를 사용자에게 표시합니다.

**실행 결과 예시:**
```
=== 작업 내역 삭제 실행 ===

[.workflow/]
  삭제 완료: .workflow/20260210-123456/

[.prompt/]
  삭제 완료: .prompt/*

[.workflow/registry.json]
  초기화 완료: .workflow/registry.json ({})

---
삭제 완료: 2개 디렉토리 정리됨

초기화된 파일:
  - .workflow/registry.json ({})
```

---

## 관련 명령어

- `/init:project` - 프로젝트 초기화
