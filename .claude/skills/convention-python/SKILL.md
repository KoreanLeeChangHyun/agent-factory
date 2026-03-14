---
name: convention-python
description: ".py 파일 읽기/쓰기 시 무조건 트리거되는 Python 코딩 컨벤션 강제 스킬. PEP 8 네이밍, 전체 타입 힌트, Google 스타일 docstring을 강제한다. OOP 설계 규칙은 convention-oop 스킬과 연계한다. Triggers: '*.py', 'Python', 'python', '.py 파일'."
license: "Apache-2.0"
---

# Python 코딩 컨벤션

Python 코드 작성 시 일관된 스타일과 구조를 유지하기 위한 컨벤션 가이드입니다. 이 스킬은 .py 파일 읽기/쓰기 시 자동으로 트리거되며, 규칙 위반 시 자동 수정을 수행합니다.

## 1. 네이밍 규칙 (PEP 8 표준)

Python 코드에서는 일관된 네이밍 규칙을 적용하여 가독성과 유지보수성을 높입니다.

### 변수 및 함수: snake_case

- 소문자와 언더스코어만 사용
- 예: `user_name`, `get_user_data()`, `max_retry_count`
- 금지: `userName`, `getUserData`, `maxRetryCount`

### 클래스: PascalCase

- 각 단어의 첫 글자를 대문자로 표기
- 예: `UserService`, `DataProcessor`, `ApiClient`
- 금지: `user_service`, `data_processor`, `api_client`

### 상수: UPPER_SNAKE_CASE

- 모든 글자를 대문자로, 단어는 언더스코어로 구분
- 예: `MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT`, `API_BASE_URL`
- 금지: `max_retry_count` (변수), `MaxRetryCount`

### Private 멤버: 언더스코어 접두사

- private 함수/메서드: `_` 접두사 1개 (예: `_internal_state`, `_validate_input()`)
- private 속성: `_` 접두사 1개 또는 `__` 접두사 2개 (예: `_cache`, `__secret`)
- dunder 메서드는 언더스코어 양쪽: `__init__`, `__str__`

### 모듈 및 패키지: snake_case

- 파일명과 디렉터리명은 소문자와 언더스코어
- 예: `user_service.py`, `data_processor.py`, `utils/`
- 금지: `UserService.py`, `DataProcessor.py`

## 2. 타입 힌트 규칙 (전체 필수)

Python 3.5+ 타입 힌트를 통해 코드의 안정성과 가독성을 높입니다. 모든 함수, 메서드, 변수에 타입 힌트를 필수로 작성합니다.

### 함수 인자: 모든 인자에 타입 힌트 필수

```python
# 좋은 예
def get_user(user_id: int) -> dict[str, str]:
    """사용자 정보를 반환합니다."""
    return {"id": str(user_id), "name": "John"}

def calculate_total(items: list[int], tax_rate: float) -> float:
    """총액을 계산합니다."""
    return sum(items) * (1 + tax_rate)

# 나쁜 예 (타입 힌트 누락)
def get_user(user_id):
    return {"id": str(user_id), "name": "John"}

def calculate_total(items, tax_rate):
    return sum(items) * (1 + tax_rate)
```

### 함수 반환값: -> Type 필수

- 모든 반환값에 타입 명시 (None 포함)
- 예:
  - `-> str`: 문자열 반환
  - `-> int | None`: 정수 또는 None
  - `-> None`: 반환값 없음
  - `-> list[dict[str, int]]`: 복잡한 컬렉션

### 변수 선언: 타입 추론 불가능한 경우 필수

```python
# 추론 가능 (선택사항)
name = "Alice"  # str로 명확

# 추론 불가능 (필수)
result: dict[str, list[int]] = {}  # 초기 빈 딕셔너리
data: Any = load_json_config()  # Any 타입 지정
optional_user: User | None = None  # Optional 명시

# Optional 활용
from typing import Optional
user: Optional[User] = None  # 또는 User | None
```

### 클래스 속성: 모든 인스턴스/클래스 변수에 타입 어노테이션 필수

```python
from typing import Optional
from dataclasses import dataclass

class UserService:
    """사용자 서비스 클래스"""

    # 클래스 변수
    MAX_USERS: int = 1000
    default_timeout: float = 30.0

    # 인스턴스 변수 (생성자)
    def __init__(self, db_url: str):
        self.db_url: str = db_url
        self.cache: dict[str, str] = {}
        self.user_count: int = 0
        self._internal_state: Optional[str] = None
```

### typing 모듈 활용

- `Optional[T]` 또는 `T | None`: 선택적 타입
- `Union[T1, T2]` 또는 `T1 | T2`: 여러 타입 중 하나
- `List[T]`, `Dict[K, V]`, `Set[T]`, `Tuple[T, ...]`: 컬렉션
- `Callable[[Arg1, Arg2], ReturnType]`: 함수 타입
- `Any`: 타입을 알 수 없는 경우 (최후의 수단)

## 3. 주석/Docstring 규칙 (Google 스타일)

명확하고 유지보수하기 쉬운 문서화를 위해 Google 스타일 docstring을 사용합니다.

### 파일 최상단 모듈 Docstring (필수)

```python
"""사용자 관리 모듈.

이 모듈은 사용자 생성, 조회, 수정, 삭제 기능을 제공합니다.

주요 클래스:
    UserService: 사용자 비즈니스 로직 처리
    User: 사용자 데이터 모델

주요 함수:
    get_user_by_id: ID로 사용자 조회
    validate_user_data: 사용자 데이터 검증
"""
```

### Public 함수/메서드: Google 스타일 Docstring (필수)

```python
def calculate_discount(price: float, discount_rate: float, is_member: bool) -> float:
    """가격에 할인을 적용합니다.

    회원 여부에 따라 추가 할인을 제공합니다.

    Args:
        price: 원래 가격 (원화)
        discount_rate: 할인율 (0.0 ~ 1.0)
        is_member: 회원 여부

    Returns:
        할인이 적용된 최종 가격. 할인율이 유효하지 않으면 원래 가격.

    Raises:
        ValueError: discount_rate가 0.0 ~ 1.0 범위를 벗어난 경우

    Example:
        >>> calculate_discount(10000, 0.1, True)
        8500
    """
    if not 0.0 <= discount_rate <= 1.0:
        raise ValueError("할인율은 0.0 ~ 1.0 범위여야 합니다")

    final_price = price * (1 - discount_rate)

    if is_member:
        final_price *= 0.95  # 추가 5% 할인

    return final_price
```

### 클래스 Docstring

```python
class UserManager:
    """사용자 관리 서비스.

    데이터베이스에서 사용자 정보를 조회, 생성, 수정, 삭제합니다.

    Attributes:
        db_connection: 데이터베이스 연결 객체
        cache: 사용자 캐시 (딕셔너리)
        logger: 로깅 객체
    """

    def __init__(self, db_url: str):
        """초기화합니다.

        Args:
            db_url: 데이터베이스 URL
        """
        self.db_connection = None
        self.cache: dict[str, dict] = {}
        self.logger = None
```

### 인라인 주석: 복잡한 로직/비즈니스 규칙에 필수

```python
def process_order(order: Order) -> None:
    """주문을 처리합니다."""

    # 배송료 계산: 기본 배송료 3,000원 + 지역별 추가 요금
    shipping_cost = 3000
    if order.region == "jeju":
        shipping_cost += 5000  # 제주도 추가료

    # 매직 넘버: 상품 수 5개 이상 시 배송료 면제 (정책 변경 시 여기서 수정)
    if len(order.items) >= 5:
        shipping_cost = 0

    order.shipping_cost = shipping_cost
```

### Private 함수/메서드: 최소한의 한 줄 Docstring 권장

```python
def _validate_email_format(email: str) -> bool:
    """이메일 형식을 검증합니다."""
    return "@" in email and "." in email.split("@")[1]

def _compute_hash(data: str) -> str:
    """SHA256 해시를 계산합니다."""
    import hashlib
    return hashlib.sha256(data.encode()).hexdigest()
```

### Google 스타일 Docstring 완전 예시

```python
"""데이터 처리 모듈.

CSV, JSON, Excel 등 다양한 형식의 데이터를 읽고 변환합니다.
"""

from typing import Optional, Any
import csv
import json

def transform_data(
    input_file: str,
    format_type: str,
    filter_key: Optional[str] = None
) -> list[dict[str, Any]]:
    """파일에서 데이터를 읽고 변환합니다.

    입력 파일을 지정된 형식으로 읽어 딕셔너리 리스트로 변환합니다.
    선택적으로 특정 키로 필터링할 수 있습니다.

    Args:
        input_file: 입력 파일 경로
        format_type: 파일 형식 ('csv', 'json', 'excel')
        filter_key: 필터링할 키 (선택사항)

    Returns:
        변환된 데이터 리스트. 각 항목은 딕셔너리 형식.
        필터_key가 지정되면 해당 키의 값으로만 필터링.

    Raises:
        FileNotFoundError: 입력 파일이 없는 경우
        ValueError: 지정된 형식이 지원되지 않는 경우
        json.JSONDecodeError: JSON 파일이 유효하지 않은 경우

    Example:
        >>> data = transform_data("users.csv", "csv", filter_key="status")
        >>> len(data)
        100
    """
    if not isinstance(input_file, str):
        raise ValueError("파일 경로는 문자열이어야 합니다")

    # 파일 읽기 로직
    with open(input_file, 'r') as f:
        if format_type == 'csv':
            reader = csv.DictReader(f)
            data = list(reader)
        elif format_type == 'json':
            data = json.load(f)
        else:
            raise ValueError(f"지원되지 않는 형식: {format_type}")

    # 필터링
    if filter_key:
        data = [item for item in data if filter_key in item]

    return data
```

## 4. 위반 시 자동 수정 동작

.py 파일 읽기/쓰기 시 컨벤션 위반을 감지하고 자동으로 수정합니다.

### 자동 수정 동작 목록

#### 타입 힌트 자동 추가

- **문제**: 함수 인자 또는 반환값에 타입 힌트 누락
- **수정**: 문맥상 타입 추론 후 `param: Type` 또는 `-> Type` 추가
- **예**:
  ```python
  # 수정 전
  def get_user(user_id):
      return {"name": "John"}

  # 수정 후
  def get_user(user_id: int) -> dict[str, str]:
      return {"name": "John"}
  ```

#### Docstring 자동 보완

- **문제**: public 함수/메서드에 docstring 누락 또는 불완전
- **수정**: Google 스타일 docstring 자동 생성 (파라미터, 반환값, 설명)
- **예**:
  ```python
  # 수정 전
  def calculate_tax(amount, rate):
      return amount * rate

  # 수정 후
  def calculate_tax(amount: float, rate: float) -> float:
      """세금을 계산합니다.

      Args:
          amount: 금액
          rate: 세율

      Returns:
          계산된 세금
      """
      return amount * rate
  ```

#### 네이밍 컨벤션 위반 수정

- **문제**: 변수/함수가 camelCase, 클래스가 snake_case 등 규칙 위반
- **수정**: 자동 변환 (변수/함수 → snake_case, 클래스 → PascalCase, 상수 → UPPER_SNAKE_CASE)
- **주의**: 문자열 내 하드코딩된 이름은 수정하지 않음

#### 모듈 Docstring 자동 추가

- **문제**: 파일 최상단에 모듈 docstring 누락
- **수정**: 파일명을 기반으로 기본 모듈 docstring 생성
- **예**:
  ```python
  # 수정 전
  def get_user(user_id: int) -> dict:
      return {}

  # 수정 후
  """사용자 관리 모듈."""

  def get_user(user_id: int) -> dict:
      return {}
  ```

#### Private 멤버 접두사 검증

- **문제**: private 멤버명에 언더스코어 접두사 누락
- **수정**: `_` 접두사 자동 추가 (필요시 이름 변경)
- **예**:
  ```python
  # 수정 전
  class Service:
      def validate_input(self):
          pass

  # 수정 후
  class Service:
      def _validate_input(self):
          pass
  ```

### 자동 수정 예외 사항

- **외부 API 호출**: 외부 라이브러리 함수의 시그니처는 수정하지 않음
- **테스트 코드**: `test_*.py` 파일의 테스트 함수 네이밍은 유연하게 허용
- **마이그레이션**: 레거시 코드의 일괄 수정이 필요한 경우 수동 개입 후 진행

### 자동 수정 수준 제어

.py 파일 작성 시 자동 수정 수준을 다음과 같이 적용:

1. **필수 수정** (항상 수행):
   - 네이밍 컨벤션 위반
   - 공개 함수 docstring 누락
   - 타입 힌트 누락 (명확한 경우)

2. **권장 수정** (경고 후 수행):
   - Private 멤버 접두사 추가
   - 모듈 docstring 추가
   - 인라인 주석 추가 (비즈니스 규칙)

3. **검토 필수** (사용자 확인 후):
   - 함수 리팩토링 (클래스 추출)
   - 상속 구조 변경

---

**마지막 갱신**: 2026-03-04
