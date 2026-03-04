import discord
import random
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select, Button
from loadnsave import load_names_data
from emojis import get_stat_emoji

class GenderSelectView(View):
    def __init__(self, cog, interaction):
        super().__init__(timeout=60)
        self.cog = cog
        self.original_interaction = interaction

    @discord.ui.button(label="Male", style=discord.ButtonStyle.primary, emoji="👨")
    async def male_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.ask_region(interaction, "male")
        self.stop()

    @discord.ui.button(label="Female", style=discord.ButtonStyle.primary, emoji="👩")
    async def female_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.ask_region(interaction, "female")
        self.stop()

    @discord.ui.button(label="Random", style=discord.ButtonStyle.secondary, emoji="🎲")
    async def random_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        gender = random.choice(["male", "female"])
        await self.cog.ask_region(interaction, gender)
        self.stop()

class RegionSelect(Select):
    def __init__(self, cog, gender):
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

class RegionSelectView(View):
    def __init__(self, cog, gender):
        super().__init__(timeout=60)
        self.add_item(RegionSelect(cog, gender))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Since this view is ephemeral or edits the original message, checks might be tricky if user changed?
        # But generally we want to allow the user who invoked it.
        # For simplicity, we assume ephemeral responses or edits are fine.
        return True

class NPCActionView(View):
    def __init__(self, cog, interaction, gender, region, embed):
        super().__init__(timeout=300)
        self.cog = cog
        self.original_interaction = interaction
        self.gender = gender
        self.region = region
        self.embed = embed

    @discord.ui.button(label="Reroll", style=discord.ButtonStyle.success, emoji="🔄")
    async def reroll_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Generate new NPC
        new_embed = await self.cog.create_npc_embed(self.gender, self.region)
        # Update view's embed reference
        self.embed = new_embed
        await interaction.response.edit_message(embed=new_embed, view=self)

    @discord.ui.button(label="Save (DM)", style=discord.ButtonStyle.secondary, emoji="💾")
    async def save_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.user.send(embed=self.embed)
            await interaction.response.send_message("✅ Sent to your DMs!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I cannot DM you. Please check your privacy settings.", ephemeral=True)

    @discord.ui.button(label="Dismiss", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def dismiss_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # If the message is ephemeral, we can't delete it, but we can edit it to be empty or dismissed.
        # The prompt says "Progression will be pure command /randomnpc". Usually ephemeral responses.
        try:
            await interaction.response.edit_message(content="Dismissed.", embed=None, view=None)
        except:
             pass
        self.stop()

class RandomNPC(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Keeper"

    async def create_npc_embed(self, gender, region):
        all_names = await load_names_data()

        # Default to English if region not found, though select menu ensures valid keys
        region_names = all_names.get(region, all_names.get("english", {}))

        last_names = region_names.get("last", [])

        if gender == "male":
            first_names = region_names.get("male", [])
        else:
            first_names = region_names.get("female", [])

        # Name Generation
        if not first_names or not last_names:
             name = "Unknown NPC"
        else:
            name = random.choice(first_names)
            # Chance for double first name
            if random.random() < 0.1:
                name += " " + random.choice(first_names)

            name += " " + random.choice(last_names)

            # Chance for double last name
            if random.random() < 0.1:
                name += "-" + random.choice(last_names)

        # Stat Generation Helpers
        def roll_3d6_x5():
            # Standard CoC 7e: STR, CON, DEX, APP, POW are 3D6 * 5.
            return 5 * sum([random.randint(1, 6) for _ in range(3)])

        def roll_2d6_plus_6_x5():
            # Standard CoC 7e: SIZ, INT, EDU are (2D6+6) * 5.
            return 5 * (sum([random.randint(1, 6) for _ in range(2)]) + 6)

        stats = {
            "STR": roll_3d6_x5(),
            "CON": roll_3d6_x5(),
            "DEX": roll_3d6_x5(),
            "APP": roll_3d6_x5(),
            "POW": roll_3d6_x5(),
            "LUCK": roll_3d6_x5(),
            "SIZ": roll_2d6_plus_6_x5(),
            "INT": roll_2d6_plus_6_x5(),
            "EDU": roll_2d6_plus_6_x5(),
        }

        # Derived Stats
        stats["HP"] = (stats["CON"] + stats["SIZ"]) // 10
        stats["MP"] = stats["POW"] // 5
        stats["SAN"] = stats["POW"]

        # Build and Damage Bonus
        str_siz = stats["STR"] + stats["SIZ"]
        if 2 <= str_siz <= 64: db="-2"; b=-2
        elif 65 <= str_siz <= 84: db="-1"; b=-1
        elif 85 <= str_siz <= 124: db="0"; b=0
        elif 125 <= str_siz <= 164: db="+1D4"; b=1
        elif 165 <= str_siz <= 204: db="+1D6"; b=2
        elif 205 <= str_siz <= 284: db="+2D6"; b=3
        elif 285 <= str_siz <= 364: db="+3D6"; b=4
        elif 365 <= str_siz <= 444: db="+4D6"; b=5
        elif 445 <= str_siz <= 524: db="+5D6"; b=6
        else: db="+6D6"; b=7
        stats["DB"] = db
        stats["Build"] = b

        # Move
        mov = 8
        if stats["DEX"] < stats["SIZ"] and stats["STR"] < stats["SIZ"]: mov = 7
        elif stats["DEX"] > stats["SIZ"] and stats["STR"] > stats["SIZ"]: mov = 9
        stats["Move"] = mov

        embed = discord.Embed(
            title=f"👤 {name}",
            description=f"**Gender:** {gender.capitalize()}\n**Region:** {region.capitalize()}",
            color=discord.Color.gold()
        )

        # Field 1: Physical
        phys_text = (
            f"{get_stat_emoji('STR')} **STR:** {stats['STR']}\n"
            f"{get_stat_emoji('CON')} **CON:** {stats['CON']}\n"
            f"{get_stat_emoji('SIZ')} **SIZ:** {stats['SIZ']}\n"
            f"{get_stat_emoji('DEX')} **DEX:** {stats['DEX']}\n"
            f"{get_stat_emoji('HP')} **HP:** {stats['HP']}\n"
            f"{get_stat_emoji('Move')} **Move:** {stats['Move']}\n"
            f"{get_stat_emoji('Build')} **Build:** {stats['Build']}\n"
            f"{get_stat_emoji('DB')} **DB:** {stats['DB']}"
        )
        embed.add_field(name="Physical", value=phys_text, inline=True)

        # Field 2: Mental
        ment_text = (
            f"{get_stat_emoji('INT')} **INT:** {stats['INT']}\n"
            f"{get_stat_emoji('POW')} **POW:** {stats['POW']}\n"
            f"{get_stat_emoji('EDU')} **EDU:** {stats['EDU']}\n"
            f"{get_stat_emoji('APP')} **APP:** {stats['APP']}\n"
            f"{get_stat_emoji('SAN')} **SAN:** {stats['SAN']}\n"
            f"{get_stat_emoji('MP')} **MP:** {stats['MP']}\n"
            f"{get_stat_emoji('LUCK')} **LUCK:** {stats['LUCK']}"
        )
        embed.add_field(name="Mental", value=ment_text, inline=True)

        embed.set_footer(text="Call of Cthulhu NPC Generator")
        return embed

    async def ask_region(self, interaction, gender):
        view = RegionSelectView(self, gender)
        embed = discord.Embed(
            title="NPC Generator - Region",
            description=f"Selected Gender: **{gender.capitalize()}**\nNow select a region for the name.",
            color=discord.Color.blue()
        )
        # Edit the message
        await interaction.response.edit_message(embed=embed, view=view)

    async def generate_and_send(self, interaction, gender, region):
        embed = await self.create_npc_embed(gender, region)
        view = NPCActionView(self, interaction, gender, region, embed)

        # Edit the message
        await interaction.response.edit_message(embed=embed, view=view)

    @app_commands.command(name="randomnpc", description="👤 Generate an NPC with random name and stats.")
    async def randomnpc(self, interaction: discord.Interaction):
        """
        Generates a random NPC.
        """
        view = GenderSelectView(self, interaction)
        embed = discord.Embed(
            title="NPC Generator",
            description="Select a gender to generate an NPC.",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(RandomNPC(bot))
