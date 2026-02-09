## 2026-02-09 - Accessible Skip Links require Tabindex
**Learning:** Skip-to-content links pointing to a non-interactive element (like a main div) might not move keyboard focus in all browsers unless that element has `tabindex="-1"`.
**Action:** Always add `tabindex="-1"` and `id` to the target container of a skip link, preferably using semantic `<main>` tag.
