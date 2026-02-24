# 작업 수행 명령어 템플릿

파일 수정, 배포, 커밋 등 부작용이 있는 명령어입니다.
`disable-model-invocation: true`로 사용자만 호출 가능하게 설정합니다.

## 템플릿

```yaml
---
name: <명령어-이름>
description: <무엇을 하는지>
disable-model-invocation: true
context: fork
---

$ARGUMENTS에 대해 수행:

1. <단계1>
2. <단계2>
3. <단계3>
4. <검증>
```

## 예시: 배포 명령어

```yaml
---
name: deploy
description: 애플리케이션을 프로덕션에 배포
disable-model-invocation: true
context: fork
---

$ARGUMENTS 환경으로 배포:

1. 테스트 스위트 실행
2. 애플리케이션 빌드
3. 배포 대상에 푸시
4. 배포 성공 확인
```

## 예시: 커밋 명령어

```yaml
---
name: commit
description: 변경사항을 커밋
disable-model-invocation: true
---

현재 변경사항 커밋:

1. `git status`로 변경 파일 확인
2. `git diff`로 변경 내용 확인
3. 최근 커밋 메시지 스타일 확인
4. 변경사항 분석하여 커밋 메시지 작성
5. 관련 파일 스테이징
6. 커밋 생성

## 커밋 메시지 형식

```
<type>: <제목>

<본문 (선택)>

Co-Authored-By: Claude <noreply@anthropic.com>
```

type: feat, fix, refactor, docs, test, chore
```

## 예시: PR 생성 명령어

```yaml
---
name: create-pr
description: Pull Request 생성
disable-model-invocation: true
argument-hint: "[base-branch]"
---

$ARGUMENTS (기본: main) 브랜치로 PR 생성:

1. 현재 브랜치 상태 확인
2. base 브랜치와 diff 분석
3. 모든 커밋 분석 (최근 커밋만 아닌 전체)
4. PR 제목과 설명 작성
5. `gh pr create` 실행

## PR 형식

```markdown
## Summary
<1-3 bullet points>

## Test plan
- [ ] 테스트 항목

Generated with Claude Code
```
```

## 예시: 이슈 수정 명령어

```yaml
---
name: fix-issue
description: GitHub 이슈 수정
disable-model-invocation: true
argument-hint: "[issue-number]"
---

GitHub 이슈 #$ARGUMENTS 수정:

1. `gh issue view $ARGUMENTS`로 이슈 내용 확인
2. 요구사항 분석
3. 관련 코드 탐색
4. 수정 구현
5. 테스트 작성/실행
6. 커밋 생성
```

## 예시: 리팩토링 명령어

```yaml
---
name: refactor
description: 코드 리팩토링 수행
disable-model-invocation: true
argument-hint: "[file-or-function]"
---

$ARGUMENTS 리팩토링:

1. 현재 코드 분석
2. 리팩토링 계획 수립
3. 테스트 존재 확인 (없으면 먼저 작성)
4. 단계별 리팩토링
5. 각 단계마다 테스트 실행
6. 변경사항 요약
```
