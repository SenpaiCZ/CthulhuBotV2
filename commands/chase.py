import discord
import random
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select, Modal, TextInput
from loadnsave import load_chase_data, save_chase_data, load_player_stats
from services.chase_service import ChaseService, ChaseParticipant, ENVIRONMENTS

# --- VIEWS ---

class ChaseSetupView(View):
    def __init__(self, cog, user):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        self.environment = "Urban"
        self.mode = "Foot"

    @discord.ui.select(placeholder="Select Environment", options=[
        discord.SelectOption(label="Urban", emoji="🏙️", description="City streets, alleys, crowds"),
        discord.SelectOption(label="Wilderness", emoji="🌲", description="Forests, mountains, mud"),
        discord.SelectOption(label="Driving", emoji="🚗", description="High speed car chase")
    ])
    async def select_env(self, interaction: discord.Interaction, select: Select):
        self.environment = select.values[0]
        self.mode = "Driving" if self.environment == "Driving" else "Foot"
        await interaction.response.defer()

    @discord.ui.button(label="Start Chase", style=discord.ButtonStyle.green)
    async def start_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.user:
             await interaction.response.send_message("Only the Keeper can start the chase.", ephemeral=True)
             return
        await self.cog.initialize_chase(interaction, self.environment, self.mode)

class AddNPCModal(Modal, title="Add NPC Threat"):
    name_input = TextInput(label="Name", placeholder="Cultist Leader")
    stats_input = TextInput(label="Stats (MOV, DEX, STR, CON)", placeholder="8, 60, 50, 50", required=False)

    def __init__(self, cog, guild_id, channel_id):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        self.channel_id = channel_id

    async def on_submit(self, interaction: discord.Interaction):
        session = self.cog.service.get_session(self.guild_id, self.channel_id)
        if not session:
            await interaction.response.send_message("Session not found.", ephemeral=True)
            return

        name = self.name_input.value
        stats_str = self.stats_input.value
        mov, dex, strength, con = 8, 50, 50, 50

        if stats_str:
            try:
                parts = [int(s.strip()) for s in stats_str.split(",")]
                if len(parts) >= 1: mov = parts[0]
                if len(parts) >= 2: dex = parts[1]
                if len(parts) >= 3: strength = parts[2]
                if len(parts) >= 4: con = parts[3]
            except ValueError:
                pass

        npc = ChaseParticipant(f"NPC_{random.randint(1000,9999)}", name, is_npc=True)
        npc.set_stats({"MOV": mov, "DEX": dex, "STR": strength, "CON": con, "Drive Auto": 50})
        npc.reset_round_actions()

        session.participants.append(npc)
        session.sort_turn_order()
        await self.cog.save_and_update(session, interaction)

class ChaseDashboardView(View):
    def __init__(self, cog, session):
        super().__init__(timeout=None)
        self.cog = cog
        self.session = session

    @discord.ui.button(label="Join Chase", style=discord.ButtonStyle.primary, custom_id="chase:join")
    async def join_button(self, interaction: discord.Interaction, button: Button):
        p = self.session.get_participant(interaction.user.id)
        if p:
            await interaction.response.send_message("You are already in the chase!", ephemeral=True)
            return

        all_stats = await load_player_stats()
        user_stats = all_stats.get(str(interaction.guild.id), {}).get(str(interaction.user.id), {})

        new_p = ChaseParticipant(interaction.user.id, interaction.user.display_name)
        new_p.set_stats(user_stats)
        new_p.reset_round_actions()

        self.session.participants.append(new_p)
        self.session.sort_turn_order()
        self.session.add_log(f"➕ **{new_p.name}** joined the chase!")
        await self.cog.save_and_update(self.session, interaction)

    @discord.ui.button(label="Add NPC", style=discord.ButtonStyle.secondary, custom_id="chase:add_npc")
    async def add_npc_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(AddNPCModal(self.cog, self.session.guild_id, self.session.channel_id))

    @discord.ui.button(label="Control NPC", style=discord.ButtonStyle.secondary, custom_id="chase:control_npc")
    async def control_npc_button(self, interaction: discord.Interaction, button: Button):
        npcs = [p for p in self.session.participants if p.is_npc]
        if not npcs:
            await interaction.response.send_message("No NPCs to control.", ephemeral=True)
            return

        options = [discord.SelectOption(label=n.name, value=n.user_id) for n in npcs]
        view = View()
        select = Select(placeholder="Select NPC...", options=options)
        
        async def select_callback(inter):
            npc = self.session.get_participant(select.values[0])
            await inter.response.send_message(f"Acting as **{npc.name}**:", view=ChaseActionsView(self.cog, self.session, npc), ephemeral=True)
        
        select.callback = select_callback
        view.add_item(select)
        await interaction.response.send_message("Select an NPC:", view=view, ephemeral=True)

    @discord.ui.button(label="Actions", style=discord.ButtonStyle.success, custom_id="chase:actions")
    async def actions_button(self, interaction: discord.Interaction, button: Button):
        p = self.session.get_participant(interaction.user.id)
        if not p:
            await interaction.response.send_message("You must join the chase first!", ephemeral=True)
            return
        await interaction.response.send_message("Choose your action:", view=ChaseActionsView(self.cog, self.session, p), ephemeral=True)

    @discord.ui.button(label="Next Round", style=discord.ButtonStyle.danger, custom_id="chase:next_round")
    async def next_round_button(self, interaction: discord.Interaction, button: Button):
        self.session.next_round()
        await self.cog.save_and_update(self.session, interaction)

class ChaseActionsView(View):
    def __init__(self, cog, session, participant):
        super().__init__(timeout=60)
        self.cog = cog
        self.session = session
        self.participant = participant

    @discord.ui.button(label="Move (1 MP)", style=discord.ButtonStyle.primary)
    async def move_button(self, interaction: discord.Interaction, button: Button):
        if self.participant.move_actions_remaining < 1:
            await interaction.response.send_message("❌ No Movement Actions remaining!", ephemeral=True)
            return

        next_loc_idx = self.participant.position + 1
        self.session.ensure_track_length(next_loc_idx)
        next_loc = self.session.track[next_loc_idx]

        success, msg = True, ""
        if next_loc.hazard:
            skill = next_loc.hazard['check']
            stat_val = getattr(self.participant, skill.lower().replace(" ", "_"), 50)
            if skill == "Drive Auto": stat_val = self.participant.drive
            
            roll = random.randint(1, 100)
            if roll <= stat_val:
                msg = f"✅ Passed **{skill}** check ({roll}/{stat_val}) for {next_loc.hazard['name']}!"
            else:
                success = False
                msg = f"❌ Failed **{skill}** check ({roll}/{stat_val})! Stuck at {next_loc.hazard['name']}."

        if success:
            self.participant.position += 1
            self.session.add_log(f"🏃 **{self.participant.name}** moved to Location {self.participant.position}. {msg}")
        else:
            self.session.add_log(f"⚠️ **{self.participant.name}** stumbled! {msg}")
            
        self.participant.move_actions_remaining -= 1
        await interaction.response.send_message(f"{'Moved' if success else 'Stumbled'}! {msg}", ephemeral=True)
        await self.cog.save_and_update(self.session, interaction, update_only=True)

    @discord.ui.button(label="Dash", style=discord.ButtonStyle.secondary)
    async def dash_button(self, interaction: discord.Interaction, button: Button):
        if self.participant.actions_remaining < 1:
            await interaction.response.send_message("❌ No Standard Actions remaining!", ephemeral=True)
            return
        self.participant.actions_remaining -= 1
        self.participant.move_actions_remaining += 1
        self.session.add_log(f"💨 **{self.participant.name}** dashes!")
        await interaction.response.send_message("You dash forward!", ephemeral=True)
        await self.cog.save_and_update(self.session, interaction, update_only=True)

    @discord.ui.button(label="Attack", style=discord.ButtonStyle.danger)
    async def attack_button(self, interaction: discord.Interaction, button: Button):
        if self.participant.actions_remaining < 1:
            await interaction.response.send_message("❌ No Actions remaining!", ephemeral=True)
            return
        self.participant.actions_remaining -= 1
        self.session.add_log(f"⚔️ **{self.participant.name}** attacks!")
        await interaction.response.send_message("Attack registered.", ephemeral=True)
        await self.cog.save_and_update(self.session, interaction, update_only=True)

# --- COG ---

class ChaseCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = ChaseService()

    async def cog_load(self):
        data = await load_chase_data()
        if data:
            self.service.load_sessions(data)
            for guild_id, guild_sessions in self.service.sessions.items():
                for session in guild_sessions.values():
                    if session.message_id:
                        self.bot.add_view(ChaseDashboardView(self, session), message_id=session.message_id)

    async def initialize_chase(self, interaction: discord.Interaction, environment, mode):
        session = self.service.create_session(interaction.guild_id, interaction.channel_id, environment, mode)
        embed = self.service.create_dashboard_embed(session)
        view = ChaseDashboardView(self, session)
        msg = await interaction.channel.send(embed=embed, view=view)
        session.message_id = msg.id
        self.bot.add_view(view, message_id=msg.id)
        await save_chase_data(self.service.get_all_sessions_dict())
        await interaction.response.edit_message(content="✅ Chase started!", embed=None, view=None)

    async def save_and_update(self, session, interaction, update_only=False):
        await save_chase_data(self.service.get_all_sessions_dict())
        embed = self.service.create_dashboard_embed(session)
        view = ChaseDashboardView(self, session)

        if update_only and session.message_id:
            try:
                channel = self.bot.get_channel(int(session.channel_id))
                msg = await channel.fetch_message(session.message_id)
                await msg.edit(embed=embed, view=view)
            except: pass
        elif not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=view)

    @app_commands.command(name="chase", description="🏃 Manage a Chase scene.")
    async def chase_command(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=discord.Embed(title="🏃 Chase Setup Wizard", color=discord.Color.blue()), 
                                              view=ChaseSetupView(self, interaction.user), ephemeral=True)

async def setup(bot):
    await bot.add_cog(ChaseCog(bot))
