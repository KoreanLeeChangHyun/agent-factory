---
name: mcp-handoff-audit
description: MCP 파일 전달 완료 확인 — 2026-09-05을 확인할 때 사용합니다.
document-type: processed
category: analyze
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/mcp-handoff-audit.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
---


# MCP 파일 전달 완료 확인 — 2026-09-05

| 요구사항 | 구현 및 검증 근거 |
| --- | --- |
| 1. 토큰 재조회 | 0017 암호문·키 버전 컬럼, ConnectionService.reveal, POST secret. 실제 PostgreSQL 비슈퍼유저 테스트에서 원문 재조회·암호문 변조 차단·다른 사용자/작업공간 차단·CSRF·만료/폐기·권한 회수·legacy 처리 통과 |
| 2. 설정 파일 다운로드 | mcp-handoff.js ZIP 생성. 브라우저가 저장한 전 클라이언트/환경 ZIP을 Python zipfile로 열어 CRC와 파일 내용 확인. JSON/TOML 문법 및 서버 주소 확인 |
| 3. 파일 전달 AI 지침 | ZIP README와 클립보드 지침 동일. 다운로드 파일명·적용 경로·기존 설정 병합·인증·도구 목록 검증 절차 포함. 지침은 비밀 원문 대신 첨부 credentials.json을 참조 |
| 4. 선택 토큰 연결 | 토큰 ID 선택 및 복원. 13개 클라이언트/전체 환경 다운로드 후 발급 횟수 변화 없음. 작업공간 전환 중 늦은 secret 응답 무시 |
| 5. 화면 | 클라이언트·토큰 선택, 파일 다운로드, 지침 복사 순서. 오른쪽 선택 토큰 복사·발급·폐기. 직접 설정과 전체 코드 보조 유지 |
| 6. 전체 흐름 | 새로고침·verified 재접속·복사 실패·발급 실패·파일 생성 실패·secret 조회 실패·목록 실패·폐기·원문 없음·40개 목록·390px 화면 검증 |
| 7. 문서 및 배포 | mcp-connections.md와 workspace-ui.md 갱신. 실행 DB 0017(head), API 재시작 후 /factory/health 정상 및 secret 경로 등록 확인 |

- 실행한 검증:
- bash scripts/verify-mcp-handoff.sh — 새 DB 적용, 0016 역적용, 0017 재적용 및 실제 API/MCP SDK 테스트 통과.
- tests/browser/mcp-handoff.cjs — 브라우저 파일 저장/전달 시나리오 통과.
- tests/browser/workspace-start.cjs — 작업공간 탐색 회귀 통과.
- pytest tests/test_workspace_ui.py tests/test_mcp_server.py — 7 passed.
- 변경 Python 파일 Ruff 및 git diff --check 통과.

- 한계:
- 원문을 저장하지 않았던 기존 토큰은 복구할 수 없으며 자동 대체 발급하지 않는다.
- 브라우저는 다운로드 시작을 표시한다. 실제 저장 여부는 사용자 브라우저가 결정한다.
- 이번 검증은 모든 에디터에서 AI를 실제 실행한 검증이 아니라, 실제 설정 파일과 지침의
  생성·저장·일치, 서버 인증/API/MCP 처리 검증이다.
