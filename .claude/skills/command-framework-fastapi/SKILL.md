---
name: command-framework-fastapi
description: "Provides production-ready FastAPI project structure and best practices including Domain-Driven directory layout, router/schema/service patterns, dependency injection, and async DB integration. Use for FastAPI development: project initialization, structure setup, API endpoint design, production pattern reference. Triggers: 'FastAPI', 'fastapi', 'Python API', 'Python 웹 서버'."
license: "Apache-2.0"
---

# FastAPI Framework Skill

확장 가능한 프로덕션 레디 FastAPI 프로젝트 구조와 베스트 프랙티스를 제공합니다.

## 프로젝트 구조 원칙

### Domain-Driven Structure (권장)

파일 타입이 아닌 **도메인/기능 단위**로 구조화:

```
project-name/
├── src/
│   ├── __init__.py
│   ├── main.py              # FastAPI 앱 진입점
│   ├── config.py            # 전역 설정
│   ├── database.py          # DB 연결 설정
│   ├── exceptions.py        # 전역 예외 클래스
│   │
│   ├── auth/                # 인증 도메인
│   │   ├── __init__.py
│   │   ├── router.py        # API 엔드포인트
│   │   ├── schemas.py       # Pydantic 모델
│   │   ├── models.py        # SQLAlchemy 모델
│   │   ├── service.py       # 비즈니스 로직
│   │   ├── dependencies.py  # 의존성 주입
│   │   ├── config.py        # 도메인별 설정
│   │   ├── constants.py     # 상수
│   │   ├── exceptions.py    # 도메인 예외
│   │   └── utils.py         # 유틸리티
│   │
│   ├── users/               # 사용자 도메인
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── schemas.py
│   │   ├── models.py
│   │   ├── service.py
│   │   └── dependencies.py
│   │
│   └── posts/               # 게시물 도메인 (예시)
│       └── ...
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # pytest fixtures
│   ├── auth/
│   │   └── test_router.py
│   └── users/
│       └── test_router.py
│
├── alembic/                 # DB 마이그레이션
│   ├── env.py
│   ├── versions/
│   └── alembic.ini
│
├── requirements/
│   ├── base.txt             # 기본 의존성
│   ├── dev.txt              # 개발 의존성
│   └── prod.txt             # 프로덕션 의존성
│
├── .env.example             # 환경 변수 예시
├── pyproject.toml           # 프로젝트 메타데이터
└── README.md
```

## 핵심 파일 구성

### src/main.py

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.auth.router import router as auth_router
from src.users.router import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users_router, prefix="/api/v1/users", tags=["users"])


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

### src/config.py

```python
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    PROJECT_NAME: str = "FastAPI App"
    VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str

    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
```

### src/database.py

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from src.config import settings


engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

## 도메인 모듈 패턴

### router.py

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.users import schemas, service
from src.auth.dependencies import get_current_user


router = APIRouter()


@router.get("/", response_model=list[schemas.UserResponse])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    return await service.get_users(db, skip=skip, limit=limit)


@router.get("/me", response_model=schemas.UserResponse)
async def get_current_user_info(
    current_user: schemas.UserResponse = Depends(get_current_user),
):
    return current_user
```

### schemas.py

```python
from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    username: str


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### service.py

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.users import models, schemas


async def get_users(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
) -> list[models.User]:
    result = await db.execute(
        select(models.User).offset(skip).limit(limit)
    )
    return result.scalars().all()


async def create_user(
    db: AsyncSession,
    user_data: schemas.UserCreate,
) -> models.User:
    user = models.User(**user_data.model_dump())
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user
```

## 베스트 프랙티스 요약

### Async 사용

- **async 라우트**: `await`로 비동기 I/O 처리
- **sync 라우트**: 스레드풀에서 실행 (블로킹 방지)
- **CPU 집약적 작업**: 별도 워커 프로세스 사용

### Pydantic 적극 활용

- 빌트인 validators 사용 (regex, enum, EmailStr 등)
- 커스텀 base model로 표준 강제
- 도메인별 설정 분리

### 의존성 주입

- 요청 범위 내 캐싱 활용
- 검증 로직을 의존성으로 분리
- 재사용 가능한 작은 의존성으로 체이닝

### 명시적 임포트

```python
# Good
from src.auth import constants as auth_constants

# Bad
from src.auth.constants import *
```

## 참조

- templates/structure.md - 전체 프로젝트 구조 템플릿
- references/best-practices.md - 상세 베스트 프랙티스
