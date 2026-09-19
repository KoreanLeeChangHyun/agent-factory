---
name: organization-github-alignment
description: GitHub에 가까운 조직 관리 방향을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/organization-github-alignment.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
---


# GitHub에 가까운 조직 관리 방향

- 2026-09-06 사용자 지침: 개발자용 사이트이므로 조직을 최대한 Git과 비슷하게 구성한다. 여기서는 조직 관리가 있는 GitHub를 참조 대상으로 해석한다. 아래는 현재 구현과의 차이를 정리한 후속 설계이며, 기존 1–12 구현 완료 기록과 구분한다. 아래 화면 구조는 2026-09-06 구현에 반영했다.

<a id="화면탐색"></a>

## 1. 화면·탐색

| 영역 | 현재 | 후속 변경 방향 |
|---|---|---|
| 조직 정체성 | 이름과 UUID 코드 | 구현됨: 표시 이름과 읽기 쉬운 고유 식별자(slug)를 중심으로 표시. UUID는 설정의 기술 정보로 이동 |
| 첫 화면 | 구성원 | 구현됨: 조직 개요, 접근 가능한 작업공간, 구성원·팀·초대 요약 |
| 조직 메뉴 | 구성원·팀·역할 및 권한·설정 | 구현됨: 개요·작업공간·구성원·팀·설정. 역할 및 권한은 설정 안으로 배치 |
| 구성원 | 목록·초대 폼·초대 이력 연속 표시 | 구현됨: 구성원과 대기 초대를 구분하고 검색·역할·상태 필터 및 초대 버튼 제공 |
| 팀 | 팀 목록·편집 | 구현됨: 팀 상세에서 구성원과 접근 가능한 작업공간을 분리해 관리 |
| 설정 | 정보·생성·이전·삭제·이력 연속 표시 | 구현됨: 일반·역할 및 권한·감사 로그를 구분하고 소유권 이전·삭제는 위험 작업 영역에 배치 |

<a id="권한"></a>

## 2. 권한

- GitHub는 조직 역할과 저장소 역할을 분리하며 개인·팀에 저장소 접근 권한을 부여한다. 이 제품에서는 실제 권한 경계인 작업공간을 같은 위치에 둔다. 작업공간 안의 연결 저장소를 작업공간과 같은 개념으로 이름만 바꾸지 않는다.

- 기본 흐름은 조직 소유자/구성원과 작업공간별 역할 선택을 중심으로 단순화한다. 기존 조직 관리자와 사용자 지정 역할은 유지하며, GitHub처럼 보이게 하려고 현재 역할을 삭제하거나 구성원의 유효 권한을 자동으로 확대하지 않는다.

- 사용자가 요청한 개별 스코프 설정은 사용자 지정 역할에서 계속 제공한다. 권한은 작업공간에 직접 또는 팀을 통해 부여하고, 구성원 상세에서 최종 권한과 부여 경로를 확인한다. 기본 역할 선택 뒤 필요한 경우 개별 스코프를 조정하는 방향으로 설계한다. 현재 시스템 기본 역할 자체는 수정할 수 없다.

- GitHub의 저장소 역할 Read/Triage/Write/Maintain/Admin은 참고 자료다. 이 제품에는 GitHub issue/PR triage와 같은 행동이 없으므로 대응하지 않는 이름·권한을 만들지 않는다. 조직 전체 기본 접근권한, 중첩 팀, 외부 협업자는 GitHub에 존재하지만 별도 데이터·권한 설계가 필요한 확장이다. 기존 격리를 바꾸는 기능은 화면 정리와 구별해 구현한다.

<a id="구현-순서와-확인-기준"></a>

## 3. 구현 순서와 확인 기준

1. [x] 조직 개요 및 탐색 재배치: 조직 전환, 작업공간 진입이 현재 조직을 유지한다.
2. [x] 이름/slug 표시: 생성 시 고유성·형식 검증, 표시 이름과 식별자 구분, 기존 UUID API 유지.
   공개 프로필·공개 URL·GitHub 계정 연결은 slug 표시만으로 제공됐다고 간주하지 않는다.
3. [x] 구성원·초대·팀 상세 정리: 기존 초대·상태·역할·배정 기능을 같은 권한 검사 아래 유지한다.
4. [x] 설정 하위 역할·감사 로그·위험 작업 분리: 세부 스코프와 설명, 소유자 보호를 유지한다.
5. [x] 브라우저 흐름과 기존 권한 회귀 검증: 메뉴·작업공간·필터·초대·팀·역할 프리셋·
   세부 스코프·감사 로그·위험 작업·조직 전환을 확인했고 기존 권한 검증도 통과했다.

<a id="검증-기록"></a>

## 4. 검증 기록

- 새 PostgreSQL의 비관리자 강제 RLS 세션에서 조직 검증 5개 통과. slug 생성·형식·중복·
  변경, 30자 자동 생성 경계, 기존 구성원·초대·팀·역할·소유자·토큰 격리를 포함한다.
- 실제 Chromium 조직 흐름 통과. 39자 UI 자동 생성 경계, `my-org` 순차 입력, 메뉴 순서,
  작업공간 화면, 구성원 검색·역할·상태 필터, 대기 초대, 역할 프리셋과 세부 스코프,
- 감사 로그, 소유권 이전·삭제의 위험 작업 배치, 조직 전환을 확인한다.
- 독립 검증자가 같은 집중 검증을 다시 실행해 통과했으며 1–9 완료를 승인했다.

<a id="공식-참고-자료"></a>

## 5. 공식 참고 자료

- [GitHub 조직](https://docs.github.com/en/organizations/collaborating-with-groups-in-organizations/about-organizations)
- [조직의 기본 역할](https://docs.github.com/en/organizations/managing-peoples-access-to-your-organization-with-roles/permissions-of-predefined-organization-roles)
- [저장소 역할](https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/repository-roles-for-an-organization)
- [팀](https://docs.github.com/en/organizations/organizing-members-into-teams/about-teams)
- [조직 프로필](https://docs.github.com/en/organizations/collaborating-with-groups-in-organizations/customizing-your-organizations-profile)
