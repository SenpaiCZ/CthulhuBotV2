import discord
from discord.ext import commands
import asyncio
import os
from loadnsave import load_settings, load_server_stats
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
                   intents=discord.Intents.all(),
                   help_command=None)

# Global list to track failed loads
bot.failed_extensions = []

UPDATE_HEALTH_MARKER = "update_health.marker"  # must match updater.py's copy of this filename
ROLLBACK_NOTICE_FILE = "rollback_notice.txt"   # must match updater.py's copy of this filename


async def _get_owner(bot_instance):
    """Resolve the bot owner (handling Team ownership), or None if unavailable."""
    try:
        app_info = await bot_instance.application_info()
        owner = app_info.owner

        # Handle Team ownership edge case
        if isinstance(owner, discord.Team):
            owner = getattr(owner, 'owner', None)
            if isinstance(owner, int):
                owner = await bot_instance.fetch_user(owner)

        return owner if owner and hasattr(owner, 'send') else None
    except Exception as e:
        print(f"Failed to resolve bot owner: {e}")
        return None


def _write_health_marker():
    try:
        open(UPDATE_HEALTH_MARKER, "w").close()
    except Exception as e:
        print(f"Failed to write health marker: {e}")


async def _send_rollback_notice_if_present(bot_instance):
    if not os.path.exists(ROLLBACK_NOTICE_FILE):
        return
    try:
        with open(ROLLBACK_NOTICE_FILE, "r", encoding="utf-8") as f:
            message = f.read()
        owner = await _get_owner(bot_instance)
        if owner:
            await owner.send(message)
    except Exception as e:
        print(f"Failed to send rollback notice: {e}")
    finally:
        try:
            os.remove(ROLLBACK_NOTICE_FILE)
        except Exception:
            pass


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

    _write_health_marker()

    if hasattr(bot, 'failed_extensions') and bot.failed_extensions:
        try:
            owner = await _get_owner(bot)

            if owner:
                error_message = "**⚠️ Startup Issues:**\nThe following extensions failed to load:\n\n"
                for filename, error in bot.failed_extensions:
                    error_message += f"**{filename}**:\n`{error}`\n\n"

                # Send DM (chunk if necessary)
                if len(error_message) > 2000:
                    chunks = [error_message[i:i+1900] for i in range(0, len(error_message), 1900)]
                    for chunk in chunks:
                        await owner.send(chunk)
                else:
                    await owner.send(error_message)

                print(f"Sent error report to owner: {owner}")
                bot.failed_extensions = [] # Clear after sending
        except Exception as e:
            print(f"Failed to send error report to owner: {e}")

    await _send_rollback_notice_if_present(bot)

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
        bot.failed_extensions.append((filename, str(e)))

async def main():
  async with bot:
    await load()

    server_task = None
    # Start Dashboard if enabled
    if settings.get("enable_dashboard", False):
        print(f"Starting Dashboard on port {settings.get('dashboard_port', 5000)}...")
        app.bot = bot  # Inject bot instance into the Quart app
        config = Config()
        config.bind = [f"0.0.0.0:{settings.get('dashboard_port', 5000)}"]
        # Run Hypercorn in the background
        server_task = asyncio.create_task(serve(app, config))
        print(f"Dashboard accessible at http://127.0.0.1:{settings.get('dashboard_port', 5000)}")
    
    try:
        # Ensure token exists before starting
        if settings.get("token"):
            TOKEN = settings["token"]
            await bot.start(TOKEN)
        else:
            print("Error: Bot token not found in settings or environment variables.")
    finally:
        if server_task:
            print("Stopping Dashboard...")
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
            print("Dashboard stopped.")

if __name__ == "__main__":
    asyncio.run(main())

@bot.event
async def on_voice_state_update(member, before, after):
    if member == bot.user:
        if before.channel and not after.channel:
            print(f"[Voice] Bot was disconnected from {before.channel.guild.name} ({before.channel.guild.id}).")
        elif not before.channel and after.channel:
            print(f"[Voice] Bot connected to {after.channel.guild.name} ({after.channel.guild.id}) in {after.channel.name}.")
