---
name: rule-extension-development
description: 공급자용 Agent Factory 익스텐션 프로젝트 규칙입니다. 사용자 배포 스킬·플러그인 개발 문서·익스텐션 개발 문서를
  구분하고 Host/Webview·연동·버전·패키징 변경에 적용합니다.
metadata:
  document-type: specification
  category: rule
  domain: null
  name: extension-development
  language: ko
  provenance:
    prior-provenance:
      organization-authority: Human approved these three package identities and organization
        on 2026-09-16 KST; unresolved semantic changes remain unresolved.
      version-alignment-authority: Human explicitly required matching plugin and extension
        versions in project-local skills on 2026-09-16 KST.
      collected-on: '2026-09-16'
      sources:
      - historical-source-path: docs/directory-structure.md
        preserved-record: docs/processed/other-directory-structure-history/SKILL.md
      - historical-source-path: docs/requirements.md
        preserved-record: docs/processed/other-requirements-history/SKILL.md
      - installed Convention references/documents.md
    merged-from:
    - docs/skills/rule-extension-development/SKILL.md
    source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
    merge-request: run-20260918T152016183617Z-2d18ad49
    source-metadata:
      name: rule-extension-development
      description: 공급자용 Agent Factory 익스텐션 프로젝트 규칙입니다. 사용자 배포 스킬·플러그인 개발 문서·익스텐션 개발
        문서를 구분하고 Host/Webview·연동·버전·패키징 변경에 적용합니다.
      metadata:
        document-type: specification
        category: rule
        domain: null
        name: extension-development
        language: ko
        provenance:
          organization-authority: Human approved these three package identities and
            organization on 2026-09-16 KST; unresolved semantic changes remain unresolved.
          version-alignment-authority: Human explicitly required matching plugin and
            extension versions in project-local skills on 2026-09-16 KST.
          collected-on: '2026-09-16'
          sources:
          - historical-source-path: docs/directory-structure.md
            preserved-record: docs/processed/other-directory-structure-history/SKILL.md
          - historical-source-path: docs/requirements.md
            preserved-record: docs/processed/other-requirements-history/SKILL.md
          - installed Convention references/documents.md
---


# Agent Factory 익스텐션 프로젝트 규칙

- 최신 버전 설치는 사용 조건이 아닙니다. 설치된 익스텐션과 플러그인의 동일 기본 버전을 기준으로 호환성을 확인하고 실행 파일을 선택합니다.

<a id="자동-플러그인-설치-경계"></a>

## 1. 자동 플러그인 설치 경계

- 설치는 workspace Extension Host의 Codex CLI를 고정 실행 파일명·인자 배열로 호출합니다. 작업 영역의 명령·셸 문자열을 실행하지 않으며 의존성 CLI의 작업 디렉터리는 호스트 홈으로 고정합니다.
- 정상 호환 설치 확인 경로에서는 네트워크 변경을 하지 않습니다. 복구 경로의 프로세스 시간·출력을 제한하고 중복 설치를 합칩니다.
- 공식 Marketplace 등록은 부재 시에만 수행하고 기존 같은 이름의 다른 소스를 덮어쓰지 않습니다. 설치 후 동일 기본 버전과 활성 상태를 재확인해야 하며 실패를 성공으로 처리하지 않습니다.

<a id="적용-범위"></a>

## 2. 적용 범위

- 이 규칙은 Agent Factory 익스텐션 저장소 개발에만 적용합니다.
- 상대 경로는 익스텐션 저장소 루트를 기준으로 합니다.

- 작업 전에 독자와 수정 대상을 기준으로 아래 세 도메인을 구분합니다.
- 사용자·공급자는 문서의 독자와 목적을 뜻합니다. `SKILL.md`나 `../.codex/skills/`라는 경로만으로 판단하지 않습니다.

| 도메인 | 독자 | 목적과 내용 | 정본 위치 |
|---|---|---|---|
| Agent Factory 스킬 | 제품을 사용하는 다른 사용자 | 사용자의 작업 수행에 필요한 기능·명령·사용 계약 | `<plugin-root>/skills/{agent,convention,document}/` |
| Agent Factory 플러그인 프로젝트 스킬 문서 | 플러그인 개발자·개발 Agent(공급자) | 배포 스킬·런타임·패키지의 개발 규칙과 설계 | `<agent-factory-root>/docs/skills/` |
| Agent Factory 익스텐션 프로젝트 스킬 문서 | 익스텐션 개발자·개발 Agent(공급자) | Extension Host·화면·adapter·VSIX의 개발 규칙과 설계 | `<agent-factory-root>/docs/skills/` |

- 배포 스킬의 소스를 개발자가 수정하더라도 해당 문서의 독자는 사용자입니다.
- 공급자의 저장소 구조·개발 절차·내부 설계·릴리스 규칙은 해당 프로젝트 스킬 문서에 기록합니다.
- 공급자 프로젝트 문서를 사용자 배포 스킬에 복사하거나 사용자 실행 지침으로 적용하지 않습니다.
- 상위 Agent Factory 저장소의 `.codex/skills/`는 같은 저장소 `docs/skills/`의 파생본입니다. 사용자에게 배포하는 스킬이 아닙니다.
- 플러그인 개발 규칙은 `rule-plugin-development`, 익스텐션 개발 규칙은 `rule-extension-development`에서 확인합니다.
- 여러 도메인에 걸친 요청은 수정 대상을 나누고 각 소유 문서에 반영합니다. 한쪽의 규칙으로 다른 쪽의 규칙을 대체하지 않습니다.
- 공동 배포는 두 프로젝트의 문서 소유권을 합치지 않습니다.
- MCP 서비스는 플러그인·익스텐션 서비스와 독립적입니다. MCP 사용·운영 지침과 구현을 세 도메인의 문서나 제품 기능에 섞지 않습니다.

- 채팅 요구사항은 [채팅 설계](../design-main-chat/SKILL.md)가 소유합니다.
- 현재 소스 위치와 연동 정보는 [구조 정보](../info-extension-architecture/SKILL.md)가 소유합니다.
- 익스텐션은 Extension Host·채팅 화면·설정·런타임 adapter·VSIX를 개발합니다.
- 플러그인의 스킬·런타임·역할 프롬프트·Marketplace 패키지는 플러그인 저장소가 개발합니다.
- MCP 서버와 Workspace 구현은 이 저장소의 개발 범위가 아닙니다.
- `src/webview/`와 아래 명명 규칙의 충돌은 미해결입니다.
  - 이 문서 정리는 코드 이동이나 규칙 폐기를 승인하지 않습니다.

<a id="명세-원문과-skill-노출"></a>

## 3. 명세 원문과 Skill 노출

- 각 명세의 의미는 `../docs/skills/<identity>/SKILL.md`에서만 편집합니다. 한국어 본문과 필요한 `assets/`가 원문입니다.
- `../.codex/skills/<identity>/`는 `../docs/skills/<identity>/`의 본문과 첨부를 단방향으로 동기화한 파생본입니다. 수정은 상위 저장소의 `docs` 정본에서 수행하며 파생본에 별도 요구사항을 축적하지 않습니다.
- HTML 또는 영어 번역을 필수로 만들지 않습니다. 향후 파생 표시물을 만들더라도 별도 편집 원본으로 삼지 않습니다.
- 원문에는 document-type, category, domain, name, language와 실제 provenance를 기록합니다. 도메인이 정의되지 않은 현재 값은 null입니다.
- 기존 네 문서의 역사 기록은 `../docs/processed/other-*-history/SKILL.md`에 있으며 최신 사실·명세의 경쟁 원본이 아닙니다. 당시 본문·외부 링크·확인 요청을 보존합니다. 옛 docs 루트 파일은 이전 후 제거하며 별도 history 루트나 stub을 두지 않습니다. 매핑은 [구조 정보](../info-extension-architecture/SKILL.md)를 참조하십시오.
- `business-mode.ts`의 문서 작성 지침도 `../docs/skills/` 정본을 사용하며, `../.codex/skills/`에는 정본을 덮어써 동기화합니다.

<a id="구조-원칙"></a>

## 4. 구조 원칙

- 저장소 루트는 하나의 VS Code 확장 패키지다.
- `core`, `common`, 기능 `modules`, 외부 연동 `infrastructure`를 구분한다.
- VS Code의 Webview API는 사용하지만 소스 디렉터리 이름으로 `webview`를 사용하지
  않는다. 화면 리소스는 `templates/`와 `static/`에 둔다.
- Agent Factory 플러그인의 런타임 코드를 복사하거나 포크하지 않는다.
- `<runtime-home>/projects/<project-id>/`는 확장 소스가 아니라 런타임 소유 데이터다. 저장 위치는 `exec.py init` 응답을 따른다.
- 웹 Workspace 코드를 이 저장소에 포함하지 않는다.
- `.backup/`과 빌드 중간 산출물은 확장 패키지에서 제외한다.

<a id="책임-경계"></a>

## 5. 책임 경계

| 영역 | 책임 | 포함하지 않는 것 |
| --- | --- | --- |
| `extension.ts` | VS Code 진입점에서 `core` 구동 및 종료 | 기능 구현과 런타임 세부사항 |
| `core` | 확장 초기화, 의존성 조립, 생명주기, 설정 병합 | 채팅 기능 세부사항, VS Code adapter 구현 |
| `common` | 여러 영역에서 공유하는 기술 중립 타입·오류·이벤트·계약 | VS Code 타입, Agent Factory JSON, 잡다한 utils |
| `modules` | 채팅, 세션, 실행, Resume, 승인, 첨부, 스냅샷, 설정 기능 | 자식 프로세스 및 VS Code API 직접 호출 |
| `infrastructure/agent-factory` | 플러그인 탐색, capability 확인, `exec.py` 호출, 이벤트 읽기와 변환 | 런타임 schema 임의 확장과 상태 파일 직접 쓰기 |
| `infrastructure/vscode` | 설정 저장소, Quick Pick, 알림, 파일 열기, Diff, DnD | Agent Factory 기능 규칙 |
| `infrastructure/filesystem` | 경로 검사와 필요한 읽기 전용 파일 접근 | 세션 상태의 우회 변경 |
| `protocol` | Extension Host와 채팅 화면 사이의 검증 가능한 메시지 계약 | DOM 객체, 함수, 검증되지 않은 payload |
| `templates` | 채팅 문서 뼈대와 안전한 리소스 placeholder | 인라인 스크립트 및 인라인 스타일 |
| `static` | 채팅 화면의 CSS, 브라우저 JS, 이미지와 폰트 | Node.js API와 Extension Host 전용 코드 |

<a id="common-승격-기준"></a>

### 5.1. `common` 승격 기준

- 한 기능에서만 사용하는 코드는 해당 `modules/<feature>/`에 둔다.
- 실제로 둘 이상의 영역에서 공유하는 기술 중립 요소만 `common/`으로 옮긴다.
- `utils.ts`, `helpers.ts` 같은 무제한 수집 파일은 만들지 않는다.
- 화면에 직렬화되는 메시지 형식은 공유되더라도 `protocol/`에 둔다.

<a id="의존-관계"></a>

## 6. 의존 관계

```text
extension.ts
    │
    ▼
  core ─────────────── 조립 ──────────────┐
    │                                     │
    ├────────> modules ───────> common    │
    │              │                      │
    └────────> infrastructure ────────────┘
                       │
                       ├── Agent Factory Runtime
                       ├── VS Code API
                       └── File System

templates/static ◄──── protocol ────► modules/chat
```

- `core`는 이 프로젝트에서 의존성 없는 도메인 계층이 아니라 확장 전체를 조립하는
  구동부다.
- `common`은 `core`, `modules`, `infrastructure`, `protocol`을 import하지 않는다.
- 모듈이 요구하는 외부 기능은 계약으로 표현하고 `infrastructure` 구현체를
  `core/container.ts`에서 연결한다.
- Agent Factory 원본 이벤트를 그대로 화면에 전달하지 않고 내부 이벤트와 protocol
  메시지로 변환한다.
- 화면에서 온 메시지는 protocol 검증 후 해당 module로 전달한다.

<a id="설정-경계"></a>

## 7. 설정 경계

- 설정 우선순위는 다음과 같다.

```text
세션 override > 프로젝트 기본값 > Codex 전역값 > 확장 fallback
```

- `core/config/types.ts`: 설정 모델
- `core/config/defaults.ts`: 확장 자체 fallback
- `core/config/resolver.ts`: 범위별 설정 병합 규칙
- `modules/settings/`: 설정 조회·변경 use case와 화면 동작
- `infrastructure/vscode/configuration-store.ts`: VS Code 프로젝트 설정 읽기·쓰기
- `infrastructure/agent-factory/`: 세션 및 Codex 전역 설정 연동
- `package.json`: `contributes.configuration` 항목 선언

- 확장은 파일이나 DB를 직접 세션 저장소로 사용하지 않는다. 세션과 실행의 영속 상태는 Agent Factory가 소유하고, 확장은 Agent Runtime 스크립트만 호출한다. 향후 Agent Factory가 내부 저장 방식으로 DB를 도입해도 이 경계는 바뀌지 않는다.

<a id="화면-리소스와-보안"></a>

## 8. 화면 리소스와 보안

- `templates/chat.html`에는 CSP, nonce, CSS URI, JS URI와 최소 bootstrap 값만
  안전하게 주입한다.
- 스크립트와 스타일은 인라인으로 넣지 않고 `static/js`, `static/css`에서
  `asWebviewUri`로 로드한다.
- `localResourceRoots`는 필요한 `templates/` 및 `static/` 범위로 제한한다.
- 선택 목록을 추가하거나 변경할 때 기존 공통 선택 목록 디자인을 재사용합니다. 권한·모델·추론·언어 선택에 별도 디자인을 만들지 않습니다.
- 선택 컨트롤과 열린 목록의 여백·테두리·화살표·선택·호버 상태는 `static/css/chat.css`의 공통 스타일에서 관리합니다. 키보드 조작과 접근성 의미를 유지하며, 스타일 미지원 환경에서는 기본 선택 기능을 보존합니다.
- 화면 JS는 `acquireVsCodeApi()`를 통해서만 Extension Host와 통신한다.
- 파일 시스템, 자식 프로세스, 인증 정보에는 화면에서 직접 접근하지 않는다.

<a id="공동-배포에서-익스텐션의-책임"></a>

## 9. 공동 배포에서 익스텐션의 책임

- Agent Factory의 지원 구성 요소는 익스텐션, 플러그인, MCP입니다.
- 배포 단위는 `익스텐션 + 플러그인`과 `MCP` 두 가지입니다.
- 익스텐션과 플러그인은 반드시 동일한 기본 버전으로 함께 배포합니다.
  - 주 버전 일치나 호환 범위로 대체하지 않습니다.
  - 별도 패키지를 사용하더라도 하나의 공동 릴리스로 관리합니다.
- 익스텐션 `package.json`과 `package-lock.json`의 최상위·루트 패키지 버전을 확인합니다.
  - 플러그인 담당 저장소가 제공하는 기본 버전·게시 증거와 대조합니다.
  - 플러그인의 `+codex.<cachebuster>` 빌드 메타데이터만 비교에서 제외합니다.
- 기본 버전 변경은 양쪽 저장소의 같은 목표 버전으로 조율합니다.
  - 익스텐션 작업에서는 익스텐션 설치 안내와 배포 계약 검사를 갱신합니다.
- 익스텐션 저장소는 VSIX 빌드·검사·게시를 담당합니다.
  - 플러그인 캐시버스터·Python 검사·Marketplace 게시 절차를 이 규칙으로 대체하지 않습니다.
- 양쪽 배포 산출물이 같은 기본 버전으로 제공되어야 공동 배포가 완료됩니다.
  - 익스텐션 배포 전에 대상 Marketplace의 플러그인 제공 여부를 확인합니다.
  - 한쪽만 게시했거나 로컬 소스만 일치하면 배포 완료로 보고하지 않습니다.
- `익스텐션 + 플러그인`은 MCP 없이 독립적으로 동작합니다.
- MCP는 익스텐션·플러그인 없이 독립적으로 동작하고 배포합니다.
  - MCP의 버전과 배포 일정은 익스텐션·플러그인에 종속되지 않습니다.
- 버전 변경·패키징·배포 시 일치 여부와 양쪽 제공 상태를 보고합니다.
- 이 규칙은 요청 범위 밖의 커밋·게시 권한을 부여하지 않습니다.

<a id="빌드-원격-실행과-패키징"></a>

## 10. 빌드, 원격 실행과 패키징

- `package.json.main`은 `dist/extension.js`를 가리킨다.
- `extensionKind`는 workspace 우선으로 선언하여 WSL/Remote 환경의 프로젝트와
  Agent Factory Runtime 가까이에서 Extension Host가 실행되도록 한다.
- `templates/`와 실행에 필요한 `static/` 리소스는 VSIX에 포함한다.
- `.backup/`, `docs/`, 테스트, source map, 임시 첨부와 `.agent-factory/`는 VSIX에서
  제외한다.
- Agent Factory 플러그인과 Codex CLI 바이너리는 VSIX에 중복 포함하지 않는다.
- 패키징 검증은 `package.json.main`, 템플릿, 정적 리소스와 불필요 파일 제외 여부를
  확인한다.

<a id="테스트-구조"></a>

## 11. 테스트 구조

- `unit`: config 우선순위, 공통 타입, 모듈 상태 전이, protocol 검증, 경로 검증
- `integration`: 가짜 `exec.py`와 이벤트 fixture를 이용한 submit, send, Resume,
  cancel 및 복원
- `e2e`: Extension Development Host에서 편집기 탭, serializer, DnD, 승인, Diff와
  알림 검증
- `fixtures`: 비밀값 없는 최소 Agent Factory 세션과 이벤트

- 실제 사용자 런타임 `<runtime-home>/projects/<project-id>/agents/`나 Codex 인증 정보를 테스트 fixture로 사용하지 않는다.

<a id="런타임-쓰기-경계"></a>

## 12. 런타임 쓰기 경계

- 상태 변경은 Agent Factory Runtime 명령을 사용합니다. 확장은 `session.json`이나 run 상태 파일을 직접 생성·수정하지 않습니다.
- append-only 이벤트처럼 런타임이 읽기 계약을 제공한 파일만 직접 읽습니다. 첨부 준비 파일과 UI 상태는 세션·실행 상태 파일과 구분합니다.
- 저장 경로 변경은 파일·세션 소유권 변경이 아닙니다. 홈 런타임 위치와 identity는 [구조 정보](../info-extension-architecture/SKILL.md)를 참조하십시오.
