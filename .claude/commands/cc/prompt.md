---
description: "자유 대화형 프롬프트 공동 작성, 자유 질문, 간단 조사, 수정 모드 포함. 대화를 통해 prompt를 점진적으로 작성/개선하거나, 워크플로우 없이 즉시 Q&A/조사/코드수정을 처리합니다. Use when: 프롬프트 작성, 프롬프트 개선, 요청문 구조화, 지시문 작성, 간단한 질문, 빠른 코드베이스 조사, 단순 코드 수정 / Do not use when: 복잡한 구현, 체계적 리뷰, 심층 조사가 목적일 때 (cc:implement, cc:review, cc:research 사용)"
argument-hint: "[-p|-q|-r|-i] (옵션 없으면 선택지 제공)"
skills:
  - research-prompt-engineering
---

# Prompt (자유 대화형 프롬프트 공동 작성)

`.prompt/prompt.txt`를 사용자와의 자유 대화를 통해 점진적으로 작성하거나 개선합니다. 워크플로우(FSM/가드/서브에이전트)와 무관한 독립 명령어입니다.

> **스킬 참조**: 이 명령어는 `research-prompt-engineering` 스킬을 사용합니다. 실행 시작 전 `.claude/skills/research-prompt-engineering/SKILL.md`를 Read로 로드하고, 필요 시 하위 references도 참조합니다.

## 실행 흐름

### Step 0. 모드 선택 (인자 기반)

`$ARGUMENTS`에서 옵션 플래그를 파싱하여 모드를 결정합니다. AskUserQuestion으로 모드를 묻지 않습니다.

| 옵션 | 모드 | 설명 |
|------|------|------|
| `-p` | 프롬프트 작성 | prompt.txt를 대화로 작성/개선합니다 |
| `-q` | 자유 질문 | 워크플로우 없이 즉시 Q&A 응답 |
| `-r` | 간단 조사 | 웹검색/코드탐색 결과를 즉시 제공 |
| `-i` | 간단 구현/수정 | 간단한 코드 수정을 즉시 처리 |

**라우팅 규칙:**

1. `$ARGUMENTS`가 비어있거나 옵션 플래그(`-p`, `-q`, `-r`, `-i`)가 없는 경우 → AskUserQuestion으로 모드 선택지를 제시:

```
AskUserQuestion(
  questions: [{
    question: "어떤 작업을 진행할까요?",
    header: "cc:prompt 모드 선택",
    options: [
      { label: "-p 프롬프트 작성", description: "prompt.txt를 대화로 작성/개선합니다" },
      { label: "-q 자유 질문", description: "워크플로우 없이 즉시 Q&A 응답" },
      { label: "-r 간단 조사", description: "웹검색/코드탐색 결과를 즉시 제공" },
      { label: "-i 간단 구현/수정", description: "간단한 코드 수정을 즉시 처리" }
    ],
    multiSelect: false
  }]
)
```

2. `-p` → Step 1로 진행 (프롬프트 공동 작성 흐름)
3. `-q` → Step Q로 분기. 플래그 뒤에 텍스트가 있으면 즉시 질문으로 사용
4. `-r` → Step R로 분기. 플래그 뒤에 텍스트가 있으면 즉시 조사 주제로 사용
5. `-i` → Step M으로 분기. 플래그 뒤에 텍스트가 있으면 즉시 수정 요청으로 사용

> **인라인 텍스트 예시**: `/cc:prompt -q JWT 토큰 갱신 방식이 뭐야?` → 자유 질문 모드로 즉시 진입하여 해당 질문에 답변. `/cc:prompt -i src/auth.ts의 오타 수정` → 수정 모드로 즉시 진입하여 해당 수정 처리.

---

### Step Q. 자유 질문 모드

워크플로우(FSM/가드/서브에이전트) 없이 즉시 질문에 답변합니다.

#### Q-1. prompt.txt 참조 (있으면)

Read 도구로 `.prompt/prompt.txt`를 읽습니다. 파일이 존재하고 내용이 있으면 질문 답변의 컨텍스트로 활용합니다. 파일이 없거나 비어있으면 이 단계를 건너뜁니다.

#### Q-2. 즉시 Q&A 응답

사용자의 질문(`$ARGUMENTS`에서 `-q` 플래그 뒤 텍스트 또는 이후 수신한 질문)에 대해 즉시 답변합니다. `-q` 뒤에 텍스트가 없으면 AskUserQuestion으로 질문을 수신합니다. 필요 시 Glob, Grep, Read로 코드베이스를 탐색하거나 WebSearch, WebFetch로 웹 정보를 조회하여 정확한 답변을 제공합니다.

#### Q-3. 대화 루프

```
AskUserQuestion(
  questions: [{
    question: "추가로 궁금한 점이 있으신가요?",
    header: "자유 질문 모드",
    options: [
      { label: "추가 질문", description: "다른 질문을 입력합니다" },
      { label: "종료", description: "질문을 마칩니다" }
    ],
    multiSelect: false
  }]
)
```

- **"추가 질문"** 선택 또는 자유 텍스트 입력 시 → Q-2로 돌아가 답변
- **"종료"** 선택 시 → 완료 메시지 출력 후 종료

#### Q-4. 종료

```
자유 질문 모드를 종료합니다.
```

워크플로우 연결 없이 종료합니다 (FSM 상태 전이, 배너 출력 없음).

**사용 가능 도구**: Read, Glob, Grep, WebSearch, WebFetch, AskUserQuestion

> **Bash 도구 호출 금지**: 가드 스크립트 비간섭을 보장합니다.

---

### Step R. 간단 조사 모드

워크플로우 없이 즉시 조사 결과를 제공합니다. cc:research 워크플로우와 달리 체계적 보고서를 생성하지 않고 즉시 결과를 출력합니다.

#### R-1. 조사 주제 확인

`$ARGUMENTS`에서 `-r` 플래그 뒤에 텍스트가 있으면 즉시 조사 주제로 사용하고 R-2로 진행합니다. 텍스트가 없으면 AskUserQuestion으로 주제를 수신합니다:

```
AskUserQuestion(
  questions: [{
    question: "조사할 주제나 키워드를 알려주세요.",
    header: "간단 조사 모드",
    options: [
      { label: "웹 조사", description: "웹검색으로 최신 정보를 조사합니다" },
      { label: "코드베이스 조사", description: "프로젝트 내 코드를 탐색합니다" }
    ],
    multiSelect: false
  }]
)
```

사용자가 입력한 주제/키워드를 조사 대상으로 확정합니다.

#### R-2. 자율 탐색

입력된 주제에 따라 자율적으로 탐색을 수행합니다:

- **웹 조사**: WebSearch, WebFetch로 최신 정보, 공식 문서, 레퍼런스를 검색
- **코드베이스 탐색**: Grep, Glob, Read로 프로젝트 내 관련 파일, 함수, 패턴을 탐색

탐색 방향은 주제의 성격에 따라 자율 판단합니다. 사전에 사용자에게 탐색 계획을 묻지 않습니다.

#### R-3. 결과 즉시 출력

탐색 결과를 구조화하여 터미널에 즉시 표시합니다:

```
## 조사 결과: <주제>

### 핵심 발견
- <핵심 내용 1>
- <핵심 내용 2>

### 관련 파일 (코드베이스 탐색 시)
- <파일 경로>: <간략한 설명>

### 참고 링크 (웹 조사 시)
- [<제목>](<URL>)
```

#### R-4. 추가 조사 루프

```
AskUserQuestion(
  questions: [{
    question: "추가로 조사할 내용이 있으신가요?",
    header: "간단 조사 모드",
    options: [
      { label: "추가 조사", description: "다른 주제나 키워드를 조사합니다" },
      { label: "종료", description: "조사를 마칩니다" }
    ],
    multiSelect: false
  }]
)
```

- **"추가 조사"** 선택 시 → R-1로 돌아가 새 주제 수신
- **"종료"** 선택 시 → 완료 메시지 출력 후 종료

#### R-5. 종료

```
간단 조사 모드를 종료합니다.
```

워크플로우 연결 없이 종료합니다 (FSM 상태 전이, 배너 출력 없음).

> **cc:research와의 차이**: 간단 조사는 즉시 결과 제공, 체계적 보고서 미생성. 심층 분석이나 구조화된 보고서가 필요한 경우 cc:research를 사용하세요.

**사용 가능 도구**: Read, Glob, Grep, WebSearch, WebFetch, AskUserQuestion

> **Bash 도구 호출 금지**: 가드 스크립트 비간섭을 보장합니다.

---

### Step M. 간단 구현/수정 모드

간단한 코드 수정을 워크플로우 없이 즉시 처리합니다.

#### M-1. 수정 요청 수신

`$ARGUMENTS`에서 `-i` 플래그 뒤에 텍스트가 있으면 즉시 수정 요청으로 사용하고 M-2로 진행합니다. 텍스트가 없으면 AskUserQuestion으로 수정 내용을 수신합니다:

```
AskUserQuestion(
  questions: [{
    question: "어떤 수정이 필요한가요?",
    header: "간단 구현/수정 모드",
    options: [
      { label: "파일 지정 수정", description: "특정 파일의 코드를 수정합니다" },
      { label: "자유 입력", description: "수정 내용을 자유롭게 입력합니다" }
    ],
    multiSelect: false
  }]
)
```

#### M-2. 복잡도 자동 판단

수정 요청 내용을 분석하여 복잡도를 자동 판단합니다:

| 복잡도 | 기준 | 처리 방향 |
|--------|------|----------|
| **T1 (간단)** | 단일 파일 수정, 함수 내부 수정, 설정값 변경, 오타 수정 | 즉시 수정 실행 |
| **T2 (보통)** | 2-3개 파일 수정, 새 함수/모듈 추가, 인터페이스 변경 | cc:implement 워크플로우 권장 |
| **T3 (복잡)** | 다중 모듈 변경, 아키텍처 영향, 새 시스템/패턴 도입 | cc:implement 워크플로우 권장 |

#### M-3. T1 판정 시: 즉시 수정

1. Read 도구로 대상 파일을 읽어 현재 내용을 확인합니다
2. Edit 또는 Write 도구로 수정을 즉시 적용합니다
3. 변경 내용 요약을 터미널에 출력합니다:

```
## 수정 완료

**파일**: <파일 경로>
**변경 내용**: <변경 사항 요약>
```

#### M-4. T2/T3 판정 시: 워크플로우 권장

복잡도 판정 근거를 표시하고 사용자에게 선택지를 제시합니다:

```
## 복잡도 판정

**판정**: T2 (보통) / T3 (복잡)
**근거**: <판정 근거>

이 수정은 cc:implement 워크플로우를 통한 체계적 계획/실행이 권장됩니다.
```

```
AskUserQuestion(
  questions: [{
    question: "어떻게 진행할까요?",
    header: "수정 방법 선택",
    options: [
      { label: "cc:implement 워크플로우로 진행", description: "체계적인 계획과 품질 검증을 통해 수정합니다" },
      { label: "그래도 즉시 수정", description: "복잡도가 높더라도 지금 바로 수정합니다 (품질 보장 제한)" }
    ],
    multiSelect: false
  }]
)
```

- **"cc:implement 워크플로우로 진행"** 선택 시 → `/cc:implement` 사용 안내 출력 후 종료
- **"그래도 즉시 수정"** 선택 시 → 주의 메시지 출력 후 M-3 절차대로 수정 수행

  ```
  주의: T2/T3 복잡도 작업을 즉시 수정 모드로 처리합니다. 결과 품질이 워크플로우 기반 실행보다 낮을 수 있습니다.
  ```

**사용 가능 도구**: Read, Glob, Grep, Edit, Write, AskUserQuestion

> **Bash 도구 호출 금지**: 가드 스크립트 비간섭을 보장합니다.

---

### Step 1. 초기화

#### 1-1. prompt.txt 읽기

Read 도구로 `.prompt/prompt.txt`를 읽습니다.

- 파일 내용이 있으면 내용을 보존하고 Step 2로 진행합니다.
- 빈 파일이거나 공백만 있는 경우에도 **종료하지 않고** Step 2로 진행합니다.

**파일 경로 자동 인식**: prompt.txt 내용이 파일 경로 패턴(`.workflow/`, `src/`, `.claude/` 등으로 시작하거나 `.md`, `.py`, `.ts`, `.json` 등 확장자로 끝나는 단일 행)인 경우, 해당 파일을 Read 도구로 자동으로 읽어 **참조 컨텍스트**로 활용합니다.

- 파일 경로 행은 prompt.txt의 원본 내용으로 보존합니다 (덮어쓰지 않음)
- 읽어들인 파일 내용은 Step 2에서 현재 상태를 표시할 때 함께 요약하고, Step 3 대화 루프에서 프롬프트 구체화의 기반 컨텍스트로 사용합니다
- 파일이 존재하지 않으면 경고를 출력하고 일반 텍스트로 취급합니다

#### 1-2. .uploads 디렉터리 읽기

`.uploads/` 디렉터리의 존재 여부를 확인하고, 첨부 파일이 있으면 공동 작성 컨텍스트에 포함합니다.

1. Glob 도구로 `.uploads/**/*` 패턴을 검색합니다.
2. 파일이 존재하면 Read 도구로 각 파일을 읽어 컨텍스트에 추가합니다.
3. `.uploads/` 디렉터리가 없거나 비어있으면 이 단계를 무시하고 다음 단계로 진행합니다.

> 읽어들인 `.uploads/` 파일 내용은 이후 대화 방향 결정, 코드베이스 탐색 판단, 프롬프트 구조화 시 추가 컨텍스트로 활용됩니다.

#### 1-3. 스킬 로드

Read 도구로 `.claude/skills/research-prompt-engineering/SKILL.md`를 읽어 모호성 분석 체크리스트, 프롬프트 구조화 5요소, 핵심 원칙을 로드합니다.

prompt.txt 내용이나 `.uploads/` 컨텍스트에서 **용도를 판별**하여 추가 references를 선택적으로 로드합니다:

| 용도 키워드 | 추가 로드 대상 |
|------------|---------------|
| 구현, 기능, 함수, 모듈 | `references/prompt-templates.md` (기능 구현 템플릿) |
| 버그, 오류, 에러, 수정 | `references/prompt-templates.md` (버그 수정 템플릿) |
| 리팩토링, 정리, 분리 | `references/prompt-templates.md` (리팩토링 템플릿) |
| 리뷰, 검토 | `references/prompt-templates.md` (코드 리뷰 템플릿) |
| 조사, 비교, 연구 | `references/prompt-templates.md` (연구 조사 템플릿) |
| 설계, 아키텍처, 시스템 | `references/prompt-templates.md` (아키텍처 설계 템플릿) |
| 에이전트, 서브에이전트, 도구 | `references/claude-code-patterns.md` (Claude Code 특화 패턴) |

> 용도가 불명확하면 `references/prompt-templates.md`와 `references/claude-code-patterns.md`를 모두 로드합니다.

---

### Step 2. 시작 분기

#### prompt.txt가 비어있는 경우

목적 선택지를 AskUserQuestion으로 제시합니다:

```
AskUserQuestion(
  questions: [{
    question: "어떤 목적의 프롬프트를 작성할까요?",
    header: "프롬프트 공동 작성 시작",
    options: [
      { label: "구현", description: "새 기능, 모듈, 함수 구현 요청" },
      { label: "리뷰", description: "코드 리뷰, 품질 검토 요청" },
      { label: "연구", description: "기술 조사, 비교 분석, 자료 수집 요청" },
      { label: "버그수정", description: "버그 원인 파악 및 수정 요청" },
      { label: "리팩토링", description: "코드 구조 개선, 정리, 분리 요청" },
      { label: "아키텍처설계", description: "시스템 설계, 구조 결정 요청" },
      { label: "기타", description: "위 분류에 해당하지 않는 자유 작성" }
    ],
    multiSelect: false
  }]
)
```

**용도→command 매핑**: 선택한 용도에 따라 아래 표를 참조하여 `<command>` 태그 값을 결정합니다.

| 용도 | command 값 |
|------|-----------|
| 구현 | `implement` |
| 리뷰 | `review` |
| 연구 | `research` |
| 버그수정 | `implement` |
| 리팩토링 | `implement` |
| 아키텍처설계 | `implement` |
| 기타 | AI 자동 판별 (대화 내용 분석으로 implement/research/review 중 선택, 애매하면 AskUserQuestion으로 사용자에게 3종 선택지 제시) |

선택 결과를 기반으로 **초기 prompt.txt 초안을 생성**하고 Write 도구로 `.prompt/prompt.txt`에 저장한 뒤 Step 3으로 진행합니다.

**6종 용도별 XML 태그 기반 초안 템플릿**: 선택한 용도에 맞는 필수 4태그 + 용도별 선택 태그 조합으로 초안을 생성합니다. 태그 내부는 TODO 플레이스홀더 대신 **용도별 가이드 문구**를 기재합니다.

**구현 (기능 구현, 모듈 개발)**:
```
<command>implement</command>
<goal>이 프로젝트에서 구현하려는 기능의 최종 목표를 작성하세요 (예: "사용자 인증 토큰 갱신 기능 추가")</goal>
<target>구현 대상 파일과 함수/모듈을 구체적으로 명시하세요 (예: "src/auth/token.ts의 refreshToken() 함수")</target>
<constraints>유지해야 할 기존 인터페이스, 기술 스택 제약, 하위 호환 요건을 기재하세요</constraints>
<criteria>구현 완료를 검증할 수 있는 기준을 작성하세요 (예: "기존 로그인 테스트 통과, 토큰 만료 시 자동 갱신 동작")</criteria>
<approach>구현 방향이나 사용할 패턴을 기재하세요 (예: "JWT 검증 후 silent refresh 방식")</approach>
<scope>구현 범위(포함/제외)를 명시하세요 (예: "토큰 갱신 로직만, UI 변경은 제외")</scope>
```

**리뷰 (코드 리뷰, 품질 검토)**:
```
<command>review</command>
<goal>리뷰를 통해 확인하려는 품질 목표를 작성하세요 (예: "보안 취약점 및 에러 핸들링 검토")</goal>
<target>리뷰 대상 파일과 범위를 명시하세요 (예: "src/api/ 디렉터리의 모든 엔드포인트")</target>
<constraints>리뷰 범위 제한, 기존 패턴 준수 확인 기준을 기재하세요</constraints>
<criteria>리뷰 결과물 형식을 기술하세요 (예: "심각도별 이슈 목록, 라인 번호 포함, 개선 코드 예시")</criteria>
<approach>리뷰 우선순위나 검토 순서를 기재하세요 (예: "보안 취약점 → 성능 → 코드 스타일 순")</approach>
<reference>참고할 코딩 가이드라인이나 체크리스트를 기재하세요</reference>
```

**연구 (기술 조사, 비교 분석)**:
```
<command>research</command>
<goal>조사를 통해 얻으려는 결론을 작성하세요 (예: "Node.js 비동기 HTTP 클라이언트 라이브러리 선택")</goal>
<target>조사 대상 기술/라이브러리/도구를 명시하세요 (예: "axios, got, node-fetch 3가지 비교")</target>
<constraints>조사 시 반드시 포함해야 할 비교 기준을 기재하세요 (예: "번들 크기, TypeScript 지원, 유지보수 현황")</constraints>
<criteria>조사 결과물 형식을 기술하세요 (예: "비교표, 각 항목 장단점, 최종 추천 및 근거")</criteria>
<context>현재 프로젝트 기술 스택이나 제약 사항을 기재하세요 (예: "FastAPI 백엔드, asyncio 사용")</context>
<reference>참고할 공식 문서나 벤치마크 자료를 기재하세요</reference>
```

**버그수정 (버그 원인 파악 및 수정)**:
```
<command>implement</command>
<goal>수정하려는 버그와 기대 동작을 작성하세요 (예: "로그인 후 세션이 유지되지 않는 문제 수정")</goal>
<target>버그가 발생하는 파일과 함수를 명시하세요 (예: "src/auth/session.ts의 validateSession()")</target>
<constraints>수정 시 변경하면 안 되는 부분을 기재하세요 (예: "try-catch 억제 금지, session 초기화 로직 유지")</constraints>
<criteria>수정 완료 기준을 작성하세요 (예: "재현 테스트 케이스 통과, 기존 세션 테스트 회귀 없음")</criteria>
<context>버그 발생 환경, 재현 단계, 관련 에러 메시지를 기재하세요</context>
<approach>수정 방향을 기재하세요 (예: "세션 만료 시간 초기화 시점 확인 및 수정")</approach>
```

**리팩토링 (코드 구조 개선)**:
```
<command>implement</command>
<goal>리팩토링을 통해 달성하려는 코드 품질 목표를 작성하세요 (예: "300줄 함수를 책임별로 분리하여 유지보수성 개선")</goal>
<target>리팩토링 대상 파일과 함수를 명시하세요 (예: "src/order/process.ts의 processOrder() 함수")</target>
<constraints>유지해야 할 공개 인터페이스, 동작 보장 범위를 기재하세요 (예: "함수 시그니처 유지, API 호출 순서 유지")</constraints>
<criteria>리팩토링 완료 기준을 작성하세요 (예: "기존 테스트 전부 통과, 각 분리 메서드 50줄 이하")</criteria>
<scope>리팩토링 대상 범위와 제외 항목을 명시하세요 (예: "processOrder만 대상, 다른 함수 수정 금지")</scope>
```

**아키텍처설계 (시스템 설계, 구조 결정)**:
```
<command>implement</command>
<goal>설계를 통해 달성하려는 시스템 목표를 작성하세요 (예: "일 100만 건 처리, 3초 내 전달 보장 알림 시스템")</goal>
<target>설계 대상 시스템이나 컴포넌트를 명시하세요 (예: "실시간 알림 시스템 아키텍처")</target>
<constraints>기술 스택, 일정, 팀 규모 등 설계 제약을 기재하세요 (예: "기존 AWS 인프라 활용, 6주 구현 일정")</constraints>
<criteria>설계 산출물 형식과 완료 기준을 작성하세요 (예: "아키텍처 다이어그램, 컴포넌트 명세, 마이그레이션 로드맵")</criteria>
<context>현재 시스템 현황, 사용자 규모, 기존 인프라를 기재하세요</context>
<approach>설계 방향을 기재하세요 (예: "메시지 큐 기반 비동기 처리, 채널별 분리")</approach>
<scope>설계 범위(포함/제외)를 명시하세요 (예: "아키텍처 설계만, 구현 코드 제외")</scope>
```

**기타 선택 시 분기 로직**:

"기타"를 선택한 경우, 사용자의 자유 텍스트 입력과 `.prompt/prompt.txt` 기존 내용, `.uploads/` 컨텍스트를 종합 분석하여 command 값을 자동 판별합니다:

1. **자동 판별**: 입력 내용에서 키워드/의도를 분석하여 `implement`, `research`, `review` 중 하나를 결정합니다.
   - 구현/개발/수정/설계/리팩토링 관련 의도 → `implement`
   - 조사/분석/비교/리서치 관련 의도 → `research`
   - 검토/리뷰/감사 관련 의도 → `review`

2. **명확한 경우**: 자동 판별된 command 값을 `<command>` 태그로 초안 최상단에 삽입합니다.

3. **판별이 애매한 경우**: AskUserQuestion으로 3종 선택지를 제시하여 사용자가 직접 선택합니다:

```
AskUserQuestion(
  questions: [{
    question: "어떤 종류의 작업을 진행하실 건가요?",
    header: "후속 커맨드 선택",
    options: [
      { label: "구현/개발/수정", description: "/cc:implement 커맨드를 사용합니다" },
      { label: "조사/분석/리서치", description: "/cc:research 커맨드를 사용합니다" },
      { label: "코드 리뷰/검토", description: "/cc:review 커맨드를 사용합니다" }
    ],
    multiSelect: false
  }]
)
```

4. **선택 결과 반영**: 선택된 값(`implement` / `research` / `review`)을 `<command>` 태그로 초안 최상단에 삽입합니다.

#### prompt.txt에 내용이 있는 경우

현재 내용을 터미널에 표시합니다:

```
## 현재 prompt.txt 내용

<prompt.txt 내용 전체>
```

**파일 경로가 인식된 경우**, 참조 파일의 핵심 내용을 함께 요약합니다:

```
## 참조 파일 요약

파일: <경로>
내용: <파일 핵심 내용 3-5줄 요약>
```

참조 파일의 내용을 기반으로 용도(구현/리뷰/연구 등)를 자동 판별하여 대화를 시작합니다. Step 3으로 진행합니다.

---

### Step 3. 자유 대화 루프

사용자와 자유롭게 대화하면서 prompt.txt를 점진적으로 개선합니다.

#### 매 턴 처리 순서

**1단계 - 사용자 입력 수신:**

```
AskUserQuestion(
  questions: [{
    question: "<현재 prompt 상태를 반영한 자연스러운 안내 문구 + 구체적 제안>",
    header: "프롬프트 공동 작성",
    options: [
      { label: "<Claude가 제안하는 개선 방향 A>", description: "<설명>" },
      { label: "<Claude가 제안하는 개선 방향 B>", description: "<설명>" },
      { label: "완료", description: "현재 상태로 작성을 마칩니다" }
    ],
    multiSelect: false
  }]
)
```

> 선택지는 매 턴마다 현재 prompt 상태에 맞게 동적으로 생성합니다. "완료" 옵션은 항상 마지막에 포함합니다. 사용자가 자유 입력(Other)을 선택하면 자유 텍스트 입력을 받습니다.

**2단계 - prompt.txt 자동 갱신:**

사용자 입력(선택지 선택 또는 자유 텍스트)을 반영하여 Write 도구로 `.prompt/prompt.txt`를 즉시 갱신합니다. 대화 중 어느 시점에 중단하더라도 마지막 갱신 내용이 유지됩니다.

**XML 태그 섹션 매핑 규칙**: prompt.txt에 XML 태그가 존재하는 경우, 사용자 입력 내용을 해당 XML 태그 섹션에 정확히 매핑하여 갱신합니다.

| 사용자 입력 성격 | 매핑 대상 태그 |
|----------------|--------------|
| 목표, 목적, 최종 결과물 관련 | `<goal>` |
| 대상 파일, 모듈, 함수, 컴포넌트 관련 | `<target>` |
| 제약, 유지해야 할 것, 변경하면 안 되는 것 | `<constraints>` |
| 완료 기준, 검증 방법, 테스트 조건 | `<criteria>` |
| 탐색/조사 결과, 배경 정보, 환경 정보 | `<context>` |
| 구현 방향, 접근 방식, 사용할 패턴 | `<approach>` |
| 포함/제외 범위, 경계 조건 | `<scope>` |
| 참고 자료, 비교 대상, 기준 문서 | `<reference>` |
| `<command>` 태그 | **갱신 제외** (보호됨) — 최초 설정값을 대화 전체에서 보존하며, 어떠한 사용자 입력이 있더라도 덮어쓰지 않음 |

> **하이브리드 유지**: 태그 외부에 존재하는 자유 텍스트는 그대로 보존합니다. 사용자 입력이 특정 태그에 명확히 매핑되지 않으면 태그 외부 자연어로 추가합니다.

**3단계 - 내부 모호성 분석 (사용자에게 노출하지 않음):**

로드한 `research-prompt-engineering` 스킬의 모호성 분석 체크리스트 5항목과 자가 점검 체크리스트 7항목을 내부적으로 재평가합니다. 분석 결과는 다음 턴의 **대화 방향 결정**에만 사용합니다. 체크리스트 항목이나 점수를 사용자에게 직접 출력하지 않습니다.

**4단계 - 웹검색/코드탐색 자율 수행:**

대화 맥락에서 코드베이스 탐색이나 웹검색이 도움된다고 판단하면 자율적으로 수행합니다. 수행 여부를 사용자에게 사전에 묻지 않습니다. 수행 결과는 대화 중 자연스럽게 요약하여 prompt 개선에 반영합니다.

| 감지 신호 | 수행 액션 | 사용 도구 |
|----------|----------|----------|
| 함수, 모듈, 파일, 클래스, 컴포넌트, 변수, 메서드 | 코드베이스 탐색 | Grep, Glob, Read |
| API, 프레임워크, 패키지, 버전, 라이브러리, SDK, 외부 서비스 | 웹검색 | WebSearch, WebFetch |
| 양쪽 신호 모두 감지 | 코드베이스 탐색 + 웹검색 모두 수행 | Grep, Glob, Read, WebSearch, WebFetch |

**탐색/검색 결과의 `<context>` 태그 구조적 기록**: 코드베이스 탐색이나 웹검색을 수행한 경우, 탐색 결과의 핵심 정보를 prompt.txt의 `<context>` 태그 내에 항목별로 구조화하여 기록합니다. `<context>` 태그가 아직 없으면 새로 추가하고, 이미 있으면 내용을 보강합니다.

아래 항목 형식을 사용하여 항목별로 분리 기록합니다:

```
<context>
- 탐색 파일: src/auth/token.ts (tokenRefresh 함수 위치), src/auth/session.ts (세션 관리)
- 핵심 패턴: JWT 검증 후 재발급 방식, refreshToken은 HttpOnly 쿠키에 저장
- 관련 함수/모듈: validateToken(), createSession(), SessionStore 클래스
- 외부 참조: RFC 6749 OAuth 2.0 §6 (토큰 갱신), axios 1.6.x 공식 문서
</context>
```

> **항목별 기록 규칙**: 코드베이스 탐색 시 `탐색 파일`, `핵심 패턴`, `관련 함수/모듈`을 기록하고, 웹검색 시 `외부 참조`를 기록합니다. 둘 다 수행한 경우 모든 항목을 기록합니다. 각 항목은 planner가 곧바로 활용할 수 있도록 구체적인 경로명과 이름을 포함합니다.

> `<context>` 기록은 planner 서브에이전트에게 신뢰 가능한 선행 정보로 전달됩니다. planner는 이 내용을 재탐색 없이 직접 활용합니다.

**5단계 - 다음 턴 안내:**

내부 모호성 분석과 탐색/검색 결과를 바탕으로 다음 턴의 AskUserQuestion 선택지를 자연스럽게 구성합니다. 브레인스토밍, 구체화, 범위 좁히기, 제약 조건 추가 등 다양한 방향을 유연하게 제안합니다.

> Step 3은 Step 4 종료 판단으로 빠져나오기 전까지 반복합니다.

---

### Step 4. 종료 판단

#### 사용자 명시적 완료

Step 3에서 사용자가 **"완료"** 옵션을 선택하거나, 자유 텍스트로 "완료", "끝", "done", "finish" 등을 입력한 경우 즉시 Step 5로 진행합니다.

#### Claude 자동 판단 완료 제안

내부 모호성 분석 결과와 함께, 아래 **G1~G4 게이트 조건**을 prompt.txt 현재 내용에 대해 내부적으로 평가합니다 (스크립트 호출 불필요, LLM 내부 판단):

| 게이트 | 조건 | 통과 기준 |
|--------|------|----------|
| **G1** | `<goal>` 태그 품질 | `<goal>` 태그가 존재하고 TODO나 빈 내용이 없으며, 구체적 목표 서술이 10자 이상 |
| **G2** | `<target>` 태그 품질 | `<target>` 태그에 구체적인 파일명, 모듈명, 컴포넌트명이 1개 이상 포함됨 |
| **G3** | `<constraints>` 태그 품질 | `<constraints>` 태그에 기술적 제약 조건이 1개 이상 명시됨 |
| **G4** | `<criteria>` 태그 품질 | `<criteria>` 태그에 검증 가능한 완료 기준이 1개 이상 포함됨 |

> **XML 태그 미사용 폴백**: prompt.txt에 XML 태그가 전혀 없는 경우, G1~G4 대신 기존 자연어 기준(목표 명확성, 대상 특정성, 제약 조건 포함, 검증 기준 존재)으로 동일하게 평가합니다.

**게이트 통과 수에 따른 동작:**

- **4개 모두 통과** → 완료를 제안합니다:

```
AskUserQuestion(
  questions: [{
    question: "현재 prompt가 충분히 구체적으로 작성된 것 같습니다. 완료할까요?",
    header: "완료 확인",
    options: [
      { label: "완료", description: "현재 상태로 작성을 마칩니다" },
      { label: "계속 개선", description: "대화를 이어서 추가 개선합니다" }
    ],
    multiSelect: false
  }]
)
```

- **"완료"** 선택 시 Step 5로 진행합니다.
- **"계속 개선"** 선택 시 Step 3으로 돌아갑니다.

- **1~3개 통과** → 완료를 제안하지 않고, 미충족 게이트에 해당하는 개선 방향을 AskUserQuestion 선택지로 제시합니다:

```
AskUserQuestion(
  questions: [{
    question: "prompt를 더 구체화하면 planner가 더 정확한 계획을 수립할 수 있습니다. 어떤 부분을 보강할까요?",
    header: "프롬프트 보강 제안",
    options: [
      // G1 미충족 시: { label: "<goal> 목표 구체화", description: "달성하려는 목표를 더 명확하게 서술합니다" }
      // G2 미충족 시: { label: "<target> 대상 파일/모듈 특정", description: "수정/생성할 파일이나 모듈을 구체적으로 지정합니다" }
      // G3 미충족 시: { label: "<constraints> 제약 조건 추가", description: "기술적 제약이나 유지해야 할 인터페이스를 명시합니다" }
      // G4 미충족 시: { label: "<criteria> 완료 기준 추가", description: "작업 완료를 검증할 수 있는 기준을 작성합니다" }
      { label: "완료", description: "현재 상태로 작성을 마칩니다" }
    ],
    multiSelect: false
  }]
)
```

> 미충족 게이트에 해당하는 선택지만 동적으로 포함합니다. "완료"는 항상 마지막 선택지로 포함합니다.

- **0개 통과** → 게이트 관련 언급 없이 자연스러운 대화를 계속합니다 (Step 3 반복).

---

### Step 5. 완료

최종 prompt.txt 내용을 표시하고 변경 요약을 출력합니다:

```
## 최종 prompt.txt 내용

<prompt.txt 내용 전체>

## 변경 요약

**시작 시 상태**: <최초 상태 요약 (빈 파일 또는 원본 내용 1-2줄)>
**완료 시 상태**: <최종 내용 요약 (1-2줄)>
**주요 변경**: <대화를 통해 추가/수정/구체화된 항목 나열>
**적용 스킬**: research-prompt-engineering (<활용된 체크리스트/템플릿 항목>)
```

완료 메시지와 후속 커맨드 안내를 출력합니다:

**권장 후속 커맨드 강조**: prompt.txt의 `<command>` 태그 값을 확인하여 해당 행에 "← 권장" 표시를 추가합니다.

- `<command>implement</command>` → "구현" 행에 "← 권장" 표시
- `<command>research</command>` → "조사" 행에 "← 권장" 표시
- `<command>review</command>` → "리뷰" 행에 "← 권장" 표시
- `<command>` 태그가 없는 경우 → "← 권장" 표시 없이 테이블만 출력

```
prompt.txt가 업데이트되었습니다.

## 후속 커맨드 안내

| 목적 | 커맨드 | 설명 |
|------|--------|------|
| 구현 | `/cc:implement` | prompt.txt의 내용이 구현 커맨드의 입력으로 활용됩니다 |
| 조사 | `/cc:research` | prompt.txt의 내용이 조사 커맨드의 입력으로 활용됩니다 |
| 리뷰 | `/cc:review` | prompt.txt의 내용이 리뷰 커맨드의 입력으로 활용됩니다 |
```

> 예: `<command>implement</command>`인 경우 출력 예시:
>
> | 목적 | 커맨드 | 설명 |
> |------|--------|------|
> | 구현 | `/cc:implement` | prompt.txt의 내용이 구현 커맨드의 입력으로 활용됩니다 **← 권장** |
> | 조사 | `/cc:research` | prompt.txt의 내용이 조사 커맨드의 입력으로 활용됩니다|
> | 리뷰 | `/cc:review` | prompt.txt의 내용이 리뷰 커맨드의 입력으로 활용됩니다|

---

## 완료 조건

| 조건 | 처리 |
|------|------|
| 사용자가 "완료" 선택 또는 입력 | 즉시 Step 5로 진행하여 최종 저장 및 완료 메시지 출력 |
| Claude 자동 판단 후 사용자 "완료" 확인 | Step 5로 진행하여 최종 저장 및 완료 메시지 출력 |
| Claude 자동 판단 후 사용자 "계속 개선" 선택 | Step 3으로 돌아가 대화 계속 |

## 후속 커맨드 연결

프롬프트 작성이 완료된 후, 작성된 prompt.txt의 내용에 따라 자연스럽게 다음 커맨드로 전환합니다. prompt.txt에 담긴 요구사항의 성격에 맞춰 적절한 커맨드를 선택하여 실행하면, 해당 커맨드가 프롬프트 내용을 자동으로 참조하고 작업을 진행합니다.

**선택 기준:**

- **구현 목적**: 새 기능, 코드 수정, 모듈 개발, 아키텍처 설계 등 → `/cc:implement` 사용
- **조사 목적**: 기술 조사, 비교 분석, 웹 리서치, 코드베이스 탐색 등 → `/cc:research` 사용
- **리뷰 목적**: 코드 리뷰, 보안/성능/아키텍처 검토 등 → `/cc:review` 사용

각 후속 커맨드는 prompt.txt의 내용을 입력으로 자동 활용하므로, 프롬프트 작성 후 바로 해당 커맨드를 실행하면 별도의 추가 설명 없이 작업이 시작됩니다.

## 주의사항

1. **Task 도구 호출 금지**: 이 명령어는 비워크플로우 독립 명령어이므로 서브에이전트를 호출하지 않습니다
2. **Bash 도구 호출 금지**: 가드 스크립트 비간섭을 보장합니다. 셸 명령어 실행이 필요 없습니다
3. **사용 가능 도구**: Read, Write, AskUserQuestion, Glob, Grep, WebSearch, WebFetch를 사용합니다
4. **워크플로우 무관**: FSM 상태 전이, initialization.py와 완전히 무관합니다. 배너 출력, workDir 생성, status.json 조작을 하지 않습니다
5. **모호성 체크리스트 비노출**: 모호성 분석 결과와 체크리스트 항목은 내부 가이드로만 활용하며 사용자에게 직접 출력하지 않습니다
6. **경량 모드 범위 제한**: 자유 질문/간단 조사/수정 모드는 워크플로우(FSM/가드/서브에이전트)를 사용하지 않습니다. 복잡한 작업은 cc:implement, cc:research, cc:review를 사용하세요
7. **수정 모드 복잡도 판단**: 수정 모드에서 T2/T3로 판정된 작업을 강제 실행할 경우, 결과 품질이 워크플로우 기반 실행보다 낮을 수 있습니다
