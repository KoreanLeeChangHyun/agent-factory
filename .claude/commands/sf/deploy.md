---
description: Salesforce 메타데이터를 배포합니다.
argument-hint: "<배포할 컴포넌트 경로>"
---

# Salesforce Deploy

Salesforce CLI를 사용하여 메타데이터를 배포합니다.

## 워크플로우 특성

sf:deploy는 Salesforce 배포 전용 명령어로, /wf 명령어와 달리 독립 워크플로우를 사용합니다.

**표준 워크플로우와의 차이:**
- /wf 명령어: INIT → PLAN → WORK → REPORT (4단계)
- sf:deploy: PLAN → WORK → REPORT (3단계, Salesforce 배포 최적화)

**독립 워크플로우 사용 이유:**
- Salesforce 배포는 단일 목적의 명령어로, ROUTING 판단이 불필요
- 배포 작업은 항상 동일한 패턴을 따르므로 간소화된 워크플로우가 효율적
- CONTEXT/SLACK 단계 없이 즉시 배포 결과를 확인하는 것이 실용적

## 입력: $ARGUMENTS

## 작업 흐름: PLAN → WORK → REPORT

```
┌─────────────────────────────────────────────────────────────┐
│  PLAN (planner)  →  사용자 확인  →  WORK (worker)  →  REPORT (reporter)  │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: PLAN (planner 에이전트)

### 1.1 환경 확인

```bash
# sfdx-project.json 존재 확인
ls sfdx-project.json

# 연결된 org 확인
sf org display

# 배포 대상 경로 확인
ls $ARGUMENTS
```

### 1.2 배포 대상 분석

| 입력 유형 | SF CLI 명령어 |
|----------|--------------|
| 폴더 경로 (`force-app`) | `sf project deploy start --source-dir <path>` |
| 매니페스트 (`manifest/package.xml`) | `sf project deploy start --manifest <path>` |
| 메타데이터 타입 (`ApexClass:MyClass`) | `sf project deploy start --metadata <type>` |
| 미지정 | `sf project deploy start --source-dir force-app` |

### 1.3 실행 계획 수립

배포할 컴포넌트 목록:

| 타입 | 이름 | 경로 |
|------|------|------|
| ApexClass | ... | ... |
| LWC | ... | ... |

### 1.4 사용자 확인 요청 (AskUserQuestion 필수)

계획 수립 후 **반드시 AskUserQuestion 도구를 사용하여** 사용자 확인을 받습니다:

```markdown
## 배포 계획

- **대상 Org**: [org alias]
- **배포 경로**: $ARGUMENTS
- **컴포넌트**: N개
- **테스트 레벨**: [NoTestRun/RunLocalTests/...]

| 타입 | 이름 |
|------|------|
| ... | ... |
```

**AskUserQuestion 호출 예시:**
```
AskUserQuestion(
  questions: [{
    question: "위 배포 계획대로 진행하시겠습니까?",
    header: "배포 승인",
    options: [
      { label: "승인 (Recommended)", description: "위 계획대로 배포를 실행합니다" },
      { label: "테스트 레벨 변경", description: "테스트 레벨을 변경합니다" },
      { label: "배포 취소", description: "배포를 중단합니다" }
    ],
    multiSelect: false
  }]
)
```

**선택지별 처리:**

| 선택 | 처리 |
|------|------|
| **승인** | Phase 2 (WORK)로 진행 |
| **테스트 레벨 변경** | AskUserQuestion으로 테스트 레벨 재선택 후 계획 갱신, 1.4 재실행 |
| **배포 취소** | "배포가 취소되었습니다" 출력 후 종료 |

**사용자 승인 후에만 다음 단계로 진행합니다.**

---

## Phase 2: WORK (worker 에이전트)

### 2.1 배포 실행

```bash
sf project deploy start --source-dir <path> --wait 30 --json
```

**주요 플래그:**
- `--wait 30`: 최대 30분 대기
- `--json`: JSON 형식 출력
- `--dry-run`: 검증만 (선택)
- `--test-level`: 테스트 레벨 지정

### 2.2 실패 시 재배포 로직

```
배포 실패 → 원인 분석 → 자동 수정 가능?
                         ├─ Yes → 수정 → 재배포 (최대 3회)
                         └─ No  → 사용자에게 보고
```

**자동 수정 가능:**
- 문법 오류 (Syntax Error)
- API 버전 불일치
- 누락된 필드/객체 참조

**수동 수정 필요:**
- 권한 부족
- Org 설정 문제
- 복잡한 의존성 문제

---

## Phase 3: REPORT (reporter 에이전트)

### 3.1 결과 문서 작성

`.workflow/deploy/<YYYYMMDD>-<HHMMSS>-<제목>/report.md` 생성:

```markdown
# Deploy Report

## 개요
- **대상 Org**: [org alias]
- **배포 대상**: [source path]
- **일시**: [날짜]
- **상태**: 성공/실패

## 배포된 컴포넌트
| 타입 | 이름 | 상태 |
|------|------|------|
| ApexClass | MyClass | Created/Changed |
| LWC | myComponent | Created/Changed |

## 요약
- 성공: N개
- 실패: N개

## 에러 (실패 시)
| 파일 | 라인 | 에러 메시지 |
|------|------|------------|
```

### 3.2 배포 성공 시

```markdown
## 배포 완료

- **대상 Org**: [org alias]
- **배포 대상**: $ARGUMENTS
- **결과**: 성공 N개
- **문서**: .workflow/deploy/<YYYYMMDD>-<HHMMSS>-<제목>/report.md
```

### 3.3 배포 실패 시

```markdown
## 배포 실패

- **대상 Org**: [org alias]
- **에러**: [에러 메시지]
- **원인**: [원인 분석]
- **수정 방안**: [구체적인 조치]
```

---

## SF CLI 명령어 레퍼런스

### 배포 (Deploy)
```bash
# 소스 디렉토리 배포
sf project deploy start --source-dir force-app

# 매니페스트 기반 배포
sf project deploy start --manifest manifest/package.xml

# 특정 메타데이터 배포
sf project deploy start --metadata ApexClass:MyClass

# 테스트 실행과 함께 배포
sf project deploy start --source-dir force-app --test-level RunLocalTests
```

### 검증 (Validate)
```bash
# 배포 전 검증 (dry-run)
sf project deploy validate --source-dir force-app --test-level RunLocalTests

# 검증 후 빠른 배포
sf project deploy quick --job-id <jobId>
```

---

## 에러 유형별 대응

| 에러 유형 | 예시 | 대응 |
|----------|------|------|
| Apex 컴파일 | `Variable does not exist` | 변수 선언 또는 오타 수정 |
| LWC 파싱 | `LWC1503: Parsing error` | JavaScript 문법 오류 수정 |
| 의존성 | `no CustomObject named X found` | 의존 메타데이터 먼저 배포 |
| 테스트 실패 | `Test failure: MyClassTest` | 테스트 코드 수정 |
| 권한 | `Not available for deploy` | 관리자에게 권한 요청 |

---

## 사용자 재질의 원칙

**이 명령어 실행 중 사용자 입력이 필요한 경우 반드시 `AskUserQuestion` 도구를 사용합니다.**

| 상황 | AskUserQuestion 사용 |
|------|---------------------|
| 배포 계획 승인 요청 (1.4) | 필수 |
| 테스트 레벨 변경 | 필수 |
| 수동 수정 필요 시 안내 | 메시지 출력만 (수정은 사용자가 직접) |
