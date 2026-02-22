## 2024-10-18 - Accessibility in Dynamic Content
**Learning:** Dynamic content generation (via JS innerHTML) often misses accessibility attributes that are standard in static HTML, creating invisible barriers for screen reader users.
**Action:** When generating HTML in JS, always include `aria-label` attributes that incorporate dynamic context (e.g., specific item names or server names) to differentiate identical-looking controls.

## 2024-10-27 - Semantic HTML & Keyboard Navigation
**Learning:** Adding a "Skip to Content" link is a critical accessibility pattern for keyboard users, but it only works effectively if the target container (e.g., `<main>`) has `tabindex="-1"` to ensure programmatic focus is received and maintained across all browsers.
**Action:** Always pair skip links with a target container that has `id="..."` and `tabindex="-1"`.

## 2026-02-21 - [ARIA for List-Detail Views]
**Learning:** Transforming list-detail views into accessible tab interfaces requires consistent role application (tablist/tab/tabpanel) and dynamic state management (aria-selected, aria-controls) to be meaningful for screen reader users.
**Action:** When refactoring list-detail components, prioritize `role="tab"` patterns over generic button lists to communicate relationship and state effectively.

## 2024-10-31 - Security and Accessibility in Template Literals
**Learning:** When injecting dynamic content (like song titles) into HTML via template literals, it is crucial to sanitize the input to prevent XSS and to use that sanitized content in `aria-label` and `alt` attributes to ensure screen readers receive meaningful context.
**Action:** Always include an `escapeHtml` utility when working with client-side rendering and use it for both visual text and accessibility attributes.
