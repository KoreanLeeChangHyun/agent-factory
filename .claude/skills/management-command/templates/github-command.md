# GitHub 연동 명령어 템플릿

GitHub CLI(`gh`)를 사용하여 동적으로 컨텍스트를 주입하는 명령어입니다.
`!`command`` 문법으로 명령어 실행 전 데이터를 가져옵니다.

## 동적 컨텍스트 주입

`!`command`` 문법은 명령어가 Claude에게 전달되기 전에 실행됩니다:
1. 각 `!`command``가 즉시 실행됨
2. 출력이 플레이스홀더를 대체
3. Claude는 실제 데이터가 포함된 최종 프롬프트를 받음

## 템플릿

```yaml
---
name: <명령어-이름>
description: <무엇을 하는지>
context: fork
agent: Explore
allowed-tools: Bash(gh *)
---

## 컨텍스트
- 데이터1: !`gh command1`
- 데이터2: !`gh command2`

## 수행 작업
<위 데이터를 바탕으로 할 일>
```

## 예시: PR 요약 명령어

```yaml
---
name: devops-pr-summary
description: Pull Request 변경사항 요약
context: fork
agent: Explore
allowed-tools: Bash(gh *)
---

## PR 컨텍스트
- PR diff: !`gh pr diff`
- PR 코멘트: !`gh pr view --comments`
- 변경 파일: !`gh pr diff --name-only`

## 수행 작업
이 PR을 다음 형식으로 요약:

1. **목적**: PR이 해결하는 문제
2. **주요 변경**: 핵심 변경사항 3-5개
3. **영향 범위**: 영향받는 컴포넌트
4. **리뷰 포인트**: 주의깊게 볼 부분
```

## 예시: 이슈 분석 명령어

```yaml
---
name: analyze-issue
description: GitHub 이슈 분석 및 해결 방안 제시
argument-hint: "[issue-number]"
context: fork
agent: Explore
---

## 이슈 컨텍스트
- 이슈 내용: !`gh issue view $ARGUMENTS`
- 관련 코멘트: !`gh issue view $ARGUMENTS --comments`

## 수행 작업
1. 이슈 요구사항 정리
2. 관련 코드 탐색
3. 해결 방안 제시
4. 예상 작업량 추정
```

## 예시: 릴리스 노트 생성 명령어

```yaml
---
name: release-notes
description: 마지막 릴리스 이후 변경사항으로 릴리스 노트 생성
context: fork
agent: Explore
allowed-tools: Bash(gh *, git *)
---

## 릴리스 컨텍스트
- 마지막 태그: !`git describe --tags --abbrev=0`
- 커밋 목록: !`git log $(git describe --tags --abbrev=0)..HEAD --oneline`
- PR 목록: !`gh pr list --state merged --limit 50`

## 릴리스 노트 생성

위 정보를 바탕으로 릴리스 노트 작성:

## [버전] - 날짜

### Added
- 새로운 기능

### Changed
- 변경사항

### Fixed
- 버그 수정

### Deprecated
- 더 이상 사용하지 않는 기능
```

## 예시: 코드 리뷰 요청 명령어

```yaml
---
name: review-request
description: PR에 대한 코드 리뷰 수행
context: fork
agent: Explore
allowed-tools: Read, Grep, Glob, Bash(gh *)
---

## PR 정보
- 변경 파일: !`gh pr diff --name-only`
- 전체 diff: !`gh pr diff`

## 리뷰 수행

각 변경 파일에 대해:

1. **코드 품질**: 가독성, 유지보수성
2. **버그 위험**: 잠재적 버그
3. **보안**: 취약점 검사
4. **테스트**: 테스트 커버리지
5. **성능**: 성능 이슈

## 리뷰 결과 형식

| 파일 | 라인 | 심각도 | 코멘트 |
|------|------|--------|--------|
```

## 주의사항

1. `!`command``는 전처리이므로 Claude가 실행하는 것이 아님
2. 명령어 실패시 에러 메시지가 컨텍스트에 포함됨
3. 대용량 출력 주의 (컨텍스트 윈도우 제한)
4. `gh` 명령어는 GitHub 인증이 필요
