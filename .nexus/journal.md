# Nexus Journal - Architectural Learnings

## 2024-05-22 - [The Soundboard Blocking Hunt] -> **Learning:** `os.listdir` and `zipfile` extraction in Quart routes block the main event loop, causing bot lag during dashboard interactions. **Action:** Moved all soundboard file operations to `dashboard/file_utils.py` and executed them via `asyncio.to_thread`.
