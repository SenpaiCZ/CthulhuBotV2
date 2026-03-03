import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
import random
import asyncio
import re
import math
from datetime import datetime, timedelta, timezone
from loadnsave import load_giveaway_data, save_giveaway_data, load_karma_stats

KARMA_VERIFICATION_HALF_THRESHOLD = 100
PERCENTAGE_TO_TICKETS_MULTIPLIER = 1000

def calculate_tickets(karma):
    """
    Calculates tickets based on karma.
    Formula: round(1000 * (karma / (100 + karma)))
    """
    try:
        k_val = int(karma)
    except (ValueError, TypeError):
        k_val = 0

    if k_val <= 0:
        return 0

    verification_percentage = k_val / (KARMA_VERIFICATION_HALF_THRESHOLD + k_val)
    tickets = math.ceil(PERCENTAGE_TO_TICKETS_MULTIPLIER * verification_percentage)
    return tickets

class GiveawayCreationModal(Modal, title="Create Giveaway"):
    giveaway_title = TextInput(label="Title", placeholder="e.g. Monthly Steam Key", max_length=100)
    description = TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Details about the prize...", required=False, max_length=1000)
    duration = TextInput(label="Duration", placeholder="e.g. 10m, 1h, 2d", max_length=20)
    prize_secret = TextInput(label="Prize Secret (Hidden)", style=discord.TextStyle.paragraph, placeholder="The key/code sent to winner...", required=True, max_length=1000)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        # Parse duration
        duration_str = self.duration.value
        duration_seconds = self.cog.parse_duration(duration_str)

        if not duration_seconds:
            await interaction.response.send_message("❌ Invalid duration format. Use 10m, 1h, 2d etc.", ephemeral=True)
            return

        end_time = datetime.now(timezone.utc).timestamp() + duration_seconds
        title = self.giveaway_title.value
        desc = self.description.value
        secret = self.prize_secret.value

        # Create Embed
        embed = discord.Embed(title=f"🎉 GIVEAWAY: {title}", description=desc, color=discord.Color.gold())
        embed.add_field(name="Ends", value=f"<t:{int(end_time)}:R>", inline=False)
        embed.add_field(name="How to win?", value="React with 🎉 to enter!\nKarma increases your chance to win!", inline=False)
        embed.set_footer(text=f"Hosted by {interaction.user.display_name}")

        try:
            # Post to Channel
            # We need to send the message to the channel where the command was invoked.
            # interaction.channel should work if the command was invoked in a guild channel.

            if not interaction.channel:
                 await interaction.response.send_message("❌ Cannot post giveaway in DM.", ephemeral=True)
                 return

            view = GiveawayView()

            # We respond to the interaction first, then send the public message?
            # Or just send the public message as a new message?
            # User expects a public post.

            await interaction.response.send_message(f"✅ Giveaway creating...", ephemeral=True)

            message = await interaction.channel.send(embed=embed, view=view)

            # Save Data
            data = await load_giveaway_data()
            guild_id = str(interaction.guild_id)
            if guild_id not in data:
                data[guild_id] = {}

            data[guild_id][str(message.id)] = {
                "creator_id": interaction.user.id,
                "channel_id": interaction.channel.id,
                "title": title,
                "description": desc,
                "prize_secret": secret,
                "status": "active",
                "participants": [],
                "end_time": end_time
            }

            await save_giveaway_data(data)

            # Confirm to user (edit original response)
            await interaction.edit_original_response(content=f"✅ Giveaway created! [Jump to message]({message.jump_url})")

        except Exception as e:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"Error creating giveaway: {e}", ephemeral=True)
            else:
                await interaction.followup.send(f"Error creating giveaway: {e}", ephemeral=True)

class GiveawayView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Join Giveaway", style=discord.ButtonStyle.green, emoji="🎉", custom_id="giveaway:join")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        message_id = str(interaction.message.id)
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)

        data = await load_giveaway_data()

        if guild_id not in data or message_id not in data[guild_id]:
            await interaction.response.send_message("This giveaway no longer exists.", ephemeral=True)
            return

        giveaway = data[guild_id][message_id]

        if giveaway["status"] != "active":
            await interaction.response.send_message("This giveaway has ended.", ephemeral=True)
            return

        if user_id in giveaway["participants"]:
            await interaction.response.send_message("You have already joined this giveaway!", ephemeral=True)
            return

        # Add user
        giveaway["participants"].append(user_id)
        await save_giveaway_data(data)

        # Calculate potential tickets
        karma_stats = await load_karma_stats()
        user_karma = karma_stats.get(guild_id, {}).get(user_id, 0)
        tickets = calculate_tickets(user_karma)

        if tickets == 0:
            await interaction.response.send_message(f"You have joined the giveaway! (Tickets: {tickets}). You need karma to have a chance to win!", ephemeral=True)
        else:
            await interaction.response.send_message(f"You have joined the giveaway! (Tickets: {tickets})", ephemeral=True)

class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Register persistent view
    async def cog_load(self):
        self.bot.add_view(GiveawayView())
        self.check_giveaways.start()

    async def cog_unload(self):
        self.check_giveaways.cancel()

    @tasks.loop(seconds=60)
    async def check_giveaways(self):
        try:
            data = await load_giveaway_data()
            now = datetime.now(timezone.utc).timestamp()

            # Create a list of targets to avoid modification during iteration issues, though we call a separate function
            targets = []
            for guild_id, giveaways in data.items():
                for message_id, gw in giveaways.items():
                    end_time = gw.get("end_time")
                    if gw["status"] == "active" and isinstance(end_time, (int, float)):
                        if now >= end_time:
                            targets.append((guild_id, message_id))

            for guild_id, message_id in targets:
                try:
                    await self.api_end_giveaway(guild_id, message_id, requester=None)
                except Exception as inner_e:
                    print(f"Error ending giveaway {message_id} in guild {guild_id}: {inner_e}")

        except Exception as e:
            print(f"Error in check_giveaways loop: {e}")

    @check_giveaways.before_loop
    async def before_check_giveaways(self):
        await self.bot.wait_until_ready()

    def parse_duration(self, duration_str):
        if not duration_str or duration_str.lower() in ["forever", "none", "no"]:
            return None

        total_seconds = 0
        matches = re.findall(r'(\d+)\s*([dhms])', duration_str.lower())

        for amount, unit in matches:
            amount = int(amount)
            if unit == 'd':
                total_seconds += amount * 86400
            elif unit == 'h':
                total_seconds += amount * 3600
            elif unit == 'm':
                total_seconds += amount * 60
            elif unit == 's':
                total_seconds += amount

        return total_seconds if total_seconds > 0 else None

    # Define the command group
    giveaway_group = app_commands.Group(name="giveaway", description="🎉 Manage Giveaways.")

    @giveaway_group.command(name="create", description="➕ Create a new giveaway.")
    async def create_giveaway(self, interaction: discord.Interaction):
        """
        Create a new giveaway via a popup form.
        """
        modal = GiveawayCreationModal(self)
        await interaction.response.send_modal(modal)

    @giveaway_group.command(name="end", description="🛑 End a giveaway and pick a winner.")
    @app_commands.describe(message_link_or_id="The message link or ID of the giveaway")
    async def end_giveaway(self, interaction: discord.Interaction, message_link_or_id: str):
        """
        End a giveaway and pick a winner.
        """
        # Extract ID
        message_id = message_link_or_id
        if "discord.com/channels/" in message_id:
            message_id = message_id.split("/")[-1]

        # Call API method
        try:
            success, msg = await self.api_end_giveaway(str(interaction.guild.id), message_id, requester=interaction.user)
            await interaction.response.send_message(msg)
        except Exception as e:
             await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @end_giveaway.autocomplete('message_link_or_id')
    async def end_autocomplete(self, interaction: discord.Interaction, current: str):
        data = await load_giveaway_data()
        guild_id = str(interaction.guild_id)

        if guild_id not in data:
            return []

        choices = []
        for msg_id, gw in data[guild_id].items():
            if gw["status"] == "active":
                title = gw.get("title", "Unknown")
                name = f"{title} (ID: {msg_id})"
                if current.lower() in name.lower():
                    choices.append(app_commands.Choice(name=name[:100], value=msg_id))

        return choices[:25]

    @giveaway_group.command(name="reroll", description="🔄 Reroll a winner for an ended giveaway.")
    @app_commands.describe(message_link_or_id="The message link or ID of the giveaway")
    async def reroll_giveaway(self, interaction: discord.Interaction, message_link_or_id: str):
        """
        Reroll a winner for an ended giveaway.
        """
        # Extract ID
        message_id = message_link_or_id
        if "discord.com/channels/" in message_id:
            message_id = message_id.split("/")[-1]

        # Call API method
        try:
             success, msg = await self.api_reroll_giveaway(str(interaction.guild.id), message_id, requester=interaction.user)
             if not success:
                 await interaction.response.send_message(msg, ephemeral=True)
             else:
                 await interaction.response.send_message(msg)
        except Exception as e:
             await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @reroll_giveaway.autocomplete('message_link_or_id')
    async def reroll_autocomplete(self, interaction: discord.Interaction, current: str):
        data = await load_giveaway_data()
        guild_id = str(interaction.guild_id)

        if guild_id not in data:
            return []

        choices = []
        for msg_id, gw in data[guild_id].items():
            if gw["status"] == "ended":
                title = gw.get("title", "Unknown")
                name = f"{title} (ID: {msg_id})"
                if current.lower() in name.lower():
                    choices.append(app_commands.Choice(name=name[:100], value=msg_id))

        return choices[:25]

    @giveaway_group.command(name="list", description="📃 List all active giveaways.")
    @app_commands.checks.has_permissions(administrator=True)
    async def list_giveaways(self, interaction: discord.Interaction):
        """
        List all active giveaways.
        """
        data = await load_giveaway_data()
        guild_id = str(interaction.guild.id)

        if guild_id not in data or not data[guild_id]:
            await interaction.response.send_message("No giveaways found.", ephemeral=True)
            return

        embed = discord.Embed(title="Active Giveaways", color=discord.Color.blue())

        found = False
        for msg_id, gw in data[guild_id].items():
            if gw["status"] == "active":
                found = True
                link = f"https://discord.com/channels/{guild_id}/{gw['channel_id']}/{msg_id}"
                embed.add_field(name=gw["title"], value=f"[Link]({link}) - {len(gw['participants'])} entries", inline=False)

        if not found:
            await interaction.response.send_message("No active giveaways.", ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed)

    async def pick_winner(self, guild_id, participants):
        """
        Picks a winner based on weighted karma.
        """
        if not participants:
            return None

        karma_stats = await load_karma_stats()
        guild_karma = karma_stats.get(str(guild_id), {})

        population = []
        weights = []

        for user_id in participants:
            k = guild_karma.get(str(user_id), 0)
            tickets = calculate_tickets(k)

            population.append(user_id)
            weights.append(tickets)

        if not population:
            return None

        if sum(weights) == 0:
            return None

        return random.choices(population, weights=weights, k=1)[0]

    # --- API Methods (Used by Dashboard and Commands) ---

    async def api_end_giveaway(self, guild_id: str, message_id: str, requester=None):
        """
        Ends the giveaway and returns (Success, Message).
        requester can be a Member/User object for permission checking.
        """
        data = await load_giveaway_data()
        guild_id = str(guild_id)
        message_id = str(message_id)

        if guild_id not in data or message_id not in data[guild_id]:
            return False, "Giveaway not found."

        gw = data[guild_id][message_id]

        # Check permissions
        if requester:
            is_admin = requester.guild_permissions.administrator
            is_creator = str(requester.id) == str(gw["creator_id"])
            if not is_admin and not is_creator:
                return False, "You do not have permission to end this giveaway."

        if gw["status"] != "active":
             return False, "This giveaway is already ended."

        # Pick Winner
        participants = gw["participants"]
        if not participants:
            gw["status"] = "ended"
            await save_giveaway_data(data)
            return True, "Giveaway ended. No participants."

        winner_id = await self.pick_winner(guild_id, participants)

        if not winner_id:
             return False, "Error picking winner."

        gw["status"] = "ended"
        gw["winner_id"] = winner_id
        await save_giveaway_data(data)

        # Notify
        guild = self.bot.get_guild(int(guild_id))
        if guild:
            winner = guild.get_member(int(winner_id))

            channel = guild.get_channel(int(gw["channel_id"]))
            if channel:
                try:
                    msg = await channel.fetch_message(int(message_id))
                    embed = msg.embeds[0]
                    embed.color = discord.Color.greyple()
                    embed.title = f"🚫 ENDED: {gw['title']}"
                    embed.add_field(name="Winner", value=f"🎉 <@{winner_id}> 🎉", inline=False)
                    await msg.edit(embed=embed, view=None)
                    await channel.send(f"🎉 The winner of **{gw['title']}** is <@{winner_id}>! Check your DMs!")
                except Exception as e:
                    print(f"Error updating giveaway message: {e}")

            # DM Winner
            if winner:
                try:
                    await winner.send(f"🎉 **Congratulations!** You won the giveaway for **{gw['title']}**!\n\nHere is your prize:\n||{gw['prize_secret']}||")
                except discord.Forbidden:
                    pass

        return True, f"Giveaway ended. Winner: {winner_id}"

    async def api_reroll_giveaway(self, guild_id: str, message_id: str, requester=None):
        """
        Rerolls the giveaway and returns (Success, Message).
        """
        data = await load_giveaway_data()
        guild_id = str(guild_id)
        message_id = str(message_id)

        if guild_id not in data or message_id not in data[guild_id]:
            return False, "Giveaway not found."

        gw = data[guild_id][message_id]

        if requester:
            is_admin = requester.guild_permissions.administrator
            is_creator = str(requester.id) == str(gw["creator_id"])
            if not is_admin and not is_creator:
                return False, "You do not have permission to reroll this giveaway."

        participants = gw["participants"]
        if not participants:
            return False, "No participants."

        # Pick new winner
        winner_id = await self.pick_winner(guild_id, participants)

        if not winner_id:
             return False, "Error picking winner."

        # Notify
        guild = self.bot.get_guild(int(guild_id))
        if guild:
            channel = guild.get_channel(int(gw["channel_id"]))
            if channel:
                await channel.send(f"🔄 **Reroll!** The new winner of **{gw['title']}** is <@{winner_id}>!")

            # DM Winner
            winner = guild.get_member(int(winner_id))
            if winner:
                try:
                    await winner.send(f"🎉 **Reroll!** You won the giveaway for **{gw['title']}**!\n\nHere is your prize:\n||{gw['prize_secret']}||")
                except:
                    pass

        return True, f"Rerolled. New Winner: {winner_id}"

async def setup(bot):
    await bot.add_cog(Giveaway(bot))
