import discord
import random
from discord import ui
from typing import TYPE_CHECKING, Any
from services.chase_service import ChaseParticipant
from emojis import get_stat_emoji

if TYPE_CHECKING:
    from commands.chase import ChaseCog
    from commands.randomnpc import RandomNPC

class ChaseSetupView(ui.View):
    def __init__(self, cog: 'ChaseCog', user: discord.User):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        self.environment = "Urban"
        self.mode = "Foot"

    @ui.select(placeholder="Select Environment", options=[
        discord.SelectOption(label="Urban", emoji="🏙️", description="City streets, alleys, crowds"),
        discord.SelectOption(label="Wilderness", emoji="🌲", description="Forests, mountains, mud"),
        discord.SelectOption(label="Driving", emoji="🚗", description="High speed car chase")
    ])
    async def select_env(self, interaction: discord.Interaction, select: ui.Select):
        self.environment = select.values[0]
        self.mode = "Driving" if self.environment == "Driving" else "Foot"
        await interaction.response.defer()

    @ui.button(label="Start Chase", style=discord.ButtonStyle.green)
    async def start_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user != self.user:
             await interaction.response.send_message("Only the Keeper can start the chase.", ephemeral=True)
             return
        await self.cog.initialize_chase(interaction, self.environment, self.mode)

class AddNPCModal(ui.Modal, title="Add NPC Threat"):
    name_input = ui.TextInput(label="Name", placeholder="Cultist Leader")
    stats_input = ui.TextInput(label="Stats (MOV, DEX, STR, CON)", placeholder="8, 60, 50, 50", required=False)

    def __init__(self, cog: 'ChaseCog', guild_id, channel_id):
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

class ChaseDashboardView(ui.View):
    def __init__(self, cog: 'ChaseCog', session):
        super().__init__(timeout=None)
        self.cog = cog
        self.session = session

    @ui.button(label="Join Chase", style=discord.ButtonStyle.primary, custom_id="chase:join")
    async def join_button(self, interaction: discord.Interaction, button: ui.Button):
        p = self.session.get_participant(interaction.user.id)
        if p:
            await interaction.response.send_message("You are already in the chase!", ephemeral=True)
            return

        from loadnsave import load_player_stats
        all_stats = await load_player_stats()
        user_stats = all_stats.get(str(interaction.guild.id), {}).get(str(interaction.user.id), {})

        new_p = ChaseParticipant(interaction.user.id, interaction.user.display_name)
        new_p.set_stats(user_stats)
        new_p.reset_round_actions()

        self.session.participants.append(new_p)
        self.session.sort_turn_order()
        self.session.add_log(f"➕ **{new_p.name}** joined the chase!")
        await self.cog.save_and_update(self.session, interaction)

    @ui.button(label="Add NPC", style=discord.ButtonStyle.secondary, custom_id="chase:add_npc")
    async def add_npc_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(AddNPCModal(self.cog, self.session.guild_id, self.session.channel_id))

    @ui.button(label="Control NPC", style=discord.ButtonStyle.secondary, custom_id="chase:control_npc")
    async def control_npc_button(self, interaction: discord.Interaction, button: ui.Button):
        npcs = [p for p in self.session.participants if p.is_npc]
        if not npcs:
            await interaction.response.send_message("No NPCs to control.", ephemeral=True)
            return

        options = [discord.SelectOption(label=n.name, value=n.user_id) for n in npcs]
        view = ui.View()
        select = ui.Select(placeholder="Select NPC...", options=options)
        
        async def select_callback(inter):
            npc = self.session.get_participant(select.values[0])
            await inter.response.send_message(f"Acting as **{npc.name}**:", view=ChaseActionsView(self.cog, self.session, npc), ephemeral=True)
        
        select.callback = select_callback
        view.add_item(select)
        await interaction.response.send_message("Select an NPC:", view=view, ephemeral=True)

    @ui.button(label="Actions", style=discord.ButtonStyle.success, custom_id="chase:actions")
    async def actions_button(self, interaction: discord.Interaction, button: ui.Button):
        p = self.session.get_participant(interaction.user.id)
        if not p:
            await interaction.response.send_message("You must join the chase first!", ephemeral=True)
            return
        await interaction.response.send_message("Choose your action:", view=ChaseActionsView(self.cog, self.session, p), ephemeral=True)

    @ui.button(label="Next Round", style=discord.ButtonStyle.danger, custom_id="chase:next_round")
    async def next_round_button(self, interaction: discord.Interaction, button: ui.Button):
        self.session.next_round()
        await self.cog.save_and_update(self.session, interaction)

class ChaseActionsView(ui.View):
    def __init__(self, cog: 'ChaseCog', session, participant):
        super().__init__(timeout=60)
        self.cog = cog
        self.session = session
        self.participant = participant

    @ui.button(label="Move (1 MP)", style=discord.ButtonStyle.primary)
    async def move_button(self, interaction: discord.Interaction, button: ui.Button):
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

    @ui.button(label="Dash", style=discord.ButtonStyle.secondary)
    async def dash_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.participant.actions_remaining < 1:
            await interaction.response.send_message("❌ No Standard Actions remaining!", ephemeral=True)
            return
        self.participant.actions_remaining -= 1
        self.participant.move_actions_remaining += 1
        self.session.add_log(f"💨 **{self.participant.name}** dashes!")
        await interaction.response.send_message("You dash forward!", ephemeral=True)
        await self.cog.save_and_update(self.session, interaction, update_only=True)

    @ui.button(label="Attack", style=discord.ButtonStyle.danger)
    async def attack_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.participant.actions_remaining < 1:
            await interaction.response.send_message("❌ No Actions remaining!", ephemeral=True)
            return
        self.participant.actions_remaining -= 1
        self.session.add_log(f"⚔️ **{self.participant.name}** attacks!")
        await interaction.response.send_message("Attack registered.", ephemeral=True)
        await self.cog.save_and_update(self.session, interaction, update_only=True)

# RandomNPC Views

class GenderSelectView(ui.View):
    def __init__(self, cog: 'RandomNPC', interaction):
        super().__init__(timeout=60)
        self.cog = cog
        self.original_interaction = interaction

    @ui.button(label="Male", style=discord.ButtonStyle.primary, emoji="👨")
    async def male_button(self, interaction: discord.Interaction, button: ui.Button):
        await self.cog.ask_region(interaction, "male")
        self.stop()

    @ui.button(label="Female", style=discord.ButtonStyle.primary, emoji="👩")
    async def female_button(self, interaction: discord.Interaction, button: ui.Button):
        await self.cog.ask_region(interaction, "female")
        self.stop()

    @ui.button(label="Random", style=discord.ButtonStyle.secondary, emoji="🎲")
    async def random_button(self, interaction: discord.Interaction, button: ui.Button):
        gender = random.choice(["male", "female"])
        await self.cog.ask_region(interaction, gender)
        self.stop()

class RegionSelect(ui.Select):
    def __init__(self, cog: 'RandomNPC', gender):
        self.cog = cog
        self.gender = gender
        options = [
            discord.SelectOption(label="English", value="english", emoji="🇬🇧"),
            discord.SelectOption(label="Scandinavian", value="scandinavian", emoji="🇩🇰"),
            discord.SelectOption(label="German", value="german", emoji="🇩🇪"),
            discord.SelectOption(label="French", value="french", emoji="🇫🇷"),
            discord.SelectOption(label="Arabic", value="arabic", emoji="🇸🇦"),
            discord.SelectOption(label="Spanish", value="spanish", emoji="🇪🇸"),
            discord.SelectOption(label="Russian", value="russian", emoji="🇷🇺"),
            discord.SelectOption(label="Chinese", value="chinese", emoji="🇨🇳"),
            discord.SelectOption(label="Japanese", value="japanese", emoji="🇯🇵"),
            discord.SelectOption(label="Random", value="random", emoji="🎲")
        ]
        super().__init__(placeholder="Select a region...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        region = self.values[0]
        if region == "random":
             regions = ["english", "scandinavian", "german", "french", "arabic", "spanish", "russian", "chinese", "japanese"]
             region = random.choice(regions)
        await self.cog.generate_and_send(interaction, self.gender, region)

class RegionSelectView(ui.View):
    def __init__(self, cog: 'RandomNPC', gender):
        super().__init__(timeout=60)
        self.add_item(RegionSelect(cog, gender))

class NPCActionView(ui.View):
    def __init__(self, cog: 'RandomNPC', interaction, gender, region, embed):
        super().__init__(timeout=300)
        self.cog = cog
        self.original_interaction = interaction
        self.gender = gender
        self.region = region
        self.embed = embed

    @ui.button(label="Reroll", style=discord.ButtonStyle.success, emoji="🔄")
    async def reroll_button(self, interaction: discord.Interaction, button: ui.Button):
        new_embed = await self.cog.create_npc_embed(self.gender, self.region)
        self.embed = new_embed
        await interaction.response.edit_message(embed=new_embed, view=self)

    @ui.button(label="Save (DM)", style=discord.ButtonStyle.secondary, emoji="💾")
    async def save_button(self, interaction: discord.Interaction, button: ui.Button):
        try:
            await interaction.user.send(embed=self.embed)
            await interaction.response.send_message("✅ Sent to your DMs!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I cannot DM you. Please check your privacy settings.", ephemeral=True)

    @ui.button(label="Dismiss", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def dismiss_button(self, interaction: discord.Interaction, button: ui.Button):
        try:
            await interaction.response.edit_message(content="Dismissed.", embed=None, view=None)
        except:
             pass
        self.stop()
