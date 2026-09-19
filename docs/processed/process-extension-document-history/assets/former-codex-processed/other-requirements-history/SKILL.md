---
name: other-requirements-history
description: 요구사항 이전 기록을 출처와 함께 보존하는 비권위 Processed 기록입니다. 현재 명세 적용 지침이 아닙니다.
metadata:
  document-type: processed
  category: other
  domain: null
  name: requirements-history
  language: ko
  provenance:
    historical-source-path: "docs/requirements.md"
    preserved-record: "docs/processed/other-requirements-history/SKILL.md"
    captured-on: "2026-09-16"
    organization-authority: "Human requested only original, processed and specification roots and authorized migration of these four historical records."
    fidelity: "기존 본문과 앞선 정리 안내를 보존하고 안내의 상대 링크만 새 위치에 맞게 변경했습니다."
    status: historical-snapshot
---

# 요구사항 이전 기록

- 이 패키지는 앞선 명세 정리 시 남겼던 `docs/requirements.md`의 이전 기록을 보존합니다. 옛 경로는 출처 식별자이며 현재 파일 위치가 아닙니다.
- 문서 유형은 Processed입니다. 역사 기록이라는 상태는 네 번째 문서 유형이나 저장 루트가 아닙니다. `other`는 내용을 분석·판정하지 않고 보존하는 가공 기록의 범주입니다.
- 현재 요구사항과 설계의 권위는 아래 링크된 기존 Specification에 있습니다. 이번 이전은 현재 명세를 강등하거나 요구사항을 폐기하지 않습니다.
- 아래 과거 경로·목표 트리·구현 설명·확인 요청·외부 근거는 당시 기록입니다. 새 검증 결과나 현재 실행 지시로 간주하지 마십시오.

## 보존된 이전 문서

<!-- Historical source preserved during the approved specification organization, 2026-09-16 KST. -->
> **역사 자료 — 현재 편집 원문은 [design-main-chat](../../skills/design-main-chat/SKILL.md)입니다.**
> 아래는 정리 직전 본문을 보존한 출처 자료이며 최신 명세의 경쟁 원본이 아닙니다. 과거 런타임 경로·구현 설명·당시 확인 요청은 현재 사실이나 검증 결과로 사용하지 마십시오. 의미 변경은 링크된 명세에서 관리합니다.

# Agent Factory Main Chat VS Code Extension 요구사항

## 1. 목적

여러 Codex CLI 터미널을 직접 열고 관리하는 대신, 독립된 Main Agent 세션을
VS Code 편집기 탭의 채팅 UI로 동시에 사용할 수 있는 확장 하나를 제공한다.

이 확장은 Agent Factory를 대체하지 않는다. 설치된 Agent Factory 플러그인의
관리형 런타임을 사용하며, 메인 에이전트에 대한 VS Code 전용 UI/UX를 제공한다.

## 2. 핵심 개념

- 편집기 채팅 탭 하나는 Main Agent 하나와 Codex 세션 하나에 대응한다.
- 여러 채팅 탭을 열어 여러 Main Agent를 병렬로 사용할 수 있다.
- Main은 사용자에게 노출되는 전문 역할 선택지가 아니다. 런타임 호환을 위해
  내부적으로만 `role: main`을 사용한다.
- Codex CLI는 화면에 노출되는 TUI가 아니라 백그라운드 실행 엔진이다.
- Main Agent별 프로세스, 환경, 세션과 실행 상태는 독립된다.
- Main Agent들은 현재 프로젝트 루트와 파일을 공유한다. Git worktree나 파일
  복제로 격리하지 않는다.
- 운영 상태의 기준 저장소는
  `<project-root>/.agent-factory/agent/<agent-id>/`이다.

## 3. 제품 및 책임 경계

### 3.1 VS Code 확장

- Main Agent 채팅 편집기 탭을 렌더링한다.
- 사용자 입력, 첨부, 승인, 설정, 알림과 VS Code 편집기 통합을 제공한다.
- Agent Factory Runtime의 명령과 이벤트를 UI 프로토콜로 변환한다.
- 자체 에이전트 런타임이나 별도 로그인 체계를 만들지 않는다.

### 3.2 Agent Factory 플러그인

- 필수 의존성이다.
- `skills/agent/scripts/exec.py`가 세션, 실행, 취소, 복원과 기록의 단일 제어
  경로다.
- `submit`, `send`, `list`, `status`, `result`, `inbox`, `cancel`, `reconcile`
  계약을 사용한다.
- 세션과 실행 상태를 `.agent-factory/agent/`에 저장한다.

### 3.3 웹 Workspace

- Main을 포함한 전체 에이전트를 관리하는 별도 웹 제품이다.
- VS Code 확장에 Workspace, Kanban, Dashboard 또는 다중 에이전트 관리 화면을
  복제하지 않는다.
- 두 UI는 같은 Agent Factory 런타임 상태를 읽을 수 있어야 한다.

## 4. 기능 요구사항

### FR-01. 채팅 편집기 탭

- 채팅은 사이드바나 하단 패널이 아니라 VS Code 편집기 영역에 Webview 탭으로
  열린다.
- 파일과 터미널처럼 탭 이동, 분할, 닫기와 다시 열기를 지원한다.
- Main Agent별 채팅 탭과 상태가 섞이지 않아야 한다.
- 채팅 탭을 닫아도 Agent 실행과 입력 대기열은 유지되어야 한다.
- 탭을 닫는 동작은 취소나 Archive로 해석하지 않는다.

### FR-02. 새 세션과 Resume

- 별도의 `New` 버튼이나 상시 세션 관리 목록을 제공하지 않는다.
- Resume로 기존 세션을 선택하지 않은 채팅 탭은 새 Main Agent 세션으로
  시작한다.
- 첫 메시지를 제출할 때 새 Agent Factory 세션을 생성한다.
- `Resume`은 현재 프로젝트의 `.agent-factory/agent/`에 저장된 Main Agent
  세션만 VS Code 선택창에 표시한다.
- 선택한 Agent ID와 Codex Session ID를 명시적으로 사용한다.
- `resume --last`처럼 세션을 추측하지 않는다.
- 세션 이름 변경과 Archive/Unarchive를 지원한다.
- 영구 삭제와 이전 메시지 수정에 따른 Fork는 제공하지 않는다.

### FR-03. 런타임 연결

- 확장은 Agent Factory 플러그인 설치 여부, `agent` Skill, `exec.py`, Python과
  Codex CLI 가용성을 진단해야 한다.
- 필수 구성요소가 없거나 호환되지 않으면 실행을 차단하고 설치 또는 수정
  안내와 다시 확인 동작을 제공한다.
- Codex CLI를 별도의 직접 제어 경로로 실행하지 않는다.
- 실행 이벤트를 실시간으로 읽고 탭이 다시 열리면 유실 없이 복원한다.
- 동일 Codex 세션에서 동시에 두 turn을 실행하지 않는다.
- Agent별 백그라운드 실행 환경은 독립하고 프로젝트 파일은 공유한다.

### FR-04. 응답 타임라인

- 다음 이벤트를 하나의 시간순 타임라인에 표시한다.
  - 사용자 및 Main Agent 텍스트
  - 진행 상태
  - 셸 명령과 출력
  - 파일 변경
  - 도구 호출과 결과
  - 계획 변경
  - Work 및 Verification Agent dispatch와 진행 상태
  - 승인 요청
  - 오류, 취소와 완료
- 긴 도구 출력은 요약 상태로 시작하며 사용자가 펼칠 수 있어야 한다.
- Main Agent가 호출한 Work와 Verification Agent는 별도 채팅 탭으로 만들지 않고
  Main 타임라인의 dispatch 카드로 표시한다.
- 상태바에는 현재 실행 중인 Work 및 Verification Agent 수를 역할별로 표시하고,
  활성 Agent가 있으면 시각적으로 강조한다.
- Markdown, 코드 블록과 표를 안전하게 렌더링한다.
- 모델이 생성한 HTML을 신뢰해 직접 삽입하지 않는다.

### FR-05. 입력과 실행 제어

- Enter는 전송, Shift+Enter는 줄바꿈으로 동작한다.
- IME 조합 중 Enter는 전송하지 않는다.
- 실행 중에도 추가 메시지를 제출할 수 있다.
- 추가 메시지는 현재 실행을 암묵적으로 취소하지 않고 세션 대기열에 저장한다.
- 대기 메시지는 실행 전까지 수정하거나 제거할 수 있어야 한다.
- 현재 실행이 끝나면 다음 대기 메시지를 순서대로 자동 처리한다.
- 실행 중 `Esc`는 현재 실행만 취소한다.
- 취소가 끝나면 다음 대기 메시지를 자동 처리한다.
- 화면의 중지 버튼도 `Esc`와 같은 동작을 제공한다.

### FR-06. 승인

- 파일 수정, 명령 실행 또는 권한 확장이 승인을 요구하면 채팅 카드로 표시한다.
- 사용자는 채팅에서 승인 또는 거절할 수 있어야 한다.
- 승인 대기 중인 실행 상태를 명확히 표시한다.
- 승인 결과와 근거를 해당 run 기록에 남긴다.
- Webview가 승인 정책을 우회하거나 직접 시스템 권한을 갖지 않는다.

### FR-07. 실행 설정

- 모델, 추론 수준, Fast 모드, Goal 모드, 샌드박스와 승인 정책을 조정할 수 있어야
  한다.
- Fast 모드는 세션 단위로 유지되는 On/Off 설정이다.
- Goal 모드는 다음 사용자 요청 한 번에 적용되는 On/Off 설정이며 제출 후 자동으로
  Off로 돌아간다.
- 모델과 지원 옵션은 하드코딩하지 않고 현재 Codex 런타임 capability를
  기준으로 제공한다.
- 설정 범위와 우선순위는 다음과 같다.
  1. 세션 설정
  2. 현재 프로젝트 기본값
  3. Codex 전역 기본값
- 세션 설정은 해당 Main Agent에만 적용하며 Resume 후에도 유지한다.
- 프로젝트 기본값은 VS Code 확장과 웹 Workspace가 함께 읽을 수 있는 Agent
  Factory 런타임 설정에 저장한다.
- UI는 각 값의 현재 값과 출처를 표시하고 상위 기본값으로 복원할 수 있어야 한다.

### FR-08. 첨부

- 클립보드 이미지 붙여넣기와 미리보기를 지원한다.
- 운영체제 파일 탐색기와 VS Code Explorer에서 파일 및 폴더 DnD를 지원한다.
- 열린 편집기 파일, 여러 파일과 여러 폴더를 첨부할 수 있어야 한다.
- 파일 및 폴더 선택 버튼을 제공한다.
- 첨부 항목은 작성기에 칩으로 표시하며 개별 제거할 수 있어야 한다.
- 폴더는 전체 내용을 복제하지 않고 경로 참조로 전달한다.
- 현재 프로젝트 외부의 파일과 폴더도 명시적 첨부로 사용할 수 있다.
- 프로젝트 외부 경로는 기본 읽기 전용이며 쓰기는 별도 승인을 요구한다.
- 첨부 개수, 크기, 형식과 경로를 검증하고 사용자에게 구체적인 오류를 표시한다.
- 선택 코드 또는 파일의 `Add to Chat`을 보조 기능으로 제공한다.
- DnD를 주 첨부 흐름으로 최적화한다.

### FR-09. VS Code 코드 통합

- 응답의 프로젝트 파일 경로와 줄 번호를 클릭하면 편집기에서 연다.
- 외부 파일 링크는 허용 경로를 검증한 뒤 연다.
- 변경된 파일 목록을 표시하고 VS Code Diff 화면으로 연결한다.
- Main Agent가 만든 변경과 실행 전 상태를 비교할 수 있어야 한다.

### FR-10. 자동 스냅샷과 복원

- 각 실행 직전에 임시 기준 상태를 안전하게 생성한다.
- 실행에서 파일 변경이 발생한 경우에만 기준 상태를 정식 스냅샷으로 보존한다.
- 파일 변경이 없으면 임시 기준 상태를 폐기한다.
- 특정 run의 실행 전 상태와 현재 상태를 Diff로 확인할 수 있어야 한다.
- 사용자는 특정 스냅샷으로 복원할 수 있어야 한다.
- 복원 직전에 현재 상태를 다시 복구 가능한 스냅샷으로 남긴다.
- 스냅샷 이후 사용자 변경과 충돌하면 자동 덮어쓰지 않고 복원을 중단해 충돌
  파일을 표시한다.
- `git reset --hard`처럼 작업 트리를 무조건 덮어쓰는 방식은 사용하지 않는다.
- Git 프로젝트에서는 브랜치나 HEAD를 이동하지 않는 Git 객체 또는 패치 기반
  구현을 우선한다.

### FR-11. 알림

- 닫힌 탭의 실행이 완료, 실패하거나 승인을 기다리면 VS Code 알림을 표시한다.
- 알림을 선택하면 정확한 Main Agent 채팅 탭을 열거나 복원한다.
- 활성 탭에서 이미 확인 중인 상태를 중복 알림하지 않는다.

### FR-12. 상태바

- 채팅 하단에 고정 상태바를 제공한다.
- 공식 Codex 확장의 실행 위치 선택 바(`로컬에서 작업`)는 제공하지 않는다.
- 실행 위치는 현재 프로젝트의 Agent Factory 로컬 런타임으로 고정한다.
- 사용자는 상태바 항목의 표시 여부와 순서를 조정할 수 있다.
- 상태바 자체의 위·아래 위치 변경은 제공하지 않는다.
- 후보 항목에는 Agent 이름, 실행 상태, 활성 Work/Verification 수, 모델, 추론 수준,
  Fast, Goal, 프로젝트, Git
  브랜치, 컨텍스트 사용량, 실행 시간, 대기 메시지 수와 런타임 상태가 포함된다.

### FR-13. 인증

- 별도 로그인, API key 또는 토큰 관리 UI를 만들지 않는다.
- 기존 Codex CLI 인증 상태를 그대로 사용한다.
- 확장과 Webview는 인증 비밀을 읽거나 저장하지 않는다.
- 미로그인 상태에서는 Codex CLI 로그인이 필요하다는 안내만 제공한다.

## 5. 품질 및 보안 요구사항

- Extension Host가 파일 시스템, 프로세스와 VS Code API를 소유한다.
- Webview는 렌더링과 입력만 담당하며 모든 메시지는 allowlist schema로 검증한다.
- Webview에는 nonce 기반 Content Security Policy를 적용한다.
- 외부 경로, 파일 링크와 DnD payload는 정규화하고 symlink 및 traversal을
  검증한다.
- 대용량 메시지, 첨부와 도구 출력에 명시적인 상한을 둔다.
- 한 Agent의 실패나 취소가 다른 Agent 세션에 영향을 주지 않아야 한다.
- 탭이 닫혀도 런타임 이벤트를 지속적으로 수집해야 한다.
- 런타임 상태 파일을 UI가 임의 수정하지 않고 공식 런타임 계약을 사용한다.
- 밝은/어두운/고대비 테마, 키보드 탐색, 스크린 리더와 reduced motion을
  지원한다.
- 핵심 상태 전이, Resume, 큐, 승인, 첨부, 설정 우선순위, 이벤트 복원과
  스냅샷 안전성을 자동화 테스트한다.

## 6. 지원 범위

### MVP

- Linux
- Linux에서 실행되는 VS Code Remote WSL Extension Host

### 후속

- macOS: Darwin/launchd containment adapter가 Agent Factory Runtime에 추가된 후
- Windows 및 Git Bash: Windows Job Object containment adapter가 추가된 후

지원되지 않는 환경에서는 capability 진단 결과와 이유를 표시하고 Main Agent
실행을 시작하지 않는다.

## 7. 제외 범위

- Agent Factory 웹 Workspace의 VS Code 확장화
- Work 및 Verification Agent 관리 화면
- Kanban, Dashboard, Document 또는 Artifact 관리
- Cloud/Local 실행 위치 전환
- Codex TUI 표시 또는 터미널 탭 관리
- 별도 인증 및 계정 관리
- 세션 영구 삭제
- 이전 메시지 수정 기반 Fork
- Agent별 Git worktree 또는 프로젝트 파일 격리

## 8. MVP 완료 조건

- Agent Factory 플러그인이 설치된 Linux/WSL 프로젝트에서 채팅 편집기 탭을
  열 수 있다.
- 여러 Main Agent 탭이 서로 독립적으로 병렬 실행된다.
- 새 세션, 명시적 Resume, 스트리밍, 승인, 큐, `Esc` 취소와 백그라운드 알림이
  동작한다.
- 탭을 닫았다 다시 열어도 세션과 진행 상태가 복원된다.
- 이미지·파일·폴더 DnD와 프로젝트 외부 읽기 전용 첨부가 동작한다.
- 파일 링크, 변경 목록과 Diff가 VS Code 편집기에 연결된다.
- 파일 변경 run만 스냅샷을 남기고 충돌 없는 복원이 가능하다.
- 전역, 프로젝트와 세션 설정 우선순위가 일관되게 적용된다.
- 상태바 항목을 선택하고 순서를 변경할 수 있다.
- 단위, 통합, Extension Host E2E와 패키징 검증이 통과한다.

## 9. 구현 전에 Agent Factory Runtime에서 확정할 계약

- Main 세션의 대화 기록과 이벤트 pagination 계약
- 승인 요청과 승인 응답의 비동기 프로토콜
- 세션 입력 대기열의 durable schema와 처리 순서
- 프로젝트 기본 설정의 저장 위치와 schema
- Archive/Unarchive 및 사용자 표시 이름 명령
- 파일 변경 감지, 스냅샷과 복원 명령
- 외부 읽기 전용 경로 전달 계약
- 모델 및 실행 capability 조회 명령
- macOS와 Windows containment adapter 경계

## 요청별 작업 모드

- 입력창 옆 선택 메뉴에서 직접 수정, 작업(기본), 작업·검증, 계획·작업·검증을 선택합니다.
- 선택은 저장되며 다음 전송 시 요청에 캡처합니다. 실행 중 선택을 바꿔도 현재 작업과 이미 대기 중인 요청의 모드는 유지합니다.
- 직접 수정은 Main이 수행하고, 작업은 Work 완료 후 Main의 적절한 자체 확인으로 마칩니다. 두 모드의 별도 Verification은 요청되지 않은 것으로 보고합니다.
- 검증 모드는 실패 시 같은 Work와 Verification 세션을 재사용합니다. 계획 모드는 같은 Work 스레드에서 실제 Codex Plan 모드와 실행 모드를 자동 전환합니다.
- 모든 모드에서 대화는 Main이 담당하며, 사용자 승인 정책과 실행 권한은 독립적으로 유지합니다.
- 런타임의 모드 capability가 없으면 업데이트 안내와 함께 거부하며, 기존 저장 실행과 루프의 경로는 재해석하지 않습니다.
