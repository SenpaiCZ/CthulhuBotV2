import sys
from unittest.mock import MagicMock
import asyncio

# Mock discord.py
class MockDiscord(MagicMock):
    pass

discord_mock = MockDiscord()
discord_mock.ui = MagicMock()

# This makes discord.ui.Modal accept kwargs like `title` without raising TypeError when inherited
class MockModal:
    def __init_subclass__(cls, **kwargs):
        pass
discord_mock.ui.Modal = MockModal

discord_mock.TextStyle = MagicMock()
discord_mock.Interaction = MagicMock
discord_mock.Member = MagicMock
discord_mock.app_commands = MagicMock()

sys.modules['discord'] = discord_mock
sys.modules['discord.ext'] = MagicMock()
sys.modules['discord.ext.commands'] = MagicMock()
sys.modules['discord.ui'] = discord_mock.ui
sys.modules['discord.app_commands'] = discord_mock.app_commands

# Mock loadnsave
class MockLoadNSave:
    async def load_player_stats(self):
        return {}
    async def save_player_stats(self, stats):
        pass

sys.modules['loadnsave'] = MockLoadNSave()

# Import the modified file
try:
    import commands.rename as rename_module
    print("Successfully imported commands/rename.py with modifications")
except Exception as e:
    print(f"Error importing commands/rename.py: {e}")
    sys.exit(1)

# Check elements
if not hasattr(rename_module, 'RenameCharacterModal'):
    print("Missing RenameCharacterModal")
    sys.exit(1)

if not hasattr(rename_module, 'rename'):
    print("Missing rename cog")
    sys.exit(1)

print("Mock verification successful!")
sys.exit(0)
