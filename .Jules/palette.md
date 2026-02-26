## 2026-02-26 - Focus Management in Dynamic Lists
**Learning:** Automatically moving focus to the new input field in a dynamic list significantly reduces friction for repetitive data entry, especially for keyboard users. This pattern is often overlooked but provides high value in "power user" interfaces like game settings.
**Action:** Always check if a "Add" action can be followed by a `focus()` call to the next logical input, particularly in modals or wizards.
