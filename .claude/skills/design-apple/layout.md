# Apple Design - Layout

## Core Principles

### 1. Content First
- UI defers to content
- Minimize visual clutter
- Let the product be the hero

### 2. Generous Whitespace
- Large margins and padding
- Breathing room between sections
- Content never feels cramped

### 3. Center-Aligned Hierarchy
- Headlines centered
- Content flows from center
- Visual balance

## Grid System

### Container Widths
```css
.container {
  max-width: 980px;
  margin: 0 auto;
  padding: 0 22px;
}

.container-wide {
  max-width: 1440px;
  margin: 0 auto;
  padding: 0 22px;
}

.container-narrow {
  max-width: 692px;
  margin: 0 auto;
  padding: 0 22px;
}
```

### Breakpoints
```css
/* Apple's standard breakpoints */
@media (max-width: 1440px) { /* Large desktop */ }
@media (max-width: 1068px) { /* Small desktop/tablet */ }
@media (max-width: 734px)  { /* Mobile */ }
@media (max-width: 480px)  { /* Small mobile */ }
```

## Spacing System

### Spacing Scale
```css
:root {
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-7: 32px;
  --space-8: 40px;
  --space-9: 48px;
  --space-10: 64px;
  --space-11: 80px;
  --space-12: 100px;
  --space-13: 120px;
}
```

### Section Spacing
```css
/* Standard section */
.section {
  padding: 100px 0;
}

/* Hero section */
.section-hero {
  padding: 120px 0 80px;
}

/* Compact section */
.section-compact {
  padding: 60px 0;
}

@media (max-width: 734px) {
  .section { padding: 60px 0; }
  .section-hero { padding: 80px 0 60px; }
}
```

## Common Layouts

### Hero Section
```css
.hero {
  text-align: center;
  padding: 120px 0;
  background: #F5F5F7;
}

.hero__title {
  font-size: 56px;
  font-weight: 600;
  color: #1D1D1F;
  margin-bottom: 6px;
}

.hero__subtitle {
  font-size: 28px;
  color: #86868B;
  margin-bottom: 20px;
}

.hero__cta {
  margin-top: 32px;
}
```

### Feature Grid
```css
.feature-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 30px;
  padding: 100px 0;
}

@media (max-width: 1068px) {
  .feature-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 734px) {
  .feature-grid {
    grid-template-columns: 1fr;
    gap: 20px;
  }
}
```

### Two-Column Split
```css
.split {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 60px;
  align-items: center;
  padding: 100px 0;
}

@media (max-width: 734px) {
  .split {
    grid-template-columns: 1fr;
    gap: 40px;
  }
}
```

### Full-Width Media
```css
.media-full {
  width: 100vw;
  margin-left: calc(-50vw + 50%);
  overflow: hidden;
}

.media-full img,
.media-full video {
  width: 100%;
  height: auto;
  display: block;
}
```

## Sticky Navigation

```css
.nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 48px;
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  z-index: 9999;
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
}

/* Dark variant */
.nav--dark {
  background: rgba(29, 29, 31, 0.8);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
```

## Card Layout

```css
.card {
  background: #FFFFFF;
  border-radius: 18px;
  overflow: hidden;
  box-shadow: 2px 4px 12px rgba(0, 0, 0, 0.08);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.card:hover {
  transform: scale(1.02);
  box-shadow: 2px 4px 16px rgba(0, 0, 0, 0.12);
}

.card__media {
  aspect-ratio: 16 / 9;
  overflow: hidden;
}

.card__content {
  padding: 24px;
}
```

## Best Practices

### Do's
- Center important content
- Use large section padding (100px+)
- Let images and products breathe
- Use consistent grid gutters

### Don'ts
- Don't crowd content
- Don't use narrow margins
- Don't left-align hero content
- Don't use inconsistent spacing
