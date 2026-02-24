# FastAPI Project Structure Template

프로덕션 레디 FastAPI 프로젝트의 전체 구조 템플릿입니다.

## 디렉토리 구조

```
<project-name>/
│
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 앱 진입점
│   ├── config.py               # 전역 설정 (Pydantic Settings)
│   ├── database.py             # DB 엔진, 세션 팩토리
│   ├── exceptions.py           # 전역 예외 클래스
│   │
│   ├── auth/                   # 인증/인가 도메인
│   │   ├── __init__.py
│   │   ├── router.py           # /auth/* 엔드포인트
│   │   ├── schemas.py          # TokenResponse, LoginRequest 등
│   │   ├── models.py           # RefreshToken 모델 (선택)
│   │   ├── service.py          # 토큰 생성/검증 로직
│   │   ├── dependencies.py     # get_current_user, require_role
│   │   ├── config.py           # JWT 설정
│   │   ├── constants.py        # 토큰 타입 상수
│   │   ├── exceptions.py       # InvalidTokenError 등
│   │   └── utils.py            # 비밀번호 해싱
│   │
│   ├── users/                  # 사용자 도메인
│   │   ├── __init__.py
│   │   ├── router.py           # /users/* 엔드포인트
│   │   ├── schemas.py          # UserCreate, UserResponse 등
│   │   ├── models.py           # User SQLAlchemy 모델
│   │   ├── service.py          # CRUD 비즈니스 로직
│   │   ├── dependencies.py     # 사용자 검증 의존성
│   │   └── exceptions.py       # UserNotFoundError 등
│   │
│   └── <domain>/               # 추가 도메인 (동일 패턴)
│       ├── __init__.py
│       ├── router.py
│       ├── schemas.py
│       ├── models.py
│       ├── service.py
│       └── dependencies.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # pytest fixtures
│   │
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── test_router.py
│   │   └── test_service.py
│   │
│   └── users/
│       ├── __init__.py
│       ├── test_router.py
│       └── test_service.py
│
├── alembic/
│   ├── env.py                  # Alembic 환경 설정
│   ├── script.py.mako          # 마이그레이션 템플릿
│   └── versions/               # 마이그레이션 파일
│       └── .gitkeep
│
├── requirements/
│   ├── base.txt                # 공통 의존성
│   ├── dev.txt                 # 개발 의존성
│   └── prod.txt                # 프로덕션 의존성
│
├── scripts/
│   ├── start.sh                # 개발 서버 시작
│   └── migrate.sh              # 마이그레이션 실행
│
├── .env.example                # 환경 변수 예시
├── .gitignore
├── alembic.ini                 # Alembic 설정
├── pyproject.toml              # 프로젝트 메타데이터
└── README.md
```

## 핵심 파일 템플릿

### pyproject.toml

```toml
[project]
name = "<project-name>"
version = "0.1.0"
description = "<project-description>"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]
ignore = ["E501"]
```

### .env.example

```env
# App
PROJECT_NAME=FastAPI App
VERSION=0.1.0
DEBUG=false

# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname

# Security
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS
ALLOWED_ORIGINS=["http://localhost:3000"]
```

### requirements/base.txt

```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
pydantic>=2.6.0
pydantic-settings>=2.1.0
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.29.0
alembic>=1.13.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
python-multipart>=0.0.6
httpx>=0.26.0
```

### requirements/dev.txt

```
-r base.txt
pytest>=8.0.0
pytest-asyncio>=0.23.0
pytest-cov>=4.1.0
ruff>=0.2.0
pre-commit>=3.6.0
```

### requirements/prod.txt

```
-r base.txt
gunicorn>=21.2.0
```

### alembic.ini

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os

[post_write_hooks]
hooks = ruff
ruff.type = exec
ruff.executable = ruff
ruff.options = format REVISION_SCRIPT_FILENAME

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

### alembic/env.py

```python
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from src.config import settings
from src.database import Base
# Import all models here
from src.users.models import User

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### tests/conftest.py

```python
import asyncio
from typing import AsyncGenerator

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.main import app
from src.database import Base, get_db


TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(TEST_DATABASE_URL, echo=True)
TestingSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
```

### scripts/start.sh

```bash
#!/bin/bash
set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Run migrations
alembic upgrade head

# Start server
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### .gitignore

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
.venv/
ENV/

# Testing
.pytest_cache/
.coverage
htmlcov/

# IDEs
.idea/
.vscode/
*.swp
*.swo

# Environment
.env
*.local

# Database
*.db
*.sqlite3

# Logs
*.log

# OS
.DS_Store
Thumbs.db
```
