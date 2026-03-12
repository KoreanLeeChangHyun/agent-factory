---
name: management-skill
description: "Unified management skill for creating and modifying Claude Code skills. Creates or modifies skill packages in .claude/skills/ directory conforming to SKILL.md frontmatter spec. Use for skill lifecycle management: creating, updating, modifying, or deleting skills. Triggers: '스킬 만들어줘', '새 스킬 생성', 'create skill', 'update skill', 'modify skill', '스킬 수정'."
license: Complete terms in LICENSE.txt
---

# Skill Manager

스킬 생성 및 수정을 위한 통합 관리 가이드입니다.

## 스킬이란

스킬은 모듈식 독립 패키지로, 특화된 지식·워크플로우·도구를 제공하여 Claude의 능력을 확장합니다. 특정 도메인이나 작업을 위한 "온보딩 가이드"라고 생각하면 됩니다. 범용 에이전트인 Claude를 절차적 지식으로 무장한 전문 에이전트로 변환합니다.

### 스킬이 제공하는 것

1. 특화된 워크플로우 - 특정 도메인을 위한 다단계 절차
2. 도구 통합 - 특정 파일 형식이나 API와 함께 작동하는 지침
3. 도메인 전문성 - 회사 특화 지식, 스키마, 비즈니스 로직
4. 번들 리소스 - 복잡하고 반복적인 작업을 위한 스크립트, 참조 자료, 에셋

## 핵심 원칙

### 간결함이 핵심

컨텍스트 윈도우는 공공재입니다. 스킬은 컨텍스트 윈도우를 시스템 프롬프트, 대화 기록, 다른 스킬의 메타데이터, 실제 사용자 요청 등 Claude가 필요로 하는 모든 것과 공유합니다.

**기본 가정: Claude는 이미 매우 똑똑합니다.** Claude가 아직 모르는 컨텍스트만 추가하세요. 각 정보를 검토할 때 "Claude가 정말 이 설명이 필요한가?"와 "이 단락이 토큰 비용을 정당화하는가?"를 자문하세요.

장황한 설명보다 간결한 예시를 선호하세요.

### 적절한 자유도 설정

작업의 취약성과 가변성에 맞게 구체성 수준을 조정하세요:

**높은 자유도 (텍스트 기반 지침)**: 여러 접근 방식이 유효하거나, 결정이 컨텍스트에 따라 달라지거나, 발견적 방법이 접근 방식을 안내할 때 사용합니다.

**중간 자유도 (매개변수가 있는 의사코드 또는 스크립트)**: 선호 패턴이 있지만 일부 변형이 허용되거나, 설정이 동작에 영향을 줄 때 사용합니다.

**낮은 자유도 (특정 스크립트, 최소 매개변수)**: 작업이 취약하고 오류 발생이 쉽거나, 일관성이 중요하거나, 특정 순서를 따라야 할 때 사용합니다.

Claude가 경로를 탐색하는 것처럼 생각하세요: 절벽이 있는 좁은 다리는 구체적인 가드레일(낮은 자유도)이 필요하고, 넓은 들판은 여러 경로(높은 자유도)를 허용합니다.

### 스킬의 구조

모든 스킬은 필수 SKILL.md 파일과 선택적 번들 리소스로 구성됩니다:

```
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter metadata (required)
│   │   ├── name: (required)
│   │   └── description: (required)
│   └── Markdown instructions (required)
└── Bundled Resources (optional)
    ├── scripts/          - Executable code (Python/Bash/etc.)
    ├── references/       - Documentation intended to be loaded into context as needed
    └── assets/           - Files used in output (templates, icons, fonts, etc.)
```

#### SKILL.md (필수)

모든 SKILL.md는 다음으로 구성됩니다:

- **프론트매터** (YAML): `name`과 `description` 필드를 포함합니다. 이 두 필드만 Claude가 스킬을 언제 사용할지 결정하기 위해 읽으므로, 스킬이 무엇인지와 언제 사용해야 하는지를 명확하고 포괄적으로 설명하는 것이 매우 중요합니다.
- **본문** (Markdown): 스킬 사용 지침. 스킬이 트리거된 후에만 로드됩니다.

#### 번들 리소스 (선택)

##### 스크립트 (`scripts/`)

결정론적 신뢰성이 필요하거나 반복적으로 작성되는 작업을 위한 실행 코드 (Python/Bash/등).

- **포함 시기**: 같은 코드가 반복적으로 재작성되거나 결정론적 신뢰성이 필요할 때
- **예시**: PDF 회전 작업을 위한 `scripts/rotate_pdf.py`
- **장점**: 토큰 효율적, 결정론적, 컨텍스트에 로드하지 않고 실행 가능
- **참고**: 스크립트는 패치나 환경별 조정을 위해 Claude가 읽어야 할 수도 있습니다

##### 참조 자료 (`references/`)

Claude의 프로세스와 사고를 안내하기 위해 필요에 따라 컨텍스트에 로드하는 문서 및 참조 자료.

- **포함 시기**: Claude가 작업 중 참조해야 하는 문서가 있을 때
- **예시**: 재무 스키마를 위한 `references/finance.md`, 회사 NDA 템플릿을 위한 `references/mnda.md`, 회사 정책을 위한 `references/policies.md`, API 명세를 위한 `references/api_docs.md`
- **활용 사례**: 데이터베이스 스키마, API 문서, 도메인 지식, 회사 정책, 상세 워크플로우 가이드
- **장점**: SKILL.md를 간결하게 유지, Claude가 필요하다고 판단할 때만 로드
- **모범 사례**: 파일이 크면(>10k 단어), SKILL.md에 grep 검색 패턴을 포함시키세요
- **중복 방지**: 정보는 SKILL.md 또는 참조 파일 중 하나에만 존재해야 합니다. 스킬의 핵심이 아닌 상세 정보는 참조 파일을 선호하세요. 이렇게 하면 SKILL.md를 간결하게 유지하면서 컨텍스트 윈도우를 차지하지 않고도 정보를 검색할 수 있습니다. SKILL.md에는 핵심 절차 지침과 워크플로우 안내만 유지하고, 상세 참조 자료, 스키마, 예시는 참조 파일로 이동하세요.

##### 에셋 (`assets/`)

컨텍스트에 로드하지 않고 Claude가 생성하는 출력물에 사용되는 파일.

- **포함 시기**: 최종 출력물에 사용될 파일이 스킬에 필요할 때
- **예시**: 브랜드 에셋을 위한 `assets/logo.png`, PowerPoint 템플릿을 위한 `assets/slides.pptx`, HTML/React 보일러플레이트를 위한 `assets/frontend-template/`, 타이포그래피를 위한 `assets/font.ttf`
- **활용 사례**: 템플릿, 이미지, 아이콘, 보일러플레이트 코드, 복사하거나 수정하는 샘플 문서
- **장점**: 출력 리소스와 문서를 분리, Claude가 파일을 컨텍스트에 로드하지 않고 사용 가능

#### 스킬에 포함하지 말아야 할 것

스킬은 기능을 직접 지원하는 필수 파일만 포함해야 합니다. 다음과 같은 부가적인 문서나 보조 파일을 생성하지 마세요:

- README.md
- INSTALLATION_GUIDE.md
- QUICK_REFERENCE.md
- CHANGELOG.md
- 기타 등등

스킬은 AI 에이전트가 해당 작업을 수행하는 데 필요한 정보만 포함해야 합니다. 스킬을 만드는 과정에 대한 부가적인 컨텍스트, 설정 및 테스트 절차, 사용자용 문서 등을 포함하지 마세요. 추가 문서 파일은 혼란과 복잡성만 증가시킵니다.

### 점진적 공개 설계 원칙

스킬은 컨텍스트를 효율적으로 관리하기 위해 3단계 로딩 시스템을 사용합니다:

1. **메타데이터 (name + description)** - 항상 컨텍스트에 존재 (~100 단어)
2. **SKILL.md 본문** - 스킬이 트리거될 때 (<5k 단어)
3. **번들 리소스** - Claude가 필요에 따라 (스크립트는 컨텍스트 윈도우에 로드하지 않고 실행 가능하므로 무제한)

#### 점진적 공개 패턴

SKILL.md 본문을 핵심 내용으로 유지하고 500줄 미만으로 제한하여 컨텍스트 증가를 최소화하세요. 이 한계에 근접하면 내용을 별도 파일로 분리하세요. 내용을 다른 파일로 분리할 때, SKILL.md에서 해당 파일을 참조하고 언제 읽을지 명확히 설명하는 것이 매우 중요합니다.

**핵심 원칙:** 스킬이 여러 변형, 프레임워크, 옵션을 지원할 때, SKILL.md에는 핵심 워크플로우와 선택 안내만 유지하세요. 변형별 세부 사항(패턴, 예시, 설정)은 별도 참조 파일로 이동하세요.

**패턴 1: 참조가 있는 고수준 가이드**

```markdown
# PDF Processing

## Quick start

Extract text with pdfplumber:
[code example]

## Advanced features

- **Form filling**: See [FORMS.md](FORMS.md) for complete guide
- **API reference**: See [REFERENCE.md](REFERENCE.md) for all methods
- **Examples**: See [EXAMPLES.md](EXAMPLES.md) for common patterns
```

Claude는 필요할 때만 FORMS.md, REFERENCE.md, EXAMPLES.md를 로드합니다.

**패턴 2: 도메인별 구성**

여러 도메인이 있는 스킬의 경우, 관련 없는 컨텍스트 로드를 방지하기 위해 도메인별로 내용을 구성하세요:

```
bigquery-skill/
├── SKILL.md (overview and navigation)
└── reference/
    ├── finance.md (revenue, billing metrics)
    ├── sales.md (opportunities, pipeline)
    ├── product.md (API usage, features)
    └── marketing.md (campaigns, attribution)
```

사용자가 판매 지표에 대해 질문하면, Claude는 sales.md만 읽습니다.

마찬가지로, 여러 프레임워크나 변형을 지원하는 스킬의 경우 변형별로 구성하세요:

```
cloud-deploy/
├── SKILL.md (workflow + provider selection)
└── references/
    ├── aws.md (AWS deployment patterns)
    ├── gcp.md (GCP deployment patterns)
    └── azure.md (Azure deployment patterns)
```

사용자가 AWS를 선택하면, Claude는 aws.md만 읽습니다.

**패턴 3: 조건부 세부 사항**

기본 내용을 표시하고, 고급 내용에 링크를 연결하세요:

```markdown
# DOCX Processing

## Creating documents

Use docx-js for new documents. See [DOCX-JS.md](DOCX-JS.md).

## Editing documents

For simple edits, modify the XML directly.

**For tracked changes**: See [REDLINING.md](REDLINING.md)
**For OOXML details**: See [OOXML.md](OOXML.md)
```

사용자가 해당 기능이 필요할 때만 Claude가 REDLINING.md나 OOXML.md를 읽습니다.

**중요 지침:**

- **깊은 중첩 참조 방지** - 참조는 SKILL.md에서 한 단계 깊이로 유지하세요. 모든 참조 파일은 SKILL.md에서 직접 링크되어야 합니다.
- **긴 참조 파일 구조화** - 100줄 이상의 파일에는 미리보기 시 전체 범위를 확인할 수 있도록 상단에 목차를 포함하세요.

## 워크플로우 모드

워크플로우 WORK 단계에서 호출될 때는 AskUserQuestion을 사용하지 않고 계획서에 사전 확정된 사양을 기반으로 동작합니다.

### 감지 방법

prompt에 `planPath:` 키가 포함되어 있으면 워크플로우 모드로 판단합니다.

### 워크플로우 모드 동작

1. `planPath`에서 계획서(plan.md)를 읽어 해당 태스크의 필수 정보를 추출합니다:
   - **name**: 스킬 이름
   - **description**: 스킬 설명 (용도와 트리거 조건)
   - **구조**: 필요한 리소스 (scripts/, references/, assets/)
   - **내용**: SKILL.md 본문에 포함할 지침
2. AskUserQuestion 호출을 **건너뜁니다** (Step 1의 사용자 질문 생략)
3. 계획서에 명시된 정보만으로 Step 3(스킬 초기화)부터 진행합니다
4. 계획서에 정보가 누락된 경우 안전한 기본값을 사용합니다:
   - scope: 프로젝트 (`.claude/skills/`)
   - 리소스 디렉토리: 필요한 것만 생성

> **주의**: 워크플로우 모드에서는 Slack 대기 알림도 전송하지 않습니다.

## 스킬 생성 프로세스

스킬 생성은 다음 단계를 포함합니다:

1. 구체적인 예시로 스킬을 이해합니다
2. 재사용 가능한 스킬 내용을 계획합니다 (스크립트, 참조 자료, 에셋)
3. 스킬을 초기화합니다 (init_skill.py 실행)
4. 스킬을 편집합니다 (리소스 구현 및 SKILL.md 작성)
5. 스킬을 패키징합니다 (package_skill.py 실행)
6. 실제 사용을 기반으로 반복 개선합니다

명확한 이유 없이는 건너뛰지 말고 이 순서대로 따르세요.

### Step 1: 구체적인 예시로 스킬 이해하기

스킬의 사용 패턴이 이미 명확히 이해된 경우에만 이 단계를 건너뛰세요. 기존 스킬로 작업할 때도 여전히 가치 있는 단계입니다.

효과적인 스킬을 만들기 위해, 스킬이 어떻게 사용될지에 대한 구체적인 예시를 명확히 이해하세요. 이 이해는 사용자의 직접적인 예시나 사용자 피드백으로 검증된 생성 예시에서 얻을 수 있습니다.

예를 들어, 이미지 편집기 스킬을 만들 때 관련 질문들:

- "이미지 편집기 스킬은 어떤 기능을 지원해야 하나요? 편집, 회전, 또 다른 것들도 있나요?"
- "이 스킬이 어떻게 사용될지 예시를 들어주실 수 있나요?"
- "사용자들이 '이 이미지에서 적목 현상을 제거해줘'나 '이 이미지를 회전해줘' 같은 요청을 할 것 같은데, 다른 사용 방법도 생각해볼 수 있을까요?"
- "이 스킬을 트리거해야 하는 사용자 발화 예시는 무엇인가요?"

사용자를 압도하지 않으려면 한 번에 너무 많은 질문을 하지 마세요. 가장 중요한 질문부터 시작하고, 더 나은 효과를 위해 필요에 따라 후속 질문을 하세요.

스킬이 지원해야 할 기능에 대한 명확한 감이 생기면 이 단계를 마칩니다.

### Step 2: 재사용 가능한 스킬 내용 계획하기

구체적인 예시를 효과적인 스킬로 전환하기 위해, 각 예시를 다음과 같이 분석하세요:

1. 처음부터 예시를 실행하는 방법 고려하기
2. 이러한 워크플로우를 반복적으로 실행할 때 도움이 될 스크립트, 참조 자료, 에셋 파악하기

예시: "이 PDF를 회전해줘"와 같은 쿼리를 처리하기 위해 `pdf-editor` 스킬을 만들 때 분석 결과:

1. PDF 회전에는 매번 같은 코드 재작성이 필요합니다
2. 스킬에 저장할 `scripts/rotate_pdf.py` 스크립트가 도움이 됩니다

예시: "할 일 앱 만들어줘"나 "걸음 수 추적 대시보드 만들어줘" 같은 쿼리를 위한 `frontend-webapp-builder` 스킬 설계 시 분석 결과:

1. 프론트엔드 웹앱 작성에는 매번 같은 보일러플레이트 HTML/React가 필요합니다
2. 보일러플레이트 HTML/React 프로젝트 파일을 포함하는 `assets/hello-world/` 템플릿이 도움이 됩니다

예시: "오늘 로그인한 사용자 수는?" 같은 쿼리를 처리하기 위한 `big-query` 스킬 생성 시 분석 결과:

1. BigQuery 쿼리 시 매번 테이블 스키마와 관계를 다시 파악해야 합니다
2. 테이블 스키마를 문서화한 `references/schema.md` 파일이 도움이 됩니다

스킬의 내용을 확정하기 위해, 각 구체적인 예시를 분석하여 포함할 재사용 가능한 리소스 목록을 만드세요: 스크립트, 참조 자료, 에셋.

### Step 3: 스킬 초기화하기

이제 실제로 스킬을 만들 차례입니다.

스킬이 이미 존재하고 반복 개선이나 패키징이 필요한 경우에만 이 단계를 건너뛰세요. 이 경우 다음 단계로 계속 진행하세요.

새 스킬을 처음부터 만들 때, 스킬 디렉토리 구조를 수동으로 생성하세요:

```bash
# 스킬 디렉토리 생성
mkdir -p <skill-name>/{scripts,references,assets}

# SKILL.md 템플릿 생성
cat > <skill-name>/SKILL.md << 'EOF'
---
name: <skill-name>
description: <skill description - 스킬의 용도와 사용 시점을 명확히 기술>
---

# <Skill Name>

## Overview
[스킬 개요 작성]

## Usage
[사용 방법 작성]
EOF
```

생성할 항목:
- 스킬 디렉토리
- SKILL.md (프론트매터 + 본문)
- 필요한 리소스 디렉토리: `scripts/`, `references/`, `assets/`

초기화 후 SKILL.md와 리소스 파일들을 실제 스킬에 맞게 수정하세요.

### Step 4: 스킬 편집하기

(새로 생성했거나 기존) 스킬을 편집할 때, 이 스킬은 다른 Claude 인스턴스가 사용하기 위해 만들어진다는 점을 기억하세요. Claude에게 유익하고 자명하지 않은 정보를 포함하세요. 어떤 절차적 지식, 도메인별 세부 사항, 또는 재사용 가능한 에셋이 다른 Claude 인스턴스가 이러한 작업을 더 효과적으로 실행하는 데 도움이 될지 고려하세요.

#### 검증된 설계 패턴 학습하기

스킬의 필요에 따라 다음 가이드를 참고하세요:

- **다단계 프로세스**: 순차적 워크플로우와 조건부 로직은 references/workflows.md 참조
- **특정 출력 형식이나 품질 기준**: 템플릿과 예시 패턴은 references/output-patterns.md 참조

이 파일들은 효과적인 스킬 설계를 위한 확립된 모범 사례를 포함합니다.

#### 재사용 가능한 스킬 내용부터 시작하기

구현을 시작하려면, 위에서 파악한 재사용 가능한 리소스부터 시작하세요: `scripts/`, `references/`, `assets/` 파일. 이 단계에서 사용자 입력이 필요할 수 있습니다. 예를 들어, `design-brand-guidelines` 스킬을 구현할 때 사용자가 `assets/`에 저장할 브랜드 에셋이나 템플릿, 또는 `references/`에 저장할 문서를 제공해야 할 수도 있습니다.

추가된 스크립트는 버그가 없고 출력이 예상과 일치하는지 확인하기 위해 실제로 실행하여 테스트해야 합니다. 유사한 스크립트가 많은 경우, 모두 작동한다는 신뢰를 얻으면서 완료 시간을 균형 있게 유지하기 위해 대표 샘플만 테스트하면 됩니다.

스킬에 필요하지 않은 예시 파일과 디렉토리는 삭제하세요. 초기화 스크립트가 구조를 시연하기 위해 `scripts/`, `references/`, `assets/`에 예시 파일을 생성하지만, 대부분의 스킬은 이들 모두가 필요하지 않습니다.

#### SKILL.md 업데이트하기

**작성 지침:** 항상 명령형/부정사 형태를 사용하세요.

**Markdown 줄 바꿈 규칙:** MD 파일에서 줄 바꿈이 필요할 때는 항상 `<br>` 태그나 빈 줄을 사용하세요. 줄 끝의 후행 이중 공백은 보이지 않아 의도가 불명확하며, 편집기나 포매터에 의해 제거될 수 있습니다.

##### 프론트매터

`name`과 `description`으로 YAML 프론트매터를 작성하세요:

- `name`: 스킬 이름
- `description`: 스킬의 주요 트리거 메커니즘으로, Claude가 언제 스킬을 사용할지 이해하는 데 도움을 줍니다.
  - 스킬이 하는 일과 사용할 시점/컨텍스트를 모두 포함하세요.
  - "언제 사용하는지" 정보는 모두 여기에 포함하세요 - 본문에는 넣지 마세요. 본문은 트리거된 후에만 로드되므로, 본문의 "이 스킬을 사용할 때" 섹션은 Claude에게 도움이 되지 않습니다.
  - `docx` 스킬의 description 예시: "Comprehensive document creation, editing, and analysis with support for tracked changes, comments, formatting preservation, and text extraction. Use when Claude needs to work with professional documents (.docx files) for: (1) Creating new documents, (2) Modifying or editing content, (3) Working with tracked changes, (4) Adding comments, or any other document tasks"

선택적 필드:

- `scope`: 스킬의 적용 범위를 지정합니다.
  - `scope: global` (기본값) — 범용 전문화 스킬. 어느 프로젝트에서든 사용 가능. scope 필드 생략 시 global로 간주.
  - `scope: project` — DDD 도메인 특화 스킬. 해당 프로젝트에서만 사용. 명명 규칙: `project-<도메인명>`.

YAML 프론트매터에 다른 필드는 포함하지 마세요.

##### 본문

스킬과 번들 리소스 사용 지침을 작성하세요.

### Step 4.5: 카탈로그 동기화

스킬 편집 완료 후 skill-catalog.md를 자동 갱신합니다. Bash 도구로 다음 명령어를 실행하여 frontmatter 변경사항을 카탈로그에 반영합니다.

```bash
python3 .claude/scripts/sync/catalog_sync.py
```

이 단계는 PostToolUse Hook과 함께 이중 안전망을 구성합니다. Hook이 실패하더라도 이 단계에서 카탈로그가 갱신됩니다.

### Step 5: 스킬 패키징 (선택)

스킬 개발이 완료되면, 배포를 위해 패키징할 수 있습니다.

**수동 패키징 방법:**

```bash
# 스킬 디렉토리를 .skill 파일로 압축 (zip 형식)
cd <path/to/skill-folder>/..
zip -r <skill-name>.skill <skill-name>/
```

**패키징 전 검증 체크리스트:**

1. **프론트매터 검증**
   - `name` 필드 존재 여부
   - `description` 필드 존재 여부 (용도와 사용 시점 포함)

2. **디렉토리 구조 검증**
   - SKILL.md 파일 존재
   - 불필요한 파일 제거 (README.md, CHANGELOG.md 등)

3. **리소스 참조 검증**
   - SKILL.md에서 참조하는 모든 파일이 존재하는지 확인

**참고:** .skill 파일은 zip 형식이며 확장자만 변경한 것입니다.

### Step 6: 반복 개선

스킬을 테스트한 후, 사용자가 개선을 요청할 수 있습니다. 스킬이 어떻게 수행되었는지 생생한 컨텍스트가 있는 스킬 사용 직후에 자주 발생합니다.

**반복 개선 워크플로우:**

1. 실제 작업에 스킬을 사용합니다
2. 어려움이나 비효율성을 파악합니다
3. SKILL.md 또는 번들 리소스를 어떻게 업데이트해야 할지 파악합니다
4. 변경 사항을 구현하고 다시 테스트합니다
