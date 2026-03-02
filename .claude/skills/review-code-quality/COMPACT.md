# review-code-quality (Compact)

## 필수 실행
1. lint + format + typecheck 실행 (프로젝트 도구 자동 감지)
2. DRY/KISS/YAGNI 위반 탐지
3. Code Quality Score (0-100) 산출

## 메트릭 임계값

| 메트릭 | OK | 경고 |
|--------|-----|------|
| 순환복잡도 | <=10 | >10 |
| 함수크기 | <=50줄 | >50줄 |
| 파일크기 | <=500줄 | >500줄 |
| 중첩깊이 | <=3 | >3 |
| 매개변수 | <=4 | >4 |

## 점수 계산
Score = 100 - metric_penalties - issue_penalties
- high 이슈: -20 (보안 취약점, O(n^2)+, N+1 쿼리)
- medium 이슈: -10 (DRY 위반, 미사용 코드, 하드코딩)
- low 이슈: -3 (네이밍 불일치, 주석 부족)

## Generator-Critic 루프
Score < 70 → 자동 수정 후 재검증 (최대 3회)

## 금지
- Score 미산출 완료 선언
- Critical 이슈 무시
