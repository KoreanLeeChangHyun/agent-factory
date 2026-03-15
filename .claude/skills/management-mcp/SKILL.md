---
name: management-mcp
description: "Unified management skill for creating and modifying MCP (Model Context Protocol) servers. Builds LLM external service integration MCP servers through a 4-step workflow (design/implement/test/deploy). Use when creating a new MCP server, modifying an existing server, adding tools to a Model Context Protocol integration, or updating MCP server configuration and deployment."
license: "Apache-2.0"
---

# MCP 관리자

MCP(Model Context Protocol) 서버 생성 및 수정을 위한 통합 관리 가이드입니다.

## 개요

MCP 서버를 생성하거나 기존 서버를 수정하여 LLM이 외부 서비스와 상호작용할 수 있도록 합니다. MCP 서버의 품질은 LLM이 실제 작업을 얼마나 효과적으로 수행할 수 있는지로 측정됩니다.

---

# 프로세스

## 전체 워크플로우

고품질 MCP 서버를 만들려면 네 가지 주요 단계를 거칩니다:

### Phase 1: 심층 조사 및 계획

#### 1.1 현대적인 MCP 설계 이해

**API 커버리지 vs. 워크플로우 도구:**
포괄적인 API 엔드포인트 커버리지와 특화된 워크플로우 도구 사이의 균형을 맞춥니다. 워크플로우 도구는 특정 작업에 더 편리할 수 있고, 포괄적인 커버리지는 에이전트가 작업을 조합할 수 있는 유연성을 제공합니다. 클라이언트마다 성능이 다릅니다. 기본 도구를 조합하는 코드 실행으로 이점을 얻는 클라이언트도 있고, 더 높은 수준의 워크플로우가 더 잘 맞는 클라이언트도 있습니다. 불확실한 경우 포괄적인 API 커버리지를 우선시합니다.

**도구 네이밍 및 탐색성:**
명확하고 설명적인 도구 이름은 에이전트가 적합한 도구를 빠르게 찾을 수 있도록 도와줍니다. 일관된 접두사(예: `github_create_issue`, `github_list_repos`)와 동작 중심 네이밍을 사용합니다.

**컨텍스트 관리:**
에이전트는 간결한 도구 설명과 결과 필터링/페이지네이션 기능에서 이점을 얻습니다. 집중적이고 관련성 높은 데이터를 반환하는 도구를 설계합니다. 일부 클라이언트는 에이전트가 데이터를 필터링하고 처리하는 데 도움이 되는 코드 실행을 지원합니다.

**실행 가능한 에러 메시지:**
에러 메시지는 구체적인 제안과 다음 단계를 통해 에이전트가 해결책을 찾도록 안내해야 합니다.

#### 1.2 MCP 프로토콜 문서 학습

**MCP 명세 탐색:**

사이트맵으로 관련 페이지를 먼저 찾습니다: `https://modelcontextprotocol.io/sitemap.xml`

그런 다음 마크다운 형식으로 `.md` 접미사를 붙여 특정 페이지를 가져옵니다 (예: `https://modelcontextprotocol.io/specification/draft.md`).

검토할 주요 페이지:
- 명세 개요 및 아키텍처
- 전송 메커니즘 (streamable HTTP, stdio)
- 도구, 리소스, 프롬프트 정의

#### 1.3 프레임워크 문서 학습

**권장 기술 스택:**
- **언어**: TypeScript (고품질 SDK 지원 및 많은 실행 환경에서의 호환성. 또한 AI 모델이 TypeScript 코드 생성에 뛰어나며, 광범위한 사용성, 정적 타입, 우수한 린팅 도구의 이점)
- **전송**: 원격 서버에는 Streamable HTTP를 사용하며 상태 비저장 JSON 방식 (상태 저장 세션 및 스트리밍 응답에 비해 확장 및 유지 관리가 간단). 로컬 서버에는 stdio.

**프레임워크 문서 불러오기:**

- **MCP 모범 사례**: [📋 모범 사례 보기](./reference/mcp_best_practices.md) - 핵심 가이드라인

**TypeScript (권장):**
- **TypeScript SDK**: WebFetch로 `https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/main/README.md` 불러오기
- [⚡ TypeScript 가이드](./reference/node_mcp_server.md) - TypeScript 패턴 및 예시

**Python:**
- **Python SDK**: WebFetch로 `https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/main/README.md` 불러오기
- [🐍 Python 가이드](./reference/python_mcp_server.md) - Python 패턴 및 예시

#### 1.4 구현 계획 수립

**API 이해:**
서비스의 API 문서를 검토하여 주요 엔드포인트, 인증 요구사항, 데이터 모델을 파악합니다. 필요시 웹 검색과 WebFetch를 활용합니다.

**도구 선택:**
포괄적인 API 커버리지를 우선시합니다. 가장 일반적인 작업부터 시작하여 구현할 엔드포인트 목록을 작성합니다.

---

### Phase 2: 구현

#### 2.1 프로젝트 구조 설정

언어별 가이드에서 프로젝트 설정 방법 참조:
- [⚡ TypeScript 가이드](./reference/node_mcp_server.md) - 프로젝트 구조, package.json, tsconfig.json
- [🐍 Python 가이드](./reference/python_mcp_server.md) - 모듈 구성, 의존성

#### 2.2 핵심 인프라 구현

공유 유틸리티 생성:
- 인증이 포함된 API 클라이언트
- 에러 처리 헬퍼
- 응답 포맷팅 (JSON/Markdown)
- 페이지네이션 지원

#### 2.3 도구 구현

각 도구에 대해:

**입력 스키마:**
- Zod (TypeScript) 또는 Pydantic (Python) 사용
- 제약 조건과 명확한 설명 포함
- 필드 설명에 예시 추가

**출력 스키마:**
- 구조화된 데이터를 위해 가능한 경우 `outputSchema` 정의
- 도구 응답에 `structuredContent` 사용 (TypeScript SDK 기능)
- 클라이언트가 도구 출력을 이해하고 처리하는 데 도움

**도구 설명:**
- 기능에 대한 간결한 요약
- 파라미터 설명
- 반환 타입 스키마

**구현:**
- I/O 작업에 async/await 적용
- 실행 가능한 메시지로 적절한 에러 처리
- 해당하는 경우 페이지네이션 지원
- 최신 SDK 사용 시 텍스트 콘텐츠와 구조화된 데이터 모두 반환

**어노테이션:**
- `readOnlyHint`: true/false
- `destructiveHint`: true/false
- `idempotentHint`: true/false
- `openWorldHint`: true/false

---

### Phase 3: 검토 및 테스트

#### 3.1 코드 품질

다음 항목 검토:
- 코드 중복 없음 (DRY 원칙)
- 일관된 에러 처리
- 완전한 타입 커버리지
- 명확한 도구 설명

#### 3.2 빌드 및 테스트

**TypeScript:**
- `npm run build` 실행하여 컴파일 검증
- MCP Inspector로 테스트: `npx @modelcontextprotocol/inspector`

**Python:**
- 구문 검증: `python -m py_compile your_server.py`
- MCP Inspector로 테스트

세부적인 테스트 방법과 품질 체크리스트는 언어별 가이드 참조.

---

### Phase 4: 평가 생성

MCP 서버를 구현한 후 효과성을 테스트하기 위한 포괄적인 평가를 생성합니다.

**완전한 평가 가이드라인은 [✅ 평가 가이드](./reference/evaluation.md)를 불러오세요.**

#### 4.1 평가 목적 이해

LLM이 MCP 서버를 효과적으로 사용하여 현실적이고 복잡한 질문에 답할 수 있는지 테스트하기 위해 평가를 사용합니다.

#### 4.2 평가 질문 10개 생성

효과적인 평가를 만들려면 평가 가이드에 설명된 프로세스를 따릅니다:

1. **도구 검사**: 사용 가능한 도구 목록 확인 및 기능 파악
2. **콘텐츠 탐색**: 읽기 전용 작업으로 사용 가능한 데이터 탐색
3. **질문 생성**: 복잡하고 현실적인 질문 10개 생성
4. **답변 검증**: 각 질문을 직접 풀어 답변 검증

#### 4.3 평가 요구사항

각 질문이 다음 조건을 충족하는지 확인합니다:
- **독립적**: 다른 질문에 의존하지 않음
- **읽기 전용**: 비파괴적 작업만 필요
- **복잡함**: 여러 도구 호출과 심층 탐색 필요
- **현실적**: 실제로 사람이 관심 가질 실제 사용 사례 기반
- **검증 가능**: 문자열 비교로 검증 가능한 단일하고 명확한 답변
- **안정적**: 시간이 지나도 답변이 변하지 않음

#### 4.4 출력 형식

다음 구조로 XML 파일 생성:

```xml
<evaluation>
  <qa_pair>
    <question>Find discussions about AI model launches with animal codenames. One model needed a specific safety designation that uses the format ASL-X. What number X was being determined for the model named after a spotted wild cat?</question>
    <answer>3</answer>
  </qa_pair>
<!-- 더 많은 qa_pairs... -->
</evaluation>
```

---

# 참고 파일

## 문서 라이브러리

개발 중 필요에 따라 아래 리소스를 불러옵니다:

### 핵심 MCP 문서 (먼저 불러오기)
- **MCP 프로토콜**: `https://modelcontextprotocol.io/sitemap.xml`의 사이트맵으로 시작한 후 `.md` 접미사를 붙여 특정 페이지 가져오기
- [📋 MCP 모범 사례](./reference/mcp_best_practices.md) - 다음을 포함한 범용 MCP 가이드라인:
  - 서버 및 도구 네이밍 규칙
  - 응답 형식 가이드라인 (JSON vs Markdown)
  - 페이지네이션 모범 사례
  - 전송 방식 선택 (streamable HTTP vs stdio)
  - 보안 및 에러 처리 기준

### SDK 문서 (Phase 1/2 중 불러오기)
- **Python SDK**: `https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/main/README.md`에서 가져오기
- **TypeScript SDK**: `https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/main/README.md`에서 가져오기

### 언어별 구현 가이드 (Phase 2 중 불러오기)
- [🐍 Python 구현 가이드](./reference/python_mcp_server.md) - 다음을 포함한 완전한 Python/FastMCP 가이드:
  - 서버 초기화 패턴
  - Pydantic 모델 예시
  - `@mcp.tool`로 도구 등록
  - 완전한 동작 예시
  - 품질 체크리스트

- [⚡ TypeScript 구현 가이드](./reference/node_mcp_server.md) - 다음을 포함한 완전한 TypeScript 가이드:
  - 프로젝트 구조
  - Zod 스키마 패턴
  - `server.registerTool`로 도구 등록
  - 완전한 동작 예시
  - 품질 체크리스트

### 평가 가이드 (Phase 4 중 불러오기)
- [✅ 평가 가이드](./reference/evaluation.md) - 다음을 포함한 완전한 평가 생성 가이드:
  - 질문 생성 가이드라인
  - 답변 검증 전략
  - XML 형식 명세
  - 예시 질문 및 답변
  - 제공된 스크립트로 평가 실행
