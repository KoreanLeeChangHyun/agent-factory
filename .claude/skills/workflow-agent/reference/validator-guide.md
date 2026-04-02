# Validator Agent Guide

WORK Phase 완료 후 통합 검증을 수행하는 에이전트 스킬. 오케스트레이터가 모든 Worker Phase(1~N) 완료 후 Phase N+1로 validator 에이전트를 호출한다.

> 이 스킬은 workflow-orchestration 스킬이 관리하는 워크플로우의 한 단계입니다. 전체 워크플로우 구조는 workflow-orchestration 스킬을 참조하세요.

**workflow-agent Validator의 역할:**
- 오케스트레이터(workflow-orchestration)가 Task 도구로 validator 에이전트를 호출
- MVP 검증 세트 4개 항목을 순차 실행
- 검증 결과를 `validation-report.md` 파일로 생성
- 결과를 오케스트레이터에 반환 (validator는 코드를 수정하지 않음)

## 핵심 원칙

1. **검증 전용**: 코드를 수정하지 않는다 (Edit 도구 미보유). 검증 결과만 기록
2. **Fail Fast, Fail Cheap**: 비용 낮고 빠른 검증부터 실행하여 조기에 결함 감지 (BP-1)
3. **Soft Blocking**: 치명적 오류(빌드 실패)만 blocking, 린트/타입 경고는 경고만 기록. 단, 작업내역 전체 누락은 Hard blocking으로 보고서 단계 진입을 차단한다
4. **조건부 스킵**: 검증 도구 미설치(설정 파일 미존재) 시 해당 항목 SKIP
5. **질문 금지**: 사용자에게 질문하지 않음

---

## 터미널 출력 원칙

> 내부 분석/사고 과정을 터미널에 출력하지 않는다. 결과만 출력한다.

- **출력 허용**: 반환값 (1줄 규격), 에러 메시지
- **출력 금지**: 검증 과정 설명, 도구 감지 과정, 판단 근거, 중간 진행 보고
- 검증 명령어 실행, 결과 분석 등 모든 작업은 묵묵히 수행하고 최종 반환값만 출력
- 배너 출력은 오케스트레이터가 담당

---

## 검증 절차

```mermaid
flowchart TD
    S_PLAN[1단계: 계획서 로드 및 요구사항 파악] --> S_PRIOR[2단계: 선행 산출물 참조]
    S_PRIOR --> S1[3단계: 환경 감지]
    S1 --> S2[4단계: 검증 실행]
    S2 --> S3[5단계: 검증 내역 작성]
```

### 1단계: 계획서 로드 및 요구사항 파악

`planPath`에서 계획서를 Read하여 검증 범위를 파악한다.

계획서에서 다음 정보를 추출한다:
- 태스크 목록(W01, W02, ...) 및 각 태스크의 작업 내용
- 검증 대상 파일 목록 (태스크별 산출물)
- 특별한 검증 요구사항 (계획서 스킬 컬럼에 전문화 스킬이 명시된 경우 동적 로드)

### 2단계: 선행 산출물 참조

모든 Worker 산출물을 Glob으로 탐색하고 내용을 Read하여 검증 컨텍스트를 확보한다.

각 파일의 "핵심 발견" 또는 "변경 파일" 섹션을 읽어 다음 컨텍스트를 확보한다:
- 어떤 소스 파일이 변경되었는지
- 어떤 의존성/import가 추가/변경되었는지
- Worker가 발견한 주의사항이나 알려진 이슈

> **목적**: validator의 선행 산출물 참조는 Worker의 "작업 연속성 보장"과 다르게, **검증 컨텍스트 확보**가 목적이다.

**판정 기준:**
- 모든 태스크의 작업 내역 파일이 존재: PASS
- 일부 누락: WARN (누락된 태스크 ID를 기록, 비차단)
- 전체 누락: FAIL (Hard blocking — 오케스트레이터가 REPORT 단계 진입을 차단하고 FAILED로 전이)

> **전체 누락 시 처리**: validator는 반환 상태를 "실패"로 반환한다. 오케스트레이터는 이 "실패" 반환을 Hard blocking으로 처리하여 REPORT 단계로 진행하지 않고 워크플로우를 FAILED로 전이한다.

### 3단계: 환경 감지

프로젝트 루트에서 검증 도구의 설정 파일 존재 여부를 확인하여 실행 가능한 검증 항목을 결정한다.

**도구 감지 매핑:**

| 설정 파일 | 검증 도구 | 검증 항목 |
|----------|----------|----------|
| `.eslintrc*`, `eslint.config.*` | ESLint | 린트 |
| `tsconfig.json` | tsc | 타입체크 |
| `.pylintrc`, `pyproject.toml` (pylint/ruff 섹션) | pylint/ruff | 린트 |
| `pyproject.toml` (mypy 섹션), `mypy.ini` | mypy | 타입체크 |
| `package.json` (scripts.build) | npm run build | 빌드 |
| `Makefile` (build 타겟) | make build | 빌드 |

설정 파일이 존재하지 않으면 해당 검증 항목을 SKIP으로 처리한다.

### 4단계: 검증 실행

#### 린트 검증

```bash
# ESLint (Node.js)
npx eslint . --max-warnings=0 2>&1 || true

# pylint (Python)
pylint **/*.py 2>&1 || true

# ruff (Python)
ruff check . 2>&1 || true
```

**판정 기준:**
- exit code 0, 에러 0개: PASS
- 경고만 존재 (에러 0개): WARN
- 에러 1개 이상: WARN (soft blocking - 린트 에러는 blocking하지 않음)

#### 타입체크 검증

```bash
# TypeScript
npx tsc --noEmit 2>&1 || true

# mypy (Python)
mypy . 2>&1 || true
```

**판정 기준:**
- exit code 0, 에러 0개: PASS
- 에러 1개 이상: WARN (soft blocking)

#### 빌드 검증

```bash
# Node.js (package.json scripts.build)
npm run build 2>&1 || true

# Make
make build 2>&1 || true
```

**판정 기준:**
- exit code 0: PASS
- exit code != 0: FAIL (빌드 실패는 유일한 blocking 항목)

### 5단계: 검증 내역 작성

항목별 결과를 집계하여 최종 상태(통과/경고/실패)를 결정하고, `<workDir>/work/validation-report.md`에 기록한다.

---

## 조건부 스킵 로직

### 명령어별 스킵

| 명령어 | validator 실행 |
|--------|---------------|
| implement | 실행 |
| review | 실행 |
| research | 스킵 (코드 변경 없음) |
| prompt | 스킵 (코드 변경 없음) |

### 검증 도구 미설치 스킵

각 검증 항목별로 설정 파일이 존재하지 않으면 해당 항목만 SKIP 처리한다. 전체 검증을 중단하지 않는다.

---

## 타임아웃 설정

| 검증 항목 | 타임아웃 | 초과 시 처리 |
|----------|---------|------------|
| 작업 내역 확인 | 없음 (파일 존재 확인만) | - |
| 린트 검증 | 5분 (300000ms) | SKIP + 경고 기록 |
| 타입체크 검증 | 5분 (300000ms) | SKIP + 경고 기록 |
| 빌드 검증 | 5분 (300000ms) | SKIP + 경고 기록 |

---

## 검증 결과 판정

### 최종 상태 결정 로직

```mermaid
flowchart TD
    S0[검증 항목 수집] --> S0a{작업내역 전체 누락?}
    S0a -->|예| R0[상태: 실패\nHard blocking]
    S0a -->|아니오| S1[빌드 검증 결과 확인]
    S1 --> S2{빌드 검증 결과}
    S2 -->|FAIL| R1[상태: 실패\nsoft blocking]
    S2 -->|PASS 또는 SKIP| S3{WARN 항목 존재?}
    S3 -->|예| R2[상태: 경고]
    S3 -->|아니오| R3[상태: 통과]
```

| 조건 | 최종 상태 | 워크플로우 진행 |
|------|---------|--------------|
| **작업내역 전체 누락** | **실패** | **차단 (Hard blocking) — REPORT 진입 불가, FAILED 전이** |
| 빌드 FAIL | 실패 | 정상 진행 (soft blocking - 경고만 기록) |
| WARN 항목 1개 이상 (빌드 PASS/SKIP) | 경고 | 정상 진행 |
| 전체 PASS 또는 SKIP | 통과 | 정상 진행 |

> **blocking 설계 예외**: "작업내역 전체 누락"으로 인한 "실패" 상태는 빌드 FAIL과 달리 Hard blocking이다. 오케스트레이터는 이 경우 REPORT 단계로 진행하지 않고 워크플로우를 FAILED로 전이한다. 빌드 FAIL 및 기타 "실패" 상태는 여전히 soft blocking(경고만 기록 후 정상 진행)이다.

### 검증 내역 파일 (`validation-report.md`)

`<workDir>/work/validation-report.md` 파일에 검증 결과를 기록한다.

---

## 반환 형식

오케스트레이터에게 반환할 때 반드시 아래 1줄 형식만 사용한다.

```
상태: 통과|경고|실패
```

> **금지 항목**: 검증 결과 테이블, 에러 목록, 상세 출력, "다음 단계" 안내 등을 반환에 포함하지 않는다.

---

## 에러 처리

| 에러 유형 | 처리 방법 |
|----------|----------|
| 검증 도구 실행 실패 | 해당 항목 SKIP, 에러 사유 기록 |
| 파일 읽기/쓰기 실패 | 최대 3회 재시도 |
| 타임아웃 초과 | 해당 항목 SKIP + 경고 기록 |
| 전체 검증 불가 | 상태 "통과" + 전 항목 SKIP으로 반환 (검증 불가 환경) |

**재시도 정책**: 최대 3회, 각 시도 간 1초 대기

---

## 역할 경계

**validator가 수행하는 행위:**
- 검증 명령어 실행 (Bash)
- 작업 내역 파일 존재 확인 (Glob/Read)
- 검증 결과 기록 (`validation-report.md` 작성)

**validator가 수행하지 않는 행위:**
- 소스 코드 수정 (Edit 도구 미보유)
- 린트/타입 에러 자동 수정 (auto-fix)
- 워크플로우 중단 결정
- 최종 보고서(`report.md`) 생성

---

## 연관 스킬

| 스킬 | 관계 | 설명 |
|------|------|------|
| workflow-system | 유사 | Worker 개별 태스크 수준 검증. validator는 워크플로우 전체 수준 통합 검증 |
| review-code-quality | 유사 | Worker가 로드하는 린트/타입체크 스킬. validator는 최종 통합 검증 |
