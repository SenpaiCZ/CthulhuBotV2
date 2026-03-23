import discord, random
from discord.ext import commands
from discord import app_commands
from models.database import SessionLocal
from services.character_service import CharacterService

class BackstoryGenerationButton(discord.ui.Button):
    def __init__(self, category, content):
        super().__init__(style=discord.ButtonStyle.secondary, label=f"Add to {category}")
        self.category = category
        self.content = content

    async def callback(self, interaction: discord.Interaction):
        view: BackstoryGenerationView = self.view
        if interaction.user != view.user:
            await interaction.response.send_message("This isn't for you!", ephemeral=True)
            return

        db = SessionLocal()
        try:
            inv = CharacterService.get_investigator_by_guild_and_user(db, str(interaction.guild.id), str(interaction.user.id))
            if not inv:
                await interaction.response.send_message("Investigator not found.", ephemeral=True)
                return

            CharacterService.manage_backstory(db, inv.id, self.category, self.content, "add")
            await interaction.response.send_message(f"✅ Added to **{self.category}**.", ephemeral=True)
            self.disabled = True
            await interaction.message.edit(view=view)
        finally:
            db.close()

class BackstoryGenerationView(discord.ui.View):
    def __init__(self, user, ideology, people, location, possession, trait):
        super().__init__(timeout=900)
        self.user = user
        self.add_item(BackstoryGenerationButton("Ideology and Beliefs", ideology))
        self.add_item(BackstoryGenerationButton("Significant People", people))
        self.add_item(BackstoryGenerationButton("Meaningful Locations", location))
        self.add_item(BackstoryGenerationButton("Treasured Possessions", possession))
        self.add_item(BackstoryGenerationButton("Traits", trait))

class generatebackstory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="generatebackstory", description="🎲 Generate random backstory for your investigator.")
    async def generatebackstory(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("This command is not allowed in DMs.", ephemeral=True)
            return

        ideology_beliefs = [
            "You devoutly follow a higher power and engage in regular worship and prayer.",
            "You firmly believe that mankind can thrive without the influence of religions.",
            "You are a dedicated follower of science, putting your faith in its ability to provide answers.",
            "You hold a strong belief in fate, whether through concepts like karma or superstitions.",
            "You are a member of a society or secret organization.",
            "You are deeply convinced that there is inherent evil in society that needs to be eradicated.",
            "You are deeply involved in the occult, exploring practices like astrology or tarot.",
            "Your ideology revolves around politics and specific principles.",
            "You firmly believe that 'money is power' and are determined to accumulate wealth.",
            "You are a passionate campaigner or activist for various causes.",
            "You are a staunch environmentalist, dedicated to conservation efforts.",
            "You are a pacifist, opposing all forms of violence.",
            "You are a staunch traditionalist, valuing long-standing customs.",
            "You are a technology enthusiast, believing it holds the key to a better future.",
            "You are a hedonist, seeking pleasure and enjoyment above all else.",
            "You are an advocate for social justice, fighting against discrimination."
        ]
        selected_ideology = random.choice(ideology_beliefs)

        significant_people = [
            "Your mentor who guided you.", "A childhood bully who made your life miserable.",
            "A long-lost relative who suddenly reappeared.", "A professional rival who constantly challenges you.",
            "A loyal pet or animal companion.", "A spiritual leader or guru.",
            "A former business partner who betrayed you.", "A supernatural being that haunts your dreams.",
            "A mysterious informant providing cryptic clues.", "A celebrity you once crossed paths with.",
            "A legendary figure from history or mythology.", "An influential political figure.",
            "A fellow explorer from perilous journeys.", "A mysterious guardian spirit.",
            "A wise old sage imparting wisdom.", "A childhood pen pal who vanished."
        ]
        selected_people = random.choice(significant_people)

        locations = [
            "A hidden cave with an ancient relic.", "A remote mountain cabin.", "A bustling city square.",
            "An abandoned factory with a secret.", "A quaint seaside town from childhood.",
            "An eerie cemetery with a paranormal encounter.", "A sacred temple atop a mist-covered mountain.",
            "A forgotten underground tunnel system.", "A historic battlefield with uncovered artifacts.",
            "A hidden garden behind an old mansion."
        ]
        selected_location = random.choice(locations)

        possessions = [
            "A handwritten journal of travels.", "A mysterious ancient artifact.", "A locket with a picture.",
            "A rare first edition book.", "A vintage typewriter.", "A vial of glowing liquid.",
            "A worn and weathered map.", "A pocket watch with mystical qualities.",
            "A peculiar amulet from a remote temple.", "A loyal animal companion."
        ]
        selected_possession = random.choice(possessions)

        traits = [
            "Meticulous Planner", "Adventurous Spirit", "Keen Observer", "Empathetic",
            "Resourceful", "Eloquent Speaker", "Fearless", "Eccentric", "Resilient", "Charismatic Leader"
        ]
        selected_trait = random.choice(traits)

        embed = discord.Embed(title="Character Backstory Generator", color=0x00ff00)
        embed.add_field(name="Ideology/Beliefs", value=selected_ideology, inline=False)
        embed.add_field(name="Significant People", value=selected_people, inline=False)
        embed.add_field(name="Meaningful Locations", value=selected_location, inline=False)
        embed.add_field(name="Treasured Possessions", value=selected_possession, inline=False)
        embed.add_field(name="Traits", value=selected_trait, inline=False)

        view = BackstoryGenerationView(
            user=interaction.user,
            ideology=selected_ideology,
            people=selected_people,
            location=selected_location,
            possession=selected_possession,
            trait=selected_trait
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(generatebackstory(bot))
