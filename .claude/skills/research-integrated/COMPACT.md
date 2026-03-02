# research-integrated (Compact)

## 목적
웹 검색(WebSearch, WebFetch)과 코드베이스 탐색(Read, Grep, Glob)을 통합하여 외부 정보와 내부 코드를 교차 대조.

## 워크플로우 (6단계)
1. 범위 정의: 웹 조사 범위 + 코드 탐색 범위 확정
2. 코드 현황 파악: Grep/Glob으로 프로젝트 내 현재 사용 패턴 파악
3. 웹 조사: WebSearch/WebFetch로 외부 최신 정보 수집
4. 교차 대조: 외부 정보 vs 내부 현황 갭 분석
5. 영향 분석: 변경 시 영향 범위 산정
6. 리포트 작성: 갭 분석 + 권고사항 정리

## 적합한 상황
- 라이브러리 업데이트 영향 분석
- 기술 마이그레이션 평가
- 외부 기술 vs 내부 구현 갭 분석

## 차별점 (vs 다른 research 스킬)
- research-general: 웹 전용 조사
- research-deep: 코드 전용 탐색
- research-integrated: 웹+코드 교차 대조 (이 스킬)

## 금지
- 웹 조사만 수행하고 코드 탐색 생략
- 코드 탐색만 수행하고 웹 조사 생략
