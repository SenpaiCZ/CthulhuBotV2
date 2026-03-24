import discord
from discord.ui import View, Select
from emojis import get_stat_emoji
from schemas.roll import RollRequest
from services.roll_service import RollService
from services.character_service import CharacterService
from models.database import SessionLocal
from views.roll_view import RollView

class SessionView(View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.create_session = False
        self.message = None

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Not for you!", ephemeral=True)
        self.create_session = True
        self.stop()
        # Disable buttons
        for child in self.children: child.disabled = True
        try:
            await interaction.response.edit_message(view=self)
        except:
            pass

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary)
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Not for you!", ephemeral=True)
        self.create_session = False
        self.stop()
        # Disable buttons
        for child in self.children: child.disabled = True
        try:
            await interaction.response.edit_message(view=self)
        except:
            pass

class DisambiguationSelect(Select):
    def __init__(self, options):
        super().__init__(placeholder="Select a skill...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_stat = self.values[0]
        await interaction.response.defer()
        self.view.stop()

class DisambiguationView(View):
    def __init__(self, ctx, matching_stats):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.selected_stat = None

        options = [
            discord.SelectOption(label=stat, value=stat)
            for stat in matching_stats[:25]
        ]
        self.add_item(DisambiguationSelect(options))

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=1)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Not your session!", ephemeral=True)
            return False
        return True

class QuickSkillSelect(Select):
    def __init__(self, char_data, server_id, user_id):
        self.char_data = char_data
        self.server_id = server_id
        self.user_id = user_id

        # Get Skills and Sort
        ignored = [
            "Residence", "Game Mode", "Archetype", "NAME", "Occupation",
            "Age", "HP", "MP", "SAN", "LUCK", "Build", "Damage Bonus", "Move",
            "STR", "DEX", "INT", "CON", "APP", "POW", "SIZ", "EDU", "Dodge",
            "Backstory"
        ]
        skills = []
        for key, val in char_data.items():
            if key in ignored: continue
            if isinstance(val, (int, float)):
                skills.append((key, val))

        skills.sort(key=lambda x: x[1], reverse=True)
        top_skills = skills[:25]

        options = []
        for name, val in top_skills:
            emoji = get_stat_emoji(name)
            options.append(discord.SelectOption(label=f"{name} ({val}%)", value=name, emoji=emoji))

        super().__init__(placeholder="🎲 Quick Roll...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        skill_name = self.values[0]
        current_val = self.char_data.get(skill_name, 0)

        # Roll using service
        request = RollRequest(stat_name=skill_name, bonus_dice=0, penalty_dice=0, difficulty="Regular")
        roll_result = RollService.calculate_roll(request, current_val)
        
        db = SessionLocal()
        investigator = CharacterService.get_investigator_by_guild_and_user(db, self.server_id, self.user_id)

        view = RollView(
            interaction=interaction,
            roll_result=roll_result,
            stat_name=skill_name,
            stat_value=current_val,
            investigator=investigator,
            db=db
        )

        color = discord.Color.green()
        if roll_result.result_level <= 1: color = discord.Color.red()
        elif roll_result.result_level >= 4: color = discord.Color.gold()

        desc = f"{interaction.user.mention} rolled **{skill_name}**!\n"
        desc += f"Dice: [{', '.join(map(str, roll_result.rolls))}] -> **{roll_result.final_roll}**\n\n"
        desc += f"**{roll_result.result_text}**\n\n"
        desc += f"**{skill_name}**: {current_val} - {current_val//2} - {current_val//5}\n"

        embed = discord.Embed(description=desc, color=color)

        # Public
        msg = await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message(f"✅ Rolled **{skill_name}** in channel.", ephemeral=True)
