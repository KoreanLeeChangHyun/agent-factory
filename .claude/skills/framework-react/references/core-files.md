# 핵심 파일 구성

React 프로젝트의 핵심 파일별 코드 예시입니다.

## src/app/main.tsx

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

## src/app/main-provider.tsx

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

## src/app/router.tsx

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

## src/config/env.ts

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

## src/lib/api-client.ts

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
