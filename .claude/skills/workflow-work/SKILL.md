---
name: workflow-work
description: "병렬 작업 실행을 위한 범용 에이전트. workflow-plan 스킬 또는 다른 에이전트가 Task 도구로 호출하여 독립적인 작업을 병렬 처리한다. 사용 시점: (1) subagent_type='worker'로 Task 도구 호출 시, (2) 병렬 실행이 필요한 독립 작업 처리 시. 코드 작성, 파일 수정, 검색, 분석 등 모든 유형의 작업을 처리할 수 있다."
disable-model-invocation: true
---

# Work

병렬 작업 실행을 위한 범용 에이전트. 상위 에이전트(planner 등)로부터 할당받은 작업을 독립적으로 처리한다.

> 이 스킬은 workflow-orchestration 스킬이 관리하는 워크플로우의 한 단계입니다. 전체 워크플로우 구조는 workflow-orchestration 스킬을 참조하세요.

**workflow-work의 역할:**
- 오케스트레이터(workflow-orchestration)가 Task 도구로 호출
- 할당받은 작업을 독립적으로 실행
- 결과를 오케스트레이터에 반환 (workflow-work는 workflow-report를 직접 호출하지 않음)
- 오케스트레이터가 모든 work 결과를 수집 후 REPORT 단계로 진행

## 핵심 원칙

1. **단일 책임**: 할당받은 작업만 수행
2. **자율적 실행**: 필요한 도구를 자유롭게 사용하여 작업 완료
3. **명확한 결과 반환**: 작업 결과를 구조화된 형태로 반환
4. **실패 시 보고**: 오류 발생 시 명확한 실패 사유 제공
5. **질문 금지**: 사용자에게 질문하지 않음 (아래 상세)

## 질문 금지 원칙

**WORK 단계에서는 사용자에게 절대 질문하지 않습니다.**

- PLAN 단계에서 모든 요구사항이 완전히 명확화되었음을 전제
- 계획서에 기반하여 독립적으로 작업 수행
- 불명확한 부분이 있어도 사용자에게 질문하지 않음
- 계획서 해석이 필요하면 합리적으로 판단하여 진행

**불명확한 요구사항 처리 절차:**
1. 계획서 재확인 (다른 섹션, 태스크 간 종속성에서 힌트 탐색)
2. 최선의 판단 (베스트 프랙티스, 기존 코드베이스 컨벤션, 안전한 방향)
3. 판단 근거를 작업 내역에 기록
4. 핵심 요구사항을 전혀 파악할 수 없는 경우에만 에러 보고

---

## 터미널 출력 원칙

> 내부 분석/사고 과정을 터미널에 출력하지 않는다. 결과만 출력한다.

- **출력 허용**: 반환값 (3줄 규격), 에러 메시지
- **출력 금지**: 코드 분석 과정, 변경 사항 설명, 파일 탐색 과정, 판단 근거, "~를 살펴보겠습니다" 류, 중간 진행 보고, 작업 계획 설명
- 코드 작성/수정, 파일 탐색, 테스트 실행 등 모든 작업은 묵묵히 수행하고 최종 반환값만 출력
- 배너 출력은 오케스트레이터가 담당 (worker 에이전트는 배너를 직접 호출하지 않음)
- **작업 내역 경로는 반드시 터미널에 출력**: 단, worker가 직접 출력하는 것이 아니라 오케스트레이터가 완료 배너를 통해 출력함. worker는 반환값에 경로를 포함하면 오케스트레이터가 배너에 반영

---

## 작업 실행

오케스트레이터가 worker 에이전트를 Task 도구로 호출하여 작업을 수행합니다.

### Phase 0: 준비 단계 (필수, 순차 1개 worker)

Phase 1~N 실행 전에 반드시 Phase 0을 먼저 수행합니다. Phase 0은 **1개 worker 에이전트가 순차적으로** 실행합니다.

**Phase 0 호출:**
```
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: phase0, planPath: <planPath>, mode: phase0")
```

**Phase 0의 2가지 기능:**

1. **work 작업 디렉터리 생성**: `<workDir>/work/` 디렉터리를 명시적으로 생성합니다.

2. **스킬 매핑**: 계획서(plan.md)의 태스크 목록과 사용 가능한 스킬 목록(`.claude/skills/` 하위)을 비교하여 각 태스크에 적합한 스킬을 매핑합니다.
   - 명령어별 기본 스킬 매핑 테이블을 기반으로 판단
   - 태스크 내용의 키워드를 분석하여 추가 스킬 추천
   - 계획서에 이미 스킬이 명시된 태스크는 그 값을 존중

**Phase 0 결과물:**
- `<workDir>/work/skill-map.md` 파일에 스킬 매핑 결과 저장

**skill-map.md 형식:**
```markdown
# Skill Map

| 태스크 ID | 태스크 설명 | 추천 스킬 | 판단 근거 |
|-----------|------------|----------|----------|
| W01 | [태스크 설명] | skill-a, skill-b | [근거] |
| W02 | [태스크 설명] | skill-c | [근거] |
```

**Phase 0 완료 후:** 오케스트레이터는 skill-map.md를 참고하여 후속 Phase 1~N의 worker 호출 시 skills 파라미터를 전달합니다.

### Phase 1~N: 작업 실행

Phase 0 완료 후 계획서의 Phase 순서대로 실행합니다:

**독립 작업 (병렬 실행):**
```
# 단일 메시지에 여러 Task 호출
# skills 파라미터는 skill-map.md 또는 계획서에 태스크별 스킬이 명시된 경우 포함
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: W01, planPath: <planPath>, skills: <스킬명>")
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: W02, planPath: <planPath>")
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: W03, planPath: <planPath>")
```

**종속 작업 (순차 실행):**
```
# 이전 Phase 완료 대기 후
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: W04, planPath: <planPath>")
```

> **skills 파라미터**: Phase 0에서 생성된 skill-map.md의 추천 스킬 또는 계획서에 명시된 스킬을 전달합니다. 명시되지 않은 태스크는 skills 파라미터를 생략하며, worker가 명령어별 기본 스킬 매핑과 키워드 분석으로 자동 결정합니다.

### 명령어별 기본 스킬 매핑

worker가 skills 파라미터 없이 호출될 때 명령어에 따라 자동 로드하는 스킬입니다:

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

**키워드 기반 추가 스킬 로드:**

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

### Explore 서브에이전트 활용 가이드

계획서에서 `서브에이전트: Explore`로 지정된 태스크는 Explore(Haiku) 서브에이전트를 활용하여 대량 읽기 작업을 최적화합니다.

**Explore 에이전트 특성:**
- **읽기 전용**: 파일 수정 불가, 분석/요약만 수행
- **저비용**: Haiku 모델 사용으로 토큰 비용 최소화
- **고속**: 경량 모델로 빠른 응답
- **낮은 컨텍스트 소비**: Worker 대비 컨텍스트 사용량 최소화

**Explore 에이전트 호출 패턴:**
```
Task(subagent_type="explore", prompt="
다음 파일들을 분석하고 각 파일의 주요 기능과 구조를 요약하세요:
- path/to/file1.py
- path/to/file2.py
- path/to/file3.py

출력 형식: 파일별 1-3줄 요약
")
```

**토폴로지 인식 파티셔닝:**

대량 파일 분석 시 파일 크기별로 Explore 에이전트에 분배합니다:

| 파일 크기 | 에이전트당 파일 수 | 예시 |
|----------|------------------|------|
| 소 (< 100줄) | 5-8개 | 설정 파일, 짧은 스크립트 |
| 중 (100-500줄) | 2-3개 | 일반 모듈, 컴포넌트 |
| 대 (> 500줄) | 1개 | 핵심 로직, 대형 클래스 |

**사용 시나리오:**
1. 대량 파일 리뷰/감사: 여러 Explore 에이전트를 병렬로 호출하여 파일 분석
2. 코드베이스 탐색: 디렉토리 구조와 파일 역할 파악
3. 패턴 스캔: 특정 패턴이나 안티패턴 탐지

**Worker에서 Explore 결과 활용:**
```
1. Explore 에이전트로 대량 파일 분석 결과 수집
2. 분석 결과를 기반으로 Worker가 수정 작업 수행
3. 읽기(Explore) → 쓰기(Worker) 파이프라인 구성
```

> **주의**: Explore 에이전트는 파일을 수정할 수 없습니다. 수정이 필요한 태스크에는 반드시 Worker를 사용하세요.

### worker 작업 처리 절차

```
계획서 확인 → 스킬 로드 → 작업 진행 → 실행 내역 작성
```

**1. 계획서에서 자신의 작업 목록 확인:** 프롬프트의 planPath에서 계획서를 읽어 자신의 taskId에 해당하는 태스크 정보(대상 파일, 작업 내용, 종속성 등)를 파악한다.

**2. Skills 디렉터리에서 필요한 스킬을 찾아 로드:** skills 파라미터가 전달된 경우 해당 스킬을, 없으면 명령어별 기본 스킬 매핑과 키워드 분석으로 필요한 스킬을 `.claude/skills/`에서 찾아 로드한다.

**3. 작업 진행:** 계획서의 요구사항에 따라 실제 작업을 수행한다. 사용 가능한 모든 도구를 활용한다.
- `Read`, `Write`, `Edit`: 파일 작업
- `Grep`, `Glob`: 검색
- `Bash`: 명령어 실행
- `Task`: 하위 작업 위임 (필요시)

**4. 작업 실행 내역 작성:** 수행한 작업의 내역을 `<workDir>/work/WXX-<작업명>.md` 파일에 기록하고, 구조화된 3줄 형식으로 결과를 반환한다.

### 작업 내역 저장 위치

`<workDir>/work/WXX-<작업명>.md` (workDir = `.workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>`)

---

## 결과 반환 형식 (필수)

> **절대 준수**: 메인 에이전트에 반환할 때 반드시 아래 3줄 형식만 사용합니다.
> 추가 정보(수행 내용, 결과물, 비고 등)는 절대 포함하지 마세요.
> 상세 내용은 작업 내역 파일(.workflow/)에 기록됩니다.
> 위반 시 메인 컨텍스트 폭증으로 워크플로우 전체 실패 가능.

### 반환 형식

```
상태: 성공 | 부분성공 | 실패
작업 내역: <workDir>/work/WXX-<작업명>.md
변경 파일: N개
```

**금지 항목**: 변경 파일 목록 테이블, "다음 단계" 안내, 작업 요약, 코드 스니펫, 수행 내용 목록 등

## 실패 처리

작업 실패 시에도 동일한 3줄 형식을 사용합니다:

```
상태: 실패
작업 내역: <workDir>/work/WXX-<작업명>.md
변경 파일: 0개
```

실패 상세 내용(원인, 시도한 해결 방법, 권장 조치)은 작업 내역 파일에 기록합니다.

> **status.json 연동**: WORK 실패 시(실패율 50% 초과 등으로 워크플로우 중단) 오케스트레이터가 `status.json`의 `phase`를 `"FAILED"`로 업데이트합니다. Worker 자체는 status.json을 직접 수정하지 않습니다.

## Frontmatter 플래그 설명

### `disable-model-invocation: true`

이 플래그는 Claude가 자동으로 이 스킬을 호출(Skill 도구 사용)하는 것을 방지합니다.

**용도:**
- workflow-work 스킬은 workflow-orchestration이 Task 도구(`subagent_type="worker"`)를 통해 **명시적으로** 호출해야 합니다
- Claude가 대화 맥락을 분석하여 자동으로 workflow-work 스킬을 호출하면 워크플로우 순서가 깨질 수 있습니다
- 이 플래그가 없으면 Claude가 "작업 수행" 관련 키워드를 감지하여 PLAN 단계를 건너뛰고 바로 workflow-work를 실행할 위험이 있습니다

**동작 방식:**
| 설정 | 사용자 `/work` 호출 | Claude 자동 호출 (Skill 도구) | Task 도구 호출 |
|------|---------------------|-------------------------------|---------------|
| `disable-model-invocation: true` (현재) | O | X (차단) | O (정상) |
| 플래그 없음 (기본값) | O | O (자동 가능) | O (정상) |

**다른 워크플로우 스킬과의 비교:**
- workflow-orchestration, workflow-init, workflow-plan, workflow-report 스킬에는 이 플래그가 없음
- workflow-work 스킬만 유일하게 이 플래그를 사용함
- 이유: workflow-work 스킬은 반드시 PLAN 완료 후에만 호출되어야 하므로, 자동 호출을 차단하여 워크플로우 순서를 보장함

**부가 효과:**
- 이 플래그가 설정된 스킬은 Claude의 자동 컨텍스트 로딩에서 제외되어 토큰 소비를 절약합니다

**주의:** 이 플래그를 제거하지 마세요. 워크플로우의 순서 보장에 필수적입니다.

## 연관 스킬

작업 수행 품질 향상을 위해 다음 스킬을 참조할 수 있습니다:

| 스킬 | 용도 | 경로 |
|------|------|------|
| command-verification-before-completion | 작업 완료 전 자동 검증 체크리스트 | `.claude/skills/command-verification-before-completion/SKILL.md` |
| command-code-quality-checker | 린트/타입체크 자동 실행 | `.claude/skills/command-code-quality-checker/SKILL.md` |
| tdd-guard-hook | TDD 원칙 위반 모니터링 (Hook 자동 적용) | `.claude/skills/tdd-guard-hook/SKILL.md` |
| dangerous-command-guard | 위험 명령어 차단 (Hook 자동 적용) | `.claude/skills/dangerous-command-guard/SKILL.md` |
| command-requesting-code-review | 리뷰 전 사전 검증 체크리스트 | `.claude/skills/command-requesting-code-review/SKILL.md` |

## 주의사항

- 할당받은 작업 범위를 벗어나지 않음
- 다른 worker 에이전트의 작업 영역과 충돌하지 않도록 주의
- 대규모 변경 전 현재 상태 확인
- 불확실한 경우 안전한 방향 선택

## Worker 산출물 범위 및 보고서 생성 금지

> **경고**: Worker는 최종 보고서를 절대 생성하지 않습니다. 위반 시 REPORT 단계와 충돌하여 워크플로우 오류가 발생합니다.

**Worker가 생성할 수 있는 산출물:**
- 작업 내역 파일: `work/WXX-*.md` (유일하게 허용되는 산출물)

**Worker가 생성해서는 안 되는 산출물 (명시적 금지 목록):**
- `report.md` (최종 보고서)
- `summary.md`, `result.md` 등 보고서 성격의 문서
- 작업 전체를 요약하는 최종 결과 문서
- 기타 reporter 에이전트(workflow-report)의 역할에 해당하는 모든 종류의 보고서/리포트

**역할 분리 원칙:**
- Worker의 역할: 개별 태스크 실행 및 작업 내역(`work/WXX-*.md`) 기록
- Reporter의 역할: 모든 Worker 작업 내역을 종합하여 최종 보고서(`report.md`) 생성
- 이 역할 경계는 PLAN 단계에서 planner가 태스크를 분배할 때부터 보장됨
