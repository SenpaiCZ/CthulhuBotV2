## 2024-05-24 - Fix Reflected XSS in 404 Error Pages
**Vulnerability:** Reflected Cross-Site Scripting (XSS) in `dashboard/app.py` `render_*` routes. The `name` query parameter was directly interpolated into the 404 error HTML response.
**Learning:** Quart uses `text/html` by default for string returns. Any unescaped user input directly returned in these strings can execute arbitrary JavaScript in the victim's browser.
**Prevention:** Always use an HTML escaper (like `markupsafe.escape`) when interpolating user-controlled data into HTML strings, even for simple error messages like 404s.