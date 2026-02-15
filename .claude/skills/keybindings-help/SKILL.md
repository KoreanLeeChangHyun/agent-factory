---
name: keybindings-help
description: Use when the user wants to customize keyboard shortcuts, rebind keys, add chord bindings, or modify ~/.claude/keybindings.json. Examples: "rebind ctrl+s", "add a chord shortcut", "change the submit key", "customize keybindings".
license: "Apache-2.0"
---

# Keybindings Help

Claude Code의 키보드 단축키를 커스터마이징하는 방법을 안내합니다.

## 사용 시기

- 키보드 단축키를 변경하고 싶을 때
- 새로운 단축키를 추가하고 싶을 때
- Chord 바인딩을 설정하고 싶을 때
- keybindings.json 파일을 수정해야 할 때

---

## 설정 파일 위치

키 바인딩 설정 파일: `~/.claude/keybindings.json`

## 기본 구조

```json
{
  "bindings": [
    {
      "key": "ctrl+s",
      "action": "submit",
      "description": "Submit the current input"
    }
  ]
}
```

## 지원되는 키 조합

### 수정자 키 (Modifiers)
- `ctrl` - Control 키
- `alt` - Alt/Option 키
- `shift` - Shift 키
- `meta` - Command(Mac) / Windows 키

### 조합 예시
- `ctrl+s` - Ctrl과 S
- `ctrl+shift+p` - Ctrl, Shift, P
- `alt+enter` - Alt와 Enter

## Chord 바인딩

두 개의 연속 키 조합:

```json
{
  "key": "ctrl+k ctrl+c",
  "action": "comment",
  "description": "Add comment"
}
```

## 일반적인 액션

| 액션 | 설명 |
|------|------|
| `submit` | 입력 제출 |
| `newline` | 새 줄 추가 |
| `cancel` | 취소 |
| `clear` | 화면 지우기 |
| `history-prev` | 이전 히스토리 |
| `history-next` | 다음 히스토리 |

## 예시 설정

```json
{
  "bindings": [
    {
      "key": "ctrl+enter",
      "action": "submit",
      "description": "Submit with Ctrl+Enter"
    },
    {
      "key": "ctrl+k ctrl+s",
      "action": "save",
      "description": "Save chord binding"
    },
    {
      "key": "escape",
      "action": "cancel",
      "description": "Cancel current operation"
    }
  ]
}
```

## 주의사항

- 설정 변경 후 Claude Code 재시작 필요
- 충돌하는 키 바인딩 주의
- 시스템 단축키와 겹치지 않도록 설정
