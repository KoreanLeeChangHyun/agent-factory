# Apple Design - Animation

## Core Principles

### 1. Purposeful Motion
- Animation serves function
- Guides user attention
- Reveals spatial relationships

### 2. Natural & Fluid
- Mimics real-world physics
- Smooth easing curves
- No jarring movements

### 3. Performance First
- Use CSS transforms
- GPU-accelerated properties
- 60fps target

## Easing Functions

### Standard Easings
```css
:root {
  /* Apple's common easings */
  --ease-in-out: cubic-bezier(0.42, 0, 0.58, 1);
  --ease-out: cubic-bezier(0, 0, 0.58, 1);
  --ease-in: cubic-bezier(0.42, 0, 1, 1);

  /* Apple's signature easing */
  --ease-apple: cubic-bezier(0.25, 0.1, 0.25, 1);
  --ease-apple-bounce: cubic-bezier(0.34, 1.56, 0.64, 1);

  /* For scroll animations */
  --ease-scroll: cubic-bezier(0.4, 0, 0.2, 1);
}
```

## Scroll Animations

### Fade In on Scroll
```css
.fade-in {
  opacity: 0;
  transform: translateY(30px);
  transition: opacity 0.6s var(--ease-apple),
              transform 0.6s var(--ease-apple);
}

.fade-in.is-visible {
  opacity: 1;
  transform: translateY(0);
}
```

### JavaScript Observer
```javascript
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('is-visible');
    }
  });
}, {
  threshold: 0.1,
  rootMargin: '0px 0px -50px 0px'
});

document.querySelectorAll('.fade-in').forEach(el => {
  observer.observe(el);
});
```

### Scroll-Driven Animations (CSS)
```css
/* Modern browsers only */
@supports (animation-timeline: scroll()) {
  .parallax-element {
    animation: parallax linear;
    animation-timeline: scroll();
  }

  @keyframes parallax {
    from { transform: translateY(100px); }
    to { transform: translateY(-100px); }
  }
}
```

## Sequence Frame Animation

Apple's signature product reveal animation using image sequences:

```javascript
// Canvas-based frame animation
const canvas = document.getElementById('hero-canvas');
const ctx = canvas.getContext('2d');
const frameCount = 148;
const images = [];

// Preload images
for (let i = 1; i <= frameCount; i++) {
  const img = new Image();
  img.src = `/frames/frame_${i.toString().padStart(4, '0')}.jpg`;
  images.push(img);
}

// Update on scroll
const updateImage = (index) => {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(images[index], 0, 0, canvas.width, canvas.height);
};

window.addEventListener('scroll', () => {
  const scrollTop = window.scrollY;
  const maxScroll = document.body.scrollHeight - window.innerHeight;
  const scrollFraction = scrollTop / maxScroll;
  const frameIndex = Math.min(
    frameCount - 1,
    Math.floor(scrollFraction * frameCount)
  );
  requestAnimationFrame(() => updateImage(frameIndex));
});
```

## Micro-interactions

### Button Hover
```css
.button {
  background: #007AFF;
  color: white;
  padding: 12px 24px;
  border-radius: 980px;
  border: none;
  font-size: 17px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.2s ease;
}

.button:hover {
  background: #0066CC;
}

.button:active {
  transform: scale(0.98);
}
```

### Link Hover
```css
.link {
  color: #007AFF;
  text-decoration: none;
  transition: color 0.2s ease;
}

.link:hover {
  color: #0066CC;
  text-decoration: underline;
}

/* Arrow animation */
.link-arrow {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.link-arrow svg {
  transition: transform 0.2s ease;
}

.link-arrow:hover svg {
  transform: translateX(4px);
}
```

### Card Hover
```css
.card {
  transition: transform 0.3s var(--ease-apple),
              box-shadow 0.3s var(--ease-apple);
}

.card:hover {
  transform: scale(1.02) translateY(-4px);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
}
```

## Page Transitions

### Section Entrance
```css
.section {
  opacity: 0;
  transform: translateY(60px);
  transition: opacity 0.8s var(--ease-apple) 0.2s,
              transform 0.8s var(--ease-apple) 0.2s;
}

.section.is-visible {
  opacity: 1;
  transform: translateY(0);
}
```

### Staggered Items
```css
.stagger-item {
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 0.5s var(--ease-apple),
              transform 0.5s var(--ease-apple);
}

.stagger-item:nth-child(1) { transition-delay: 0.1s; }
.stagger-item:nth-child(2) { transition-delay: 0.2s; }
.stagger-item:nth-child(3) { transition-delay: 0.3s; }
.stagger-item:nth-child(4) { transition-delay: 0.4s; }

.stagger-container.is-visible .stagger-item {
  opacity: 1;
  transform: translateY(0);
}
```

## Video Background

```css
.video-hero {
  position: relative;
  width: 100%;
  height: 100vh;
  overflow: hidden;
}

.video-hero video {
  position: absolute;
  top: 50%;
  left: 50%;
  min-width: 100%;
  min-height: 100%;
  transform: translate(-50%, -50%);
  object-fit: cover;
}
```

## Performance Tips

### Use Transform & Opacity Only
```css
/* Good - GPU accelerated */
.animated {
  transform: translateY(20px);
  opacity: 0;
}

/* Avoid - causes reflow */
.animated {
  top: 20px;
  margin-top: 20px;
}
```

### Will-Change Hint
```css
/* Use sparingly */
.will-animate {
  will-change: transform, opacity;
}
```

### Reduce Motion
```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```
