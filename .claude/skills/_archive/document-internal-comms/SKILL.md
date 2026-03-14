---
name: document-internal-comms
description: A set of resources to help me write all kinds of internal communications, using the formats that my company likes to use. Claude should use this skill whenever asked to write some sort of internal communications (status reports, leadership updates, 3P updates, company newsletters, FAQs, incident reports, project updates, etc.).
license: Complete terms in LICENSE.txt
---

## 이 스킬을 사용하는 시기
내부 커뮤니케이션을 작성할 때, 다음 항목에 이 스킬을 사용한다:
- 3P 업데이트 (Progress, Plans, Problems)
- 회사 뉴스레터
- FAQ 답변
- 상태 보고서
- 리더십 업데이트
- 프로젝트 업데이트
- 인시던트 보고서

## 이 스킬을 사용하는 방법

내부 커뮤니케이션을 작성하려면:

1. 요청에서 **커뮤니케이션 유형을 파악한다**
2. `examples/` 디렉터리에서 **적절한 가이드라인 파일을 불러온다**:
    - `examples/3p-updates.md` - 진행상황/계획/문제 팀 업데이트
    - `examples/company-newsletter.md` - 전사 뉴스레터
    - `examples/faq-answers.md` - 자주 묻는 질문 답변
    - `examples/general-comms.md` - 위 항목에 명시적으로 해당하지 않는 그 외 모든 것
3. 해당 파일의 **구체적인 지침을 따른다** (형식, 톤, 내용 수집)

커뮤니케이션 유형이 기존 가이드라인과 일치하지 않는 경우, AskUserQuestion 도구를 사용하여 원하는 형식에 대한 설명이나 추가 컨텍스트를 요청한다.

## 키워드
3P updates, company newsletter, company comms, weekly update, faqs, common questions, updates, internal comms
