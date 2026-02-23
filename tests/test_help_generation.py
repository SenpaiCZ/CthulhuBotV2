import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Add root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 1. Mock Discord Structure BEFORE importing commands.help
discord = MagicMock()
discord.ext = MagicMock()
discord_ext_commands = MagicMock()

# Ensure Cog is a class we can inherit from if needed, or just a Mock
class MockCog:
    pass
discord_ext_commands.Cog = MockCog

discord.ext.commands = discord_ext_commands

# Apply to sys.modules
sys.modules['discord'] = discord
sys.modules['discord.ext'] = discord.ext
sys.modules['discord.ext.commands'] = discord_ext_commands
sys.modules['discord.app_commands'] = MagicMock()
sys.modules['discord.ui'] = MagicMock()

# 2. Import the module under test
# This will use the mocks above
from commands.help import Help, LEGACY_CATEGORY_MAP

import unittest

class TestHelpGeneration(unittest.IsolatedAsyncioTestCase):
    async def test_generate_help_data(self):
        # Setup Mock Bot
        bot = MagicMock()
        bot.tree.get_commands.return_value = [] # No extra tree commands for now

        # Define Cog Classes to test logic
        # We need classes to properly test hasattr() behavior, as MagicMocks behave weirdly with hasattr

        class LegacyRollCog:
            def get_app_commands(self):
                cmd = MagicMock()
                cmd.name = "roll"
                return [cmd]
            def get_commands(self): return []

        class NewLootCog:
            help_category = "Keeper"
            def get_app_commands(self):
                cmd = MagicMock()
                cmd.name = "loot"
                return [cmd]
            def get_commands(self): return []

        class MysteryCog:
            def get_app_commands(self):
                cmd = MagicMock()
                cmd.name = "mystery"
                return [cmd]
            def get_commands(self): return []

        # Populate bot.cogs
        # "Roll" is in LEGACY_CATEGORY_MAP -> should be "Player"
        # "Loot" has help_category -> should be "Keeper"
        # "Mystery" is neither -> should be "Other"

        bot.cogs = {
            "Roll": LegacyRollCog(),
            "Loot": NewLootCog(),
            "Mystery": MysteryCog()
        }

        # Initialize Help Cog
        help_cog = Help(bot)

        # Mock Context (needed for _can_run checks on legacy commands, though we invoke app commands here)
        ctx = AsyncMock()

        # Execute
        print("Generating Help Data...")
        data = await help_cog.generate_help_data(ctx)

        # Verification
        print("Help Data Generated:", {k: [c.name for c in v] for k,v in data.items()})

        # 1. Check Player (Roll)
        self.assertIn("Player", data)
        self.assertTrue(any(c.name == "roll" for c in data["Player"]), "Roll command not found in Player category")

        # 2. Check Keeper (Loot)
        self.assertIn("Keeper", data)
        self.assertTrue(any(c.name == "loot" for c in data["Keeper"]), "Loot command not found in Keeper category")

        # 3. Check Other (Mystery)
        self.assertIn("Other", data)
        self.assertTrue(any(c.name == "mystery" for c in data["Other"]), "Mystery command not found in Other category")

        print("SUCCESS: All categories verified.")

if __name__ == '__main__':
    unittest.main()
