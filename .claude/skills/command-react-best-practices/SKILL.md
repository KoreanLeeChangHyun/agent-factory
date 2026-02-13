---
name: command-react-best-practices
description: "React/Next.js 코드 레벨 베스트 프랙티스를 제공한다. 컴포넌트 설계, 상태 관리, 훅 규칙, 렌더링 최적화, 에러 경계, 서버 컴포넌트, 데이터 페칭 등 8개 카테고리 40+ 규칙을 포함. Use when React/Next.js 코드 작성, 성능 최적화, 훅 사용 규칙 준수, 서버/클라이언트 컴포넌트 분리, 코드 리뷰 시. 키워드: React, Next.js, 리액트, react-performance, 컴포넌트, hooks, 리액트 최적화. 역할 구분: command-framework-react는 프로젝트 구조 설정, 이 스킬은 코드 패턴/성능 규칙."
---

# React Best Practices

React/Next.js 애플리케이션의 코드 패턴, 성능 최적화, 아키텍처 규칙을 제공한다.

**역할 분리:**
- `command-framework-react`: 프로젝트 초기화, Feature-Based 디렉터리 구조, 기술 스택 설정
- `command-react-best-practices` (이 스킬): 코드 레벨 패턴, 성능 규칙, 훅 규칙, 렌더링 최적화

**참조 파일:**
- 복합 컴포넌트 패턴, 합성 전략 상세: [references/composition-patterns.md](references/composition-patterns.md) 참조

## 1. Component Design

### 1.1 Single Responsibility

```tsx
// Good: 단일 책임
const UserAvatar = ({ src, name }: { src: string; name: string }) => (
  <img src={src} alt={name} className="avatar" loading="lazy" />
);

// Bad: 복합 책임
const UserCard = ({ user }: { user: User }) => {
  // avatar + name + bio + actions + API call 모두 포함
};
```

### 1.2 Props Interface

```tsx
// 명시적 인터페이스 정의
interface ButtonProps {
  variant: 'primary' | 'secondary' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  children: React.ReactNode;
  onClick?: () => void;
}

// children 대신 render props는 명확한 이유가 있을 때만
// 기본값은 defaultProps 대신 destructuring default 사용
const Button = ({ variant, size = 'md', isLoading = false, children, onClick }: ButtonProps) => {
  // ...
};
```

### 1.3 Early Return Pattern

```tsx
const UserProfile = ({ user, isLoading }: Props) => {
  if (isLoading) return <Skeleton />;
  if (!user) return <EmptyState />;
  if (user.isBanned) return <BannedNotice />;

  return <ProfileContent user={user} />;
};
```

### 1.4 Avoid Prop Drilling

3단계 이상 props 전달 시 Context 또는 상태 관리 라이브러리 사용. 상세 패턴은 [references/composition-patterns.md](references/composition-patterns.md) 참조.

## 2. State Management

### 2.1 State Placement Rules

| 상태 유형 | 관리 방법 | 예시 |
|----------|----------|------|
| UI 로컬 | `useState` / `useReducer` | 모달 열림, 폼 입력 |
| 서버 데이터 | React Query / SWR | API 응답, 캐시 |
| 전역 클라이언트 | Zustand / Jotai | 인증, 테마, 알림 |
| URL 상태 | URL params / searchParams | 필터, 페이지네이션 |

### 2.2 State Minimization

```tsx
// Good: 파생 상태는 계산으로
const Cart = ({ items }: { items: CartItem[] }) => {
  const total = items.reduce((sum, item) => sum + item.price * item.qty, 0);
  const isEmpty = items.length === 0;
  // total, isEmpty를 별도 state로 관리하지 않음
};

// Bad: 불필요한 상태 동기화
const [items, setItems] = useState<CartItem[]>([]);
const [total, setTotal] = useState(0); // items에서 파생 가능
```

### 2.3 useReducer for Complex State

```tsx
type Action =
  | { type: 'ADD_ITEM'; payload: CartItem }
  | { type: 'REMOVE_ITEM'; payload: string }
  | { type: 'UPDATE_QTY'; payload: { id: string; qty: number } };

function cartReducer(state: CartState, action: Action): CartState {
  switch (action.type) {
    case 'ADD_ITEM':
      return { ...state, items: [...state.items, action.payload] };
    case 'REMOVE_ITEM':
      return { ...state, items: state.items.filter(i => i.id !== action.payload) };
    case 'UPDATE_QTY':
      return {
        ...state,
        items: state.items.map(i =>
          i.id === action.payload.id ? { ...i, qty: action.payload.qty } : i
        ),
      };
  }
}
```

## 3. Performance Optimization

### 3.1 Memoization Rules

```tsx
// React.memo: 순수 컴포넌트 + 부모 리렌더링이 빈번할 때만
const ExpensiveList = React.memo(({ items }: { items: Item[] }) => (
  <ul>{items.map(item => <ListItem key={item.id} item={item} />)}</ul>
));

// useMemo: 비용이 큰 계산에만 (측정 후 적용)
const sortedItems = useMemo(
  () => items.toSorted((a, b) => a.name.localeCompare(b.name)),
  [items]
);

// useCallback: memo된 자식에 전달하는 콜백에만
const handleClick = useCallback((id: string) => {
  setSelected(id);
}, []);
```

**금지:**
- 모든 컴포넌트에 무조건 `React.memo` 적용
- 단순 계산에 `useMemo` 적용 (오히려 오버헤드)
- 의존성 배열이 매 렌더마다 바뀌는 `useCallback`

### 3.2 List Rendering

```tsx
// key는 안정적이고 고유한 값 사용
{items.map(item => <ListItem key={item.id} item={item} />)}

// Bad: index를 key로 사용 (리스트 변경 시 문제)
{items.map((item, index) => <ListItem key={index} item={item} />)}

// 대규모 리스트: 가상화 적용
import { useVirtualizer } from '@tanstack/react-virtual';
```

### 3.3 Code Splitting

```tsx
// 라우트 레벨 분할
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Settings = lazy(() => import('./pages/Settings'));

// 조건부 로드 (모달, 탭 등)
const HeavyEditor = lazy(() => import('./components/HeavyEditor'));

// Suspense로 폴백 제공
<Suspense fallback={<PageSkeleton />}>
  <Dashboard />
</Suspense>
```

### 3.4 Bundle Optimization

- barrel export(`index.ts`에서 re-export) 최소화 (tree-shaking 방해)
- dynamic import로 큰 라이브러리 지연 로드
- `React.lazy` + `Suspense`로 라우트 레벨 코드 분할
- 이미지: `next/image` 또는 `loading="lazy"` 필수

## 4. Rendering Patterns

### 4.1 Conditional Rendering

```tsx
// 삼항 연산자: 간단한 조건
{isLoggedIn ? <Dashboard /> : <LoginPage />}

// 논리 AND: 조건부 표시 (falsy 주의)
{items.length > 0 && <ItemList items={items} />}
// Bad: {count && <Badge count={count} />}  // count=0일 때 "0" 렌더링

// 복잡한 조건: 조기 반환 또는 맵
const statusComponent: Record<Status, React.ReactNode> = {
  loading: <Spinner />,
  error: <ErrorView />,
  success: <SuccessView />,
};
return statusComponent[status] ?? <DefaultView />;
```

### 4.2 Render Props vs Hooks

```tsx
// 우선: Custom Hook (대부분의 경우)
function useMousePosition() {
  const [pos, setPos] = useState({ x: 0, y: 0 });
  useEffect(() => {
    const handler = (e: MouseEvent) => setPos({ x: e.clientX, y: e.clientY });
    window.addEventListener('mousemove', handler);
    return () => window.removeEventListener('mousemove', handler);
  }, []);
  return pos;
}

// Render Props: 동적 렌더링이 필요한 라이브러리 패턴에만
```

## 5. Hooks Rules

### 5.1 Core Rules

- 최상위에서만 호출 (조건문/반복문/중첩 함수 내부 금지)
- React 함수 컴포넌트 또는 커스텀 훅에서만 호출
- 커스텀 훅 이름은 `use`로 시작

### 5.2 useEffect Guidelines

```tsx
// 1 Effect = 1 목적
useEffect(() => {
  const controller = new AbortController();
  fetchData(controller.signal);
  return () => controller.abort(); // cleanup 필수
}, [dependency]);

// Bad: 여러 관심사를 하나의 Effect에 결합
useEffect(() => {
  fetchUser();
  trackPageView();
  setupWebSocket();
}, []);
```

### 5.3 Custom Hook Patterns

```tsx
// 반환 타입 명시
function useToggle(initial = false): [boolean, () => void] {
  const [value, setValue] = useState(initial);
  const toggle = useCallback(() => setValue(v => !v), []);
  return [value, toggle];
}

// 복잡한 반환: 객체 사용
function useForm<T>(initialValues: T) {
  // ...
  return { values, errors, handleChange, handleSubmit, reset };
}
```

### 5.4 Dependency Array

- 모든 외부 값을 의존성에 포함 (ESLint `exhaustive-deps` 규칙 준수)
- 객체/배열 의존성은 `useMemo`로 안정화
- 함수 의존성은 `useCallback`으로 안정화
- 빈 배열 `[]`은 마운트 시 1회만 실행할 때만

## 6. Error Boundaries

### 6.1 Error Boundary Setup

```tsx
class ErrorBoundary extends React.Component<
  { fallback: React.ReactNode; children: React.ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    reportError(error, info.componentStack);
  }

  render() {
    if (this.state.hasError) return this.props.fallback;
    return this.props.children;
  }
}
```

### 6.2 Granular Error Boundaries

```tsx
// 페이지 레벨 + 위젯 레벨 이중 배치
<ErrorBoundary fallback={<PageError />}>
  <Header />
  <ErrorBoundary fallback={<WidgetError />}>
    <ExpensiveWidget />
  </ErrorBoundary>
  <ErrorBoundary fallback={<WidgetError />}>
    <DataChart />
  </ErrorBoundary>
</ErrorBoundary>
```

### 6.3 Async Error Handling

```tsx
// React Query 에러 처리
const { data, error, isError } = useQuery({
  queryKey: ['users'],
  queryFn: fetchUsers,
  retry: 2,
});

if (isError) return <ErrorDisplay error={error} />;
```

## 7. Server Components (Next.js App Router)

### 7.1 Server vs Client Decision

| 기준 | Server Component | Client Component |
|------|-----------------|-----------------|
| 데이터 페칭 | O (직접 DB/API 호출) | X (useEffect/React Query) |
| 상태/이벤트 | X | O (useState, onClick) |
| 브라우저 API | X | O (localStorage, window) |
| 번들 크기 영향 | 없음 (서버에서만 실행) | 있음 (JS 번들 포함) |

### 7.2 Component Separation

```tsx
// Server Component (기본값, 'use client' 없음)
async function UserPage({ params }: { params: { id: string } }) {
  const user = await getUser(params.id); // 직접 DB 호출
  return (
    <div>
      <h1>{user.name}</h1>
      <UserActions userId={user.id} /> {/* Client Component */}
    </div>
  );
}

// Client Component ('use client' 선언)
'use client';
function UserActions({ userId }: { userId: string }) {
  const [isFollowing, setIsFollowing] = useState(false);
  return <button onClick={() => toggleFollow(userId)}>Follow</button>;
}
```

### 7.3 Server Component Rules

- `'use client'` 경계를 최대한 아래(leaf)로 내림
- Server Component에서 Client Component를 children으로 전달 가능
- Client Component에서 Server Component를 import 불가 (children/props로만 전달)
- `async/await` 가능 (Server Component만)

## 8. Data Fetching

### 8.1 React Query Patterns

```tsx
// 쿼리 키 팩토리
const userKeys = {
  all: ['users'] as const,
  lists: () => [...userKeys.all, 'list'] as const,
  list: (filters: Filters) => [...userKeys.lists(), filters] as const,
  details: () => [...userKeys.all, 'detail'] as const,
  detail: (id: string) => [...userKeys.details(), id] as const,
};

// 쿼리 훅
function useUser(id: string) {
  return useQuery({
    queryKey: userKeys.detail(id),
    queryFn: () => fetchUser(id),
    staleTime: 5 * 60 * 1000,
  });
}

// 뮤테이션 + 캐시 무효화
function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateUser,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: userKeys.detail(data.id) });
      queryClient.invalidateQueries({ queryKey: userKeys.lists() });
    },
  });
}
```

### 8.2 Loading/Error States

```tsx
function UserList() {
  const { data, isLoading, isError, error } = useUsers();

  if (isLoading) return <ListSkeleton count={5} />;
  if (isError) return <ErrorMessage error={error} />;
  if (!data?.length) return <EmptyState message="No users found" />;

  return <ul>{data.map(user => <UserItem key={user.id} user={user} />)}</ul>;
}
```

### 8.3 Optimistic Updates

```tsx
const mutation = useMutation({
  mutationFn: toggleLike,
  onMutate: async (postId) => {
    await queryClient.cancelQueries({ queryKey: ['post', postId] });
    const prev = queryClient.getQueryData(['post', postId]);
    queryClient.setQueryData(['post', postId], (old: Post) => ({
      ...old,
      isLiked: !old.isLiked,
      likeCount: old.isLiked ? old.likeCount - 1 : old.likeCount + 1,
    }));
    return { prev };
  },
  onError: (_err, postId, context) => {
    queryClient.setQueryData(['post', postId], context?.prev);
  },
  onSettled: (_data, _err, postId) => {
    queryClient.invalidateQueries({ queryKey: ['post', postId] });
  },
});
```

## Quick Reference: Anti-Patterns

| Anti-Pattern | Fix |
|-------------|-----|
| Props drilling 3+ levels | Context, Zustand, composition pattern |
| `useEffect`로 상태 동기화 | 파생 상태로 계산, `useMemo` |
| `useEffect` 내 데이터 페칭 | React Query / SWR |
| 모든 컴포넌트 `React.memo` | 프로파일러 측정 후 선별 적용 |
| index를 key로 사용 | 안정적 고유 ID |
| 거대한 컨텍스트 1개 | 도메인별 분리, 세분화 |
| Client Component에서 데이터 페칭 | Server Component로 이동 (Next.js) |
| barrel export 남용 | 직접 import, tree-shaking 보장 |
| `any` 타입 남용 | 구체적 타입, `unknown` + 타입 가드 |
| cleanup 없는 `useEffect` | 구독 해제, AbortController |
