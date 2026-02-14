import discord
from discord import app_commands
from discord.ext import commands
from loadnsave import load_bot_status, save_bot_status

class BotStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Sets the bot status when the bot is ready."""
        try:
            status_data = await load_bot_status()
            activity_type_str = status_data.get("type", "playing")
            text = status_data.get("text", "Call of Cthulhu")

            activity = self._get_activity(activity_type_str, text)
            if activity:
                await self.bot.change_presence(activity=activity)
                print(f"Status set to: {activity_type_str} {text}")
        except Exception as e:
            print(f"Error setting initial bot status: {e}")

    def _get_activity(self, type_str, text):
        type_str = type_str.lower()
        if type_str == "playing":
            return discord.Game(name=text)
        elif type_str == "watching":
            return discord.Activity(type=discord.ActivityType.watching, name=text)
        elif type_str == "listening":
            return discord.Activity(type=discord.ActivityType.listening, name=text)
        elif type_str == "competing":
            return discord.Activity(type=discord.ActivityType.competing, name=text)
        return None

    @app_commands.command(name="status", description="Sets the bot's status. Owner only.")
    @app_commands.describe(activity_type="The type of activity", text="The status text")
    @app_commands.choices(activity_type=[
        app_commands.Choice(name="Playing", value="playing"),
        app_commands.Choice(name="Watching", value="watching"),
        app_commands.Choice(name="Listening", value="listening"),
        app_commands.Choice(name="Competing", value="competing")
    ])
    async def status(self, interaction: discord.Interaction, activity_type: app_commands.Choice[str], text: str):
        """
        Sets the bot's status.
        """
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("⛔ You do not have permission to run this command.", ephemeral=True)
            return

        activity = self._get_activity(activity_type.value, text)

        try:
            await self.bot.change_presence(activity=activity)

            # Save to file
            await save_bot_status({"type": activity_type.value, "text": text})

            await interaction.response.send_message(f"Status updated to: {activity_type.value} **{text}**", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Failed to update status: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(BotStatus(bot))
