---
description: Claude Code 사용자 환경 초기화. Shell alias, StatusLine, Slack 환경변수, Git global 설정을 수행합니다. 사용자 환경에 1회 실행합니다.
---

# Initialize Claude Environment

Claude Code 사용을 위한 사용자 환경을 초기화합니다.

**실행 시점:** 사용자 환경에 1회 (새 머신에서 Claude Code 처음 사용 시)

## 스크립트

`.claude/hooks/init/init-claude.sh` - 서브커맨드: check-alias, setup-alias, setup-statusline, setup-slack, setup-git, verify

## 오케스트레이션 흐름

아래 순서대로 실행합니다. 각 단계에서 Bash 도구로 스크립트를 호출하고, 결과 JSON을 파싱하여 다음 단계를 결정합니다.

### Step 1. Shell Alias 체크

Bash 도구로 실행:

```bash
wf-claude check-alias
```

**결과 JSON 예시:**
```json
{"status":"ok","cc_exists":true,"ccc_exists":true,"cc_value":"alias cc='...'","ccc_value":"alias ccc='...'"}
```

**분기:**
- `cc_exists` 또는 `ccc_exists`가 `true`인 경우 -> Step 2 (사용자 확인)
- 둘 다 `false`인 경우 -> Step 3 (바로 설정)

### Step 2. Alias 덮어쓰기 확인 (대화형)

**AskUserQuestion** 으로 사용자에게 확인:
- 질문: "기존 alias가 있습니다. 덮어쓰시겠습니까? [yes/no]"
  - 현재 값: `cc_value`, `ccc_value` 표시
- `yes` -> Step 3
- `no` -> Step 4 (alias 스킵)

### Step 3. Alias 설정

Bash 도구로 실행:

```bash
wf-claude setup-alias
```

PATH export(`~/.local/bin`)와 alias(cc, ccc)가 블록 마커 안에 함께 설정됩니다. 결과 메시지 출력 후 Step 4로 진행.

### Step 4. StatusLine 설정

Bash 도구로 실행:

```bash
wf-claude setup-statusline
```

결과 JSON에서 `settings_updated`, `script_created` 확인 후 결과 메시지 출력.

### Step 5. Slack Webhook URL 입력 (대화형)

**AskUserQuestion** 으로 사용자에게 입력 요청:
- 질문: "Slack Webhook URL을 입력해주세요. (스킵하려면 'skip' 입력)"
- 입력값 검증: URL 형식 (`https://`로 시작) 또는 `skip`
- URL 형식 오류 시 AskUserQuestion으로 재입력 요청

**분기:**
- `skip` -> Step 7 (Git 설정)
- URL 입력 -> Step 6

### Step 6. Slack 설정

Bash 도구로 실행 (URL은 사용자 입력값):

```bash
wf-claude setup-slack "<입력받은_URL>"
```

결과 메시지 출력 후 Step 7로 진행.

### Step 7. Git Global 설정

Bash 도구로 실행:

```bash
wf-claude setup-git
```

**결과 JSON 분기:**
- `status: "skip"` -> `.claude.env` 파일이 생성됨. 편집 후 재실행 안내 메시지 출력.
- `status: "ok"` -> Before/After 비교 테이블 출력:

```
| 설정 | Before | After |
|------|--------|-------|
| user.name | (before.user_name) | (after.user_name) |
| user.email | (before.user_email) | (after.user_email) |
| core.sshCommand | (before.ssh_command) | (after.ssh_command) |
```

- `status: "error"` -> 에러 메시지 출력, 계속 진행.

### Step 8. 전체 검증

Bash 도구로 실행:

```bash
wf-claude verify
```

결과 JSON의 `checks` 객체를 파싱하여 최종 결과 출력:

```
=== Claude Code 환경 초기화 완료 ===

[v] Shell Alias: cc, ccc 등록 완료
[v] PATH: ~/.local/bin 추가 완료
[v] StatusLine: settings.json, statusline.sh 설정 완료
[v] Slack: CLAUDE_CODE_SLACK_WEBHOOK_URL 설정 완료 (또는 스킵됨)
[v] Git: user.name, user.email 설정 완료 (또는 .env 편집 필요)

다음 단계:
1. source ~/.zshrc 실행하여 변경사항 적용
2. 터미널에서 cc 명령어로 Claude Code 시작
```

**verify가 확인하는 키 목록:**

| 키 | 소스 | 필수 |
|----|------|------|
| `alias cc`, `alias ccc` | `~/.zshrc` | 필수 |
| `statusLine` (settings.json) | `~/.claude/settings.json` | 필수 |
| `statusline.sh` (실행 권한) | `~/.claude/statusline.sh` | 필수 |
| `CLAUDE_CODE_SLACK_WEBHOOK_URL` | `.claude.env` 또는 `~/.zshrc` | 선택 |
| `CLAUDE_CODE_SLACK_BOT_TOKEN` | `.claude.env` (수동 설정) | 선택 |
| `~/.local/bin` in PATH | `~/.zshrc` (export PATH) | 필수 |
| `user.name`, `user.email` | `git config --global` | 필수 |

> **참고**: `CLAUDE_CODE_SLACK_BOT_TOKEN`은 `/init:claude` 오케스트레이션 흐름에서 자동 설정되지 않습니다. `.claude.env` 파일에 `CLAUDE_CODE_SLACK_BOT_TOKEN=xoxb-...` 형식으로 수동 설정할 수 있으며, verify 단계에서 Webhook URL과 함께 검증됩니다.

---

## 관련 명령어

| 명령어 | 설명 |
|--------|------|
| `/init:project` | 프로젝트 초기 구조 설정 (디렉토리, .gitignore, 빈 CLAUDE.md 템플릿). (프로젝트당 1회) |
| `/sync:context` | 코드베이스를 분석하여 CLAUDE.md를 생성/갱신합니다. 코드 변경 후 CLAUDE.md를 최신화할 때 수시로 실행 |
| `/init:workflow` | 워크플로우 초기화. CLAUDE.md 로드, workflow-orchestration 스킬 로드. (매 세션마다) |
| `/git:config` | .claude.env에서 Git 설정을 읽어 git config를 자동 설정합니다 |

---

## 사용자 재질의 원칙

**이 명령어 실행 중 사용자 입력이 필요한 경우 반드시 `AskUserQuestion` 도구를 사용합니다.**

| 상황 | AskUserQuestion 사용 |
|------|---------------------|
| 기존 alias 덮어쓰기 확인 | 필수 |
| Slack Webhook URL 입력 | 필수 |
| .env 파일 생성 후 편집 안내 | 메시지 출력만 (편집은 사용자가 직접) |

---

## 사전 조건

| 항목 | 설명 | 필수 |
|------|------|------|
| `wf-claude` 커맨드 | `~/.local/bin/wf-claude` wrapper 스크립트 (init-claude.sh 호출용) | 필수 |
| `python3` | settings.json JSON 병합에 사용 (setup-statusline) | 필수 |
| `~/.zshrc` | Shell alias, Slack export 등록 대상 (없으면 자동 생성) | 자동 |

## 오류 처리

| 오류 상황 | 대응 |
|----------|------|
| `~/.zshrc` 쓰기 권한 없음 | 에러 메시지 출력, 수동 설정 안내 |
| `~/.claude` 디렉토리 없음 | 스크립트가 자동 생성 |
| `.claude.env` 필수 필드 누락 | 해당 섹션 스킵, 편집 후 재실행 안내 |
| Slack URL 형식 오류 | AskUserQuestion으로 재입력 요청 |
| `python3` 미설치 | 에러 JSON 반환 (`error_detail: "python3 not found"`), python3 설치 안내 |
| `python3` JSON 병합 실패 | 에러 JSON 반환 (`error_detail`에 stderr 포함), settings.json 수동 편집 안내 |
