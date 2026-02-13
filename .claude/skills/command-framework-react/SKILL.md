---
name: command-framework-react
description: "Bulletproof React 아키텍처 기반 Feature-Based 프로젝트 구조, Next.js App Router 구조, 기술 스택 권장(Vite, Zustand, React Query, Tailwind), 단방향 의존성 원칙을 제공한다. Use when React/Next.js 프로젝트 초기화, Feature-Based 구조 설정, 아키텍처 기반 개발이 필요할 때. 키워드: React, Next.js, nextjs, React 프로젝트, 프론트엔드 프레임워크."
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

### src/app/main.tsx

```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { MainProvider } from './main-provider';
import { AppRouter } from './router';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MainProvider>
      <AppRouter />
    </MainProvider>
  </StrictMode>
);
```

### src/app/main-provider.tsx

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { ErrorBoundary } from '@/components/errors/error-boundary';
import { Notifications } from '@/components/ui/notifications';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 1000 * 60 * 5, // 5 minutes
    },
  },
});

type MainProviderProps = {
  children: React.ReactNode;
};

export const MainProvider = ({ children }: MainProviderProps) => {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <Notifications />
        {children}
        <ReactQueryDevtools initialIsOpen={false} />
      </QueryClientProvider>
    </ErrorBoundary>
  );
};
```

### src/app/router.tsx

```tsx
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import { useMemo } from 'react';

import { ProtectedRoute } from './routes/protected';
import { publicRoutes } from './routes';

export const AppRouter = () => {
  const router = useMemo(
    () =>
      createBrowserRouter([
        ...publicRoutes,
        {
          path: '/app',
          element: <ProtectedRoute />,
          children: [
            // Protected routes here
          ],
        },
      ]),
    []
  );

  return <RouterProvider router={router} />;
};
```

### src/config/env.ts

```typescript
import { z } from 'zod';

const envSchema = z.object({
  VITE_API_URL: z.string().url(),
  VITE_APP_ENV: z.enum(['development', 'staging', 'production']),
  VITE_ENABLE_MOCKING: z.string().transform((val) => val === 'true'),
});

export const env = envSchema.parse({
  VITE_API_URL: import.meta.env.VITE_API_URL,
  VITE_APP_ENV: import.meta.env.VITE_APP_ENV,
  VITE_ENABLE_MOCKING: import.meta.env.VITE_ENABLE_MOCKING,
});
```

### src/lib/api-client.ts

```typescript
import Axios, { AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios';
import { env } from '@/config/env';
import { useNotifications } from '@/components/ui/notifications';

const authRequestInterceptor = (config: InternalAxiosRequestConfig) => {
  if (config.headers) {
    config.headers.Accept = 'application/json';
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
};

export const api = Axios.create({
  baseURL: env.VITE_API_URL,
});

api.interceptors.request.use(authRequestInterceptor);

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.message || error.message;
    useNotifications.getState().addNotification({
      type: 'error',
      title: 'Error',
      message,
    });
    return Promise.reject(error);
  }
);
```

## Feature 모듈 패턴

### features/auth/api/login.ts

```typescript
import { useMutation } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import { useAuthStore } from '../stores/auth-store';
import type { LoginCredentials, AuthResponse } from '../types';

export const loginWithCredentials = (
  data: LoginCredentials
): Promise<AuthResponse> => {
  return api.post('/auth/login', data);
};

export const useLogin = () => {
  const { setUser, setToken } = useAuthStore();

  return useMutation({
    mutationFn: loginWithCredentials,
    onSuccess: (data) => {
      setUser(data.user);
      setToken(data.token);
    },
  });
};
```

### features/auth/stores/auth-store.ts

```typescript
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User } from '../types';

type AuthState = {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
  logout: () => void;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      setUser: (user) => set({ user, isAuthenticated: !!user }),
      setToken: (token) => set({ token }),
      logout: () => set({ user: null, token: null, isAuthenticated: false }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ token: state.token }),
    }
  )
);
```

### features/auth/components/login-form.tsx

```tsx
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useLogin } from '../api/login';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

const loginSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
});

type LoginFormData = z.infer<typeof loginSchema>;

export const LoginForm = () => {
  const login = useLogin();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = (data: LoginFormData) => {
    login.mutate(data);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <Input
        label="Email"
        type="email"
        error={errors.email?.message}
        {...register('email')}
      />
      <Input
        label="Password"
        type="password"
        error={errors.password?.message}
        {...register('password')}
      />
      <Button type="submit" isLoading={login.isPending}>
        Login
      </Button>
    </form>
  );
};
```

### features/auth/index.ts (Public API)

```typescript
// Only export what other features can use
export { useLogin } from './api/login';
export { useLogout } from './api/logout';
export { useAuthStore } from './stores/auth-store';
export { LoginForm } from './components/login-form';
export type { User, LoginCredentials } from './types';
```

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
