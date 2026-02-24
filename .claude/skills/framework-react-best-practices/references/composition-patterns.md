# React Composition Patterns

컴포넌트 합성, Props 드릴링 회피, 재사용 가능한 UI 패턴에 대한 상세 가이드.

## Table of Contents

1. [Compound Components](#1-compound-components)
2. [Slots Pattern](#2-slots-pattern)
3. [Render Props](#3-render-props)
4. [Higher-Order Components](#4-higher-order-components)
5. [Children as Function](#5-children-as-function)
6. [Provider Pattern](#6-provider-pattern)
7. [Container/Presentational Split](#7-containerpresentational-split)
8. [Composition over Configuration](#8-composition-over-configuration)

## 1. Compound Components

관련된 컴포넌트를 하나의 논리적 단위로 묶어, 내부 상태를 Context로 공유하는 패턴.

```tsx
// 사용 예시
<Select value={selected} onChange={setSelected}>
  <Select.Trigger>
    <Select.Value placeholder="Choose..." />
  </Select.Trigger>
  <Select.Content>
    <Select.Item value="a">Option A</Select.Item>
    <Select.Item value="b">Option B</Select.Item>
  </Select.Content>
</Select>
```

### 구현

```tsx
import { createContext, useContext, useState, useCallback } from 'react';

interface SelectContextValue {
  value: string;
  onChange: (value: string) => void;
  isOpen: boolean;
  toggle: () => void;
}

const SelectContext = createContext<SelectContextValue | null>(null);

function useSelectContext() {
  const ctx = useContext(SelectContext);
  if (!ctx) throw new Error('Select compound components must be used within <Select>');
  return ctx;
}

function Select({ value, onChange, children }: {
  value: string;
  onChange: (v: string) => void;
  children: React.ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const toggle = useCallback(() => setIsOpen(prev => !prev), []);

  return (
    <SelectContext.Provider value={{ value, onChange, isOpen, toggle }}>
      <div className="select-root">{children}</div>
    </SelectContext.Provider>
  );
}

Select.Trigger = function Trigger({ children }: { children: React.ReactNode }) {
  const { toggle } = useSelectContext();
  return <button onClick={toggle}>{children}</button>;
};

Select.Value = function Value({ placeholder }: { placeholder: string }) {
  const { value } = useSelectContext();
  return <span>{value || placeholder}</span>;
};

Select.Content = function Content({ children }: { children: React.ReactNode }) {
  const { isOpen } = useSelectContext();
  if (!isOpen) return null;
  return <ul role="listbox">{children}</ul>;
};

Select.Item = function Item({ value, children }: { value: string; children: React.ReactNode }) {
  const { onChange, value: selected, toggle } = useSelectContext();
  return (
    <li
      role="option"
      aria-selected={value === selected}
      onClick={() => { onChange(value); toggle(); }}
    >
      {children}
    </li>
  );
};
```

**사용 시점:** 관련 UI 요소가 상태를 공유해야 하고, 사용자에게 유연한 구조를 제공할 때. 예: Select, Tabs, Accordion, Menu, Dialog.

## 2. Slots Pattern

children 대신 명명된 props로 UI 영역을 주입하는 패턴.

```tsx
interface CardProps {
  header?: React.ReactNode;
  footer?: React.ReactNode;
  children: React.ReactNode;
}

function Card({ header, footer, children }: CardProps) {
  return (
    <div className="card">
      {header && <div className="card-header">{header}</div>}
      <div className="card-body">{children}</div>
      {footer && <div className="card-footer">{footer}</div>}
    </div>
  );
}

// 사용
<Card
  header={<h2>Title</h2>}
  footer={<Button>Save</Button>}
>
  <p>Card content here</p>
</Card>
```

**사용 시점:** 레이아웃 컴포넌트에서 여러 영역을 독립적으로 커스터마이즈할 때.

## 3. Render Props

함수를 props로 전달하여 렌더링 로직을 위임하는 패턴. 대부분의 경우 커스텀 훅이 더 적합하지만, 렌더링 로직 자체를 위임해야 할 때 유효하다.

```tsx
interface MouseTrackerProps {
  render: (position: { x: number; y: number }) => React.ReactNode;
}

function MouseTracker({ render }: MouseTrackerProps) {
  const [pos, setPos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const handler = (e: MouseEvent) => setPos({ x: e.clientX, y: e.clientY });
    window.addEventListener('mousemove', handler);
    return () => window.removeEventListener('mousemove', handler);
  }, []);

  return <>{render(pos)}</>;
}

// 사용
<MouseTracker render={({ x, y }) => (
  <div>Mouse: {x}, {y}</div>
)} />
```

**사용 시점:** 라이브러리 패턴에서 렌더링 제어권을 소비자에게 위임할 때. 일반적인 로직 재사용은 커스텀 훅을 우선 사용한다.

## 4. Higher-Order Components

컴포넌트를 받아 강화된 컴포넌트를 반환하는 함수. 훅 도입 이후 사용 빈도가 낮지만, 횡단 관심사(cross-cutting concern) 적용에 여전히 유효하다.

```tsx
function withAuth<P extends object>(Component: React.ComponentType<P>) {
  return function AuthenticatedComponent(props: P) {
    const { isAuthenticated, isLoading } = useAuth();

    if (isLoading) return <Spinner />;
    if (!isAuthenticated) return <Navigate to="/login" />;

    return <Component {...props} />;
  };
}

// 사용
const ProtectedDashboard = withAuth(Dashboard);
```

**사용 시점:**
- 여러 컴포넌트에 동일한 횡단 관심사 적용 (인증, 로깅, 에러 경계)
- 타사 라이브러리 컴포넌트 래핑

**제한:**
- ref 전달 시 `React.forwardRef` 필요
- 정적 메서드가 전달되지 않음 (`hoist-non-react-statics`)
- 디버깅 시 displayName 설정 권장

## 5. Children as Function

children을 함수로 전달하여 부모가 제공하는 데이터로 렌더링하는 패턴.

```tsx
interface DataLoaderProps<T> {
  url: string;
  children: (data: T, isLoading: boolean) => React.ReactNode;
}

function DataLoader<T>({ url, children }: DataLoaderProps<T>) {
  const { data, isLoading } = useFetch<T>(url);
  return <>{children(data as T, isLoading)}</>;
}

// 사용
<DataLoader<User[]> url="/api/users">
  {(users, isLoading) =>
    isLoading ? <Spinner /> : <UserList users={users} />
  }
</DataLoader>
```

**사용 시점:** Render Props와 동일한 상황에서, children prop을 활용하여 JSX 가독성을 높일 때.

## 6. Provider Pattern

Context API를 사용하여 컴포넌트 트리 전체에 데이터를 전달하는 패턴.

```tsx
// Theme Provider
interface ThemeContextValue {
  theme: 'light' | 'dark';
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const toggleTheme = useCallback(
    () => setTheme(t => (t === 'light' ? 'dark' : 'light')),
    []
  );

  const value = useMemo(() => ({ theme, toggleTheme }), [theme, toggleTheme]);

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
```

**최적화 규칙:**
- Provider value는 `useMemo`로 안정화 (불필요한 리렌더링 방지)
- 자주 변경되는 상태와 정적 상태를 별도 Context로 분리
- 세분화된 Context 선호 (ThemeContext, AuthContext, NotificationContext 별도)

## 7. Container/Presentational Split

데이터 로직(Container)과 UI 표현(Presentational)을 분리하는 패턴.

```tsx
// Presentational: 순수 UI, props만 의존
interface UserListViewProps {
  users: User[];
  onSelect: (id: string) => void;
  isLoading: boolean;
}

function UserListView({ users, onSelect, isLoading }: UserListViewProps) {
  if (isLoading) return <Skeleton />;
  return (
    <ul>
      {users.map(user => (
        <li key={user.id} onClick={() => onSelect(user.id)}>
          {user.name}
        </li>
      ))}
    </ul>
  );
}

// Container: 데이터 로직
function UserListContainer() {
  const { data: users = [], isLoading } = useUsers();
  const navigate = useNavigate();

  const handleSelect = (id: string) => navigate(`/users/${id}`);

  return <UserListView users={users} onSelect={handleSelect} isLoading={isLoading} />;
}
```

**사용 시점:** Storybook 테스트, 시각적 테스트, UI 재사용이 중요한 경우. 단순한 컴포넌트에는 과도한 분리를 피한다.

## 8. Composition over Configuration

복잡한 props 객체 대신 합성으로 유연성을 제공하는 패턴.

```tsx
// Bad: Configuration 방식 (props 폭발)
<Table
  columns={columns}
  data={data}
  sortable
  filterable
  paginated
  selectable
  expandable
  onSort={handleSort}
  onFilter={handleFilter}
  onPageChange={handlePage}
  onSelect={handleSelect}
  renderExpandedRow={renderExpanded}
/>

// Good: Composition 방식 (유연하고 확장 가능)
<Table data={data}>
  <Table.Header>
    <Table.Sort column="name" />
    <Table.Filter column="status" />
  </Table.Header>
  <Table.Body>
    {row => (
      <Table.Row key={row.id} expandable>
        <Table.Cell>{row.name}</Table.Cell>
        <Table.Cell>{row.status}</Table.Cell>
        <Table.ExpandedContent>
          <DetailView data={row} />
        </Table.ExpandedContent>
      </Table.Row>
    )}
  </Table.Body>
  <Table.Pagination pageSize={10} />
</Table>
```

**원칙:**
- 10개 이상의 props가 필요하면 합성 패턴 검토
- 각 하위 컴포넌트가 단일 책임을 가짐
- 사용자가 필요한 기능만 조합할 수 있음

## Pattern Selection Guide

| 상황 | 권장 패턴 |
|------|----------|
| 관련 UI 요소의 상태 공유 | Compound Components |
| 레이아웃 영역 커스터마이즈 | Slots Pattern |
| 로직 재사용 (렌더링 무관) | Custom Hook |
| 렌더링 제어권 위임 | Render Props / Children as Function |
| 횡단 관심사 적용 | HOC 또는 Provider |
| 트리 전체 데이터 전달 | Provider Pattern |
| UI와 로직 분리 | Container/Presentational |
| 복잡한 설정 대체 | Composition over Configuration |
