## 2024-05-22 - Accessibility of Destructive Actions
**Learning:** Icon-only buttons for critical destructive actions (like "Delete Character") are a common pattern in this app but lack accessibility labels, making them invisible to screen readers and potentially confusing without tooltips.
**Action:** Always pair icon-only buttons with `aria-label` for screen readers and `data-bs-toggle="tooltip"` for visual users to ensure intent is clear before clicking.
