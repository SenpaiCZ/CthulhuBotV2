## 2025-03-02 - Enforcing Defense in Depth for File Serving
**Vulnerability:** Weak path traversal checks in Flask/Quart endpoints `serve_fonts`, `serve_image` and `backup_download_file`.
**Learning:** While `send_from_directory` generally offers basic traversal protection, relying solely on it or a simple string check (`.. in filename`) is insufficient defense in depth. Explicit server-side normalization (`os.path.abspath`) and prefix checking (`os.path.commonpath`) offer better and foolproof security.
**Prevention:** Always implement `os.path.commonpath([full_path, base_path]) == base_path` whenever serving files from dynamically parsed URL paths or inputs, rather than depending purely on framework defaults or naive string checking.
