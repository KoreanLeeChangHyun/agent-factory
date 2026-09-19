---
document-type: processed
category: interview
domain: null
name: plugin-document-rules-history
language: ko
provenance:
  source-paths:
  - plugin/.backup/docs/processed/interview-agents-md-compression/SKILL.md
  - plugin/.backup/docs/인터뷰-스킬문서규약.md
  migration-request: run-20260918T153502344625Z-53d84a1e
  authority: 백업 당시 기록입니다. 현재 명세를 대체하거나 새 실행 권한을 부여하지 않습니다.
  renamed-from: docs/processed/interview-plugin-document-backups
  classification-request: run-20260918T154226499325Z-8d8d4959
---

# 플러그인 문서 규칙 인터뷰 이력

## 1. 기록의 범위

- 같은 주제의 백업 요청·명세·작업 기록과 첨부를 모았습니다. 과거 상태·승인·검사 결과는 해당 시점의 기록이며 현재 검증 결과가 아닙니다.
- 현행 기준은 [현재 프로젝트 명세](../../skills/)에서 확인합니다. 원문·식별자·코드·출처는 원래 언어와 바이트를 보존합니다.
- 첨부는 보존용 원문입니다. 이 문서는 원문을 탐색하기 위한 가공 기록이며, 백업의 오래된 규칙을 활성화하지 않습니다.

## 2. 원본과 이관 위치

| 이전 경로 | 보존 자료 | SHA-256 |
| --- | --- | --- |
| `plugin/.backup/docs/processed/interview-agents-md-compression/SKILL.md` | [SKILL.md](assets/docs/processed/interview-agents-md-compression/SKILL.md) | `a46ebf27521d9f3f7848d5f479a3cedde7c71737d78a631f3600a71b191b0043` |
| `plugin/.backup/docs/인터뷰-스킬문서규약.md` | [인터뷰-스킬문서규약.md](assets/docs/인터뷰-스킬문서규약.md) | `a06b879b8d9dc7c6044d864f149e381599d58c0050b6c74f688adf2c006c0e39` |

## 3. 본문 기록

### 3.1. SKILL

- 원문: [SKILL.md](assets/docs/processed/interview-agents-md-compression/SKILL.md)

> 
> # AGENTS.md 압축 인터뷰 기록
> 
> ## 성격과 출처
> 
> - 이 문서는 완료된 인터뷰를 정리한 비권위적 Processed 작업 지식입니다. 실행 지침이나 Specification으로 승격된 문서가 아닙니다.
> - 질문·선택지·권고는 아래 Main 실행 기록에서 옮겼습니다. 표제는 한국어로 정리했으며, Human의 선택은 Main의 위임 요청에 근거합니다.
> - 첫 질문 출처: `/home/deus/.agent-factory/projects/project-a27653322490497fa8b2009fc4f28352/agents/main-cbd4f7f1-f1cf-4378-903f-a906a154a0c6/runs/run-20260917T122829141384Z-044c8184/result.md`.
> - 둘째 질문 출처: `/home/deus/.agent-factory/projects/project-a27653322490497fa8b2009fc4f28352/agents/main-cbd4f7f1-f1cf-4378-903f-a906a154a0c6/runs/run-20260917T123113678366Z-de0b020b/result.md`.
> - 선택 및 실행 범위 출처: `/home/deus/.agent-factory/projects/project-a27653322490497fa8b2009fc4f28352/agents/work-agents-md-compress-890618c4/runs/run-20260917T123633040236Z-261d8a48/request.md`.
> - Main이 참고한 [공식 OpenAI AGENTS.md 안내](https://learn.chatgpt.com/docs/agent-configuration/agents-md)의 요지는 루트에 저장소 공통 기대사항을 두고, 특수 규칙은 해당 코드 가까이에 배치하며, 지침을 간결하게 유지하는 것입니다. 이는 Main의 조사 결과를 기록한 것이며 Work의 별도 웹 검증 결과가 아닙니다.
> 
> ## 최초 결정 목록과 질문 수
> 
> 1. 루트 `AGENTS.md`를 어느 수준으로 압축할지 결정합니다.
> 2. 결과의 문서 분류와 완료 신호를 결정합니다. 최초 안내는 이를 “압축본을 완료된 Specification으로 승격할 때 사용할 이름·분류와 완료 확인”이라고 표현했습니다.
> 
> - 총 질문 수는 2개였으며 변경되지 않았습니다.
> - 둘째 질문에서는 대상이 Provider 실행 지침이라는 소유권 근거를 반영하여, Specification 승격을 전제하지 않고 분류와 완료 신호를 선택하도록 구체화했습니다.
> 
> ## 질문 1과 결정
> 
> 질문: [1/2] 어느 수준으로 압축할까요?
> 
> | 선택지 | 결정 | 장점 | 단점 |
> |---|---|---|---|
> | 1 | 의미 보존형: 저장소 고유 의무와 경계를 모두 유지하고 중복·설명·링크 목록만 축약 | 기존 계약 손실 위험이 가장 낮음 | 길이 감소 폭은 중간 수준 |
> | 2 | 핵심 규칙형: 일상 작업에 필요한 구조·소유권·변경 규칙만 남김 | 가장 짧고 읽기 쉬움 | 드물게 필요한 경로·예외를 Skill에서 다시 찾아야 함 |
> | 3 | 최소 인덱스형: “관련 Skill을 읽고 따르라”는 안내와 핵심 정체성만 남김 | 토큰 사용량이 가장 적음 | 중요한 저장소 경계가 즉시 보이지 않아 누락 위험이 커짐 |
> 
> 권고: **Option 1**을 권장합니다. 공식 문서의 간결성 원칙을 따르면서도 이 저장소의 중요한 소유권·저장 위치·기여 경계를 보존할 수 있습니다.
> 
> 직전 결정:
> 
> - 없음
> 
> - Human 선택: **Option 2 — 핵심 규칙형**입니다.
> - 권고는 Option 1이었지만 실제 결정은 Option 2입니다. 권고를 Human의 승인으로 취급하지 않습니다.
> 
> ## 질문 2와 결정
> 
> 질문: [2/2] 결과의 문서 분류와 완료 신호를 어떻게 정할까요?
> 
> | 선택지 | 결정 | 장점 | 단점 |
> |---|---|---|---|
> | 1 | 압축된 `AGENTS.md` 자체를 최종 Provider 지침으로 사용하고, 수정 및 자체 점검 완료를 워크플로 완료 신호로 간주 | 기존 소유권과 파일 역할을 보존하며 별도 중복 문서를 만들지 않음 | 별도의 Specification 표시 문서는 없음 |
> | 2 | `AGENTS.md`를 수정하고 Client `rule-agent-factory-plugin-guidance` Specification도 함께 생성한 뒤 완료 처리 | 별도 규칙 문서가 명시적으로 남음 | Provider 지침을 Client Specification으로 중복하여 저장소 계약과 충돌할 수 있음 |
> | 3 | 우선 Processed 인터뷰 기록과 압축 초안만 만들고, 완료 및 승격은 이후 확인으로 보류 | 검토 후 의미를 조정하기 쉬움 | 이번 요청에서 `AGENTS.md` 최종 수정이 완료되지 않음 |
> 
> 권고: **Option 1**을 권장합니다. 대상이 이미 Provider 지침이므로 해당 파일을 간결하게 유지하는 것이 가장 정확합니다.
> 
> 직전 결정:
> 
> - 핵심 규칙형으로 압축하여 일상 작업에 필요한 구조·소유권·변경 규칙만 유지
> 
> - Human 선택: **Option 1**입니다.
> - 질문의 “자체 점검”은 위임 요청에서 **Main의 점검**으로 명시되었습니다. Work의 자체 검증이나 테스트 실행을 허용하지 않습니다.
> 
> ## 전체 결정 이력과 최종 요약
> 
> 1. Human은 첫 질문에서 Option 2를 선택하셨습니다. 일상 작업에 필요한 구조·소유권·저장 위치·기여 규칙을 유지하고 상세 참조 목록과 불필요한 표현을 제거합니다.
> 2. Human은 둘째 질문에서 Option 1을 선택하셨습니다. 압축된 `AGENTS.md` 자체가 최종 Provider 지침이며, 수정과 Main의 점검 완료가 워크플로 완료 신호입니다. 별도 Client Specification을 만들지 않습니다.
> 
> - 유지 대상은 공개 Skill `agent`·`convention`의 정체성, 소유 Skill과 참조의 사전 열람, `.codex/` 복제 금지, 체크아웃 외부 런타임, MCP 도메인 분리, 영어 Provider 지침, 공유 체크아웃과 무관한 작업 보존, Work의 자체 검증·커밋 금지, `tests/` 구성 및 development 소유 릴리스 규칙입니다.
> - 완료된 인터뷰의 기록 의무에 따라 이 Processed 문서를 작성합니다. 이 문서의 작성이나 인터뷰 완료는 Specification 승격 또는 점검 통과를 뜻하지 않습니다.
> - 제공된 기록에 추가 Human 정정이나 미해결 결정은 없습니다. Main의 점검은 Work 결과 이후에 수행할 절차이며, 이 기록은 그 완료를 주장하지 않습니다.
### 3.2. 인터뷰-스킬문서규약

- 원문: [인터뷰-스킬문서규약.md](assets/docs/인터뷰-스킬문서규약.md)

> # 스킬 문서 규약 인터뷰 기록
> 
> ## 문서 상태
> 
> | 항목 | 값 |
> |---|---|
> | 문서 유형 | 가공 문서(Processed) |
> | 권위 | 비권위적 인터뷰 기록 |
> | 언어 | 한국어 |
> | 목적 | 스킬 문서 전수 조사 과정에서 제기된 문서 유형·명명·표현 규칙의 결정 과정 보존 |
> 
> 이 기록은 인터뷰에서 확인된 Human의 결정을 정리하지만, 그 자체가 명세 문서는
> 아닙니다. 확정된 규칙은 Convention의 영어 Skill 참조 문서에 반영됩니다.
> 
> ## 최초 결정 목록과 문항 수 변경
> 
> 인터뷰 전 최초 목록은 스킬 경로 발견성, 명세 이름, 문서 유형 경계, 역할 프롬프트의
> 참조 경로라는 네 가지 감사 쟁점으로 시작했습니다. 대화에서 새로운 쟁점이 드러나거나
> 기존 쟁점이 합쳐지고 감사 가설이 철회되면서 전체 문항 수가 다음과 같이 바뀌었습니다.
> 
> | 변경 | 이유 |
> |---|---|
> | 4문항 | 최초 감사 쟁점 목록 |
> | 3문항 | 격리 런타임 검사에서 `.agents/skills`와 `.codex/skills`가 모두 발견되어 경로 오류 가설 철회 |
> | 4문항 | 기획 의도와 기술 설계의 분리 여부 추가 |
> | 5문항 | `plan-*`와 설계 분류의 관계를 별도 쟁점으로 분리 |
> | 4문항 | 기획·설계 분류와 문서 결합 여부를 하나의 결정으로 통합 |
> | 6문항 | 가공 문서 형식, AI/Human 명세 표현 및 HTML 구성 쟁점 구체화 |
> | 5문항 | `references/*`가 소유 Skill 기준의 유효한 참조임을 확인하여 역할 프롬프트 경로 문항 철회 |
> 
> 철회된 두 감사 가설은 결정 사항이 아닙니다. `.codex/skills`는 현재 런타임에서
> 프로젝트 Skill 경로로 발견되며, 역할 프롬프트의 `references/*`는 Convention을
> 적용한 뒤 `skills/convention/references/`를 기준으로 해석됩니다.
> 
> ## 질문별 기록
> 
> 아래 표는 대화 중 표현이 수정된 질문을 최종 결정 단위로 정규화한 기록입니다.
> 
> ### 질문 1 — 명세의 이름과 분류
> 
> | 선택지 | 결정 | 장점 | 단점 |
> |---|---|---|---|
> | 1 | `<category>-<name>`을 사용하고 정보·규칙·설계를 분류 | 이름만으로 용도 식별 가능 | 분류 경계를 유지해야 함 |
> | 2 | 모든 명세에 공통 `spec-*` 사용 | 명세임이 단순하게 드러남 | 정보·규칙·설계 목적이 이름에서 사라짐 |
> | 3 | 자유 이름 사용 | 제약이 적음 | 발견성과 일관성이 낮음 |
> 
> 추천: 1번.
> 
> Human 결정: 1번. `info-*`는 Agent 참고 정보, `rule-*`는 Agent가 지켜야 하는
> 규칙, 설계 명세는 후속 결정에 따라 `design-*`를 사용합니다.
> 
> ### 질문 2 — 기획 의도와 기술 설계의 관계
> 
> | 선택지 | 결정 | 장점 | 단점 |
> |---|---|---|---|
> | 1 | `plan-*`과 `design-*`로 분리 | 책임 구분이 선명함 | 함께 변하는 내용의 동기화 비용 발생 |
> | 2 | 하나의 `design-*`에 기획 의도와 기술 설계를 통합 | 맥락과 구현 판단을 한곳에서 유지 | 큰 문서는 구조화가 필요함 |
> | 3 | `plan-*`을 상위 문서로 두고 설계를 연결 | 계층이 명확함 | 문서와 링크 관리가 복잡함 |
> 
> 추천: 웹 조사 결과를 근거로 2번. GitLab Design Documents, Kubernetes KEP,
> Rust RFC처럼 동기·목표와 기술 결정을 한 문서에서 함께 관리하는 사례를 참고했습니다.
> 
> Human 결정: 2번. 별도 `plan-*` 없이 `design-*` 하나에 기획 의도와 기술 설계를
> 함께 둡니다.
> 
> ### 질문 3 — 가공 문서와 명세 문서의 경계
> 
> | 선택지 | 결정 | 장점 | 단점 |
> |---|---|---|---|
> | 1 | AI가 생성한 모든 문서를 명세 및 Skill로 취급 | 저장 규칙이 단순함 | 비권위적 초안까지 규칙으로 오인됨 |
> | 2 | 파일 형식에 따라 가공·명세를 구분 | 기계적 분류 가능 | 형식이 의미와 권위를 결정하는 오류 발생 |
> | 3 | AI 생성물은 가공 문서가 기본이고 Human이 명확히 요청한 명세만 Skill로 생성 | 권위 경계가 명확함 | 명세 요청 여부를 보존해야 함 |
> 
> 추천: 3번.
> 
> Human 결정: 3번. 가공 문서는 Markdown이 기본이며 필요하면 CSV나 JSON을
> 사용합니다. 명세 문서만 Project Skill로 만듭니다.
> 
> ### 질문 4 — AI용 명세와 사람용 명세의 동기화
> 
> | 선택지 | 결정 | 장점 | 단점 |
> |---|---|---|---|
> | 1 | 영어 Skill을 원본으로 삼아 HTML로 단방향 생성 | 충돌이 단순함 | HTML에서 한 의미 변경을 잃을 수 있음 |
> | 2 | 사람용 HTML을 원본으로 삼아 Skill로 단방향 생성 | Human 편집 중심 | Agent 규칙 편집의 반영이 지연될 수 있음 |
> | 3 | 동일 ID·버전으로 양방향 동기화하고 의미 충돌은 Human에게 반환 | 두 표현의 의미를 동등하게 보존 | 충돌 판정과 조정 절차가 필요함 |
> 
> 추천: 3번.
> 
> Human 결정: 3번. AI용 Skill은 영어, 사람용 HTML은 Human의 언어로 작성하며
> 한국인에게는 한국어를 사용합니다. 사람용 HTML에는 텍스트 하이라이팅과 이해를
> 돕는 그림·도형을 추가합니다. 표현 전용 요소는 Skill 의미로 역수입하지 않습니다.
> 
> ### 질문 5 — 사람용 HTML의 파일 구성
> 
> | 선택지 | 결정 | 장점 | 단점 |
> |---|---|---|---|
> | 1 | CSS와 JavaScript를 포함한 단일 HTML | 전달·열람·동기화가 간단함 | 지나치게 커지면 유지보수가 어려움 |
> | 2 | HTML·CSS·JavaScript를 항상 분리 | 코드 재사용과 관리가 쉬움 | 하나의 명세가 여러 파일로 분산됨 |
> | 3 | 단일 HTML을 기본으로 하되 정해진 임계값에서 자동 분리 | 기본 휴대성과 확장성을 절충 | 보편적인 임계값을 추가로 정의해야 함 |
> 
> 추천: 1번.
> 
> Human 결정: 1번. 단일 HTML을 기본으로 하고, 문서가 너무 커져 사용성이나
> 유지보수성이 실제로 나빠지는 경우에는 지원 파일 또는 하위 문서로 분리합니다.
> 
> ## 전체 결정 사항
> 
> - Project Skill은 `<category>-<name>` 형식을 사용합니다.
> - `info-*`는 Agent 참고 정보, `rule-*`는 Agent 준수 규칙입니다.
> - `design-*`는 기획 의도와 기술 설계를 한 문서에서 함께 다룹니다. 별도
>   `plan-*` 또는 설계용 `spec-*` 분류는 사용하지 않습니다.
> - AI가 생성하는 문서는 가공 문서가 기본입니다. 가공 문서는 Markdown을 기본으로
>   하고 데이터 형태에 따라 CSV 또는 JSON을 사용할 수 있습니다.
> - Human이 명세 생성을 명확히 요청한 경우에만 명세 문서로 분류하며, 명세 문서만
>   Project Skill이 됩니다.
> - 하나의 명세는 동일한 ID와 버전을 공유하는 영어 AI용 Skill과 Human 언어의
>   사람용 HTML로 표현합니다.
> - 두 표현은 의미 변경을 양방향으로 동기화합니다. 의미 충돌은 자동으로 선택하거나
>   병합하지 않고 Human에게 반환합니다.
> - 사람용 HTML에는 강조와 이해하기 쉬운 그림·도형을 추가할 수 있습니다. 이러한
>   표현 전용 변경은 AI용 Skill의 의미 규칙이 아닙니다.
> - 사람용 명세는 CSS와 JavaScript를 내장한 단일 HTML이 기본입니다. 파일 크기가
>   사용성이나 유지보수성을 실제로 해칠 정도가 되면 관련 자산이나 하위 문서를
>   분리합니다.
> 
> ## 미해결 사항
> 
> - 최초 인터뷰 종료 시점에는 HTML 분리 임계값, 동기화 도구, 메타데이터 및 충돌
>   UI가 미해결이었습니다. 아래 후속 인터뷰에서 모두 결정했습니다.
> 
> ## 참고 근거
> 
> - [GitLab Architecture Design Workflow](https://handbook.gitlab.com/handbook/engineering/architecture/workflow/)
> - [GitLab Design Documents](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/)
> - [Kubernetes Enhancement Proposal Template](https://github.com/kubernetes/enhancements/blob/master/keps/NNNN-kep-template/README.md)
> - [Rust RFC Template](https://github.com/rust-lang/rfcs/blob/master/0000-template.md)
> - [Microsoft Engineering Playbook — Design Reviews](https://microsoft.github.io/code-with-engineering-playbook/design/design-reviews/)
> 
> ## 후속 인터뷰: HTML 분리와 양방향 동기화
> 
> ### 문항 수 변경
> 
> | 변경 | 이유 |
> |---|---|
> | 3문항 | 최초 목록: 동기화 도구, 메타데이터, 충돌 UI |
> | 4문항 | 3000줄의 적용 방식이 다시 결정 사항이 됨 |
> | 5문항 | 수정 날짜의 판정 역할과 충돌 UI를 분리 |
> | 6문항 | 영어 Skill과 한국어 HTML의 의미 정합성 방식 추가 |
> 
> ### 질문 1 — 3000줄 기준
> 
> | 선택지 | 결정 | 장점 | 단점 |
> |---|---|---|---|
> | 1 | 3000줄 초과 시 반드시 분리 | 자동 판정이 명확함 | 인라인 SVG·데이터로 불필요하게 분리될 수 있음 |
> | 2 | 비압축 원본 3000줄부터 분리를 검토하고 DOM·파일 크기·구성요소 독립성을 함께 평가 | 휴대성과 유지보수성을 함께 고려 | 정성 판단이 일부 필요함 |
> | 3 | 줄 수를 폐기하고 DOM·파일 크기·복잡도만 평가 | 브라우저 동작과 직접 관련된 지표 사용 | 빠르고 일관된 검토 기준이 사라짐 |
> 
> 추천: 2번. 공식 자료에는 HTML 3000줄 표준이 없으며, 줄 수는 검토 기준으로만
> 사용하는 편이 타당합니다.
> 
> Human 결정: 2번. AI가 읽고 쓰기 쉬운지를 핵심 판단 기준으로 추가했습니다.
> 
> ### 질문 2 — 동기화 도구 소유권
> 
> Human이 정형 질문 전에 직접 결정하여 선택지와 추천은 제시하지 않았습니다.
> 
> Human 결정: MCP 서버가 양방향 동기화 도구를 제공합니다. 플러그인은 자체
> 동기화 엔진을 두지 않고, Human 요청을 받은 Agent가 두 문서를 함께 변경합니다.
> 
> ### 질문 3 — 동기화 메타데이터 위치
> 
> | 선택지 | 결정 | 장점 | 단점 |
> |---|---|---|---|
> | 1 | Skill frontmatter와 HTML 내부에 동일한 최소 메타데이터 내장 | 파일만 읽어도 AI가 관계와 상태를 파악 가능 | 양쪽 메타데이터도 동기화해야 함 |
> | 2 | 별도 `specification.json` 사용 | 구조화된 메타데이터 원본 유지 | 추가 파일로 자기완결성이 낮아짐 |
> | 3 | MCP 서버에만 저장 | 로컬 파일이 간결함 | MCP 없이 관계와 버전을 판별하기 어려움 |
> 
> 추천: 1번.
> 
> Human 결정: 1번. 두 표현에 Specification ID·버전, 표현 유형, 언어, 상대 표현,
> 의미 리비전을 내장합니다. 후속 결정으로 공통 기준 리비전과 수정 시각도 추가했습니다.
> 
> ### 질문 4 — 수정 날짜의 역할
> 
> | 선택지 | 결정 | 장점 | 단점 |
> |---|---|---|---|
> | 1 | 가장 최근 수정 표현이 항상 승리 | 단순함 | 늦은 사소한 편집이 중요한 변경을 덮어쓸 수 있음 |
> | 2 | 날짜는 순서 확인에 쓰고 공통 기준 이후 양쪽 의미가 다르면 Human에게 결정 요청 | 변경 유실 방지 | 공통 기준 리비전이 추가로 필요함 |
> | 3 | 날짜를 판정에서 제외하고 의미 리비전만 비교 | 시계 오차의 영향을 받지 않음 | Human이 변경 시점을 확인하기 어려움 |
> 
> 추천: 2번.
> 
> Human 결정: 2번. 정상 변경은 두 표현을 함께 수정하며, 양쪽 성공 후에만 새 공통
> 리비전을 확정합니다. `modified-at`은 의미 권위가 아니라 변경 순서의 증거입니다.
> 
> ### 질문 5 — 의미 충돌 UI
> 
> | 선택지 | 결정 | 장점 | 단점 |
> |---|---|---|---|
> | 1 | MCP가 구조화된 충돌을 반환하고 Agent가 현재 대화의 Interview에서 질문 | 별도 UI 없이 작업 흐름 유지 | 큰 충돌은 대화 비교가 어려움 |
> | 2 | MCP Workspace 전용 비교·해결 UI | 대규모 비교에 유리 | 별도 UI와 상태 관리 필요 |
> | 3 | HTML 충돌 보고서에서 Human이 결정 | 긴 변경을 시각적으로 검토 가능 | 작은 충돌에도 문서를 열어야 함 |
> 
> 추천: 1번. 큰 충돌에는 가공 HTML 비교 보고서를 보조 자료로 사용할 수 있습니다.
> 
> Human 결정: 1번. Human 결정 전에는 어느 표현도 덮어쓰지 않습니다.
> 
> ### 질문 6 — 영문 Skill과 한국어 HTML의 의미 정합성
> 
> | 선택지 | 결정 | 장점 | 단점 |
> |---|---|---|---|
> | 1 | MCP는 파일·버전·트랜잭션만 관리하고 Agent가 `clause-id` 기준으로 두 언어를 수정·검토 | MCP 의미 모델 없이 양방향 동기화 유지 | 번역 정합성이 Agent 판단에 의존 |
> | 2 | MCP가 언어 중립 의미 모델을 관리 | 의미를 구조적으로 추적 | MCP 책임과 구현 증가 |
> | 3 | 영어 Skill을 원본으로 한국어 HTML을 단방향 번역 | 구조가 단순함 | 양방향 동기화를 포기해야 함 |
> 
> 추천: 최초에는 2번을 제안했으나, MCP가 의미 모델을 소유하지 않는 방향을 반영해
> 1번으로 수정했습니다.
> 
> Human 결정: 1번. 별도 언어 중립 모델이나 세 번째 명세 문서를 만들지 않습니다.
> Agent가 공통 `clause-id`를 사용해 두 언어의 의미를 맞춥니다.
> 
> ## 후속 인터뷰 전체 결정 사항
> 
> - 비압축 HTML 3000줄은 강제 분리가 아니라 검토 시작 기준입니다.
> - 분리 판단은 AI의 읽기·쓰기 용이성, DOM 크기, 바이트 크기, 구성요소 독립성을
>   함께 평가합니다.
> - MCP 서버가 동기화 도구를 제공하고 플러그인은 중복 엔진을 구현하지 않습니다.
> - 정상 수정은 Skill과 HTML을 함께 갱신하고, 두 변경이 모두 성공해야 완료됩니다.
> - 메타데이터는 두 표현에 내장하며 `specification-id`, `specification-version`,
>   `projection`, `language`, `counterpart`, `semantic-revision`,
>   `sync-base-revision`, `modified-at`을 포함합니다.
> - `modified-at`은 변경 순서를 나타낼 뿐 최신 문서에 의미 권위를 부여하지 않습니다.
> - 의미 충돌은 Agent가 현재 대화의 Interview에서 Human에게 결정받습니다.
> - MCP는 언어 모델이나 언어 중립 의미 모델을 제공하지 않습니다. Agent가 안정적인
>   `clause-id`를 기준으로 영어 Skill과 Human 언어 HTML의 의미를 맞춥니다.
> 
> ## 최종 미해결 사항
> 
> Human이 결정해야 하는 항목은 남아 있지 않습니다. MCP 도구의 구체적인 API와
> 저장 구현은 MCP 애플리케이션이 소유하는 후속 구현 사항입니다.
> 
> ## Provider Convention 반영
> 
> 이 저장소는 Client가 아니라 Agent Factory Plugin Provider입니다. 따라서 이
> 인터뷰에서 확정한 규약은 별도 Project Skill이나 Human HTML을 이 저장소에 만들지
> 않고 Provider의 `convention` Skill 참조 문서에 반영했습니다. 해당 Convention이
> Client 프로젝트에서 명세를 생성할 때 영문 Project Skill과 Human 언어 HTML을
> 만들도록 지시합니다. 이 인터뷰 기록은 결정 근거인 가공 문서로 유지합니다.
> 
> Provider에는 활성 원본 문서 경로를 두지 않습니다. Provider의 가공 문서는 Git에서
> 제외된 `docs/`에 두고, Provider 명세는 `skills/`의 유지되는 Skill 패키지에만
> 둡니다. 원본·가공·명세 전체 규칙은 Convention의 `references/documents.md`가
> 소유합니다.
> 
> ## 용어 정리 인터뷰
> 
> 질문은 기획 의도와 기술 설계를 함께 담는 `design-*`의 이름을 정하는 한
> 문항이었습니다. `design-*`, `solution-*`, `architecture-*`를 비교했고
> `design-*` 유지가 추천이었으나, Human은 시각·인터페이스 규칙 문서의 이름을
> `design.md`에서 `theme.md`로 바꾸는 방식으로 용어 충돌을 해결했습니다.
> 
> - `design-*`: Client의 기획 의도·제품·기술 설계 명세
> - `theme.md`: Provider Convention의 시각 테마·인터페이스·표현 규칙
> 
> ### 후속 조사 근거
> 
> - [ESLint `max-lines`](https://eslint.org/docs/latest/rules/max-lines)
> - [Google HTML/CSS Style Guide](https://google.github.io/styleguide/htmlcssguide.html)
> - [Chrome Lighthouse DOM size](https://developer.chrome.com/docs/lighthouse/performance/dom-size)
> - [web.dev Performance Budget](https://web.dev/articles/your-first-performance-budget)