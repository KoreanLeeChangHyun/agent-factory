# Command-Skill Mapping

Worker가 skills 파라미터 없이 호출될 때 명령어에 따라 자동 로드하는 스킬 매핑 정의.

> 이 파일은 `workflow-work/SKILL.md`와 `worker.md`에서 참조됩니다.
> 스킬 매핑을 변경할 때 이 파일만 수정하면 됩니다.

## 명령어별 기본 스킬 매핑

| 명령어 | 자동 로드 스킬 | 용도 |
|--------|---------------|------|
| implement | command-code-quality-checker, command-verification-before-completion | 코드 품질 검사, 완료 전 검증. 에셋 관리 키워드 감지 시 매니저 스킬 조건부 로드 |
| refactor | command-code-quality-checker, command-verification-before-completion | 코드 품질 검사, 완료 전 검증 |
| review | command-requesting-code-review | 리뷰 체크리스트 적용 |
| build | command-verification-before-completion | 빌드 스크립트 검증 |
| analyze | analyze-* (키워드 판단) | 분석 유형별 스킬 |
| architect | command-architect, command-mermaid-diagrams | 아키텍처 설계, 다이어그램 생성 |
| framework | framework-* (프레임워크명 판단) | 프레임워크별 스킬 |
| research | command-research, deep-research | 조사 및 심층 연구 |

## 키워드 기반 추가 스킬 로드

작업 내용에 특정 키워드가 포함되면 추가 스킬을 로드합니다:

| 키워드 | 추가 로드 스킬 |
|--------|---------------|
| 테스트, test, TDD | tdd-guard-hook |
| PR, pull request | pr-summary, github-integration |
| 다이어그램, diagram, UML | command-mermaid-diagrams |
| 프론트엔드, frontend, UI | frontend-design |
| 웹앱, webapp | webapp-testing |
| docx, 문서, document, 워드 | document-skills/docx |
| pptx, 프레젠테이션, presentation, 슬라이드 | document-skills/pptx |
| xlsx, 스프레드시트, spreadsheet, 엑셀 | document-skills/xlsx |
| pdf, PDF | document-skills/pdf |
| MCP, Model Context Protocol | mcp-manager |
| 3P, newsletter, status report, 뉴스레터 | internal-comms |
| changelog, release notes, 릴리스 노트, 변경 이력 | changelog-generator |
| LWC, Lightning Web Component, Salesforce, 세일즈포스 | lwc-custom |
| Apple, HIG, 애플, apple design | apple-design |
| GHA, GitHub Actions, CI, CI/CD, pipeline, 빌드 실패, workflow run | command-gha-analysis |

## 확장 가이드

새로운 명령어나 키워드-스킬 매핑을 추가할 때:

1. **명령어별 기본 스킬**: 위 "명령어별 기본 스킬 매핑" 테이블에 행을 추가
2. **키워드 기반 추가 스킬**: 위 "키워드 기반 추가 스킬 로드" 테이블에 행을 추가
3. **worker.md/SKILL.md 수정 불필요**: 두 파일 모두 이 파일을 참조하므로 별도 수정 없이 매핑이 반영됨

## Description 기반 폴백 가이드

위의 명령어별 기본 매핑과 키워드 매핑에서 적합한 스킬을 찾지 못한 경우, `.claude/skills/*/SKILL.md`의 `description` 필드를 탐색하여 태스크 내용과 매칭할 수 있습니다.

### 매칭 우선순위

스킬을 결정할 때 다음 우선순위를 따릅니다. 상위 단계에서 적합한 스킬을 찾으면 하위 단계는 실행하지 않습니다.

| 우선순위 | 매칭 방식 | 설명 |
|---------|----------|------|
| 1순위 | **skills 파라미터** | 오케스트레이터가 명시적으로 전달한 스킬. 무조건 사용 |
| 2순위 | **명령어별 기본 매핑** | 위 "명령어별 기본 스킬 매핑" 테이블 참조 |
| 3순위 | **키워드 기반 매핑** | 위 "키워드 기반 추가 스킬 로드" 테이블 참조 |
| 4순위 | **description 기반 폴백** | SKILL.md의 description 필드를 태스크 내용과 의미론적으로 매칭 |

### Description 기반 폴백 절차

1순위~3순위에서 적합한 스킬을 찾지 못했을 때 다음 절차를 수행합니다.

1. **description 스캔**: `.claude/skills/*/SKILL.md`의 frontmatter에서 `description` 필드를 읽어 사용 가능한 스킬 목록을 파악합니다.
2. **태스크 내용 대조**: 현재 태스크의 작업 내용(계획서의 태스크 설명, 대상 파일, 작업 상세)과 각 스킬의 description을 의미론적으로 비교합니다.
3. **매칭 판단 기준**: description에 다음 패턴이 포함된 스킬을 우선 선택합니다.
   - `"use for [태스크 유형]"` - 태스크 유형이 현재 작업과 일치하는 경우
   - `"Use this when [상황]"` - 상황이 현재 태스크와 부합하는 경우
   - 태스크 내용의 핵심 키워드가 description에 자연어로 포함된 경우
4. **선택**: 가장 적합한 스킬을 선택하여 로드합니다. 복수의 스킬이 매칭되면 description의 구체성이 높은 것을 우선합니다.

### 제외 대상

다음 스킬은 description 폴백 대상에서 제외합니다.

| 제외 조건 | 이유 |
|----------|------|
| `disable-model-invocation: true` 플래그가 설정된 스킬 | 내부 워크플로우 전용으로 자동 호출 차단 |
| `workflow-*` 접두사 스킬 | 워크플로우 오케스트레이션 전용, Worker가 직접 로드 대상이 아님 |

### Description 품질 기준

description 기반 폴백의 정확도는 각 스킬의 description 품질에 직접 의존합니다. 스킬 작성 시 다음 기준을 따르면 폴백 매칭 정확도가 향상됩니다.

| 기준 | 양호한 예시 | 미흡한 예시 |
|------|-----------|-----------|
| 역할 명시 | "Use this when generating PR summaries for GitHub pull requests" | "PR helper" |
| 태스크 유형 포함 | "use for code review checklist validation and quality gates" | "review skill" |
| 최소 길이 50자 이상 | "Mermaid diagram generator. Use this when creating flowcharts, sequence diagrams, or architecture visualizations in markdown documents" | "mermaid diagrams" |
