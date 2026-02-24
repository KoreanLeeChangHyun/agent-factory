# FastAPI Best Practices

프로덕션 환경에서 검증된 FastAPI 베스트 프랙티스 모음입니다.

## 1. 프로젝트 구조

### Domain-Driven Design 적용

```python
# Good - 도메인별 분리
from src.auth import constants as auth_constants
from src.users import service as users_service

# Bad - 파일 타입별 분리 (확장성 저하)
from src.constants import AUTH_TOKEN_TYPE
from src.services import get_user
```

### 순환 참조 방지

```python
# Good - 명시적 모듈 임포트
from src.auth.dependencies import get_current_user

# Bad - 상대 임포트 남용
from ..auth.dependencies import get_current_user
```

## 2. 비동기 처리

### Async vs Sync 라우트

```python
# Async 라우트 - 비동기 I/O에 적합
@router.get("/users")
async def get_users(db: AsyncSession = Depends(get_db)):
    # await 사용 필수
    return await service.get_users(db)

# Sync 라우트 - CPU 바운드 또는 동기 라이브러리 사용 시
@router.post("/process")
def process_data(data: ProcessRequest):
    # 스레드풀에서 실행됨
    return heavy_computation(data)
```

### 주의사항

- Async 라우트에서 블로킹 호출 금지 (이벤트 루프 차단)
- CPU 집약적 작업은 별도 프로세스 (GIL 문제)
- 동기 DB 드라이버 사용 시 Sync 라우트 사용

## 3. Pydantic 활용

### 검증 최대 활용

```python
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Annotated


class UserCreate(BaseModel):
    email: EmailStr
    username: Annotated[str, Field(min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_]+$')]
    password: Annotated[str, Field(min_length=8)]

    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain uppercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain digit')
        return v
```

### Custom Base Model

```python
from pydantic import BaseModel, ConfigDict
from datetime import datetime


class AppBaseModel(BaseModel):
    """모든 스키마의 기본 클래스"""
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class TimestampMixin(BaseModel):
    created_at: datetime
    updated_at: datetime | None = None
```

### Settings 분리

```python
# src/config.py - 전역 설정
class Settings(BaseSettings):
    PROJECT_NAME: str
    DEBUG: bool = False

# src/auth/config.py - 도메인 설정
class AuthSettings(BaseSettings):
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"

    model_config = SettingsConfigDict(env_prefix="AUTH_")
```

## 4. 의존성 주입

### 재사용 가능한 의존성

```python
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession


async def get_user_or_404(
    user_id: int,
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await service.get_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


# 라우터에서 사용
@router.get("/{user_id}")
async def get_user(user: User = Depends(get_user_or_404)):
    return user


@router.delete("/{user_id}")
async def delete_user(user: User = Depends(get_user_or_404)):
    # user가 이미 검증됨
    ...
```

### 의존성 체이닝

```python
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    # 토큰 검증 및 사용자 조회
    ...


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_user
```

### 의존성 캐싱 활용

```python
# FastAPI는 요청 범위 내에서 의존성을 캐싱
# 아래 라우트에서 get_db는 한 번만 호출됨

@router.post("/items")
async def create_item(
    item: ItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),  # 내부에서 get_db 사용
):
    ...
```

## 5. 에러 처리

### 도메인별 예외

```python
# src/exceptions.py
class AppException(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code


# src/users/exceptions.py
class UserNotFoundError(AppException):
    def __init__(self, user_id: int):
        super().__init__(
            detail=f"User with id {user_id} not found",
            status_code=404
        )


class EmailAlreadyExistsError(AppException):
    def __init__(self, email: str):
        super().__init__(
            detail=f"User with email {email} already exists",
            status_code=409
        )
```

### 전역 예외 핸들러

```python
# src/main.py
from fastapi import Request
from fastapi.responses import JSONResponse
from src.exceptions import AppException


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )
```

## 6. 데이터베이스

### 명명 규칙 강제

```python
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=convention)
```

### 모델 정의

```python
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    posts: Mapped[list["Post"]] = relationship(back_populates="author")
```

## 7. 테스트

### 테스트 구조

```
tests/
├── conftest.py          # 공통 fixtures
├── auth/
│   ├── test_router.py   # API 테스트
│   └── test_service.py  # 유닛 테스트
└── users/
    └── ...
```

### API 테스트 예시

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_user(client: AsyncClient):
    response = await client.post(
        "/api/v1/users",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "Password123"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "password" not in data


@pytest.mark.asyncio
async def test_create_user_duplicate_email(client: AsyncClient, db_session):
    # 먼저 사용자 생성
    await service.create_user(db_session, UserCreate(...))

    # 중복 이메일로 생성 시도
    response = await client.post(
        "/api/v1/users",
        json={"email": "test@example.com", ...}
    )
    assert response.status_code == 409
```

## 8. 프로덕션 배포

### Uvicorn 설정

```bash
# 개발
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 프로덕션 (Gunicorn + Uvicorn workers)
gunicorn src.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Worker 수 계산

```python
# CPU 코어 수 * 2 + 1 (일반적인 권장)
# I/O 바운드 앱의 경우 더 많이 설정 가능
workers = (multiprocessing.cpu_count() * 2) + 1
```

## 9. 보안

### CORS 설정

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,  # 프로덕션에서는 구체적으로
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

### Rate Limiting

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, ...):
    ...
```

## 참조

- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
- [zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices)
- [Pydantic V2 문서](https://docs.pydantic.dev/)
