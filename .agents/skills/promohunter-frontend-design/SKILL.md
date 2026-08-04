---
name: promohunter-frontend-design
description: >
  Design and implement polished PromoHunter frontend interfaces using React 18,
  TypeScript, Vite 5, React Router 6, Leaflet/React Leaflet, plain CSS, existing
  CSS tokens, the project's custom fetch client, and its internal typed SVG icon
  system. Use this skill whenever creating, redesigning, reviewing, or polishing
  PromoHunter pages, components, navigation, map overlays, cards, forms, dialogs,
  bottom sheets, loading states, empty states, responsive layouts, or animations.
  Also use it when the user asks to make the frontend more beautiful, modern,
  mobile-friendly, consistent, accessible, or visually polished.
---

# PromoHunter Frontend Design

Create production-ready frontend changes that look intentionally designed, remain
consistent with the existing application, and do not introduce a foreign design
language.

Do not treat visual work as decoration added after implementation. Layout,
hierarchy, spacing, responsiveness, interaction states, accessibility, and motion
are part of the feature.

## Core stack constraints

Use the project's existing stack:

- React 18.
- TypeScript with strict, explicit types.
- Vite 5.
- React Router 6.
- Leaflet and React Leaflet for maps.
- Plain CSS.
- Existing CSS custom properties from `tokens.css`.
- Existing custom fetch wrapper.
- Existing typed SVG icon components.

Do not introduce any of the following unless the user explicitly requests it:

- Tailwind CSS.
- Material UI.
- Ant Design.
- Bootstrap.
- shadcn/ui.
- Chakra UI.
- Styled Components.
- Emotion.
- Axios.
- An external icon library.
- A second design-token system.
- A CSS framework or UI kit.

Do not access, print, edit, copy, or expose `.env` files or secret values.

## Required workflow

Follow this workflow for every applicable task.

### 1. Inspect before editing

Before writing code:

1. Inspect the relevant route, page, component, styles, and nearby reusable
   components.
2. Read `tokens.css` and reuse existing variables.
3. Inspect the existing icon component before creating or referencing an icon.
4. Inspect the API client and existing response types before adding data calls.
5. Check how responsive layouts, modals, sheets, buttons, inputs, loaders, and
   empty states are already implemented.
6. Identify which parts should be reused, extended, or extracted.

Never assume the project structure or invent imports without checking.

### 2. Preserve architecture

Prefer small, focused changes.

- Reuse existing components and patterns.
- Extract reusable components only when they remove real duplication.
- Keep page-specific code close to the page.
- Keep shared primitives in the existing shared-component location.
- Do not perform unrelated refactoring.
- Do not rewrite working code merely to match personal preferences.
- Keep components easy to read and avoid deeply nested JSX.
- Move non-trivial calculations and transformations into named functions.
- Do not use lambda-style anonymous helper abstractions when a named function is
  clearer.
- Keep the solution KISS and DRY without creating premature abstractions.

### 3. Establish visual hierarchy

Every screen must have a clear hierarchy:

1. Primary page purpose.
2. Primary action or most important status.
3. Main content groups.
4. Secondary information.
5. Tertiary metadata and supporting actions.

Do not make every element equally prominent.

Use whitespace, typography, surface, and position before adding more colors,
borders, or shadows.

### 4. Implement all states

A component that fetches or mutates data is incomplete until it has appropriate:

- Initial state.
- Loading state.
- Success state.
- Empty state.
- Error state.
- Disabled state.
- Focus-visible state.
- Pressed/active state.
- Long-content behavior.
- Mobile layout.
- Wide-screen layout when relevant.

For optimistic or destructive actions, preserve a safe recovery path and provide
clear feedback.

### 5. Review the result

Before finishing:

1. Run the existing type-check, lint, tests, and build commands that apply.
2. Check for TypeScript errors and invalid imports.
3. Check narrow mobile width first, then tablet and desktop.
4. Check long Russian text, long names, missing images, and zero-result lists.
5. Check keyboard focus and `prefers-reduced-motion`.
6. Check that status meaning is not encoded by color alone.
7. Remove accidental visual inconsistencies and duplicated CSS.
8. Summarize what changed and mention any check that could not be run.

## Visual identity

The design language is:

> Warm mobile minimalism with a natural green and terracotta palette, soft
> cards, compact typography, and restrained functional motion.

The interface should feel friendly, human, calm, slightly gastronomic, and
suited to everyday mobile use. It must not look like a corporate dashboard,
generic admin template, crypto product, gaming HUD, or default AI-generated
landing page.

## Color system

Prefer existing variables from `tokens.css`. Do not scatter raw hex colors
through component CSS when a suitable token exists.

Canonical visual references:

- App background: `#F7F5F2`.
- Primary surface: `#FFFFFF`.
- Main text: `#2E2A26`.
- Secondary text: `#6F665E`.
- Primary green: `#6B9080`.
- Soft green surface: `#E3EDE8`.
- Terracotta accent: `#C98B6B`.

Colors should be muted and slightly dusty. Avoid saturated pure blue, neon
green, vivid red, harsh black, and cold blue-gray surfaces.

Terracotta is a scarce accent. Use it for a genuinely important focal element,
such as the raised central navigation action. Do not make every primary button
terracotta.

### Availability statuses

Use the project's semantic status colors and ensure every status also has text
and, where appropriate, an icon:

- Available: soft green.
- Sold out: muted red.
- Possibly sold out: warm amber-orange.
- Possibly available: mint.
- Disputed: sandy yellow.
- No data: neutral gray-beige.

Never rely on color alone.

## Surfaces, borders, and depth

Use white cards on the warm background as the default grouping mechanism.

Preferred radii:

- Cards: `16px`.
- Inputs and ordinary controls: `12px`.
- Pills, counters, and brand chips: fully rounded.
- Floating navigation: `20px`.
- Large illustrative surfaces: up to `24px`.

Preferred standard shadow:

```css
box-shadow: 0 2px 8px rgba(46, 42, 38, 0.06);
```

Use stronger shadows only for:

- Floating bottom navigation.
- Bottom sheets and centered dialogs.
- Map controls and content floating over the map.

Avoid:

- Thick gray borders around every card.
- Multiple competing shadows.
- Glassmorphism across the whole application.
- Excessive gradients.
- Excessively rounded bubble-like layouts.
- Cards nested inside cards without a clear reason.

## Spacing and layout

Use the spacing variables already available in `tokens.css`. When adding a
missing token, choose a coherent compact scale and add it centrally rather than
using arbitrary one-off values repeatedly.

General rules:

- Design mobile-first.
- Keep horizontal mobile padding consistent.
- Use comfortable touch spacing without making the interface sparse.
- Group related elements tightly and separate unrelated groups clearly.
- Align recurring controls and card content.
- Avoid unexplained empty areas.
- Do not solve layout problems with fixed heights unless the content is truly
  fixed.
- Use `min-width: 0` on flex/grid children that may contain long text.
- Ensure text can wrap without overlapping actions.
- Reserve safe space for fixed bottom navigation and device safe areas.

Use:

```css
padding-bottom: calc(var(--navigation-safe-space) + env(safe-area-inset-bottom));
```

or the project's equivalent when content sits above fixed mobile navigation.

## Typography

Use the device system stack already used by the project:

```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
```

Visual guidance:

- Body: about `16px`.
- Page title: about `22px`.
- Card and promo title: about `15px`.
- Labels and metadata: `12px` to `13px`.
- Headings: typically `font-weight: 600`.
- Large headings may use a subtle negative letter spacing.

Typography should remain compact and readable on mobile.

Avoid:

- Oversized marketing headings inside application screens.
- Ultra-light text.
- Long centered paragraphs.
- All-caps labels except very short technical badges.
- Using muted color for essential information.
- More than three visibly competing font sizes in one compact card.

## Components

### Cards

A good card should:

- Have one clear purpose.
- Use a predictable internal layout.
- Expose the most important information first.
- Keep metadata secondary.
- Have one obvious primary interaction.
- Avoid excessive separators.
- Handle long content and missing media gracefully.

Interactive cards need visible hover where pointer devices exist, keyboard
focus, and a subtle pressed state.

### Buttons

Buttons must have clear hierarchy:

- Primary: green by default.
- Secondary: light neutral or soft green surface.
- Tertiary: quiet text or icon action.
- Destructive: muted semantic red, used sparingly.
- Special central navigation action: terracotta when consistent with the
  existing dock.

All buttons must:

- Have a sufficiently large touch target.
- Use a verb or unambiguous icon.
- Show focus-visible state.
- Show disabled state.
- Avoid layout shift during loading.
- Use an inline loader without losing accessible text where possible.

Do not place several visually identical primary buttons in one view.

### Inputs and forms

Forms should:

- Use persistent labels when ambiguity is possible.
- Explain validation near the relevant field.
- Preserve entered values on recoverable errors.
- Use the correct mobile input type and autocomplete attributes.
- Avoid placeholder-only labeling.
- Keep helper and error text compact.
- Make the primary submit action easy to reach on mobile.

### Chips and filters

Use rounded chips for compact filters, brands, counters, and statuses.

- Keep chip labels short.
- Make selected state visually stronger than hover state.
- Ensure multi-select and single-select behavior is obvious.
- Allow horizontal scrolling only when it improves mobile usability.
- Do not hide critical filters behind an unlabeled icon.

### Lists

Lists need:

- Consistent row rhythm.
- Stable alignment.
- Clear tap target.
- Appropriate empty state.
- Skeletons that resemble the final layout.
- No separators when spacing or card grouping already provides enough structure.

### Empty states

An empty state should explain:

1. What is absent.
2. Why that may be normal.
3. What the user can do next.

Keep it concise. Use the project's SVG icon system or a small existing
illustration. Do not use a giant generic illustration that dominates the page.

### Skeletons

Skeletons should match the approximate shape of the final content.

Use a soft shimmer. Disable or simplify it under
`prefers-reduced-motion: reduce`.

Do not show generic full-width gray bars unrelated to the actual layout.

## Navigation

The floating bottom dock is a signature component.

Preserve these characteristics:

- Semi-transparent white surface.
- Backdrop blur where supported.
- Soft large shadow.
- Rounded outer shape.
- Moving soft-green active background.
- Slightly enlarged active icon.
- Raised terracotta center action.
- Correct safe-area handling.
- Enough space around the raised center action.
- No content hidden behind the dock.

Navigation transitions should feel stable. Do not make the entire dock jump,
resize, or reflow when the route changes.

Use semantic navigation elements and accessible labels for icon-only items.

## Map interfaces

The map may occupy the full viewport.

Floating map controls should:

- Share consistent sizing and radius.
- Use white surfaces, a thin border, and a soft shadow.
- Have strong contrast over varied map tiles.
- Show green active state.
- Avoid covering essential Leaflet attribution.
- Avoid conflicting with browser and device safe areas.
- Avoid overlapping the bottom sheet and floating dock.

The selected location should open as a mobile bottom sheet. On wider screens,
use an appropriate anchored card or centered/side presentation if this matches
existing behavior.

For markers:

- Preserve readable hit targets.
- Avoid unnecessary DOM-heavy markers.
- Use semantic status design consistently.
- Provide selected, hover, and focus states when technically applicable.
- Do not introduce map re-renders for unrelated UI state.

## Modals and bottom sheets

On mobile, prefer bottom sheets. On wider screens, use centered dialogs where
appropriate.

Required behavior:

- Dimmed translucent backdrop.
- White surface.
- Large top corner radius on mobile.
- Stable header.
- Scrollable content area.
- Visible close action.
- Escape-key support for dialogs.
- Focus management when the existing modal infrastructure supports it.
- Body scroll lock without losing scroll position.
- Safe-area bottom padding.
- Smooth entrance from below.
- Reduced-motion fallback.

Nested flows must retain the same visual language. Avoid opening multiple
full-screen overlays on top of each other unless the product flow requires it.

## Motion

Motion must be short, restrained, and functional.

Suitable patterns:

- Slight scale-down on press.
- Cards entering with a small upward fade.
- Small stagger for short lists.
- Accordion content with a subtle shift.
- Bottom sheets sliding from below.
- Active navigation indicator moving between items.
- Active icon scaling slightly.
- Soft skeleton shimmer.

Prefer transforms and opacity. Avoid animating expensive layout properties when
a transform can achieve the same effect.

Always support:

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    scroll-behavior: auto;
  }
}
```

Do not blindly disable every transition if the project already has a more
targeted reduced-motion implementation. Follow the existing pattern.

Avoid:

- Long cinematic animations.
- Bouncy spring motion on ordinary controls.
- Animating every element.
- Large parallax effects.
- Motion that delays interaction.
- Repeated attention-seeking pulses.

## Responsive behavior

Implement mobile-first and validate at least these conceptual widths:

- Narrow phone.
- Ordinary phone.
- Tablet.
- Desktop or wide admin layout where relevant.

Do not simply stretch the mobile layout across a desktop.

On wide screens:

- Constrain readable content width.
- Use columns only when they improve scanning.
- Keep map experiences appropriately full-screen or split-panel.
- Center dialogs rather than retaining an oversized mobile sheet.
- Preserve compact application typography.

Avoid breakpoint proliferation. Add a breakpoint only when the layout genuinely
needs to change.

## Accessibility

At minimum:

- Use semantic HTML.
- Ensure icon-only controls have accessible names.
- Preserve visible keyboard focus.
- Maintain useful heading order.
- Associate labels with inputs.
- Use buttons for actions and links for navigation.
- Do not encode status only with color.
- Respect reduced motion.
- Keep touch targets comfortably sized.
- Avoid disabled-looking secondary text for interactive elements.
- Use ARIA only when native semantics are insufficient.

Do not add misleading ARIA roles or duplicate accessible names.

## TypeScript and React quality

- Do not use `any` unless an unavoidable external boundary is documented.
- Reuse or extend existing API types.
- Prefer explicit component props.
- Keep derived state derived; do not duplicate it unnecessarily in state.
- Avoid unnecessary effects.
- Keep effect dependencies correct.
- Keep event handlers named when logic is non-trivial.
- Do not create a new global state solution for local UI state.
- Avoid premature memoization.
- Preserve route and API behavior.
- Use stable keys based on identifiers, not array indexes, when items can change.
- Clean up timers, listeners, observers, and Leaflet resources.

## CSS quality

- Reuse tokens and existing utilities where appropriate.
- Keep selectors shallow.
- Prefer component classes over element chains.
- Avoid `!important` unless overriding unavoidable third-party Leaflet styles;
  document why when used.
- Avoid inline styles for static presentation.
- Use inline style only for genuinely dynamic values and expose them through CSS
  custom properties when practical.
- Do not globally style generic tags from a feature stylesheet.
- Keep z-index values within the project's existing layer system.
- Avoid arbitrary z-index escalation.
- Use logical properties where they improve layout robustness.
- Account for safe areas and overlay stacking.

For Leaflet overrides, scope selectors beneath a page or map root class.

## Visual anti-patterns

Do not produce generic AI-generated UI.

Specifically avoid:

- A large gradient hero on an internal app page.
- Purple-blue SaaS gradients.
- Random emoji used as product icons.
- Excessive glass effects.
- Neon glow.
- Heavy black shadows.
- Huge titles with tiny body content.
- Three-column desktop dashboard cards forced into a mobile app.
- Arbitrary decorative blobs.
- Replacing the project's icon language with a third-party icon set.
- Replacing the warm background with cold white or blue-gray.
- Showing all information inside bordered containers.
- Making every card clickable without a clear reason.
- Decorative animation that distracts from availability data or map use.

## Design decision rules

When details are missing, make decisions in this order:

1. Existing PromoHunter pattern.
2. Existing token or reusable component.
3. The visual identity defined in this skill.
4. Familiar mobile interaction patterns.
5. The smallest new pattern that solves the problem.

If the existing UI and this document conflict, preserve product consistency
unless the user explicitly requested a redesign. Improve incrementally rather
than creating an isolated screen that looks like another application.

## Definition of done

A frontend task is done only when:

- The requested behavior works.
- The result matches PromoHunter's visual identity.
- Existing tokens and components were reused where reasonable.
- Mobile layout is complete.
- Wide-screen behavior is sensible where relevant.
- Loading, empty, error, disabled, focus, and pressed states are addressed where
  applicable.
- Long Russian content does not break the layout.
- Status is understandable without color alone.
- Reduced motion is respected.
- Type-check/build/tests relevant to the change pass, or failures are reported.
- No secret or `.env` content was accessed or exposed.
- No unnecessary dependency or UI framework was added.
