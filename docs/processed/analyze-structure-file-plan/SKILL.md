---
name: structure-file-plan
description: 디렉터리·파일 구현 계획 초안을 확인할 때 사용합니다.
document-type: processed
category: analyze
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/structure-file-plan.html
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
---


# 디렉터리·파일 구현 계획 초안

- 2026-09-15 · 가공 자료 · 사용자 검수 전 · 기준 커밋 ea086252119aae1dc257eca7d501e1564167f1d2

- 이번 문서는 채팅·사용량·앱 초기화·커스텀 작업 경계를 구체화한 1차 계획이다. 목표 트리의 파일 116개에 상태를 부여했으며, 그중 36개에 구체적인 함수/입출력/오류/권한/테스트 후보를 작성했다. 나머지는 책임 배치만으로 상세 기록 미완료다. 전체 저장소 파일 명세가 완성되거나 구현이 승인되었다는 뜻은 아니다. 정확한 선행 파일 ID·스키마 필드·수치·기존 심볼 대응은 추가 검수해야 한다.

- [전체 목표 트리](../../skills/rule-workbench-structure/SKILL.md#target-structure) · [명세 완료 조건](../../skills/rule-workbench-structure/SKILL.md#directory-contract) · [725개 기준 파일 대응표](../process-structure-migration-ledger/SKILL.md) · [기계 판독 기록](assets/structure-file-plan.json)

<a id="이번에-고정한-경계와-제안"></a>

## 1. 이번에 고정한 경계와 제안

- 채팅의 발신자는 사람이다. 에이전트는 권한 있는 저장 이력·변경을 MCP로 조회한다. 발송·상시 연결·알림으로 자동 실행하는 기능을 만들지 않는다.

- 실시간 사람 채팅 연결은 MCP 조회와 독립이다. 전송 기술과 채팅방 범위는 후속 결정이다.

- 동시 편집은 expected revision 기반 충돌 안내가 기본 제안이다. 마지막 저장으로 조용히 덮어쓰기 금지 방향을 검토한다. CRDT·OT·실시간 커서 공유는 승인하지 않았다.

- usage는 가격과 결제 없이 작동한다. 연결·작업 사용권은 회수·갱신·실제 실행 중단과의 정합성을 설계한다.

- 채팅/usage/코드 실행 구조는 배치안이지 숫자 한도나 특정 샌드박스 도입을 확정하는 문서가 아니다.

<a id="구현-전-결정-목록"></a>

## 2. 구현 전 결정 목록

| ID | 결정할 내용 | 영향 |
| --- | --- | --- |
| Q1 | 채팅방은 조직/워크스페이스 중 어디에 속하며 DM·비공개 채널이 필요한가? | chat channels/policies/schema 확정 전 |
| Q2 | 메시지 수정·삭제·읽음·첨부·보존 범위는? | message schema·페이지 변경 커서·저장 모델 |
| Q3 | 사람 채팅 이벤트 전송과 영속 전달 방식은? | chat_events endpoint·Redis adapter·outbox worker는 후보 |
| Q4 | 편집은 저장 리비전 충돌 안내 기본안으로 시작할 것인가? | 실시간 공동 편집 엔진은 포함하지 않음 |
| Q5 | 동시 연결·실행·메시지/조회 빈도의 초기 수치와 장애 정책은? | usage defaults·scope override·lease 만료 후 실행 처리 |
| Q6 | 로컬 빌드 격리·서비스 실행·정적 출처 제공 방식은? | deploy 파일명·빌드 adapter·보안 헤더·취소/fencing |
| Q7 | 표준 Logs/Tests/DB 화면의 상세 기능과 채팅 진입 위치는? | 기존 Reporting 보존·새 UI 파일 상세 계약 |

<a id="디렉터리-책임표"></a>

## 3. 디렉터리 책임표

- 트리에 표현된 소유 경계를 기록했다. 하위 목록은 대표 경로이며 저장소 전체 목록은 대응표와 함께 검수해야 한다. 보호 대상 feedback/·uploads/는 표의 구현 대상에서 제외했다.

<a id="D001"></a>

<a id="d001--apps--실행배포-단위-애플리케이션"></a>

### 3.1. D001 · `apps/` — 실행·배포 단위 애플리케이션

- **소유·목적**: apps / 실행·배포 단위 애플리케이션

- **허용·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/api`<br>`apps/web`<br>`apps/mcp`<br>`apps/worker`

<a id="D002"></a>

<a id="d002--appsapi--http-진입점api-서비스-흐름"></a>

### 3.2. D002 · `apps/api/` — HTTP 진입점·API 서비스 흐름

- **소유·목적**: apps/api / HTTP 진입점·API 서비스 흐름

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/api/main.py` (F001)<br>`apps/api/settings.py` (F002)<br>`apps/api/composition`<br>`apps/api/routes`<br>`apps/api/services`

<a id="D003"></a>

<a id="d003--appsapicomposition--api-의존성-조립공유-업무-판단-제외"></a>

### 3.3. D003 · `apps/api/composition/` — API 의존성 조립·공유 업무 판단 제외

- **소유·목적**: apps/api / API 의존성 조립·공유 업무 판단 제외

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/api/composition/chat.py` (F003)<br>`apps/api/composition/usage.py` (F004)

<a id="D004"></a>

<a id="d004--appsapiroutes--기능별-요청응답-계약"></a>

### 3.4. D004 · `apps/api/routes/` — 기능별 요청·응답 계약

- **소유·목적**: apps/api / 기능별 요청·응답 계약

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/api/routes/organizations.py` (F005)<br>`apps/api/routes/workspaces.py` (F006)<br>`apps/api/routes/workbenches.py` (F007)<br>`apps/api/routes/identity.py` (F008)<br>`apps/api/routes/connections.py` (F009)<br>`apps/api/routes/data_access.py` (F010)<br>`apps/api/routes/usage.py` (F011)<br>`apps/api/routes/chat.py` (F012)<br>`apps/api/routes/chat_events.py` (F013)<br>`apps/api/routes/billing.py` (F014)<br>`apps/api/routes/admin.py` (F015)

<a id="D005"></a>

<a id="d005--appsapiservices--api-흐름-조립공통-유스케이스-호출"></a>

### 3.5. D005 · `apps/api/services/` — API 흐름 조립·공통 유스케이스 호출

- **소유·목적**: apps/api / API 흐름 조립·공통 유스케이스 호출

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D006"></a>

<a id="d006--appsweb--관제-화면웹-렌더링"></a>

### 3.6. D006 · `apps/web/` — 관제 화면·웹 렌더링

- **소유·목적**: apps/web / 관제 화면·웹 렌더링

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/web/main.tsx` (F016)<br>`apps/web/App.tsx` (F017)<br>`apps/web/pages`<br>`apps/web/components`<br>`apps/web/api`

<a id="D007"></a>

<a id="d007--appswebpages--스탠다드-작업별-화면"></a>

### 3.7. D007 · `apps/web/pages/` — 스탠다드 작업별 화면

- **소유·목적**: apps/web / 스탠다드 작업별 화면

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/web/pages/organizations`<br>`apps/web/pages/workspaces`<br>`apps/web/pages/schedule`<br>`apps/web/pages/agents`<br>`apps/web/pages/documents`<br>`apps/web/pages/connections`<br>`apps/web/pages/logs`<br>`apps/web/pages/tests`<br>`apps/web/pages/db`<br>`apps/web/pages/account`<br>`apps/web/pages/admin`

<a id="D008"></a>

<a id="d008--appswebpagesorganizations--조직멤버권한-집합-관리"></a>

### 3.8. D008 · `apps/web/pages/organizations/` — 조직·멤버·권한 집합 관리

- **소유·목적**: apps/web / 조직·멤버·권한 집합 관리

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/web/pages/organizations/OrganizationWorkbench.tsx` (F018)

<a id="D009"></a>

<a id="d009--appswebpagesworkspaces--작업공간-선택관리"></a>

### 3.9. D009 · `apps/web/pages/workspaces/` — 작업공간 선택·관리

- **소유·목적**: apps/web / 작업공간 선택·관리

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/web/pages/workspaces/WorkspaceWorkbench.tsx` (F019)

<a id="D010"></a>

<a id="d010--appswebpagesschedule--일정-화면"></a>

### 3.10. D010 · `apps/web/pages/schedule/` — 일정 화면

- **소유·목적**: apps/web / 일정 화면

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/web/pages/schedule/ScheduleWorkbench.tsx` (F020)

<a id="D011"></a>

<a id="d011--appswebpagesagents--에이전트-관제-화면"></a>

### 3.11. D011 · `apps/web/pages/agents/` — 에이전트 관제 화면

- **소유·목적**: apps/web / 에이전트 관제 화면

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/web/pages/agents/AgentsWorkbench.tsx` (F021)

<a id="D012"></a>

<a id="d012--appswebpagesdocuments--문서-탐색열람편집"></a>

### 3.12. D012 · `apps/web/pages/documents/` — 문서 탐색·열람·편집

- **소유·목적**: apps/web / 문서 탐색·열람·편집

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/web/pages/documents/DocumentsWorkbench.tsx` (F022)

<a id="D013"></a>

<a id="d013--appswebpagesconnections--연동-등록연결-상태"></a>

### 3.13. D013 · `apps/web/pages/connections/` — 연동 등록·연결 상태

- **소유·목적**: apps/web / 연동 등록·연결 상태

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/web/pages/connections/ConnectionsWorkbench.tsx` (F023)

<a id="D014"></a>

<a id="d014--appswebpageslogs--허용된-작업운영-이력-조회"></a>

### 3.14. D014 · `apps/web/pages/logs/` — 허용된 작업·운영 이력 조회

- **소유·목적**: apps/web / 허용된 작업·운영 이력 조회

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/web/pages/logs/LogsWorkbench.tsx` (F024)

<a id="D015"></a>

<a id="d015--appswebpagestests--제품의-테스트-작업-화면"></a>

### 3.15. D015 · `apps/web/pages/tests/` — 제품의 테스트 작업 화면

- **소유·목적**: apps/web / 제품의 테스트 작업 화면

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/web/pages/tests/TestsWorkbench.tsx` (F025)

<a id="D016"></a>

<a id="d016--appswebpagesdb--외부-db-연결데이터-관리-화면"></a>

### 3.16. D016 · `apps/web/pages/db/` — 외부 DB 연결·데이터 관리 화면

- **소유·목적**: apps/web / 외부 DB 연결·데이터 관리 화면

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/web/pages/db/DatabaseWorkbench.tsx` (F026)

<a id="D017"></a>

<a id="d017--appswebpagesaccount--본인-계정개인-구독-관리"></a>

### 3.17. D017 · `apps/web/pages/account/` — 본인 계정·개인 구독 관리

- **소유·목적**: apps/web / 본인 계정·개인 구독 관리

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/web/pages/account/AccountWorkbench.tsx` (F027)

<a id="D018"></a>

<a id="d018--appswebpagesadmin--saas-관리자-전용-관제사용량-조회한도-조정"></a>

### 3.18. D018 · `apps/web/pages/admin/` — SaaS 관리자 전용 관제·사용량 조회·한도 조정

- **소유·목적**: apps/web / SaaS 관리자 전용 관제·사용량 조회·한도 조정

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/web/pages/admin/AdminWorkbench.tsx` (F028)

<a id="D019"></a>

<a id="d019--appswebcomponents--웹-앱에만-필요한-재사용-ui"></a>

### 3.19. D019 · `apps/web/components/` — 웹 앱에만 필요한 재사용 UI

- **소유·목적**: apps/web / 웹 앱에만 필요한 재사용 UI

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/web/components/WorkbenchHost.tsx` (F029)<br>`apps/web/components/chat`

<a id="D020"></a>

<a id="d020--appswebcomponentschat--앱-전용-채팅-ui내비게이션-위치-미정"></a>

### 3.20. D020 · `apps/web/components/chat/` — 앱 전용 채팅 UI·내비게이션 위치 미정

- **소유·목적**: apps/web / 앱 전용 채팅 UI·내비게이션 위치 미정

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/web/components/chat/ChatPanel.tsx` (F030)<br>`apps/web/components/chat/chat-state.ts` (F031)

<a id="D021"></a>

<a id="d021--appswebapi--도메인별-http-클라이언트비밀-값-금지"></a>

### 3.21. D021 · `apps/web/api/` — 도메인별 HTTP 클라이언트·비밀 값 금지

- **소유·목적**: apps/web / 도메인별 HTTP 클라이언트·비밀 값 금지

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/web/api/chat.ts` (F032)<br>`apps/web/api/usage.ts` (F033)

<a id="D022"></a>

<a id="d022--appsmcp--독립-워크스페이스-mcp공통-요청-한도-적용"></a>

### 3.22. D022 · `apps/mcp/` — 독립 워크스페이스 MCP·공통 요청 한도 적용

- **소유·목적**: apps/mcp / 독립 워크스페이스 MCP·공통 요청 한도 적용

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/mcp/main.py` (F034)<br>`apps/mcp/settings.py` (F035)<br>`apps/mcp/composition.py` (F036)<br>`apps/mcp/auth.py` (F037)<br>`apps/mcp/tools`<br>`apps/mcp/resources`<br>`apps/mcp/services`

<a id="D023"></a>

<a id="d023--appsmcptools--허용된-기능별-mcp-도구"></a>

### 3.23. D023 · `apps/mcp/tools/` — 허용된 기능별 MCP 도구

- **소유·목적**: apps/mcp / 허용된 기능별 MCP 도구

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/mcp/tools/workbenches.py` (F038)<br>`apps/mcp/tools/chat.py` (F039)<br>`apps/mcp/tools/data_access.py` (F040)

<a id="D024"></a>

<a id="d024--appsmcpresources--허용된-워크스페이스-리소스-제공"></a>

### 3.24. D024 · `apps/mcp/resources/` — 허용된 워크스페이스 리소스 제공

- **소유·목적**: apps/mcp / 허용된 워크스페이스 리소스 제공

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D025"></a>

<a id="d025--appsmcpservices--mcp-흐름-조립공통-유스케이스-호출"></a>

### 3.25. D025 · `apps/mcp/services/` — MCP 흐름 조립·공통 유스케이스 호출

- **소유·목적**: apps/mcp / MCP 흐름 조립·공통 유스케이스 호출

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D026"></a>

<a id="d026--appsworker--비동기배치스케줄러공통-실행-동시성-한도-적용"></a>

### 3.26. D026 · `apps/worker/` — 비동기·배치·스케줄러·공통 실행 동시성 한도 적용

- **소유·목적**: apps/worker / 비동기·배치·스케줄러·공통 실행 동시성 한도 적용

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/worker/main.py` (F041)<br>`apps/worker/settings.py` (F042)<br>`apps/worker/composition.py` (F043)<br>`apps/worker/celery_app.py` (F044)<br>`apps/worker/scheduler.py` (F045)<br>`apps/worker/jobs`

<a id="D027"></a>

<a id="d027--appsworkerjobs--작업-유형별-실행현재-권한-재확인"></a>

### 3.27. D027 · `apps/worker/jobs/` — 작업 유형별 실행·현재 권한 재확인

- **소유·목적**: apps/worker / 작업 유형별 실행·현재 권한 재확인

- **허용·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `apps/worker/jobs/data_access.py` (F046)<br>`apps/worker/jobs/chat_events.py` (F047)<br>`apps/worker/jobs/usage_reconcile.py` (F048)<br>`apps/worker/jobs/workbench_build.py` (F049)

<a id="D028"></a>

<a id="d028--packages--공통-구현도메인별-책임-분리"></a>

### 3.28. D028 · `packages/` — 공통 구현·도메인별 책임 분리

- **소유·목적**: packages / 공통 구현·도메인별 책임 분리

- **허용·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `packages/core`<br>`packages/adapters`<br>`packages/contracts-py`<br>`packages/contracts-ts`<br>`packages/design-system`<br>`packages/workbench-sdk`<br>`packages/workbench-build`<br>`packages/workbench-runtime`<br>`packages/workbench-editor`

<a id="D029"></a>

<a id="d029--packagescore--공통-업무-규칙유스케이스외부-구현-인터페이스"></a>

### 3.29. D029 · `packages/core/` — 공통 업무 규칙·유스케이스·외부 구현 인터페이스

- **소유·목적**: packages/core / 공통 업무 규칙·유스케이스·외부 구현 인터페이스

- **허용·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `packages/core/identity`<br>`packages/core/organizations`<br>`packages/core/workspaces`<br>`packages/core/workbenches`<br>`packages/core/agents`<br>`packages/core/planning`<br>`packages/core/scheduling`<br>`packages/core/reporting`<br>`packages/core/knowledge`<br>`packages/core/connections`<br>`packages/core/chat`<br>`packages/core/data_access`<br>`packages/core/usage`<br>`packages/core/billing`<br>`packages/core/appearance`<br>`packages/core/audit`<br>`packages/core/administration`<br>`packages/core/shared`

<a id="D030"></a>

<a id="d030--packagescoreidentity--계정인증-주체공통-인가"></a>

### 3.30. D030 · `packages/core/identity/` — 계정·인증 주체·공통 인가

- **소유·목적**: packages/core/identity / 계정·인증 주체·공통 인가

- **허용·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **이 깊이의 이유**: 업무 책임의 소유를 분리. 단일 라우터를 위해 깊이를 추가한 것이 아님

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D031"></a>

<a id="d031--packagescoreorganizations--조직초대소속권한-집합할당"></a>

### 3.31. D031 · `packages/core/organizations/` — 조직·초대·소속·권한 집합·할당

- **소유·목적**: packages/core/organizations / 조직·초대·소속·권한 집합·할당

- **허용·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **이 깊이의 이유**: 업무 책임의 소유를 분리. 단일 라우터를 위해 깊이를 추가한 것이 아님

- **하위 경로**: `packages/core/organizations/permissions.py` (F050)<br>`packages/core/organizations/permission_sets.py` (F051)<br>`packages/core/organizations/grants.py` (F052)

<a id="D032"></a>

<a id="d032--packagescoreworkspaces--개인조직-소유-작업공간의-규칙"></a>

### 3.32. D032 · `packages/core/workspaces/` — 개인·조직 소유 작업공간의 규칙

- **소유·목적**: packages/core/workspaces / 개인·조직 소유 작업공간의 규칙

- **허용·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **이 깊이의 이유**: 업무 책임의 소유를 분리. 단일 라우터를 위해 깊이를 추가한 것이 아님

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D033"></a>

<a id="d033--packagescoreworkbenches--소스빌드게시활성화-업무-규칙"></a>

### 3.33. D033 · `packages/core/workbenches/` — 소스·빌드·게시·활성화 업무 규칙

- **소유·목적**: packages/core/workbenches / 소스·빌드·게시·활성화 업무 규칙

- **허용·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **이 깊이의 이유**: 업무 책임의 소유를 분리. 단일 라우터를 위해 깊이를 추가한 것이 아님

- **하위 경로**: `packages/core/workbenches/definitions.py` (F053)<br>`packages/core/workbenches/builds.py` (F054)<br>`packages/core/workbenches/releases.py` (F055)<br>`packages/core/workbenches/activations.py` (F056)<br>`packages/core/workbenches/policies.py` (F057)<br>`packages/core/workbenches/ports.py` (F058)<br>`packages/core/workbenches/use_cases.py` (F059)

<a id="D034"></a>

<a id="d034--packagescoreagents--에이전트-관련-업무-규칙"></a>

### 3.34. D034 · `packages/core/agents/` — 에이전트 관련 업무 규칙

- **소유·목적**: packages/core/agents / 에이전트 관련 업무 규칙

- **허용·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **이 깊이의 이유**: 업무 책임의 소유를 분리. 단일 라우터를 위해 깊이를 추가한 것이 아님

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D035"></a>

<a id="d035--packagescoreplanning--계획일정-편집-규칙"></a>

### 3.35. D035 · `packages/core/planning/` — 계획·일정 편집 규칙

- **소유·목적**: packages/core/planning / 계획·일정 편집 규칙

- **허용·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **이 깊이의 이유**: 업무 책임의 소유를 분리. 단일 라우터를 위해 깊이를 추가한 것이 아님

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D036"></a>

<a id="d036--packagescorescheduling--주기실행-상태중복재시도-규칙"></a>

### 3.36. D036 · `packages/core/scheduling/` — 주기·실행 상태·중복·재시도 규칙

- **소유·목적**: packages/core/scheduling / 주기·실행 상태·중복·재시도 규칙

- **허용·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **이 깊이의 이유**: 업무 책임의 소유를 분리. 단일 라우터를 위해 깊이를 추가한 것이 아님

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D037"></a>

<a id="d037--packagescorereporting--실행-보고결과-수집-규칙"></a>

### 3.37. D037 · `packages/core/reporting/` — 실행 보고·결과 수집 규칙

- **소유·목적**: packages/core/reporting / 실행 보고·결과 수집 규칙

- **허용·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **이 깊이의 이유**: 업무 책임의 소유를 분리. 단일 라우터를 위해 깊이를 추가한 것이 아님

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D038"></a>

<a id="d038--packagescoreknowledge--문서검색패키지이력-규칙"></a>

### 3.38. D038 · `packages/core/knowledge/` — 문서·검색·패키지·이력 규칙

- **소유·목적**: packages/core/knowledge / 문서·검색·패키지·이력 규칙

- **허용·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **이 깊이의 이유**: 업무 책임의 소유를 분리. 단일 라우터를 위해 깊이를 추가한 것이 아님

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D039"></a>

<a id="d039--packagescoreconnections--연결-소유상태자격증명-수명-규칙"></a>

### 3.39. D039 · `packages/core/connections/` — 연결 소유·상태·자격증명 수명 규칙

- **소유·목적**: packages/core/connections / 연결 소유·상태·자격증명 수명 규칙

- **허용·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **이 깊이의 이유**: 업무 책임의 소유를 분리. 단일 라우터를 위해 깊이를 추가한 것이 아님

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D040"></a>

<a id="d040--packagescorechat--사람-채팅에이전트-읽기-접근-도메인"></a>

### 3.40. D040 · `packages/core/chat/` — 사람 채팅·에이전트 읽기 접근 도메인

- **소유·목적**: packages/core/chat / 사람 채팅·에이전트 읽기 접근 도메인

- **허용·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **이 깊이의 이유**: 업무 책임의 소유를 분리. 단일 라우터를 위해 깊이를 추가한 것이 아님

- **하위 경로**: `packages/core/chat/channels.py` (F060)<br>`packages/core/chat/messages.py` (F061)<br>`packages/core/chat/policies.py` (F062)<br>`packages/core/chat/ports.py` (F063)<br>`packages/core/chat/use_cases.py` (F064)

<a id="D041"></a>

<a id="d041--packagescoredata_access--후보-외부-데이터-작업의-공통-정책"></a>

### 3.41. D041 · `packages/core/data_access/` — [후보] 외부 데이터 작업의 공통 정책

- **소유·목적**: packages/core/data_access / [후보] 외부 데이터 작업의 공통 정책

- **허용·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **이 깊이의 이유**: 업무 책임의 소유를 분리. 단일 라우터를 위해 깊이를 추가한 것이 아님

- **하위 경로**: `packages/core/data_access/domain.py` (F065)<br>`packages/core/data_access/ports.py` (F066)<br>`packages/core/data_access/policies.py` (F067)<br>`packages/core/data_access/use_cases.py` (F068)

<a id="D042"></a>

<a id="d042--packagescoreusage--과금과-독립된-사용량-계측자원-한도"></a>

### 3.42. D042 · `packages/core/usage/` — 과금과 독립된 사용량 계측·자원 한도

- **소유·목적**: packages/core/usage / 과금과 독립된 사용량 계측·자원 한도

- **허용·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **이 깊이의 이유**: 업무 책임의 소유를 분리. 단일 라우터를 위해 깊이를 추가한 것이 아님

- **하위 경로**: `packages/core/usage/metrics.py` (F069)<br>`packages/core/usage/limits.py` (F070)<br>`packages/core/usage/policies.py` (F071)<br>`packages/core/usage/ports.py` (F072)<br>`packages/core/usage/use_cases.py` (F073)

<a id="D043"></a>

<a id="d043--packagescorebilling--후보-향후-구독플랜-제공-기능계측과-분리"></a>

### 3.43. D043 · `packages/core/billing/` — [후보] 향후 구독·플랜 제공 기능·계측과 분리

- **소유·목적**: packages/core/billing / [후보] 향후 구독·플랜 제공 기능·계측과 분리

- **허용·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **이 깊이의 이유**: 업무 책임의 소유를 분리. 단일 라우터를 위해 깊이를 추가한 것이 아님

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D044"></a>

<a id="d044--packagescoreappearance--테마-설정검증-규칙"></a>

### 3.44. D044 · `packages/core/appearance/` — 테마 설정·검증 규칙

- **소유·목적**: packages/core/appearance / 테마 설정·검증 규칙

- **허용·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **이 깊이의 이유**: 업무 책임의 소유를 분리. 단일 라우터를 위해 깊이를 추가한 것이 아님

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D045"></a>

<a id="d045--packagescoreaudit--조직권한실행-변경-이력"></a>

### 3.45. D045 · `packages/core/audit/` — 조직·권한·실행 변경 이력

- **소유·목적**: packages/core/audit / 조직·권한·실행 변경 이력

- **허용·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **이 깊이의 이유**: 업무 책임의 소유를 분리. 단일 라우터를 위해 깊이를 추가한 것이 아님

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D046"></a>

<a id="d046--packagescoreadministration--saas-운영자-유스케이스"></a>

### 3.46. D046 · `packages/core/administration/` — SaaS 운영자 유스케이스

- **소유·목적**: packages/core/administration / SaaS 운영자 유스케이스

- **허용·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **이 깊이의 이유**: 업무 책임의 소유를 분리. 단일 라우터를 위해 깊이를 추가한 것이 아님

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D047"></a>

<a id="d047--packagescoreshared--실제-여러-도메인이-공유하는-최소-기반"></a>

### 3.47. D047 · `packages/core/shared/` — 실제 여러 도메인이 공유하는 최소 기반

- **소유·목적**: packages/core/shared / 실제 여러 도메인이 공유하는 최소 기반

- **허용·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **이 깊이의 이유**: 업무 책임의 소유를 분리. 단일 라우터를 위해 깊이를 추가한 것이 아님

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D048"></a>

<a id="d048--packagesadapters--db비밀-정보큐외부-서비스-구현"></a>

### 3.48. D048 · `packages/adapters/` — DB·비밀 정보·큐·외부 서비스 구현

- **소유·목적**: packages/adapters / DB·비밀 정보·큐·외부 서비스 구현

- **허용·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `packages/adapters/postgres`<br>`packages/adapters/identity`<br>`packages/adapters/external_db`<br>`packages/adapters/redis`<br>`packages/adapters/object_storage`<br>`packages/adapters/workbench_build.py` (F081)<br>`packages/adapters/mcp_client`<br>`packages/adapters/http_connectors`<br>`packages/adapters/embeddings`<br>`packages/adapters/pgvector`

<a id="D049"></a>

<a id="d049--packagesadapterspostgres--플랫폼-저장테넌트-격리한도-설정사용량-이력"></a>

### 3.49. D049 · `packages/adapters/postgres/` — 플랫폼 저장·테넌트 격리·한도 설정·사용량 이력

- **소유·목적**: packages/adapters / 플랫폼 저장·테넌트 격리·한도 설정·사용량 이력

- **허용·금지 의존성**: core ports 구현·인프라 SDK 허용. 앱 import·정책 복제 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `packages/adapters/postgres/chat.py` (F074)<br>`packages/adapters/postgres/usage.py` (F075)

<a id="D050"></a>

<a id="d050--packagesadaptersidentity--암호-처리인증-제공자-연동"></a>

### 3.50. D050 · `packages/adapters/identity/` — 암호 처리·인증 제공자 연동

- **소유·목적**: packages/adapters / 암호 처리·인증 제공자 연동

- **허용·금지 의존성**: core ports 구현·인프라 SDK 허용. 앱 import·정책 복제 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D051"></a>

<a id="d051--packagesadaptersexternal_db--후보-고객-db-드라이버운영-db와-분리"></a>

### 3.51. D051 · `packages/adapters/external_db/` — [후보] 고객 DB 드라이버·운영 DB와 분리

- **소유·목적**: packages/adapters / [후보] 고객 DB 드라이버·운영 DB와 분리

- **허용·금지 의존성**: core ports 구현·인프라 SDK 허용. 앱 import·정책 복제 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `packages/adapters/external_db/postgres.py` (F076)<br>`packages/adapters/external_db/pools.py` (F077)<br>`packages/adapters/external_db/network.py` (F078)

<a id="D052"></a>

<a id="d052--packagesadaptersredis--큐공유-상태원자적-사용량-카운터만료-가능한-사용권"></a>

### 3.52. D052 · `packages/adapters/redis/` — 큐·공유 상태·원자적 사용량 카운터·만료 가능한 사용권

- **소유·목적**: packages/adapters / 큐·공유 상태·원자적 사용량 카운터·만료 가능한 사용권

- **허용·금지 의존성**: core ports 구현·인프라 SDK 허용. 앱 import·정책 복제 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `packages/adapters/redis/chat_events.py` (F079)<br>`packages/adapters/redis/usage.py` (F080)

<a id="D053"></a>

<a id="d053--packagesadaptersobject_storage--문서사용자-소스-스냅샷불변-산출물-저장"></a>

### 3.53. D053 · `packages/adapters/object_storage/` — 문서·사용자 소스 스냅샷·불변 산출물 저장

- **소유·목적**: packages/adapters / 문서·사용자 소스 스냅샷·불변 산출물 저장

- **허용·금지 의존성**: core ports 구현·인프라 SDK 허용. 앱 import·정책 복제 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D054"></a>

<a id="d054--packagesadaptersmcp_client--외부-mcp-연결-구현"></a>

### 3.54. D054 · `packages/adapters/mcp_client/` — 외부 MCP 연결 구현

- **소유·목적**: packages/adapters / 외부 MCP 연결 구현

- **허용·금지 의존성**: core ports 구현·인프라 SDK 허용. 앱 import·정책 복제 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D055"></a>

<a id="d055--packagesadaptershttp_connectors--외부-api제공자-호출-구현"></a>

### 3.55. D055 · `packages/adapters/http_connectors/` — 외부 API·제공자 호출 구현

- **소유·목적**: packages/adapters / 외부 API·제공자 호출 구현

- **허용·금지 의존성**: core ports 구현·인프라 SDK 허용. 앱 import·정책 복제 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D056"></a>

<a id="d056--packagesadaptersembeddings--임베딩-제공자-구현"></a>

### 3.56. D056 · `packages/adapters/embeddings/` — 임베딩 제공자 구현

- **소유·목적**: packages/adapters / 임베딩 제공자 구현

- **허용·금지 의존성**: core ports 구현·인프라 SDK 허용. 앱 import·정책 복제 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D057"></a>

<a id="d057--packagesadapterspgvector--문서-벡터-검색-구현"></a>

### 3.57. D057 · `packages/adapters/pgvector/` — 문서 벡터 검색 구현

- **소유·목적**: packages/adapters / 문서 벡터 검색 구현

- **허용·금지 의존성**: core ports 구현·인프라 SDK 허용. 앱 import·정책 복제 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D058"></a>

<a id="d058--packagescontracts-py--python-계약-코드생성물-원본-추적"></a>

### 3.58. D058 · `packages/contracts-py/` — Python 계약 코드·생성물 원본 추적

- **소유·목적**: packages/contracts-py / Python 계약 코드·생성물 원본 추적

- **허용·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D059"></a>

<a id="d059--packagescontracts-ts--typescript-계약-코드생성물-원본-추적"></a>

### 3.59. D059 · `packages/contracts-ts/` — TypeScript 계약 코드·생성물 원본 추적

- **소유·목적**: packages/contracts-ts / TypeScript 계약 코드·생성물 원본 추적

- **허용·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D060"></a>

<a id="d060--packagesdesign-system--공통-골격데이터-계약테마ui-자산"></a>

### 3.60. D060 · `packages/design-system/` — 공통 골격·데이터 계약·테마·UI 자산

- **소유·목적**: packages/design-system / 공통 골격·데이터 계약·테마·UI 자산

- **허용·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `packages/design-system/components`<br>`packages/design-system/theme.tsx` (F082)<br>`packages/design-system/tokens.css` (F083)<br>`packages/design-system/assets`

<a id="D061"></a>

<a id="d061--packagesdesign-systemcomponents--공통-작업-목록사이드바패널기본-ui"></a>

### 3.61. D061 · `packages/design-system/components/` — 공통 작업 목록·사이드바·패널·기본 UI

- **소유·목적**: packages/design-system / 공통 작업 목록·사이드바·패널·기본 UI

- **허용·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D062"></a>

<a id="d062--packagesdesign-systemassets--공통-아이콘시각-자산"></a>

### 3.62. D062 · `packages/design-system/assets/` — 공통 아이콘·시각 자산

- **소유·목적**: packages/design-system / 공통 아이콘·시각 자산

- **허용·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D063"></a>

<a id="d063--packagesworkbench-sdk--사용자-코드용-공개-api호스트-내부-구현-제외"></a>

### 3.63. D063 · `packages/workbench-sdk/` — 사용자 코드용 공개 API·호스트 내부 구현 제외

- **소유·목적**: packages/workbench-sdk / 사용자 코드용 공개 API·호스트 내부 구현 제외

- **허용·금지 의존성**: 공개 계약과 브라우저 통신만 허용. host runtime·core·adapters·비밀 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `packages/workbench-sdk/index.ts` (F084)<br>`packages/workbench-sdk/client.ts` (F085)<br>`packages/workbench-sdk/data.ts` (F086)<br>`packages/workbench-sdk/actions.ts` (F087)<br>`packages/workbench-sdk/context.ts` (F088)<br>`packages/workbench-sdk/theme.ts` (F089)

<a id="D064"></a>

<a id="d064--packagesworkbench-build--격리-환경-안에서-실행하는-고정-빌드-도구"></a>

### 3.64. D064 · `packages/workbench-build/` — 격리 환경 안에서 실행하는 고정 빌드 도구

- **소유·목적**: packages/workbench-build / 격리 환경 안에서 실행하는 고정 빌드 도구

- **허용·금지 의존성**: 격리된 고정 도구체인만 실행. 일반 앱 프로세스·고객 임의 명령 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `packages/workbench-build/main.ts` (F090)<br>`packages/workbench-build/validate.ts` (F091)<br>`packages/workbench-build/typecheck.ts` (F092)<br>`packages/workbench-build/bundle.ts` (F093)<br>`packages/workbench-build/artifact.ts` (F094)

<a id="D065"></a>

<a id="d065--packagesworkbench-runtime--플랫폼-측-로딩렌더링수명-관리"></a>

### 3.65. D065 · `packages/workbench-runtime/` — 플랫폼 측 로딩·렌더링·수명 관리

- **소유·목적**: packages/workbench-runtime / 플랫폼 측 로딩·렌더링·수명 관리

- **허용·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `packages/workbench-runtime/renderer.tsx` (F095)<br>`packages/workbench-runtime/SandboxHost.tsx` (F096)<br>`packages/workbench-runtime/bridge.ts` (F097)<br>`packages/workbench-runtime/bindings.ts` (F098)<br>`packages/workbench-runtime/actions.ts` (F099)<br>`packages/workbench-runtime/registry.ts` (F100)<br>`packages/workbench-runtime/view-state.ts` (F101)

<a id="D066"></a>

<a id="d066--packagesworkbench-editor--사용자-코드-작성-환경"></a>

### 3.66. D066 · `packages/workbench-editor/` — 사용자 코드 작성 환경

- **소유·목적**: packages/workbench-editor / 사용자 코드 작성 환경

- **허용·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `packages/workbench-editor/WorkbenchEditor.tsx` (F102)<br>`packages/workbench-editor/preview.tsx` (F103)<br>`packages/workbench-editor/diagnostics.ts` (F104)

<a id="D067"></a>

<a id="d067--contracts--언어-독립-계약-원본"></a>

### 3.67. D067 · `contracts/` — 언어 독립 계약 원본

- **소유·목적**: contracts / 언어 독립 계약 원본

- **허용·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `contracts/schemas`<br>`contracts/examples`<br>`contracts/compatibility`

<a id="D068"></a>

<a id="d068--contractsschemas--실제-공존-버전의-스키마"></a>

### 3.68. D068 · `contracts/schemas/` — 실제 공존 버전의 스키마

- **소유·목적**: contracts / 실제 공존 버전의 스키마

- **허용·금지 의존성**: 언어 독립 계약 원본. 생성 코드는 contracts-py/ts; 원본/생성물 소유 역전 금지

- **이 깊이의 이유**: 계약 주제·실제 공존 버전을 구분; 후보 버전은 승인 후 생성

- **하위 경로**: `contracts/schemas/workbench`<br>`contracts/schemas/catalog`<br>`contracts/schemas/appearance`<br>`contracts/schemas/usage`<br>`contracts/schemas/chat`<br>`contracts/schemas/data-access`

<a id="D069"></a>

<a id="d069--contractsschemasworkbench--등록-정보sdk-메시지릴리스화면-계약"></a>

### 3.69. D069 · `contracts/schemas/workbench/` — 등록 정보·SDK 메시지·릴리스·화면 계약

- **소유·목적**: contracts / 등록 정보·SDK 메시지·릴리스·화면 계약

- **허용·금지 의존성**: 언어 독립 계약 원본. 생성 코드는 contracts-py/ts; 원본/생성물 소유 역전 금지

- **이 깊이의 이유**: 계약 주제·실제 공존 버전을 구분; 후보 버전은 승인 후 생성

- **하위 경로**: `contracts/schemas/workbench/v1`<br>`contracts/schemas/workbench/v2`

<a id="D070"></a>

<a id="d070--contractsschemasworkbenchv1--기존-선언형-계약-보존이전-대응-후-전환"></a>

### 3.70. D070 · `contracts/schemas/workbench/v1/` — 기존 선언형 계약 보존·이전 대응 후 전환

- **소유·목적**: contracts / 기존 선언형 계약 보존·이전 대응 후 전환

- **허용·금지 의존성**: 언어 독립 계약 원본. 생성 코드는 contracts-py/ts; 원본/생성물 소유 역전 금지

- **이 깊이의 이유**: 계약 주제·실제 공존 버전을 구분; 후보 버전은 승인 후 생성

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D071"></a>

<a id="d071--contractsschemasworkbenchv2--제안-코드-기반-계약-버전미구현"></a>

### 3.71. D071 · `contracts/schemas/workbench/v2/` — 제안: 코드 기반 계약 버전·미구현

- **소유·목적**: contracts / 제안: 코드 기반 계약 버전·미구현

- **허용·금지 의존성**: 언어 독립 계약 원본. 생성 코드는 contracts-py/ts; 원본/생성물 소유 역전 금지

- **이 깊이의 이유**: 계약 주제·실제 공존 버전을 구분; 후보 버전은 승인 후 생성

- **하위 경로**: `contracts/schemas/workbench/v2/manifest.schema.json` (F105)<br>`contracts/schemas/workbench/v2/bridge.schema.json` (F106)<br>`contracts/schemas/workbench/v2/release.schema.json` (F107)

<a id="D072"></a>

<a id="d072--contractsschemascatalog--컴포넌트자산-목록-계약"></a>

### 3.72. D072 · `contracts/schemas/catalog/` — 컴포넌트·자산 목록 계약

- **소유·목적**: contracts / 컴포넌트·자산 목록 계약

- **허용·금지 의존성**: 언어 독립 계약 원본. 생성 코드는 contracts-py/ts; 원본/생성물 소유 역전 금지

- **이 깊이의 이유**: 계약 주제·실제 공존 버전을 구분; 후보 버전은 승인 후 생성

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D073"></a>

<a id="d073--contractsschemasappearance--테마-계약"></a>

### 3.73. D073 · `contracts/schemas/appearance/` — 테마 계약

- **소유·목적**: contracts / 테마 계약

- **허용·금지 의존성**: 언어 독립 계약 원본. 생성 코드는 contracts-py/ts; 원본/생성물 소유 역전 금지

- **이 깊이의 이유**: 계약 주제·실제 공존 버전을 구분; 후보 버전은 승인 후 생성

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D074"></a>

<a id="d074--contractsschemasusage--사용량한도초과-오류-계약"></a>

### 3.74. D074 · `contracts/schemas/usage/` — 사용량·한도·초과 오류 계약

- **소유·목적**: contracts / 사용량·한도·초과 오류 계약

- **허용·금지 의존성**: 언어 독립 계약 원본. 생성 코드는 contracts-py/ts; 원본/생성물 소유 역전 금지

- **이 깊이의 이유**: 계약 주제·실제 공존 버전을 구분; 후보 버전은 승인 후 생성

- **하위 경로**: `contracts/schemas/usage/v1`

<a id="D075"></a>

<a id="d075--contractsschemasusagev1--제안-첫-사용량-계약"></a>

### 3.75. D075 · `contracts/schemas/usage/v1/` — 제안: 첫 사용량 계약

- **소유·목적**: contracts / 제안: 첫 사용량 계약

- **허용·금지 의존성**: 언어 독립 계약 원본. 생성 코드는 contracts-py/ts; 원본/생성물 소유 역전 금지

- **이 깊이의 이유**: 계약 주제·실제 공존 버전을 구분; 후보 버전은 승인 후 생성

- **하위 경로**: `contracts/schemas/usage/v1/limit.schema.json` (F108)<br>`contracts/schemas/usage/v1/result.schema.json` (F109)

<a id="D076"></a>

<a id="d076--contractsschemaschat--사람-채팅읽기-전용-mcp-데이터-계약"></a>

### 3.76. D076 · `contracts/schemas/chat/` — 사람 채팅·읽기 전용 MCP 데이터 계약

- **소유·목적**: contracts / 사람 채팅·읽기 전용 MCP 데이터 계약

- **허용·금지 의존성**: 언어 독립 계약 원본. 생성 코드는 contracts-py/ts; 원본/생성물 소유 역전 금지

- **이 깊이의 이유**: 계약 주제·실제 공존 버전을 구분; 후보 버전은 승인 후 생성

- **하위 경로**: `contracts/schemas/chat/v1`

<a id="D077"></a>

<a id="d077--contractsschemaschatv1--제안-첫-채팅-계약"></a>

### 3.77. D077 · `contracts/schemas/chat/v1/` — 제안: 첫 채팅 계약

- **소유·목적**: contracts / 제안: 첫 채팅 계약

- **허용·금지 의존성**: 언어 독립 계약 원본. 생성 코드는 contracts-py/ts; 원본/생성물 소유 역전 금지

- **이 깊이의 이유**: 계약 주제·실제 공존 버전을 구분; 후보 버전은 승인 후 생성

- **하위 경로**: `contracts/schemas/chat/v1/message.schema.json` (F110)<br>`contracts/schemas/chat/v1/page.schema.json` (F111)

<a id="D078"></a>

<a id="d078--contractsschemasdata-access--후보-데이터-작업-입력출력-계약"></a>

### 3.78. D078 · `contracts/schemas/data-access/` — [후보] 데이터 작업 입력·출력 계약

- **소유·목적**: contracts / [후보] 데이터 작업 입력·출력 계약

- **허용·금지 의존성**: 언어 독립 계약 원본. 생성 코드는 contracts-py/ts; 원본/생성물 소유 역전 금지

- **이 깊이의 이유**: 계약 주제·실제 공존 버전을 구분; 후보 버전은 승인 후 생성

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D079"></a>

<a id="d079--contractsexamples--계약-예제민감-데이터-금지"></a>

### 3.79. D079 · `contracts/examples/` — 계약 예제·민감 데이터 금지

- **소유·목적**: contracts / 계약 예제·민감 데이터 금지

- **허용·금지 의존성**: 언어 독립 계약 원본. 생성 코드는 contracts-py/ts; 원본/생성물 소유 역전 금지

- **이 깊이의 이유**: 계약 주제·실제 공존 버전을 구분; 후보 버전은 승인 후 생성

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D080"></a>

<a id="d080--contractscompatibility--버전-호환성-비교-자료"></a>

### 3.80. D080 · `contracts/compatibility/` — 버전 호환성 비교 자료

- **소유·목적**: contracts / 버전 호환성 비교 자료

- **허용·금지 의존성**: 언어 독립 계약 원본. 생성 코드는 contracts-py/ts; 원본/생성물 소유 역전 금지

- **이 깊이의 이유**: 계약 주제·실제 공존 버전을 구분; 후보 버전은 승인 후 생성

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D081"></a>

<a id="d081--tests--모든-테스트앱-또는-패키지-우선-분류"></a>

### 3.81. D081 · `tests/` — 모든 테스트·앱 또는 패키지 우선 분류

- **소유·목적**: tests / 모든 테스트·앱 또는 패키지 우선 분류

- **허용·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `tests/api`<br>`tests/web`<br>`tests/mcp`<br>`tests/worker`<br>`tests/packages`<br>`tests/contracts`<br>`tests/integration`<br>`tests/support`

<a id="D082"></a>

<a id="d082--testsapi--api-테스트"></a>

### 3.82. D082 · `tests/api/` — API 테스트

- **소유·목적**: tests / API 테스트

- **허용·금지 의존성**: 테스트·보조 코드만. 실제 테스트 실행은 전체 개편 후; 운영 데이터 접근 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D083"></a>

<a id="d083--testsweb--웹브라우저-테스트"></a>

### 3.83. D083 · `tests/web/` — 웹·브라우저 테스트

- **소유·목적**: tests / 웹·브라우저 테스트

- **허용·금지 의존성**: 테스트·보조 코드만. 실제 테스트 실행은 전체 개편 후; 운영 데이터 접근 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D084"></a>

<a id="d084--testsmcp--mcp-테스트"></a>

### 3.84. D084 · `tests/mcp/` — MCP 테스트

- **소유·목적**: tests / MCP 테스트

- **허용·금지 의존성**: 테스트·보조 코드만. 실제 테스트 실행은 전체 개편 후; 운영 데이터 접근 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D085"></a>

<a id="d085--testsworker--작업-실행스케줄러-테스트"></a>

### 3.85. D085 · `tests/worker/` — 작업 실행·스케줄러 테스트

- **소유·목적**: tests / 작업 실행·스케줄러 테스트

- **허용·금지 의존성**: 테스트·보조 코드만. 실제 테스트 실행은 전체 개편 후; 운영 데이터 접근 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D086"></a>

<a id="d086--testspackages--패키지-테스트사용량-한도동시성사용권-회수-포함"></a>

### 3.86. D086 · `tests/packages/` — 패키지 테스트·사용량 한도·동시성·사용권 회수 포함

- **소유·목적**: tests / 패키지 테스트·사용량 한도·동시성·사용권 회수 포함

- **허용·금지 의존성**: 테스트·보조 코드만. 실제 테스트 실행은 전체 개편 후; 운영 데이터 접근 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D087"></a>

<a id="d087--testscontracts--계약-생성언어-간-일치호환성-테스트"></a>

### 3.87. D087 · `tests/contracts/` — 계약 생성·언어 간 일치·호환성 테스트

- **소유·목적**: tests / 계약 생성·언어 간 일치·호환성 테스트

- **허용·금지 의존성**: 테스트·보조 코드만. 실제 테스트 실행은 전체 개편 후; 운영 데이터 접근 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D088"></a>

<a id="d088--testsintegration--여러-앱에-걸친-통합-테스트"></a>

### 3.88. D088 · `tests/integration/` — 여러 앱에 걸친 통합 테스트

- **소유·목적**: tests / 여러 앱에 걸친 통합 테스트

- **허용·금지 의존성**: 테스트·보조 코드만. 실제 테스트 실행은 전체 개편 후; 운영 데이터 접근 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D089"></a>

<a id="d089--testssupport--공통-테스트-데이터보조-코드"></a>

### 3.89. D089 · `tests/support/` — 공통 테스트 데이터·보조 코드

- **소유·목적**: tests / 공통 테스트 데이터·보조 코드

- **허용·금지 의존성**: 테스트·보조 코드만. 실제 테스트 실행은 전체 개편 후; 운영 데이터 접근 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D090"></a>

<a id="d090--scripts--개발생성검증-실행-도구"></a>

### 3.90. D090 · `scripts/` — 개발·생성·검증 실행 도구

- **소유·목적**: scripts / 개발·생성·검증 실행 도구

- **허용·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `scripts/contracts`<br>`scripts/quality`

<a id="D091"></a>

<a id="d091--scriptscontracts--계약-코드-생성-도구"></a>

### 3.91. D091 · `scripts/contracts/` — 계약 코드 생성 도구

- **소유·목적**: scripts / 계약 코드 생성 도구

- **허용·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D092"></a>

<a id="d092--scriptsquality--코드-품질-검사-실행-도구설정"></a>

### 3.92. D092 · `scripts/quality/` — 코드 품질 검사 실행 도구·설정

- **소유·목적**: scripts / 코드 품질 검사 실행 도구·설정

- **허용·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D093"></a>

<a id="d093--deploy--배포-대상별-절차설정"></a>

### 3.93. D093 · `deploy/` — 배포 대상별 절차·설정

- **소유·목적**: deploy / 배포 대상별 절차·설정

- **허용·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `deploy/local`

<a id="D094"></a>

<a id="d094--deploylocal--현재-로컬-서버-배포"></a>

### 3.94. D094 · `deploy/local/` — 현재 로컬 서버 배포

- **소유·목적**: deploy / 현재 로컬 서버 배포

- **허용·금지 의존성**: 선택한 로컬 배포·자원 설정만. 업무 로직·비밀 값·미선정 기술 파일 생성 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `deploy/local/config`<br>`deploy/local/env.example` (F112)<br>`deploy/local/deploy.sh` (F113)<br>`deploy/local/rollback.sh` (F114)<br>`deploy/local/OPERATIONS.md` (F115)

<a id="D095"></a>

<a id="d095--deploylocalconfig--로컬-서비스빌드-격리산출물-제공서버-자원-상한"></a>

### 3.95. D095 · `deploy/local/config/` — 로컬 서비스·빌드 격리·산출물 제공·서버 자원 상한

- **소유·목적**: deploy / 로컬 서비스·빌드 격리·산출물 제공·서버 자원 상한

- **허용·금지 의존성**: 선택한 로컬 배포·자원 설정만. 업무 로직·비밀 값·미선정 기술 파일 생성 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D096"></a>

<a id="d096--migrations--플랫폼-db의-추가-방식-변경-이력"></a>

### 3.96. D096 · `migrations/` — 플랫폼 DB의 추가 방식 변경 이력

- **소유·목적**: migrations / 플랫폼 DB의 추가 방식 변경 이력

- **허용·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D097"></a>

<a id="d097--docs--원본조사명세-문서"></a>

### 3.97. D097 · `docs/` — 원본·조사·명세 문서

- **소유·목적**: docs / 원본·조사·명세 문서

- **허용·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: `docs/original`<br>`docs/processed`<br>`docs/specification`

<a id="D098"></a>

<a id="d098--docsoriginal--보존할-원본-자료"></a>

### 3.98. D098 · `docs/original/` — 보존할 원본 자료

- **소유·목적**: docs / 보존할 원본 자료

- **허용·금지 의존성**: 문서 단계·권위 구분. 비밀/업로드/실행 로그 저장 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D099"></a>

<a id="d099--docsprocessed--출처-기반-조사미승인-제안"></a>

### 3.99. D099 · `docs/processed/` — 출처 기반 조사·미승인 제안

- **소유·목적**: docs / 출처 기반 조사·미승인 제안

- **허용·금지 의존성**: 문서 단계·권위 구분. 비밀/업로드/실행 로그 저장 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D100"></a>

<a id="d100--docsspecification--사용자-언어-html-명세"></a>

### 3.100. D100 · `docs/specification/` — 사용자 언어 HTML 명세

- **소유·목적**: docs / 사용자 언어 HTML 명세

- **허용·금지 의존성**: 문서 단계·권위 구분. 비밀/업로드/실행 로그 저장 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D101"></a>

<a id="d101--githubworkflows--cicd-단계-연결"></a>

### 3.101. D101 · `.github/workflows/` — CI/CD 단계 연결

- **소유·목적**: .github / CI/CD 단계 연결

- **허용·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="D102"></a>

<a id="d102--codexskills--ai용-영문-명세작업-규칙"></a>

### 3.102. D102 · `.codex/skills/` — AI용 영문 명세·작업 규칙

- **소유·목적**: .codex / AI용 영문 명세·작업 규칙

- **허용·금지 의존성**: 문서 단계·권위 구분. 비밀/업로드/실행 로그 저장 금지

- **이 깊이의 이유**: 실제 실행·소유·리소스 범위를 구분. 생략된 기존 파일은 대응표에서 보존

- **하위 경로**: 정확한 하위 파일 목록 추가 명세 필요

<a id="파일별-구현-기록"></a>

## 4. 파일별 구현 기록

- 아래 테스트 경로는 향후 작성·이전할 후보이며 실제 존재나 통과를 뜻하지 않는다. 코드가 없는 새 파일에는 원본 없음으로 표시한다. 원본 후보가 있어도 분리·통합하는 정확한 심볼까지 확정된 것은 아니다.

<a id="F001"></a>

<a id="f001--appsapimainpy--구현-계약-초안--검수-전"></a>

### 4.1. F001 · `apps/api/main.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: apps/api / HTTP 앱 구성·수명 관리

- **원본·처리**: [L0101](../process-structure-migration-ledger/SKILL.md#L0101) `apps/api/main.py` (분리 후보)

- **구현할 심볼**: create_app, lifespan

- **입력 → 출력**: 검증된 API 설정 → FastAPI 앱

- **오류**: 필수 설정 누락·시작 실패·종료 오류

- **권한·상태·부수 효과**: API 인증·한도·관측 적용; MCP 생성/mount는 제거 계획

- **허용 의존성·호출 관계**: API composition/routes; adapter lifecycle

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/api/test_lifecycle.py`

- **완료·검수 조건**: 없는 api.http.endpoints 참조 제거; MCP 앱 import 없음

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 웹 정적 파일 제공 주체·실제 readiness checks

<a id="F002"></a>

<a id="f002--appsapisettingspy--책임-배치만--상세-기록-미완료"></a>

### 4.2. F002 · `apps/api/settings.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/api / API 전용 설정 검증

- **원본·처리**: [L0109](../process-structure-migration-ledger/SKILL.md#L0109) `apps/api/settings.py` (유지·설정 검토)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F003"></a>

<a id="f003--appsapicompositionchatpy--책임-배치만--상세-기록-미완료"></a>

### 4.3. F003 · `apps/api/composition/chat.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/api / 채팅 저장·권한·이벤트 서비스 조립

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F004"></a>

<a id="f004--appsapicompositionusagepy--책임-배치만--상세-기록-미완료"></a>

### 4.4. F004 · `apps/api/composition/usage.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/api / 사용량 저장소·사용권 검사 조립

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F005"></a>

<a id="f005--appsapiroutesorganizationspy--책임-배치만--상세-기록-미완료"></a>

### 4.5. F005 · `apps/api/routes/organizations.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/api / 조직·초대·멤버·권한 집합 API

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F006"></a>

<a id="f006--appsapiroutesworkspacespy--책임-배치만--상세-기록-미완료"></a>

### 4.6. F006 · `apps/api/routes/workspaces.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/api / 개인·조직 작업공간 API

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F007"></a>

<a id="f007--appsapiroutesworkbenchespy--책임-배치만--상세-기록-미완료"></a>

### 4.7. F007 · `apps/api/routes/workbenches.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/api / 소스·빌드 요청·게시·활성화 API

- **원본·처리**: [L0098](../process-structure-migration-ledger/SKILL.md#L0098) `apps/api/http/routes/workbenches.py` (이동 후보)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F008"></a>

<a id="f008--appsapiroutesidentitypy--책임-배치만--상세-기록-미완료"></a>

### 4.8. F008 · `apps/api/routes/identity.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/api / 로그인·계정·세션 API

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F009"></a>

<a id="f009--appsapiroutesconnectionspy--책임-배치만--상세-기록-미완료"></a>

### 4.9. F009 · `apps/api/routes/connections.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/api / 연결 등록·상태·자격증명 변경 API

- **원본·처리**: [L0090](../process-structure-migration-ledger/SKILL.md#L0090) `apps/api/http/routes/connections/router.py` (이동 후보)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F010"></a>

<a id="f010--appsapiroutesdata_accesspy--책임-배치만--상세-기록-미완료"></a>

### 4.10. F010 · `apps/api/routes/data_access.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/api / [후보] 외부 데이터 작업 API

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F011"></a>

<a id="f011--appsapiroutesusagepy--구현-계약-초안--검수-전"></a>

### 4.11. F011 · `apps/api/routes/usage.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: apps/api / 권한 있는 사용량 조회·한도 설정 API

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: get_usage, update_limits

- **입력 → 출력**: 허용 범위·metric·expected_revision → 사용량/새 설정

- **오류**: 금지·범위 없음·낡은 리비전·검증 오류

- **권한·상태·부수 효과**: SaaS 관리자 조정 기본; 조직 관리자의 수정 권한은 자동 부여하지 않음

- **허용 의존성·호출 관계**: API composition/usage; usage use cases

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/api/test_usage_routes.py`

- **완료·검수 조건**: 과금·자동 결제 부수 효과 없음

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 공개 API 필드·조회 권한

<a id="F012"></a>

<a id="f012--appsapirouteschatpy--구현-계약-초안--검수-전"></a>

### 4.12. F012 · `apps/api/routes/chat.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: apps/api / 사람 채팅 명령·권한 있는 이력 조회

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: send_message, list_messages, get_changes

- **입력 → 출력**: 인증 HTTP 요청 → 검증된 채팅 결과

- **오류**: 검증·권한·한도·충돌을 HTTP 응답으로 변환

- **권한·상태·부수 효과**: 서버 인증 컨텍스트로 열람 범위 확인; 사람 발송과 에이전트 읽기 경계 유지. 사용자 입력의 조직/워크스페이스 ID를 권한 증거로 사용하지 않음; 세션 쓰기의 CSRF 검사

- **허용 의존성·호출 관계**: API composition/chat; generated contracts; core chat

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/api/chat/test_routes.py`

- **완료·검수 조건**: 브라우저 발송·조회 경로가 동일 core 유스케이스 호출

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 실제 URL·동사·상태 코드 호환 계약

<a id="F013"></a>

<a id="f013--appsapirouteschat_eventspy--구현-계약-초안--검수-전"></a>

### 4.13. F013 · `apps/api/routes/chat_events.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: apps/api / 사람 클라이언트 이벤트 연결·복구·종료

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: open_chat_events, resume_chat_events

- **입력 → 출력**: 인증·채널·마지막 이벤트 위치 → 사람 클라이언트 이벤트 스트림

- **오류**: 재접속·오래된 커서·느린 수신자·권한 회수·한도 초과

- **권한·상태·부수 효과**: 연결 사용권 확보/갱신/반환; 연결 후에도 권한 회수 반영

- **허용 의존성·호출 관계**: chat use cases; usage; event adapter

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/api/chat/test_events.py`

- **완료·검수 조건**: 끊김 후 저장 이력으로 복구; 큐 무한 성장 금지

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: WebSocket/SSE 선택, 재인증 주기, 연결당 버퍼 상한

<a id="F014"></a>

<a id="f014--appsapiroutesbillingpy--책임-배치만--상세-기록-미완료"></a>

### 4.14. F014 · `apps/api/routes/billing.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/api / [후보] 향후 구독 API·실시간 한도 집행과 분리

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F015"></a>

<a id="f015--appsapiroutesadminpy--책임-배치만--상세-기록-미완료"></a>

### 4.15. F015 · `apps/api/routes/admin.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/api / SaaS 관리자 전용 API

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F016"></a>

<a id="f016--appswebmaintsx--책임-배치만--상세-기록-미완료"></a>

### 4.16. F016 · `apps/web/main.tsx` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/web / 웹 진입점

- **원본·처리**: [L0122](../process-structure-migration-ledger/SKILL.md#L0122) `apps/web/src/main.tsx` (임시 목적지)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F017"></a>

<a id="f017--appswebapptsx--책임-배치만--상세-기록-미완료"></a>

### 4.17. F017 · `apps/web/App.tsx` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/web / 작업 목록·선택적 사이드바·패널 조립

- **원본·처리**: [L0112](../process-structure-migration-ledger/SKILL.md#L0112) `apps/web/src/App.tsx` (임시 목적지)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F018"></a>

<a id="f018--appswebpagesorganizationsorganizationworkbenchtsx--책임-배치만--상세-기록-미완료"></a>

### 4.18. F018 · `apps/web/pages/organizations/OrganizationWorkbench.tsx` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/web / 조직 화면 진입·세부 동작 후속 명세

- **원본·처리**: [L0151](../process-structure-migration-ledger/SKILL.md#L0151) `apps/web/src/standard/organization/OrganizationWorkbench.tsx` (이동 후보)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F019"></a>

<a id="f019--appswebpagesworkspacesworkspaceworkbenchtsx--책임-배치만--상세-기록-미완료"></a>

### 4.19. F019 · `apps/web/pages/workspaces/WorkspaceWorkbench.tsx` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/web / 작업공간 화면 진입·세부 동작 후속 명세

- **원본·처리**: [L0162](../process-structure-migration-ledger/SKILL.md#L0162) `apps/web/src/standard/workspace/WorkspaceWorkbench.tsx` (이동 후보)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F020"></a>

<a id="f020--appswebpagesschedulescheduleworkbenchtsx--책임-배치만--상세-기록-미완료"></a>

### 4.20. F020 · `apps/web/pages/schedule/ScheduleWorkbench.tsx` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/web / 일정 화면 진입·세부 동작 후속 명세

- **원본·처리**: [L0158](../process-structure-migration-ledger/SKILL.md#L0158) `apps/web/src/standard/schedule/ScheduleWorkbench.tsx` (이동 후보)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F021"></a>

<a id="f021--appswebpagesagentsagentsworkbenchtsx--책임-배치만--상세-기록-미완료"></a>

### 4.21. F021 · `apps/web/pages/agents/AgentsWorkbench.tsx` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/web / 에이전트 화면 진입·세부 동작 후속 명세

- **원본·처리**: [L0132](../process-structure-migration-ledger/SKILL.md#L0132) `apps/web/src/standard/agents/AgentsWorkbench.tsx` (이동 후보)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F022"></a>

<a id="f022--appswebpagesdocumentsdocumentsworkbenchtsx--책임-배치만--상세-기록-미완료"></a>

### 4.22. F022 · `apps/web/pages/documents/DocumentsWorkbench.tsx` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/web / 문서 화면 진입·세부 동작 후속 명세

- **원본·처리**: [L0143](../process-structure-migration-ledger/SKILL.md#L0143) `apps/web/src/standard/documents/DocumentsWorkbench.tsx` (이동 후보)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F023"></a>

<a id="f023--appswebpagesconnectionsconnectionsworkbenchtsx--책임-배치만--상세-기록-미완료"></a>

### 4.23. F023 · `apps/web/pages/connections/ConnectionsWorkbench.tsx` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/web / 연동 화면 진입·세부 동작 후속 명세

- **원본·처리**: [L0135](../process-structure-migration-ledger/SKILL.md#L0135) `apps/web/src/standard/connections/ConnectionsWorkbench.tsx` (이동 후보)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F024"></a>

<a id="f024--appswebpageslogslogsworkbenchtsx--책임-배치만--상세-기록-미완료"></a>

### 4.24. F024 · `apps/web/pages/logs/LogsWorkbench.tsx` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/web / 로그 화면 진입·세부 동작 후속 명세

- **원본·처리**: [L0155](../process-structure-migration-ledger/SKILL.md#L0155) `apps/web/src/standard/reporting/ReportingWorkbench.tsx` (이동 후보)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F025"></a>

<a id="f025--appswebpagesteststestsworkbenchtsx--책임-배치만--상세-기록-미완료"></a>

### 4.25. F025 · `apps/web/pages/tests/TestsWorkbench.tsx` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/web / 테스트 화면 진입·세부 동작 후속 명세

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F026"></a>

<a id="f026--appswebpagesdbdatabaseworkbenchtsx--책임-배치만--상세-기록-미완료"></a>

### 4.26. F026 · `apps/web/pages/db/DatabaseWorkbench.tsx` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/web / DB 화면 진입·세부 동작 후속 명세

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F027"></a>

<a id="f027--appswebpagesaccountaccountworkbenchtsx--책임-배치만--상세-기록-미완료"></a>

### 4.27. F027 · `apps/web/pages/account/AccountWorkbench.tsx` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/web / 계정 화면 진입·세부 동작 후속 명세

- **원본·처리**: [L0125](../process-structure-migration-ledger/SKILL.md#L0125) `apps/web/src/standard/account/AccountWorkbench.tsx` (이동 후보)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F028"></a>

<a id="f028--appswebpagesadminadminworkbenchtsx--책임-배치만--상세-기록-미완료"></a>

### 4.28. F028 · `apps/web/pages/admin/AdminWorkbench.tsx` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/web / SaaS 관리 화면 진입·세부 동작 후속 명세

- **원본·처리**: [L0129](../process-structure-migration-ledger/SKILL.md#L0129) `apps/web/src/standard/admin/AdminWorkbench.tsx` (이동 후보)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F029"></a>

<a id="f029--appswebcomponentsworkbenchhosttsx--책임-배치만--상세-기록-미완료"></a>

### 4.29. F029 · `apps/web/components/WorkbenchHost.tsx` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/web / 작업 목록·선택적 사이드바·패널 배치

- **원본·처리**: [L0124](../process-structure-migration-ledger/SKILL.md#L0124) `apps/web/src/shell/WorkbenchShell.tsx` (이동·분리 후보)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F030"></a>

<a id="f030--appswebcomponentschatchatpaneltsx--구현-계약-초안--검수-전"></a>

### 4.30. F030 · `apps/web/components/chat/ChatPanel.tsx` — 구현 계약 초안 — 검수 전

- **소유·책임**: apps/web / 사람 대화 이력·발송 UI

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: ChatPanel

- **입력 → 출력**: 허용된 채널·메시지·발송 상태 → 사람 채팅 UI

- **오류**: 로딩·빈 이력·발송 실패·접근 회수 분리

- **권한·상태·부수 효과**: 본문을 코드로 실행하지 않음; 권한이 사라지면 캐시/입력 범위 정리

- **허용 의존성·호출 관계**: design-system; chat-state; web/api/chat

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/web/chat/ChatPanel.test.tsx`

- **완료·검수 조건**: 에이전트 응답 UI 없이 사람 발송·읽기 제공

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 화면 진입 위치·접근성·첨부/읽음 미정

<a id="F031"></a>

<a id="f031--appswebcomponentschatchat-statets--구현-계약-초안--검수-전"></a>

### 4.31. F031 · `apps/web/components/chat/chat-state.ts` — 구현 계약 초안 — 검수 전

- **소유·책임**: apps/web / 중복 제거·조회 커서·발송 대기 상태

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: reduceChatState, applyChatPage, reconcilePendingSend

- **입력 → 출력**: 서버 페이지/이벤트·클라이언트 발송 ID → 중복 없는 상태

- **오류**: 불연속 커서·재전송·이전 채널 응답 무시

- **권한·상태·부수 효과**: 사용자·워크스페이스·채널별 범위; 로그아웃 시 초기화

- **허용 의존성·호출 관계**: generated chat types only

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/web/chat/chat-state.test.ts`

- **완료·검수 조건**: 낙관 표시와 서버 저장 확인 구분; 순서/중복 일관성

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 메시지 수정·삭제 병합·오프라인 발송 지원 여부

<a id="F032"></a>

<a id="f032--appswebapichatts--구현-계약-초안--검수-전"></a>

### 4.32. F032 · `apps/web/api/chat.ts` — 구현 계약 초안 — 검수 전

- **소유·책임**: apps/web / 이력·발송·재접속 클라이언트

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: sendMessage, readMessages, readChanges, subscribeChat

- **입력 → 출력**: HTTP/이벤트 입력 → typed result/dispose

- **오류**: 네트워크·권한·한도·재접속 실패

- **권한·상태·부수 효과**: 현재 세션 인증; 토큰을 프레임/로그에 노출하지 않음

- **허용 의존성·호출 관계**: web HTTP client; generated contracts

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/web/chat/chat-client.test.ts`

- **완료·검수 조건**: 조회 취소·재접속·이전 컨텍스트 응답 무시

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 이벤트 전송 선택 후 subscribe 구현

<a id="F033"></a>

<a id="f033--appswebapiusagets--구현-계약-초안--검수-전"></a>

### 4.33. F033 · `apps/web/api/usage.ts` — 구현 계약 초안 — 검수 전

- **소유·책임**: apps/web / 사용량 조회·권한 있는 설정 클라이언트

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: getUsage, updateLimits

- **입력 → 출력**: metric 범위·리비전 → typed snapshot/result

- **오류**: 권한·충돌·네트워크

- **권한·상태·부수 효과**: 클라이언트에서 한도 집행이나 가격 계산하지 않음

- **허용 의존성·호출 관계**: web HTTP client; contracts

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/web/admin/usage-client.test.ts`

- **완료·검수 조건**: CAS 오류를 덮어쓰지 않고 UI에 전달

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 스키마의 정확한 필드·상한·오류 코드와 구현 순서 검수

<a id="F034"></a>

<a id="f034--appsmcpmainpy--구현-계약-초안--검수-전"></a>

### 4.34. F034 · `apps/mcp/main.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: apps/mcp / MCP 서버 구성·수명 관리

- **원본·처리**: [L0101](../process-structure-migration-ledger/SKILL.md#L0101) `apps/api/main.py` (분리 후보)<br>[L0105](../process-structure-migration-ledger/SKILL.md#L0105) `apps/api/mcp/server.py` (분리 미완료)

- **구현할 심볼**: create_mcp_server, lifespan

- **입력 → 출력**: MCP 설정·도구 등록 → 독립 서버

- **오류**: 설정/등록/전송 시작 실패

- **권한·상태·부수 효과**: 토큰 범위·현재 권한 검사; API 앱 import 금지

- **허용 의존성·호출 관계**: MCP composition/tools/resources

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/mcp/test_lifecycle.py`

- **완료·검수 조건**: API 없이 구성 가능; 연결 수명 종료 정리

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: SDK 지원 프로토콜·런처·배포 경로

<a id="F035"></a>

<a id="f035--appsmcpsettingspy--책임-배치만--상세-기록-미완료"></a>

### 4.35. F035 · `apps/mcp/settings.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/mcp / 독립 MCP 설정

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F036"></a>

<a id="f036--appsmcpcompositionpy--구현-계약-초안--검수-전"></a>

### 4.36. F036 · `apps/mcp/composition.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: apps/mcp / API import 없는 MCP 의존성 조립

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: compose_mcp_services

- **입력 → 출력**: MCP 설정·세션 자원 → 공유 유스케이스

- **오류**: 자원 생성 실패

- **권한·상태·부수 효과**: 현재 MCP 주체를 서버 컨텍스트로 매핑

- **허용 의존성·호출 관계**: core; adapters; MCP settings

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/mcp/test_composition.py`

- **완료·검수 조건**: API composition/presenter import 제거

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 기존 query installer 누락과 모든 도구 대응

<a id="F037"></a>

<a id="f037--appsmcpauthpy--책임-배치만--상세-기록-미완료"></a>

### 4.37. F037 · `apps/mcp/auth.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/mcp / 토큰 신원·범위와 공통 인가 연결

- **원본·처리**: [L0103](../process-structure-migration-ledger/SKILL.md#L0103) `apps/api/mcp/auth.py` (이동 후보)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F038"></a>

<a id="f038--appsmcptoolsworkbenchespy--책임-배치만--상세-기록-미완료"></a>

### 4.38. F038 · `apps/mcp/tools/workbenches.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/mcp / 작업 정의 관련 도구·범위 별도 명세

- **원본·처리**: [L0105](../process-structure-migration-ledger/SKILL.md#L0105) `apps/api/mcp/server.py` (분리 미완료)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F039"></a>

<a id="f039--appsmcptoolschatpy--구현-계약-초안--검수-전"></a>

### 4.39. F039 · `apps/mcp/tools/chat.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: apps/mcp / 권한 있는 채팅 이력·변경 읽기 전용 조회

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: register_chat_tools; list/read/changes handlers

- **입력 → 출력**: 인증된 MCP 도구 입력 → 제한된 채팅 페이지

- **오류**: 권한·커서·한도 오류의 MCP 표현

- **권한·상태·부수 효과**: 토큰 범위와 현재 사용자 권한의 교집합; 발송 도구 없음

- **허용 의존성·호출 관계**: MCP composition; core chat; contracts

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/mcp/test_chat_tools.py`

- **완료·검수 조건**: 연결되지 않은 기간의 메시지를 재조회 가능; 발송/자동 기동 없음

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 공개 도구명·버전·응답 상한·클라이언트 지원 확인

<a id="F040"></a>

<a id="f040--appsmcptoolsdata_accesspy--책임-배치만--상세-기록-미완료"></a>

### 4.40. F040 · `apps/mcp/tools/data_access.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/mcp / [후보] 등록 데이터 작업 호출

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F041"></a>

<a id="f041--appsworkermainpy--책임-배치만--상세-기록-미완료"></a>

### 4.41. F041 · `apps/worker/main.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/worker / 작업 실행 프로세스 진입점

- **원본·처리**: [L0172](../process-structure-migration-ledger/SKILL.md#L0172) `apps/worker/src/agent_factory_worker/main.py` (이동 후보)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F042"></a>

<a id="f042--appsworkersettingspy--책임-배치만--상세-기록-미완료"></a>

### 4.42. F042 · `apps/worker/settings.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/worker / worker 설정·큐 한도

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F043"></a>

<a id="f043--appsworkercompositionpy--책임-배치만--상세-기록-미완료"></a>

### 4.43. F043 · `apps/worker/composition.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/worker / worker 핸들러·어댑터 조립

- **원본·처리**: [L0171](../process-structure-migration-ledger/SKILL.md#L0171) `apps/worker/src/agent_factory_worker/composition.py` (이동 후보)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F044"></a>

<a id="f044--appsworkercelery_apppy--구현-계약-초안--검수-전"></a>

### 4.44. F044 · `apps/worker/celery_app.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: apps/worker / 명시적 Celery 앱·허용 핸들러 등록

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: create_celery_app, register_handlers

- **입력 → 출력**: worker 설정·허용 handler 표 → Celery 앱

- **오류**: 알 수 없는 유형·큐 설정 오류

- **권한·상태·부수 효과**: 외부 payload의 임의 callable/queue 선택 금지

- **허용 의존성·호출 관계**: worker composition/jobs/settings

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/worker/test_registration.py`

- **완료·검수 조건**: scripts 실행기가 실제 등록된 앱을 참조

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 배포명·프로세스별 동시성·우선순위

<a id="F045"></a>

<a id="f045--appsworkerschedulerpy--책임-배치만--상세-기록-미완료"></a>

### 4.45. F045 · `apps/worker/scheduler.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/worker / 주기 실행 등록·호출

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F046"></a>

<a id="f046--appsworkerjobsdata_accesspy--책임-배치만--상세-기록-미완료"></a>

### 4.46. F046 · `apps/worker/jobs/data_access.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/worker / [후보] 장기 데이터 작업·내보내기

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F047"></a>

<a id="f047--appsworkerjobschat_eventspy--구현-계약-초안--검수-전"></a>

### 4.47. F047 · `apps/worker/jobs/chat_events.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: apps/worker / 후보: 저장된 채팅 이벤트 전달·에이전트 기동 아님

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: relay_chat_events

- **입력 → 출력**: 저장된 미전달 이벤트 → 전송 및 시도 기록

- **오류**: 중복·브로커 장애·재시도 소진

- **권한·상태·부수 효과**: 사용자 권한을 우회한 채팅 조회·에이전트 기동 금지

- **허용 의존성·호출 관계**: core chat ports; adapters; worker composition

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/worker/test_chat_events.py`

- **완료·검수 조건**: DB 저장 후 전달 실패를 복구; 같은 이벤트 중복에 안전

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: outbox 채택 시 구현; 원자적 claim·재시도 예산

<a id="F048"></a>

<a id="f048--appsworkerjobsusage_reconcilepy--구현-계약-초안--검수-전"></a>

### 4.48. F048 · `apps/worker/jobs/usage_reconcile.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: apps/worker / 사용권 만료·정합성 회수 요청

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: reconcile_usage_leases

- **입력 → 출력**: 만료/실행 상태 조회 → 회수·갱신·경고 결과

- **오류**: 브로커 장애·상태 불일치·상실 사용권

- **권한·상태·부수 효과**: 만료된 사용권으로 계속 실행 중인 작업을 식별; 무관한 작업 강제 종료 금지

- **허용 의존성·호출 관계**: usage use cases; scheduling execution port

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/worker/test_usage_reconcile.py`

- **완료·검수 조건**: 회수 재실행에 안전; 점유 수와 실제 작업 차이 보고

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 자동 취소·fencing·운영 개입 기준

<a id="F049"></a>

<a id="f049--appsworkerjobsworkbench_buildpy--책임-배치만--상세-기록-미완료"></a>

### 4.49. F049 · `apps/worker/jobs/workbench_build.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: apps/worker / 격리 빌드 요청 전달·상태·결과 처리

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 자기 앱과 공개 packages만 사용. 다른 앱 import 금지; 공유 업무 규칙은 core

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F050"></a>

<a id="f050--packagescoreorganizationspermissionspy--책임-배치만--상세-기록-미완료"></a>

### 4.50. F050 · `packages/core/organizations/permissions.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/core/organizations / 행위 권한 목록·허용 범위 정의

- **원본·처리**: [L0418](../process-structure-migration-ledger/SKILL.md#L0418) `packages/platform-core/src/agent_factory_core/organizations/permissions.py` (이동 후보)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F051"></a>

<a id="f051--packagescoreorganizationspermission_setspy--책임-배치만--상세-기록-미완료"></a>

### 4.51. F051 · `packages/core/organizations/permission_sets.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/core/organizations / 권한 집합 구성·변경·검증

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F052"></a>

<a id="f052--packagescoreorganizationsgrantspy--책임-배치만--상세-기록-미완료"></a>

### 4.52. F052 · `packages/core/organizations/grants.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/core/organizations / 사용자·권한 집합·대상 범위 할당

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F053"></a>

<a id="f053--packagescoreworkbenchesdefinitionspy--구현-계약-초안--검수-전"></a>

### 4.53. F053 · `packages/core/workbenches/definitions.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: packages/core/workbenches / 소스 스냅샷·초안·소유 규칙

- **원본·처리**: [L0428](../process-structure-migration-ledger/SKILL.md#L0428) `packages/platform-core/src/agent_factory_core/workbenches/domain.py` (분리·통합 미완료)

- **구현할 심볼**: WorkbenchDefinition, SourceSnapshot

- **입력 → 출력**: source revision·소유 범위 → 초안 스냅샷

- **오류**: 낡은 expected revision·잘못된 소스

- **권한·상태·부수 효과**: 소스 열람과 실행 권한 분리

- **허용 의존성·호출 관계**: workbench ports; shared

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/packages/core/workbenches/test_definitions.py`

- **완료·검수 조건**: 기존 JSON 정의를 자동 폐기하지 않음

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 소유 범위·저장 충돌 기본안 검수

<a id="F054"></a>

<a id="f054--packagescoreworkbenchesbuildspy--책임-배치만--상세-기록-미완료"></a>

### 4.54. F054 · `packages/core/workbenches/builds.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/core/workbenches / 빌드 요청·상태 전이

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F055"></a>

<a id="f055--packagescoreworkbenchesreleasespy--책임-배치만--상세-기록-미완료"></a>

### 4.55. F055 · `packages/core/workbenches/releases.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/core/workbenches / 불변 게시 버전·호환성

- **원본·처리**: [L0428](../process-structure-migration-ledger/SKILL.md#L0428) `packages/platform-core/src/agent_factory_core/workbenches/domain.py` (분리·통합 미완료)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F056"></a>

<a id="f056--packagescoreworkbenchesactivationspy--구현-계약-초안--검수-전"></a>

### 4.56. F056 · `packages/core/workbenches/activations.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: packages/core/workbenches / 워크스페이스별 릴리스 선택·롤백

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: WorkbenchActivation, ActivateRelease, RollbackActivation

- **입력 → 출력**: workspace·release·expected_revision → 활성화 기록

- **오류**: 게시되지 않은 릴리스·호환성·낡은 설정·차단 버전

- **권한·상태·부수 효과**: 사용 기능 승인과 현재 사용자 권한 재검사

- **허용 의존성·호출 관계**: workbench release/policies/ports

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/packages/core/workbenches/test_activations.py`

- **완료·검수 조건**: 게시와 활성화 분리; rollback으로 보안 차단 우회 금지

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 스키마의 정확한 필드·상한·오류 코드와 구현 순서 검수

<a id="F057"></a>

<a id="f057--packagescoreworkbenchespoliciespy--책임-배치만--상세-기록-미완료"></a>

### 4.57. F057 · `packages/core/workbenches/policies.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/core/workbenches / 작성·게시·활성화·실행 권한

- **원본·처리**: [L0430](../process-structure-migration-ledger/SKILL.md#L0430) `packages/platform-core/src/agent_factory_core/workbenches/policies.py` (이동 후보)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F058"></a>

<a id="f058--packagescoreworkbenchesportspy--책임-배치만--상세-기록-미완료"></a>

### 4.58. F058 · `packages/core/workbenches/ports.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/core/workbenches / 저장소·산출물·격리 빌드 인터페이스

- **원본·처리**: [L0431](../process-structure-migration-ledger/SKILL.md#L0431) `packages/platform-core/src/agent_factory_core/workbenches/ports.py` (이동 후보)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F059"></a>

<a id="f059--packagescoreworkbenchesuse_casespy--책임-배치만--상세-기록-미완료"></a>

### 4.59. F059 · `packages/core/workbenches/use_cases.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/core/workbenches / 공유 업무 흐름

- **원본·처리**: [L0427](../process-structure-migration-ledger/SKILL.md#L0427) `packages/platform-core/src/agent_factory_core/workbenches/commands.py` (분리·통합 미완료)<br>[L0432](../process-structure-migration-ledger/SKILL.md#L0432) `packages/platform-core/src/agent_factory_core/workbenches/queries.py` (분리·통합 미완료)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F060"></a>

<a id="f060--packagescorechatchannelspy--구현-계약-초안--검수-전"></a>

### 4.60. F060 · `packages/core/chat/channels.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: packages/core/chat / 대화방 식별·참여 모델

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: ChatChannel, ChannelMembership

- **입력 → 출력**: 범위 참조·채널 ID·사람 참여자 → 채널 상태

- **오류**: 잘못된 범위·중복 참여 상태 거절

- **권한·상태·부수 효과**: 서버 인증 컨텍스트로 열람 범위 확인; 사람 발송과 에이전트 읽기 경계 유지. 사용자 입력의 조직/워크스페이스 ID를 권한 증거로 사용하지 않음

- **허용 의존성·호출 관계**: core identity/organizations/workspaces의 공개 권한 계약

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/packages/core/chat/test_channels.py`

- **완료·검수 조건**: 채널 소유와 열람 권한 관계가 명확하며 DB/HTTP import 없음

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 조직/워크스페이스 채널·DM·비공개 채널 범위 미정

<a id="F061"></a>

<a id="f061--packagescorechatmessagespy--구현-계약-초안--검수-전"></a>

### 4.61. F061 · `packages/core/chat/messages.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: packages/core/chat / 메시지 식별·버전·정렬

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: ChatMessage, MessageCursor, SendMessageInput

- **입력 → 출력**: 발신자·채널·클라이언트 요청 ID·본문 → 메시지 식별자·서버 시각·정렬 위치

- **오류**: 본문 상한·잘못된 커서·같은 요청 ID의 다른 내용

- **권한·상태·부수 효과**: 서버 인증 컨텍스트로 열람 범위 확인; 사람 발송과 에이전트 읽기 경계 유지. 사용자 입력의 조직/워크스페이스 ID를 권한 증거로 사용하지 않음

- **허용 의존성·호출 관계**: chat channels; shared errors

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/packages/core/chat/test_messages.py`

- **완료·검수 조건**: 같은 요청 재전달의 중복과 메시지 순서 계약 정의

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 수정·삭제·첨부·읽음·보존 정책 미정; timestamp만으로 순서 보장하지 않음

<a id="F062"></a>

<a id="f062--packagescorechatpoliciespy--구현-계약-초안--검수-전"></a>

### 4.62. F062 · `packages/core/chat/policies.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: packages/core/chat / 사람 발송·범위별 열람 권한

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: require_read_chat, require_human_send

- **입력 → 출력**: 인증 주체·채널·요청 동작 → 허용 또는 거절

- **오류**: 권한 회수·주체 유형·범위 불일치 거절

- **권한·상태·부수 효과**: 서버 인증 컨텍스트로 열람 범위 확인; 사람 발송과 에이전트 읽기 경계 유지. 사용자 입력의 조직/워크스페이스 ID를 권한 증거로 사용하지 않음

- **허용 의존성·호출 관계**: identity authorization; usage 공개 계약

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/packages/core/chat/test_policies.py`

- **완료·검수 조건**: MCP/에이전트는 발송 불가; 표시 여부와 독립된 인가

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 사람의 브라우저 세션과 위임된 토큰 식별 규칙 상세화

<a id="F063"></a>

<a id="f063--packagescorechatportspy--구현-계약-초안--검수-전"></a>

### 4.63. F063 · `packages/core/chat/ports.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: packages/core/chat / 이력 저장 트랜잭션·이벤트 전달 인터페이스

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: ChatRepository, ChatTransaction, ChatEventPublisher

- **입력 → 출력**: 저장·페이지 조회·변경 조회·이벤트 전달의 인터페이스

- **오류**: 오류를 저장/전달/커서 만료로 구분

- **권한·상태·부수 효과**: 저장·조회마다 인증 범위 전달

- **허용 의존성·호출 관계**: chat models; typing Protocol

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/packages/core/chat/test_ports.py`

- **완료·검수 조건**: DB 저장과 전송 간 실패를 숨기지 않는 계약

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 영속 이벤트 outbox 채택·커서 수명 결정

<a id="F064"></a>

<a id="f064--packagescorechatuse_casespy--구현-계약-초안--검수-전"></a>

### 4.64. F064 · `packages/core/chat/use_cases.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: packages/core/chat / 발송·열람·변경 조회 흐름

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: SendChatMessage, ReadChatMessages, GetChatChanges

- **입력 → 출력**: 주체·채널·요청 ID/커서/상한 → 저장 결과 또는 페이지

- **오류**: 권한·한도·멱등 충돌·저장 실패·만료 커서

- **권한·상태·부수 효과**: 서버 인증 컨텍스트로 열람 범위 확인; 사람 발송과 에이전트 읽기 경계 유지. 사용자 입력의 조직/워크스페이스 ID를 권한 증거로 사용하지 않음; 사용량 검사·저장·이벤트 기록의 원자성 설계

- **허용 의존성·호출 관계**: chat ports/policies; usage use cases

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/packages/core/chat/test_use_cases.py`

- **완료·검수 조건**: 중복 발송 방지; 권한 변경 후 조회 차단; 저장 성공과 전달 실패 구분

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 페이지 상한·커서 복구·수정/삭제 이벤트 정책

<a id="F065"></a>

<a id="f065--packagescoredata_accessdomainpy--책임-배치만--상세-기록-미완료"></a>

### 4.65. F065 · `packages/core/data_access/domain.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/core/data_access / [후보] 데이터 작업·버전·실행 상태

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F066"></a>

<a id="f066--packagescoredata_accessportspy--책임-배치만--상세-기록-미완료"></a>

### 4.66. F066 · `packages/core/data_access/ports.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/core/data_access / [후보] 실행·스키마 조회·저장 인터페이스

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F067"></a>

<a id="f067--packagescoredata_accesspoliciespy--책임-배치만--상세-기록-미완료"></a>

### 4.67. F067 · `packages/core/data_access/policies.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/core/data_access / [후보] 입력·범위·실행 한도

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F068"></a>

<a id="f068--packagescoredata_accessuse_casespy--책임-배치만--상세-기록-미완료"></a>

### 4.68. F068 · `packages/core/data_access/use_cases.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/core/data_access / [후보] 등록·게시·실행·취소

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F069"></a>

<a id="f069--packagescoreusagemetricspy--구현-계약-초안--검수-전"></a>

### 4.69. F069 · `packages/core/usage/metrics.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: packages/core/usage / 계측 항목·단위·측정 의미

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: MetricDefinition, MetricKind

- **입력 → 출력**: 항목 키·단위·gauge/window/total 종류 → 검증된 정의

- **오류**: 중복 키·단위 혼용·잘못된 측정 종류

- **권한·상태·부수 효과**: 사용자 원문/비밀을 계측 레이블에 넣지 않음

- **허용 의존성·호출 관계**: shared types only

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/packages/core/usage/test_metrics.py`

- **완료·검수 조건**: 메시지/바이트/연결/작업 단위 구분

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 실제 항목 목록·집계 윈도우

<a id="F070"></a>

<a id="f070--packagescoreusagelimitspy--구현-계약-초안--검수-전"></a>

### 4.70. F070 · `packages/core/usage/limits.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: packages/core/usage / 시스템 기본값·조직·워크스페이스별 한도 설정

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: LimitSetting, LimitScope

- **입력 → 출력**: 시스템/조직/워크스페이스 값·리비전 → 설정 모델

- **오류**: 음수·지원하지 않는 단위·수정 리비전 충돌

- **권한·상태·부수 효과**: 할당 범위가 한도 수정 권한을 부여하지 않음

- **허용 의존성·호출 관계**: usage metrics; shared errors

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/packages/core/usage/test_limits.py`

- **완료·검수 조건**: 요금·플랜 의존성 없이 설정 가능

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 0·미설정·무제한 의미와 상속 우선순위

<a id="F071"></a>

<a id="f071--packagescoreusagepoliciespy--구현-계약-초안--검수-전"></a>

### 4.71. F071 · `packages/core/usage/policies.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: packages/core/usage / 유효 한도 결정·초과 처리 판단

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: resolve_effective_limit, decide_admission

- **입력 → 출력**: 권한 확인 후 범위·설정·현재 사용량·요청량 → 허용/거절/대기 판단

- **오류**: 상한 초과·계측 불가·충돌

- **권한·상태·부수 효과**: 조직별 설정은 서버 전체 안전 상한을 우회하지 않음

- **허용 의존성·호출 관계**: usage limits/metrics

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/packages/core/usage/test_policies.py`

- **완료·검수 조건**: billing import 없음; 정책 결정과 카운터 집행 분리

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 한도 축소 시 기존 연결·작업 처리

<a id="F072"></a>

<a id="f072--packagescoreusageportspy--구현-계약-초안--검수-전"></a>

### 4.72. F072 · `packages/core/usage/ports.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: packages/core/usage / 계측·저장·원자적 사용권 확보 인터페이스

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: UsageRepository, CapacityLeaseStore, UsageMeter

- **입력 → 출력**: 원자적 acquire/renew/release·설정 CAS·사용량 읽기 계약

- **오류**: 사용권 만료/중복 반환/저장소 장애

- **권한·상태·부수 효과**: 범위·요청 ID·점유자 식별자를 명시

- **허용 의존성·호출 관계**: usage types; typing Protocol

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/packages/core/usage/test_ports.py`

- **완료·검수 조건**: 단순 read+increment 구현으로 대체 불가

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 다중 범위 동시 예약 원자성·실패 정책

<a id="F073"></a>

<a id="f073--packagescoreusageuse_casespy--구현-계약-초안--검수-전"></a>

### 4.73. F073 · `packages/core/usage/use_cases.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: packages/core/usage / 조회·설정·사용권 확보·갱신·반환

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: GetUsage, UpdateLimits, AcquireCapacity, RenewCapacity, ReleaseCapacity

- **입력 → 출력**: 인증 컨텍스트·metric·요청량·멱등 키 → snapshot/lease/decision

- **오류**: 권한·리비전·한도·사용권 상실·저장소 실패

- **권한·상태·부수 효과**: 한도 변경은 audit 기록; billing 없이 동작

- **허용 의존성·호출 관계**: usage ports/policies; audit port; identity

- **제외 책임·금지 의존성**: 도메인 모델·정책·ports만 사용. apps/adapters/DB/큐/웹 프레임워크 import 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/packages/core/usage/test_use_cases.py`

- **완료·검수 조건**: 재시도 중복 계측·반환 방지; 비정상 종료 회수

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 사용권 만료와 실제 작업 종료 연결·집계 보존

<a id="F074"></a>

<a id="f074--packagesadapterspostgreschatpy--구현-계약-초안--검수-전"></a>

### 4.74. F074 · `packages/adapters/postgres/chat.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: packages/adapters / 채팅 저장·커서 조회·트랜잭션 이벤트 기록

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: PostgresChatRepository, ChatTransaction

- **입력 → 출력**: 범위·요청 ID·메시지 → 저장 결과/이력/변경 페이지

- **오류**: 고유키 충돌·재시도 가능한 DB 오류·커서 범위 불일치

- **권한·상태·부수 효과**: RLS+서버 인가; 동일 요청 ID 중복 방지; 메시지와 이벤트 기록 트랜잭션

- **허용 의존성·호출 관계**: core chat ports; postgres session/tenant

- **제외 책임·금지 의존성**: core ports 구현·인프라 SDK 허용. 앱 import·정책 복제 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/packages/adapters/test_chat_postgres.py`

- **완료·검수 조건**: 동시 발송 순서·페이지 누락·다른 조직 접근 차단

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 마이그레이션 번호·DDL·색인·이벤트 순번 정책

<a id="F075"></a>

<a id="f075--packagesadapterspostgresusagepy--구현-계약-초안--검수-전"></a>

### 4.75. F075 · `packages/adapters/postgres/usage.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: packages/adapters / 한도 설정 이력·영속 계측 저장

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: PostgresUsageRepository

- **입력 → 출력**: 설정 리비전·집계 배치 → 영속 설정/사용량 이력

- **오류**: 낡은 리비전·중복 집계·트랜잭션 오류

- **권한·상태·부수 효과**: RLS 및 관리자 인가; 감사 이력 일관성

- **허용 의존성·호출 관계**: usage ports; postgres session/tenant

- **제외 책임·금지 의존성**: core ports 구현·인프라 SDK 허용. 앱 import·정책 복제 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/packages/adapters/test_usage_postgres.py`

- **완료·검수 조건**: 설정 변경 충돌·집계 중복·범위별 조회 검증

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 집계 주기·보존 기간·DDL

<a id="F076"></a>

<a id="f076--packagesadaptersexternal_dbpostgrespy--책임-배치만--상세-기록-미완료"></a>

### 4.76. F076 · `packages/adapters/external_db/postgres.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/adapters / [후보] 외부 PostgreSQL 실행·스키마 조회

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: core ports 구현·인프라 SDK 허용. 앱 import·정책 복제 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F077"></a>

<a id="f077--packagesadaptersexternal_dbpoolspy--책임-배치만--상세-기록-미완료"></a>

### 4.77. F077 · `packages/adapters/external_db/pools.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/adapters / [후보] 연결별 풀·상한·회수

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: core ports 구현·인프라 SDK 허용. 앱 import·정책 복제 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F078"></a>

<a id="f078--packagesadaptersexternal_dbnetworkpy--책임-배치만--상세-기록-미완료"></a>

### 4.78. F078 · `packages/adapters/external_db/network.py` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/adapters / [후보] 목적지·TLS·접속 경로 검증

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: core ports 구현·인프라 SDK 허용. 앱 import·정책 복제 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F079"></a>

<a id="f079--packagesadaptersredischat_eventspy--구현-계약-초안--검수-전"></a>

### 4.79. F079 · `packages/adapters/redis/chat_events.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: packages/adapters / 실시간 이벤트 전달·채팅 이력 원본 아님

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: RedisChatEventPublisher, ChatEventSubscription

- **입력 → 출력**: 저장된 이벤트 참조 → 구독자 알림

- **오류**: 전달 실패·재연결·중복은 이력 재조회로 수렴

- **권한·상태·부수 효과**: 메시지 원본 저장소 아님; 채널 격리·payload 제한

- **허용 의존성·호출 관계**: chat event port; Redis

- **제외 책임·금지 의존성**: core ports 구현·인프라 SDK 허용. 앱 import·정책 복제 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/packages/adapters/test_chat_events.py`

- **완료·검수 조건**: 전달 중복을 허용하되 누락 복구 계약 제공

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: Pub/Sub/Streams 선정·소비 위치 보존

<a id="F080"></a>

<a id="f080--packagesadaptersredisusagepy--구현-계약-초안--검수-전"></a>

### 4.80. F080 · `packages/adapters/redis/usage.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: packages/adapters / 원자적 카운터·사용권·갱신·반환

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: RedisCapacityLeaseStore, RedisUsageMeter

- **입력 → 출력**: 한도·범위·요청 ID → 원자적 카운터/사용권

- **오류**: 분산 경합·연결 장애·TTL 만료·이중 반환

- **권한·상태·부수 효과**: 테넌트 키 격리; 제한된 Lua/transaction 등 구현 기술 후속 선택

- **허용 의존성·호출 관계**: usage ports; Redis

- **제외 책임·금지 의존성**: core ports 구현·인프라 SDK 허용. 앱 import·정책 복제 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/packages/adapters/test_usage_redis.py`

- **완료·검수 조건**: 동시 획득에서 상한 초과 방지·중복 해제 안전

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: Redis failover 시 보장·gauge 재조정 방식

<a id="F081"></a>

<a id="f081--packagesadaptersworkbench_buildpy--구현-계약-초안--검수-전"></a>

### 4.81. F081 · `packages/adapters/workbench_build.py` — 구현 계약 초안 — 검수 전

- **소유·책임**: packages/adapters / 격리 빌드 환경 생성·호출·취소·회수

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: IsolatedWorkbenchBuilder

- **입력 → 출력**: 빌드 작업·스냅샷 → 격리 실행 결과

- **오류**: 시간 초과·취소·회수 실패·손상 산출물

- **권한·상태·부수 효과**: 작업별 파일/네트워크/자원 경계·사용권 유지

- **허용 의존성·호출 관계**: core workbenches ports; usage; selected isolation provider

- **제외 책임·금지 의존성**: core ports 구현·인프라 SDK 허용. 앱 import·정책 복제 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/packages/adapters/test_workbench_build.py`

- **완료·검수 조건**: worker 프로세스 직접 실행 금지; 종료 후 환경 회수

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 로컬 격리 기술 미선정

<a id="F082"></a>

<a id="f082--packagesdesign-systemthemetsx--책임-배치만--상세-기록-미완료"></a>

### 4.82. F082 · `packages/design-system/theme.tsx` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/design-system / 테마 제공·전환

- **원본·처리**: [L0284](../process-structure-migration-ledger/SKILL.md#L0284) `packages/design-system/src/theme.tsx` (이동·분리 검토)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F083"></a>

<a id="f083--packagesdesign-systemtokenscss--책임-배치만--상세-기록-미완료"></a>

### 4.83. F083 · `packages/design-system/tokens.css` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/design-system / 공통 시각 토큰

- **원본·처리**: [L0285](../process-structure-migration-ledger/SKILL.md#L0285) `packages/design-system/src/tokens.css` (이동·분리 검토)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F084"></a>

<a id="f084--packagesworkbench-sdkindexts--책임-배치만--상세-기록-미완료"></a>

### 4.84. F084 · `packages/workbench-sdk/index.ts` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/workbench-sdk / 공개 export

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 공개 계약과 브라우저 통신만 허용. host runtime·core·adapters·비밀 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F085"></a>

<a id="f085--packagesworkbench-sdkclientts--구현-계약-초안--검수-전"></a>

### 4.85. F085 · `packages/workbench-sdk/client.ts` — 구현 계약 초안 — 검수 전

- **소유·책임**: packages/workbench-sdk / 호스트 통신 클라이언트

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: createWorkbenchClient, dispose

- **입력 → 출력**: 호스트 연결·공개 SDK 호출 → bounded typed promise

- **오류**: 시간 초과·연결 종료·프로토콜 불일치

- **권한·상태·부수 효과**: 호스트 권한/토큰 노출 없음; SDK는 인가 경계 아님

- **허용 의존성·호출 관계**: contracts-ts; public protocol only

- **제외 책임·금지 의존성**: 공개 계약과 브라우저 통신만 허용. host runtime·core·adapters·비밀 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/packages/workbench-sdk/client.test.ts`

- **완료·검수 조건**: runtime 내부 import 없이 동작

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 정확한 handshake·취소·재연결 정책

<a id="F086"></a>

<a id="f086--packagesworkbench-sdkdatats--책임-배치만--상세-기록-미완료"></a>

### 4.86. F086 · `packages/workbench-sdk/data.ts` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/workbench-sdk / 허용된 데이터 동작 요청

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 공개 계약과 브라우저 통신만 허용. host runtime·core·adapters·비밀 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F087"></a>

<a id="f087--packagesworkbench-sdkactionsts--책임-배치만--상세-기록-미완료"></a>

### 4.87. F087 · `packages/workbench-sdk/actions.ts` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/workbench-sdk / 실행·탐색 요청

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 공개 계약과 브라우저 통신만 허용. host runtime·core·adapters·비밀 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F088"></a>

<a id="f088--packagesworkbench-sdkcontextts--책임-배치만--상세-기록-미완료"></a>

### 4.88. F088 · `packages/workbench-sdk/context.ts` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/workbench-sdk / 화면 컨텍스트·변경 구독

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 공개 계약과 브라우저 통신만 허용. host runtime·core·adapters·비밀 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F089"></a>

<a id="f089--packagesworkbench-sdkthemets--책임-배치만--상세-기록-미완료"></a>

### 4.89. F089 · `packages/workbench-sdk/theme.ts` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/workbench-sdk / 호스트 테마 연결

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 공개 계약과 브라우저 통신만 허용. host runtime·core·adapters·비밀 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F090"></a>

<a id="f090--packagesworkbench-buildmaints--구현-계약-초안--검수-전"></a>

### 4.90. F090 · `packages/workbench-build/main.ts` — 구현 계약 초안 — 검수 전

- **소유·책임**: packages/workbench-build / 내부 빌드 도구 진입점

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: runBuild

- **입력 → 출력**: 고정 빌드 입력·소스 참조 → 산출물/진단

- **오류**: 검증·타입·번들·자원 제한 실패

- **권한·상태·부수 효과**: 격리 환경 안에서만 실행; 운영 비밀 없음

- **허용 의존성·호출 관계**: build validate/typecheck/bundle/artifact

- **제외 책임·금지 의존성**: 격리된 고정 도구체인만 실행. 일반 앱 프로세스·고객 임의 명령 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/packages/workbench-build/main.test.ts`

- **완료·검수 조건**: 플랫폼 고정 진입; 사용자 임의 build script 실행 금지

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 번들러·격리 실행 프로토콜·버전

<a id="F091"></a>

<a id="f091--packagesworkbench-buildvalidatets--책임-배치만--상세-기록-미완료"></a>

### 4.91. F091 · `packages/workbench-build/validate.ts` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/workbench-build / 소스·등록 정보·의존성 정책 검사

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 격리된 고정 도구체인만 실행. 일반 앱 프로세스·고객 임의 명령 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F092"></a>

<a id="f092--packagesworkbench-buildtypecheckts--책임-배치만--상세-기록-미완료"></a>

### 4.92. F092 · `packages/workbench-build/typecheck.ts` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/workbench-build / 타입 검사·진단

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 격리된 고정 도구체인만 실행. 일반 앱 프로세스·고객 임의 명령 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F093"></a>

<a id="f093--packagesworkbench-buildbundlets--책임-배치만--상세-기록-미완료"></a>

### 4.93. F093 · `packages/workbench-build/bundle.ts` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/workbench-build / 고정 도구체인으로 번들 생성

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 격리된 고정 도구체인만 실행. 일반 앱 프로세스·고객 임의 명령 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F094"></a>

<a id="f094--packagesworkbench-buildartifactts--책임-배치만--상세-기록-미완료"></a>

### 4.94. F094 · `packages/workbench-build/artifact.ts` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/workbench-build / 파일 목록·해시·빌드 메타데이터

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 격리된 고정 도구체인만 실행. 일반 앱 프로세스·고객 임의 명령 금지

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F095"></a>

<a id="f095--packagesworkbench-runtimerenderertsx--책임-배치만--상세-기록-미완료"></a>

### 4.95. F095 · `packages/workbench-runtime/renderer.tsx` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/workbench-runtime / 신뢰된 표준 화면·격리된 커스텀 화면 선택

- **원본·처리**: [L0449](../process-structure-migration-ledger/SKILL.md#L0449) `packages/workbench-runtime/src/renderer.tsx` (이동·분리 검토)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F096"></a>

<a id="f096--packagesworkbench-runtimesandboxhosttsx--구현-계약-초안--검수-전"></a>

### 4.96. F096 · `packages/workbench-runtime/SandboxHost.tsx` — 구현 계약 초안 — 검수 전

- **소유·책임**: packages/workbench-runtime / 격리 화면 생성·종료·복구·구체 기술 미정

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: SandboxHost

- **입력 → 출력**: 릴리스·뷰 진입점·호스트 핸들러 → 격리 뷰

- **오류**: 로드 실패·권한 회수·시간 초과·종료

- **권한·상태·부수 효과**: 호스트 DOM/쿠키/토큰 분리

- **허용 의존성·호출 관계**: runtime bridge; release contracts

- **제외 책임·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/packages/workbench-runtime/sandbox.test.tsx`

- **완료·검수 조건**: 표준 뷰와 다른 신뢰 경계; 종료·복구 UI

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: iframe/Remote DOM 최종 선택·CSP·별도 출처

<a id="F097"></a>

<a id="f097--packagesworkbench-runtimebridgets--구현-계약-초안--검수-전"></a>

### 4.97. F097 · `packages/workbench-runtime/bridge.ts` — 구현 계약 초안 — 검수 전

- **소유·책임**: packages/workbench-runtime / SDK 메시지 검사·허용 기능 중계

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: validateMessage, dispatchHostRequest

- **입력 → 출력**: 현재 뷰 세션·SDK 요청 → 허용 응답

- **오류**: 스키마·origin/source·세션·상한·종료 후 응답 오류

- **권한·상태·부수 효과**: SDK 우회에도 검사; 비밀·임의 URL 전달 금지

- **허용 의존성·호출 관계**: generated bridge contracts; injected host handlers

- **제외 책임·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/packages/workbench-runtime/bridge.test.ts`

- **완료·검수 조건**: 다른 작업/릴리스 요청 거부; 전환 시 in-flight 취소

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: iframe 출처·opaque origin·메시지 포트 정책

<a id="F098"></a>

<a id="f098--packagesworkbench-runtimebindingsts--책임-배치만--상세-기록-미완료"></a>

### 4.98. F098 · `packages/workbench-runtime/bindings.ts` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/workbench-runtime / 호스트 측 데이터 연결·취소

- **원본·처리**: [L0445](../process-structure-migration-ledger/SKILL.md#L0445) `packages/workbench-runtime/src/bindings.ts` (이동·분리 검토)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F099"></a>

<a id="f099--packagesworkbench-runtimeactionsts--책임-배치만--상세-기록-미완료"></a>

### 4.99. F099 · `packages/workbench-runtime/actions.ts` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/workbench-runtime / 호스트 측 동작 전달·서버 인가 대체 금지

- **원본·처리**: [L0444](../process-structure-migration-ledger/SKILL.md#L0444) `packages/workbench-runtime/src/actions.ts` (이동·분리 검토)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F100"></a>

<a id="f100--packagesworkbench-runtimeregistryts--책임-배치만--상세-기록-미완료"></a>

### 4.100. F100 · `packages/workbench-runtime/registry.ts` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/workbench-runtime / 작업·에셋·호환 버전 조회

- **원본·처리**: [L0448](../process-structure-migration-ledger/SKILL.md#L0448) `packages/workbench-runtime/src/registry.ts` (이동·분리 검토)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F101"></a>

<a id="f101--packagesworkbench-runtimeview-statets--책임-배치만--상세-기록-미완료"></a>

### 4.101. F101 · `packages/workbench-runtime/view-state.ts` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/workbench-runtime / 사이드바·패널 상태 연결·복원

- **원본·처리**: [L0451](../process-structure-migration-ledger/SKILL.md#L0451) `packages/workbench-runtime/src/view-state.ts` (이동·분리 검토)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F102"></a>

<a id="f102--packagesworkbench-editorworkbencheditortsx--책임-배치만--상세-기록-미완료"></a>

### 4.102. F102 · `packages/workbench-editor/WorkbenchEditor.tsx` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/workbench-editor / 편집·미리보기·게시 화면

- **원본·처리**: [L0440](../process-structure-migration-ledger/SKILL.md#L0440) `packages/workbench-editor/src/WorkbenchEditor.tsx` (이동·분리 검토)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F103"></a>

<a id="f103--packagesworkbench-editorpreviewtsx--구현-계약-초안--검수-전"></a>

### 4.103. F103 · `packages/workbench-editor/preview.tsx` — 구현 계약 초안 — 검수 전

- **소유·책임**: packages/workbench-editor / 동일한 격리 런타임의 초안 미리보기

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: WorkbenchPreview

- **입력 → 출력**: 초안/빌드 결과·뷰 컨텍스트 → 미리보기

- **오류**: 컴파일 오류·격리 로딩 오류

- **권한·상태·부수 효과**: 운영과 동일 경계; 실제 데이터 접근은 별도 인가

- **허용 의존성·호출 관계**: runtime; draft contracts

- **제외 책임·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `tests/packages/workbench-editor/preview.test.tsx`

- **완료·검수 조건**: 미리보기 성공을 게시 상태로 취급하지 않음

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 스키마의 정확한 필드·상한·오류 코드와 구현 순서 검수

<a id="F104"></a>

<a id="f104--packagesworkbench-editordiagnosticsts--책임-배치만--상세-기록-미완료"></a>

### 4.104. F104 · `packages/workbench-editor/diagnostics.ts` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: packages/workbench-editor / 파일·행·열·단계별 오류 표시

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F105"></a>

<a id="f105--contractsschemasworkbenchv2manifestschemajson--책임-배치만--상세-기록-미완료"></a>

### 4.105. F105 · `contracts/schemas/workbench/v2/manifest.schema.json` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: contracts / 코드 진입점·요구 기능·호환성

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 언어 독립 계약 원본. 생성 코드는 contracts-py/ts; 원본/생성물 소유 역전 금지

- **설정·생성물**: 언어별 생성기는 scripts/contracts; 생성물 직접 수정 금지

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F106"></a>

<a id="f106--contractsschemasworkbenchv2bridgeschemajson--책임-배치만--상세-기록-미완료"></a>

### 4.106. F106 · `contracts/schemas/workbench/v2/bridge.schema.json` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: contracts / SDK 요청·응답·이벤트·취소

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 언어 독립 계약 원본. 생성 코드는 contracts-py/ts; 원본/생성물 소유 역전 금지

- **설정·생성물**: 언어별 생성기는 scripts/contracts; 생성물 직접 수정 금지

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F107"></a>

<a id="f107--contractsschemasworkbenchv2releaseschemajson--책임-배치만--상세-기록-미완료"></a>

### 4.107. F107 · `contracts/schemas/workbench/v2/release.schema.json` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: contracts / 소스·빌드·산출물 릴리스 메타데이터

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 언어 독립 계약 원본. 생성 코드는 contracts-py/ts; 원본/생성물 소유 역전 금지

- **설정·생성물**: 언어별 생성기는 scripts/contracts; 생성물 직접 수정 금지

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F108"></a>

<a id="f108--contractsschemasusagev1limitschemajson--책임-배치만--상세-기록-미완료"></a>

### 4.108. F108 · `contracts/schemas/usage/v1/limit.schema.json` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: contracts / 범위·계측 단위·한도 설정

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 언어 독립 계약 원본. 생성 코드는 contracts-py/ts; 원본/생성물 소유 역전 금지

- **설정·생성물**: 언어별 생성기는 scripts/contracts; 생성물 직접 수정 금지

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F109"></a>

<a id="f109--contractsschemasusagev1resultschemajson--책임-배치만--상세-기록-미완료"></a>

### 4.109. F109 · `contracts/schemas/usage/v1/result.schema.json` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: contracts / 사용량·허용·한도 초과 결과

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 언어 독립 계약 원본. 생성 코드는 contracts-py/ts; 원본/생성물 소유 역전 금지

- **설정·생성물**: 언어별 생성기는 scripts/contracts; 생성물 직접 수정 금지

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F110"></a>

<a id="f110--contractsschemaschatv1messageschemajson--책임-배치만--상세-기록-미완료"></a>

### 4.110. F110 · `contracts/schemas/chat/v1/message.schema.json` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: contracts / 메시지 레코드·제한된 발송 입력

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 언어 독립 계약 원본. 생성 코드는 contracts-py/ts; 원본/생성물 소유 역전 금지

- **설정·생성물**: 언어별 생성기는 scripts/contracts; 생성물 직접 수정 금지

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F111"></a>

<a id="f111--contractsschemaschatv1pageschemajson--책임-배치만--상세-기록-미완료"></a>

### 4.111. F111 · `contracts/schemas/chat/v1/page.schema.json` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: contracts / 이력·변경·불투명 다음 조회 커서

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 언어 독립 계약 원본. 생성 코드는 contracts-py/ts; 원본/생성물 소유 역전 금지

- **설정·생성물**: 언어별 생성기는 scripts/contracts; 생성물 직접 수정 금지

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F112"></a>

<a id="f112--deploylocalenvexample--책임-배치만--상세-기록-미완료"></a>

### 4.112. F112 · `deploy/local/env.example` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: deploy / 비밀 값 없는 설정 예시

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 선택한 로컬 배포·자원 설정만. 업무 로직·비밀 값·미선정 기술 파일 생성 금지

- **설정·생성물**: 배포 방식 선택 전 실제 설정 파일 내용 미정; 비밀 제외

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F113"></a>

<a id="f113--deploylocaldeploysh--책임-배치만--상세-기록-미완료"></a>

### 4.113. F113 · `deploy/local/deploy.sh` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: deploy / 설치·갱신 절차

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 선택한 로컬 배포·자원 설정만. 업무 로직·비밀 값·미선정 기술 파일 생성 금지

- **설정·생성물**: 배포 방식 선택 전 실제 설정 파일 내용 미정; 비밀 제외

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F114"></a>

<a id="f114--deploylocalrollbacksh--책임-배치만--상세-기록-미완료"></a>

### 4.114. F114 · `deploy/local/rollback.sh` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: deploy / 이전 배포 복구 절차

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 선택한 로컬 배포·자원 설정만. 업무 로직·비밀 값·미선정 기술 파일 생성 금지

- **설정·생성물**: 배포 방식 선택 전 실제 설정 파일 내용 미정; 비밀 제외

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F115"></a>

<a id="f115--deploylocaloperationsmd--책임-배치만--상세-기록-미완료"></a>

### 4.115. F115 · `deploy/local/OPERATIONS.md` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: deploy / 시작·재시작·운영·복구 안내

- **원본·처리**: 기준 목록에서 직접 대응된 원본 없음. 신규 후보 또는 추가 분리 분석 대상.

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 선택한 로컬 배포·자원 설정만. 업무 로직·비밀 값·미선정 기술 파일 생성 금지

- **설정·생성물**: 배포 방식 선택 전 실제 설정 파일 내용 미정; 비밀 제외

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="F116"></a>

<a id="f116--readmemd--책임-배치만--상세-기록-미완료"></a>

### 4.116. F116 · `README.md` — 책임 배치만 — 상세 기록 미완료

- **소유·책임**: README.md / 저장소 안내

- **원본·처리**: [L0063](../process-structure-migration-ledger/SKILL.md#L0063) `README.md` (유지 후보)

- **구현할 심볼**: 미정 — 실제 export/함수/클래스 분석 필요

- **입력 → 출력**: 미정 — 필드·스키마·입출력 상세화 필요

- **오류**: 미정 — 실패와 재시도 계약 필요

- **권한·상태·부수 효과**: 해당 파일의 인가·상태·부수 효과 적용 여부 검수 필요

- **허용 의존성·호출 관계**: 미정 — 실제 호출자·의존성 대응 필요

- **제외 책임·금지 의존성**: 소유 책임에 필요한 의존성만; 정확한 import/export 검수 필요

- **설정·생성물**: 설정·빌드 포함 파일·공개 namespace/export 매핑 별도 검수

- **테스트 경로 후보**: `미정 — tests/ 아래 정확한 파일 지정 필요`

- **완료·검수 조건**: 책임·입출력·오류·권한·테스트·소스 대응 검수 전에는 구현 준비 완료 아님

- **선행·순서**: 계약·핵심 정책 → 저장/외부 어댑터 → 앱 연결 → UI. 정확한 선행 F ID는 추가 검수

- **미정 사항**: 파일별 구현 기록 미완료

<a id="아직-전체-명세-완료가-아닌-이유"></a>

## 5. 아직 전체 명세 완료가 아닌 이유

- 대응표는 파일의 존재와 경로 기반 목적지 후보를 포괄한다. 모든 소스 본문·호출자·테스트를 분석한 것은 아니다.

- 기존 MCP 혼합 서버·공통 components.tsx·workbench domain/commands/queries의 정확한 심볼 분리표가 남아 있다.

- API composition의 기존 파일은 보존한다. 새 chat/usage 두 파일만 필요하다고 해석하지 않는다.

- 서로 같은 목적지에 모이는 원본은 통합 검토 대상이다. 덮어쓰기나 삭제를 승인하지 않는다.

- 루트 pyproject·pnpm-workspace·각 패키지 exports·빌드 포함 파일·migrations/deploy 정확한 설정 파일의 기록이 필요하다.

- 새 코드 기반 v2 계약은 v1과 의미가 달라 공존 경로를 제안한 것이다. 기존 v1을 덮어쓰거나 자동 변환하지 않는다.

<a id="다음-검수-순서"></a>

## 6. 다음 검수 순서

- Q1~Q7 결정 → 상세 기록이 없는 파일의 심볼/입출력 보완 → 기존 소스/새 파일 전체 대응 검수 → 선행 ID·구현 순서 확정 → 단계 실행 계약. 지금은 코드 이동·설치·제품 테스트·빌드·DB 연결·배포를 하지 않았다.

<a id="첨부-자료"></a>

## 7. 첨부 자료

- [structure-file-plan.json](assets/structure-file-plan.json)
