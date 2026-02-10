---
description: 프로젝트 빌드 및 실행 스크립트(build.sh, run.sh)를 생성합니다.
---

# Build Scripts

## -np 플래그 (No-Plan 모드)

`$ARGUMENTS`에 `-np` 플래그가 포함된 경우 Tier 2 (no-plan) 모드로 실행합니다.

- `-np` 감지 시: init 에이전트 호출에 `mode: no-plan` 전달
- `-np` 미감지 시: 기존과 동일 (mode: full)

```
# -np 플래그 감지 예시
cc:build -np "빌드 스크립트 생성"
→ Task(subagent_type="init", prompt="command: build\nmode: no-plan")
```

## 프레임워크 감지

프로젝트 루트의 파일들을 분석하여 프레임워크를 감지합니다:

| 파일/패턴 | 프레임워크 | 빌드 명령 | 실행 명령 |
|-----------|------------|-----------|-----------|
| `requirements.txt` + `main.py` (FastAPI) | FastAPI | pip install | uvicorn |
| `requirements.txt` + `app.py` (Flask) | Flask | pip install | flask run / gunicorn |
| `requirements.txt` + `manage.py` | Django | pip install | python manage.py runserver |
| `package.json` + Next.js | Next.js | npm install && npm run build | npm run start |
| `package.json` + React | React | npm install && npm run build | npm run start / serve |
| `package.json` + Express | Express/Node | npm install | node / npm run start |
| `pom.xml` | Maven/Java | mvn clean package | java -jar |
| `build.gradle` | Gradle/Java | gradle build | java -jar |
| `go.mod` | Go | go build | ./<binary> |
| `Cargo.toml` | Rust | cargo build --release | ./target/release/<binary> |

## build.sh 생성

**필수 요구사항:**
- 가상 환경(venv) 구성 필수 (Python 프로젝트)
- Node.js 프로젝트는 node_modules 의존성 설치
- 빌드 아티팩트 생성

**템플릿 구조:**
```bash
#!/bin/bash
set -e

# 프로젝트 루트로 이동
cd "$(dirname "$0")"

echo "=== Build Script ==="
echo "Framework: <detected_framework>"
echo "===================="

# [Python 프로젝트의 경우]
# 가상 환경 생성 (없으면)
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# 가상 환경 활성화
source venv/bin/activate

# 의존성 설치
echo "Installing dependencies..."
pip install -r requirements.txt

# [빌드가 필요한 경우]
# npm run build, mvn package 등

echo "Build completed successfully!"
```

## run.sh 생성

**필수 요구사항:**
- 기존 포트 사용 프로세스 kill 후 실행
- 백그라운드/포그라운드 선택 가능
- PID 파일 관리 (선택)

**템플릿 구조:**
```bash
#!/bin/bash
set -e

# 프로젝트 루트로 이동
cd "$(dirname "$0")"

HOST="${1:-0.0.0.0}"
PORT="${2:-8000}"

echo "=== Run Script ==="
echo "Framework: <detected_framework>"
echo "Binding: ${HOST}:${PORT}"
echo "=================="

# 기존 포트 사용 프로세스 종료
if lsof -ti:${PORT} > /dev/null 2>&1; then
    echo "Killing existing process on port ${PORT}..."
    lsof -ti:${PORT} | xargs kill -9
    sleep 1
fi

# [Python 프로젝트의 경우]
# 가상 환경 활성화
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 서버 실행
echo "Starting server..."
# uvicorn main:app --host ${HOST} --port ${PORT}
# python manage.py runserver ${HOST}:${PORT}
# npm run start
# etc.
```

### 권한 설정

```bash
chmod 700 build.sh run.sh
```

## 프레임워크별 세부 설정

프레임워크별 상세 빌드/실행 설정은 해당 프레임워크 스킬을 참조합니다:

- Python (FastAPI): `command-framework-fastapi` 스킬
- React/Next.js: `command-framework-react` 스킬

## 출력 파일

| 파일 | 위치 | 권한 |
|------|------|------|
| build.sh | 프로젝트 루트 | 700 |
| run.sh | 프로젝트 루트 | 700 |

## 관련 스킬

| 스킬 | 용도 | 경로 |
|------|------|------|
| command-verification-before-completion | 빌드 스크립트 검증 | `.claude/skills/command-verification-before-completion/SKILL.md` |

## 주의사항

- 프레임워크 감지 실패 시 AskUserQuestion 도구로 사용자에게 확인 요청
- 기존 build.sh/run.sh 파일이 있으면 AskUserQuestion 도구로 백업/덮어쓰기 확인
- Windows 환경은 지원하지 않음 (bash 스크립트)
- 실행 전 build.sh를 먼저 실행해야 함
