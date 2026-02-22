## 2024-05-21 - Initial Audit -> **UX Fail:** Help command command discovery is flaky. **UX Win:** TBD

**Profile:**
- **Command Flow:** `/help` relies on string matching against `app_commands` objects, which might fail if names don't match exactly or if `get_commands()` returns unexpected structures.
- **Visual Design:** Dashboard (`/mycharacter`) is functional but could use more "glance value" for HP/SAN.
- **Dead Ends:** If `generate_help_data` fails to match commands, they end up in "Other" or missing entirely.

**Plan:**
1. Fix `commands/help.py` dynamic discovery logic.
2. Polish `commands/_mychar_view.py` to use better visual indicators (Health Bars are already there, but maybe layout can be improved).
3. Verify `/roll` visuals.
