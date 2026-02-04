## 2024-10-26 - Invisible Icons
**Learning:** This project uses Bootstrap Icons classes (e.g., `bi-file-earmark-person`) but was missing the CDN link in `base.html`, rendering important UI elements (like "View Sheet" icons) invisible without error.
**Action:** Always check `base.html` or `package.json` to verify that icon libraries used in templates are actually imported.
