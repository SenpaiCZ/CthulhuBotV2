import discord
import random
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
from loadnsave import load_names_male_data, load_names_female_data, load_names_last_data

class GenderSelectView(View):
    def __init__(self, cog, ctx):
        super().__init__(timeout=60)
        self.cog = cog
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("This menu is not for you.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Male", style=discord.ButtonStyle.primary, emoji="👨")
    async def male_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.generate_and_send(self.ctx, "male", interaction)
        self.stop()

    @discord.ui.button(label="Female", style=discord.ButtonStyle.primary, emoji="👩")
    async def female_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.generate_and_send(self.ctx, "female", interaction)
        self.stop()

    @discord.ui.button(label="Random", style=discord.ButtonStyle.secondary, emoji="🎲")
    async def random_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        gender = random.choice(["male", "female"])
        await self.cog.generate_and_send(self.ctx, gender, interaction)
        self.stop()

class NPCActionView(View):
    def __init__(self, cog, ctx, gender, embed):
        super().__init__(timeout=300)
        self.cog = cog
        self.ctx = ctx
        self.gender = gender
        self.embed = embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("This menu is not for you.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Reroll", style=discord.ButtonStyle.success, emoji="🔄")
    async def reroll_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Generate new NPC
        new_embed = await self.cog.create_npc_embed(self.gender)
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
        if interaction.message.flags.ephemeral:
            # Cannot delete ephemeral messages, so we clear content
            await interaction.response.edit_message(content="Dismissed.", embed=None, view=None)
        else:
            try:
                await interaction.message.delete()
            except discord.NotFound:
                pass # Already deleted
            except discord.Forbidden:
                await interaction.response.edit_message(content="Dismissed.", embed=None, view=None)
        self.stop()

class createnpc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_stat_emoji(self, stat_name):
        stat_emojis = {
            "STR": "💪", "DEX": "🏃", "CON": "🧡", "INT": "🧠",
            "POW": "⚡", "APP": "😍", "EDU": "🎓", "SIZ": "📏",
            "HP": "❤️", "LUCK": "🍀",
        }
        return stat_emojis.get(stat_name, "")

    async def create_npc_embed(self, gender):
        last_names = await load_names_last_data()

        if gender == "male":
            first_names = await load_names_male_data()
        else:
            first_names = await load_names_female_data()

        # Name Generation
        name = random.choice(first_names)
        if random.random() < 0.3:
            name += " " + random.choice(first_names)
        name += " " + random.choice(last_names)
        if random.random() < 0.5:
            name += "-" + random.choice(last_names)

        # Stat Generation Helpers
        def roll_3d6_x5():
            # Using logic from original: sum of (sorted 3 dice)[1:] -> sum of top 2 of 3?
            # Original: 5 * sum(sorted([random.randint(1, 6) for _ in range(3)])[1:])
            # This is correct.
            return 5 * sum(sorted([random.randint(1, 6) for _ in range(3)])[1:])

        def roll_2d6_plus_6_x5():
             # Original: 5 * (sum(sorted([random.randint(1, 6) for _ in range(2)])) + 6)
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

        embed = discord.Embed(
            title=f"👤 {name}",
            description=f"**Gender:** {gender.capitalize()}",
            color=discord.Color.gold()
        )

        # Field 1: Physical
        phys_text = (
            f"{self.get_stat_emoji('STR')} **STR:** {stats['STR']}\n"
            f"{self.get_stat_emoji('CON')} **CON:** {stats['CON']}\n"
            f"{self.get_stat_emoji('SIZ')} **SIZ:** {stats['SIZ']}\n"
            f"{self.get_stat_emoji('DEX')} **DEX:** {stats['DEX']}\n"
             f"{self.get_stat_emoji('HP')} **HP:** {stats['HP']}"
        )
        embed.add_field(name="Physical", value=phys_text, inline=True)

        # Field 2: Mental
        ment_text = (
            f"{self.get_stat_emoji('INT')} **INT:** {stats['INT']}\n"
            f"{self.get_stat_emoji('POW')} **POW:** {stats['POW']}\n"
            f"{self.get_stat_emoji('EDU')} **EDU:** {stats['EDU']}\n"
            f"{self.get_stat_emoji('APP')} **APP:** {stats['APP']}\n"
            f"{self.get_stat_emoji('LUCK')} **LUCK:** {stats['LUCK']}"
        )
        embed.add_field(name="Mental", value=ment_text, inline=True)

        embed.set_footer(text="Call of Cthulhu NPC Generator")
        return embed

    async def generate_and_send(self, ctx, gender, interaction=None):
        embed = await self.create_npc_embed(gender)
        view = NPCActionView(self, ctx, gender, embed)

        if interaction:
            # If responding to a button press (edit the message)
            await interaction.response.edit_message(content=None, embed=embed, view=view)
        else:
            # If responding to a command
            if ctx.interaction:
                await ctx.interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            else:
                await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(aliases=["cNPC"], description="Generate an NPC with random name and stats.")
    @app_commands.describe(gender="Gender of the NPC (male, female, or random)")
    async def createnpc(self, ctx, gender: str = None):
        """
        Generates a random NPC.
        Usage: /createnpc [gender]
        """
        if gender:
            gender = gender.lower()
            if gender not in ["male", "female", "random"]:
                if ctx.interaction:
                    await ctx.interaction.response.send_message("Invalid gender. Use 'male', 'female', or 'random'.", ephemeral=True)
                else:
                    await ctx.send("Invalid gender. Use 'male', 'female', or 'random'.")
                return

            if gender == "random":
                gender = random.choice(["male", "female"])

            await self.generate_and_send(ctx, gender)
        else:
            # Show selection menu
            view = GenderSelectView(self, ctx)
            embed = discord.Embed(
                title="NPC Generator",
                description="Select a gender to generate an NPC.",
                color=discord.Color.blue()
            )

            if ctx.interaction:
                await ctx.interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            else:
                # For text command, we just send it.
                # Note: 'ephemeral' doesn't work for ctx.send, but buttons will guard interaction.
                await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(createnpc(bot))
