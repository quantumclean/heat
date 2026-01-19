# Liquid Glass Design System — HEAT

Following Apple's 2026 design principles for optical + fluid interfaces.

## Core Principles Applied

### 1. **Optical + Fluid Material**
- Glass material combines optical transparency with sense of fluidity
- Backgrounds use `backdrop-filter: blur()` for true glass effect
- Dynamic response to hover/focus states with fluid morphing

### 2. **Hardware-Informed Curvature**
Concentric corner radii matching device shapes:
```css
--radius-sm: 8px    /* Small controls */
--radius-md: 12px   /* Buttons, inputs */
--radius-lg: 16px   /* Cards, panels */
--radius-xl: 20px   /* Sections */
--radius-2xl: 24px  /* Major containers */
```

### 3. **Reduced Custom Backgrounds**
- Let system handle glass effects automatically
- Remove competing visual layers
- Controls float in distinct functional layer above content

### 4. **Fluid Transitions with Spring Physics**
```css
--transition-fast: 0.15s cubic-bezier(0.4, 0, 0.2, 1)      /* Immediate */
--transition-base: 0.35s cubic-bezier(0.32, 0.72, 0, 1)    /* Standard */
--transition-slow: 0.5s cubic-bezier(0.32, 0.72, 0, 1)     /* Deliberate */
--transition-spring: 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) /* Bounce */
```

## Implementation

### Logo Integration
- Flame SVG with gradient (yellow → orange → red → dark red)
- 48×48px with glow animation
- Positioned in header brand with proper spacing
- Favicon support for PWA

### Glass Components

**Glass Cards:**
```css
background: var(--glass-bg);                  /* 75% opacity */
backdrop-filter: var(--blur-medium);          /* 20px blur */
border: 1px solid var(--glass-border);        /* 12% opacity */
border-radius: var(--radius-lg);              /* 16px */
box-shadow: var(--glass-shadow);              /* Layered shadows */
```

**Glass Buttons:**
- Subtle blur (12px) for lighter weight
- Interactive morphing on hover (scale 1.02, lift -1px)
- Active state with scale 0.96 and fast transition
- Border color intensifies on hover (12% → 18%)

**Header:**
- Glass background with medium blur
- Logo + title in flex brand container
- Concentric controls with proper spacing
- Title gradient (accent → danger)

### Silence Warning Enhancement
Updated "No data ≠ Safe" indicator:
- Larger padding (1.125rem × 1.375rem)
- Gradient background (orange 12% → 6%)
- 4px left border for emphasis
- Proper rounded corners (--radius-lg)
- Smooth fade-in animation (0.4s)

### Content Sections
- Glass background with medium blur
- XL rounded corners (20px) for major containers
- Hover state enhances shadow and border
- Transition uses base timing (0.35s)

## Dark Mode Adaptation

Liquid Glass automatically adapts:
```css
[data-theme="dark"] {
    --glass-bg: rgba(22, 27, 34, 0.75);
    --glass-border: rgba(255, 255, 255, 0.12);
    --glass-shadow: 0 8px 32px rgba(0, 0, 0, 0.4),
                    0 2px 8px rgba(0, 0, 0, 0.2);
}
```

## Accessibility

- Translucency adapts to "Reduce Transparency" setting via standard components
- Motion respects "Reduce Motion" preference
- Focus states use increased contrast
- Touch targets meet 44px iOS guidelines (mobile.css)

## Performance

- Combined glass effects in single container
- Hardware-accelerated transforms
- Efficient blur values (12px/20px/32px)
- CSS containment for paint optimization

## Files Modified

1. **build/logo.svg** — New flame logo with layers
2. **build/index.html** — Added logo, updated header structure
3. **build/styles.css** — Liquid Glass design system, updated variables, components
4. **build/mobile.css** — Touch-optimized details/summary for new sections

## Deployment

- **Status:** ✅ Live
- **URL:** https://d18kxgbrvjlp8x.cloudfront.net
- **CDN:** CloudFront (E7LJPCZOG4PM9)
- **Invalidation:** IALDZCQ20OL19REPV1SC7GFSJY

## Design Philosophy Alignment

Liquid Glass strengthens HEAT's core mission:

1. **Content First** — Glass layer elevates content, doesn't compete
2. **Interpretation Over Surveillance** — Refined aesthetics signal thoughtful approach
3. **Community Safety** — Professional design builds trust in safety-critical tool
4. **Transparent Limitations** — Clear visual hierarchy emphasizes silence-as-signal warnings

---

**References:**
- [Apple Liquid Glass Guidelines](https://developer.apple.com/design/liquid-glass/)
- Concentric design: Hardware shape informs nested interface curvature
- Fluid morphing: Controls dynamically transform during interaction
- Optical properties: Glass refracts, reflects, and blurs underlying content

