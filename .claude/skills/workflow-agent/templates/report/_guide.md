# Report Template Guide

reporter 에이전트가 보고서 작성 시 참조하는 템플릿 선택 가이드.

## 템플릿 선택 매핑

| command | 템플릿 파일 | 보고서 유형 |
|---------|------------|------------|
| implement | `templates/implement.md` | 코드 변경형 (문제-해결 구조) |
| refactor | `templates/implement.md` | 코드 변경형 (개선 전/후 비교) |
| build | `templates/implement.md` | 코드 변경형 (빌드 결과 중심) |
| framework | `templates/implement.md` | 코드 변경형 (생성 구조 중심) |
| review | `templates/review.md` | 검토/분석형 (판정 구조) |
| analyze | `templates/review.md` | 검토/분석형 (분석 결과 구조) |
| research | `templates/research.md` | 조사형 (조사-결론 구조) |
| architect | `templates/architect.md` | 설계형 (아키텍처 구조) |

## 사용 방법

1. `command`에 해당하는 템플릿 파일을 Read 도구로 로드
2. `{{placeholder}}`를 실제 값으로 치환
3. 작업 내역(`work/` 디렉터리)을 분석하여 각 섹션 작성
4. `(선택)` 표기된 섹션은 해당 없으면 생략

## 공통 원칙

1. **메타 정보 필수**: 작업 ID, 명령어, 작성일은 모든 보고서에 포함
2. **작업 내역 필수**: 태스크별 수행 내용 기록
3. **가이드라인 성격**: 템플릿은 권장 구조이며, 내용에 따라 유연하게 조정 가능
4. **실제 수행 내용만 기록**: 계획이 아닌 실제 결과를 기반으로 작성

## Placeholder 목록

reporter 에이전트는 `command`, `workId`, `workDir`, `workPath` 4개의 입력 파라미터를 받습니다.
아래 placeholder는 이 입력 파라미터로부터 도출합니다.

| Placeholder | 설명 | 도출 방법 | 예시 |
|-------------|------|----------|------|
| `{{workId}}` | 작업 ID (HHMMSS 6자리) | 입력 파라미터 `workId` 직접 사용 | `143000` |
| `{{command}}` | 실행 명령어 | 입력 파라미터 `command` 직접 사용 | `implement` |
| `{{workName}}` | 작업명 (한글/영문) | `workDir`에서 3번째 경로 세그먼트 추출 (`workDir` 형식: `.workflow/YYYYMMDD-HHMMSS/<workName>/<command>`) | `로그인기능추가` |
| `{{date}}` | 작성일 (KST) | `workDir`에서 2번째 경로 세그먼트의 YYYYMMDD-HHMMSS를 파싱하여 `YYYY-MM-DD HH:MM:SS` 형식으로 변환 | `2026-02-09 14:30:00` |
| `{{planPath}}` | 계획서 경로 | `{workDir}/plan.md`로 구성 | `.workflow/20260209-143000/로그인기능추가/implement/plan.md` |
| `{{workflowId}}` | 워크플로우 ID (YYYYMMDD-HHMMSS) | `workDir`에서 2번째 경로 세그먼트 추출 | `20260209-143000` |

### workDir 경로 파싱 예시

```
workDir: .workflow/20260209-143000/로그인기능추가/implement
                   ───────────────  ──────────────  ─────────
                   {{workflowId}}   {{workName}}    {{command}}
                   → {{date}} 도출
```
