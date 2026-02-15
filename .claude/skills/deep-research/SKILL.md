---
name: deep-research
description: "Deep codebase exploration skill using context:fork in an isolated Explore agent. Use for deep code exploration tasks: (1) large-scale codebase deep exploration, (2) deep investigation without main context pollution, (3) large-scale exploration with token usage savings, (4) complex dependency tracking and impact analysis. Triggers: '심층 조사', 'deep research', '코드 탐색', '대규모 분석'."
context: fork
agent: Explore
license: "Apache-2.0"
---

# Deep Research

`context:fork`와 Explore 에이전트를 활용하여 메인 컨텍스트를 오염시키지 않고 코드베이스를 심층 탐색하는 스킬입니다.

## 목적

- 메인 컨텍스트 오염 없이 깊은 코드베이스 탐색
- Explore 에이전트(Haiku 모델)로 빠르고 효율적인 탐색
- 대규모 탐색 결과를 요약하여 메인 컨텍스트에 반환
- 토큰 사용량 절약 (격리 컨텍스트에서 탐색 후 요약만 전달)

## 동작 방식

### context:fork

이 스킬은 `context: fork` frontmatter 설정을 사용합니다.
- 스킬 호출 시 현재 컨텍스트의 **복사본**이 생성됩니다
- 격리된 컨텍스트에서 탐색이 수행됩니다
- 탐색 결과 요약만 메인 컨텍스트에 반환됩니다
- 격리 컨텍스트는 완료 후 폐기됩니다

### Explore 에이전트

`agent: Explore` 설정으로 Explore 에이전트에서 실행됩니다.
- **읽기 전용**: 파일 수정 불가 (Read, Grep, Glob만 사용)
- **Haiku 모델**: 빠른 응답 속도, 낮은 토큰 비용
- **대량 탐색에 최적화**: 많은 파일을 빠르게 스캔

### 실행 흐름

```
메인 컨텍스트
    |
    v
[context:fork] --> 격리된 Explore 에이전트 생성
    |                    |
    |                    v
    |               코드베이스 탐색
    |               (Read, Grep, Glob)
    |                    |
    |                    v
    |               결과 요약 생성
    |                    |
    v                    v
메인 컨텍스트 <-- 요약 결과 반환
    |
    v
요약 기반으로 후속 작업 수행
```

## 사용 방법

### $ARGUMENTS를 통한 탐색 주제 지정

이 스킬은 `$ARGUMENTS`로 탐색 주제와 범위를 받습니다.

**호출 예시:**
```
deep-research 프로젝트의 Hook 시스템 구조를 분석해줘
deep-research 인증 모듈의 의존성 그래프를 파악해줘
deep-research src/utils/ 디렉토리의 공통 패턴을 찾아줘
```

### 탐색 수행 절차

1. **주제 파악**: `$ARGUMENTS`에서 탐색 주제와 범위 식별
2. **구조 탐색**: Glob으로 관련 파일/디렉토리 구조 파악
3. **키워드 검색**: Grep으로 관련 코드 패턴 검색
4. **상세 분석**: Read로 핵심 파일 내용 분석
5. **결과 요약**: 탐색 결과를 구조화된 요약으로 정리

### 탐색 가이드

> 도메인별 상세 전략은 `references/search-strategies.md`를 참조하세요. 구조 분석, 패턴 발견, 의존성 추적, 데이터 흐름 추적 등 전략별 도구 조합 예시와 적용 시나리오를 제공합니다.

#### 코드베이스 구조 분석

```
1. 프로젝트 루트의 주요 파일 확인 (package.json, Cargo.toml 등)
2. 디렉토리 구조 파악 (src/, lib/, tests/ 등)
3. 진입점(entry point) 식별
4. 모듈 간 의존성 추적
```

#### 패턴 발견

```
1. 공통 코딩 패턴 식별 (팩토리, 싱글톤, 옵저버 등)
2. 에러 처리 패턴 분석
3. 설정 관리 패턴 파악
4. 테스트 전략 분석
```

#### 의존성 추적

```
1. import/require 문 분석
2. 모듈 간 호출 그래프 구성
3. 순환 의존성 감지
4. 외부 라이브러리 의존성 파악
```

## 결과 요약 형식

격리 컨텍스트에서 메인 컨텍스트로 반환되는 요약 형식:

```markdown
## 탐색 결과 요약

### 탐색 주제
[탐색한 주제/범위]

### 핵심 발견사항
1. [발견 1]
2. [발견 2]
3. [발견 3]

### 관련 파일
| 파일 | 역할 | 핵심 내용 |
|------|------|----------|
| `path/to/file1` | [역할] | [내용 요약] |
| `path/to/file2` | [역할] | [내용 요약] |

### 구조/패턴
[발견된 구조나 패턴 설명]

### 추가 조사 필요 항목
- [추가 조사가 필요한 부분]
```

## 적용 단계

- **WORK**: `research`, `analyze` 명령어에서 코드베이스 심층 탐색 시 활용
- 기존 `command-research` 스킬과 독립적으로 사용 가능
- `command-research` 스킬은 웹 검색 중심, `deep-research`는 코드베이스 탐색 중심

## 기존 command-research 스킬과의 차이

| 항목 | command-research | deep-research |
|------|----------|---------------|
| 주요 대상 | 웹 (WebSearch, WebFetch) | 코드베이스 (Read, Grep, Glob) |
| 컨텍스트 | 메인 컨텍스트에서 실행 | 격리된 fork 컨텍스트 |
| 모델 | 현재 모델 | Haiku (Explore 에이전트) |
| 토큰 비용 | 높음 (탐색 내용이 메인에 축적) | 낮음 (요약만 반환) |
| 적합한 상황 | 최신 기술 조사, 외부 정보 수집 | 대규모 코드베이스 분석, 패턴 발견 |

### 통합 활용 가이드

하나의 연구 태스크에서 command-research와 deep-research를 순차적으로 활용하면 웹 정보와 코드베이스 분석을 결합한 포괄적 연구가 가능합니다. 일반적으로 deep-research로 코드베이스에서 현재 사용 중인 기술/패턴/라이브러리를 먼저 식별한 뒤, command-research로 해당 기술의 최신 동향, 알려진 이슈, 대안, 베스트 프랙티스를 웹에서 조사합니다. 이 순서는 코드 기반의 구체적 맥락이 있을 때 웹 조사의 초점을 좁혀 더 관련성 높은 결과를 얻을 수 있기 때문입니다.

반대로 외부 기술 트렌드나 신규 프레임워크를 먼저 조사(command-research)한 후, 해당 기술이 현재 코드베이스에 어느 정도 적용되어 있는지 확인(deep-research)하는 역순 패턴도 효과적입니다. 상세한 도구 조합 예시와 전략별 시나리오는 `references/search-strategies.md`의 "command-research와의 통합 활용" 섹션을 참조하세요.

## 참고

- Claude Code 공식 문서: [Skills - context:fork](https://code.claude.com/docs/en/skills)
- Claude Code 공식 문서: [Subagents - Explore](https://code.claude.com/docs/en/sub-agents)
- 관련 스킬: `command-research` (웹 중심 조사), `command-analyze-codebase` (코드 분석)
