# Nexus's UX Journal

## 2024-10-24 - Stat Command Interaction Upgrade
**UX Fail:** Users had to react with emojis (✅/❌) to confirm HP/MP limits, which is slow and clunky. Error messages were public and spammed the chat.
**UX Win:** Replaced `wait_for("reaction_add")` with `discord.ui.View` and Buttons (Go over limit/Stop/Set Max) for instant interaction. Made error messages and advice `ephemeral=True` to reduce noise. Autocomplete now shows current values for better context.
