# Grammar and Style Report

This report lists identified grammatical errors, typos, and stylistic suggestions for the CthulhuBotV2 codebase.

## 1. Documentation (`README.md`)

| Original Text | Suggested Correction | Reason |
| :--- | :--- | :--- |
| `reaction to messages` | `reacting to messages` | Grammar flow. |
| `easily configure` | `Easily configure` | Capitalization consistency. |
| `Auto Deleter` | `Auto-Deleter` | Hyphenation consistency. |
| `install ffmpeg` | `install FFmpeg` | Proper noun capitalization. |
| `System PATH` | `system PATH` | Minor capitalization fix. |

## 2. Info Data (`infodata/*.json`)

### `infodata/poisons_info.json`
*   **Filename:** Rename to `infodata/poisons_info.json` (Typo in filename).
*   **Content:**
    *   `handfulls` -> `handfuls` (Entry: Yew).

### `infodata/inventions_info.json`
*   `1800s`: `auto-mobile` -> `automobile`.
*   `1880s`: `invents Kinetoscope` -> `invents the Kinetoscope`.
*   `1910s`: Fragment `BERy articulated streetcar no. 2 in 1913.` -> `The Boston Elevated Railway introduces articulated streetcar no. 2 in 1913.`
*   `1930s`: `The Supersonic` -> `The supersonic` (Capitalization).
*   `1930s`: `The Phase-contrast` -> `Phase-contrast` (Article usage).
*   `1950s`: `water-closet` -> `water closet`.
*   `1990s`: `on short distances` -> `over short distances`.

### `infodata/archetype_info.json`
*   `divided amongst` -> `divided among` (Consistency).
*   `You can get random two with !tinfo.` -> `You can get two random ones with !tinfo.` (Word order).

## 3. Python Commands (`commands/*.py`)

### `commands/mychar.py`
*   `You are CHONKER!` -> `You are a CHONKER!` (Grammar).
*   `to see others.` -> `to see another's.` (Grammar).

### `commands/newroll.py`
*   `The first successful rolls have been recorded!` -> `The first successful roll has been recorded!` (Singular event context).

## 4. Dashboard Templates (`dashboard/templates/*.html`)

### `base.html` & `admin_dashboard.html`
*   `Automatization` -> `Automation` (Menu header).
*   `Auto rooms` -> `Auto Rooms` (Capitalization).
*   `Pokemon Go` / `Pokemon GO` -> Standardize to `Pokemon GO`.

## 5. Other
*   `loadnsave.py`: Update reference to `poisions_info.json` to `poisons_info.json`.
