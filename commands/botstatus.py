import discord
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

    @commands.command()
    @commands.is_owner()
    async def status(self, ctx, activity_type: str, *, text: str):
        """
        Sets the bot's status.
        Usage: !status <playing|watching|listening|competing> <text>
        Example: !status watching The Stars
        """
        activity = self._get_activity(activity_type, text)

        if not activity:
            await ctx.send("Invalid activity type. Choose from: playing, watching, listening, competing.")
            return

        try:
            await self.bot.change_presence(activity=activity)

            # Save to file
            await save_bot_status({"type": activity_type.lower(), "text": text})

            await ctx.send(f"Status updated to: {activity_type.lower()} **{text}**")
        except Exception as e:
            await ctx.send(f"Failed to update status: {e}")

async def setup(bot):
    await bot.add_cog(BotStatus(bot))
