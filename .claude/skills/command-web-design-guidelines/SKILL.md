---
name: command-web-design-guidelines
description: Provides web accessibility and standards compliance checklists for implementation tasks. Use this skill when building or reviewing web interfaces that must meet WCAG 2.1 Level AA, ARIA requirements, keyboard navigation, form accessibility, dark mode support, or internationalization readiness. Triggers on keywords including accessibility, a11y, WCAG, form, dark mode, color contrast, keyboard navigation, screen reader, semantic HTML, and responsive design.
---

# Web Design Guidelines

Accessibility and standards compliance technical checklist for web implementation. This skill focuses on **technical correctness and standards adherence** -- for visual design quality and aesthetic judgment, see `frontend-design`.

## Role Separation

| Skill | Scope |
|-------|-------|
| `frontend-design` | Design quality, aesthetics, typography, color, motion, spatial composition |
| `command-web-design-guidelines` | Accessibility compliance, standards checklists, technical correctness |

Apply both when building user-facing web interfaces: `frontend-design` for how it looks, this skill for how it works for all users.

## WCAG 2.1 Level AA Checklist

### Perceivable

1. **Text alternatives**: All non-text content has `alt` text. Decorative images use `alt=""` or `role="presentation"`.
2. **Captions/transcripts**: Pre-recorded audio/video has captions. Live audio has captions where feasible.
3. **Color contrast**: Normal text >= 4.5:1 ratio. Large text (18px bold / 24px regular) >= 3:1 ratio. UI components and graphical objects >= 3:1 ratio.
4. **Resize**: Content readable at 200% zoom without horizontal scrolling at 1280px viewport.
5. **Text spacing**: No loss of content when line-height is 1.5x, paragraph spacing is 2x, letter spacing is 0.12em, word spacing is 0.16em.
6. **Images of text**: Avoid. Use real text with CSS styling.

### Operable

7. **Keyboard accessible**: All functionality available via keyboard. No keyboard traps. Shortcut keys can be disabled or remapped.
8. **Focus order**: Logical tab sequence matching visual layout. Never use positive `tabindex` values.
9. **Focus visible**: Custom focus indicators with >= 3:1 contrast. Minimum 2px outline. Never `outline: none` without replacement.
10. **Skip navigation**: "Skip to main content" link as first focusable element.
11. **Page titles**: Unique, descriptive `<title>` per page.
12. **Link purpose**: Link text meaningful in context. Avoid "click here" or "read more" without context.
13. **Timing**: If time limits exist, users can turn off, adjust, or extend (at least 10x).
14. **Motion/animation**: Respect `prefers-reduced-motion`. Provide pause/stop controls for auto-playing content.

### Understandable

15. **Language**: `lang` attribute on `<html>`. `lang` attribute on passages in different languages.
16. **Predictable navigation**: Consistent navigation across pages. No unexpected context changes on focus or input.
17. **Error identification**: Errors described in text (not just color). Error message associated to field via `aria-describedby` or `aria-errormessage`.
18. **Labels/instructions**: Form inputs have visible labels. Required fields indicated in text (not just `*`).
19. **Error prevention**: For legal/financial submissions, allow review, confirm, and reverse actions.

### Robust

20. **Valid HTML**: No duplicate IDs. Proper nesting. Complete start/end tags.
21. **Name/role/value**: Custom controls expose correct ARIA roles, states, and properties.
22. **Status messages**: Dynamic content updates use `aria-live` regions. Use `role="alert"` for errors, `role="status"` for informational updates.

## ARIA Patterns

### Required ARIA Attributes by Component

```
Button:        role="button" (implicit for <button>)
               aria-pressed (toggle), aria-expanded (menu trigger)

Dialog/Modal:  role="dialog", aria-modal="true"
               aria-labelledby (title), aria-describedby (description)
               Focus trap: tab cycles within modal

Tabs:          role="tablist" > role="tab" + role="tabpanel"
               aria-selected, aria-controls, aria-labelledby

Menu:          role="menu" > role="menuitem"
               aria-haspopup, aria-expanded
               Arrow key navigation

Combobox:      role="combobox", aria-expanded, aria-controls
               aria-activedescendant for active option
               role="listbox" > role="option"

Alert:         role="alert" (assertive) or role="status" (polite)
               aria-live="assertive" or "polite"

Progress:      role="progressbar"
               aria-valuenow, aria-valuemin, aria-valuemax, aria-label

Breadcrumb:    <nav aria-label="Breadcrumb">
               aria-current="page" on current item

Accordion:     <button aria-expanded="true/false" aria-controls="panel-id">
               role="region" on panel, aria-labelledby pointing to button
```

### ARIA Rules

1. Prefer native HTML elements over ARIA: `<button>` over `<div role="button">`.
2. Never change native semantics: avoid `<h2 role="tab">`.
3. All interactive ARIA controls must be keyboard operable.
4. Never use `aria-hidden="true"` on focusable elements.
5. All interactive elements must have accessible names (via content, `aria-label`, or `aria-labelledby`).

## Keyboard Navigation

### Expected Key Behaviors

| Pattern | Keys | Behavior |
|---------|------|----------|
| Buttons | Enter, Space | Activate |
| Links | Enter | Navigate |
| Tab panels | Arrow Left/Right | Switch tabs |
| Menu items | Arrow Up/Down | Navigate items |
| Dropdowns | Escape | Close |
| Modals | Escape | Close, return focus to trigger |
| Radio groups | Arrow keys | Move selection |
| Checkboxes | Space | Toggle |
| Sliders | Arrow keys | Increment/decrement |

### Focus Management

- Trap focus inside modals (cycle Tab between first and last focusable elements).
- On modal close, return focus to the element that opened it.
- On route change in SPAs, move focus to main content or announce via `aria-live`.
- Use `inert` attribute on background content when modal is open.
- Manage `aria-activedescendant` for composite widgets (listbox, combobox, grid).

## Form Accessibility

### Input Patterns

```html
<!-- Proper label association -->
<label for="email">Email address</label>
<input id="email" type="email" required aria-required="true"
       aria-describedby="email-hint email-error">
<p id="email-hint" class="hint">We will never share your email.</p>
<p id="email-error" class="error" role="alert" aria-live="assertive"></p>

<!-- Group related inputs -->
<fieldset>
  <legend>Shipping address</legend>
  <!-- address fields -->
</fieldset>

<!-- Required field indication -->
<p class="form-note">Fields marked with <span aria-hidden="true">*</span>
<span class="sr-only">asterisk</span> are required.</p>
```

### Validation Patterns

1. **Inline validation**: Validate on blur (not on every keystroke). Show error adjacent to field.
2. **Summary on submit**: List all errors at top of form with links to each field. Move focus to summary.
3. **Prevent submission of invalid forms**: Announce error count via `aria-live` region.
4. **Error messages**: Specific ("Email must include @") not generic ("Invalid input").
5. **Success confirmation**: Announce via `role="status"` or redirect to confirmation page.

### Autocomplete

Use `autocomplete` attributes for common fields:

```
name, email, tel, street-address, postal-code,
country, cc-number, cc-exp, cc-csc,
username, current-password, new-password
```

## Color and Contrast

### Checking Contrast Ratios

| Element | Minimum Ratio (AA) | Enhanced (AAA) |
|---------|-------------------|----------------|
| Normal text (< 18px / < 14px bold) | 4.5:1 | 7:1 |
| Large text (>= 18px / >= 14px bold) | 3:1 | 4.5:1 |
| UI components (borders, icons) | 3:1 | N/A |
| Non-text contrast (charts, graphs) | 3:1 | N/A |

### Color Independence

- Never convey information by color alone. Add text labels, icons, or patterns.
- Form errors: red border + error icon + text message.
- Charts: use patterns/shapes in addition to colors.
- Links in text: underline or 3:1 contrast with surrounding text + non-color indicator on hover/focus.

## Dark Mode Implementation

### CSS Strategy

```css
/* System preference detection */
@media (prefers-color-scheme: dark) {
  :root { /* dark tokens */ }
}

/* Manual toggle support */
[data-theme="dark"] { /* dark tokens */ }
[data-theme="light"] { /* light tokens */ }
```

### Dark Mode Rules

1. **Token-based**: All colors via CSS custom properties. Never hard-code colors in components.
2. **Contrast preserved**: Re-check all contrast ratios in dark mode. Dark backgrounds need lighter text with same AA ratios.
3. **Elevated surfaces**: Use lighter shades (not just opacity) for elevation in dark mode.
4. **Images**: Consider `filter: brightness(0.85)` for images in dark mode. Provide dark variants for logos/illustrations where possible.
5. **Shadows**: Replace box-shadows with subtle borders or lighter overlays in dark mode.
6. **Persistence**: Store preference in `localStorage`. Initialize before first paint to prevent flash.
7. **Transition**: Use `transition: background-color 0.2s, color 0.2s` for smooth switching. Exclude transition on initial load.

## Animation Accessibility

### Motion Preferences

```css
/* Default: include animations */
.element {
  animation: fadeIn 0.3s ease;
  transition: transform 0.2s ease;
}

/* Respect user preference */
@media (prefers-reduced-motion: reduce) {
  .element {
    animation: none;
    transition: none;
  }
  /* Or provide subtle alternatives */
  .element {
    animation-duration: 0.01ms;
    transition-duration: 0.01ms;
  }
}
```

### Motion Rules

1. Never auto-play animations longer than 5 seconds without pause controls.
2. No content conveyed only through motion.
3. Avoid parallax scrolling or provide non-motion alternative.
4. Flashing content: never exceed 3 flashes per second.
5. Vestibular triggers: avoid large-scale motion, zooming animations, spinning effects unless behind `prefers-reduced-motion` guard.

## Internationalization Readiness

### Text Direction

```css
/* Logical properties for RTL support */
margin-inline-start: 1rem;  /* not margin-left */
padding-inline-end: 1rem;   /* not padding-right */
inset-inline-start: 0;      /* not left: 0 */
border-inline-end: 1px solid;
text-align: start;           /* not text-align: left */
```

### i18n Patterns

1. **No hardcoded strings**: Extract all user-facing text to translation files.
2. **Flexible layouts**: Design for text expansion (German ~30% longer than English). Avoid fixed-width containers for text.
3. **Date/number formatting**: Use `Intl.DateTimeFormat` and `Intl.NumberFormat`.
4. **Pluralization**: Handle 0/1/many cases. Use ICU MessageFormat or equivalent.
5. **Text in images**: Avoid. If unavoidable, provide translated variants.
6. **Font stacks**: Include CJK and Arabic font fallbacks in global styles.
7. **`lang` attribute**: Set on `<html>` and override on inline foreign-language content.

## Semantic HTML Reference

### Landmark Regions

```html
<header>       <!-- Banner landmark: site header -->
<nav>          <!-- Navigation landmark -->
<main>         <!-- Main landmark: primary content (one per page) -->
<aside>        <!-- Complementary landmark: sidebar -->
<footer>       <!-- Contentinfo landmark: site footer -->
<section>      <!-- Generic with aria-label becomes region landmark -->
<form>         <!-- Form landmark when has accessible name -->
<search>       <!-- Search landmark (HTML5.2+) -->
```

### Heading Hierarchy

- One `<h1>` per page.
- Never skip levels (h1 -> h3 without h2).
- Headings describe the content below them.
- Use headings for structure, not for visual sizing (use CSS).

### Lists

- Navigation menus: `<ul>` with `<li>` inside `<nav>`.
- Ordered steps: `<ol>`.
- Key-value pairs: `<dl>`, `<dt>`, `<dd>`.

## Responsive Design

### Breakpoint Strategy

```css
/* Mobile-first approach */
.container { /* mobile styles */ }

@media (min-width: 640px)  { /* sm: tablet */ }
@media (min-width: 768px)  { /* md: tablet landscape */ }
@media (min-width: 1024px) { /* lg: desktop */ }
@media (min-width: 1280px) { /* xl: wide desktop */ }
```

### Touch Targets

- Minimum 44x44 CSS pixels for interactive elements (WCAG 2.5.8).
- Minimum 8px spacing between adjacent touch targets.
- Inline links in text are exempt if block alternative exists.

### Responsive Rules

1. Content readable without horizontal scrolling at any viewport >= 320px.
2. Use relative units (`rem`, `em`, `%`, `vw`) for sizing. Avoid fixed pixel widths for containers.
3. Hide/show content based on viewport: use `display: none` (removes from a11y tree) or `visibility: hidden` + `position: absolute` (hides visually, keeps in tree).
4. Test with screen magnification at 400%.

## Testing Checklist

Before marking accessible implementation complete:

- [ ] Run axe-core or Lighthouse accessibility audit. Score >= 90.
- [ ] Keyboard-only navigation through all interactive flows.
- [ ] Screen reader testing (VoiceOver/NVDA) on primary user flows.
- [ ] Color contrast verified for all text and UI elements in both light and dark themes.
- [ ] `prefers-reduced-motion` behavior verified.
- [ ] HTML validation: no duplicate IDs, proper nesting.
- [ ] Focus indicators visible on all interactive elements.
- [ ] Form error handling tested with assistive technology.
- [ ] Resize to 200% and 400% without content loss.
- [ ] Touch targets meet 44x44px minimum on mobile.
