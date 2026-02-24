# Apple Design - Typography

## Font Families

### San Francisco (SF) Pro
Apple's primary system font, optimized for legibility.

```css
/* Web Font Stack */
font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue', Helvetica, Arial, sans-serif;

/* Short version */
font-family: -apple-system, BlinkMacSystemFont, sans-serif;
```

### Font Variants
| Font | Usage | Size Range |
|------|-------|------------|
| SF Pro Display | Headlines, large text | 20pt+ |
| SF Pro Text | Body text, UI elements | Below 20pt |
| SF Mono | Code, monospace content | All sizes |

## Font Weights

### Available Weights
| Weight | CSS Value | Usage |
|--------|-----------|-------|
| Ultralight | 100 | Decorative only (avoid for UI) |
| Thin | 200 | Decorative only |
| Light | 300 | Large display text only |
| Regular | 400 | Body text |
| Medium | 500 | Emphasis, subheadings |
| Semibold | 600 | Headlines, CTAs |
| Bold | 700 | Strong emphasis |
| Heavy | 800 | Display text |
| Black | 900 | Display text |

### Recommended Weights
- **Headlines**: 600 (Semibold)
- **Body**: 400 (Regular)
- **Links**: 400 (Regular)
- **Buttons**: 500 (Medium) or 600 (Semibold)

## Type Scale (Apple.com Style)

### Hero Headlines
```css
.hero-title {
  font-size: 96px;
  font-weight: 700;
  letter-spacing: -0.015em;
  line-height: 1.05;
}

@media (max-width: 1068px) {
  .hero-title { font-size: 80px; }
}

@media (max-width: 734px) {
  .hero-title { font-size: 48px; }
}
```

### Section Headlines
```css
.section-title {
  font-size: 56px;
  font-weight: 600;
  letter-spacing: -0.015em;
  line-height: 1.07;
}

@media (max-width: 1068px) {
  .section-title { font-size: 48px; }
}

@media (max-width: 734px) {
  .section-title { font-size: 32px; }
}
```

### Subheadlines
```css
.subheadline {
  font-size: 28px;
  font-weight: 400;
  letter-spacing: 0.007em;
  line-height: 1.14;
  color: #86868B;
}

@media (max-width: 734px) {
  .subheadline { font-size: 21px; }
}
```

### Body Text
```css
.body-text {
  font-size: 17px;
  font-weight: 400;
  letter-spacing: -0.022em;
  line-height: 1.47;
}

.body-text-large {
  font-size: 21px;
  line-height: 1.38;
}
```

### Links
```css
.link {
  font-size: 21px;
  font-weight: 400;
  color: #007AFF;
  text-decoration: none;
}

.link:hover {
  text-decoration: underline;
}

/* Link with arrow */
.link-arrow::after {
  content: ' >';
  font-family: system-ui;
}
```

## Complete Type System CSS

```css
:root {
  /* Font Family */
  --font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', sans-serif;

  /* Font Sizes */
  --text-xs: 12px;
  --text-sm: 14px;
  --text-base: 17px;
  --text-lg: 21px;
  --text-xl: 28px;
  --text-2xl: 32px;
  --text-3xl: 40px;
  --text-4xl: 48px;
  --text-5xl: 56px;
  --text-6xl: 64px;
  --text-7xl: 80px;
  --text-8xl: 96px;
}

/* Apply to document */
body {
  font-family: var(--font-family);
  font-size: var(--text-base);
  line-height: 1.47;
  color: #1D1D1F;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
```

## Best Practices

### Do's
- Use Semibold (600) for headlines
- Use Regular (400) for body text
- Apply negative letter-spacing for large text
- Use `-webkit-font-smoothing: antialiased`

### Don'ts
- Avoid Ultralight/Thin weights for UI text
- Don't use more than 2-3 font weights per page
- Avoid positive letter-spacing for headlines
- Don't use pure black text - use `#1D1D1F`
