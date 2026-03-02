---
name: workflow-cc-implement
description: "Workflow command skill for cc:implement. Handles code implementation, modification, refactoring, architecture design, and asset management (agent/skill/command). Auto-loads keyword-based skills for refactoring, architecture, and manager operations."
disable-model-invocation: true
---

# Implement Command

코드 구현, 수정, 리팩토링을 수행하는 워크플로우 커맨드 스킬.

상세 실행 절차는 `.claude/commands/cc/implement.md`를 참조한다.

## 메타데이터

### 키워드 매핑 요약

| 키워드 | 로드 스킬 | 비고 |
|--------|----------|------|
| 리팩토링, refactor, 코드 개선, 추출, extract | review-code-quality | 코드 품질 검사 병행 |
| 아키텍처, architecture, 설계, architect, 시스템 구조, 컴포넌트 | design-architect + design-mermaid-diagrams | 다이어그램 생성 지원 |
| 에이전트, agent | management-agent | 에이전트 관리 |
| 스킬, skill | management-skill | 스킬 관리 |
| 커맨드, command, 명령어 | management-command | 커맨드 관리 |

### 에셋 경로

| 에셋 | 경로 |
|------|------|
| 에이전트 | `.claude/agents/*.md` |
| 스킬 | `.claude/skills/<skill-name>/` |
| 커맨드 | `.claude/commands/cc/*.md` |

## 참조

이 스킬의 실행 절차는 대응 커맨드 파일(`.claude/commands/cc/implement.md`)이 Single Source of Truth이다.
