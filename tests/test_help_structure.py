import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
sys.path.append(os.getcwd())

from commands.help import Help, COG_GROUPS

async def test_help_generation():
    print("Starting Help Generation Test...")

    # Mock Bot
    bot = MagicMock()
    bot.cogs = {}

    # Mock Context
    ctx = MagicMock()
    ctx.author.id = 123

    # specific test cases

    # 1. Standard Cog (Character)
    char_cog = MagicMock()
    char_cmd = AsyncMock()
    char_cmd.name = "newinv"
    char_cmd.hidden = False
    char_cmd.can_run.return_value = True
    char_cog.get_commands.return_value = [char_cmd]
    bot.cogs["newinvestigator"] = char_cog

    # 2. Hidden Command
    hidden_cog = MagicMock()
    hidden_cmd = AsyncMock()
    hidden_cmd.name = "secret"
    hidden_cmd.hidden = True
    hidden_cog.get_commands.return_value = [hidden_cmd]
    bot.cogs["secret_cog"] = hidden_cog

    # 3. Admin Command (No Access)
    admin_cog = MagicMock()
    admin_cmd = AsyncMock()
    admin_cmd.name = "ban"
    admin_cmd.hidden = False
    admin_cmd.can_run.side_effect = Exception("Permission Denied") # specific Exception type not needed for mock
    admin_cog.get_commands.return_value = [admin_cmd]
    bot.cogs["admin_slash"] = admin_cog

    # 4. Uncategorized (Other)
    other_cog = MagicMock()
    other_cmd = AsyncMock()
    other_cmd.name = "foo"
    other_cmd.hidden = False
    other_cmd.can_run.return_value = True
    other_cog.get_commands.return_value = [other_cmd]
    bot.cogs["unknown_cog"] = other_cog

    # Initialize Help Cog
    help_cog = Help(bot)

    # Run Generation
    print("Calling generate_help_data...")
    data = await help_cog.generate_help_data(ctx)

    # Assertions
    print("Verifying Results...")

    # Character Category should exist and contain newinv
    assert "Character" in data, "Character category missing"
    assert any(c.name == "newinv" for c in data["Character"]), "newinv command missing from Character"
    print("✅ Character Category Verified")

    # Hidden command should NOT be present
    all_cmds = []
    for cmds in data.values(): all_cmds.extend(cmds)
    assert not any(c.name == "secret" for c in all_cmds), "Hidden command 'secret' is visible!"
    print("✅ Hidden Command Verified")

    # Admin command should NOT be present (due to exception)
    assert not any(c.name == "ban" for c in all_cmds), "Admin command 'ban' is visible!"
    print("✅ Admin Permission Check Verified")

    # Other Category should exist
    assert "Other" in data, "Other category missing" # Assuming I defaulted to "Other"
    # Actually, check COG_GROUPS logic.
    # COG_GROUPS.get(cog_name.lower(), "Other")
    # "unknown_cog" -> "Other"
    assert any(c.name == "foo" for c in data.get("Other", [])), "foo command missing from Other"
    print("✅ Uncategorized/Other Logic Verified")

    print("🎉 All Tests Passed!")

if __name__ == "__main__":
    asyncio.run(test_help_generation())
