---
name: rule-plugin-development
description: 공급자용 Agent Factory 플러그인 프로젝트 규칙입니다. 사용자 배포 스킬·플러그인 개발 문서·익스텐션 개발 문서를
  구분하고 플러그인 개발·테스트·공동 배포에 적용합니다.
metadata:
  document-type: specification
  category: rule
  domain: null
  name: plugin-development
  language: ko
  provenance:
    prior-provenance: null
    merged-from:
    - docs/skills/rule-plugin-development/SKILL.md
    source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
    merge-request: run-20260918T152016183617Z-2d18ad49
    source-metadata:
      name: rule-plugin-development
      description: 공급자용 Agent Factory 플러그인 프로젝트 규칙입니다. 사용자 배포 스킬·플러그인 개발 문서·익스텐션 개발
        문서를 구분하고 플러그인 개발·테스트·공동 배포에 적용합니다.
      metadata:
        document-type: specification
        category: rule
        domain: null
        name: plugin-development
        language: ko
---


# Agent Factory 플러그인 프로젝트 규칙

<a id="적용-범위와-개발-책임"></a>

## 1. 적용 범위와 개발 책임

- 이 규칙은 Agent Factory 플러그인 저장소 개발에만 적용합니다.
- 익스텐션의 화면·Extension Host·VSIX 구현과 MCP 서버 개발에는 적용하지 않습니다.
- 문서의 상대 경로는 플러그인 저장소 루트를 기준으로 합니다.

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

| 경로 | 플러그인 프로젝트의 개발 책임 |
|---|---|
| `skills/` | 배포할 스킬 구현과 실행 지침 |
| `skills/agent/scripts/` | 실행 진입점 |
| `skills/agent/runtime/` | 세션·실행·receipt·프로세스 관리 구현 |
| `skills/agent/prompt/` | 관리형 역할 프롬프트 원문 |
| `.codex-plugin/plugin.json` | 플러그인 메타데이터와 버전 |
| `hooks/` | 플러그인 훅 구성 |
| `tests/` | 플러그인 계약·런타임·통합 검사 |

- 배포 문서와 실행 지침은 영어로 작성합니다.
- 런타임 데이터는 경로 해석기를 통해 저장소 밖에 둡니다.
- 익스텐션 소스·VSIX와 MCP 서비스·Workspace 자산을 플러그인에 포함하지 않습니다.
- 이 프로젝트 규칙의 정본은 `../docs/skills/rule-plugin-development/SKILL.md`입니다.
- `../.codex/skills/rule-plugin-development/`는 해당 정본의 파생본입니다.

<a id="공동-배포에서-플러그인의-책임"></a>

## 2. 공동 배포에서 플러그인의 책임

- 지원 구성 요소는 익스텐션, 플러그인, MCP입니다.
- 독립 배포 단위는 `익스텐션 + 플러그인`과 `MCP`입니다.
- 익스텐션과 플러그인은 정확히 같은 기본 버전으로 함께 배포합니다.
  - 플러그인은 `.codex-plugin/plugin.json`의 버전을 관리합니다.
  - 익스텐션 저장소가 제공하는 목표 버전과 패키지 버전 증거를 대조합니다.
  - 플러그인의 `+codex.<cachebuster>` 빌드 메타데이터만 비교에서 제외합니다.
  - 기본 버전 변경은 양쪽 저장소의 같은 목표 버전으로 조율합니다.
  - 플러그인 작업에서는 플러그인 설치 안내·검사를 갱신합니다.
- 양쪽 산출물의 제공 여부와 버전을 확인해야 공동 배포가 완료됩니다.
  - 로컬 소스 일치나 한쪽 게시만으로 완료를 보고하지 않습니다.
- `익스텐션 + 플러그인`은 MCP 없이 동작합니다.
- MCP는 별도 버전·일정으로 독립 배포하며 익스텐션·플러그인을 요구하지 않습니다.
- 이 규칙은 게시·병합·푸시 권한을 추가로 부여하지 않습니다.

<a id="플러그인-릴리스-절차"></a>

## 3. 플러그인 릴리스 절차

- 저장소 Marketplace의 설치 소스는 `main`입니다.
- 다른 브랜치는 릴리스 후보이며 게시 완료 상태가 아닙니다.

1. 원격 `main` 대비 후보 변경과 공동 릴리스 범위를 확인합니다.
2. Plugin Creator의 `update_plugin_cachebuster.py`로 캐시버스터를 갱신합니다.
   - 확정된 기본 버전과 하나의 `+codex.<cachebuster>` 접미사를 유지합니다.
3. 승인된 검사를 수행합니다.
   - `Human-authorized verification` 워크플로나 Human이 지정한 검사를 사용합니다.
   - 전체 릴리스 검사는 Python 3.10·3.12와 배포·계약·런타임·통합 검사를 포함합니다.
4. Plugin Creator 검증기로 플러그인 로딩 형식을 확인합니다.
   - 저장소 테스트로 이 검사를 대체하지 않습니다.
5. 플러그인 버전·Marketplace 참조·스킬 목록·변경 범위를 재확인합니다.
   - 익스텐션 담당 저장소의 패키지 버전·배포 증거를 받아 대조합니다.
   - 승인된 커밋 전에 실제 검사 증거를 기록합니다.
6. 명시적 게시 권한이 있을 때만 `main`에 병합하거나 푸시합니다.
   - 원격 커밋과 새 Codex 스레드의 Marketplace 설치를 확인합니다.
   - 익스텐션 배포 증거도 확인한 후 공동 배포 완료를 보고합니다.
   - VSIX 빌드·검사·게시는 익스텐션 프로젝트 규칙을 따릅니다.

- 메타데이터 검사만으로 원격 배포·계정·설치 상태를 보증하지 않습니다.

<a id="테스트-구성과-실행"></a>

## 4. 테스트 구성과 실행

| 경로 | 책임 |
|---|---|
| `tests/contracts/` | 패키지·메타데이터·공개 계약 |
| `tests/runtime/` | 로컬 Agent 런타임 |
| `tests/integration/` | 설치·구성 요소 연동 |
| `tests/support/` | 공통 fixture·helper |
| `tests/benchmarks/` | 명시적으로 실행하는 성능 측정 |

- 수집 대상은 `test_<name>.py`로 명명합니다.
- helper는 테스트 수집 모듈과 분리합니다.
- 프로젝트 의존성은 루트 `requirements.txt`에서 확인합니다.
- 승인된 전체 검사에는 `pytest-xdist`를 사용합니다.
  - 명령은 `<project-python> -m pytest tests -n auto --maxprocesses=4 --dist=worksteal`입니다.
  - `<project-python>`은 확인된 프로젝트 환경의 인터프리터를 뜻합니다.
  - 직렬 실행은 `-n 0`을 사용합니다.
- 작은 범위의 검사는 직렬로 실행합니다.
- 실행 권한과 역할 경계는 적용 중인 Agent 실행 모드를 따릅니다.

<a id="사용자-배포-스킬의-책임과-병합-기준"></a>

## 5. 사용자 배포 스킬의 책임과 병합 기준

| 배포 스킬 | 소유 내용 | 다른 스킬에 맡기는 내용 |
|---|---|---|
| `agent` | 관리형 역할·실행 모드·세션·결과·영수증·런타임 명령 | 문서 작성·저장 규칙, 공통 개발 규칙 |
| `convention` | 소통·Human 결정·개발·테스트·시각 표현·조사·Interview | 실행 모드 정의, 문서 유형·패키지·동기화 |
| `document` | 문서 유형·작성·메타데이터·정본·저장·동기화·기존 문서 보존 | Agent 실행 절차, 소프트웨어 개발 절차 |

- 같은 규칙의 본문은 소유 스킬 한 곳에서 관리하고 다른 스킬은 필요한 작업에서만 참조합니다.
- `convention/SKILL.md`는 작업별 스킬 선택을 안내합니다. 별도 핵심 모델 문서에 각 스킬의 계약을 재작성하지 않습니다.
- Human 결정·권한 원칙은 `convention/SKILL.md#human-decisions`, 결정 누락 시 역할별 대응은 `agent/SKILL.md#delegation`이 소유합니다.
- 문서 저장 위치와 기존 문서 보존 원칙은 `document/SKILL.md`가 소유합니다.
- 실행 상태 저장 위치는 `agent/references/home-runtime.md`가 소유합니다. 문서 저장 규칙과 합치지 않습니다.
- 조사·근거 보존 원칙은 `convention/SKILL.md#research`, Interview 진행 규칙은 `convention/references/interview.md`가 소유합니다. 산출물 작성·저장은 `document`를 따릅니다.
- 표현·도표의 일반 의미는 `convention`, 문서 파일·첨부 형식은 `document`가 소유합니다.
- 참조를 병합하거나 이동할 때 진입점·템플릿·README·검사의 참조를 함께 갱신합니다.
- 공개 스킬 이름과 런타임 동작은 문서 정리만으로 변경하지 않습니다.
