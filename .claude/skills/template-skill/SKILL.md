---
name: template-skill
description: "새 스킬 생성 시 참고할 수 있는 템플릿 스킬. 이 스킬을 직접 사용하지 마세요. Use for skill template reference only: skill-manager 스킬을 사용하여 새 스킬을 만드세요. 이 파일은 SKILL.md 구조의 참고 자료 역할만 합니다."
disable-model-invocation: true
---

# Template Skill

이 파일은 새 스킬 생성 시 복사하여 사용할 수 있는 템플릿입니다.

## 사용 방법

### 자동 생성 (권장)

skill-manager 스킬을 사용하여 새 스킬을 자동으로 생성할 수 있습니다:

```
cc:implement "PDF 처리 스킬 만들어줘"
```

### 수동 생성

1. 이 디렉토리를 복사하여 새 스킬 디렉토리 생성
   ```bash
   cp -r .claude/skills/template-skill .claude/skills/my-new-skill
   ```
2. `name`과 `description`을 실제 스킬에 맞게 수정
3. 본문에 스킬 사용 지침 작성

## 관련 스킬

- `.claude/skills/command-skill-manager/SKILL.md` - 스킬 생성/수정 자동화

## 참고

새 스킬 생성 시 `cc:implement` 명령어 또는 command-skill-manager 스킬 사용을 권장합니다.
