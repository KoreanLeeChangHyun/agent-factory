---
name: devops-docker-compose
description: "Configures Docker Compose-based local development environments and multi-container orchestration. Covers service networking, volume and environment variable management, and docker-compose.yml best practices. Use when setting up a local dev environment with Docker or docker-compose, orchestrating multi-container services, configuring inter-service networking, managing volumes and env vars, or defining container health checks and dependency ordering."
license: "Apache-2.0"
---

# Docker Compose 스킬

Docker Compose 기반 로컬 개발 환경 구성 및 멀티 컨테이너 오케스트레이션 가이드.

## 파일 구조 원칙

```
project/
├── docker-compose.yml        # 개발 환경 (기본)
├── docker-compose.prod.yml   # 프로덕션 오버라이드
├── docker-compose.test.yml   # 테스트 환경
├── .env                      # 환경변수 (git 제외)
├── .env.example              # 환경변수 예시 (git 포함)
└── services/
    ├── app/Dockerfile
    └── db/init.sql
```

## docker-compose.yml 베스트 프랙티스

### 기본 구조

```yaml
version: "3.9"

services:
  app:
    build:
      context: .
      dockerfile: services/app/Dockerfile
      target: development          # 멀티스테이지 타겟
    ports:
      - "${APP_PORT:-8000}:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/mydb
      - REDIS_URL=redis://redis:6379
    env_file:
      - .env
    volumes:
      - .:/app                     # 핫리로드용 바인드 마운트
      - /app/node_modules          # 익명 볼륨으로 호스트 node_modules 차단
    depends_on:
      db:
        condition: service_healthy  # 헬스체크 기반 의존성
      redis:
        condition: service_started
    networks:
      - backend
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${DB_NAME:-mydb}
      POSTGRES_USER: ${DB_USER:-user}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-password}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./services/db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    ports:
      - "${DB_PORT:-5432}:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-user} -d ${DB_NAME:-mydb}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    networks:
      - backend

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    networks:
      - backend

volumes:
  postgres_data:
  redis_data:

networks:
  backend:
    driver: bridge
```

## 핵심 패턴

### 환경변수 관리

```bash
# .env.example (반드시 커밋)
APP_PORT=8000
DB_NAME=mydb
DB_USER=user
DB_PASSWORD=changeme   # 실제값은 .env에서 교체
```

- `.env`는 `.gitignore`에 추가, `.env.example`만 커밋
- 하드코딩 금지: 모든 시크릿은 `${VAR:-default}` 패턴
- 프로덕션 시크릿은 Docker Secrets 또는 외부 시크릿 매니저 사용

### 멀티스테이지 Dockerfile

```dockerfile
# 개발 스테이지
FROM node:20-alpine AS development
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
USER node
CMD ["npm", "run", "dev"]

# 프로덕션 스테이지
FROM node:20-alpine AS production
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build
USER node
CMD ["node", "dist/main.js"]
```

### 오버라이드 파일 패턴

```yaml
# docker-compose.prod.yml
services:
  app:
    build:
      target: production
    volumes: []           # 바인드 마운트 제거
    environment:
      NODE_ENV: production
```

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up
```

## 주요 명령어

```bash
# 빌드 후 시작 (백그라운드)
docker-compose up -d --build

# 특정 서비스만 재시작
docker-compose restart app

# 로그 스트리밍
docker-compose logs -f app

# 컨테이너 내부 접근
docker-compose exec app sh

# 완전 초기화 (볼륨 포함)
docker-compose down -v

# 헬스 상태 확인
docker-compose ps
```

## 자주 발생하는 문제

| 증상 | 원인 | 해결 |
|------|------|------|
| 서비스 연결 실패 | `localhost` 사용 | 서비스명으로 교체 (`db`, `redis`) |
| 볼륨 권한 오류 | 호스트/컨테이너 UID 불일치 | `user: "${UID}:${GID}"` 설정 |
| 포트 충돌 | 호스트 포트 점유 | `.env`에서 포트 변수화 |
| 코드 변경 미반영 | 이미지 캐시 | `--build` 플래그 추가 |
| DB 초기화 안 됨 | 볼륨 잔존 | `docker-compose down -v` 후 재시작 |
