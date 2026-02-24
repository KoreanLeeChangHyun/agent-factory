---
name: design-apple
description: Apple Human Interface Guidelines inspired design system for creating sleek, minimalist web interfaces. Use when building Apple-style landing pages, product showcases, or modern web applications with clean aesthetics.
license: MIT
---

# Apple Design System Skill

## Overview

This skill provides Apple-inspired design guidelines for creating modern, minimalist web interfaces following Apple's Human Interface Guidelines (HIG) principles.

**Keywords**: apple design, HIG, minimalist, clean UI, SF Pro, system colors, scroll animation, parallax, product page, landing page

## When to Use

- Building product landing pages
- Creating Apple-style showcase websites
- Designing minimalist web applications
- Implementing scroll-driven animations
- Need clean, premium aesthetic

## Quick Reference

### Colors
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

### Typography
```css
font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue', sans-serif;
```

### Key Principles
1. **Clarity** - Text is legible, icons precise
2. **Deference** - UI helps understand content
3. **Depth** - Visual layers and motion
4. **Whitespace** - Generous spacing

## Files in This Skill

| File | Description |
|------|-------------|
| `colors.md` | Complete color palette and usage |
| `typography.md` | Font families, sizes, weights |
| `layout.md` | Spacing, grid, responsive design |
| `animation.md` | Scroll effects, transitions |
| `components.md` | Common UI patterns |

## Usage Example

```jsx
// React component with Apple styling
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

## Sources

- [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)
- [Apple Developer Design](https://developer.apple.com/design/)
- [Apple Fonts](https://developer.apple.com/fonts/)
