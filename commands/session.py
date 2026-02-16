import discord
from discord import app_commands
from discord.ext import commands
import random
import math
from loadnsave import load_session_data, save_session_data, save_player_stats, load_player_stats
from emojis import get_stat_emoji

class SessionCleanupView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = str(user_id)
        self.value = None
        self.message = None

    @discord.ui.button(label="Yes, Wipe Data", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This confirmation is not for you.", ephemeral=True)
            return

        session_data = await load_session_data()
        if self.user_id in session_data:
            del session_data[self.user_id]
            await save_session_data(session_data)
            await interaction.response.edit_message(content="✅ Session data **wiped** successfully.", view=None)
        else:
            await interaction.response.edit_message(content="⚠️ No session data found to wipe.", view=None)

        self.value = True
        self.stop()

    @discord.ui.button(label="No, Keep Data", style=discord.ButtonStyle.secondary, emoji="🛡️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This confirmation is not for you.", ephemeral=True)
            return

        await interaction.response.edit_message(content="✅ Session data **preserved**.", view=None)
        self.value = False
        self.stop()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass
        self.stop()

class SessionUpgradeView(discord.ui.View):
    def __init__(self, user_id, server_id, pending_upgrades, player_stats):
        super().__init__(timeout=180)
        self.user_id = str(user_id)
        self.server_id = str(server_id)
        self.pending_upgrades = pending_upgrades # List of (skill, current, new, gain)
        self.player_stats = player_stats
        self.applied = False
        self.message = None

    @discord.ui.button(label="Confirm Upgrades", style=discord.ButtonStyle.success, emoji="📈")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("Not your session!", ephemeral=True)

        if self.applied:
            return await interaction.response.send_message("Already applied!", ephemeral=True)

        # Apply changes
        for skill, current, new, gain in self.pending_upgrades:
            self.player_stats[self.server_id][self.user_id][skill] = new

        await save_player_stats(self.player_stats)
        self.applied = True

        # Update Embed to show "Applied" state
        embed = interaction.message.embeds[0]
        embed.title = "✅ Session Upgrades Applied"
        embed.color = discord.Color.green()

        # Disable all buttons
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

        # Ask to wipe
        view = SessionCleanupView(self.user_id)
        # Use followup for ephemeral confirmation
        msg = await interaction.followup.send("Do you want to wipe your session data now?", view=view, ephemeral=True)
        # We can't easily edit ephemeral messages on timeout unless we keep the interaction token alive,
        # but cleanup view is short-lived anyway.
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("Not your session!", ephemeral=True)

        embed = interaction.message.embeds[0]
        embed.title = "❌ Session Upgrades Cancelled"
        embed.color = discord.Color.red()

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass
        self.stop()

class PaginatedSessionView(discord.ui.View):
    def __init__(self, items, title, user_id):
        super().__init__(timeout=180)
        self.items = items
        self.title = title
        self.user_id = str(user_id)
        self.per_page = 10
        self.current_page = 0
        self.total_pages = max(1, math.ceil(len(items) / self.per_page))
        self.message = None

    def get_embed(self):
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_items = self.items[start:end]

        embed = discord.Embed(title=self.title, color=discord.Color.blue())
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages} | Total Skills: {len(self.items)}")

        description = ""
        for skill in page_items:
            emoji = get_stat_emoji(skill)
            description += f"{emoji} **{skill}**\n"

        if not description:
            description = "No skills recorded."

        embed.description = description
        embed.add_field(name="How to Upgrade", value="1. Use `/roll skill: Name`\n2. If you fail (❌), the skill is marked.\n3. Use `/session action:Auto` to roll for improvements.", inline=False)

        return embed

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, disabled=True)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
             return await interaction.response.send_message("Not your list!", ephemeral=True)

        self.current_page = max(0, self.current_page - 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
             return await interaction.response.send_message("Not your list!", ephemeral=True)

        self.current_page = min(self.total_pages - 1, self.current_page + 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    def update_buttons(self):
        self.prev_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page == self.total_pages - 1)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass
        self.stop()

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

        # --- START SESSION ---
        if action.value == "start":
            session_data = await load_session_data()
            if user_id not in session_data:
                session_data[user_id] = []
                await save_session_data(session_data)

            embed = discord.Embed(
                title="🎬 Session Started",
                description=f"**{interaction.user.display_name}**, your session is now active.\n\nStats you fail rolls on will be recorded for potential improvement.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

        # --- AUTO UPGRADE ---
        elif action.value == "auto":
            session_data = await load_session_data()
            player_stats = await load_player_stats()

            if user_id not in session_data or user_id not in player_stats.get(server_id, {}):
                return await interaction.response.send_message(f"⚠️ No active session or character found for {interaction.user.display_name}.", ephemeral=True)

            user_session = session_data[user_id]
            excluded_skills = ["HP", "MP", "STR", "DEX", "CON", "INT", "POW", "EDU", "SIZ", "APP", "SAN", "LUCK", "Credit Rating"]
            # Deduplicate skills
            filtered_session = sorted(list(set([entry for entry in user_session if not any(skill in entry for skill in excluded_skills)])))

            if not filtered_session:
                return await interaction.response.send_message("ℹ️ No eligible skills to upgrade in this session.", ephemeral=True)

            # Calculate Potential Upgrades
            pending_upgrades = [] # (skill, current, new, gain)
            logs = []

            for skill in filtered_session:
                current_value = player_stats[server_id][user_id].get(skill, 0)

                check_roll = random.randint(1, 100)

                if check_roll > current_value or check_roll >= 96:
                    gain = random.randint(1, 10)
                    new_value = min(99, current_value + gain)
                    pending_upgrades.append((skill, current_value, new_value, gain))
                    logs.append(f"**{skill}**: Roll {check_roll} (> {current_value}) -> **+{gain}** ({new_value})")
                else:
                    logs.append(f"**{skill}**: Roll {check_roll} (<= {current_value}) -> No Change")

            if not pending_upgrades:
                embed = discord.Embed(title="Session Upgrade Results", description="No skills improved this time.", color=discord.Color.orange())
                log_text = "\n".join(logs)
                if len(log_text) > 4000: log_text = log_text[:4000] + "..."
                embed.description += "\n\n" + log_text

                # Check interaction response state
                if interaction.response.is_done():
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.response.send_message(embed=embed)

                # Still offer wipe
                view = SessionCleanupView(user_id)
                msg = await interaction.followup.send("Do you want to wipe your session data?", view=view, ephemeral=True)
                # No need to store message for ephemeral views usually, as they disappear or can't be edited after timeout easily
                return

            # Show Preview
            embed = discord.Embed(title="📈 Potential Skill Upgrades", color=discord.Color.gold())
            embed.description = "Confirm these changes to apply them to your character."

            success_text = ""
            for skill, cur, new, gain in pending_upgrades:
                emoji = get_stat_emoji(skill)
                success_text += f"{emoji} **{skill}**: {cur} ➔ **{new}** (+{gain})\n"

            if len(success_text) > 1024:
                # Chunk it
                chunks = [success_text[i:i+1024] for i in range(0, len(success_text), 1024)]
                for i, chunk in enumerate(chunks):
                    embed.add_field(name=f"Improvements {i+1}", value=chunk, inline=False)
            else:
                embed.add_field(name="Improvements", value=success_text, inline=False)

            failures = [l for l in logs if "No Change" in l]
            if failures:
                fail_count = len(failures)
                embed.set_footer(text=f"{fail_count} skills did not improve.")

            view = SessionUpgradeView(user_id, server_id, pending_upgrades, player_stats)
            if interaction.response.is_done():
                msg = await interaction.followup.send(embed=embed, view=view)
            else:
                await interaction.response.send_message(embed=embed, view=view)
                msg = await interaction.original_response()
            view.message = msg

        # --- SHOW SESSION ---
        elif action.value == "show":
            target_member = member or interaction.user
            target_id = str(target_member.id)
            session_data = await load_session_data()

            if target_id in session_data:
                user_session = session_data[target_id]
                excluded_skills = ["HP", "MP", "STR", "DEX", "CON", "INT", "POW", "EDU", "SIZ", "APP", "SAN", "LUCK", "Credit Rating"]
                filtered_session = sorted(list(set([entry for entry in user_session if not any(skill in entry for skill in excluded_skills)])))

                if filtered_session:
                    view = PaginatedSessionView(filtered_session, f"📝 Session: {target_member.display_name}", target_id)
                    view.update_buttons()

                    if interaction.response.is_done():
                        msg = await interaction.followup.send(embed=view.get_embed(), view=view)
                    else:
                        await interaction.response.send_message(embed=view.get_embed(), view=view)
                        msg = await interaction.original_response()
                    view.message = msg
                else:
                    await interaction.response.send_message("ℹ️ No skills marked for improvement in current session.", ephemeral=True)
            else:
                await interaction.response.send_message(f"ℹ️ No active session for {target_member.display_name}.", ephemeral=True)

        # --- WIPE SESSION ---
        elif action.value == "wipe":
            session_data = await load_session_data()
            if user_id in session_data:
                view = SessionCleanupView(user_id)
                await interaction.response.send_message("🗑️ Are you sure you want to **wipe** your session data?", view=view, ephemeral=True)
                view.message = await interaction.original_response()
            else:
                await interaction.response.send_message("ℹ️ No active session found to wipe.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Session(bot))
