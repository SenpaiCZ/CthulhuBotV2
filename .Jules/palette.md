## 2024-10-18 - Accessibility in Dynamic Content
**Learning:** Dynamic content generation (via JS innerHTML) often misses accessibility attributes that are standard in static HTML, creating invisible barriers for screen reader users.
**Action:** When generating HTML in JS, always include `aria-label` attributes that incorporate dynamic context (e.g., specific item names or server names) to differentiate identical-looking controls.
