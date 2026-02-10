---
description: 시스템 아키텍처 설계 및 UML 다이어그램 생성. 클래스, 시퀀스, ER, 컴포넌트, 배포, 상태 등 모든 다이어그램 지원.
---

# Architect

## -np 플래그 (No-Plan 모드)

`$ARGUMENTS`에 `-np` 플래그가 포함된 경우 Tier 2 (no-plan) 모드로 실행합니다.

- `-np` 감지 시: init 에이전트 호출에 `mode: no-plan` 전달
- `-np` 미감지 시: 기존과 동일 (mode: full)

```
# -np 플래그 감지 예시
cc:architect -np "간단한 시퀀스 다이어그램"
→ Task(subagent_type="init", prompt="command: architect\nmode: no-plan")
```

## 다이어그램 유형 선택

요청에 따라 적절한 다이어그램 유형을 결정합니다.

| 다이어그램 | 용도 | 예시 |
|-----------|------|------|
| 클래스 | 객체 지향 구조 | 도메인 모델, 클래스 관계 |
| 시퀀스 | 상호작용 흐름 | API 호출, 인증 흐름 |
| ER | 데이터 모델 | DB 스키마, 엔티티 관계 |
| 컴포넌트 | 시스템 구조 | 마이크로서비스, 모듈 구조 |
| 상태 | 상태 전이 | 주문 상태, 워크플로우 |
| 플로우차트 | 프로세스 흐름 | 비즈니스 로직, 알고리즘 |

## Mermaid 코드 생성

- command-architect 스킬 참조
- command-mermaid-diagrams 스킬의 문법 활용
- `.md` 파일로 Mermaid 코드 저장

## PNG 변환

```bash
mmdc -i <file>.md -o <file>.png
```

- mmdc CLI 사용 (@mermaid-js/mermaid-cli)
- 미설치 시 설치 가이드 제공

## 관련 스킬

- `command-architect` - `.claude/skills/command-architect/SKILL.md`
- `command-mermaid-diagrams` - `.claude/skills/command-mermaid-diagrams/SKILL.md`
