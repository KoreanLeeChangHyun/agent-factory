---
name: command-review-frontend
description: "Frontend-specialized code review skill. Validates React/Vue patterns, state management, accessibility (a11y/WCAG), rendering performance, and component design patterns. Use for frontend review: React/Vue component review, UI change review, frontend performance review. Triggers: '프론트엔드 리뷰', 'frontend review', 'React 리뷰', 'UI 리뷰', '컴포넌트 리뷰'."
license: "Apache-2.0"
---

# Frontend Code Review

프론트엔드 코드 변경에 대한 전문 리뷰 체크리스트를 제공한다. React/Vue 패턴 검증, 접근성(a11y) 준수, 렌더링 성능 최적화를 리뷰 관점에서 체계적으로 점검한다.

**핵심 원칙:** 사용자가 실제로 경험하는 품질(접근성, 성능, 일관성)을 코드 레벨에서 검증한다.

## Overview

**목적:** 프론트엔드 코드 변경 시 React/Vue 패턴 준수, 접근성 기준 충족, 렌더링 성능 저하 방지를 리뷰어 관점에서 일괄 점검한다.

**적용 시점:**
- React/Vue 컴포넌트 신규 생성 또는 수정 리뷰
- UI/UX 변경 사항 리뷰
- 프론트엔드 성능 관련 코드 변경 리뷰
- 상태 관리 로직 변경 리뷰
- 디자인 시스템 컴포넌트 변경 리뷰

## frontend-design 및 command-react-best-practices와의 역할 분리

| 스킬 | 역할 | 사용 시점 | 관점 |
|------|------|----------|------|
| `frontend-design` | UI 구현 가이드. 미적 품질, 타이포그래피, 색상, 모션, 공간 구성 | 프론트엔드 코드 작성 시 | 디자인 품질 |
| `command-react-best-practices` | React/Next.js 코드 패턴 가이드. 컴포넌트 설계, 훅 규칙, 렌더링 최적화 규칙 제공 | React 코드 작성 시 | 구현 패턴 |
| `command-web-design-guidelines` | 접근성/표준 준수 체크리스트. WCAG 2.1 AA, ARIA, 키보드 네비게이션 | 웹 인터페이스 구현 시 | 기술 표준 |
| `command-review-frontend` (이 스킬) | 리뷰어 관점 프론트엔드 체크리스트. 패턴 위반 탐지, 접근성 누락 지적, 성능 저하 경고 | 프론트엔드 코드 리뷰 시 | 리뷰 판정 |

**핵심 구분:** frontend-design/react-best-practices/web-design-guidelines는 **코드 작성 시** 따르는 가이드이고, review-frontend는 **리뷰 시** 위반 사항을 탐지하고 판정하는 체크리스트다.

## React 패턴 리뷰 체크리스트

### Hooks 사용 규칙

- [ ] **의존성 배열 완전성**: useEffect/useMemo/useCallback의 의존성 배열에 참조하는 모든 값이 포함되어 있는가
- [ ] **useEffect 남용 방지**: 파생 상태 계산에 useEffect를 사용하지 않는가 (useMemo 또는 렌더링 중 계산으로 대체 가능 여부)
- [ ] **useEffect 클린업**: 구독, 타이머, 이벤트 리스너 등록 시 클린업 함수를 반환하는가
- [ ] **커스텀 훅 추출**: 컴포넌트 내 반복되는 훅 로직이 커스텀 훅으로 분리되어 있는가
- [ ] **조건부 훅 호출 금지**: 조건문/반복문 내부에서 훅을 호출하지 않는가

### 상태 관리

- [ ] **불필요한 상태 제거**: 기존 state나 props에서 파생 가능한 값을 별도 state로 관리하지 않는가
- [ ] **상태 위치 적정성**: state가 필요한 최하위 공통 조상 컴포넌트에 위치하는가 (불필요한 lifting 또는 과도한 drilling 없음)
- [ ] **prop drilling 심화 방지**: 3단계 이상 props 전달 시 Context, 상태 관리 라이브러리, 또는 합성(composition) 패턴을 사용하는가
- [ ] **상태 업데이트 불변성**: 객체/배열 상태 업데이트 시 불변성을 유지하는가 (직접 mutation 없음)
- [ ] **비동기 상태 관리**: 로딩/에러/성공 상태를 적절히 분리하여 관리하는가

### 컴포넌트 분리

- [ ] **단일 책임**: 하나의 컴포넌트가 하나의 관심사만 담당하는가 (200줄 초과 시 분리 검토)
- [ ] **적정 Props 수**: props가 5개를 초과하면 객체로 그룹화하거나 컴포넌트 분리를 검토했는가
- [ ] **Presentational/Container 분리**: 데이터 페칭 로직과 UI 렌더링 로직이 분리되어 있는가
- [ ] **합성 패턴 활용**: children이나 render props로 유연한 합성이 가능한 구조인가

### 메모이제이션

- [ ] **React.memo 적정 사용**: 렌더링 비용이 높고 동일 props로 자주 호출되는 컴포넌트에만 적용했는가 (과도한 memo 금지)
- [ ] **useMemo/useCallback 필요성**: 실제 성능 문제가 있는 경우에만 사용하는가 (premature optimization 방지)
- [ ] **참조 안정성**: 자식에게 전달하는 콜백/객체의 참조가 불필요하게 변경되지 않는가
- [ ] **key 속성 적정성**: 리스트 렌더링 시 안정적이고 고유한 key를 사용하는가 (index를 key로 사용하지 않음, 단 정적 리스트는 예외)

## Vue 패턴 리뷰 체크리스트

### Composition API

- [ ] **setup 함수 구조화**: 관련 로직이 composable 함수로 그룹화되어 있는가 (기능별 분리)
- [ ] **composable 네이밍**: `use` 접두사를 일관되게 사용하는가 (useAuth, useForm 등)
- [ ] **Options API 혼용 금지**: 동일 컴포넌트에서 Composition API와 Options API를 혼용하지 않는가

### reactive/ref 사용

- [ ] **ref vs reactive 선택**: 원시값은 ref, 객체는 reactive를 사용하는가 (또는 프로젝트 컨벤션 준수)
- [ ] **반응성 유지**: reactive 객체를 구조 분해할 때 `toRefs`를 사용하여 반응성을 유지하는가
- [ ] **ref 접근 시 .value**: 스크립트 내에서 ref 값 접근 시 `.value`를 빠뜨리지 않았는가

### computed 적정성

- [ ] **파생 상태는 computed**: watch + 별도 ref 대신 computed로 파생 상태를 표현하는가
- [ ] **computed 부수 효과 금지**: computed 내에서 비동기 호출, DOM 조작 등 부수 효과를 실행하지 않는가
- [ ] **getter/setter 분리**: 양방향 바인딩이 필요한 경우에만 writable computed를 사용하는가

### watch 남용 방지

- [ ] **watch 대신 computed**: 단순 파생 값 계산에 watch를 사용하지 않는가
- [ ] **watchEffect 정리**: watchEffect 내 비동기 작업에 `onCleanup`을 등록하는가
- [ ] **deep watch 최소화**: deep: true 옵션 사용 시 성능 영향을 고려했는가

## 접근성(a11y) 리뷰 체크리스트

WCAG 2.1 AA 기준을 적용한다.

### 시맨틱 HTML

- [ ] **적절한 HTML 요소 사용**: `<div>` 남용 대신 `<nav>`, `<main>`, `<article>`, `<section>`, `<aside>`, `<header>`, `<footer>` 등 시맨틱 요소를 사용하는가
- [ ] **제목 계층 순서**: `<h1>`~`<h6>` 계층이 논리적 순서를 따르는가 (레벨 건너뛰기 없음)
- [ ] **랜드마크 역할**: 페이지에 최소 `<main>` 랜드마크가 존재하는가

### ARIA 속성

- [ ] **ARIA 필요성**: 네이티브 HTML로 표현 가능한 경우 ARIA 대신 네이티브 요소를 사용하는가 (첫 번째 원칙)
- [ ] **aria-label/labelledby**: 시각적으로만 명확하고 프로그래밍적으로 불명확한 요소에 레이블이 있는가
- [ ] **aria-live 영역**: 동적 콘텐츠 업데이트(알림, 에러 메시지, 로딩 상태)에 적절한 aria-live 속성이 있는가
- [ ] **역할-상태 일관성**: `role` 속성 사용 시 해당 역할에 요구되는 상태/속성(aria-checked, aria-expanded 등)을 함께 제공하는가

### 키보드 네비게이션

- [ ] **포커스 가능성**: 모든 인터랙티브 요소(버튼, 링크, 폼)가 키보드로 접근 가능한가
- [ ] **포커스 순서**: Tab 순서가 시각적 레이아웃과 논리적으로 일치하는가
- [ ] **포커스 표시**: 포커스 상태가 시각적으로 명확하게 표시되는가 (`outline: none`만 적용하고 대체 스타일 없음은 금지)
- [ ] **키보드 트랩 방지**: 모달/드롭다운에서 키보드 포커스가 갇히지 않고 Escape로 닫을 수 있는가

### 색상 대비

- [ ] **텍스트 대비**: 일반 텍스트 4.5:1 이상, 대형 텍스트(18px bold 또는 24px regular) 3:1 이상
- [ ] **UI 컴포넌트 대비**: 버튼, 입력 필드 등 UI 컴포넌트 경계선이 배경 대비 3:1 이상
- [ ] **색상 단독 전달 금지**: 정보 전달 시 색상만으로 구분하지 않고 아이콘, 텍스트, 패턴 등 추가 수단을 제공하는가

### 스크린 리더 호환

- [ ] **이미지 대체 텍스트**: 모든 의미 있는 이미지에 `alt` 텍스트가 있고, 장식용 이미지는 `alt=""`인가
- [ ] **폼 레이블**: 모든 입력 요소에 연결된 `<label>` 또는 `aria-label`이 있는가
- [ ] **에러 메시지 연결**: 폼 유효성 검사 에러가 `aria-describedby`로 해당 입력에 연결되어 있는가

## 렌더링 성능 체크리스트

### 리렌더링 최적화

- [ ] **불필요한 리렌더링**: 부모 리렌더링 시 변경 없는 자식이 함께 리렌더링되지 않도록 조치했는가
- [ ] **상태 업데이트 배치**: 여러 상태를 개별 setter로 연속 업데이트하지 않고 배치 처리하는가
- [ ] **Context 분리**: 자주 변경되는 값과 정적인 값이 같은 Context에 있지 않은가

### 대용량 리스트 가상화

- [ ] **가상화 적용**: 100개 이상의 아이템 리스트에 가상 스크롤(react-window, vue-virtual-scroller 등)을 적용했는가
- [ ] **무한 스크롤/페이지네이션**: 대량 데이터 로딩 시 적절한 페이징 전략을 사용하는가

### 이미지 최적화

- [ ] **lazy loading**: 뷰포트 밖 이미지에 `loading="lazy"`를 적용했는가
- [ ] **적정 포맷/크기**: WebP/AVIF 포맷 사용, srcset으로 반응형 이미지를 제공하는가
- [ ] **CLS 방지**: 이미지에 width/height 또는 aspect-ratio를 명시하여 레이아웃 이동(CLS)을 방지하는가

### 번들 크기

- [ ] **트리 셰이킹**: 라이브러리를 전체 import하지 않고 필요한 모듈만 import하는가 (`import { pick } from 'lodash-es'`)
- [ ] **불필요한 의존성**: 새로 추가된 의존성이 번들 크기 대비 충분한 가치를 제공하는가
- [ ] **중복 의존성**: 동일 기능을 하는 라이브러리가 중복으로 포함되지 않았는가

### 코드 스플리팅

- [ ] **라우트 기반 분할**: 각 라우트가 lazy import로 분할되어 있는가 (`React.lazy`, `defineAsyncComponent`)
- [ ] **동적 import**: 초기 로드에 불필요한 모듈(모달, 차트 등)이 동적으로 import되는가
- [ ] **로딩 상태**: 코드 스플리팅 지점에 Suspense/fallback UI가 제공되는가

## Output Format

```yaml
frontend_review:
  verdict: PASS | CONCERNS | ISSUES_FOUND
  summary: "<1-2문장 핵심 요약>"

  react_patterns:
    hooks_compliance: PASS | WARN | FAIL
    state_management: PASS | WARN | FAIL
    component_design: PASS | WARN | FAIL
    memoization: PASS | WARN | FAIL
    issues:
      - category: "hooks | state | component | memo"
        severity: "Critical | Important | Minor"
        file: "<파일:라인>"
        description: "<위반 내용>"
        suggestion: "<수정 방안>"

  vue_patterns:  # Vue 프로젝트인 경우
    composition_api: PASS | WARN | FAIL
    reactivity: PASS | WARN | FAIL
    computed_watch: PASS | WARN | FAIL
    issues: []

  accessibility:
    semantic_html: PASS | WARN | FAIL
    aria_usage: PASS | WARN | FAIL
    keyboard_nav: PASS | WARN | FAIL
    color_contrast: PASS | WARN | FAIL
    screen_reader: PASS | WARN | FAIL
    issues:
      - wcag_criterion: "<WCAG 기준 번호>"
        severity: "Critical | Important | Minor"
        file: "<파일:라인>"
        description: "<위반 내용>"
        suggestion: "<수정 방안>"

  rendering_performance:
    rerender_optimization: PASS | WARN | FAIL
    list_virtualization: PASS | WARN | FAIL
    image_optimization: PASS | WARN | FAIL
    bundle_size: PASS | WARN | FAIL
    code_splitting: PASS | WARN | FAIL
    issues:
      - category: "rerender | list | image | bundle | splitting"
        severity: "Critical | Important | Minor"
        file: "<파일:라인>"
        description: "<성능 이슈>"
        impact: "<예상 영향>"
        suggestion: "<최적화 방안>"
```

## Critical Rules

1. **프레임워크 감지 우선**: 프로젝트의 프레임워크(React/Vue/기타)를 먼저 확인하고 해당 섹션만 적용한다. React 프로젝트에 Vue 체크리스트를 적용하지 않는다.
2. **접근성은 선택이 아닌 필수**: a11y 이슈 중 WCAG AA 기준 미달은 최소 Important로 분류한다. 키보드 접근 불가, 대체 텍스트 누락은 Critical이다.
3. **성능은 측정 기반 판단**: "느릴 수 있다"는 추측이 아닌, 구체적 패턴(O(n^2) 리스트 렌더링, 전체 라이브러리 import 등)에 기반하여 이슈를 제기한다.
4. **기존 패턴 존중**: 프로젝트에 이미 확립된 패턴(상태 관리 방식, 컴포넌트 구조 등)과의 일관성을 우선한다. 프로젝트 컨벤션과 충돌하는 "이론적 최선"을 강제하지 않는다.
5. **과도한 최적화 경고**: React.memo, useMemo, useCallback의 불필요한 사용은 오히려 성능을 저하시킨다. 최적화의 근거가 명확한 경우에만 적용을 권장한다.

## 연관 스킬

| 스킬 | 용도 | 경로 |
|------|------|------|
| `frontend-design` | UI 구현 가이드, 디자인 품질 | `.claude/skills/frontend-design/SKILL.md` |
| `command-react-best-practices` | React/Next.js 코드 패턴 규칙 | `.claude/skills/command-react-best-practices/SKILL.md` |
| `command-web-design-guidelines` | 접근성/표준 준수 체크리스트 | `.claude/skills/command-web-design-guidelines/SKILL.md` |
| `command-requesting-code-review` | 리뷰 요청 워크플로우, 이슈 분류 체계 | `.claude/skills/command-requesting-code-review/SKILL.md` |
| `command-code-quality-checker` | 정량적 품질 검사, Code Quality Score | `.claude/skills/command-code-quality-checker/SKILL.md` |
