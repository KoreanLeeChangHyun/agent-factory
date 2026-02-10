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
