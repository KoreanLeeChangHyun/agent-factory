# Command-Skill Mapping

Worker가 skills 파라미터 없이 호출될 때 명령어에 따라 자동 로드하는 스킬 매핑 정의.

> 이 파일은 `workflow-work/SKILL.md`와 `worker.md`에서 참조됩니다.
> 스킬 매핑을 변경할 때 이 파일만 수정하면 됩니다.

## 명령어별 기본 스킬 매핑

| 명령어 | 자동 로드 스킬 | 용도 |
|--------|---------------|------|
| implement | command-code-quality-checker, command-verification-before-completion | 코드 품질 검사(Generator-Critic 루프 포함), 완료 전 검증(점진적 검증 포함). 에셋 관리 키워드 감지 시 매니저 스킬 조건부 로드 |
| review | command-requesting-code-review, command-code-quality-checker | 리뷰 체크리스트 적용 + 정량적 품질 검사. 보안/아키텍처/프론트엔드/성능 키워드 감지 시 전문 리뷰 스킬 조건부 로드 |
| research | command-research, research-integrated | 웹 조사(command-research) + 통합 조사(research-integrated). references/ 가이드로 교차 검증 및 출처 평가 지원. 키워드별 병렬/검증 스킬 자동 로드. 분석 키워드 감지 시 analyze-* 스킬 조건부 로드. 코드 탐색(deep-research)은 키워드 매핑으로 조건부 로드 |
| strategy | command-strategy | 다중 워크플로우 전략 수립, 로드맵 생성 |

## 키워드 기반 추가 스킬 로드

작업 내용에 특정 키워드가 포함되면 추가 스킬을 로드합니다:

| 키워드 | 추가 로드 스킬 |
|--------|---------------|
| 테스트, test, TDD | tdd-guard-hook |
| 구현, implement, 기능 추가, feature | command-verification-before-completion |
| 리팩토링, refactor, 리팩터, 코드 개선 | command-code-quality-checker |
| 마이그레이션, migration, 스키마 변경, DB 변경 | command-code-quality-checker, command-verification-before-completion |
| 품질, quality, 코드 품질, code quality | command-code-quality-checker |
| API, REST, GraphQL, 엔드포인트, endpoint | command-code-quality-checker |
| PR, pull request | pr-summary, github-integration |
| 다이어그램, diagram, UML | command-mermaid-diagrams |
| 아키텍처, architecture, 설계, architect, 시스템 구조, 컴포넌트 | command-architect, command-mermaid-diagrams |
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
| 교차 검증, cross-validation, 출처 평가, source evaluation | command-research, research-grounding |
| 심층 조사, deep research, 코드 탐색, 대규모 분석 | deep-research |
| 웹+코드 통합, integrated research, 통합 조사, 복합 조사 | research-integrated |
| 병렬 조사, parallel research, 종합 조사, 다중 에이전트 | research-parallel |
| 신뢰도 검증, 출처 검증, source verification, grounding | research-grounding |
| 보안 리뷰, security review, OWASP 리뷰, 취약점 리뷰, 보안 감사 | command-review-security |
| 아키텍처 리뷰, architecture review, 설계 리뷰, 구조 리뷰, 계층 검증 | command-review-architecture |
| 프론트엔드 리뷰, frontend review, React 리뷰, UI 리뷰, 컴포넌트 리뷰 | command-review-frontend |
| 성능 리뷰, performance review, 쿼리 리뷰, DB 리뷰, N+1 | command-review-performance |
| 종합 리뷰, comprehensive review, 전체 리뷰, full review | review-comprehensive |
| 리뷰 반영, review feedback, 피드백 구현, 리뷰 수정, 리뷰 대응 | review-feedback-handler |
| PR 리뷰, pull request review, PR 검증, PR 체크 | review-pr-integration |
| 보안, security, OWASP, 취약점, 정적 분석, static analysis, CodeQL, Semgrep | command-static-analysis |
| 접근성, a11y, accessibility, WCAG | command-web-design-guidelines |
| 디버깅, debugging, 버그, bug, 에러 추적, error tracking, 근본 원인 | command-systematic-debugging |
| React, Next.js, 리액트, react 성능, react performance | command-react-best-practices, command-framework-react |
| FastAPI, fastapi, Python API, 파이썬 API | command-framework-fastapi |
| 전략, strategy, 로드맵, roadmap, 마일스톤, milestone, 다중 워크플로우 | command-strategy |
| 디자인 패턴, design pattern, GoF, SOLID 패턴 | software-design-patterns |
| RICE, 우선순위, 작업 분해, task decomposition, scope | scope-decomposer |
| 명령어 관리, command manager, 명령어 등록 | command-manager |
| 스킬 생성, skill create, 스킬 관리, skill manage | command-skill-manager |
| 스킬 검색, skill search, find skill, 스킬 설치, 스킬 통합, auto integrate | skill-auto-integrator |
| 에이전트 관리, agent manager, 에이전트 목록 | command-agent-manager |
| 요구사항 분석, SRS, 코드베이스 분석, 코드 구조, 데이터베이스 분석, DB 분석, 데이터 분석, EDA | analyze-* (키워드 판단) |
| 커버리지, coverage, diff coverage, 코드 커버리지, 테스트 커버리지 | command-coverage-analysis |
| PBT, property-based, 속성 기반 테스트, Hypothesis, fast-check | command-property-based-testing |
| 런타임 검증, runtime validation, Zod, beartype, 스키마 검증, 계약 검증 | command-runtime-contract |
| 뮤테이션, mutation testing, Stryker, mutmut, 테스트 품질 | command-mutation-testing |
| 테스트 설계, test design, 동치 분할, 경계값, 결정 테이블 | command-test-design |

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
