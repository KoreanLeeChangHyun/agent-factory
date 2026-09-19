---
name: rule-documents
description: 프로젝트 문서 규칙을 확인할 때 사용합니다.
metadata:
  document-type: specification
  category: rule
  domain: null
  name: documents
  language: ko
  provenance:
    prior-provenance: null
    merged-from:
    - docs/skills/rule-documents/SKILL.md
    source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
    merge-request: run-20260918T152016183617Z-2d18ad49
    source-metadata:
      name: rule-documents
      description: Classify, create, move, or review repository documents using the
        Original, Processed, and Specification lifecycle. Use for documentation structure,
        promotion, provenance, and deciding whether knowledge belongs in docs or a
        project Skill.
---


# 프로젝트 문서 규칙

<a id="문서-유형과-권한"></a>

## 1. 문서 유형과 권한

- 적용 대상은 이 저장소의 프로젝트 문서입니다. 클라우드 서비스의 데이터·API 계약을 변경하는 지시가 아닙니다.

| 유형 | 정본 위치 | 내용 |
| --- | --- | --- |
| Original | `docs/original/<category>-<name>/metadata.yaml` | 외부 원본의 메타데이터와 링크 |
| Processed | `docs/processed/<category>-<name>/SKILL.md` | 조사·분석·인터뷰·과거 결정과 실행 기록 |
| Specification | `docs/skills/<category>-<name>/SKILL.md` | 사용자가 명시적으로 요청한 현재 사실·규칙·설계 |

- 유형은 권한과 목적에 따라 정합니다. 작성·형식 개선·구현 일치만으로 Processed를 명세로 승격하지 않습니다.
- 명세 분류는 `info`, `rule`, `design`입니다. 기획과 기술 설계는 모두 `design`으로 관리합니다.
- Original 없이 Processed를 작성하거나 사용자가 직접 명세를 확정할 수 있습니다. 세 유형은 필수 단계가 아닙니다.

<a id="본문과-출처"></a>

## 2. 본문과 출처

- Processed와 명세는 `SKILL.md` 하나와 필요한 `assets/`로 구성합니다. 별도 `references/`·`agents/`·`scripts/`를 두지 않습니다.
- Original에는 `metadata.yaml` 하나만 두고 원본 본문이나 자산을 복사하지 않습니다.
- 사용자 언어로 작성하되 원문·인용·코드·식별자와 실제 출처를 보존합니다. 번역이나 내용 변경은 별도 요청 범위를 따릅니다.
- 명세는 현재 기준을 본문에서 완결되게 설명합니다. 과거 결정·구현 기록·대체된 설계는 Processed에 둡니다.
- 같은 의미를 중복 작성하지 않고 소유 문서로 연결합니다. 충돌하거나 미확정인 결정을 자동 확정하지 않습니다.
- 독립 JSON·CSV·이미지와 인터페이스 자료는 `assets/`에 두고 본문에서 사용 위치와 권한을 설명합니다.
- 비밀·자격 증명·사용자 업로드·빌드 결과·런타임 로그는 문서에 저장하지 않습니다.

<a id="단일-원본과-동기화"></a>

## 3. 단일 원본과 동기화

- 상위 Agent Factory 저장소의 `docs/`가 프로젝트 문서 정본입니다. `docs/specification/`·`docs/mcp/`나 별도 HTML 명세를 편집 원본으로 운영하지 않습니다.
- `.codex/skills/`는 `docs/skills/`의 파생본입니다. 정본을 수정한 후 Document 스킬의 동기화 스크립트를 상위 프로젝트 루트에 직접 실행하고 결과를 확인합니다.
- `original`·`processed`는 Codex Skill로 동기화하지 않습니다. 설치·배포용 `plugin/skills/`는 이 문서 패키지와 구분합니다.
- 문서를 이동하거나 병합할 때 실제 출처, 고유한 내용, 첨부와 직접 참조를 보존하고 링크·사용 코드·테스트를 함께 조정합니다.
