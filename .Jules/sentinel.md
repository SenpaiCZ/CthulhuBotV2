## 2024-05-24 - [CSRF Protection in Legacy Dashboard]
**Vulnerability:** The Quart dashboard API endpoints were vulnerable to CSRF because they relied solely on cookie-based authentication (`session['logged_in']`) without verifying the origin of the request.
**Learning:** When implementing CSRF protection via `Origin`/`Referer` headers, a simple `.startswith(trusted_origin)` check is insufficient as it allows prefix matches (e.g., `trusted.com.evil.com`).
**Prevention:** Always use exact matching for `Origin`, and for `Referer`, ensure the trusted origin is followed by a path separator (e.g., `startswith(trusted_origin + "/")`) or check for exact match.
