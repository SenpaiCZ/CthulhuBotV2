import discord
import random
import asyncio
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select, Modal, TextInput
from loadnsave import load_chase_data, save_chase_data, load_player_stats

# --- CONSTANTS & DATA ---

ENVIRONMENTS = {
    "Urban": {
        "icon": "🏙️",
        "hazards": [
            {"name": "Crowded Market", "check": "DEX", "difficulty": "Regular", "desc": "A dense crowd blocks your path."},
            {"name": "Locked Gate", "check": "STR", "difficulty": "Hard", "desc": "A tall iron gate creates a dead end."},
            {"name": "Slippery Cobbles", "check": "DEX", "difficulty": "Regular", "desc": "Rain-slicked stones make footing treacherous."},
            {"name": "Police Barricade", "check": "Luck", "difficulty": "Regular", "desc": "Officers are blocking the street."},
            {"name": "Fruit Cart", "check": "DEX", "difficulty": "Regular", "desc": "The classic obstacle! My cabbages!"},
            {"name": "Narrow Alley", "check": "SIZ", "difficulty": "Regular", "desc": "It's a tight squeeze."},
            {"name": "Construction Site", "check": "DEX", "difficulty": "Regular", "desc": "Open pits and scaffolding."},
        ]
    },
    "Wilderness": {
        "icon": "🌲",
        "hazards": [
            {"name": "Fallen Tree", "check": "STR", "difficulty": "Regular", "desc": "A massive oak blocks the trail."},
            {"name": "Mudslide", "check": "DEX", "difficulty": "Hard", "desc": "The ground gives way beneath you."},
            {"name": "Dense Thicket", "check": "STR", "difficulty": "Regular", "desc": "Thorny vines tear at your clothes."},
            {"name": "Stream", "check": "DEX", "difficulty": "Regular", "desc": "A rushing stream cuts across the path."},
            {"name": "Wild Animal", "check": "DEX", "difficulty": "Regular", "desc": "A bear? A wolf? Run!"},
            {"name": "Steep Incline", "check": "CON", "difficulty": "Regular", "desc": "A grueling uphill sprint."},
        ]
    },
    "Driving": {
        "icon": "🚗",
        "hazards": [
            {"name": "Red Light", "check": "Drive Auto", "difficulty": "Regular", "desc": "Traffic from the cross street is coming!"},
            {"name": "Pedestrian", "check": "Drive Auto", "difficulty": "Hard", "desc": "Someone steps out into the road!"},
            {"name": "Sharp Turn", "check": "Drive Auto", "difficulty": "Regular", "desc": "A hairpin bend approaches."},
            {"name": "Road Works", "check": "Drive Auto", "difficulty": "Regular", "desc": "Lane closure ahead."},
            {"name": "Oil Slick", "check": "Drive Auto", "difficulty": "Hard", "desc": "Slippery road surface."},
            {"name": "Oncoming Traffic", "check": "Drive Auto", "difficulty": "Hard", "desc": "You swerve into the wrong lane!"},
        ]
    }
}

# --- CLASSES ---

class ChaseLocation:
    def __init__(self, index, environment_type):
        self.index = index
        self.environment = environment_type
        self.hazard = None
        self.description = "Clear path"
        self.generate_hazard()

    def generate_hazard(self):
        # 30% chance of hazard, but index 0 is always clear
        if self.index > 0 and random.random() < 0.3:
            env_data = ENVIRONMENTS.get(self.environment, ENVIRONMENTS["Urban"])
            hazard_data = random.choice(env_data["hazards"])
            self.hazard = hazard_data
            self.description = f"⚠️ **{hazard_data['name']}** ({hazard_data['check']} Check)"
        else:
            self.hazard = None
            self.description = "Clear path"

    def to_dict(self):
        return {
            "index": self.index,
            "environment": self.environment,
            "hazard": self.hazard,
            "description": self.description
        }

    @classmethod
    def from_dict(cls, data):
        loc = cls(data["index"], data["environment"])
        loc.hazard = data["hazard"]
        loc.description = data["description"]
        return loc

class ChaseParticipant:
    def __init__(self, user_id, name, is_npc=False):
        self.user_id = str(user_id)
        self.name = name
        self.is_npc = is_npc
        self.position = 0
        self.mov = 8
        self.dex = 50
        self.str = 50
        self.con = 50
        self.drive = 20
        self.actions_remaining = 0
        self.move_actions_remaining = 0
        self.state = "active" # active, caught, escaped

    def set_stats(self, stats):
        self.mov = stats.get("MOV", 8)
        self.dex = stats.get("DEX", 50)
        self.str = stats.get("STR", 50)
        self.con = stats.get("CON", 50)
        self.drive = stats.get("Drive Auto", 20)

    def reset_round_actions(self):
        # Base: 1 Standard Action + 1 Move Action
        self.actions_remaining = 1
        self.move_actions_remaining = 1

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "name": self.name,
            "is_npc": self.is_npc,
            "position": self.position,
            "mov": self.mov,
            "dex": self.dex,
            "str": self.str,
            "con": self.con,
            "drive": self.drive,
            "actions_remaining": self.actions_remaining,
            "move_actions_remaining": self.move_actions_remaining,
            "state": self.state
        }

    @classmethod
    def from_dict(cls, data):
        p = cls(data["user_id"], data["name"], data["is_npc"])
        p.position = data["position"]
        p.mov = data["mov"]
        p.dex = data["dex"]
        p.str = data["str"]
        p.con = data["con"]
        p.drive = data["drive"]
        p.actions_remaining = data["actions_remaining"]
        p.move_actions_remaining = data["move_actions_remaining"]
        p.state = data["state"]
        return p

class ChaseSession:
    def __init__(self, guild_id, channel_id, environment="Urban", mode="Foot"):
        self.guild_id = str(guild_id)
        self.channel_id = str(channel_id)
        self.environment = environment
        self.mode = mode
        self.track = []
        self.participants = []
        self.turn_order = []
        self.current_turn_index = 0
        self.round_number = 1
        self.log = []
        self.message_id = None # Store dashboard message ID

        # Generate initial track (5 locations)
        for i in range(5):
            self.track.append(ChaseLocation(i, self.environment))
        self.track[0].hazard = None
        self.track[0].description = "Start Line"

    def add_log(self, message):
        self.log.append(message)
        if len(self.log) > 5:
            self.log.pop(0)

    def get_participant(self, user_id):
        for p in self.participants:
            if p.user_id == str(user_id):
                return p
        return None

    def sort_turn_order(self):
        self.participants.sort(key=lambda p: p.dex, reverse=True)
        self.turn_order = [p.user_id for p in self.participants]

    def next_round(self):
        self.round_number += 1
        self.current_turn_index = 0
        for p in self.participants:
            p.reset_round_actions()
        self.add_log(f"🔄 **Round {self.round_number} Start!**")

    def ensure_track_length(self, target_index):
        while len(self.track) <= target_index + 2:
            next_idx = len(self.track)
            self.track.append(ChaseLocation(next_idx, self.environment))

    def to_dict(self):
        return {
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "environment": self.environment,
            "mode": self.mode,
            "track": [t.to_dict() for t in self.track],
            "participants": [p.to_dict() for p in self.participants],
            "turn_order": self.turn_order,
            "current_turn_index": self.current_turn_index,
            "round_number": self.round_number,
            "log": self.log,
            "message_id": self.message_id
        }

    @classmethod
    def from_dict(cls, data):
        s = cls(data["guild_id"], data["channel_id"], data["environment"], data.get("mode", "Foot"))
        s.track = [ChaseLocation.from_dict(t) for t in data["track"]]
        s.participants = [ChaseParticipant.from_dict(p) for p in data["participants"]]
        s.turn_order = data["turn_order"]
        s.current_turn_index = data["current_turn_index"]
        s.round_number = data["round_number"]
        s.log = data.get("log", [])
        s.message_id = data.get("message_id")
        return s

# --- VIEWS ---

class ChaseSetupView(View):
    def __init__(self, cog, ctx):
        super().__init__(timeout=120)
        self.cog = cog
        self.ctx = ctx
        self.environment = "Urban"
        self.mode = "Foot"

    @discord.ui.select(placeholder="Select Environment", options=[
        discord.SelectOption(label="Urban", emoji="🏙️", description="City streets, alleys, crowds"),
        discord.SelectOption(label="Wilderness", emoji="🌲", description="Forests, mountains, mud"),
        discord.SelectOption(label="Driving", emoji="🚗", description="High speed car chase")
    ])
    async def select_env(self, interaction: discord.Interaction, select: Select):
        self.environment = select.values[0]
        if self.environment == "Driving":
            self.mode = "Driving"
        else:
            self.mode = "Foot"
        await interaction.response.defer()

    @discord.ui.button(label="Start Chase", style=discord.ButtonStyle.green)
    async def start_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.ctx.author:
             await interaction.response.send_message("Only the Keeper can start the chase.", ephemeral=True)
             return

        await self.cog.initialize_chase(self.ctx, self.environment, self.mode, interaction)

class AddNPCModal(Modal, title="Add NPC Threat"):
    name = discord.ui.Label(text="Name", component=TextInput(placeholder="Cultist Leader"))
    stats = discord.ui.Label(text="Stats (MOV, DEX, STR, CON)", component=TextInput(placeholder="8, 60, 50, 50", required=False))

    def __init__(self, cog, session_key):
        super().__init__()
        self.cog = cog
        self.session_key = session_key

    async def on_submit(self, interaction: discord.Interaction):
        guild_id, channel_id = self.session_key
        session = self.cog.sessions.get(guild_id, {}).get(channel_id)
        if not session:
            await interaction.response.send_message("Session not found.", ephemeral=True)
            return

        name = self.name.component.value
        stats_str = self.stats.component.value
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

class NPCSelectView(View):
    def __init__(self, cog, session):
        super().__init__(timeout=60)
        self.cog = cog
        self.session = session

        npcs = [p for p in session.participants if p.is_npc]
        options = []
        for npc in npcs:
            desc = f"Pos: {npc.position} | MOV: {npc.mov}"
            options.append(discord.SelectOption(label=npc.name, value=npc.user_id, description=desc))

        self.add_item(NPCSelect(options, cog, session))

class NPCSelect(Select):
    def __init__(self, options, cog, session):
        super().__init__(placeholder="Select NPC to control...", min_values=1, max_values=1, options=options)
        self.cog = cog
        self.session = session

    async def callback(self, interaction: discord.Interaction):
        npc_id = self.values[0]
        participant = self.session.get_participant(npc_id)
        if not participant:
             await interaction.response.send_message("NPC not found.", ephemeral=True)
             return

        view = ChaseActionsView(self.cog, self.session, participant)
        await interaction.response.send_message(f"Acting as **{participant.name}**:", view=view, ephemeral=True)


class ChaseDashboardView(View):
    def __init__(self, cog, session):
        super().__init__(timeout=None) # Persistent
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
        session_key = (self.session.guild_id, self.session.channel_id)
        await interaction.response.send_modal(AddNPCModal(self.cog, session_key))

    @discord.ui.button(label="Control NPC", style=discord.ButtonStyle.secondary, custom_id="chase:control_npc")
    async def control_npc_button(self, interaction: discord.Interaction, button: Button):
        # Only allow Keeper/Admin to control NPCs? Assuming open for now or add check
        # For simplicity, anyone can click but usually only keeper adds NPCs.

        npcs = [p for p in self.session.participants if p.is_npc]
        if not npcs:
            await interaction.response.send_message("No NPCs to control.", ephemeral=True)
            return

        view = NPCSelectView(self.cog, self.session)
        await interaction.response.send_message("Select an NPC:", view=view, ephemeral=True)

    @discord.ui.button(label="Actions", style=discord.ButtonStyle.success, custom_id="chase:actions")
    async def actions_button(self, interaction: discord.Interaction, button: Button):
        p = self.session.get_participant(interaction.user.id)
        if not p:
            await interaction.response.send_message("You must join the chase first!", ephemeral=True)
            return

        view = ChaseActionsView(self.cog, self.session, p)
        await interaction.response.send_message("Choose your action:", view=view, ephemeral=True)

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

    async def update_dashboard(self, interaction):
        await self.cog.save_and_update(self.session, interaction, update_only=True)

    @discord.ui.button(label="Move (1 MP)", style=discord.ButtonStyle.primary)
    async def move_button(self, interaction: discord.Interaction, button: Button):
        if self.participant.move_actions_remaining < 1:
            await interaction.response.send_message("❌ No Movement Actions remaining!", ephemeral=True)
            return

        current_loc = self.session.track[self.participant.position]
        next_loc_idx = self.participant.position + 1
        self.session.ensure_track_length(next_loc_idx)
        next_loc = self.session.track[next_loc_idx]

        success = True
        msg = ""

        if next_loc.hazard:
            skill = next_loc.hazard['check']
            stat_val = 50
            if skill == "DEX": stat_val = self.participant.dex
            elif skill == "STR": stat_val = self.participant.str
            elif skill == "CON": stat_val = self.participant.con
            elif skill == "Drive Auto": stat_val = self.participant.drive

            roll = random.randint(1, 100)
            if roll <= stat_val:
                msg = f"✅ Passed **{skill}** check ({roll}/{stat_val}) for {next_loc.hazard['name']}!"
            else:
                success = False
                msg = f"❌ Failed **{skill}** check ({roll}/{stat_val})! Stuck at {next_loc.hazard['name']}."

        if success:
            self.participant.position += 1
            self.participant.move_actions_remaining -= 1
            self.session.add_log(f"🏃 **{self.participant.name}** moved to Location {self.participant.position}. {msg}")
            await interaction.response.send_message(f"Moved! {msg}", ephemeral=True)
        else:
            self.participant.move_actions_remaining -= 1
            self.session.add_log(f"⚠️ **{self.participant.name}** stumbled! {msg}")
            await interaction.response.send_message(f"Stumbled! {msg}", ephemeral=True)

        await self.update_dashboard(interaction)

    @discord.ui.button(label="Dash (Use Action for +1 Move)", style=discord.ButtonStyle.secondary)
    async def dash_button(self, interaction: discord.Interaction, button: Button):
        if self.participant.actions_remaining < 1:
            await interaction.response.send_message("❌ No Standard Actions remaining!", ephemeral=True)
            return
            
        self.participant.actions_remaining -= 1
        self.participant.move_actions_remaining += 1
        self.session.add_log(f"💨 **{self.participant.name}** dashes! (+1 Move Action)")
        await interaction.response.send_message("You dash forward!", ephemeral=True)
        await self.update_dashboard(interaction)

    @discord.ui.button(label="Attack", style=discord.ButtonStyle.danger)
    async def attack_button(self, interaction: discord.Interaction, button: Button):
        if self.participant.actions_remaining < 1:
            await interaction.response.send_message("❌ No Actions remaining!", ephemeral=True)
            return

        self.participant.actions_remaining -= 1
        self.session.add_log(f"⚔️ **{self.participant.name}** attacks!")
        await interaction.response.send_message("Attack registered (Resolve manually).", ephemeral=True)
        await self.update_dashboard(interaction)

# --- COG ---

class ChaseCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sessions = {} # guild_id -> channel_id -> ChaseSession

    async def cog_load(self):
        # Load data from disk
        data = await load_chase_data()
        if not data: return

        for guild_id, guild_data in data.items():
            if guild_id not in self.sessions: self.sessions[guild_id] = {}
            for channel_id, session_data in guild_data.items():
                try:
                    if "track" not in session_data: continue
                    session = ChaseSession.from_dict(session_data)
                    self.sessions[guild_id][channel_id] = session

                    # Restore persistent view if message_id exists
                    if session.message_id:
                        # Note: We must create a new view instance
                        view = ChaseDashboardView(self, session)
                        self.bot.add_view(view, message_id=session.message_id)

                except Exception as e:
                    print(f"Failed to load chase session for {guild_id}/{channel_id}: {e}")

    async def save_session(self, session):
        all_data = await load_chase_data()
        if not all_data: all_data = {}
        if session.guild_id not in all_data: all_data[session.guild_id] = {}
        all_data[session.guild_id][session.channel_id] = session.to_dict()
        await save_chase_data(all_data)

    async def create_dashboard_embed(self, session):
        env_icon = ENVIRONMENTS.get(session.environment, {}).get("icon", "🏃")
        
        embed = discord.Embed(
            title=f"{env_icon} Chase Dashboard: Round {session.round_number}",
            description=f"**Environment:** {session.environment} | **Mode:** {session.mode}",
            color=discord.Color.dark_red()
        )

        positions = [p.position for p in session.participants]
        if not positions: positions = [0]
        min_pos = min(positions)
        max_pos = max(positions) + 2
        
        session.ensure_track_length(max_pos)

        start_idx = max(0, min_pos - 1)
        end_idx = max_pos

        track_str = ""
        for i in range(start_idx, end_idx + 1):
            if i >= len(session.track): break
            loc = session.track[i]

            parts_here = [p for p in session.participants if p.position == i]

            loc_icon = "🟩"
            if loc.hazard: loc_icon = "⚠️"

            line = f"`{i:02}` {loc_icon} "
            if parts_here:
                avatars = " ".join([("👹" if p.is_npc else "🕵️") for p in parts_here])
                line += f"**{avatars}**"

            if loc.hazard:
                line += f" *{loc.hazard['name']} ({loc.hazard['check']})*"
            elif parts_here:
                line += " *Clear*"
            
            track_str += line + "\n"
            if i < end_idx:
                track_str += "      |\n"

        if not track_str: track_str = "Empty Track"
        embed.add_field(name="🏁 The Track", value=track_str, inline=False)

        status_str = ""
        for p in session.participants:
            actions = "🔴" * p.actions_remaining + "⚪" * (1-p.actions_remaining)
            moves = "🦶" * p.move_actions_remaining
            status_str += f"**{p.name}** (Pos {p.position}): {actions} {moves} [MOV {p.mov}]\n"

        embed.add_field(name="👥 Participants", value=status_str or "No participants", inline=False)

        log_str = "\n".join(session.log[-5:])
        if log_str:
            embed.add_field(name="📜 Log", value=log_str, inline=False)

        embed.set_footer(text="Nexus Chase System v2.0")
        return embed

    async def initialize_chase(self, ctx, environment, mode, interaction=None):
        session = ChaseSession(ctx.guild.id, ctx.channel.id, environment, mode)

        if str(ctx.guild.id) not in self.sessions:
            self.sessions[str(ctx.guild.id)] = {}
        self.sessions[str(ctx.guild.id)][str(ctx.channel.id)] = session

        embed = await self.create_dashboard_embed(session)
        view = ChaseDashboardView(self, session)

        # Send new dashboard message
        if interaction:
             # Edit the setup message to become the dashboard
             await interaction.response.edit_message(content=None, embed=embed, view=view)
             msg = await interaction.original_response()
             session.message_id = msg.id
        else:
             msg = await ctx.send(embed=embed, view=view)
             session.message_id = msg.id

        # Make persistent
        self.bot.add_view(view, message_id=session.message_id)

        await self.save_session(session)

    async def save_and_update(self, session, interaction, update_only=False):
        await self.save_session(session)
        embed = await self.create_dashboard_embed(session)
        view = ChaseDashboardView(self, session)

        if update_only:
            # We are called from a secondary interaction (ephemeral button)
            # We need to fetch the original message using message_id
            if session.message_id:
                try:
                    # Fetch channel using channel_id from session (which is str, convert to int)
                    channel = self.bot.get_channel(int(session.channel_id))
                    if channel:
                        msg = await channel.fetch_message(session.message_id)
                        await msg.edit(embed=embed, view=view)
                except discord.NotFound:
                    # Message deleted?
                    pass
                except Exception as e:
                    print(f"Error updating chase dashboard: {e}")
        else:
            # We are directly interacting with the dashboard (e.g. Join button)
            # The interaction object belongs to the dashboard message
            if interaction.message and not interaction.message.flags.ephemeral:
                await interaction.response.edit_message(embed=embed, view=view)
                session.message_id = interaction.message.id
                # Save again to ensure message_id is correct? It shouldn't change.
            else:
                # Fallback
                await interaction.response.send_message(embed=embed, view=view)

    @commands.hybrid_command(name="chase", description="Manage a Chase scene.")
    async def chase_command(self, ctx):
        """
        Opens the Chase Wizard.
        """
        view = ChaseSetupView(self, ctx)
        embed = discord.Embed(
            title="🏃 Chase Setup Wizard",
            description="Configure the parameters for the chase sequence.",
            color=discord.Color.blue()
        )
        if ctx.interaction:
            await ctx.interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(ChaseCog(bot))
