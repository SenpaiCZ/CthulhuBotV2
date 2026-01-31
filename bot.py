import discord
from discord.ext import commands
import asyncio
import os
from loadnsave import load_settings, load_server_stats
from help_command import CustomHelpCommand
from dashboard.app import app
from hypercorn.asyncio import serve
from hypercorn.config import Config

# Load the settings
settings = load_settings()
# Token printing removed for security

# Function to get the bot's prefix dynamically from the JSON file or mentions
async def get_prefix(bot, message):
    server_prefixes = await load_server_stats()
    server_id = str(message.guild.id) if message.guild else None
    server_prefix = server_prefixes.get(server_id, "!") if server_id else "!"
    return commands.when_mentioned_or(server_prefix)(bot, message)

# Create a bot instance and pass it to the CustomHelpCommand constructor
bot = commands.Bot(command_prefix=get_prefix,
                   description='Call of Cthulhu MASTER bot',
                   intents=discord.Intents.all())

help_command = CustomHelpCommand()
bot.help_command = help_command

# Loading cogs!
async def load():
  # in folder commands
  for filename in os.listdir('./commands'):
    # all files ending with .py
    if filename.endswith('.py') and not filename.startswith('_'):
      # load as extensions
      try:
        await bot.load_extension(f"commands.{filename[:-3]}")
        print(f"{filename[:-3]} is now LOADED! Yeah Baby!")
      except commands.errors.NoEntryPointError:
        print(f"Warning: {filename} has no 'setup' function. Skipping.")
      except Exception as e:
        print(f"Failed to load extension {filename}: {e}")

async def main():
  async with bot:
    await load()

    # Start Dashboard if enabled
    if settings.get("enable_dashboard", False):
        print(f"Starting Dashboard on port {settings.get('dashboard_port', 5000)}...")
        config = Config()
        config.bind = [f"0.0.0.0:{settings.get('dashboard_port', 5000)}"]
        # Run Hypercorn in the background
        asyncio.create_task(serve(app, config))
    
    # Ensure token exists before starting
    if settings.get("token"):
        TOKEN = settings["token"]
        await bot.start(TOKEN)
    else:
        print("Error: Bot token not found in settings or environment variables.")

if __name__ == "__main__":
    asyncio.run(main())
