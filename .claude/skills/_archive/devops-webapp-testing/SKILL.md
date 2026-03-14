---
name: devops-webapp-testing
description: Toolkit for interacting with and testing local web applications using Playwright. Supports verifying frontend functionality, debugging UI behavior, capturing browser screenshots, and viewing browser logs.
license: "Apache-2.0"
---

# 웹 애플리케이션 테스트

로컬 웹 애플리케이션을 테스트할 때는 네이티브 Python Playwright 스크립트를 작성한다.

**사용 가능한 헬퍼 스크립트**:
- `scripts/with_server.py` - 서버 라이프사이클 관리 (다중 서버 지원)

**항상 `--help` 옵션을 먼저 실행**하여 사용법을 확인한다. 커스텀 솔루션이 반드시 필요하다고 판단되기 전까지 소스를 직접 읽지 않는다. 이 스크립트들은 매우 길어서 컨텍스트 창을 오염시킬 수 있다. 컨텍스트에 불러오는 것이 아니라 블랙박스 스크립트로 직접 호출하기 위해 존재한다.

## 의사결정 트리: 접근 방식 선택

```
사용자 작업 → 정적 HTML인가?
    ├─ 예 → HTML 파일을 직접 읽어 셀렉터 파악
    │         ├─ 성공 → 셀렉터를 사용해 Playwright 스크립트 작성
    │         └─ 실패/불완전 → 동적으로 처리 (아래 참조)
    │
    └─ 아니오 (동적 웹앱) → 서버가 이미 실행 중인가?
        ├─ 아니오 → 실행: python scripts/with_server.py --help
        │        그 후 헬퍼를 사용해 간소화된 Playwright 스크립트 작성
        │
        └─ 예 → 정찰-후-실행 패턴:
            1. 페이지 이동 후 networkidle 대기
            2. 스크린샷 촬영 또는 DOM 검사
            3. 렌더링된 상태에서 셀렉터 파악
            4. 발견한 셀렉터로 액션 실행
```

## 예시: with_server.py 사용법

서버를 시작하려면 먼저 `--help`를 실행한 후 헬퍼를 사용한다:

**단일 서버:**
```bash
python scripts/with_server.py --server "npm run dev" --port 5173 -- python your_automation.py
```

**다중 서버 (예: 백엔드 + 프론트엔드):**
```bash
python scripts/with_server.py \
  --server "cd backend && python server.py" --port 3000 \
  --server "cd frontend && npm run dev" --port 5173 \
  -- python your_automation.py
```

자동화 스크립트를 작성할 때는 Playwright 로직만 포함한다 (서버는 자동으로 관리됨):
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True) # 항상 chromium을 headless 모드로 실행
    page = browser.new_page()
    page.goto('http://localhost:5173') # 서버가 이미 실행 중이고 준비된 상태
    page.wait_for_load_state('networkidle') # 필수: JS 실행 완료 대기
    # ... 자동화 로직
    browser.close()
```

## 정찰-후-실행 패턴

1. **렌더링된 DOM 검사**:
   ```python
   page.screenshot(path='/tmp/inspect.png', full_page=True)
   content = page.content()
   page.locator('button').all()
   ```

2. 검사 결과에서 **셀렉터 파악**

3. 발견한 셀렉터로 **액션 실행**

## 흔한 실수

❌ **금지** - 동적 앱에서 `networkidle` 대기 전에 DOM 검사
✅ **권장** - 검사 전에 `page.wait_for_load_state('networkidle')` 대기

## 모범 사례

- **번들된 스크립트를 블랙박스로 활용** - 작업 수행 시 `scripts/`에 있는 스크립트 중 도움이 될 것이 있는지 먼저 확인한다. 이 스크립트들은 복잡한 워크플로우를 안정적으로 처리하며 컨텍스트 창을 오염시키지 않는다. `--help`로 사용법을 확인한 후 직접 호출한다.
- 동기 스크립트에는 `sync_playwright()` 사용
- 작업 완료 후 반드시 브라우저 종료
- 설명적인 셀렉터 사용: `text=`, `role=`, CSS 셀렉터, 또는 ID
- 적절한 대기 추가: `page.wait_for_selector()` 또는 `page.wait_for_timeout()`

## 참고 파일

- **examples/** - 일반적인 패턴을 보여주는 예시:
  - `element_discovery.py` - 페이지에서 버튼, 링크, 입력 요소 탐색
  - `static_html_automation.py` - 로컬 HTML에 file:// URL 사용
  - `console_logging.py` - 자동화 중 콘솔 로그 캡처
