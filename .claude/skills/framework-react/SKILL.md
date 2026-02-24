---
name: framework-react
description: "Provides Bulletproof React architecture-based Feature-Based project structure, Next.js App Router layout, recommended tech stack (Vite, Zustand, React Query, Tailwind), and unidirectional dependency principles. Use for React/Next.js development: project initialization, Feature-Based structure setup, architecture-driven development. Triggers: 'React', 'Next.js', 'nextjs', 'React 프로젝트', '프론트엔드 프레임워크'."
license: "Apache-2.0"
---

# React Framework Skill

확장 가능한 프로덕션 레디 React 프로젝트 구조와 베스트 프랙티스를 제공합니다.
Bulletproof React 아키텍처를 기반으로 Feature-Based 구조를 채택합니다.

## 프로젝트 구조 원칙

### Feature-Based Structure (권장)

파일 타입이 아닌 **기능/도메인 단위**로 구조화:

```
project-name/
├── src/
│   ├── app/                    # 애플리케이션 레이어
│   │   ├── routes/             # 라우트 정의
│   │   │   ├── index.tsx       # 라우트 설정
│   │   │   └── protected.tsx   # 인증 필요 라우트
│   │   ├── main-provider.tsx   # 전역 프로바이더 조합
│   │   ├── main.tsx            # 앱 진입점
│   │   └── router.tsx          # 라우터 설정
│   │
│   ├── assets/                 # 정적 파일
│   │   ├── images/
│   │   └── fonts/
│   │
│   ├── components/             # 공유 컴포넌트
│   │   ├── ui/                 # 기본 UI 컴포넌트
│   │   │   ├── button/
│   │   │   │   ├── button.tsx
│   │   │   │   ├── button.test.tsx
│   │   │   │   └── index.ts
│   │   │   ├── input/
│   │   │   ├── modal/
│   │   │   └── index.ts
│   │   ├── layouts/            # 레이아웃 컴포넌트
│   │   │   ├── main-layout.tsx
│   │   │   └── auth-layout.tsx
│   │   └── errors/             # 에러 바운더리
│   │       └── error-boundary.tsx
│   │
│   ├── config/                 # 전역 설정
│   │   ├── env.ts              # 환경 변수
│   │   └── constants.ts        # 상수
│   │
│   ├── features/               # 기능별 모듈 (핵심)
│   │   ├── auth/               # 인증 기능
│   │   │   ├── api/            # API 호출
│   │   │   │   ├── login.ts
│   │   │   │   ├── logout.ts
│   │   │   │   └── get-user.ts
│   │   │   ├── components/     # 기능 전용 컴포넌트
│   │   │   │   ├── login-form.tsx
│   │   │   │   └── register-form.tsx
│   │   │   ├── hooks/          # 기능 전용 훅
│   │   │   │   └── use-auth.ts
│   │   │   ├── stores/         # 기능 상태
│   │   │   │   └── auth-store.ts
│   │   │   ├── types/          # 기능 타입
│   │   │   │   └── index.ts
│   │   │   ├── utils/          # 기능 유틸리티
│   │   │   │   └── token.ts
│   │   │   └── index.ts        # 공개 API
│   │   │
│   │   ├── users/              # 사용자 기능
│   │   │   ├── api/
│   │   │   ├── components/
│   │   │   ├── hooks/
│   │   │   ├── types/
│   │   │   └── index.ts
│   │   │
│   │   └── posts/              # 게시물 기능 (예시)
│   │       └── ...
│   │
│   ├── hooks/                  # 공유 커스텀 훅
│   │   ├── use-disclosure.ts
│   │   ├── use-media-query.ts
│   │   └── index.ts
│   │
│   ├── lib/                    # 라이브러리 설정
│   │   ├── api-client.ts       # Axios/Fetch 설정
│   │   ├── react-query.ts      # React Query 설정
│   │   └── auth.ts             # 인증 라이브러리
│   │
│   ├── stores/                 # 전역 상태 관리
│   │   ├── app-store.ts        # Zustand 스토어
│   │   └── notifications.ts
│   │
│   ├── testing/                # 테스트 유틸리티
│   │   ├── mocks/              # MSW 핸들러
│   │   │   ├── handlers/
│   │   │   └── server.ts
│   │   ├── test-utils.tsx      # 테스트 헬퍼
│   │   └── setup.ts            # 테스트 설정
│   │
│   ├── types/                  # 전역 타입
│   │   ├── api.ts
│   │   └── index.ts
│   │
│   └── utils/                  # 공유 유틸리티
│       ├── format.ts
│       ├── storage.ts
│       └── index.ts
│
├── public/                     # 정적 자산
│
├── tests/                      # E2E 테스트
│   └── e2e/
│       └── auth.spec.ts
│
├── .env.example                # 환경 변수 예시
├── .eslintrc.cjs               # ESLint 설정
├── .prettierrc                 # Prettier 설정
├── index.html                  # HTML 템플릿
├── package.json
├── tsconfig.json               # TypeScript 설정
├── vite.config.ts              # Vite 설정
└── README.md
```

## 핵심 파일 구성

main.tsx, main-provider.tsx, router.tsx, env.ts, api-client.ts 등 프로젝트 핵심 파일의 코드 예시를 제공합니다.

> 핵심 파일 코드 예시는 `references/core-files.md`를 참조하세요.

## Feature 모듈 패턴

auth 기능을 예시로 API 호출(login.ts), 상태 관리(auth-store.ts), 컴포넌트(login-form.tsx), Public API(index.ts) 패턴을 제공합니다.

> Feature 모듈 코드 예시는 `references/feature-patterns.md`를 참조하세요.

## 아키텍처 원칙

### 단방향 의존성

```
shared (components, hooks, lib, utils)
    ↓
features (auth, users, posts)
    ↓
app (routes, providers)
```

**금지**: Feature 간 직접 import
**허용**: Feature → Shared, App → Feature

### ESLint 규칙 (의존성 강제)

```javascript
// .eslintrc.cjs
module.exports = {
  rules: {
    'no-restricted-imports': [
      'error',
      {
        patterns: [
          {
            group: ['@/features/*/*'],
            message: 'Import from feature index only: @/features/auth',
          },
        ],
      },
    ],
  },
};
```

### Colocation 원칙

- 관련 코드는 함께 배치
- 기능별로 폴더 내 API, 컴포넌트, 훅, 타입 포함
- 전역 코드가 비대해지면 기능으로 이동

## 기술 스택 권장

### 필수
- **빌드**: Vite
- **언어**: TypeScript
- **라우팅**: React Router v6

### 권장
- **상태 관리**: Zustand (전역), React Query (서버)
- **폼**: React Hook Form + Zod
- **스타일링**: Tailwind CSS
- **테스트**: Vitest + Testing Library + MSW + Playwright

### 선택적
- **UI**: shadcn/ui, Radix UI
- **애니메이션**: Framer Motion
- **차트**: Recharts

## Next.js 프로젝트 구조

Next.js App Router 사용 시:

```
project-name/
├── src/
│   ├── app/                    # App Router
│   │   ├── (auth)/             # 인증 그룹
│   │   │   ├── login/
│   │   │   │   └── page.tsx
│   │   │   └── register/
│   │   │       └── page.tsx
│   │   ├── (dashboard)/        # 대시보드 그룹
│   │   │   ├── layout.tsx
│   │   │   └── dashboard/
│   │   │       └── page.tsx
│   │   ├── api/                # API Routes
│   │   │   └── auth/
│   │   │       └── route.ts
│   │   ├── layout.tsx          # 루트 레이아웃
│   │   ├── page.tsx            # 홈페이지
│   │   └── providers.tsx       # 클라이언트 프로바이더
│   │
│   ├── components/             # 공유 컴포넌트
│   ├── features/               # 기능별 모듈
│   ├── lib/                    # 라이브러리 설정
│   └── ...                     # 나머지 동일
│
├── next.config.js
└── ...
```

## 베스트 프랙티스 요약

### 컴포넌트

- 작고 집중된 컴포넌트 (SRP)
- Props는 인터페이스로 정의
- 조기 반환으로 조건부 렌더링

### 상태 관리

- 서버 상태: React Query
- 전역 상태: Zustand (최소화)
- 로컬 상태: useState/useReducer

### 성능

- React.memo 선별적 사용
- useMemo/useCallback 측정 후 적용
- Dynamic import로 코드 스플리팅
- Barrel export 피하기 (tree-shaking)

### 테스트

- 각 Feature에 테스트 포함
- MSW로 API 모킹
- Testing Library로 사용자 관점 테스트

## 참조

- [Bulletproof React](https://github.com/alan2207/bulletproof-react)
- [React Folder Structure](https://www.robinwieruch.de/react-folder-structure/)
- [Feature-Sliced Design](https://feature-sliced.design/)
