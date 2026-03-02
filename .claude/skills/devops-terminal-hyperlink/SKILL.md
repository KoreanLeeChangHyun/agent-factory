---
name: devops-terminal-hyperlink
description: OSC 8 터미널 하이퍼링크 가이드. 클릭 가능한 파일/URL 링크를 터미널 출력에 삽입하는 방법을 제공한다. Use when: (1) Bash/Python 스크립트에서 클릭 가능한 경로 출력이 필요할 때, (2) 배너/상태줄에 하이퍼링크를 삽입할 때, (3) 터미널 출력에서 파일 경로를 라벨로 표시할 때. Triggers: 'terminal link', 'hyperlink', 'OSC 8', '터미널 링크', '클릭 가능한 경로'.
---

# OSC 8 터미널 하이퍼링크

## 구문

```
\033]8;;<URL>\a<라벨텍스트>\033]8;;\a
```

| 요소 | 값 | 설명 |
|------|---|------|
| OSC 시작 | `\033]8;;` | ESC ] 8 ; ; |
| URL | `file:///abs/path` 또는 `https://...` | URI 스킴 필수 |
| ST (종료자) | `\a` (BEL, 0x07) | `\033\\` (ESC \\) 대신 **BEL 사용 필수** |
| 라벨 | 임의 텍스트 | 사용자에게 보이는 텍스트 |
| 링크 종료 | `\033]8;;\a` | URL 없이 OSC 8 닫기 |

## 종료자: BEL vs ST

```
\a        (BEL, 0x07)  — 사용. 상태줄/echo -e/Bash에서 안정적
\033\\    (ESC \\)     — 사용 금지. echo -e가 \\ 를 재해석하여 깨짐
```

## Bash

```bash
# printf 권장 (escape 바이트를 직접 출력)
osc8_link() {
    local ABS_PATH="$1" LABEL="$2"
    printf '\033]8;;file://%s\a%s\033]8;;\a' "$ABS_PATH" "$LABEL"
}

# 사용: ANSI 색상과 조합 시 printf %b + %s 분리
LINK=$(osc8_link "/home/user/file.txt" "file.txt")
printf '%b%s%b\n' '\033[2m' "$LINK" '\033[0m'
```

**echo -e 금지**: 링크 변수를 `echo -e` 안에 넣으면 BEL/ESC 바이트가 재해석됨.<br>
ANSI 색상은 `%b`로, 링크는 `%s`로 분리하여 `printf`에 전달.

## Python

```python
def osc8_link(abs_path: str, label: str) -> str:
    return f"\033]8;;file://{abs_path}\a{label}\033]8;;\a"

# 사용
link = osc8_link("/home/user/report.md", "report.md")
print(f"\033[2m{link}\033[0m")
```

## 주의사항

- URI에 공백이 있으면 `%20`으로 인코딩
- `file://` URI는 절대 경로만 사용 (상대 경로 불가)
- URI 최대 길이: 2083 바이트 (VTE/iTerm2 제한)
- 미지원 터미널은 라벨 텍스트만 표시 (graceful degradation)

## 지원 터미널

iTerm2 3.1+, Kitty, WezTerm, Windows Terminal, GNOME Terminal (VTE 0.50+), Ghostty, Konsole, Alacritty, foot
