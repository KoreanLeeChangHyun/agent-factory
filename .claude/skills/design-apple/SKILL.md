---
name: design-apple
description: Apple Human Interface Guidelines inspired design system for creating sleek, minimalist web interfaces. Use when building Apple-style landing pages, product showcases, or modern web applications with clean aesthetics.
license: MIT
---

# Apple 디자인 시스템 스킬

## 개요

이 스킬은 Apple의 Human Interface Guidelines(HIG) 원칙을 따라 현대적이고 미니멀한 웹 인터페이스를 만들기 위한 Apple 영감의 디자인 가이드라인을 제공한다.

**키워드**: apple design, HIG, minimalist, clean UI, SF Pro, system colors, scroll animation, parallax, product page, landing page

## 사용 시기

- 제품 랜딩 페이지 빌드
- Apple 스타일 쇼케이스 웹사이트 제작
- 미니멀리스트 웹 애플리케이션 디자인
- 스크롤 기반 애니메이션 구현
- 깔끔하고 프리미엄한 미학이 필요할 때

## 빠른 참조

### 색상
```css
/* Primary */
--apple-black: #1D1D1F;
--apple-white: #FFFFFF;
--apple-gray-bg: #F5F5F7;

/* System Colors */
--apple-blue: #007AFF;
--apple-green: #34C759;
--apple-red: #FF3B30;
--apple-orange: #FF9500;
```

### 타이포그래피
```css
font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue', sans-serif;
```

### 핵심 원칙
1. **명료성(Clarity)** - 텍스트는 가독성 있게, 아이콘은 정밀하게
2. **존중(Deference)** - UI가 콘텐츠 이해를 돕는다
3. **깊이(Depth)** - 시각적 레이어와 모션
4. **여백(Whitespace)** - 넉넉한 간격

## 이 스킬의 파일들

| 파일 | 설명 |
|------|------|
| `colors.md` | 전체 색상 팔레트 및 사용법 |
| `typography.md` | 폰트 패밀리, 크기, 굵기 |
| `layout.md` | 간격, 그리드, 반응형 디자인 |
| `animation.md` | 스크롤 효과, 트랜지션 |
| `components.md` | 일반적인 UI 패턴 |

## 사용 예시

```jsx
// Apple 스타일링이 적용된 React 컴포넌트
const ProductHero = () => (
  <section style={{
    background: '#F5F5F7',
    padding: '120px 0',
    textAlign: 'center'
  }}>
    <h1 style={{
      fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
      fontSize: '56px',
      fontWeight: 600,
      color: '#1D1D1F',
      letterSpacing: '-0.015em'
    }}>
      iPhone 16 Pro
    </h1>
    <p style={{
      fontSize: '28px',
      fontWeight: 400,
      color: '#86868B',
      marginTop: '6px'
    }}>
      Hello, Apple Intelligence.
    </p>
    <a href="#" style={{
      color: '#007AFF',
      fontSize: '21px',
      textDecoration: 'none'
    }}>
      Learn more →
    </a>
  </section>
);
```

## 참고 자료

- [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)
- [Apple Developer Design](https://developer.apple.com/design/)
- [Apple Fonts](https://developer.apple.com/fonts/)
