---
name: prompt-engineering-guide
description: "Reference guide for prompt refinement and ambiguity analysis. Provides structured prompt improvement checklists, templates, and Claude Code-specific patterns. Use when analyzing prompt ambiguity, suggesting prompt improvements, or providing prompt writing guidance. Triggers: cc:prompt prompt refinement, 'prompt ambiguity analysis', 'improve prompt quality', 'prompt structure guide', 'prompt template'."
---

# Prompt Engineering Guide

cc:prompt 프롬프트 정제 시 참조하는 가이드 스킬. 프롬프트의 모호성을 분석하고 구조화된 개선을 제안한다.

## 모호성 분석 체크리스트

프롬프트 제출 전 검토해야 할 5대 모호성 유형. 하나라도 해당하면 프롬프트를 개선해야 한다.

| # | 모호성 유형 | 징후 | 개선 질문 예시 |
|---|------------|------|---------------|
| 1 | **대상 불명확** | "사용자", "코드", "API" 등 범위 미정 | "어떤 파일/모듈/레이어를 대상으로 하나요?" |
| 2 | **요구사항 불완전** | 기능 설명은 있지만 경계 조건, 수량, 측정 기준 미정 | "최대/최소 허용 값이 있나요? 어떤 상태가 성공인가요?" |
| 3 | **컨텍스트 부족** | 기존 패턴, 관련 파일, 기술 스택 언급 없음 | "현재 프로젝트에서 유사한 기능은 어디에 구현되어 있나요?" |
| 4 | **범위 미정의** | 여러 해석이 가능한 요청 | "이 작업이 영향을 주는 파일 범위는 어디까지인가요?" |
| 5 | **제약 조건 누락** | "빠르게", "깔끔하게" 같은 형용사형 목표 | "사용할 수 없는 라이브러리나 패턴이 있나요?" |

### 자가 점검 체크리스트

- [ ] **숫자 명확성**: "빠른", "적절한" 대신 구체적 수치 포함
- [ ] **단일 목표**: 하나의 턴에 하나의 작업 (복합 요청 분리)
- [ ] **경계 조건**: 엣지 케이스, 한계값, 예외 상황 정의
- [ ] **긍정 지시**: "~하지 마시오" 대신 "~을 사용하시오"
- [ ] **공유 어휘**: 전문 용어 사용 시 컨텍스트 제공
- [ ] **검증 기준**: 완료 기준이 측정 가능한지 확인
- [ ] **기존 패턴**: 유사한 기존 구현체 파일 참조 포함

### 모호성 적신호

- 동일 요청에서 여러 해석이 가능
- 상충하는 제약 조건 혼재
- "느낌상 맞는" 표현 (측정 불가 성공 기준)
- "전체", "모든", "다" 같은 무제한적 범위 표현

## 프롬프트 구조화 5요소

효과적인 프롬프트의 필수 구성 요소. 각 요소가 누락되면 결과 품질이 저하된다.

| # | 요소 | 설명 | 나쁜 예 | 좋은 예 |
|---|------|------|---------|---------|
| 1 | **명확한 목표** | 동사 포함, 구체적 행동 지시 | "확인해줘" | "validateEmail 함수를 구현하시오" |
| 2 | **구체적 대상** | 파일, 모듈, 함수명 명시 | "코드 고쳐줘" | "`src/auth/session.ts`의 `refreshToken` 함수를 수정하시오" |
| 3 | **제약 조건** | 사용 가능/불가 기술, 패턴 한정 | (없음) | "외부 라이브러리 없이 표준 라이브러리만 사용" |
| 4 | **검증 기준** | 테스트 케이스 또는 성공 조건 | (없음) | "`user@example.com` -> true, `invalid` -> false로 검증" |
| 5 | **참조 컨텍스트** | 배경 정보, 기존 패턴 파일 경로 | (없음) | "`@src/auth/oauth.ts` 패턴을 참고하여 구현" |

### 기본 프롬프트 구조 (4-블록 분리 패턴)

```
## INSTRUCTIONS
[무엇을 해야 하는지 명시적으로 기술]

## CONTEXT
[배경 정보, 관련 파일, 기존 패턴]

## TASK
[구체적 작업 내용, 범위, 제약 조건]

## OUTPUT FORMAT
[기대하는 결과물 형식, 구조, 길이]
```

## 핵심 원칙

### 리터럴 지시 따르기

Claude는 지시를 문자 그대로 따른다. "확인해줘"에는 확인만 하고, "구현해줘"에는 구현한다.

- 모호한 동사("확인해줘", "봐줘") 사용 자제
- "구현하시오", "수정하시오", "실행하시오" 등 명확한 동사 사용
- 원하는 동작을 명시하지 않으면 보수적으로 처리

### 검증 가능한 성공 기준

```
# 낮은 품질
"이메일 검증 함수를 구현해줘"

# 높은 품질
"validateEmail 함수를 구현하시오.
테스트 케이스: user@example.com -> true, invalid -> false, user@.com -> false
구현 후 테스트를 실행하시오."
```

### Few-Shot 예시 활용

| 작업 유형 | 권장 예시 수 |
|----------|------------|
| 포맷 민감 (JSON, 이메일) | 1-2개 |
| 톤 조정 | 1개 |
| 복잡한 분류 | 2-3개 |
| 단순 Q&A | 0개 (제약 조건으로 충분) |

## 상세 참조

- **용도별 프롬프트 템플릿 6종** (기능구현, 버그수정, 리팩토링, 코드리뷰, 연구조사, 아키텍처설계): [references/prompt-templates.md](references/prompt-templates.md)
- **클로드 코드 특화 패턴 4종** (에이전트 지시, 도구 활용 힌트, 컨텍스트 제공, 컨텍스트 창 관리): [references/claude-code-patterns.md](references/claude-code-patterns.md)
