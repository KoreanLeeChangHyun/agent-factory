---
name: rule-workbench-structure
description: Apply Agent Factory's target Python/TypeScript monorepo structure and
  dependency boundaries when scaffolding, reorganizing, or porting the MCP cloud Workbench
  platform. Use for target file placement and migration sequencing; do not use it
  to infer product behavior or to force a broad migration during an unrelated fix.
metadata:
  document-type: specification
  category: rule
  domain: null
  name: workbench-structure
  language: ko
  provenance:
    prior-provenance: null
    merged-from:
    - docs/skills/rule-workbench-structure/SKILL.md
    - docs/skills/rule-workbench-structure/references/directory-contract.md
    - docs/skills/rule-workbench-structure/references/target-structure.md
    - docs/specification/rule-workbench-structure/index.html
    - docs/specification/rule-workbench-structure/contract.html
    source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
    merge-request: run-20260918T152016183617Z-2d18ad49
    source-metadata:
      name: rule-workbench-structure
      description: Apply Agent Factory's target Python/TypeScript monorepo structure
        and dependency boundaries when scaffolding, reorganizing, or porting the MCP
        cloud Workbench platform. Use for target file placement and migration sequencing;
        do not use it to infer product behavior or to force a broad migration during
        an unrelated fix.
---


# Workbench Structure Rules

- Build toward the target architecture rather than reshaping the target around the legacy tree.

<a id="human-approved-structure"></a>

## 1. Human-approved structure

- Read [the accepted tree and ownership contract](#target-structure) before structural work. Managed root directories are fixed; further root additions, removals, or renames require an explicit Human decision. Preserve Human-owned, Git-ignored `feedback/` and `uploads/` under that contract.

- For the 2026-09-15 file-planning pass, consult the linked Processed file plan and baseline migration ledger in target-structure.md. Their mappings and implementation records are drafts, not approved moves; do not treat path-based classification as completed source analysis. Chat is human-to-human with read-only agent MCP access.

- For directory contracts and file-level implementation planning, read [the directory structure contract](#directory-contract). It requires an exact target tree, directory responsibilities, per-file implementation records, and an existing-to-target ledger before claiming the specification complete. Use the Human's [product overview](../design-platform/SKILL.md#product-overview) as the product basis.

<a id="authority"></a>

## 2. Authority

- Apply decisions in this order:

1. The Human's explicit instruction.
2. Current facts from `$info-platform`, accepted architecture from `$design-platform`, and mandatory behavior from `$rule-platform`.
3. The target structure in [target-structure](#target-structure).
4. Existing implementation patterns only when they do not conflict with the target.

- Use `$rule-ui` for Human-facing interface work and `$rule-layout` for the canonical **작업 목록 | 사이드바 | 패널** names. Use `$rule-project` for repository safety, verification, and preservation of unrelated work, but do not let its legacy placement table override an explicitly authorized target-architecture migration.

<a id="core-boundaries"></a>

## 3. Core boundaries

- Put executable and deployable entrypoints in `apps/`.
- Put reusable implementation packages in `packages/`.
- Treat `packages/contracts` as the data-contract domain: `schemas/` owns feature-grouped language-neutral sources; `py/` and `ts/` own generated code. Do not retain a second root contracts owner. Group SDK/build/runtime/editor packages under `packages/workbench` while preserving their separate dependencies.
- Keep all tests under root `tests/`, classified by tested app or package, with shared contract, integration, and support areas.
- Keep HTTP and MCP adapters thin. They call the same Python application use cases.
- Keep API, MCP, web, and jobs applications separate while sharing package business logic.
- Make `design-system` the only owner of shared visual foundations, assets, primitives, patterns, shell surfaces, interaction semantics, and common product language.
- Make `workbench/runtime` own platform-side loading, trusted/isolated rendering and bridge validation.
- Make `workbench/sdk` own the public customer API, and `workbench/build` own the fixed toolchain inside build isolation. These package additions were Human-approved on 2026-09-15.
- Keep worker job dispatch separate from adapter-managed build isolation; do not run customer builds in the ordinary worker process. The build package is an internal tool, not a new application service.
- Preserve sandbox boundaries for untrusted external UI without inventing another package outside the accepted tree.
- Keep PostgreSQL, queue, object storage, MCP client, HTTP connector, vector, embedding, and secret implementations in `packages/adapters`.
- Do not place framework, database, queue, or provider SDK imports in `packages/core`.
- Keep metering and configurable resource limits in `core/usage`, independent of billing. Adapters own atomic counters and expiring capacity leases; deployment owns whole-server safety ceilings. See the target structure's usage ownership section; do not introduce pricing or automatic overage charging.

<a id="scaffolding-and-porting"></a>

## 4. Scaffolding and porting

- Read [target-structure](#target-structure) completely before creating, moving, or substantially reorganizing target files.

- Create only directories required by the current vertical slice; do not generate an empty final tree.
- Establish contract schemas and dependency checks before moving feature code.
- Port one end-to-end behavior at a time through a compatibility boundary.
- Keep a rollback path until the replacement passes contract, authorization, tenant-isolation, and browser checks.
- Do not combine a large file move, renderer replacement, and product-behavior change in one step.
- Promote shared UI only when its meaning is stable across real consumers. Keep feature-only visualization logic with the feature.
- Generated Python and TypeScript contract packages are build outputs. Change the source JSON Schema instead of editing generated files.
- Preserve published Workbench versions as immutable revisions; migrations append rather than rewrite history.

<a id="naming"></a>

## 5. Naming

- Background application: `apps/jobs/`; its tests: `tests/jobs/`. Worker remains a process role, not the target application directory name.

- UI term: `작업` for an item in the `작업 목록` region.
- Domain aggregate: `WorkbenchDefinition`.
- Immutable published snapshot: `WorkbenchRelease`.
- Long-running durable execution: `Job`.
- Do not use generic `task` for both a Workbench definition and a queue job.

<a id="verification"></a>

## 6. Verification

- Verify the smallest affected boundary first, then widen:

1. Schema examples and Python/TypeScript validator parity.
2. Owning package unit tests and dependency-direction checks.
3. HTTP/MCP/jobs integration tests for the affected use case.
4. Browser tests for 작업 목록, 사이드바, 패널, state restoration, permissions, and responsive behavior.
5. Build, migration, security, and deployment gates proportional to the change.

- Do not claim the target structure is ported merely because directories exist. Completion requires a working vertical slice using the new contracts and dependency direction.

<a id="current-human-instruction-test-ownership"></a>

## 7. Current Human instruction: test ownership

- All test code and test-only helpers live under root `tests/`. Use the app/package-first classification in [the accepted structure](#target-structure), replacing the former domain-first layout. Do not place tests beside production source. Docker and Makefile execution have been retired; use direct package/runtime commands.

<a id="directory-contract"></a>

## 8. directory-contract

- 계약 ID: `directory-structure-001` · 버전: 5 · 갱신일: 2026-09-15 · 소유 명세: rule-workbench-structure

<a id="purpose"></a>

<a id="목적과-현재-상태"></a>

## 9. 목적과 현재 상태

- 장기 구현 작업에 앞서 디렉터리 구조 계약을 작성한다. 이미 합의한 구조와 파일 단위 구현 명세를 완성하는 절차를 기록한다. 전체 구조는 합의된 상태이며, 전체 목표 파일 목록과 파일별 구현 명세는 아직 작성·검수 완료 전이다. 이 계약의 작성만으로 코드 이동이나 무인 구현을 시작하지 않는다.

<a id="구조-기준과-문서-소유권"></a>

## 10. 구조 기준과 문서 소유권

- 전체 트리와 디렉터리 책임은 이 문서의 목표 트리와 책임 절이 단일 기준입니다. 이 계약은 파일별 계획·완료 조건·변경 절차를 추가하며 별도 경쟁 구조를 만들지 않는다. 사용자의 명시적 지시는 과거 문서나 기존 구현보다 우선한다. 정본은 이 SKILL.md에서 유지합니다.

<a id="scope"></a>

<a id="명세-작성-범위"></a>

## 11. 명세 작성 범위

- apps/api·web·mcp·jobs, 계약 도메인(schemas/py/ts)과 workbench 도구 묶음을 포함한 모든 packages, tests·scripts·deploy/local·migrations·docs 및 영향을 받는 루트 설정·잠금 파일·빌드 설정·CI·유지 중인 스킬을 포함한다. 기준 커밋과 작업 트리 상태를 기록하고 기존 추적 파일과 관련된 비무시 미추적 소스를 조사한다. 현재 사실·제안 목적지·확정 결정·누락 구현·후속 작업을 구분한다. 사용자 보호 데이터는 조사 대상에 포함하지 않는다.

<a id="boundaries"></a>

<a id="필수-배치-경계"></a>

## 12. 필수 배치 경계

- API는 HTTP와 API 전용 흐름, MCP는 MCP 프로토콜과 전용 흐름, web은 페이지 렌더링과 브라우저 호출, jobs는 비동기·주기·배치 진입점을 소유한다. 공통 업무 판단은 core, 인프라 구현은 adapters에 둔다. 앱끼리 직접 import하지 않으며 core는 adapters나 실행 프레임워크에 의존하지 않는다. 웹 앱 내부 컴포넌트와 design-system 공통 컴포넌트의 소유자를 구분한다. workbench/runtime은 호스트 로딩·렌더링·메시지 검사, workbench/sdk는 사용자용 공개 API, workbench/build는 격리 환경 안의 고정 빌드 도구, workbench/editor는 코드 작성·미리보기를 소유한다. jobs의 요청 전달과 adapters의 격리 관리는 빌드 실행과 분리하며 빌드 도구를 별도 배포 앱으로 취급하지 않는다. 컴포넌트는 골격 + 데이터 + 테마 원칙을 따르되, 모든 컴포넌트마다 기계적으로 파일 세 개를 만들지는 않는다.

<a id="depth"></a>

<a id="경로깊이이름"></a>

## 13. 경로·깊이·이름

- 실제 저장소 상대 파일 경로를 명시하고 <domain>/service.py 같은 자리표시자 트리로 완료 처리하지 않는다. 목표 구조에서 불필요한 src/패키지명 중첩을 제거한다. 모든 도메인에 동일한 폴더를 강제하거나 빈 골격을 만들지 않는다. 실제 공존하는 외부 계약은 필요할 때 버저닝한다. 물리 경로 변경으로 공개 URL·MCP 도구 ID·계약 필드·저장 ID·마이그레이션을 임의 변경하지 않는다. Python import 이름·배포 패키지 매핑·TypeScript exports·진입점·패키지 리소스 경로를 물리 경로와 별도로 기록한다. Python MCP 앱은 외부 mcp SDK 이름을 가리지 않아야 한다.

<a id="inventory"></a>

<a id="파일-목록과-이전-대응표"></a>

## 14. 파일 목록과 이전 대응표

- 범위 내 기존 파일마다 유지·이동·분리·통합·생성물·별도 검토 후 폐기 중 처리 방식을 기록한다. 모든 원본 파일에 정확한 목적지를 대응시키거나 미확정 사유를 남긴다. 분리는 목적 파일별 책임과 추출할 주요 심볼을, 통합은 수신 파일과 중복 조정 내용을 명시한다. import 대상이 없으면 기존 파일이 아니라 구현 누락으로 기록한다. 목표 트리에 없다는 이유로 삭제하지 않는다. 생성물은 원본과 생성기를 명시하며 직접 수정하지 않는다.

<a id="deliverables"></a>

<a id="필수-산출물과-자료-조사-목적"></a>

## 15. 필수 산출물과 자료 조사 목적

- 자료 조사는 사용자의 [제품 전체 그림](../design-platform/SKILL.md#product-overview)을 기준으로 목표 구조와 코드 배치 명세를 완성하기 위해 수행한다. 출처·대안·선택 근거·미확정 결정을 기록하며 조사 결과를 자동 확정하지 않는다. 소유 명세 안에서 네 산출물을 서로 연결하여 작성한다: 정확한 파일명까지 포함한 전체 목표 트리, 디렉터리 책임표, 파일별 구현 명세, 기존 파일과 목표 파일의 대응표. 이는 필수 결과물이며 이미 작성되었다는 뜻은 아니다. 폴더만 나열한 그림이나 ‘services에는 서비스 코드를 둔다’는 일반적인 설명으로 완료 처리하지 않는다.

<a id="directory"></a>

<a id="디렉터리별-필수-책임-명세"></a>

## 16. 디렉터리별 필수 책임 명세

- 범위 내 모든 목표 디렉터리에 정확한 경로·소유자·목적·담을 구체적인 코드 종류·넣으면 안 되는 코드·하위 디렉터리와 파일 및 명세 ID·허용 및 금지 의존성·해당 깊이가 필요한 이유를 기록한다. 계층 이름만 적지 않고 어떤 서비스가 어떤 책임을 수행하는지 명시한다. 설정·자산·생성물·문서 디렉터리는 호출 인터페이스를 지어내지 않고 내용과 생명주기를 설명한다. 전체 트리·디렉터리 책임표·파일 명세·이전 대응표가 일치해야 하며 연결되지 않은 경로나 설명 없는 파일을 남기지 않는다.

<a id="record"></a>

<a id="파일별-필수-구현-명세"></a>

## 17. 파일별 필수 구현 명세

- 각 목표 파일마다 다음을 기록한다: 고유 명세 ID와 정확한 경로, 소유 앱·패키지와 도메인, 기존 원본 경로와 처리 방식, 한 문장 책임과 제외 책임, 구현할 함수·클래스·컴포넌트·exports 및 역할, 입력·출력·스키마·오류 처리, 허용 의존성·호출자·금지 의존성, 필요한 권한·테넌트 격리·상태·트랜잭션·멱등성·부수 효과, 리소스·설정·생성 원본 소유권, 연결할 테스트 파일과 검수 시나리오, 선행 명세 ID와 구현 순서, 완료 조건·결정 상태·미해결 질문. 해당하지 않는 항목은 이유를 명시하며 동작을 지어내지 않는다. 소유권을 다시 설계하지 않고 구현할 수 있을 만큼 구체화하되 함수 본문 전체를 미리 쓰지는 않는다.

<a id="stages"></a>

<a id="작업-순서와-검수-단계"></a>

## 18. 작업 순서와 검수 단계

- ① 기준 파일 조사·불일치 보고 → ② 전체 디렉터리와 목표 파일 목록 → ③ 파일별 구현 명세·의존성·이전 대응표·테스트 연결 → ④ 실행할 단계 범위에 대한 사용자 검수·확정 → ⑤ 단계 실행 계약·솔로 구현 순서로 진행한다. 후속 기능은 명시적으로 다음 단계에 둘 수 있지만, 곧 실행할 단계에 속한 파일이나 동작이 미확정이면 그 단계는 준비 완료가 아니다. 일부 파일 목록만 작성하고 전체 파일 명세가 끝났다고 보고하지 않는다.

<a id="completion"></a>

<a id="구조파일-명세-완료-조건"></a>

## 19. 구조·파일 명세 완료 조건

- 해당 단계의 기존 파일에 누락이 없고, 모든 목표 파일의 명세가 갖춰지고, 분리·통합 책임 및 import·export·빌드·리소스 매핑이 명확해야 한다. API·MCP·jobs 및 web·SDK·build·runtime·editor·격리 경계, 계약 원본과 생성물 연결, 테스트 경로와 시나리오, 배포·설정 소유권을 정해야 한다. 승인되지 않은 삭제나 구조 변경을 숨기지 않아야 하며 사용자 검수를 마쳐야 한다. 문서 확정·코드 이전·동작 검증·배포 완료는 각각 별도 상태로 관리한다.

- 전체 구조 명세 완료는 네 가지 산출물과 범위 내 모든 디렉터리·파일 명세의 작성 및 검수가 끝난 상태다. 보류·미확정 항목을 숨기지 않으며 남아 있는 동안 전체 파일 명세가 최종 확정되었다고 보고하지 않는다. 특정 단계의 준비 완료가 저장소 전체의 완료를 뜻하지 않는다. 코드 개편은 해당 명세와 실행 범위에 대한 사용자 검수·확정 이후 시작한다.

<a id="changes"></a>

<a id="구현-중-변경-관리"></a>

## 20. 구현 중 변경 관리

- 단계 확정 후 합의 경로·파일 책임·공개 계약·범위·삭제 결정을 바꾸려면 사유와 영향받는 명세·호출자·테스트를 기록하고 해당 변경 전에 사용자 결정을 받는다. 확정 명세 안의 함수 내부 구현은 자율 판단하며 이미 계약된 일반 구현을 매번 재승인받지 않는다. 변경 부분이 보류되어도 독립적인 승인 범위는 계속 진행한다. 루트 추가·삭제·이름 변경은 기존 고정 루트 규칙을 따른다. 문서 확정은 파괴적 작업·DB 이력 재작성·운영 환경 변경의 허가가 아니다.

<a id="tests"></a>

<a id="테스트-보류와-제외-사항"></a>

## 21. 테스트 보류와 제외 사항

- 현재 작업은 문서 작성과 읽기 전용 조사에 한정한다. 운영 코드 이동·구현·테스트 실행·배포·데이터 이전·서비스 변경은 하지 않는다. 제품 테스트 실행은 사용자 지시에 따라 전체 코드 개편 후 로드맵 8단계로 보류한다. 테스트 코드와 검수 시나리오는 지금 설계하되 통과했다고 보고하지 않는다. 문서 확인은 동작 검증이 아니다. 배포는 현재 로컬 대상이며 실제 서비스 관리자·프록시·설정 파일명은 별도 배포 결정 사항이다. systemd·Docker·AWS를 임의 선택하지 않는다. feedback/·uploads/·무시된 비밀 설정·기존 env/·마이그레이션 이력·무관한 변경을 보존한다.

<a id="handoff"></a>

<a id="장기-실행-인계-조건"></a>

## 22. 장기 실행 인계 조건

- 후속 실행 계약에 확정 파일 명세 리비전·정확한 범위와 순서·완료 조건·자율 판단 및 중단 기준·선택한 사용량/시간 예산·중간 저장 기준·인수인계 결과물을 명시한다. 서브에이전트 없이 솔로로 진행한다. 모델과 수치 예산은 이 디렉터리 계약에서 확정하지 않는다. 무인 실행 후보는 사용자가 만든 Agent Factory 확장이지만 윈도우·VS Code 종료 후 독립 실행 여부는 아직 미검증이다. 이에 의존하기 전에 실행 환경을 별도 확인한다. 이 문서는 백그라운드 실행을 시작하거나 무중단 실행을 보장하지 않는다.

<a id="target-structure"></a>

## 23. target-structure

- 사용자와 합의한 목표 구조와 책임 기준이다.

- *실제 코드 이전이 완료되었다는 뜻은 아니다.*

- AI용 문서는 [구조 스킬]()에 있다.

- 파일 단위 계획과 자료 조사는 [제품 전체 그림](../design-platform/SKILL.md#product-overview)을 기준으로 [디렉터리 구조 계약](#directory-contract)에 따라 진행한다.

- 명세 완료에는 정확한 전체 목표 트리·디렉터리 책임표·파일별 구현 명세·기존 파일 대응표가 필요하다.

- 아래 트리는 이 상세 명세를 대신하지 않는다.

<a id="section-1"></a>

<a id="고정된-루트-경계"></a>

## 24. 고정된 루트 경계

<a id="section-1-1"></a>

<a id="관리-대상과-변경-승인"></a>

### 24.1. 관리 대상과 변경 승인

- 관리 대상 루트 디렉터리는 `apps/`, `packages/`, `tests/`, `scripts/`, `deploy/`, `migrations/`, `docs/`다.

- 추가적인 루트 생성·삭제·이름 변경은 계획되어 있지 않으며 암묵적으로 허용하지 않는다.

- 기능·프레임워크 관례·패키징 편의 때문에 새 루트를 만들지 않는다.

- 향후 요구사항을 이 구조에 담을 수 없다면 사유와 영향 경로를 설명하고 사용자 결정 후 변경한다.

- 이미 명시적으로 승인한 변경은 같은 승인을 반복해서 묻지 않는다.

<a id="section-1-2"></a>

<a id="도구로컬-설정-보존"></a>

### 24.2. 도구·로컬 설정 보존

- `.git/`, `.github/`, `.codex/`, `.vscode/`, `.venv/`, `node_modules/` 및 캐시는 기존 메타데이터·도구 디렉터리로 보존한다.

- 애플리케이션 구조와 구분하며, `env/`를 포함한 기존 로컬 설정과 무시된 데이터도 명시적인 이전 범위가 정해질 때까지 보존한다.

- 그림에 없다는 이유로 삭제하지 않는다.

- `env/local/dev/`·`stg/`·`prod/`: 실제 환경변수·비밀 설정. Git 관리 대상이 아니다.

- `deploy/`는 배포 절차·비밀 없는 예시를, `env/`는 실제 값을 소유한다.

- `env/aws/`는 AWS 전환 시 추가한다. 현재 구조 표기는 기존 설정의 이동을 뜻하지 않는다.

- `.codex/`: Codex 프로젝트 설정과 스킬·영문 AI 명세.

- `.github/`: CI/CD와 이슈·PR 템플릿.

- `.vscode/`: 에디터·디버깅·개발 명령·권장 확장 설정.

- 도구 설정 중 공유 가능한 항목만 Git으로 관리한다. 개인 설정·토큰·비밀 값은 제외한다.

- 템플릿·에디터 파일은 목표 배치다. 필요한 파일만 만들며 기존 파일을 덮어쓰지 않는다.

<a id="section-2"></a>

<a id="통합-반영-내용과-확정-상태"></a>

## 25. 통합 반영 내용과 확정 상태

<a id="section-2-1"></a>

<a id="반영-범위와-문서-상태"></a>

### 25.1. 반영 범위와 문서 상태

- 2026-09-15 사용자 승인에 따라 코드 기반 커스텀 작업 구조와 workbench/sdk·workbench/build 패키지를 반영했다.

- 사용자 승인으로 루트 contracts를 packages/contracts에 통합하고 workbench 하위 패키지를 묶는다. 앱 경계는 유지한다.

- **[후보]**는 조사에서 제안한 기능·방식으로 미확정이다.

- 나머지 추가 경로도 확정 요구의 담당 위치를 제안한 것이며 정확한 파일명은 파일별 명세 검수가 필요하다.

- 트리만 보고 빈 디렉터리를 만들지 않는다.

<a id="section-2-2"></a>

<a id="확정된-제품-기능"></a>

### 25.2. 확정된 제품 기능

- **확정**: 클라우드 에이전트 관제 시스템.

- **확정**: 스탠다드 작업과 사용자 코드 기반 커스텀 작업.

- **확정**: 공통 에셋·공개 SDK 제공.

- **확정**: 사이드바와 패널 탭은 선택 사항.

- **확정**: 커스텀 작업 컴파일·렌더링 지원.

- **확정**: 워크스페이스 MCP와 외부 DB 연결.

<a id="section-2-3"></a>

<a id="플랜조직사용량"></a>

### 25.3. 플랜·조직·사용량

- **확정**: 개인은 1인·워크스페이스 1개 무료·추가 개수별 구독이며 조직 작업·초대가 없다.

- **팀은 조직을 뜻한다.**

- 조직 소유자가 초대·접근 범위·관리자 권한·권한 집합을 관리한다.

- 엔터프라이즈는 보안 차등이며 구체 기능과 가격은 미정이다.

- **확정**: 과금과 독립된 사용량 계측·자원 한도 조절. 시스템 기본값과 조직·워크스페이스별 한도를 관리하며 가격 계산·자동 초과 과금을 도입하지 않는다.

<a id="section-2-4"></a>

<a id="미확정-사항"></a>

### 25.4. 미확정 사항

- **미확정**: 등록형 데이터 작업.

- **미확정**: PostgreSQL 우선·읽기 우선 도입과 사설망 연결 방식.

- **미확정**: 구독 소유 모델과 권한 합산 규칙.

- **미확정**: SSO·SCIM·감사 내보내기 등 보안 기능.

- **조사 결과를 자동 채택하지 않는다.**

<a id="section-2-5"></a>

<a id="관련-자료와-우선순위"></a>

### 25.5. 관련 자료와 우선순위

- [제품 개요](../design-platform/SKILL.md#product-overview) · [외부 DB 조사](../../../docs/processed/research-external-db-custom-work/SKILL.md) · [SaaS 플랜·권한 조사](../../../docs/processed/research-saas-plans-organization-permissions/SKILL.md) · [사용자 코드·실행 구조 조사](../../../docs/processed/research-custom-work-code-runtime/SKILL.md)

- 이전 조사 문서의 배치안은 당시 제안이다.

- **현재 승인된 구조가 우선한다.**

<a id="section-3"></a>

<a id="도메인-연결과-미확정-경계"></a>

## 26. 도메인 연결과 미확정 경계

<a id="section-3-1"></a>

<a id="화면과-도메인-연결"></a>

### 26.1. 화면과 도메인 연결

- 스탠다드 작업과 업무 도메인은 일대일이 아니다.

- 조직 화면: organizations·identity.

- 계정 화면: identity·후보 billing.

- DB 화면: connections·후보 data_access.

- 로그 화면: audit·reporting.

- 제품의 테스트 작업은 실행 도메인 상세가 미정이다.

- 루트 tests/는 개발 검증 코드이며 제품 데이터 저장소가 아니다.

<a id="section-3-2"></a>

<a id="기존-업무-도메인-배치"></a>

### 26.2. 기존 업무 도메인 배치

- agents·planning·scheduling·reporting을 core 바로 아래로 옮겨 executions 중첩을 줄이는 안을 반영했다.

- 문서 업무는 knowledge가 소유한다.

- 실제 이동 전에 기존 클래스·import·이력을 대응시켜야 하며 트리에 없는 기존 기능을 폐기하는 뜻은 아니다.

<a id="section-3-3"></a>

<a id="연결데이터-경계"></a>

### 26.3. 연결·데이터 경계

- 연동과 DB 화면이 같은 연결을 보여줘도 연결 수명 관리는 한 도메인이 소유한다.

- 외부 DB 접근과 플랫폼 운영 DB 권한을 분리하며 고객 테이블 자동 생성을 가정하지 않는다.

<a id="section-3-4"></a>

<a id="조직과-권한"></a>

### 26.4. 조직과 권한

- 권한 목록·조직별 권한 집합·사용자 범위 할당은 organizations, 공통 인가 적용은 identity가 담당하는 안이다.

- 멤버십·소유권·구독 제공 기능·유효 권한을 구분한다.

- 조직 하위 팀 도메인은 추가하지 않는다.

<a id="section-3-5"></a>

<a id="커스텀-작업의-소유사용-설정"></a>

### 26.5. 커스텀 작업의 소유·사용 설정

- 작업 정의·릴리스·사용 설정은 workbenches, 공통 렌더러는 workbench/runtime이 소유한다.

- 개인·조직별 커스텀 정의는 데이터와 결과물로 관리하며 고객 이름별 소스 디렉터리를 만들지 않는다.

- 정의 소유·워크스페이스 사용 설정·개인 표시 설정은 분리할 설계 축이며 공유·상속 규칙은 미확정이다.

<a id="section-3-6"></a>

<a id="사용자-코드-작성-방식"></a>

### 26.6. 사용자 코드 작성 방식

- 커스텀 작업은 사용자 코드·공통 UI 에셋·공개 SDK를 사용한다.

- TypeScript·React를 계획 기준으로 두며 정확한 버전·번들러·의존성 허용 목록·격리 기술은 후속 명세 대상이다.

- JSON은 등록·프로토콜 계약이며 화면 작성의 유일한 형식이 아니다.

<a id="section-3-7"></a>

<a id="sdk런타임빌드-역할"></a>

### 26.7. SDK·런타임·빌드 역할

- workbench/sdk는 사용자용 API, workbench/runtime은 호스트의 로딩·렌더링·메시지 검사, workbench/build는 격리 환경 안의 고정 빌드 도구를 소유한다.

- jobs는 요청을 전달하고 adapters가 격리 환경 생성·호출·취소·회수를 담당한다.

- **일반 worker 프로세스 안에서 사용자 빌드를 직접 실행하지 않는다.**

- 임의 사용자 서버 함수 지원은 포함하지 않는다.

- 두 패키지 추가는 사용자 승인 사항이다.

<a id="section-3-8"></a>

<a id="산출물게시활성화"></a>

### 26.8. 산출물·게시·활성화

- 소스 스냅샷과 불변 산출물은 런타임 저장 데이터이며 고객별 저장소 폴더가 아니다.

- 메타데이터·소유·게시·워크스페이스 활성화는 core/workbenches가 소유한다.

- 빌드 완료·게시·활성화를 구분하고 사용할 릴리스를 고정한다.

<a id="section-3-9"></a>

<a id="공통-ui-구성"></a>

### 26.9. 공통 UI 구성

- **컴포넌트는 골격 + 데이터 + 테마로 구성**하고 사이드바와 패널 탭은 독립적으로 선택한다.

- 공통 UI는 design-system이 소유하며 웹 클라이언트와 런타임 바인딩에 DB 비밀을 전달하지 않는다.

- `packages/design-system/assets/`는 공통 아이콘·로고·폰트·이미지 원본을 소유한다.

- 웹과 커스텀 작업은 design-system의 공개 에셋 경로를 사용한다. 복사본을 따로 관리하지 않는다.

<a id="section-3-10"></a>

<a id="후속-설계와-미완료-범위"></a>

### 26.10. 후속 설계와 미완료 범위

- 엔터프라이즈는 현재 플랜·보안 구분이지 조직 상위 엔터티가 아니다.

- SSO·SCIM·세션 통제·결제 어댑터·서비스 신원은 별도 결정과 파일 명세가 필요하다.

- 대표 파일만 표기한 도메인 라우트·서비스는 후속 명세에서 개별 경로를 완성해야 한다.

- 설정·자산·테스트·기존 파일 대응표까지 모두 완료한 상태는 아니다.

<a id="section-4"></a>

<a id="채팅편집-범위와-파일-계획"></a>

## 27. 채팅·편집 범위와 파일 계획

<a id="section-4-1"></a>

<a id="사람-채팅과-mcp-조회"></a>

### 27.1. 사람 채팅과 MCP 조회

- 채팅은 사람끼리 하며 **에이전트는 권한 있는 대화를 MCP로 읽기만 한다**.

- 에이전트 발송 도구·상시 구독·자동 기동은 추가하지 않는다.

- 사람의 실시간 전달과 MCP 조회는 별도 경로다.

<a id="section-4-2"></a>

<a id="채팅-ui와-미정-기능"></a>

### 27.2. 채팅 UI와 미정 기능

- 채팅 UI는 우선 앱 전용 보조 UI로 배치하며 내비게이션 위치는 미정이다.

- 11번째 스탠다드 작업을 확정하지 않는다.

- 대화방 범위·참여·수정/삭제·보존·읽음·첨부는 후속 결정이다.

- 저장과 전달 사이 누락을 막기 위한 영속 이벤트 전달은 제안이며 전송 기술은 미선정이다.

<a id="section-4-3"></a>

<a id="동시-편집-범위"></a>

### 27.3. 동시 편집 범위

- 초기 편집은 저장 버전 검사·충돌 안내를 제안한다.

- 실시간 커서 공유·CRDT/OT 공동 편집은 승인되지 않았다.

- 충돌 처리는 편집 대상 도메인에 두며 여러 사용자가 저장한다는 이유로 별도 공동 편집 서비스를 만들지 않는다.

<a id="section-4-4"></a>

<a id="파일-계획과-대응표"></a>

### 27.4. 파일 계획과 대응표

- [파일별 구현 계획 초안](../../../docs/processed/analyze-structure-file-plan/SKILL.md) · [기준 파일·이전 대응표](../../../docs/processed/process-structure-migration-ledger/SKILL.md).

- 두 문서는 관찰·목적지 후보·미정 설계를 구분한 가공 자료다.

- [도메인·서비스·데이터·배포 경계 설계 초안](../../../docs/processed/analyze-service-boundary-design/SKILL.md): 독립 서비스안을 비교하는 검수 자료. 현재 트리를 대체하지 않는다.

- **경로 재조정 필요**: 두 초안은 contracts·workbench 통합 및 worker → jobs 이름 변경 전 자료다.

- 기존 소스 경로 기록은 보존하고, 구현 전에 목적지를 현재 구조에 맞춘다.

- *구현 승인이나 전체 파일 명세 완료를 뜻하지 않는다.*

- 트리에서 생략된 기존 파일도 대응표에서 보존한다.

<a id="section-5"></a>

<a id="확장된-전체-목표-트리"></a>

## 28. 확장된 전체 목표 트리

<a id="directory-tree"></a>

- [목표 트리 데이터](assets/target-tree.json)를 아래에 읽기용으로 표시합니다.

```text
mcp/ # 목표 구조·상세 경로는 검수 전 설계안
├── apps/ # 실행·배포 단위 애플리케이션
│   ├── api/ # HTTP 진입점·API 서비스 흐름
│   │   ├── main.py # HTTP 앱 구성·수명 관리
│   │   ├── settings.py # API 전용 설정 검증
│   │   ├── composition/ # API 의존성 조립·공유 업무 판단 제외
│   │   │   ├── chat.py # 채팅 저장·권한·이벤트 서비스 조립
│   │   │   └── usage.py # 사용량 저장소·사용권 검사 조립
│   │   ├── routes/ # 기능별 요청·응답 계약
│   │   │   ├── organizations.py # 조직·초대·멤버·권한 집합 API
│   │   │   ├── workspaces.py # 개인·조직 작업공간 API
│   │   │   ├── workbenches.py # 소스·빌드 요청·게시·활성화 API
│   │   │   ├── identity.py # 로그인·계정·세션 API
│   │   │   ├── connections.py # 연결 등록·상태·자격증명 변경 API
│   │   │   ├── data_access.py # [후보] 외부 데이터 작업 API
│   │   │   ├── usage.py # 권한 있는 사용량 조회·한도 설정 API
│   │   │   ├── chat.py # 사람 채팅 명령·권한 있는 이력 조회
│   │   │   ├── chat_events.py # 사람 클라이언트 이벤트 연결·복구·종료
│   │   │   ├── billing.py # [후보] 향후 구독 API·실시간 한도 집행과 분리
│   │   │   └── admin.py # SaaS 관리자 전용 API
│   │   └── services/ # API 흐름 조립·공통 유스케이스 호출
│   ├── web/ # 관제 화면·웹 렌더링
│   │   ├── main.tsx # 웹 진입점
│   │   ├── App.tsx # 작업 목록·선택적 사이드바·패널 조립
│   │   ├── pages/ # 스탠다드 작업별 화면
│   │   │   ├── organizations/ # 조직·멤버·권한 집합 관리
│   │   │   │   └── OrganizationWorkbench.tsx # 조직 화면 진입·세부 동작 후속 명세
│   │   │   ├── workspaces/ # 작업공간 선택·관리
│   │   │   │   └── WorkspaceWorkbench.tsx # 작업공간 화면 진입·세부 동작 후속 명세
│   │   │   ├── schedule/ # 일정 화면
│   │   │   │   └── ScheduleWorkbench.tsx # 일정 화면 진입·세부 동작 후속 명세
│   │   │   ├── agents/ # 에이전트 관제 화면
│   │   │   │   └── AgentsWorkbench.tsx # 에이전트 화면 진입·세부 동작 후속 명세
│   │   │   ├── documents/ # 문서 탐색·열람·편집
│   │   │   │   └── DocumentsWorkbench.tsx # 문서 화면 진입·세부 동작 후속 명세
│   │   │   ├── connections/ # 연동 등록·연결 상태
│   │   │   │   └── ConnectionsWorkbench.tsx # 연동 화면 진입·세부 동작 후속 명세
│   │   │   ├── logs/ # 허용된 작업·운영 이력 조회
│   │   │   │   └── LogsWorkbench.tsx # 로그 화면 진입·세부 동작 후속 명세
│   │   │   ├── tests/ # 제품의 테스트 작업 화면
│   │   │   │   └── TestsWorkbench.tsx # 테스트 화면 진입·세부 동작 후속 명세
│   │   │   ├── db/ # 외부 DB 연결·데이터 관리 화면
│   │   │   │   └── DatabaseWorkbench.tsx # DB 화면 진입·세부 동작 후속 명세
│   │   │   ├── account/ # 본인 계정·개인 구독 관리
│   │   │   │   └── AccountWorkbench.tsx # 계정 화면 진입·세부 동작 후속 명세
│   │   │   └── admin/ # SaaS 관리자 전용 관제·사용량 조회·한도 조정
│   │   │       └── AdminWorkbench.tsx # SaaS 관리 화면 진입·세부 동작 후속 명세
│   │   ├── components/ # 웹 앱에만 필요한 재사용 UI
│   │   │   ├── WorkbenchHost.tsx # 작업 목록·선택적 사이드바·패널 배치
│   │   │   └── chat/ # 앱 전용 채팅 UI·내비게이션 위치 미정
│   │   │       ├── ChatPanel.tsx # 사람 대화 이력·발송 UI
│   │   │       └── chat-state.ts # 중복 제거·조회 커서·발송 대기 상태
│   │   └── api/ # 도메인별 HTTP 클라이언트·비밀 값 금지
│   │       ├── chat.ts # 이력·발송·재접속 클라이언트
│   │       └── usage.ts # 사용량 조회·권한 있는 설정 클라이언트
│   ├── mcp/ # 독립 워크스페이스 MCP·공통 요청 한도 적용
│   │   ├── main.py # MCP 서버 구성·수명 관리
│   │   ├── settings.py # 독립 MCP 설정
│   │   ├── composition.py # API import 없는 MCP 의존성 조립
│   │   ├── auth.py # 토큰 신원·범위와 공통 인가 연결
│   │   ├── tools/ # 허용된 기능별 MCP 도구
│   │   │   ├── workbenches.py # 작업 정의 관련 도구·범위 별도 명세
│   │   │   ├── chat.py # 권한 있는 채팅 이력·변경 읽기 전용 조회
│   │   │   └── data_access.py # [후보] 등록 데이터 작업 호출
│   │   ├── resources/ # 허용된 워크스페이스 리소스 제공
│   │   └── services/ # MCP 흐름 조립·공통 유스케이스 호출
│   └── jobs/ # 비동기·배치·스케줄러·공통 실행 동시성 한도 적용
│       ├── main.py # 작업 실행 프로세스 진입점
│       ├── settings.py # worker 설정·큐 한도
│       ├── composition.py # worker 핸들러·어댑터 조립
│       ├── celery_app.py # 명시적 Celery 앱·허용 핸들러 등록
│       ├── scheduler.py # 주기 실행 등록·호출
│       └── jobs/ # 작업 유형별 실행·현재 권한 재확인
│           ├── data_access.py # [후보] 장기 데이터 작업·내보내기
│           ├── chat_events.py # 후보: 저장된 채팅 이벤트 전달·에이전트 기동 아님
│           ├── usage_reconcile.py # 사용권 만료·정합성 회수 요청
│           └── workbench_build.py # 격리 빌드 요청 전달·상태·결과 처리
├── packages/ # 공통 구현·도메인별 책임 분리
│   ├── core/ # 공통 업무 규칙·유스케이스·외부 구현 인터페이스
│   │   ├── identity/ # 계정·인증 주체·공통 인가
│   │   ├── organizations/ # 조직·초대·소속·권한 집합·할당
│   │   │   ├── permissions.py # 행위 권한 목록·허용 범위 정의
│   │   │   ├── permission_sets.py # 권한 집합 구성·변경·검증
│   │   │   └── grants.py # 사용자·권한 집합·대상 범위 할당
│   │   ├── workspaces/ # 개인·조직 소유 작업공간의 규칙
│   │   ├── workbenches/ # 소스·빌드·게시·활성화 업무 규칙
│   │   │   ├── definitions.py # 소스 스냅샷·초안·소유 규칙
│   │   │   ├── builds.py # 빌드 요청·상태 전이
│   │   │   ├── releases.py # 불변 게시 버전·호환성
│   │   │   ├── activations.py # 워크스페이스별 릴리스 선택·롤백
│   │   │   ├── policies.py # 작성·게시·활성화·실행 권한
│   │   │   ├── ports.py # 저장소·산출물·격리 빌드 인터페이스
│   │   │   └── use_cases.py # 공유 업무 흐름
│   │   ├── agents/ # 에이전트 관련 업무 규칙
│   │   ├── planning/ # 계획·일정 편집 규칙
│   │   ├── scheduling/ # 주기·실행 상태·중복·재시도 규칙
│   │   ├── reporting/ # 실행 보고·결과 수집 규칙
│   │   ├── knowledge/ # 문서·검색·패키지·이력 규칙
│   │   ├── connections/ # 연결 소유·상태·자격증명 수명 규칙
│   │   ├── chat/ # 사람 채팅·에이전트 읽기 접근 도메인
│   │   │   ├── channels.py # 대화방 식별·참여 모델
│   │   │   ├── messages.py # 메시지 식별·버전·정렬
│   │   │   ├── policies.py # 사람 발송·범위별 열람 권한
│   │   │   ├── ports.py # 이력 저장 트랜잭션·이벤트 전달 인터페이스
│   │   │   └── use_cases.py # 발송·열람·변경 조회 흐름
│   │   ├── data_access/ # [후보] 외부 데이터 작업의 공통 정책
│   │   │   ├── domain.py # [후보] 데이터 작업·버전·실행 상태
│   │   │   ├── ports.py # [후보] 실행·스키마 조회·저장 인터페이스
│   │   │   ├── policies.py # [후보] 입력·범위·실행 한도
│   │   │   └── use_cases.py # [후보] 등록·게시·실행·취소
│   │   ├── usage/ # 과금과 독립된 사용량 계측·자원 한도
│   │   │   ├── metrics.py # 계측 항목·단위·측정 의미
│   │   │   ├── limits.py # 시스템 기본값·조직·워크스페이스별 한도 설정
│   │   │   ├── policies.py # 유효 한도 결정·초과 처리 판단
│   │   │   ├── ports.py # 계측·저장·원자적 사용권 확보 인터페이스
│   │   │   └── use_cases.py # 조회·설정·사용권 확보·갱신·반환
│   │   ├── billing/ # [후보] 향후 구독·플랜 제공 기능·계측과 분리
│   │   ├── appearance/ # 테마 설정·검증 규칙
│   │   ├── audit/ # 조직·권한·실행 변경 이력
│   │   ├── administration/ # SaaS 운영자 유스케이스
│   │   └── shared/ # 실제 여러 도메인이 공유하는 최소 기반
│   ├── adapters/ # DB·비밀 정보·큐·외부 서비스 구현
│   │   ├── postgres/ # 플랫폼 저장·테넌트 격리·한도 설정·사용량 이력
│   │   │   ├── chat.py # 채팅 저장·커서 조회·트랜잭션 이벤트 기록
│   │   │   └── usage.py # 한도 설정 이력·영속 계측 저장
│   │   ├── identity/ # 암호 처리·인증 제공자 연동
│   │   ├── external_db/ # [후보] 고객 DB 드라이버·운영 DB와 분리
│   │   │   ├── postgres.py # [후보] 외부 PostgreSQL 실행·스키마 조회
│   │   │   ├── pools.py # [후보] 연결별 풀·상한·회수
│   │   │   └── network.py # [후보] 목적지·TLS·접속 경로 검증
│   │   ├── redis/ # 큐·공유 상태·원자적 사용량 카운터·만료 가능한 사용권
│   │   │   ├── chat_events.py # 실시간 이벤트 전달·채팅 이력 원본 아님
│   │   │   └── usage.py # 원자적 카운터·사용권·갱신·반환
│   │   ├── object_storage/ # 문서·사용자 소스 스냅샷·불변 산출물 저장
│   │   ├── workbench_build.py # 격리 빌드 환경 생성·호출·취소·회수
│   │   ├── mcp_client/ # 외부 MCP 연결 구현
│   │   ├── http_connectors/ # 외부 API·제공자 호출 구현
│   │   ├── embeddings/ # 임베딩 제공자 구현
│   │   └── pgvector/ # 문서 벡터 검색 구현
│   ├── contracts/ # 데이터 계약 도메인·원본과 언어별 생성 코드 소유
│   │   ├── schemas/ # 실제 공존 버전의 스키마
│   │   │   ├── workbench/ # 등록 정보·SDK 메시지·릴리스·화면 계약
│   │   │   │   ├── v1/ # 기존 선언형 계약 보존·이전 대응 후 전환
│   │   │   │   └── v2/ # 제안: 코드 기반 계약 버전·미구현
│   │   │   │       ├── manifest.schema.json # 코드 진입점·요구 기능·호환성
│   │   │   │       ├── bridge.schema.json # SDK 요청·응답·이벤트·취소
│   │   │   │       └── release.schema.json # 소스·빌드·산출물 릴리스 메타데이터
│   │   │   ├── catalog/ # 컴포넌트·자산 목록 계약
│   │   │   ├── appearance/ # 테마 계약
│   │   │   ├── usage/ # 사용량·한도·초과 오류 계약
│   │   │   │   └── v1/ # 제안: 첫 사용량 계약
│   │   │   │       ├── limit.schema.json # 범위·계측 단위·한도 설정
│   │   │   │       └── result.schema.json # 사용량·허용·한도 초과 결과
│   │   │   ├── chat/ # 사람 채팅·읽기 전용 MCP 데이터 계약
│   │   │   │   └── v1/ # 제안: 첫 채팅 계약
│   │   │   │       ├── message.schema.json # 메시지 레코드·제한된 발송 입력
│   │   │   │       └── page.schema.json # 이력·변경·불투명 다음 조회 커서
│   │   │   └── data-access/ # [후보] 데이터 작업 입력·출력 계약
│   │   ├── py/ # Python 계약 코드·생성물 원본 추적
│   │   ├── ts/ # TypeScript 계약 코드·생성물 원본 추적
│   │   ├── examples/ # 계약 예제·민감 데이터 금지
│   │   └── compatibility/ # 버전 호환성 비교 자료
│   ├── design-system/ # 공통 골격·데이터 계약·테마·UI 자산
│   │   ├── components/ # 공통 작업 목록·사이드바·패널·기본 UI
│   │   ├── theme.tsx # 테마 제공·전환
│   │   ├── tokens.css # 공통 시각 토큰
│   │   └── assets/ # 공통 UI 에셋·아이콘·로고·폰트·이미지 원본
│   └── workbench/ # 작업 화면 도구 묶음·하위 패키지 의존성 독립
│       ├── sdk/ # 사용자 코드용 공개 API·호스트 내부 구현 제외
│       │   ├── index.ts # 공개 export
│       │   ├── client.ts # 호스트 통신 클라이언트
│       │   ├── data.ts # 허용된 데이터 동작 요청
│       │   ├── actions.ts # 실행·탐색 요청
│       │   ├── context.ts # 화면 컨텍스트·변경 구독
│       │   └── theme.ts # 호스트 테마 연결
│       ├── build/ # 격리 환경 안에서 실행하는 고정 빌드 도구
│       │   ├── main.ts # 내부 빌드 도구 진입점
│       │   ├── validate.ts # 소스·등록 정보·의존성 정책 검사
│       │   ├── typecheck.ts # 타입 검사·진단
│       │   ├── bundle.ts # 고정 도구체인으로 번들 생성
│       │   └── artifact.ts # 파일 목록·해시·빌드 메타데이터
│       ├── runtime/ # 플랫폼 측 로딩·렌더링·수명 관리
│       │   ├── renderer.tsx # 신뢰된 표준 화면·격리된 커스텀 화면 선택
│       │   ├── SandboxHost.tsx # 격리 화면 생성·종료·복구·구체 기술 미정
│       │   ├── bridge.ts # SDK 메시지 검사·허용 기능 중계
│       │   ├── bindings.ts # 호스트 측 데이터 연결·취소
│       │   ├── actions.ts # 호스트 측 동작 전달·서버 인가 대체 금지
│       │   ├── registry.ts # 작업·에셋·호환 버전 조회
│       │   └── view-state.ts # 사이드바·패널 상태 연결·복원
│       └── editor/ # 사용자 코드 작성 환경
│           ├── WorkbenchEditor.tsx # 편집·미리보기·게시 화면
│           ├── preview.tsx # 동일한 격리 런타임의 초안 미리보기
│           └── diagnostics.ts # 파일·행·열·단계별 오류 표시
├── tests/ # 모든 테스트·앱 또는 패키지 우선 분류
│   ├── api/ # API 테스트
│   ├── web/ # 웹·브라우저 테스트
│   ├── mcp/ # MCP 테스트
│   ├── jobs/ # 작업 실행·스케줄러 테스트
│   ├── packages/ # 패키지 테스트·사용량 한도·동시성·사용권 회수 포함
│   ├── contracts/ # 계약 생성·언어 간 일치·호환성 테스트
│   ├── integration/ # 여러 앱에 걸친 통합 테스트
│   └── support/ # 공통 테스트 데이터·보조 코드
├── scripts/ # 개발·생성·검증 실행 도구
│   ├── contracts/ # 계약 코드 생성 도구
│   └── quality/ # 코드 품질 검사 실행 도구·설정
├── deploy/ # 배포 대상별 절차·설정
│   └── local/ # 현재 로컬 서버 배포
│       ├── dev/ # 개발 환경 설정·개발용 자원 참조
│       ├── stg/ # 사전 검증 환경 설정·검증용 자원 참조
│       ├── prod/ # 운영 환경 설정·운영용 자원 참조
│       ├── config/ # 로컬 서비스·빌드 격리·산출물 제공·서버 자원 상한
│       ├── env.example # 비밀 값 없는 설정 예시
│       ├── deploy.sh # 설치·갱신 절차
│       ├── rollback.sh # 이전 배포 복구 절차
│       └── OPERATIONS.md # 시작·재시작·운영·복구 안내
├── migrations/ # 플랫폼 DB의 추가 방식 변경 이력
├── docs/ # 원본·조사·명세 문서
│   ├── original/ # 보존할 원본 자료
│   ├── processed/ # 출처 기반 조사·미승인 제안
│   │   └── artifacts/ # 문서·검수용 비민감 증빙·런타임 출력 제외
│   │       └── screenshots/ # Codex 화면 캡처·검수 이미지
│   └── skills/ # 사용자 언어 HTML 명세
│       ├── info-*/ # 정보 명세·용어와 확인된 시스템 정보
│       ├── rule-*/ # 규칙 명세·필수 정책과 개발 규칙
│       └── design-*/ # 설계 명세·승인된 제품 및 기술 설계
├── env/ # 로컬 전용 실제 환경변수·비밀 설정·Git 제외
│   └── local/ # 현재 로컬 서버 환경별 설정
│       ├── dev/ # 개발 환경 실제 값
│       ├── stg/ # 사전 검증 환경 실제 값
│       └── prod/ # 운영 환경 실제 값
├── .codex/ # Codex 프로젝트 설정·영문 AI 명세
│   ├── config.toml # 공유 가능한 Codex 설정·비밀 제외
│   └── skills/ # 프로젝트 스킬·명세
│       ├── info-*/ # 정보 명세
│       ├── rule-*/ # 규칙 명세
│       └── design-*/ # 설계 명세
├── .github/ # GitHub 협업·자동화 설정
│   ├── workflows/ # CI/CD 워크플로
│   ├── ISSUE_TEMPLATE/ # 이슈 작성 템플릿
│   └── pull_request_template.md # PR 작성 템플릿
├── .vscode/ # 공유 가능한 VS Code 개발 설정
│   ├── settings.json # 프로젝트 에디터 설정
│   ├── launch.json # 실행·디버깅 설정
│   ├── tasks.json # 개발 명령 연결
│   └── extensions.json # 권장 확장 목록
├── feedback/ # 사용자 소유·Git 제외·자동 관리 금지
├── uploads/ # 사용자 소유·Git 제외·자동 관리 금지
└── README.md # 저장소 안내
```

- 루트 패키지 설정·잠금 파일·언어 설정·`.gitignore`는 루트에 둔다.

- 이 그림은 소유권을 설명하며 모든 설정 파일을 나열한 최종 파일 명세가 아니다.

- 실제 파일이 필요할 때만 디렉터리를 만든다.

- 불필요한 `src/<앱 또는 패키지 이름>/` 중첩을 추가하지 않는다.

- 라우터 하나를 위해 `<도메인>/router.py` 구조를 만들지 않는다.

- 합의 범위를 벗어난 구조 그룹 추가·이름 변경은 사유와 범위를 먼저 설명한다.

- 기존 소유자 아래 필요한 일반 파일이나 도메인 묶음은 새 루트 설계와 구분한다.

<a id="section-6"></a>

<a id="앱과-패키지의-책임"></a>

## 29. 앱과 패키지의 책임

| 소유 경로 | 책임 |
| --- | --- |
| `apps/api` | HTTP 입출력과 API 전용 서비스 흐름 조립 |
| `apps/web/pages` | 페이지 단위 화면 |
| `apps/web/components` | 웹 앱 내부에서 재사용하는 UI |
| `apps/web/api` | 브라우저 HTTP 요청 함수. 서버 진입점이 아님 |
| `apps/mcp` | MCP 도구·리소스·전송과 MCP 전용 서비스 흐름 조립 |
| `apps/jobs` | 비동기 작업·스케줄러·배치·주기 실행 |
| `packages/core` | 공유 도메인 규칙·유스케이스·외부 구현을 위한 인터페이스 |
| `packages/core/usage` | 계측 항목·조절 가능한 한도·사용권 허용 판단. 과금에 의존하지 않음 |
| `packages/core/chat` | 사람 메시지·권한 있는 이력/변경 조회. 에이전트 발송 제외 |
| `packages/adapters` | DB·스토리지·큐·비밀·외부 서비스·원자적 카운터와 사용권 구현 |
| `packages/contracts/schemas` | 기능별 데이터 계약 원본 |
| `packages/contracts/py`, `packages/contracts/ts` | 언어별 계약 생성 코드 |
| `packages/design-system` | 공통 시각 기반·자산·컴포넌트·UI 용어 |
| `packages/workbench/sdk` | 사용자용 타입 API·호스트 통신. 호스트 내부 구현·비밀 제외 |
| `packages/workbench/build` | 격리 환경 안의 고정 검증·타입 검사·번들·산출물 도구 |
| `packages/workbench/runtime` | 호스트 로딩·표준/격리 렌더링·중계·화면 수명 관리 |
| `packages/workbench/editor` | 코드 편집·진단·격리 미리보기·게시 UI |

<a id="section-6-1"></a>

<a id="서비스-조립과-의존성"></a>

### 29.1. 서비스 조립과 의존성

- 앱 서비스는 전송 방식에 맞는 흐름을 조립한다.

- 공통 권한 판단·검증·상태 전이·업무 판단은 패키지 유스케이스에 두고 API와 MCP에 중복 구현하지 않는다.

- **앱끼리 직접 import하지 않는다.**

- core는 앱·adapters·프레임워크·DB 라이브러리·큐·외부 제공자 SDK를 import하지 않는다.

- adapters는 core의 인터페이스를 구현한다.

- 연결 구성을 바꿔도 테넌트 격리·불변 이력·멱등성·실행 시점 권한 확인·외부 UI 샌드박스 경계를 유지한다.

<a id="section-6-2"></a>

<a id="python-패키징"></a>

### 29.2. Python 패키징

- Python 이름 공간과 빌드 매핑은 이 물리 구조를 유지하면서 공식 `mcp` SDK 같은 외부 모듈을 가리지 않도록 선택한다.

- import 이름 충돌을 해결하려고 물리적 중첩 디렉터리를 다시 만들지 않는다.

<a id="section-7"></a>

<a id="사용량자원-한도의-책임"></a>

## 30. 사용량·자원 한도의 책임

<a id="section-7-1"></a>

<a id="사용량과-과금-분리"></a>

### 30.1. 사용량과 과금 분리

- 2026-09-15 승인: BM 구현에 앞서 운영 사용량을 계측하고 한도를 조절한다.

- core/usage가 계측 항목·시스템 기본값·조직/워크스페이스별 설정·사용 허용 판단을 소유한다.

- **billing 없이 동작하며 billing을 import하지 않는다.**

- 향후 billing이 usage 계약으로 플랜별 한도 설정을 제공할 수 있지만 이번 구조에 가격·청구·자동 초과 과금을 도입하지 않는다.

<a id="section-7-2"></a>

<a id="한도-변경-권한"></a>

### 30.2. 한도 변경 권한

- API는 권한 있는 조회·설정, SaaS 관리자 화면은 조정을 담당한다.

- 조직/워크스페이스별 한도가 있다는 이유로 해당 구성원에게 변경 권한이 생기지는 않는다.

- 변경 이력은 기존 audit 도메인에 남긴다.

- MCP와 jobs도 같은 정책을 적용한다.

<a id="section-7-3"></a>

<a id="계측과-저장소"></a>

### 30.3. 계측과 저장소

- 계측 후보는 동시 연결·메시지 빈도/크기·저장 바이트·MCP 조회 빈도·빌드/작업 동시 실행 수다.

- 현재 점유량·시간 구간별 횟수·누적 사용량을 구분하고 재시도·재전달을 중복 계측하지 않는다.

- PostgreSQL은 설정·사용량 이력, Redis는 공유 원자적 카운터·만료 가능한 사용권을 구현한다.

- 도메인은 Redis API가 아닌 필요한 동작을 정의한다.

- 여러 프로세스에서 단순 조회 후 증가만으로 한도를 집행하지 않는다.

<a id="section-7-4"></a>

<a id="사용권-수명과-서버-상한"></a>

### 30.4. 사용권 수명과 서버 상한

- 사용권 확보·갱신·반환·만료/정합성 회수는 연결 해제와 비정상 종료를 포함한다.

- 사용권만 만료되고 작업은 계속 실행되어 한도를 넘는 문제도 설계해야 한다.

- 한도가 권한 검사나 실행 격리를 대신하지 않는다.

- deploy/local은 서버 전체 연결·메모리·프로세스의 안전 상한을 소유하며 테넌트 설정이 이를 우회하지 못한다.

- 새 루트·서비스·배포 기술은 추가하지 않는다.

<a id="section-7-5"></a>

<a id="후속-명세"></a>

### 30.5. 후속 명세

- 수치 기본값·집계 시간 구간·설정 우선순위·실행 중 한도 축소·거절/대기/재시도·계측 저장소 장애 정책은 파일별 후속 명세 대상이다.

- 기존 Redis 배치 재사용이 서비스 변경 허가는 아니다.

- *전체 파일/테스트 대응표는 아직 완료 전이다.*

<a id="section-8"></a>

<a id="사용자-코드의-의존성과-실행-경계"></a>

## 31. 사용자 코드의 의존성과 실행 경계

<a id="section-8-1"></a>

<a id="sdk와-호스트-검증"></a>

### 31.1. SDK와 호스트 검증

- 사용자 코드는 공개 SDK와 design-system을 사용하며 앱·호스트 runtime 내부·core·adapters·빌드 도구를 import하지 않는다.

- SDK는 생성된 계약을 사용하고 권한을 부여하지 않는다.

- runtime은 호스트 측 프로토콜을 구현한다.

- SDK를 우회한 요청도 메시지와 서버 동작 검사를 거친다.

- **클라이언트 컨텍스트는 권한 증거가 아니다.**

<a id="section-8-2"></a>

<a id="미리보기와-화면-격리"></a>

### 31.2. 미리보기와 화면 격리

- editor는 runtime으로 미리보기를 구성한다.

- 스탠다드·커스텀은 UI·데이터 계약을 공유하지만 신뢰 수준은 다르다.

- 호스트가 작업 목록·외곽 배치를 소유하고 선택적 사이드바·패널은 제한된 상태를 교환한다.

- 호스트 DOM 접근을 공유하지 않으며 패널 탭은 선택 사항이다.

<a id="section-8-3"></a>

<a id="빌드-실행-경계"></a>

### 31.3. 빌드 실행 경계

- workbench/build는 내부 실행 도구 패키지이지 별도 배포 서비스가 아니다.

- 작업 진입점은 apps/jobs이고 adapter가 격리 경계 너머에서 빌드 도구를 호출한다.

- 환경별 설정은 deploy/local에 둔다.

- 브라우저 패키지는 빌드 도구에 의존하지 않는다.

- 임의 사용자 스크립트·플러그인으로 고정 빌드 정책을 대체하지 않는다.

<a id="section-8-4"></a>

<a id="후속-검수"></a>

### 31.4. 후속 검수

- 정확한 SDK export·메시지 스키마·산출물 접근 통제·의존성 정책·샌드박스 기술·파일별 입출력/오류/테스트 연결은 후속 검수 대상이다.

- 이 트리로 구현 계약 완료나 현재 테스트 실행을 승인하지 않는다.

<a id="section-9"></a>

<a id="계약과-테스트"></a>

## 32. 계약과 테스트

<a id="section-9-1"></a>

<a id="계약-원본과-생성물"></a>

### 32.1. 계약 원본과 생성물

- `packages/contracts/`는 데이터 계약 도메인이다.

- `schemas/`: 기능별 계약 원본. 채팅·작업·사용량 등으로 구분한다.

- `py/`·`ts/`: 원본에서 생성하는 언어별 코드.

- 루트 `contracts/`는 목표 구조에서 제외한다. 기존 파일은 후속 이전 때 대응시켜 보존한다.

- `packages/workbench/`는 sdk·build·runtime·editor를 묶으며 하위 패키지의 의존성 경계는 유지한다.

- 실제 공존하는 계약에만 `packages/contracts/schemas/<대상>/v1/`처럼 버전을 두고 빈 버전 구조는 만들지 않는다.

- 생성물을 직접 수정하지 말고 원본 스키마나 생성기를 수정한다.

<a id="section-9-2"></a>

<a id="테스트-배치"></a>

### 32.2. 테스트 배치

- 모든 테스트와 테스트 전용 보조 코드는 루트 `tests/`에 둔다.

- 검증 대상인 api·web·mcp·jobs·packages를 우선 기준으로 분류하고 필요한 경우에만 그 안에서 도메인을 나눈다.

- `tests/contracts`: 스키마·코드 생성·언어 간 일치·호환성 검증.

- `tests/integration`: 여러 앱에 걸친 동작 검증.

- `tests/support`: 공통 테스트 데이터와 보조 코드.

- 패키지 단위 테스트는 `tests/packages`에 둔다.

- 이는 이전의 도메인 우선 구조와 패키지 내부 테스트 배치를 대체한다.

<a id="section-10"></a>

<a id="스크립트와-배포"></a>

## 33. 스크립트와 배포

<a id="section-10-1"></a>

<a id="개발-스크립트"></a>

### 33.1. 개발 스크립트

- `scripts/`는 개발·코드 생성·검증 실행 도구를 담는다.

- 검증 조건은 tests, 비즈니스 로직은 packages, 반복 업무 실행은 apps/jobs에 둔다.

- 단순 스크립트 하나 때문에 폴더를 만들지 않는다.

<a id="section-10-2"></a>

<a id="현재-로컬-배포"></a>

### 33.2. 현재 로컬 배포

- **현재 배포 대상은 사용자의 로컬 서버다.**

- `deploy/local`은 서버 설정 및 설치·시작·재시작·업데이트·복구 절차를 소유한다.

- **추가 승인**: `dev/`·`stg/`·`prod/`를 환경별 설정 위치로 확보한다.

- 공통 절차는 local에 두고 환경별 차이만 각 하위 디렉터리에 둔다.

- 환경 구조 확보는 세 환경의 실제 배포·기동을 뜻하지 않는다. 비밀 값은 저장하지 않는다.

- 이를 `scripts/operations`에 중복 배치하지 않는다.

- 실제 선택한 배포 방식의 설정만 포함한다.

- 폐기한 Docker·Makefile 실행 방식을 이 구조로 다시 도입하지 않는다.

- `.github/workflows`는 CI/CD 단계를 연결한다.

- `migrations`는 추가 방식으로 DB 스키마 이력을 관리하며 디렉터리 개편 중 기존 이력을 재작성하지 않는다.

<a id="section-10-3"></a>

<a id="향후-aws-전환"></a>

### 33.3. 향후 AWS 전환

- AWS는 향후 배포 대상이다.

- 실제 전환 시 `deploy/aws`를 추가하며 새 루트는 필요 없다.

- 지금 빈 aws·shared 디렉터리를 만들지 않는다.

- 두 대상이 실제로 공유하고 사용자가 수용할 때만 공통 배포 설정을 추출한다.

- 배포 대상(local·향후 aws)과 운영 환경(dev·stg·prod)은 별개이므로 로컬 서버에서도 운영 환경을 실행할 수 있다.

- **비밀 값은 Git에 넣지 않으며 env.example에도 포함하지 않는다.**

<a id="section-11"></a>

<a id="사용자-소유-디렉터리"></a>

## 34. 사용자 소유 디렉터리

- 루트 feedback/·uploads/는 사용자 소유이며 앱 코드·배포 출력·임시 빌드 저장소나 이번 개편 대상이 아니다.

- 기존 `.gitignore`의 `/feedback/`·`/uploads/` 항목을 유지한다.

- 이동·이름 변경·삭제·정리·용도 변경·자동 관리·Git 강제 추가를 하지 않는다.

- 접근이나 변경에는 해당 디렉터리를 대상으로 한 별도 사용자 지시가 필요하며 일반 정리·배포·개편 허가에 포함되지 않는다.

- docs의 원본·가공 자료·명세 소유권을 보존한다.

- `docs/processed/<category>-<name>/assets/`: Codex가 생성한 문서·검수용 화면 캡처.

- 캡처에는 비밀·개인정보·사용자 업로드를 포함하지 않는다. 보존할 증빙은 관련 가공 문서에서 출처·검수 대상을 기록한다.

- 자동 테스트 출력·빌드 결과·런타임 로그는 이 문서 증빙 디렉터리에 넣지 않는다.

- `docs/skills/info-*/`: 용어·확인된 시스템 정보.

- `docs/skills/rule-*/`: 필수 정책·개발 규칙.

- `docs/skills/design-*/`: 승인된 제품·기술 설계.

- `*`는 이름 패턴이다. 실제 디렉터리는 `rule-workbench-structure/`처럼 만든다.

- 과거 구조 그림은 이전 아키텍처를 복원할 권한이 아니다.

<a id="section-12"></a>

<a id="이전-완료-기준"></a>

## 35. 이전 완료 기준

- 파일 이동 시 import·빌드 및 패키지 매핑·리소스 경로·테스트 탐색·실행 명령·CI·유지 중인 참조 문서를 함께 갱신한다.

- 기존 미커밋 변경과 데이터를 보존한다.

- 영향받는 동작과 패키징을 검증하고 기존 실패는 별도로 보고한다.

- 이 명세의 작성은 코드나 테스트의 이전 완료를 뜻하지 않는다.

- **현재 명세 단계의 실행 제한과 테스트 보류**는 [디렉터리 구조 계약](#directory-contract)을 따른다.
