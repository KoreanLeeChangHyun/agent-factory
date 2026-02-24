# Apple Design - Colors

## Brand Colors

### Primary Colors
| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| Shark Black | `#1D1D1F` | rgb(29, 29, 31) | Primary text, headings |
| Pure White | `#FFFFFF` | rgb(255, 255, 255) | Backgrounds, text on dark |
| Athens Gray | `#F5F5F7` | rgb(245, 245, 247) | Section backgrounds |

### Text Colors
| Name | Hex | Usage |
|------|-----|-------|
| Primary Text | `#1D1D1F` | Headlines, important text |
| Secondary Text | `#86868B` | Subheadings, descriptions |
| Tertiary Text | `#6E6E73` | Supporting text |
| Link Blue | `#007AFF` | Links, CTAs |

## System Colors (iOS/macOS)

### Semantic Colors
```css
:root {
  /* Primary Actions */
  --system-blue: #007AFF;
  --system-blue-dark: #0A84FF;

  /* Success */
  --system-green: #34C759;
  --system-green-dark: #30D158;

  /* Warning */
  --system-orange: #FF9500;
  --system-orange-dark: #FF9F0A;

  /* Destructive */
  --system-red: #FF3B30;
  --system-red-dark: #FF453A;

  /* Info */
  --system-purple: #AF52DE;
  --system-purple-dark: #BF5AF2;

  /* Accent */
  --system-pink: #FF2D55;
  --system-pink-dark: #FF375F;

  /* Neutral */
  --system-gray: #8E8E93;
  --system-gray-dark: #98989D;
}
```

### Gray Scale
```css
:root {
  --gray-1: #F5F5F7;
  --gray-2: #E8E8ED;
  --gray-3: #D2D2D7;
  --gray-4: #C7C7CC;
  --gray-5: #AEAEB2;
  --gray-6: #8E8E93;
}
```

## Color Usage Guidelines

### Do's
- Use `#1D1D1F` for primary text on light backgrounds
- Use `#F5F5F7` for alternating section backgrounds
- Use `#007AFF` for interactive elements (links, buttons)
- Use `#FF3B30` for destructive actions only

### Don'ts
- Don't use the same color for different meanings
- Don't use low contrast color combinations
- Don't overuse accent colors
- Don't use pure black (`#000000`) for text

## Light/Dark Mode

### Light Mode
```css
:root {
  --bg-primary: #FFFFFF;
  --bg-secondary: #F5F5F7;
  --text-primary: #1D1D1F;
  --text-secondary: #86868B;
}
```

### Dark Mode
```css
@media (prefers-color-scheme: dark) {
  :root {
    --bg-primary: #000000;
    --bg-secondary: #1D1D1F;
    --text-primary: #F5F5F7;
    --text-secondary: #86868B;
  }
}
```

## CSS Variables Template

```css
:root {
  /* Backgrounds */
  --apple-bg-primary: #FFFFFF;
  --apple-bg-secondary: #F5F5F7;
  --apple-bg-tertiary: #E8E8ED;

  /* Text */
  --apple-text-primary: #1D1D1F;
  --apple-text-secondary: #86868B;
  --apple-text-tertiary: #6E6E73;

  /* Accent */
  --apple-blue: #007AFF;
  --apple-green: #34C759;
  --apple-red: #FF3B30;
  --apple-orange: #FF9500;

  /* Borders */
  --apple-border: #D2D2D7;
  --apple-border-light: #E8E8ED;
}
```
