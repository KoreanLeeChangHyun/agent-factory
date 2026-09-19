---
name: structure-migration-ledger
description: 구조 이전 대응표 — 기준 파일 조사을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/structure-migration-ledger.html
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
---


# 구조 이전 대응표 — 기준 파일 조사

- 기준 커밋: `ea086252119aae1dc257eca7d501e1564167f1d2` · 캡처: 2026-09-14T17:02:43.098Z · 분류: 가공 자료 / 이전 검토 초안

- 파일 725개(추적 718, 비무시 미추적 7)를 경로 기준으로 빠짐없이 등록했다. 모든 파일 본문을 검토했다는 뜻은 아니다. 대부분의 목적지는 경로 규칙에 따른 후보이며 승인된 이동표가 아니다. “미확정”은 누락이나 삭제가 아니라 추가 분석이 필요한 명시적 기록이다. 이번에 생성하는 계획 문서는 캡처 이후 파일이므로 이 기준 목록에 포함되지 않는다. feedback/·uploads/·ignored env/ 등은 접근 대상에서 제외했다. 실제 이동·삭제·테스트 실행은 하지 않았다.

- [목표 구조](../../skills/rule-workbench-structure/SKILL.md#target-structure) · [파일 구현 계획](../analyze-structure-file-plan/SKILL.md) · [기계 판독 대응표](assets/structure-migration-ledger.json)

<a id="분류-집계"></a>

## 1. 분류 집계

- 유지 후보: 177

- 미확정: 7

- 유지·설정 검토: 13

- 유지·분리 검토: 16

- 이동 후보: 199

- 분리/배치 미확정: 6

- 분리 후보: 1

- 분리 미완료: 1

- 임시 목적지: 14

- 이동·분리 후보: 1

- 이동·분리 검토: 26

- 생성물 경로 후보: 7

- 설정 이동 후보: 2

- 분리·통합 미완료: 3

- 유지·소유 검토: 5

- 이동·보완 후보: 1

- 테스트 소유 미확정: 80

- 테스트 이동 후보: 166

<a id="직접-확인한-주요-불일치"></a>

## 2. 직접 확인한 주요 불일치

- apps/api/main.py는 MCP 서버를 생성·mount하고 존재하지 않는 api.http.endpoints를 import한다. API/MCP 분리와 route wiring 보완이 필요하다.

- apps/api/mcp/server.py는 API composition과 HTTP presenter를 직접 사용한다. 독립 앱으로 이동하면서 업무 조회와 프로토콜 표현을 분리해야 한다.

- worker CLI는 실제 Celery 앱을 외부 -A 선택에 맡긴다. scripts/operations/run.py는 현재 없는 celery_app을 참조한다.

- 루트 pyproject.toml에는 app*·app.build_assets·구 src 경로가 남아 있다. manifest와 namespace 매핑은 코드 이전과 함께 바꿔야 한다.

- apps/packages의 py/ts/tsx/package.json 대상 chat·websocket·yjs·crdt 검색 결과가 없었다. 이를 완전한 기능 부재 증명으로 확대하지 않는다.

- 테스트는 기존 도메인 우선 배치가 남아 있다. 분류 후보는 실제 import·fixture 확인 후 확정해야 한다.

<a id="전체-기준-파일"></a>

## 3. 전체 기준 파일

- 브라우저 찾기로 경로·상태를 검색할 수 있다. 목적지 “미정”은 해당 사유가 해결될 때까지 보존한다.

| ID / 원본 | 처리 상태 / 근거 | 목적지 후보 | 추가 작업 |
| --- | --- | --- | --- |
| <a id="L0001"></a>L0001<br>`.codex/config.toml`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/config.toml` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0002"></a>L0002<br>`.codex/skills/design-platform/SKILL.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/design-platform/SKILL.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0003"></a>L0003<br>`.codex/skills/design-platform/agents/openai.yaml`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/design-platform/agents/openai.yaml` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0004"></a>L0004<br>`.codex/skills/design-platform/references/cloud-documents.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/design-platform/references/cloud-documents.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0005"></a>L0005<br>`.codex/skills/design-platform/references/cloud-integrations.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/design-platform/references/cloud-integrations.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0006"></a>L0006<br>`.codex/skills/design-platform/references/cloud-platform.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/design-platform/references/cloud-platform.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0007"></a>L0007<br>`.codex/skills/design-platform/references/cloud-reporting.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/design-platform/references/cloud-reporting.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0008"></a>L0008<br>`.codex/skills/design-platform/references/document-editor.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/design-platform/references/document-editor.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0009"></a>L0009<br>`.codex/skills/design-platform/references/organization-management.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/design-platform/references/organization-management.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0010"></a>L0010<br>`.codex/skills/design-platform/references/planning-import.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/design-platform/references/planning-import.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0011"></a>L0011<br>`.codex/skills/design-platform/references/product-overview.md`<br>미추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/design-platform/references/product-overview.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0012"></a>L0012<br>`.codex/skills/design-platform/references/theme-profiles.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/design-platform/references/theme-profiles.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0013"></a>L0013<br>`.codex/skills/design-platform/references/workbench-runtime.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/design-platform/references/workbench-runtime.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0014"></a>L0014<br>`.codex/skills/info-platform/SKILL.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/info-platform/SKILL.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0015"></a>L0015<br>`.codex/skills/info-platform/agents/openai.yaml`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/info-platform/agents/openai.yaml` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0016"></a>L0016<br>`.codex/skills/info-platform/references/agent-reporting.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/info-platform/references/agent-reporting.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0017"></a>L0017<br>`.codex/skills/info-platform/references/mcp-clients.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/info-platform/references/mcp-clients.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0018"></a>L0018<br>`.codex/skills/info-platform/references/platform-map.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/info-platform/references/platform-map.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0019"></a>L0019<br>`.codex/skills/rule-documents/SKILL.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-documents/SKILL.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0020"></a>L0020<br>`.codex/skills/rule-documents/agents/openai.yaml`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-documents/agents/openai.yaml` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0021"></a>L0021<br>`.codex/skills/rule-layout/SKILL.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-layout/SKILL.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0022"></a>L0022<br>`.codex/skills/rule-layout/agents/openai.yaml`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-layout/agents/openai.yaml` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0023"></a>L0023<br>`.codex/skills/rule-platform/SKILL.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-platform/SKILL.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0024"></a>L0024<br>`.codex/skills/rule-platform/agents/openai.yaml`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-platform/agents/openai.yaml` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0025"></a>L0025<br>`.codex/skills/rule-platform/references/admin.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-platform/references/admin.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0026"></a>L0026<br>`.codex/skills/rule-platform/references/agents.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-platform/references/agents.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0027"></a>L0027<br>`.codex/skills/rule-platform/references/authentication.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-platform/references/authentication.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0028"></a>L0028<br>`.codex/skills/rule-platform/references/authorization.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-platform/references/authorization.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0029"></a>L0029<br>`.codex/skills/rule-platform/references/database.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-platform/references/database.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0030"></a>L0030<br>`.codex/skills/rule-platform/references/documents.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-platform/references/documents.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0031"></a>L0031<br>`.codex/skills/rule-platform/references/external-agent-reporting.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-platform/references/external-agent-reporting.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0032"></a>L0032<br>`.codex/skills/rule-platform/references/integrations.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-platform/references/integrations.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0033"></a>L0033<br>`.codex/skills/rule-platform/references/mcp-connections.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-platform/references/mcp-connections.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0034"></a>L0034<br>`.codex/skills/rule-platform/references/mcp.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-platform/references/mcp.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0035"></a>L0035<br>`.codex/skills/rule-platform/references/migration.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-platform/references/migration.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0036"></a>L0036<br>`.codex/skills/rule-platform/references/observability.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-platform/references/observability.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0037"></a>L0037<br>`.codex/skills/rule-platform/references/operations.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-platform/references/operations.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0038"></a>L0038<br>`.codex/skills/rule-platform/references/search.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-platform/references/search.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0039"></a>L0039<br>`.codex/skills/rule-platform/references/security.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-platform/references/security.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0040"></a>L0040<br>`.codex/skills/rule-platform/references/workers.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-platform/references/workers.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0041"></a>L0041<br>`.codex/skills/rule-platform/references/workspaces.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-platform/references/workspaces.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0042"></a>L0042<br>`.codex/skills/rule-project/SKILL.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-project/SKILL.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0043"></a>L0043<br>`.codex/skills/rule-project/agents/openai.yaml`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-project/agents/openai.yaml` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0044"></a>L0044<br>`.codex/skills/rule-project/references/directory-structure.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-project/references/directory-structure.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0045"></a>L0045<br>`.codex/skills/rule-project/references/testing.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-project/references/testing.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0046"></a>L0046<br>`.codex/skills/rule-ui/SKILL.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-ui/SKILL.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0047"></a>L0047<br>`.codex/skills/rule-ui/agents/openai.yaml`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-ui/agents/openai.yaml` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0048"></a>L0048<br>`.codex/skills/rule-ui/references/audit-checklist.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-ui/references/audit-checklist.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0049"></a>L0049<br>`.codex/skills/rule-ui/references/design-rules.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-ui/references/design-rules.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0050"></a>L0050<br>`.codex/skills/rule-ui/references/sidebar-assets.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-ui/references/sidebar-assets.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0051"></a>L0051<br>`.codex/skills/rule-ui/references/ui-components.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-ui/references/ui-components.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0052"></a>L0052<br>`.codex/skills/rule-ui/references/ui-kit-api.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-ui/references/ui-kit-api.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0053"></a>L0053<br>`.codex/skills/rule-ui/references/workspace-ui.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-ui/references/workspace-ui.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0054"></a>L0054<br>`.codex/skills/rule-workbench-structure/SKILL.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-workbench-structure/SKILL.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0055"></a>L0055<br>`.codex/skills/rule-workbench-structure/agents/openai.yaml`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-workbench-structure/agents/openai.yaml` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0056"></a>L0056<br>`.codex/skills/rule-workbench-structure/references/directory-contract.md`<br>미추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-workbench-structure/references/directory-contract.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0057"></a>L0057<br>`.codex/skills/rule-workbench-structure/references/target-structure.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.codex/skills/rule-workbench-structure/references/target-structure.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0058"></a>L0058<br>`.github/workflows/ci.yml`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.github/workflows/ci.yml` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0059"></a>L0059<br>`.github/workflows/workbench-stage1.yml`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.github/workflows/workbench-stage1.yml` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0060"></a>L0060<br>`.gitignore`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `.gitignore` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0061"></a>L0061<br>`.vscode/mcp.json`<br>추적 / 존재 | 미확정<br>경로 기준 분류 | 미정 | 내용·호출자 검토 후 목적지 확정 |
| <a id="L0062"></a>L0062<br>`.vscode/settings.json`<br>추적 / 존재 | 미확정<br>경로 기준 분류 | 미정 | 내용·호출자 검토 후 목적지 확정 |
| <a id="L0063"></a>L0063<br>`README.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `README.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0064"></a>L0064<br>`apps/api/__init__.py`<br>추적 / 존재 | 유지·설정 검토<br>경로 기준 분류 | `apps/api/__init__.py` | 기존 파일 보존; API 자체 책임·빌드 포함 목록과 누락된 route wiring 검토 |
| <a id="L0065"></a>L0065<br>`apps/api/composition/__init__.py`<br>추적 / 존재 | 유지·분리 검토<br>경로 기준 분류 | `apps/api/composition/__init__.py` | API 조립은 유지. MCP/worker에서 필요한 조립은 각 앱에서 소유하며 공유 업무 판단만 core로 추출 |
| <a id="L0066"></a>L0066<br>`apps/api/composition/admin.py`<br>추적 / 존재 | 유지·분리 검토<br>경로 기준 분류 | `apps/api/composition/admin.py` | API 조립은 유지. MCP/worker에서 필요한 조립은 각 앱에서 소유하며 공유 업무 판단만 core로 추출 |
| <a id="L0067"></a>L0067<br>`apps/api/composition/agent_execution.py`<br>추적 / 존재 | 유지·분리 검토<br>경로 기준 분류 | `apps/api/composition/agent_execution.py` | API 조립은 유지. MCP/worker에서 필요한 조립은 각 앱에서 소유하며 공유 업무 판단만 core로 추출 |
| <a id="L0068"></a>L0068<br>`apps/api/composition/agents.py`<br>추적 / 존재 | 유지·분리 검토<br>경로 기준 분류 | `apps/api/composition/agents.py` | API 조립은 유지. MCP/worker에서 필요한 조립은 각 앱에서 소유하며 공유 업무 판단만 core로 추출 |
| <a id="L0069"></a>L0069<br>`apps/api/composition/appearance.py`<br>추적 / 존재 | 유지·분리 검토<br>경로 기준 분류 | `apps/api/composition/appearance.py` | API 조립은 유지. MCP/worker에서 필요한 조립은 각 앱에서 소유하며 공유 업무 판단만 core로 추출 |
| <a id="L0070"></a>L0070<br>`apps/api/composition/connections.py`<br>추적 / 존재 | 유지·분리 검토<br>경로 기준 분류 | `apps/api/composition/connections.py` | API 조립은 유지. MCP/worker에서 필요한 조립은 각 앱에서 소유하며 공유 업무 판단만 core로 추출 |
| <a id="L0071"></a>L0071<br>`apps/api/composition/identity.py`<br>추적 / 존재 | 유지·분리 검토<br>경로 기준 분류 | `apps/api/composition/identity.py` | API 조립은 유지. MCP/worker에서 필요한 조립은 각 앱에서 소유하며 공유 업무 판단만 core로 추출 |
| <a id="L0072"></a>L0072<br>`apps/api/composition/knowledge.py`<br>추적 / 존재 | 유지·분리 검토<br>경로 기준 분류 | `apps/api/composition/knowledge.py` | API 조립은 유지. MCP/worker에서 필요한 조립은 각 앱에서 소유하며 공유 업무 판단만 core로 추출 |
| <a id="L0073"></a>L0073<br>`apps/api/composition/mcp_access.py`<br>추적 / 존재 | 유지·분리 검토<br>경로 기준 분류 | `apps/api/composition/mcp_access.py` | API 조립은 유지. MCP/worker에서 필요한 조립은 각 앱에서 소유하며 공유 업무 판단만 core로 추출 |
| <a id="L0074"></a>L0074<br>`apps/api/composition/organizations.py`<br>추적 / 존재 | 유지·분리 검토<br>경로 기준 분류 | `apps/api/composition/organizations.py` | API 조립은 유지. MCP/worker에서 필요한 조립은 각 앱에서 소유하며 공유 업무 판단만 core로 추출 |
| <a id="L0075"></a>L0075<br>`apps/api/composition/planning.py`<br>추적 / 존재 | 유지·분리 검토<br>경로 기준 분류 | `apps/api/composition/planning.py` | API 조립은 유지. MCP/worker에서 필요한 조립은 각 앱에서 소유하며 공유 업무 판단만 core로 추출 |
| <a id="L0076"></a>L0076<br>`apps/api/composition/queries.py`<br>추적 / 존재 | 유지·분리 검토<br>경로 기준 분류 | `apps/api/composition/queries.py` | API 조립은 유지. MCP/worker에서 필요한 조립은 각 앱에서 소유하며 공유 업무 판단만 core로 추출 |
| <a id="L0077"></a>L0077<br>`apps/api/composition/reporting.py`<br>추적 / 존재 | 유지·분리 검토<br>경로 기준 분류 | `apps/api/composition/reporting.py` | API 조립은 유지. MCP/worker에서 필요한 조립은 각 앱에서 소유하며 공유 업무 판단만 core로 추출 |
| <a id="L0078"></a>L0078<br>`apps/api/composition/scheduling.py`<br>추적 / 존재 | 유지·분리 검토<br>경로 기준 분류 | `apps/api/composition/scheduling.py` | API 조립은 유지. MCP/worker에서 필요한 조립은 각 앱에서 소유하며 공유 업무 판단만 core로 추출 |
| <a id="L0079"></a>L0079<br>`apps/api/composition/workbenches.py`<br>추적 / 존재 | 유지·분리 검토<br>경로 기준 분류 | `apps/api/composition/workbenches.py` | API 조립은 유지. MCP/worker에서 필요한 조립은 각 앱에서 소유하며 공유 업무 판단만 core로 추출 |
| <a id="L0080"></a>L0080<br>`apps/api/composition/workspaces.py`<br>추적 / 존재 | 유지·분리 검토<br>경로 기준 분류 | `apps/api/composition/workspaces.py` | API 조립은 유지. MCP/worker에서 필요한 조립은 각 앱에서 소유하며 공유 업무 판단만 core로 추출 |
| <a id="L0081"></a>L0081<br>`apps/api/http/__init__.py`<br>추적 / 존재 | 유지·설정 검토<br>경로 기준 분류 | `apps/api/http/__init__.py` | 기존 파일 보존; API 자체 책임·빌드 포함 목록과 누락된 route wiring 검토 |
| <a id="L0082"></a>L0082<br>`apps/api/http/middleware/__init__.py`<br>추적 / 존재 | 유지·설정 검토<br>경로 기준 분류 | `apps/api/http/middleware/__init__.py` | 기존 파일 보존; API 자체 책임·빌드 포함 목록과 누락된 route wiring 검토 |
| <a id="L0083"></a>L0083<br>`apps/api/http/middleware/context.py`<br>추적 / 존재 | 유지·설정 검토<br>경로 기준 분류 | `apps/api/http/middleware/context.py` | 기존 파일 보존; API 자체 책임·빌드 포함 목록과 누락된 route wiring 검토 |
| <a id="L0084"></a>L0084<br>`apps/api/http/middleware/security.py`<br>추적 / 존재 | 유지·설정 검토<br>경로 기준 분류 | `apps/api/http/middleware/security.py` | 기존 파일 보존; API 자체 책임·빌드 포함 목록과 누락된 route wiring 검토 |
| <a id="L0085"></a>L0085<br>`apps/api/http/responses/__init__.py`<br>추적 / 존재 | 유지·설정 검토<br>경로 기준 분류 | `apps/api/http/responses/__init__.py` | 기존 파일 보존; API 자체 책임·빌드 포함 목록과 누락된 route wiring 검토 |
| <a id="L0086"></a>L0086<br>`apps/api/http/responses/errors.py`<br>추적 / 존재 | 유지·설정 검토<br>경로 기준 분류 | `apps/api/http/responses/errors.py` | 기존 파일 보존; API 자체 책임·빌드 포함 목록과 누락된 route wiring 검토 |
| <a id="L0087"></a>L0087<br>`apps/api/http/routes/__init__.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/api/routes/__init__.py` | 불필요한 HTTP wrapper·단일 router 디렉터리 제거; 공개 URL은 보존 |
| <a id="L0088"></a>L0088<br>`apps/api/http/routes/agents/router.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/api/routes/agents.py` | 불필요한 HTTP wrapper·단일 router 디렉터리 제거; 공개 URL은 보존 |
| <a id="L0089"></a>L0089<br>`apps/api/http/routes/appearance.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/api/routes/appearance.py` | 불필요한 HTTP wrapper·단일 router 디렉터리 제거; 공개 URL은 보존 |
| <a id="L0090"></a>L0090<br>`apps/api/http/routes/connections/router.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/api/routes/connections.py` | 불필요한 HTTP wrapper·단일 router 디렉터리 제거; 공개 URL은 보존 |
| <a id="L0091"></a>L0091<br>`apps/api/http/routes/knowledge/cloud.py`<br>추적 / 존재 | 분리/배치 미확정<br>경로 기준 분류 | 미정 | 문서 HTTP·preview HTML/JS의 웹/런타임 경계를 분석한 뒤 정확한 목적지 지정 |
| <a id="L0092"></a>L0092<br>`apps/api/http/routes/knowledge/documents.py`<br>추적 / 존재 | 분리/배치 미확정<br>경로 기준 분류 | 미정 | 문서 HTTP·preview HTML/JS의 웹/런타임 경계를 분석한 뒤 정확한 목적지 지정 |
| <a id="L0093"></a>L0093<br>`apps/api/http/routes/knowledge/preview.py`<br>추적 / 존재 | 분리/배치 미확정<br>경로 기준 분류 | 미정 | 문서 HTTP·preview HTML/JS의 웹/런타임 경계를 분석한 뒤 정확한 목적지 지정 |
| <a id="L0094"></a>L0094<br>`apps/api/http/routes/knowledge/preview_runtime.js`<br>추적 / 존재 | 분리/배치 미확정<br>경로 기준 분류 | 미정 | 문서 HTTP·preview HTML/JS의 웹/런타임 경계를 분석한 뒤 정확한 목적지 지정 |
| <a id="L0095"></a>L0095<br>`apps/api/http/routes/planning/router.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/api/routes/planning.py` | 불필요한 HTTP wrapper·단일 router 디렉터리 제거; 공개 URL은 보존 |
| <a id="L0096"></a>L0096<br>`apps/api/http/routes/reporting/router.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/api/routes/reporting.py` | 불필요한 HTTP wrapper·단일 router 디렉터리 제거; 공개 URL은 보존 |
| <a id="L0097"></a>L0097<br>`apps/api/http/routes/scheduling/router.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/api/routes/scheduling.py` | 불필요한 HTTP wrapper·단일 router 디렉터리 제거; 공개 URL은 보존 |
| <a id="L0098"></a>L0098<br>`apps/api/http/routes/workbenches.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/api/routes/workbenches.py` | 불필요한 HTTP wrapper·단일 router 디렉터리 제거; 공개 URL은 보존 |
| <a id="L0099"></a>L0099<br>`apps/api/http/sessions.py`<br>추적 / 존재 | 유지·설정 검토<br>경로 기준 분류 | `apps/api/http/sessions.py` | 기존 파일 보존; API 자체 책임·빌드 포함 목록과 누락된 route wiring 검토 |
| <a id="L0100"></a>L0100<br>`apps/api/logging.py`<br>추적 / 존재 | 유지·설정 검토<br>경로 기준 분류 | `apps/api/logging.py` | 기존 파일 보존; API 자체 책임·빌드 포함 목록과 누락된 route wiring 검토 |
| <a id="L0101"></a>L0101<br>`apps/api/main.py`<br>추적 / 존재 | 분리 후보<br>본문 확인 | `apps/api/main.py`<br>`apps/mcp/main.py` | create_app의 MCP 생성·수명·mount를 독립 MCP 진입으로 분리. 존재하지 않는 api.http.endpoints import 해소. 웹 정적 제공 방식은 배포 결정 |
| <a id="L0102"></a>L0102<br>`apps/api/mcp/__init__.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/mcp/__init__.py` | MCP 전용 코드를 독립 앱으로 이동. api 설정·composition import 제거 필요 |
| <a id="L0103"></a>L0103<br>`apps/api/mcp/auth.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/mcp/auth.py` | MCP 전용 코드를 독립 앱으로 이동. api 설정·composition import 제거 필요 |
| <a id="L0104"></a>L0104<br>`apps/api/mcp/scoped.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/mcp/scoped.py` | MCP 전용 코드를 독립 앱으로 이동. api 설정·composition import 제거 필요 |
| <a id="L0105"></a>L0105<br>`apps/api/mcp/server.py`<br>추적 / 존재 | 분리 미완료<br>본문·심볼 일부 확인 | `apps/mcp/main.py`<br>`apps/mcp/tools/workbenches.py`<br>`apps/mcp/resources/activities.py`<br>`apps/mcp/services/queries.py` | create_mcp_server·도구·리소스·공통 인가 분리. document/agent/schedule/connection 기존 도구 각각의 목적 파일과 HTTP presenter 의존 제거는 추가 대응 필요 |
| <a id="L0106"></a>L0106<br>`apps/api/observability.py`<br>추적 / 존재 | 유지·설정 검토<br>경로 기준 분류 | `apps/api/observability.py` | 기존 파일 보존; API 자체 책임·빌드 포함 목록과 누락된 route wiring 검토 |
| <a id="L0107"></a>L0107<br>`apps/api/paths.py`<br>추적 / 존재 | 유지·설정 검토<br>경로 기준 분류 | `apps/api/paths.py` | 기존 파일 보존; API 자체 책임·빌드 포함 목록과 누락된 route wiring 검토 |
| <a id="L0108"></a>L0108<br>`apps/api/pyproject.toml`<br>추적 / 존재 | 유지·설정 검토<br>경로 기준 분류 | `apps/api/pyproject.toml` | 기존 파일 보존; API 자체 책임·빌드 포함 목록과 누락된 route wiring 검토 |
| <a id="L0109"></a>L0109<br>`apps/api/settings.py`<br>추적 / 존재 | 유지·설정 검토<br>경로 기준 분류 | `apps/api/settings.py` | 기존 파일 보존; API 자체 책임·빌드 포함 목록과 누락된 route wiring 검토 |
| <a id="L0110"></a>L0110<br>`apps/web/index.html`<br>추적 / 존재 | 미확정<br>경로 기준 분류 | 미정 | 내용·호출자 검토 후 목적지 확정 |
| <a id="L0111"></a>L0111<br>`apps/web/package.json`<br>추적 / 존재 | 미확정<br>경로 기준 분류 | 미정 | 내용·호출자 검토 후 목적지 확정 |
| <a id="L0112"></a>L0112<br>`apps/web/src/App.tsx`<br>추적 / 존재 | 임시 목적지<br>경로 기준 분류 | `apps/web/App.tsx` | wrapper 제거 후보일 뿐. app/registry/shell 및 API·테마 클라이언트 소유권 재검토 |
| <a id="L0113"></a>L0113<br>`apps/web/src/AuthenticatedThemeRoot.tsx`<br>추적 / 존재 | 임시 목적지<br>경로 기준 분류 | `apps/web/AuthenticatedThemeRoot.tsx` | wrapper 제거 후보일 뿐. app/registry/shell 및 API·테마 클라이언트 소유권 재검토 |
| <a id="L0114"></a>L0114<br>`apps/web/src/CatalogPreview.tsx`<br>추적 / 존재 | 임시 목적지<br>경로 기준 분류 | `apps/web/CatalogPreview.tsx` | wrapper 제거 후보일 뿐. app/registry/shell 및 API·테마 클라이언트 소유권 재검토 |
| <a id="L0115"></a>L0115<br>`apps/web/src/ThemeBootstrap.tsx`<br>추적 / 존재 | 임시 목적지<br>경로 기준 분류 | `apps/web/ThemeBootstrap.tsx` | wrapper 제거 후보일 뿐. app/registry/shell 및 API·테마 클라이언트 소유권 재검토 |
| <a id="L0116"></a>L0116<br>`apps/web/src/WorkbenchAuthoring.tsx`<br>추적 / 존재 | 임시 목적지<br>경로 기준 분류 | `apps/web/WorkbenchAuthoring.tsx` | wrapper 제거 후보일 뿐. app/registry/shell 및 API·테마 클라이언트 소유권 재검토 |
| <a id="L0117"></a>L0117<br>`apps/web/src/api-client.ts`<br>추적 / 존재 | 임시 목적지<br>경로 기준 분류 | `apps/web/api-client.ts` | wrapper 제거 후보일 뿐. app/registry/shell 및 API·테마 클라이언트 소유권 재검토 |
| <a id="L0118"></a>L0118<br>`apps/web/src/api-path.ts`<br>추적 / 존재 | 임시 목적지<br>경로 기준 분류 | `apps/web/api-path.ts` | wrapper 제거 후보일 뿐. app/registry/shell 및 API·테마 클라이언트 소유권 재검토 |
| <a id="L0119"></a>L0119<br>`apps/web/src/app.css`<br>추적 / 존재 | 임시 목적지<br>경로 기준 분류 | `apps/web/app.css` | wrapper 제거 후보일 뿐. app/registry/shell 및 API·테마 클라이언트 소유권 재검토 |
| <a id="L0120"></a>L0120<br>`apps/web/src/app/WorkbenchContext.tsx`<br>추적 / 존재 | 임시 목적지<br>경로 기준 분류 | `apps/web/app/WorkbenchContext.tsx` | wrapper 제거 후보일 뿐. app/registry/shell 및 API·테마 클라이언트 소유권 재검토 |
| <a id="L0121"></a>L0121<br>`apps/web/src/app/workbench-bindings.ts`<br>추적 / 존재 | 임시 목적지<br>경로 기준 분류 | `apps/web/app/workbench-bindings.ts` | wrapper 제거 후보일 뿐. app/registry/shell 및 API·테마 클라이언트 소유권 재검토 |
| <a id="L0122"></a>L0122<br>`apps/web/src/main.tsx`<br>추적 / 존재 | 임시 목적지<br>경로 기준 분류 | `apps/web/main.tsx` | wrapper 제거 후보일 뿐. app/registry/shell 및 API·테마 클라이언트 소유권 재검토 |
| <a id="L0123"></a>L0123<br>`apps/web/src/registry/WorkbenchRegistry.ts`<br>추적 / 존재 | 임시 목적지<br>경로 기준 분류 | `apps/web/registry/WorkbenchRegistry.ts` | wrapper 제거 후보일 뿐. app/registry/shell 및 API·테마 클라이언트 소유권 재검토 |
| <a id="L0124"></a>L0124<br>`apps/web/src/shell/WorkbenchShell.tsx`<br>추적 / 존재 | 이동·분리 후보<br>imports·export 확인 | `apps/web/components/WorkbenchHost.tsx` | WorkbenchShell의 배치 조합 이전. 앱 전용 선택 상태와 공통 런타임 로직 분리 검토 |
| <a id="L0125"></a>L0125<br>`apps/web/src/standard/account/AccountWorkbench.tsx`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/account/AccountWorkbench.tsx` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0126"></a>L0126<br>`apps/web/src/standard/account/account-client.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/api/account-client.ts` | 브라우저 HTTP 클라이언트 분리; 이름 충돌·타입 import 확인 |
| <a id="L0127"></a>L0127<br>`apps/web/src/standard/account/account-types.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/account/account-types.ts` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0128"></a>L0128<br>`apps/web/src/standard/account/index.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/account/index.ts` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0129"></a>L0129<br>`apps/web/src/standard/admin/AdminWorkbench.tsx`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/admin/AdminWorkbench.tsx` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0130"></a>L0130<br>`apps/web/src/standard/admin/admin-client.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/api/admin-client.ts` | 브라우저 HTTP 클라이언트 분리; 이름 충돌·타입 import 확인 |
| <a id="L0131"></a>L0131<br>`apps/web/src/standard/admin/index.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/admin/index.ts` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0132"></a>L0132<br>`apps/web/src/standard/agents/AgentsWorkbench.tsx`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/agents/AgentsWorkbench.tsx` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0133"></a>L0133<br>`apps/web/src/standard/agents/agent-client.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/api/agent-client.ts` | 브라우저 HTTP 클라이언트 분리; 이름 충돌·타입 import 확인 |
| <a id="L0134"></a>L0134<br>`apps/web/src/standard/agents/index.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/agents/index.ts` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0135"></a>L0135<br>`apps/web/src/standard/connections/ConnectionsWorkbench.tsx`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/connections/ConnectionsWorkbench.tsx` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0136"></a>L0136<br>`apps/web/src/standard/connections/WorkspaceConnections.tsx`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/connections/WorkspaceConnections.tsx` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0137"></a>L0137<br>`apps/web/src/standard/connections/index.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/connections/index.ts` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0138"></a>L0138<br>`apps/web/src/standard/connections/mcp-connection-client.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/api/mcp-connection-client.ts` | 브라우저 HTTP 클라이언트 분리; 이름 충돌·타입 import 확인 |
| <a id="L0139"></a>L0139<br>`apps/web/src/standard/connections/provider-client.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/api/provider-client.ts` | 브라우저 HTTP 클라이언트 분리; 이름 충돌·타입 import 확인 |
| <a id="L0140"></a>L0140<br>`apps/web/src/standard/documents/DocumentEditor.tsx`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/documents/DocumentEditor.tsx` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0141"></a>L0141<br>`apps/web/src/standard/documents/DocumentExplorer.tsx`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/documents/DocumentExplorer.tsx` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0142"></a>L0142<br>`apps/web/src/standard/documents/DocumentViewer.tsx`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/documents/DocumentViewer.tsx` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0143"></a>L0143<br>`apps/web/src/standard/documents/DocumentsWorkbench.tsx`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/documents/DocumentsWorkbench.tsx` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0144"></a>L0144<br>`apps/web/src/standard/documents/document-bindings.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/documents/document-bindings.ts` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0145"></a>L0145<br>`apps/web/src/standard/documents/document-client.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/api/document-client.ts` | 브라우저 HTTP 클라이언트 분리; 이름 충돌·타입 import 확인 |
| <a id="L0146"></a>L0146<br>`apps/web/src/standard/documents/document-editor-selection.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/documents/document-editor-selection.ts` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0147"></a>L0147<br>`apps/web/src/standard/documents/document-editor-state.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/documents/document-editor-state.ts` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0148"></a>L0148<br>`apps/web/src/standard/documents/document-operations.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/documents/document-operations.ts` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0149"></a>L0149<br>`apps/web/src/standard/documents/documents.css`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/documents/documents.css` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0150"></a>L0150<br>`apps/web/src/standard/documents/index.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/documents/index.ts` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0151"></a>L0151<br>`apps/web/src/standard/organization/OrganizationWorkbench.tsx`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/organizations/OrganizationWorkbench.tsx` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0152"></a>L0152<br>`apps/web/src/standard/organization/index.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/organizations/index.ts` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0153"></a>L0153<br>`apps/web/src/standard/organization/organization-client.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/api/organization-client.ts` | 브라우저 HTTP 클라이언트 분리; 이름 충돌·타입 import 확인 |
| <a id="L0154"></a>L0154<br>`apps/web/src/standard/organization/organization-types.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/organizations/organization-types.ts` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0155"></a>L0155<br>`apps/web/src/standard/reporting/ReportingWorkbench.tsx`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/logs/LogsWorkbench.tsx` | Reporting 화면을 로그 화면 전체와 동일시하지 않음; 기존 보고 기능 보존·UI 통합 검토 |
| <a id="L0156"></a>L0156<br>`apps/web/src/standard/reporting/index.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/logs/index.ts` | Reporting 화면을 로그 화면 전체와 동일시하지 않음; 기존 보고 기능 보존·UI 통합 검토 |
| <a id="L0157"></a>L0157<br>`apps/web/src/standard/reporting/reporting-client.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/api/reporting-client.ts` | 브라우저 HTTP 클라이언트 분리; 이름 충돌·타입 import 확인 |
| <a id="L0158"></a>L0158<br>`apps/web/src/standard/schedule/ScheduleWorkbench.tsx`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/schedule/ScheduleWorkbench.tsx` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0159"></a>L0159<br>`apps/web/src/standard/schedule/index.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/schedule/index.ts` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0160"></a>L0160<br>`apps/web/src/standard/schedule/schedule-client.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/api/schedule-client.ts` | 브라우저 HTTP 클라이언트 분리; 이름 충돌·타입 import 확인 |
| <a id="L0161"></a>L0161<br>`apps/web/src/standard/schedule/schedule.css`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/schedule/schedule.css` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0162"></a>L0162<br>`apps/web/src/standard/workspace/WorkspaceWorkbench.tsx`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/workspaces/WorkspaceWorkbench.tsx` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0163"></a>L0163<br>`apps/web/src/standard/workspace/index.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/pages/workspaces/index.ts` | 기능 전용 화면·상태·스타일은 해당 페이지 소유 |
| <a id="L0164"></a>L0164<br>`apps/web/src/standard/workspace/workspace-client.ts`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/web/api/workspace-client.ts` | 브라우저 HTTP 클라이언트 분리; 이름 충돌·타입 import 확인 |
| <a id="L0165"></a>L0165<br>`apps/web/src/theme-client.ts`<br>추적 / 존재 | 임시 목적지<br>경로 기준 분류 | `apps/web/theme-client.ts` | wrapper 제거 후보일 뿐. app/registry/shell 및 API·테마 클라이언트 소유권 재검토 |
| <a id="L0166"></a>L0166<br>`apps/web/src/workbench-client.ts`<br>추적 / 존재 | 임시 목적지<br>경로 기준 분류 | `apps/web/workbench-client.ts` | wrapper 제거 후보일 뿐. app/registry/shell 및 API·테마 클라이언트 소유권 재검토 |
| <a id="L0167"></a>L0167<br>`apps/web/tsconfig.json`<br>추적 / 존재 | 미확정<br>경로 기준 분류 | 미정 | 내용·호출자 검토 후 목적지 확정 |
| <a id="L0168"></a>L0168<br>`apps/web/vite.config.ts`<br>추적 / 존재 | 미확정<br>경로 기준 분류 | 미정 | 내용·호출자 검토 후 목적지 확정 |
| <a id="L0169"></a>L0169<br>`apps/worker/pyproject.toml`<br>추적 / 존재 | 미확정<br>경로 기준 분류 | 미정 | 내용·호출자 검토 후 목적지 확정 |
| <a id="L0170"></a>L0170<br>`apps/worker/src/agent_factory_worker/__init__.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/worker/__init__.py` | 물리 wrapper 제거. Python namespace 유지 매핑·실제 Celery app 등록 필요 |
| <a id="L0171"></a>L0171<br>`apps/worker/src/agent_factory_worker/composition.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/worker/composition.py` | 물리 wrapper 제거. Python namespace 유지 매핑·실제 Celery app 등록 필요 |
| <a id="L0172"></a>L0172<br>`apps/worker/src/agent_factory_worker/main.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `apps/worker/main.py` | 물리 wrapper 제거. Python namespace 유지 매핑·실제 Celery app 등록 필요 |
| <a id="L0173"></a>L0173<br>`contracts/compatibility/breaking/base.schema.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/compatibility/breaking/base.schema.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0174"></a>L0174<br>`contracts/compatibility/breaking/candidate.schema.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/compatibility/breaking/candidate.schema.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0175"></a>L0175<br>`contracts/compatibility/compatible/base.schema.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/compatibility/compatible/base.schema.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0176"></a>L0176<br>`contracts/compatibility/compatible/candidate.schema.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/compatibility/compatible/candidate.schema.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0177"></a>L0177<br>`contracts/examples/catalog/documents-icon.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/examples/catalog/documents-icon.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0178"></a>L0178<br>`contracts/examples/catalog/panel-split.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/examples/catalog/panel-split.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0179"></a>L0179<br>`contracts/examples/catalog/sidebar-favorites-recent.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/examples/catalog/sidebar-favorites-recent.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0180"></a>L0180<br>`contracts/examples/invalid/access-token.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/examples/invalid/access-token.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0181"></a>L0181<br>`contracts/examples/invalid/arbitrary-url.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/examples/invalid/arbitrary-url.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0182"></a>L0182<br>`contracts/examples/invalid/credential.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/examples/invalid/credential.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0183"></a>L0183<br>`contracts/examples/invalid/dismiss-without-target.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/examples/invalid/dismiss-without-target.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0184"></a>L0184<br>`contracts/examples/invalid/expression.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/examples/invalid/expression.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0185"></a>L0185<br>`contracts/examples/invalid/ftp-url.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/examples/invalid/ftp-url.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0186"></a>L0186<br>`contracts/examples/invalid/nested-unsafe-records.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/examples/invalid/nested-unsafe-records.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0187"></a>L0187<br>`contracts/examples/invalid/raw-css.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/examples/invalid/raw-css.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0188"></a>L0188<br>`contracts/examples/invalid/request-headers.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/examples/invalid/request-headers.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0189"></a>L0189<br>`contracts/examples/invalid/theme-raw-css.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/examples/invalid/theme-raw-css.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0190"></a>L0190<br>`contracts/examples/invalid/websocket-url.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/examples/invalid/websocket-url.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0191"></a>L0191<br>`contracts/examples/theme-profile.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/examples/theme-profile.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0192"></a>L0192<br>`contracts/examples/workbenches/documents.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/examples/workbenches/documents.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0193"></a>L0193<br>`contracts/fixtures.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/fixtures.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0194"></a>L0194<br>`contracts/limits.v1.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/limits.v1.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0195"></a>L0195<br>`contracts/schemas/appearance/v1/theme-profile.schema.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/schemas/appearance/v1/theme-profile.schema.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0196"></a>L0196<br>`contracts/schemas/catalog/v1/asset-descriptor.schema.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/schemas/catalog/v1/asset-descriptor.schema.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0197"></a>L0197<br>`contracts/schemas/workbench/v1/action.schema.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/schemas/workbench/v1/action.schema.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0198"></a>L0198<br>`contracts/schemas/workbench/v1/binding.schema.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/schemas/workbench/v1/binding.schema.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0199"></a>L0199<br>`contracts/schemas/workbench/v1/component.schema.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/schemas/workbench/v1/component.schema.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0200"></a>L0200<br>`contracts/schemas/workbench/v1/definition.schema.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/schemas/workbench/v1/definition.schema.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0201"></a>L0201<br>`contracts/schemas/workbench/v1/descriptor.schema.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/schemas/workbench/v1/descriptor.schema.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0202"></a>L0202<br>`contracts/schemas/workbench/v1/panel.schema.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/schemas/workbench/v1/panel.schema.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0203"></a>L0203<br>`contracts/schemas/workbench/v1/release.schema.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/schemas/workbench/v1/release.schema.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0204"></a>L0204<br>`contracts/schemas/workbench/v1/sidebar.schema.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/schemas/workbench/v1/sidebar.schema.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0205"></a>L0205<br>`contracts/schemas/workbench/v1/view-state.schema.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `contracts/schemas/workbench/v1/view-state.schema.json` | 기존 계약·예제 보존. JSON 전용 검증의 새 코드 계약 적용 범위는 별도 검토 |
| <a id="L0206"></a>L0206<br>`docs/original/.gitkeep`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/original/.gitkeep` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0207"></a>L0207<br>`docs/processed/custom-work-code-runtime-research.html`<br>미추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/custom-work-code-runtime-research.html` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0208"></a>L0208<br>`docs/processed/external-db-custom-work-research.html`<br>미추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/external-db-custom-work-research.html` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0209"></a>L0209<br>`docs/processed/mcp-handoff-audit.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/mcp-handoff-audit.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0210"></a>L0210<br>`docs/processed/mcp-implementation-audit.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/mcp-implementation-audit.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0211"></a>L0211<br>`docs/processed/notes/2026-09-05-development-planning.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/notes/2026-09-05-development-planning.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0212"></a>L0212<br>`docs/processed/notes/2026-09-05-workspace-document-storage.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/notes/2026-09-05-workspace-document-storage.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0213"></a>L0213<br>`docs/processed/notes/2026-09-11-greenfield-workbench-architecture.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/notes/2026-09-11-greenfield-workbench-architecture.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0214"></a>L0214<br>`docs/processed/notes/2026-09-11-saas-service-boundaries.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/notes/2026-09-11-saas-service-boundaries.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0215"></a>L0215<br>`docs/processed/notes/2026-09-12-target-directory-structure.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/notes/2026-09-12-target-directory-structure.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0216"></a>L0216<br>`docs/processed/notes/2026-09-12-workbench-baseline.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/notes/2026-09-12-workbench-baseline.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0217"></a>L0217<br>`docs/processed/notes/2026-09-12-workbench-migration-map.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/notes/2026-09-12-workbench-migration-map.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0218"></a>L0218<br>`docs/processed/notes/2026-09-12-workbench-refactoring-status.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/notes/2026-09-12-workbench-refactoring-status.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0219"></a>L0219<br>`docs/processed/notes/2026-09-12-workbench-stage1-evidence.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/notes/2026-09-12-workbench-stage1-evidence.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0220"></a>L0220<br>`docs/processed/notes/2026-09-12-workbench-stage2-evidence.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/notes/2026-09-12-workbench-stage2-evidence.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0221"></a>L0221<br>`docs/processed/notes/2026-09-12-workbench-stage3-evidence.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/notes/2026-09-12-workbench-stage3-evidence.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0222"></a>L0222<br>`docs/processed/notes/2026-09-12-workbench-stage4-evidence.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/notes/2026-09-12-workbench-stage4-evidence.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0223"></a>L0223<br>`docs/processed/notes/2026-09-13-workbench-stage5-evidence.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/notes/2026-09-13-workbench-stage5-evidence.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0224"></a>L0224<br>`docs/processed/notes/2026-09-13-workbench-stage6-evidence.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/notes/2026-09-13-workbench-stage6-evidence.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0225"></a>L0225<br>`docs/processed/notes/2026-09-13-workbench-stage7-evidence.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/notes/2026-09-13-workbench-stage7-evidence.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0226"></a>L0226<br>`docs/processed/notes/2026-09-13-workbench-stage8-evidence.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/notes/2026-09-13-workbench-stage8-evidence.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0227"></a>L0227<br>`docs/processed/notes/2026-09-13-workbench-stage9-evidence.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/notes/2026-09-13-workbench-stage9-evidence.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0228"></a>L0228<br>`docs/processed/notes/2026-09-14-app-retirement-runtime-evidence.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/notes/2026-09-14-app-retirement-runtime-evidence.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0229"></a>L0229<br>`docs/processed/notes/2026-09-14-knowledge-mcp-authority-evidence.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/notes/2026-09-14-knowledge-mcp-authority-evidence.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0230"></a>L0230<br>`docs/processed/notes/2026-09-14-mcp-consumer-authority-evidence.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/notes/2026-09-14-mcp-consumer-authority-evidence.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0231"></a>L0231<br>`docs/processed/notes/reporting-verification.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/notes/reporting-verification.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0232"></a>L0232<br>`docs/processed/notes/설계-경험재사용과프로젝트지식.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/notes/설계-경험재사용과프로젝트지식.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0233"></a>L0233<br>`docs/processed/organization-github-alignment.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/organization-github-alignment.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0234"></a>L0234<br>`docs/processed/organization-implementation.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/organization-implementation.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0235"></a>L0235<br>`docs/processed/saas-plans-organization-permissions-research.html`<br>미추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/saas-plans-organization-permissions-research.html` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0236"></a>L0236<br>`docs/processed/ui-asset-rollout.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/ui-asset-rollout.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0237"></a>L0237<br>`docs/processed/ui-asset-visual-review.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/ui-asset-visual-review.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0238"></a>L0238<br>`docs/processed/ui-kit-acceptance.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/processed/ui-kit-acceptance.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0239"></a>L0239<br>`docs/specification/design-platform/adr/ADR-001-python-typescript-monorepo.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/specification/design-platform/adr/ADR-001-python-typescript-monorepo.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0240"></a>L0240<br>`docs/specification/design-platform/adr/ADR-002-application-runtime-boundaries.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/specification/design-platform/adr/ADR-002-application-runtime-boundaries.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0241"></a>L0241<br>`docs/specification/design-platform/adr/ADR-003-workbench-json-schema.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/specification/design-platform/adr/ADR-003-workbench-json-schema.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0242"></a>L0242<br>`docs/specification/design-platform/adr/ADR-004-single-workbench-registry.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/specification/design-platform/adr/ADR-004-single-workbench-registry.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0243"></a>L0243<br>`docs/specification/design-platform/adr/ADR-005-native-renderer-and-mcp-app-sandbox.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/specification/design-platform/adr/ADR-005-native-renderer-and-mcp-app-sandbox.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0244"></a>L0244<br>`docs/specification/design-platform/adr/ADR-006-postgresql-pgvector-and-rls.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/specification/design-platform/adr/ADR-006-postgresql-pgvector-and-rls.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0245"></a>L0245<br>`docs/specification/design-platform/adr/ADR-007-draft-publish-immutable-release.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/specification/design-platform/adr/ADR-007-draft-publish-immutable-release.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0246"></a>L0246<br>`docs/specification/design-platform/adr/ADR-008-connection-references-and-server-secrets.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/specification/design-platform/adr/ADR-008-connection-references-and-server-secrets.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0247"></a>L0247<br>`docs/specification/design-platform/adr/ADR-009-incremental-port-and-rollback.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/specification/design-platform/adr/ADR-009-incremental-port-and-rollback.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0248"></a>L0248<br>`docs/specification/design-platform/adr/ADR-010-design-system-assets-and-theme.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/specification/design-platform/adr/ADR-010-design-system-assets-and-theme.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0249"></a>L0249<br>`docs/specification/design-platform/index.html`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/specification/design-platform/index.html` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0250"></a>L0250<br>`docs/specification/design-platform/product-overview.html`<br>미추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/specification/design-platform/product-overview.html` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0251"></a>L0251<br>`docs/specification/design-platform/ui-kit-scope.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/specification/design-platform/ui-kit-scope.md` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0252"></a>L0252<br>`docs/specification/info-platform/index.html`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/specification/info-platform/index.html` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0253"></a>L0253<br>`docs/specification/rule-platform/index.html`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/specification/rule-platform/index.html` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0254"></a>L0254<br>`docs/specification/rule-workbench-structure/contract.html`<br>미추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/specification/rule-workbench-structure/contract.html` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0255"></a>L0255<br>`docs/specification/rule-workbench-structure/index.html`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `docs/specification/rule-workbench-structure/index.html` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0256"></a>L0256<br>`package.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `package.json` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0257"></a>L0257<br>`packages/contracts-py/pyproject.toml`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `packages/contracts-py/pyproject.toml` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0258"></a>L0258<br>`packages/contracts-py/src/agent_factory_contracts/__init__.py`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/contracts-py/__init__.py` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0259"></a>L0259<br>`packages/contracts-py/src/agent_factory_contracts/generated/__init__.py`<br>추적 / 존재 | 생성물 경로 후보<br>경로 기준 분류 | `packages/contracts-py/generated/__init__.py` | contracts 스키마·scripts/contracts 생성기가 원본. 직접 편집 금지 |
| <a id="L0260"></a>L0260<br>`packages/contracts-py/src/agent_factory_contracts/generated/models.py`<br>추적 / 존재 | 생성물 경로 후보<br>경로 기준 분류 | `packages/contracts-py/generated/models.py` | contracts 스키마·scripts/contracts 생성기가 원본. 직접 편집 금지 |
| <a id="L0261"></a>L0261<br>`packages/contracts-py/src/agent_factory_contracts/generated/schema_bundle.py`<br>추적 / 존재 | 생성물 경로 후보<br>경로 기준 분류 | `packages/contracts-py/generated/schema_bundle.py` | contracts 스키마·scripts/contracts 생성기가 원본. 직접 편집 금지 |
| <a id="L0262"></a>L0262<br>`packages/contracts-py/src/agent_factory_contracts/validation.py`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/contracts-py/validation.py` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0263"></a>L0263<br>`packages/contracts-ts/package.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `packages/contracts-ts/package.json` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0264"></a>L0264<br>`packages/contracts-ts/src/generated/schema-bundle.ts`<br>추적 / 존재 | 생성물 경로 후보<br>경로 기준 분류 | `packages/contracts-ts/generated/schema-bundle.ts` | contracts 스키마·scripts/contracts 생성기가 원본. 직접 편집 금지 |
| <a id="L0265"></a>L0265<br>`packages/contracts-ts/src/generated/types.ts`<br>추적 / 존재 | 생성물 경로 후보<br>경로 기준 분류 | `packages/contracts-ts/generated/types.ts` | contracts 스키마·scripts/contracts 생성기가 원본. 직접 편집 금지 |
| <a id="L0266"></a>L0266<br>`packages/contracts-ts/src/generated/validators.d.ts`<br>추적 / 존재 | 생성물 경로 후보<br>경로 기준 분류 | `packages/contracts-ts/generated/validators.d.ts` | contracts 스키마·scripts/contracts 생성기가 원본. 직접 편집 금지 |
| <a id="L0267"></a>L0267<br>`packages/contracts-ts/src/generated/validators.js`<br>추적 / 존재 | 생성물 경로 후보<br>경로 기준 분류 | `packages/contracts-ts/generated/validators.js` | contracts 스키마·scripts/contracts 생성기가 원본. 직접 편집 금지 |
| <a id="L0268"></a>L0268<br>`packages/contracts-ts/src/index.ts`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/contracts-ts/index.ts` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0269"></a>L0269<br>`packages/contracts-ts/src/validation.ts`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/contracts-ts/validation.ts` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0270"></a>L0270<br>`packages/contracts-ts/tsconfig.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `packages/contracts-ts/tsconfig.json` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0271"></a>L0271<br>`packages/design-system/catalog/POLICY.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `packages/design-system/catalog/POLICY.md` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0272"></a>L0272<br>`packages/design-system/catalog/provenance.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `packages/design-system/catalog/provenance.json` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0273"></a>L0273<br>`packages/design-system/package.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `packages/design-system/package.json` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0274"></a>L0274<br>`packages/design-system/src/assets/icons/group-open.svg`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/design-system/assets/icons/group-open.svg` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0275"></a>L0275<br>`packages/design-system/src/assets/icons/group.svg`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/design-system/assets/icons/group.svg` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0276"></a>L0276<br>`packages/design-system/src/assets/icons/subtask.svg`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/design-system/assets/icons/subtask.svg` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0277"></a>L0277<br>`packages/design-system/src/assets/icons/task-open.svg`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/design-system/assets/icons/task-open.svg` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0278"></a>L0278<br>`packages/design-system/src/assets/icons/task.svg`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/design-system/assets/icons/task.svg` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0279"></a>L0279<br>`packages/design-system/src/assets/icons/workspace.svg`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/design-system/assets/icons/workspace.svg` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0280"></a>L0280<br>`packages/design-system/src/catalog.ts`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/design-system/catalog.ts` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0281"></a>L0281<br>`packages/design-system/src/components.css`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/design-system/components.css` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0282"></a>L0282<br>`packages/design-system/src/components.tsx`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/design-system/components.tsx` | 단일 공통 컴포넌트 파일을 책임별 components/ 파일로 나눌 심볼 대응 미완료 |
| <a id="L0283"></a>L0283<br>`packages/design-system/src/index.ts`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/design-system/index.ts` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0284"></a>L0284<br>`packages/design-system/src/theme.tsx`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/design-system/theme.tsx` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0285"></a>L0285<br>`packages/design-system/src/tokens.css`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/design-system/tokens.css` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0286"></a>L0286<br>`packages/design-system/tsconfig.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `packages/design-system/tsconfig.json` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0287"></a>L0287<br>`packages/platform-adapters/pyproject.toml`<br>추적 / 존재 | 설정 이동 후보<br>경로 기준 분류 | `packages/adapters/pyproject.toml` | 배포 이름·리소스·namespace 매핑 확인 |
| <a id="L0288"></a>L0288<br>`packages/platform-adapters/src/agent_factory_adapters/__init__.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/__init__.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0289"></a>L0289<br>`packages/platform-adapters/src/agent_factory_adapters/appearance/__init__.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/appearance/__init__.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0290"></a>L0290<br>`packages/platform-adapters/src/agent_factory_adapters/appearance/postgres.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/appearance.py` | PostgreSQL 구현 소유를 한 곳으로 통합; 관련 모델·세션·RLS 연결 검토 |
| <a id="L0291"></a>L0291<br>`packages/platform-adapters/src/agent_factory_adapters/appearance/validation.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/appearance/validation.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0292"></a>L0292<br>`packages/platform-adapters/src/agent_factory_adapters/clock.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/clock.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0293"></a>L0293<br>`packages/platform-adapters/src/agent_factory_adapters/email.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/email.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0294"></a>L0294<br>`packages/platform-adapters/src/agent_factory_adapters/embeddings/knowledge/provider.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/embeddings/knowledge/provider.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0295"></a>L0295<br>`packages/platform-adapters/src/agent_factory_adapters/http_connectors/providers/client.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/http_connectors/providers/client.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0296"></a>L0296<br>`packages/platform-adapters/src/agent_factory_adapters/http_connectors/providers/drivers.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/http_connectors/providers/drivers.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0297"></a>L0297<br>`packages/platform-adapters/src/agent_factory_adapters/identity/__init__.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/identity/__init__.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0298"></a>L0298<br>`packages/platform-adapters/src/agent_factory_adapters/identity/crypto.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/identity/crypto.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0299"></a>L0299<br>`packages/platform-adapters/src/agent_factory_adapters/identity/oauth.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/identity/oauth.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0300"></a>L0300<br>`packages/platform-adapters/src/agent_factory_adapters/identity/postgres.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/identity.py` | PostgreSQL 구현 소유를 한 곳으로 통합; 관련 모델·세션·RLS 연결 검토 |
| <a id="L0301"></a>L0301<br>`packages/platform-adapters/src/agent_factory_adapters/mcp_client/connections/client.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/mcp_client/connections/client.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0302"></a>L0302<br>`packages/platform-adapters/src/agent_factory_adapters/object_storage/knowledge/storage.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/object_storage/knowledge/storage.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0303"></a>L0303<br>`packages/platform-adapters/src/agent_factory_adapters/organizations/__init__.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/organizations/__init__.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0304"></a>L0304<br>`packages/platform-adapters/src/agent_factory_adapters/organizations/crypto.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/organizations/crypto.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0305"></a>L0305<br>`packages/platform-adapters/src/agent_factory_adapters/organizations/postgres.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/organizations.py` | PostgreSQL 구현 소유를 한 곳으로 통합; 관련 모델·세션·RLS 연결 검토 |
| <a id="L0306"></a>L0306<br>`packages/platform-adapters/src/agent_factory_adapters/pgvector/knowledge/search.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/pgvector/knowledge/search.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0307"></a>L0307<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/__init__.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/__init__.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0308"></a>L0308<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/administration.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/administration.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0309"></a>L0309<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/agents/projections.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/agents/projections.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0310"></a>L0310<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/agents/repository.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/agents/repository.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0311"></a>L0311<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/agents/workspace.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/agents/workspace.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0312"></a>L0312<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/audit/__init__.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/audit/__init__.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0313"></a>L0313<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/audit/repository.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/audit/repository.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0314"></a>L0314<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/connections/access.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/connections/access.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0315"></a>L0315<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/connections/collections.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/connections/collections.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0316"></a>L0316<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/connections/credentials.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/connections/credentials.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0317"></a>L0317<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/connections/mcp.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/connections/mcp.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0318"></a>L0318<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/connections/projections.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/connections/projections.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0319"></a>L0319<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/connections/providers.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/connections/providers.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0320"></a>L0320<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/connections/webhooks.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/connections/webhooks.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0321"></a>L0321<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/database/__init__.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/database/__init__.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0322"></a>L0322<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/database/base.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/database/base.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0323"></a>L0323<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/database/session.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/database/session.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0324"></a>L0324<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/database/settings.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/database/settings.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0325"></a>L0325<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/database/tenant.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/database/tenant.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0326"></a>L0326<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/knowledge/audit.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/knowledge/audit.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0327"></a>L0327<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/knowledge/cloud.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/knowledge/cloud.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0328"></a>L0328<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/knowledge/delivery.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/knowledge/delivery.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0329"></a>L0329<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/knowledge/projections.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/knowledge/projections.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0330"></a>L0330<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/knowledge/repository.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/knowledge/repository.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0331"></a>L0331<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/models/__init__.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/models/__init__.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0332"></a>L0332<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/models/audit.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/models/audit.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0333"></a>L0333<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/planning/calendar.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/planning/calendar.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0334"></a>L0334<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/planning/repository.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/planning/repository.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0335"></a>L0335<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/reporting/repository.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/reporting/repository.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0336"></a>L0336<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/scheduling/execution_lease.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/scheduling/execution_lease.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0337"></a>L0337<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/scheduling/projections.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/scheduling/projections.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0338"></a>L0338<br>`packages/platform-adapters/src/agent_factory_adapters/postgres/scheduling/repository.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/scheduling/repository.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0339"></a>L0339<br>`packages/platform-adapters/src/agent_factory_adapters/redis/scheduling/client.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/redis/scheduling/client.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0340"></a>L0340<br>`packages/platform-adapters/src/agent_factory_adapters/redis/scheduling/publisher.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/redis/scheduling/publisher.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0341"></a>L0341<br>`packages/platform-adapters/src/agent_factory_adapters/workbenches/__init__.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/workbenches/__init__.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0342"></a>L0342<br>`packages/platform-adapters/src/agent_factory_adapters/workbenches/catalog.json`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/workbenches/catalog.json` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0343"></a>L0343<br>`packages/platform-adapters/src/agent_factory_adapters/workbenches/postgres.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/workbenches.py` | PostgreSQL 구현 소유를 한 곳으로 통합; 관련 모델·세션·RLS 연결 검토 |
| <a id="L0344"></a>L0344<br>`packages/platform-adapters/src/agent_factory_adapters/workbenches/validation.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/workbenches/validation.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0345"></a>L0345<br>`packages/platform-adapters/src/agent_factory_adapters/workspaces/__init__.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/workspaces/__init__.py` | wrapper 제거. 기술별 소유·리소스 배포·누락 모델 import 확인 |
| <a id="L0346"></a>L0346<br>`packages/platform-adapters/src/agent_factory_adapters/workspaces/postgres.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/adapters/postgres/workspaces.py` | PostgreSQL 구현 소유를 한 곳으로 통합; 관련 모델·세션·RLS 연결 검토 |
| <a id="L0347"></a>L0347<br>`packages/platform-core/pyproject.toml`<br>추적 / 존재 | 설정 이동 후보<br>경로 기준 분류 | `packages/core/pyproject.toml` | 배포 이름·namespace 유지와 실제 flat layout 패키징 매핑 |
| <a id="L0348"></a>L0348<br>`packages/platform-core/src/agent_factory_core/__init__.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/__init__.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0349"></a>L0349<br>`packages/platform-core/src/agent_factory_core/administration/__init__.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/administration/__init__.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0350"></a>L0350<br>`packages/platform-core/src/agent_factory_core/administration/domain.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/administration/domain.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0351"></a>L0351<br>`packages/platform-core/src/agent_factory_core/administration/ports.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/administration/ports.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0352"></a>L0352<br>`packages/platform-core/src/agent_factory_core/administration/use_cases.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/administration/use_cases.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0353"></a>L0353<br>`packages/platform-core/src/agent_factory_core/appearance/__init__.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/appearance/__init__.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0354"></a>L0354<br>`packages/platform-core/src/agent_factory_core/appearance/domain.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/appearance/domain.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0355"></a>L0355<br>`packages/platform-core/src/agent_factory_core/appearance/errors.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/appearance/errors.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0356"></a>L0356<br>`packages/platform-core/src/agent_factory_core/appearance/ports.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/appearance/ports.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0357"></a>L0357<br>`packages/platform-core/src/agent_factory_core/appearance/use_cases.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/appearance/use_cases.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0358"></a>L0358<br>`packages/platform-core/src/agent_factory_core/audit/__init__.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/audit/__init__.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0359"></a>L0359<br>`packages/platform-core/src/agent_factory_core/audit/administration.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/audit/administration.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0360"></a>L0360<br>`packages/platform-core/src/agent_factory_core/connections/__init__.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/connections/__init__.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0361"></a>L0361<br>`packages/platform-core/src/agent_factory_core/connections/administration.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/connections/administration.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0362"></a>L0362<br>`packages/platform-core/src/agent_factory_core/connections/mcp/access.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/connections/mcp/access.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0363"></a>L0363<br>`packages/platform-core/src/agent_factory_core/connections/mcp/configuration.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/connections/mcp/configuration.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0364"></a>L0364<br>`packages/platform-core/src/agent_factory_core/connections/mcp/domain.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/connections/mcp/domain.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0365"></a>L0365<br>`packages/platform-core/src/agent_factory_core/connections/mcp/ports.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/connections/mcp/ports.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0366"></a>L0366<br>`packages/platform-core/src/agent_factory_core/connections/mcp/use_cases.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/connections/mcp/use_cases.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0367"></a>L0367<br>`packages/platform-core/src/agent_factory_core/connections/providers/collection_domain.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/connections/providers/collection_domain.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0368"></a>L0368<br>`packages/platform-core/src/agent_factory_core/connections/providers/collection_ports.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/connections/providers/collection_ports.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0369"></a>L0369<br>`packages/platform-core/src/agent_factory_core/connections/providers/collection_use_cases.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/connections/providers/collection_use_cases.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0370"></a>L0370<br>`packages/platform-core/src/agent_factory_core/connections/providers/credentials.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/connections/providers/credentials.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0371"></a>L0371<br>`packages/platform-core/src/agent_factory_core/connections/providers/domain.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/connections/providers/domain.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0372"></a>L0372<br>`packages/platform-core/src/agent_factory_core/connections/providers/guide.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/connections/providers/guide.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0373"></a>L0373<br>`packages/platform-core/src/agent_factory_core/connections/providers/ports.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/connections/providers/ports.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0374"></a>L0374<br>`packages/platform-core/src/agent_factory_core/connections/providers/queries.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/connections/providers/queries.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0375"></a>L0375<br>`packages/platform-core/src/agent_factory_core/connections/providers/use_cases.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/connections/providers/use_cases.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0376"></a>L0376<br>`packages/platform-core/src/agent_factory_core/connections/providers/webhooks.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/connections/providers/webhooks.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0377"></a>L0377<br>`packages/platform-core/src/agent_factory_core/executions/__init__.py`<br>추적 / 존재 | 분리/배치 미확정<br>경로 기준 분류 | 미정 | executions 상위 공용 초기화·administration을 소비 도메인별로 분석 |
| <a id="L0378"></a>L0378<br>`packages/platform-core/src/agent_factory_core/executions/administration.py`<br>추적 / 존재 | 분리/배치 미확정<br>경로 기준 분류 | 미정 | executions 상위 공용 초기화·administration을 소비 도메인별로 분석 |
| <a id="L0379"></a>L0379<br>`packages/platform-core/src/agent_factory_core/executions/agents/domain.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/agents/domain.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0380"></a>L0380<br>`packages/platform-core/src/agent_factory_core/executions/agents/jobs.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/agents/jobs.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0381"></a>L0381<br>`packages/platform-core/src/agent_factory_core/executions/agents/ports.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/agents/ports.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0382"></a>L0382<br>`packages/platform-core/src/agent_factory_core/executions/agents/queries.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/agents/queries.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0383"></a>L0383<br>`packages/platform-core/src/agent_factory_core/executions/agents/use_cases.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/agents/use_cases.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0384"></a>L0384<br>`packages/platform-core/src/agent_factory_core/executions/planning/domain.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/planning/domain.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0385"></a>L0385<br>`packages/platform-core/src/agent_factory_core/executions/planning/imports.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/planning/imports.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0386"></a>L0386<br>`packages/platform-core/src/agent_factory_core/executions/planning/ports.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/planning/ports.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0387"></a>L0387<br>`packages/platform-core/src/agent_factory_core/executions/planning/use_cases.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/planning/use_cases.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0388"></a>L0388<br>`packages/platform-core/src/agent_factory_core/executions/reporting/domain.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/reporting/domain.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0389"></a>L0389<br>`packages/platform-core/src/agent_factory_core/executions/reporting/ports.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/reporting/ports.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0390"></a>L0390<br>`packages/platform-core/src/agent_factory_core/executions/reporting/use_cases.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/reporting/use_cases.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0391"></a>L0391<br>`packages/platform-core/src/agent_factory_core/executions/scheduling/dispatch.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/scheduling/dispatch.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0392"></a>L0392<br>`packages/platform-core/src/agent_factory_core/executions/scheduling/domain.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/scheduling/domain.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0393"></a>L0393<br>`packages/platform-core/src/agent_factory_core/executions/scheduling/execution.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/scheduling/execution.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0394"></a>L0394<br>`packages/platform-core/src/agent_factory_core/executions/scheduling/ports.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/scheduling/ports.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0395"></a>L0395<br>`packages/platform-core/src/agent_factory_core/executions/scheduling/queries.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/scheduling/queries.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0396"></a>L0396<br>`packages/platform-core/src/agent_factory_core/executions/scheduling/use_cases.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/scheduling/use_cases.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0397"></a>L0397<br>`packages/platform-core/src/agent_factory_core/identity/__init__.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/identity/__init__.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0398"></a>L0398<br>`packages/platform-core/src/agent_factory_core/identity/administration.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/identity/administration.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0399"></a>L0399<br>`packages/platform-core/src/agent_factory_core/identity/authorization.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/identity/authorization.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0400"></a>L0400<br>`packages/platform-core/src/agent_factory_core/identity/domain.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/identity/domain.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0401"></a>L0401<br>`packages/platform-core/src/agent_factory_core/identity/ports.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/identity/ports.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0402"></a>L0402<br>`packages/platform-core/src/agent_factory_core/identity/settings.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/identity/settings.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0403"></a>L0403<br>`packages/platform-core/src/agent_factory_core/identity/use_cases.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/identity/use_cases.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0404"></a>L0404<br>`packages/platform-core/src/agent_factory_core/knowledge/application.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/knowledge/application.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0405"></a>L0405<br>`packages/platform-core/src/agent_factory_core/knowledge/cloud.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/knowledge/cloud.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0406"></a>L0406<br>`packages/platform-core/src/agent_factory_core/knowledge/delivery.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/knowledge/delivery.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0407"></a>L0407<br>`packages/platform-core/src/agent_factory_core/knowledge/domain.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/knowledge/domain.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0408"></a>L0408<br>`packages/platform-core/src/agent_factory_core/knowledge/errors.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/knowledge/errors.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0409"></a>L0409<br>`packages/platform-core/src/agent_factory_core/knowledge/package_queries.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/knowledge/package_queries.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0410"></a>L0410<br>`packages/platform-core/src/agent_factory_core/knowledge/packages.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/knowledge/packages.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0411"></a>L0411<br>`packages/platform-core/src/agent_factory_core/knowledge/ports.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/knowledge/ports.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0412"></a>L0412<br>`packages/platform-core/src/agent_factory_core/knowledge/queries.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/knowledge/queries.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0413"></a>L0413<br>`packages/platform-core/src/agent_factory_core/knowledge/specification_pair.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/knowledge/specification_pair.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0414"></a>L0414<br>`packages/platform-core/src/agent_factory_core/knowledge/use_cases.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/knowledge/use_cases.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0415"></a>L0415<br>`packages/platform-core/src/agent_factory_core/organizations/__init__.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/organizations/__init__.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0416"></a>L0416<br>`packages/platform-core/src/agent_factory_core/organizations/administration.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/organizations/administration.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0417"></a>L0417<br>`packages/platform-core/src/agent_factory_core/organizations/domain.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/organizations/domain.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0418"></a>L0418<br>`packages/platform-core/src/agent_factory_core/organizations/permissions.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/organizations/permissions.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0419"></a>L0419<br>`packages/platform-core/src/agent_factory_core/organizations/policies.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/organizations/policies.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0420"></a>L0420<br>`packages/platform-core/src/agent_factory_core/organizations/ports.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/organizations/ports.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0421"></a>L0421<br>`packages/platform-core/src/agent_factory_core/organizations/system_roles.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/organizations/system_roles.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0422"></a>L0422<br>`packages/platform-core/src/agent_factory_core/organizations/use_cases.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/organizations/use_cases.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0423"></a>L0423<br>`packages/platform-core/src/agent_factory_core/shared/__init__.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/shared/__init__.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0424"></a>L0424<br>`packages/platform-core/src/agent_factory_core/shared/errors.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/shared/errors.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0425"></a>L0425<br>`packages/platform-core/src/agent_factory_core/shared/request_context.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/shared/request_context.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0426"></a>L0426<br>`packages/platform-core/src/agent_factory_core/workbenches/__init__.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/workbenches/__init__.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0427"></a>L0427<br>`packages/platform-core/src/agent_factory_core/workbenches/commands.py`<br>추적 / 존재 | 분리·통합 미완료<br>심볼 확인 | `packages/core/workbenches/use_cases.py` | 기존 JSON 기반 모델/명령/조회와 새 소스·빌드·릴리스 모델 대응 필요. 기존 심볼 폐기 승인 아님 |
| <a id="L0428"></a>L0428<br>`packages/platform-core/src/agent_factory_core/workbenches/domain.py`<br>추적 / 존재 | 분리·통합 미완료<br>심볼 확인 | `packages/core/workbenches/definitions.py`<br>`packages/core/workbenches/releases.py` | 기존 JSON 기반 모델/명령/조회와 새 소스·빌드·릴리스 모델 대응 필요. 기존 심볼 폐기 승인 아님 |
| <a id="L0429"></a>L0429<br>`packages/platform-core/src/agent_factory_core/workbenches/errors.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/workbenches/errors.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0430"></a>L0430<br>`packages/platform-core/src/agent_factory_core/workbenches/policies.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/workbenches/policies.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0431"></a>L0431<br>`packages/platform-core/src/agent_factory_core/workbenches/ports.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/workbenches/ports.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0432"></a>L0432<br>`packages/platform-core/src/agent_factory_core/workbenches/queries.py`<br>추적 / 존재 | 분리·통합 미완료<br>심볼 확인 | `packages/core/workbenches/use_cases.py` | 기존 JSON 기반 모델/명령/조회와 새 소스·빌드·릴리스 모델 대응 필요. 기존 심볼 폐기 승인 아님 |
| <a id="L0433"></a>L0433<br>`packages/platform-core/src/agent_factory_core/workspaces/__init__.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/workspaces/__init__.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0434"></a>L0434<br>`packages/platform-core/src/agent_factory_core/workspaces/administration.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/workspaces/administration.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0435"></a>L0435<br>`packages/platform-core/src/agent_factory_core/workspaces/domain.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/workspaces/domain.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0436"></a>L0436<br>`packages/platform-core/src/agent_factory_core/workspaces/policies.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/workspaces/policies.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0437"></a>L0437<br>`packages/platform-core/src/agent_factory_core/workspaces/ports.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/workspaces/ports.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0438"></a>L0438<br>`packages/platform-core/src/agent_factory_core/workspaces/use_cases.py`<br>추적 / 존재 | 이동 후보<br>경로 기준 분류 | `packages/core/workspaces/use_cases.py` | 기존 심볼·업무 기능 보존; 이름 공간과 최신 조직/개인 요구 정합성은 추가 검토 |
| <a id="L0439"></a>L0439<br>`packages/workbench-editor/package.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `packages/workbench-editor/package.json` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0440"></a>L0440<br>`packages/workbench-editor/src/WorkbenchEditor.tsx`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/workbench-editor/WorkbenchEditor.tsx` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0441"></a>L0441<br>`packages/workbench-editor/src/index.ts`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/workbench-editor/index.ts` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0442"></a>L0442<br>`packages/workbench-editor/tsconfig.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `packages/workbench-editor/tsconfig.json` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0443"></a>L0443<br>`packages/workbench-runtime/package.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `packages/workbench-runtime/package.json` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0444"></a>L0444<br>`packages/workbench-runtime/src/actions.ts`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/workbench-runtime/actions.ts` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0445"></a>L0445<br>`packages/workbench-runtime/src/bindings.ts`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/workbench-runtime/bindings.ts` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0446"></a>L0446<br>`packages/workbench-runtime/src/contracts.ts`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/workbench-runtime/contracts.ts` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0447"></a>L0447<br>`packages/workbench-runtime/src/index.ts`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/workbench-runtime/index.ts` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0448"></a>L0448<br>`packages/workbench-runtime/src/registry.ts`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/workbench-runtime/registry.ts` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0449"></a>L0449<br>`packages/workbench-runtime/src/renderer.tsx`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/workbench-runtime/renderer.tsx` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0450"></a>L0450<br>`packages/workbench-runtime/src/validation.ts`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/workbench-runtime/validation.ts` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0451"></a>L0451<br>`packages/workbench-runtime/src/view-state.ts`<br>추적 / 존재 | 이동·분리 검토<br>경로 기준 분류 | `packages/workbench-runtime/view-state.ts` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0452"></a>L0452<br>`packages/workbench-runtime/tsconfig.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `packages/workbench-runtime/tsconfig.json` | 공개 exports·리소스 경로·신뢰된 UI와 사용자 코드 계약 분리 검토 |
| <a id="L0453"></a>L0453<br>`pnpm-lock.yaml`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `pnpm-lock.yaml` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0454"></a>L0454<br>`pnpm-workspace.yaml`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `pnpm-workspace.yaml` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0455"></a>L0455<br>`pyproject.toml`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `pyproject.toml` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0456"></a>L0456<br>`scripts/contracts/generate_workbench_contracts.py`<br>추적 / 존재 | 유지·소유 검토<br>경로 기준 분류 | `scripts/contracts/generate_workbench_contracts.py` | 생성 도구·검증 도구 책임과 import 경로 확인 |
| <a id="L0457"></a>L0457<br>`scripts/contracts/generate_workbench_validators.mjs`<br>추적 / 존재 | 유지·소유 검토<br>경로 기준 분류 | `scripts/contracts/generate_workbench_validators.mjs` | 생성 도구·검증 도구 책임과 import 경로 확인 |
| <a id="L0458"></a>L0458<br>`scripts/operations/run.py`<br>추적 / 존재 | 이동·보완 후보<br>본문 확인 | `scripts/run.py` | 개발 프로세스 실행기. deploy 절차 아님; 독립 MCP 선택·실제 worker app 연결 필요 |
| <a id="L0459"></a>L0459<br>`scripts/quality/eslint.config.mjs`<br>추적 / 존재 | 유지·소유 검토<br>경로 기준 분류 | `scripts/quality/eslint.config.mjs` | 생성 도구·검증 도구 책임과 import 경로 확인 |
| <a id="L0460"></a>L0460<br>`scripts/quality/prettier.ignore`<br>추적 / 존재 | 유지·소유 검토<br>경로 기준 분류 | `scripts/quality/prettier.ignore` | 생성 도구·검증 도구 책임과 import 경로 확인 |
| <a id="L0461"></a>L0461<br>`scripts/workbenches/generate_workbench_server_catalog.mjs`<br>추적 / 존재 | 유지·소유 검토<br>경로 기준 분류 | `scripts/workbenches/generate_workbench_server_catalog.mjs` | 생성 도구·검증 도구 책임과 import 경로 확인 |
| <a id="L0462"></a>L0462<br>`tests/STRUCTURE.md`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `tests/STRUCTURE.md` | 테스트 소유 구조와 코드 생성/도구 책임 확인; 실행하지 않음 |
| <a id="L0463"></a>L0463<br>`tests/__init__.py`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `tests/__init__.py` | 테스트 소유 구조와 코드 생성/도구 책임 확인; 실행하지 않음 |
| <a id="L0464"></a>L0464<br>`tests/administration/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0465"></a>L0465<br>`tests/administration/api/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/api/administration/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0466"></a>L0466<br>`tests/administration/api/test_admin_composition.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/api/administration/test_admin_composition.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0467"></a>L0467<br>`tests/administration/browser/admin-assets.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/administration/browser/admin-assets.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0468"></a>L0468<br>`tests/administration/core/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/administration/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0469"></a>L0469<br>`tests/administration/core/test_administration.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/administration/test_administration.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0470"></a>L0470<br>`tests/administration/regression/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0471"></a>L0471<br>`tests/administration/regression/test_admin.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0472"></a>L0472<br>`tests/agents/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0473"></a>L0473<br>`tests/agents/api/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/api/agents/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0474"></a>L0474<br>`tests/agents/api/test_evidence_presenter.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/api/agents/test_evidence_presenter.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0475"></a>L0475<br>`tests/agents/core/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/agents/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0476"></a>L0476<br>`tests/agents/core/test_agent_domain.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/agents/test_agent_domain.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0477"></a>L0477<br>`tests/agents/core/test_agent_use_cases.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/agents/test_agent_use_cases.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0478"></a>L0478<br>`tests/agents/regression/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0479"></a>L0479<br>`tests/agents/regression/test_agents.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0480"></a>L0480<br>`tests/agents/web/AgentsWorkbench.test.tsx`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/agents/AgentsWorkbench.test.tsx` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0481"></a>L0481<br>`tests/appearance/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0482"></a>L0482<br>`tests/appearance/adapters/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/adapters/appearance/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0483"></a>L0483<br>`tests/appearance/adapters/test_theme_validation.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/adapters/appearance/test_theme_validation.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0484"></a>L0484<br>`tests/appearance/api/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/api/appearance/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0485"></a>L0485<br>`tests/appearance/api/test_appearance.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/api/appearance/test_appearance.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0486"></a>L0486<br>`tests/appearance/browser/theme-profile.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/appearance/browser/theme-profile.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0487"></a>L0487<br>`tests/appearance/components/theme.test.ts`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/design-system/appearance/theme.test.ts` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0488"></a>L0488<br>`tests/appearance/integration/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/appearance/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0489"></a>L0489<br>`tests/appearance/integration/test_theme_profiles.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/appearance/test_theme_profiles.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0490"></a>L0490<br>`tests/appearance/web/ThemeBootstrap.test.tsx`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/appearance/ThemeBootstrap.test.tsx` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0491"></a>L0491<br>`tests/appearance/web/theme-client.test.ts`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/appearance/theme-client.test.ts` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0492"></a>L0492<br>`tests/architecture/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0493"></a>L0493<br>`tests/architecture/regression/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0494"></a>L0494<br>`tests/architecture/regression/test_architecture_boundaries.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0495"></a>L0495<br>`tests/architecture/test_platform_specification_pairs.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0496"></a>L0496<br>`tests/architecture/test_workbench_dependencies.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0497"></a>L0497<br>`tests/connections/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0498"></a>L0498<br>`tests/connections/adapters/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/adapters/connections/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0499"></a>L0499<br>`tests/connections/adapters/test_pinned_http.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/adapters/connections/test_pinned_http.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0500"></a>L0500<br>`tests/connections/adapters/test_provider_drivers.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/adapters/connections/test_provider_drivers.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0501"></a>L0501<br>`tests/connections/api/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/api/connections/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0502"></a>L0502<br>`tests/connections/api/test_mcp_status.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/api/connections/test_mcp_status.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0503"></a>L0503<br>`tests/connections/api/test_oauth_callback.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/api/connections/test_oauth_callback.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0504"></a>L0504<br>`tests/connections/api/test_provider_collection_routes.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/api/connections/test_provider_collection_routes.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0505"></a>L0505<br>`tests/connections/browser/mcp-clients.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/connections/browser/mcp-clients.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0506"></a>L0506<br>`tests/connections/browser/mcp-handoff.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/connections/browser/mcp-handoff.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0507"></a>L0507<br>`tests/connections/browser/mcp-onboarding.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/connections/browser/mcp-onboarding.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0508"></a>L0508<br>`tests/connections/core/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/connections/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0509"></a>L0509<br>`tests/connections/core/test_mcp_connection_use_cases.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/connections/test_mcp_connection_use_cases.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0510"></a>L0510<br>`tests/connections/core/test_provider_collections.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/connections/test_provider_collections.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0511"></a>L0511<br>`tests/connections/core/test_provider_credentials.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/connections/test_provider_credentials.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0512"></a>L0512<br>`tests/connections/core/test_provider_guide.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/connections/test_provider_guide.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0513"></a>L0513<br>`tests/connections/core/test_provider_webhooks.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/connections/test_provider_webhooks.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0514"></a>L0514<br>`tests/connections/integration/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/connections/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0515"></a>L0515<br>`tests/connections/integration/test_cloud_integrations_collections.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/connections/test_cloud_integrations_collections.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0516"></a>L0516<br>`tests/connections/integration/test_cloud_integrations_packaging.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/connections/test_cloud_integrations_packaging.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0517"></a>L0517<br>`tests/connections/integration/test_cloud_integrations_providers.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/connections/test_cloud_integrations_providers.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0518"></a>L0518<br>`tests/connections/integration/test_integrations.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/connections/test_integrations.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0519"></a>L0519<br>`tests/connections/integration/test_mcp_connections_integration.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/connections/test_mcp_connections_integration.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0520"></a>L0520<br>`tests/connections/integration/test_mcp_integration_credentials.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/connections/test_mcp_integration_credentials.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0521"></a>L0521<br>`tests/connections/regression/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0522"></a>L0522<br>`tests/connections/regression/test_mcp_connections.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0523"></a>L0523<br>`tests/connections/web/ConnectionsWorkbench.test.tsx`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/connections/ConnectionsWorkbench.test.tsx` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0524"></a>L0524<br>`tests/contracts/__init__.py`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `tests/contracts/__init__.py` | 테스트 소유 구조와 코드 생성/도구 책임 확인; 실행하지 않음 |
| <a id="L0525"></a>L0525<br>`tests/contracts/test_schema_compatibility.py`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `tests/contracts/test_schema_compatibility.py` | 테스트 소유 구조와 코드 생성/도구 책임 확인; 실행하지 않음 |
| <a id="L0526"></a>L0526<br>`tests/contracts/test_validation_limits.py`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `tests/contracts/test_validation_limits.py` | 테스트 소유 구조와 코드 생성/도구 책임 확인; 실행하지 않음 |
| <a id="L0527"></a>L0527<br>`tests/contracts/type_contracts.py`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `tests/contracts/type_contracts.py` | 테스트 소유 구조와 코드 생성/도구 책임 확인; 실행하지 않음 |
| <a id="L0528"></a>L0528<br>`tests/contracts/typescript/generated-types.test.ts`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `tests/contracts/typescript/generated-types.test.ts` | 테스트 소유 구조와 코드 생성/도구 책임 확인; 실행하지 않음 |
| <a id="L0529"></a>L0529<br>`tests/contracts/typescript/validation.test.ts`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `tests/contracts/typescript/validation.test.ts` | 테스트 소유 구조와 코드 생성/도구 책임 확인; 실행하지 않음 |
| <a id="L0530"></a>L0530<br>`tests/database/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0531"></a>L0531<br>`tests/database/integration/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/postgres/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0532"></a>L0532<br>`tests/database/integration/test_migrations.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/postgres/test_migrations.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0533"></a>L0533<br>`tests/database/regression/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0534"></a>L0534<br>`tests/database/regression/test_database_foundation.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0535"></a>L0535<br>`tests/design_system/browser/ui-boundaries.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/design-system/browser/ui-boundaries.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0536"></a>L0536<br>`tests/design_system/browser/ui-components.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/design-system/browser/ui-components.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0537"></a>L0537<br>`tests/design_system/browser/ui-screens.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/design-system/browser/ui-screens.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0538"></a>L0538<br>`tests/design_system/browser/verify-compositions.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/design-system/browser/verify-compositions.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0539"></a>L0539<br>`tests/design_system/browser/verify-http.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/design-system/browser/verify-http.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0540"></a>L0540<br>`tests/design_system/browser/verify-inputs.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/design-system/browser/verify-inputs.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0541"></a>L0541<br>`tests/design_system/browser/verify-interactions.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/design-system/browser/verify-interactions.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0542"></a>L0542<br>`tests/design_system/browser/verify-layouts.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/design-system/browser/verify-layouts.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0543"></a>L0543<br>`tests/design_system/browser/verify-navigation.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/design-system/browser/verify-navigation.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0544"></a>L0544<br>`tests/design_system/browser/verify-states.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/design-system/browser/verify-states.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0545"></a>L0545<br>`tests/design_system/browser/verify-uploads.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/design-system/browser/verify-uploads.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0546"></a>L0546<br>`tests/design_system/browser/verify-web-components.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/design-system/browser/verify-web-components.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0547"></a>L0547<br>`tests/design_system/components/catalog.test.ts`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/design-system/design-system/catalog.test.ts` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0548"></a>L0548<br>`tests/design_system/components/components.test.tsx`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/design-system/design-system/components.test.tsx` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0549"></a>L0549<br>`tests/design_system/tools/verify-all.mjs`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0550"></a>L0550<br>`tests/design_system/tools/verify-package.mjs`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0551"></a>L0551<br>`tests/design_system/tools/verify-provenance.mjs`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0552"></a>L0552<br>`tests/design_system/tools/verify-source-kit.cjs`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0553"></a>L0553<br>`tests/identity/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0554"></a>L0554<br>`tests/identity/adapters/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/adapters/identity/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0555"></a>L0555<br>`tests/identity/adapters/test_email_adapter.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/adapters/identity/test_email_adapter.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0556"></a>L0556<br>`tests/identity/adapters/test_identity_adapters.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/adapters/identity/test_identity_adapters.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0557"></a>L0557<br>`tests/identity/api/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/api/identity/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0558"></a>L0558<br>`tests/identity/api/test_identity_composition.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/api/identity/test_identity_composition.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0559"></a>L0559<br>`tests/identity/browser/auth-assets.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/identity/browser/auth-assets.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0560"></a>L0560<br>`tests/identity/core/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/identity/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0561"></a>L0561<br>`tests/identity/core/test_identity.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/identity/test_identity.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0562"></a>L0562<br>`tests/identity/regression/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0563"></a>L0563<br>`tests/identity/regression/test_authentication.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0564"></a>L0564<br>`tests/identity/regression/test_authorization.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0565"></a>L0565<br>`tests/knowledge/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0566"></a>L0566<br>`tests/knowledge/adapters/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/adapters/knowledge/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0567"></a>L0567<br>`tests/knowledge/adapters/test_postgres_forced_rls.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/adapters/knowledge/test_postgres_forced_rls.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0568"></a>L0568<br>`tests/knowledge/adapters/test_storage_and_provider.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/adapters/knowledge/test_storage_and_provider.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0569"></a>L0569<br>`tests/knowledge/api/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/api/knowledge/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0570"></a>L0570<br>`tests/knowledge/api/test_cloud_routes.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/api/knowledge/test_cloud_routes.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0571"></a>L0571<br>`tests/knowledge/api/test_presenters.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/api/knowledge/test_presenters.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0572"></a>L0572<br>`tests/knowledge/api/test_preview.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/api/knowledge/test_preview.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0573"></a>L0573<br>`tests/knowledge/browser/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/knowledge/browser/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0574"></a>L0574<br>`tests/knowledge/browser/cloud-document-delivery.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/knowledge/browser/cloud-document-delivery.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0575"></a>L0575<br>`tests/knowledge/browser/cloud-document-delivery.fixture.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/knowledge/browser/cloud-document-delivery.fixture.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0576"></a>L0576<br>`tests/knowledge/browser/document-editor.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/knowledge/browser/document-editor.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0577"></a>L0577<br>`tests/knowledge/browser/workbench-documents-db.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/knowledge/browser/workbench-documents-db.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0578"></a>L0578<br>`tests/knowledge/core/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/knowledge/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0579"></a>L0579<br>`tests/knowledge/core/test_cloud.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/knowledge/test_cloud.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0580"></a>L0580<br>`tests/knowledge/core/test_package_queries.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/knowledge/test_package_queries.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0581"></a>L0581<br>`tests/knowledge/core/test_packages.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/knowledge/test_packages.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0582"></a>L0582<br>`tests/knowledge/core/test_use_cases.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/knowledge/test_use_cases.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0583"></a>L0583<br>`tests/knowledge/regression/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0584"></a>L0584<br>`tests/knowledge/regression/test_cloud_document_delivery.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0585"></a>L0585<br>`tests/knowledge/regression/test_cloud_document_delivery_http.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0586"></a>L0586<br>`tests/knowledge/regression/test_cloud_documents.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0587"></a>L0587<br>`tests/knowledge/regression/test_cloud_source_inventory.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0588"></a>L0588<br>`tests/knowledge/regression/test_document_paths.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0589"></a>L0589<br>`tests/knowledge/regression/test_document_search.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0590"></a>L0590<br>`tests/knowledge/regression/test_document_template.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0591"></a>L0591<br>`tests/knowledge/regression/test_documents.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0592"></a>L0592<br>`tests/knowledge/regression/test_legacy_document_import.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0593"></a>L0593<br>`tests/knowledge/regression/test_mcp_documents_authority.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0594"></a>L0594<br>`tests/knowledge/web/DocumentEditor.test.tsx`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/knowledge/DocumentEditor.test.tsx` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0595"></a>L0595<br>`tests/knowledge/web/document-bindings.test.ts`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/knowledge/document-bindings.test.ts` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0596"></a>L0596<br>`tests/mcp/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0597"></a>L0597<br>`tests/mcp/regression/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0598"></a>L0598<br>`tests/mcp/regression/test_mcp_server.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0599"></a>L0599<br>`tests/operations/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0600"></a>L0600<br>`tests/operations/api/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/api/operations/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0601"></a>L0601<br>`tests/operations/api/test_health.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/api/operations/test_health.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0602"></a>L0602<br>`tests/operations/fixtures/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0603"></a>L0603<br>`tests/operations/fixtures/workbench_repository.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0604"></a>L0604<br>`tests/operations/fixtures/worker_reference.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0605"></a>L0605<br>`tests/operations/regression/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0606"></a>L0606<br>`tests/operations/regression/test_deployment.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0607"></a>L0607<br>`tests/operations/regression/test_health.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0608"></a>L0608<br>`tests/operations/regression/test_observability.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0609"></a>L0609<br>`tests/operations/web/api-path.test.ts`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/operations/api-path.test.ts` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0610"></a>L0610<br>`tests/operations/worker/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/worker/operations/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0611"></a>L0611<br>`tests/operations/worker/test_smoke.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/worker/operations/test_smoke.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0612"></a>L0612<br>`tests/organizations/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0613"></a>L0613<br>`tests/organizations/browser/organizations.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/organizations/browser/organizations.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0614"></a>L0614<br>`tests/organizations/core/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/organizations/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0615"></a>L0615<br>`tests/organizations/core/test_organization_policies.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/organizations/test_organization_policies.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0616"></a>L0616<br>`tests/organizations/core/test_organization_use_cases.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/organizations/test_organization_use_cases.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0617"></a>L0617<br>`tests/organizations/regression/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0618"></a>L0618<br>`tests/organizations/regression/test_organization_management.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0619"></a>L0619<br>`tests/package.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `tests/package.json` | 테스트 소유 구조와 코드 생성/도구 책임 확인; 실행하지 않음 |
| <a id="L0620"></a>L0620<br>`tests/planning/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0621"></a>L0621<br>`tests/planning/browser/planning.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/planning/browser/planning.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0622"></a>L0622<br>`tests/planning/core/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/planning/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0623"></a>L0623<br>`tests/planning/core/test_planning_domain.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/planning/test_planning_domain.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0624"></a>L0624<br>`tests/planning/core/test_planning_imports.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/planning/test_planning_imports.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0625"></a>L0625<br>`tests/planning/integration/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/planning/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0626"></a>L0626<br>`tests/planning/integration/test_planning_import_integration.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/planning/test_planning_import_integration.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0627"></a>L0627<br>`tests/planning/integration/test_planning_integration.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/planning/test_planning_integration.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0628"></a>L0628<br>`tests/planning/regression/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0629"></a>L0629<br>`tests/planning/regression/test_planning.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0630"></a>L0630<br>`tests/planning/regression/test_planning_calendar.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0631"></a>L0631<br>`tests/planning/regression/test_planning_import.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0632"></a>L0632<br>`tests/platform/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0633"></a>L0633<br>`tests/platform/browser/cloud-platform.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/platform/browser/cloud-platform.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0634"></a>L0634<br>`tests/platform/browser/native-management.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/platform/browser/native-management.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0635"></a>L0635<br>`tests/platform/integration/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/platform/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0636"></a>L0636<br>`tests/platform/integration/test_cloud_platform_integration.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/platform/test_cloud_platform_integration.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0637"></a>L0637<br>`tests/platform/regression/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0638"></a>L0638<br>`tests/platform/regression/test_cloud_platform_packaging.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0639"></a>L0639<br>`tests/platform/web/NativeManagement.test.tsx`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/platform/NativeManagement.test.tsx` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0640"></a>L0640<br>`tests/platform/web/management-clients.test.ts`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/platform/management-clients.test.ts` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0641"></a>L0641<br>`tests/reporting/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0642"></a>L0642<br>`tests/reporting/browser/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/reporting/browser/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0643"></a>L0643<br>`tests/reporting/browser/reporting.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/reporting/browser/reporting.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0644"></a>L0644<br>`tests/reporting/core/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/reporting/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0645"></a>L0645<br>`tests/reporting/core/test_reporting_commands.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/reporting/test_reporting_commands.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0646"></a>L0646<br>`tests/reporting/core/test_reporting_domain.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/reporting/test_reporting_domain.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0647"></a>L0647<br>`tests/reporting/core/test_reporting_use_cases.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/reporting/test_reporting_use_cases.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0648"></a>L0648<br>`tests/reporting/integration/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/reporting/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0649"></a>L0649<br>`tests/reporting/integration/test_reporting_integration.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/reporting/test_reporting_integration.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0650"></a>L0650<br>`tests/reporting/regression/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0651"></a>L0651<br>`tests/reporting/regression/test_cloud_reporting.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0652"></a>L0652<br>`tests/reporting/regression/test_reporting.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0653"></a>L0653<br>`tests/reporting/regression/test_reporting_runtime.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0654"></a>L0654<br>`tests/reporting/web/ReportingWorkbench.test.tsx`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/reporting/ReportingWorkbench.test.tsx` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0655"></a>L0655<br>`tests/scheduling/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0656"></a>L0656<br>`tests/scheduling/adapters/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/adapters/scheduling/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0657"></a>L0657<br>`tests/scheduling/adapters/test_execution_lease_postgres.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/adapters/scheduling/test_execution_lease_postgres.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0658"></a>L0658<br>`tests/scheduling/adapters/test_postgres_conflicts.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/adapters/scheduling/test_postgres_conflicts.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0659"></a>L0659<br>`tests/scheduling/adapters/test_publisher.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/adapters/scheduling/test_publisher.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0660"></a>L0660<br>`tests/scheduling/core/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/scheduling/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0661"></a>L0661<br>`tests/scheduling/core/test_dispatch.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/scheduling/test_dispatch.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0662"></a>L0662<br>`tests/scheduling/core/test_execution.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/scheduling/test_execution.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0663"></a>L0663<br>`tests/scheduling/core/test_scheduling_domain.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/scheduling/test_scheduling_domain.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0664"></a>L0664<br>`tests/scheduling/regression/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0665"></a>L0665<br>`tests/scheduling/regression/test_scheduling.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0666"></a>L0666<br>`tests/scheduling/web/ScheduleWorkbench.test.tsx`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/scheduling/ScheduleWorkbench.test.tsx` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0667"></a>L0667<br>`tests/scheduling/web/schedule-client.test.ts`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/scheduling/schedule-client.test.ts` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0668"></a>L0668<br>`tests/scheduling/worker/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/worker/scheduling/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0669"></a>L0669<br>`tests/security/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0670"></a>L0670<br>`tests/security/integration/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/security/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0671"></a>L0671<br>`tests/security/integration/test_multitenancy.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/security/test_multitenancy.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0672"></a>L0672<br>`tests/security/regression/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0673"></a>L0673<br>`tests/security/regression/test_security.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0674"></a>L0674<br>`tests/support/__init__.py`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `tests/support/__init__.py` | 테스트 소유 구조와 코드 생성/도구 책임 확인; 실행하지 않음 |
| <a id="L0675"></a>L0675<br>`tests/support/auth.py`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `tests/support/auth.py` | 테스트 소유 구조와 코드 생성/도구 책임 확인; 실행하지 않음 |
| <a id="L0676"></a>L0676<br>`tests/support/fastapi.py`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `tests/support/fastapi.py` | 테스트 소유 구조와 코드 생성/도구 책임 확인; 실행하지 않음 |
| <a id="L0677"></a>L0677<br>`tests/support/inventory.py`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `tests/support/inventory.py` | 테스트 소유 구조와 코드 생성/도구 책임 확인; 실행하지 않음 |
| <a id="L0678"></a>L0678<br>`tests/support/mcp.py`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `tests/support/mcp.py` | 테스트 소유 구조와 코드 생성/도구 책임 확인; 실행하지 않음 |
| <a id="L0679"></a>L0679<br>`tests/tools/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/support/tools/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0680"></a>L0680<br>`tests/tools/check_workbench_contract_parity.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/support/tools/check_workbench_contract_parity.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0681"></a>L0681<br>`tests/tools/check_workbench_dependencies.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/support/tools/check_workbench_dependencies.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0682"></a>L0682<br>`tests/tools/check_workbench_schema_compatibility.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/support/tools/check_workbench_schema_compatibility.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0683"></a>L0683<br>`tests/tools/prepare_theme_verifier.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/support/tools/prepare_theme_verifier.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0684"></a>L0684<br>`tests/tools/validate_workbench_contracts_ts.ts`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/support/tools/validate_workbench_contracts_ts.ts` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0685"></a>L0685<br>`tests/tools/verify-native-management.sh`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/support/tools/verify-native-management.sh` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0686"></a>L0686<br>`tests/tools/verify-workbench-runtime.sh`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/support/tools/verify-workbench-runtime.sh` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0687"></a>L0687<br>`tests/tsconfig.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `tests/tsconfig.json` | 테스트 소유 구조와 코드 생성/도구 책임 확인; 실행하지 않음 |
| <a id="L0688"></a>L0688<br>`tests/vitest.config.mts`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `tests/vitest.config.mts` | 테스트 소유 구조와 코드 생성/도구 책임 확인; 실행하지 않음 |
| <a id="L0689"></a>L0689<br>`tests/workbenches/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0690"></a>L0690<br>`tests/workbenches/api/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/api/workbenches/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0691"></a>L0691<br>`tests/workbenches/api/test_workbenches.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/api/workbenches/test_workbenches.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0692"></a>L0692<br>`tests/workbenches/browser/workbench-authoring-db.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/workbenches/browser/workbench-authoring-db.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0693"></a>L0693<br>`tests/workbenches/browser/workbench-catalog.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/workbenches/browser/workbench-catalog.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0694"></a>L0694<br>`tests/workbenches/browser/workbench-runtime-editor.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/workbenches/browser/workbench-runtime-editor.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0695"></a>L0695<br>`tests/workbenches/browser/workbench-shell.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/workbenches/browser/workbench-shell.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0696"></a>L0696<br>`tests/workbenches/core/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/workbenches/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0697"></a>L0697<br>`tests/workbenches/core/test_standard_workbench_ids.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/workbenches/test_standard_workbench_ids.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0698"></a>L0698<br>`tests/workbenches/editor/WorkbenchEditor.test.tsx`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/workbench-editor/WorkbenchEditor.test.tsx` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0699"></a>L0699<br>`tests/workbenches/integration/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/workbenches/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0700"></a>L0700<br>`tests/workbenches/integration/test_workbench_persistence_integration.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/workbenches/test_workbench_persistence_integration.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0701"></a>L0701<br>`tests/workbenches/regression/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0702"></a>L0702<br>`tests/workbenches/regression/test_workbench_mcp.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0703"></a>L0703<br>`tests/workbenches/regression/test_workbench_shadow_route.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0704"></a>L0704<br>`tests/workbenches/runtime/bindings.test.ts`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/workbench-runtime/bindings.test.ts` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0705"></a>L0705<br>`tests/workbenches/runtime/index.test.ts`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/workbench-runtime/index.test.ts` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0706"></a>L0706<br>`tests/workbenches/runtime/renderer-actions.test.tsx`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/workbench-runtime/renderer-actions.test.tsx` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0707"></a>L0707<br>`tests/workbenches/runtime/runtime-contracts.test.tsx`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/workbench-runtime/runtime-contracts.test.tsx` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0708"></a>L0708<br>`tests/workbenches/web/App.test.tsx`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/workbenches/App.test.tsx` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0709"></a>L0709<br>`tests/workbenches/web/WorkbenchContext.test.tsx`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/workbenches/WorkbenchContext.test.tsx` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0710"></a>L0710<br>`tests/workbenches/web/WorkbenchRegistry.test.ts`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/workbenches/WorkbenchRegistry.test.ts` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0711"></a>L0711<br>`tests/workspaces/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0712"></a>L0712<br>`tests/workspaces/adapters/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/adapters/workspaces/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0713"></a>L0713<br>`tests/workspaces/adapters/test_workspace_location_adapter.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/adapters/workspaces/test_workspace_location_adapter.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0714"></a>L0714<br>`tests/workspaces/browser/workspace-start.cjs`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/web/workspaces/browser/workspace-start.cjs` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0715"></a>L0715<br>`tests/workspaces/core/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/workspaces/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0716"></a>L0716<br>`tests/workspaces/core/test_workspace_policies.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/workspaces/test_workspace_policies.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0717"></a>L0717<br>`tests/workspaces/core/test_workspace_use_cases.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/packages/core/workspaces/test_workspace_use_cases.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0718"></a>L0718<br>`tests/workspaces/integration/__init__.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/workspaces/__init__.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0719"></a>L0719<br>`tests/workspaces/integration/test_personal_workspaces_integration.py`<br>추적 / 존재 | 테스트 이동 후보<br>경로 기준 분류 | `tests/integration/workspaces/test_personal_workspaces_integration.py` | 경로 기준 소유 후보. 실제 피검증 import·공통 fixture·실행 설정 검토 필요 |
| <a id="L0720"></a>L0720<br>`tests/workspaces/regression/__init__.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0721"></a>L0721<br>`tests/workspaces/regression/test_personal_workspaces.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0722"></a>L0722<br>`tests/workspaces/regression/test_workspace_management.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0723"></a>L0723<br>`tests/workspaces/regression/test_workspace_ui.py`<br>추적 / 존재 | 테스트 소유 미확정<br>경로 기준 분류 | 미정 | regression·architecture·도메인 __init__·도구를 실제 피검증 대상별로 분류해야 함 |
| <a id="L0724"></a>L0724<br>`tsconfig.json`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `tsconfig.json` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |
| <a id="L0725"></a>L0725<br>`uv.lock`<br>추적 / 존재 | 유지 후보<br>경로 기준 분류 | `uv.lock` | 기존 경로 보존. 경로를 참조하는 문서·설정은 이전 시 동기화 |

<a id="캡처-당시-미커밋-상태"></a>

### 3.1. 캡처 당시 미커밋 상태

```text
M .codex/skills/design-platform/SKILL.md
 M .codex/skills/design-platform/references/workbench-runtime.md
 M .codex/skills/rule-workbench-structure/SKILL.md
 M .codex/skills/rule-workbench-structure/references/target-structure.md
 M docs/specification/design-platform/index.html
 M docs/specification/rule-workbench-structure/index.html
?? .codex/skills/design-platform/references/product-overview.md
?? .codex/skills/rule-workbench-structure/references/directory-contract.md
?? docs/processed/custom-work-code-runtime-research.html
?? docs/processed/external-db-custom-work-research.html
?? docs/processed/saas-plans-organization-permissions-research.html
?? docs/specification/design-platform/product-overview.html
?? docs/specification/rule-workbench-structure/contract.html
```

<a id="첨부-자료"></a>

## 4. 첨부 자료

- [structure-migration-ledger.json](assets/structure-migration-ledger.json)
