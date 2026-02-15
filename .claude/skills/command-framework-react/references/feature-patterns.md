# Feature 모듈 패턴

Feature-Based 구조에서의 모듈별 코드 패턴 예시입니다.

## features/auth/api/login.ts

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

## features/auth/stores/auth-store.ts

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

## features/auth/components/login-form.tsx

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

## features/auth/index.ts (Public API)

```typescript
// Only export what other features can use
export { useLogin } from './api/login';
export { useLogout } from './api/logout';
export { useAuthStore } from './stores/auth-store';
export { LoginForm } from './components/login-form';
export type { User, LoginCredentials } from './types';
```
