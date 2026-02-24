# Apple Design - Components

## Navigation Bar

### Global Nav
```html
<nav class="global-nav">
  <div class="global-nav__container">
    <a href="/" class="global-nav__logo">
      <svg><!-- Apple logo --></svg>
    </a>
    <ul class="global-nav__menu">
      <li><a href="#">Store</a></li>
      <li><a href="#">Mac</a></li>
      <li><a href="#">iPad</a></li>
      <li><a href="#">iPhone</a></li>
    </ul>
    <div class="global-nav__actions">
      <button class="global-nav__search">Search</button>
      <button class="global-nav__cart">Cart</button>
    </div>
  </div>
</nav>
```

```css
.global-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 44px;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: saturate(180%) blur(20px);
  z-index: 9999;
}

.global-nav__container {
  max-width: 980px;
  margin: 0 auto;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 22px;
}

.global-nav__menu {
  display: flex;
  gap: 30px;
  list-style: none;
}

.global-nav__menu a {
  color: #F5F5F7;
  font-size: 12px;
  text-decoration: none;
  opacity: 0.8;
  transition: opacity 0.2s ease;
}

.global-nav__menu a:hover {
  opacity: 1;
}
```

## Hero Section

### Product Hero
```html
<section class="hero">
  <div class="hero__content">
    <h1 class="hero__title">iPhone 16 Pro</h1>
    <p class="hero__subtitle">Hello, Apple Intelligence.</p>
    <div class="hero__cta">
      <a href="#" class="link-primary">Learn more</a>
      <a href="#" class="link-secondary">Buy</a>
    </div>
  </div>
  <div class="hero__media">
    <img src="iphone.jpg" alt="iPhone 16 Pro" />
  </div>
</section>
```

```css
.hero {
  text-align: center;
  padding: 120px 0 60px;
  background: #000;
  color: #F5F5F7;
}

.hero__title {
  font-size: 56px;
  font-weight: 600;
  letter-spacing: -0.015em;
  margin-bottom: 4px;
}

.hero__subtitle {
  font-size: 28px;
  font-weight: 400;
  color: #86868B;
}

.hero__cta {
  margin-top: 20px;
  display: flex;
  justify-content: center;
  gap: 24px;
}

.hero__media img {
  max-width: 100%;
  height: auto;
}
```

## Buttons

### Primary Button (Filled)
```css
.btn-primary {
  display: inline-block;
  padding: 12px 22px;
  background: #007AFF;
  color: #FFFFFF;
  border-radius: 980px;
  font-size: 17px;
  font-weight: 400;
  text-decoration: none;
  border: none;
  cursor: pointer;
  transition: background 0.2s ease;
}

.btn-primary:hover {
  background: #0066CC;
}
```

### Secondary Button (Outline)
```css
.btn-secondary {
  display: inline-block;
  padding: 12px 22px;
  background: transparent;
  color: #007AFF;
  border: 1px solid #007AFF;
  border-radius: 980px;
  font-size: 17px;
  font-weight: 400;
  text-decoration: none;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease;
}

.btn-secondary:hover {
  background: #007AFF;
  color: #FFFFFF;
}
```

### Text Link
```css
.link {
  color: #007AFF;
  font-size: 21px;
  text-decoration: none;
}

.link:hover {
  text-decoration: underline;
}

.link--with-arrow::after {
  content: ' >';
  transition: margin-left 0.2s ease;
}

.link--with-arrow:hover::after {
  margin-left: 4px;
}
```

## Feature Cards

### Tile Card
```html
<div class="tile">
  <div class="tile__media">
    <img src="feature.jpg" alt="Feature" />
  </div>
  <div class="tile__content">
    <p class="tile__eyebrow">New</p>
    <h3 class="tile__title">Feature Name</h3>
    <p class="tile__description">Description text goes here.</p>
    <a href="#" class="tile__link">Learn more</a>
  </div>
</div>
```

```css
.tile {
  background: #F5F5F7;
  border-radius: 18px;
  overflow: hidden;
  text-align: center;
}

.tile__media img {
  width: 100%;
  height: auto;
}

.tile__content {
  padding: 35px 30px 40px;
}

.tile__eyebrow {
  font-size: 12px;
  font-weight: 600;
  color: #FF9500;
  text-transform: uppercase;
  letter-spacing: 0.02em;
  margin-bottom: 4px;
}

.tile__title {
  font-size: 28px;
  font-weight: 600;
  color: #1D1D1F;
  margin-bottom: 8px;
}

.tile__description {
  font-size: 17px;
  color: #86868B;
  margin-bottom: 12px;
}

.tile__link {
  color: #007AFF;
  font-size: 17px;
  text-decoration: none;
}
```

## Ribbon / Banner

```css
.ribbon {
  background: #F5F5F7;
  padding: 12px 22px;
  text-align: center;
}

.ribbon__text {
  font-size: 14px;
  color: #1D1D1F;
}

.ribbon__link {
  color: #007AFF;
  text-decoration: none;
}

.ribbon__link:hover {
  text-decoration: underline;
}
```

## Footer

```css
.footer {
  background: #F5F5F7;
  padding: 17px 0 21px;
  border-top: 1px solid #D2D2D7;
}

.footer__container {
  max-width: 980px;
  margin: 0 auto;
  padding: 0 22px;
}

.footer__legal {
  font-size: 12px;
  color: #86868B;
  line-height: 1.33;
  margin-bottom: 7px;
}

.footer__links {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
}

.footer__links a {
  color: #424245;
  text-decoration: none;
}

.footer__links a:hover {
  text-decoration: underline;
}

.footer__divider {
  color: #D2D2D7;
}
```

## Form Elements

### Text Input
```css
.input {
  width: 100%;
  padding: 16px;
  font-size: 17px;
  font-family: inherit;
  background: #FFFFFF;
  border: 1px solid #D2D2D7;
  border-radius: 12px;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.input:focus {
  border-color: #007AFF;
  box-shadow: 0 0 0 4px rgba(0, 122, 255, 0.1);
}

.input::placeholder {
  color: #86868B;
}
```

### Checkbox/Radio
```css
.checkbox {
  appearance: none;
  width: 22px;
  height: 22px;
  border: 2px solid #86868B;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.checkbox:checked {
  background: #007AFF;
  border-color: #007AFF;
  background-image: url('data:image/svg+xml,...'); /* checkmark */
  background-repeat: no-repeat;
  background-position: center;
}
```

## Usage Tips

### Do's
- Use rounded corners (18px for cards, 980px for pills)
- Keep interactions subtle
- Use backdrop blur for overlays
- Maintain consistent spacing

### Don'ts
- Don't use sharp corners
- Avoid heavy drop shadows
- Don't overuse animations
- Avoid cluttered layouts
