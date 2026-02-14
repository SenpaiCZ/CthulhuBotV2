import discord
from discord import app_commands
from discord.ext import commands
import random
from loadnsave import load_session_data, save_session_data, save_player_stats, load_player_stats
from emojis import get_stat_emoji

class SessionCleanupView(discord.ui.View):
    def __init__(self, bot, user_id):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = str(user_id)
        self.value = None

    @discord.ui.button(label="Yes, Wipe Data", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This confirmation is not for you.", ephemeral=True)
            return

        session_data = await load_session_data()
        if self.user_id in session_data:
            del session_data[self.user_id]
            await save_session_data(session_data)
            await interaction.response.send_message("Session data wiped successfully.", ephemeral=True)
        else:
            await interaction.response.send_message("No session data found to wipe.", ephemeral=True)

        self.value = True
        self.stop()
        # Disable buttons after use
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(label="No, Keep Data", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This confirmation is not for you.", ephemeral=True)
            return

        await interaction.response.send_message("Session data preserved.", ephemeral=True)
        self.value = False
        self.stop()
        # Disable buttons after use
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

class Session(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="session", description="Manage your character development session.")
    @app_commands.describe(action="The session action to perform", member="The member to show session for (only for 'show' action)")
    @app_commands.choices(action=[
        app_commands.Choice(name="Start Session", value="start"),
        app_commands.Choice(name="Auto Upgrade Stats", value="auto"),
        app_commands.Choice(name="Show Session", value="show"),
        app_commands.Choice(name="Wipe Session", value="wipe")
    ])
    async def session(self, interaction: discord.Interaction, action: app_commands.Choice[str], member: discord.Member = None):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        if action.value == "start":
            session_data = await load_session_data()
            if user_id not in session_data:
                session_data[user_id] = []

            await save_session_data(session_data)
            await interaction.response.send_message(f"Session started for {interaction.user.display_name}!")

        elif action.value == "auto":
            session_data = await load_session_data()
            player_stats = await load_player_stats()

            # Check if user has session data and if user exists in player_stats for this server
            if user_id not in session_data or user_id not in player_stats.get(server_id, {}):
                await interaction.response.send_message(f"No active session or character found for {interaction.user.display_name}.", ephemeral=True)
                return

            user_session = session_data[user_id]
            excluded_skills = ["HP", "MP", "STR", "DEX", "CON", "INT", "POW", "EDU", "SIZ", "APP", "SAN", "LUCK", "Credit Rating"]
            filtered_session = [entry for entry in user_session if not any(skill in entry for skill in excluded_skills)]

            if not filtered_session:
                await interaction.response.send_message("No skills to upgrade in this session.", ephemeral=True)
                return

            embed = discord.Embed(
                title=f"Session upgrade results for {interaction.user.display_name}",
                color=discord.Color.blue()
            )

            for skill in filtered_session:
                current_value = player_stats[server_id][user_id].get(skill, 0)
                roll = random.randint(1, 100)
                upgrade_value = 0

                if roll > current_value:
                    upgrade_value = random.randint(1, 10)
                    player_stats[server_id][user_id][skill] = current_value + upgrade_value

                emoji = get_stat_emoji(skill)
                embed.add_field(name=f"{skill} {emoji}", value=f"Current: {current_value}, Roll: {roll}, Upgrade: +{upgrade_value}", inline=False)

            await save_player_stats(player_stats)

            # Send results and then ask for wipe
            await interaction.response.send_message(embed=embed)

            view = SessionCleanupView(self.bot, user_id)
            await interaction.followup.send("Do you want to wipe your session data?", view=view)

        elif action.value == "show":
            target_member = member or interaction.user
            target_id = str(target_member.id)
            session_data = await load_session_data()

            if target_id in session_data:
                user_session = session_data[target_id]
                excluded_skills = ["STR", "DEX", "CON", "INT", "POW", "EDU", "SIZ", "APP", "SAN", "LUCK", "Credit Rating"]
                filtered_session = [entry for entry in user_session if not any(skill in entry for skill in excluded_skills)]

                if filtered_session:
                    embed = discord.Embed(
                        title=f"Upgradable skills for {target_member.display_name}",
                        color=discord.Color.green()
                    )

                    for skill in filtered_session:
                        emoji = get_stat_emoji(skill)
                        embed.add_field(name=f"{emoji} {skill}", value="", inline=False)

                    embed.add_field(name="Upgrading skills", value="First roll for a stat with `d skill`. If you fail :x:, you can upgrade skill by :game_die:1D10. You can also use `/session action:Auto Upgrade Stats`", inline=False)
                    await interaction.response.send_message(embed=embed)
                else:
                    await interaction.response.send_message("No session data to display.", ephemeral=True)
            else:
                await interaction.response.send_message(f"No active session for {target_member.display_name}.", ephemeral=True)

        elif action.value == "wipe":
            session_data = await load_session_data()
            if user_id in session_data:
                view = SessionCleanupView(self.bot, user_id)
                await interaction.response.send_message("Are you sure you want to wipe your session data?", view=view)
            else:
                await interaction.response.send_message("No active session for this user.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Session(bot))
