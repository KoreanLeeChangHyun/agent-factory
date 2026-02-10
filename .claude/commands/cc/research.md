---
description: 웹 검색 기반 연구/조사 수행. 외부 정보 수집, 기술 비교 분석, 심층 검색을 통해 리포트를 제공합니다.
---

# Research

## -np 플래그 (No-Plan 모드)

`$ARGUMENTS`에 `-np` 플래그가 포함된 경우 Tier 2 (no-plan) 모드로 실행합니다.

- `-np` 감지 시: init 에이전트 호출에 `mode: no-plan` 전달
- `-np` 미감지 시: 기존과 동일 (mode: full)

```
# -np 플래그 감지 예시
cc:research -np "빠른 기술 조사"
→ Task(subagent_type="init", prompt="command: research\nmode: no-plan")
```

## 연구 절차

1. **주제 파악 및 범위 정의**
   - 연구 주제 파악 (기술 조사 / 개념 연구 / 비교 분석)
   - 조사 깊이, 범위, 시간 범위 정의
   - 비교 대상 확인 (해당 시)

2. **정보 수집**
   - WebSearch: 최신 정보, 문서, 블로그 등
   - WebFetch: 특정 페이지 상세 내용
   - Grep, Glob, Read: 코드베이스 탐색, 기존 사용 패턴

3. **분석 및 정리**
   - 핵심 개념 추출
   - 장단점 분석
   - 비교 분석 (해당 시)
   - 실제 적용 가능성 평가
   - 주의사항 및 제한사항

4. **리포트 작성**
   - 구조화된 문서 생성
   - 출처 명시

리포트 템플릿, 주의사항 등 상세 절차는 command-research 스킬(`.claude/skills/command-research/SKILL.md`)을 참조합니다.

## 관련 스킬

- `.claude/skills/command-research/SKILL.md` - 연구/조사 워크플로우 상세 정의, 리포트 템플릿
