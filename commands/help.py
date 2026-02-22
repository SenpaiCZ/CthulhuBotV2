import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
import traceback
import random
from rapidfuzz import process, fuzz

# Mapping of Cog Names to Categories
# Keys are the class name of the Cog (or the name passed to bot.add_cog)
COG_CATEGORY_MAP = {
    # Player
    "newinvestigator": "Player",
    "mycharacter": "Player",
    "Roll": "Player",
    "stat": "Player",
    "Backstory": "Player",
    "Session": "Player",
    "Retire": "Player",
    "DeleteInvestigator": "Player",
    "PrintCharacter": "Player",
    "Versus": "Player",
    "AddSkill": "Player",
    "Rename": "Player",
    "RenameSkill": "Player",

    # Codex
    "Codex": "Codex",

    # Keeper
    "Loot": "Keeper",
    "Madness": "Keeper",
    "Handout": "Keeper",
    "MacGuffin": "Keeper",
    "RandomNPC": "Keeper",
    "RandomName": "Keeper",
    "Chase": "Keeper",

    # Music
    "Music": "Music",

    # Admin
    "Admin": "Admin",
    "Enroll": "Admin",
    "AutoRoom": "Admin",
    "ReactionRole": "Admin",
    "GameRoles": "Admin",
    "RSS": "Admin",
    "Karma": "Admin",
    "Ping": "Admin",
    "Restart": "Admin",
    "UpdateBot": "Admin",

    # Other
    "Help": "Other",
    "Polls": "Other",
    "Reminders": "Other",
    "ReportBug": "Other",
    "Uptime": "Other",
    "Giveaway": "Other"
}

CATEGORY_EMOJIS = {
    "Player": "🎲",
    "Codex": "📜",
    "Keeper": "🐙",
    "Music": "🎵",
    "Admin": "🛠️",
    "Other": "📁"
}

CATEGORY_STYLES = {
    "Player": discord.ButtonStyle.primary,
    "Codex": discord.ButtonStyle.secondary,
    "Keeper": discord.ButtonStyle.danger,
    "Music": discord.ButtonStyle.secondary,
    "Admin": discord.ButtonStyle.secondary,
    "Other": discord.ButtonStyle.secondary
}

GRIMOIRE_TIPS = [
    "Tip: Use /roll sanity to quickly make a Sanity check.",
    "Tip: You can use /pogo forceupdate to refresh event data.",
    "Tip: The Codex has info on thousands of monsters and spells.",
    "Tip: Use /session to track your skill improvements automatically.",
    "Tip: Keep your inventory updated with /addbackstory.",
    "Tip: Need to find a rule? Try searching for 'combat' or 'chase'.",
    "Tip: Check your luck often with /stat.",
    "Tip: You can print your character sheet to PDF with /printcharacter."
]

class SearchModal(Modal, title="Search Commands"):
    query = TextInput(label="What are you looking for?", placeholder="e.g. roll, madness, sanity...", min_length=2, max_length=50)

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        # Update the dashboard directly
        query_str = self.query.value
        embed = self.view.get_search_embed(query_str)
        await interaction.response.edit_message(embed=embed, view=self.view)

class HelpView(View):
    def __init__(self, help_data, user, bot):
        super().__init__(timeout=300)
        self.help_data = help_data
        self.user = user
        self.bot = bot
        self.current_category = None

        # Build dynamic buttons based on available categories
        # Row 0: Navigation / Utilities
        self.add_item(Button(label="Start Here", style=discord.ButtonStyle.success, emoji="👋", row=0, custom_id="btn_onboarding"))
        self.add_item(Button(label="Search", style=discord.ButtonStyle.primary, emoji="🔍", row=0, custom_id="btn_search"))
        self.add_item(Button(label="Home", style=discord.ButtonStyle.secondary, emoji="🏠", row=0, custom_id="btn_home"))

        # Row 1 & 2: Categories
        # We want a specific order: Player, Codex, Keeper, Music, Other, Admin
        order = ["Player", "Codex", "Keeper", "Music", "Other", "Admin"]

        # Calculate available categories
        available = [cat for cat in order if cat in help_data and help_data[cat]]

        row_idx = 1
        col_idx = 0
        for cat in available:
            btn = Button(
                label=cat,
                style=CATEGORY_STYLES.get(cat, discord.ButtonStyle.secondary),
                emoji=CATEGORY_EMOJIS.get(cat, "📁"),
                row=row_idx,
                custom_id=f"btn_cat_{cat}"
            )
            # We need to bind the callback properly
            btn.callback = self.category_button_callback
            self.add_item(btn)

            col_idx += 1
            if col_idx >= 3: # 3 buttons per row for categories to look nice
                col_idx = 0
                row_idx += 1

        # Hook up Row 0 callbacks
        for child in self.children:
            if child.custom_id == "btn_onboarding":
                child.callback = self.onboarding_callback
            elif child.custom_id == "btn_search":
                child.callback = self.search_callback
            elif child.custom_id == "btn_home":
                child.callback = self.home_callback

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.user:
            await interaction.response.send_message("This menu is for the investigator who summoned it.", ephemeral=True)
            return False
        return True

    # --- Callbacks ---

    async def home_callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.get_home_embed(), view=self)

    async def onboarding_callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.get_onboarding_embed(), view=self)

    async def search_callback(self, interaction: discord.Interaction):
        # Modals require response.send_modal, cannot be deferred beforehand
        await interaction.response.send_modal(SearchModal(self))

    async def category_button_callback(self, interaction: discord.Interaction):
        # Extract category from custom_id
        custom_id = interaction.data["custom_id"]
        category = custom_id.replace("btn_cat_", "")
        await interaction.response.edit_message(embed=self.get_category_embed(category), view=self)

    # --- Embed Generators ---

    def get_home_embed(self):
        embed = discord.Embed(
            title="🐙 CthulhuBot Help",
            description=(
                "**Greetings, Investigator.**\n"
                "The stars have aligned. Access the archives, manage your sanity, or consult the Keeper below.\n\n"
                "ℹ️ **Tip:** Use the `🔍 Search` button to find specific commands instantly."
            ),
            color=discord.Color.dark_teal()
        )

        # Add visual flair
        embed.add_field(name="🎲 Player Zone", value="Manage character, roll dice, check stats.", inline=True)
        embed.add_field(name="📜 Codex", value="Browse monsters, spells, and items.", inline=True)
        embed.add_field(name="🐙 Keeper Tools", value="Loot, madness, and handouts.", inline=True)

        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)
        embed.set_footer(text=random.choice(GRIMOIRE_TIPS))
        return embed

    def get_onboarding_embed(self):
        embed = discord.Embed(
            title="👋 New Investigator Guide",
            description="Welcome to the team! Here is your survival guide:",
            color=discord.Color.green()
        )

        embed.add_field(
            name="1️⃣ Create an Investigator",
            value="Use `/newinvestigator` to launch the character creation wizard. It will guide you through stats, occupation, and skills.",
            inline=False
        )
        embed.add_field(
            name="2️⃣ Roll the Dice",
            value="Use `/roll` (or `/r`) to make checks. Example: `/roll Spot Hidden`. The bot knows your stats!",
            inline=False
        )
        embed.add_field(
            name="3️⃣ Track your Session",
            value="Use `/session action:Start Session` to begin tracking skill checks for improvement. At the end, use `/session action:Auto` to roll for upgrades.",
            inline=False
        )
        embed.add_field(
            name="4️⃣ Consult the Codex",
            value="Use `/codex` or specific commands like `/monster` or `/spell` to look up rules and lore.",
            inline=False
        )

        embed.set_footer(text="Good luck. You'll need it.")
        return embed

    def get_category_embed(self, category):
        commands_list = self.help_data.get(category, [])
        commands_list.sort(key=lambda c: c.name)

        embed = discord.Embed(
            title=f"{CATEGORY_EMOJIS.get(category, '')} {category} Commands",
            color=discord.Color.blue()
        )

        description = ""
        for cmd in commands_list:
            name = f"/{cmd.name}"
            # Context Menus (and other types) might not have a description attribute
            desc = getattr(cmd, "description", "No description.") or "No description."

            # Hybrid command check
            if hasattr(cmd, 'help') and cmd.help:
                desc = cmd.help

            if len(desc) > 60:
                desc = desc[:57] + "..."

            description += f"**`{name}`** - {desc}\n"

        if not description:
            description = "No commands found."

        embed.description = description
        embed.set_footer(text=f"Total: {len(commands_list)} commands")
        return embed

    def get_search_embed(self, query):
        # We need to search across all categories
        all_commands = []
        for cat_cmds in self.help_data.values():
            all_commands.extend(cat_cmds)

        # Deduplicate by name
        seen = set()
        unique_commands = []
        for cmd in all_commands:
            if cmd.name not in seen:
                seen.add(cmd.name)
                unique_commands.append(cmd)

        # Prepare for fuzzy search
        # We search name and description
        choices = {cmd.name: cmd for cmd in unique_commands}
        names = list(choices.keys())

        # 1. Exact match
        exact = [cmd for cmd in unique_commands if query.lower() == cmd.name.lower()]

        # 2. Fuzzy match names
        fuzzy_results = process.extract(query, names, scorer=fuzz.WRatio, limit=10, score_cutoff=50)
        fuzzy_names = [res[0] for res in fuzzy_results]

        # 3. Description search (simple contains)
        desc_matches = []
        for cmd in unique_commands:
            desc = getattr(cmd, "description", "") or ""
            if query.lower() in desc.lower():
                desc_matches.append(cmd)

        # Combine results
        final_results = []
        if exact: final_results.extend(exact)

        for name in fuzzy_names:
            cmd = choices[name]
            if cmd not in final_results:
                final_results.append(cmd)

        for cmd in desc_matches:
            if cmd not in final_results:
                final_results.append(cmd)

        # Limit to top 10
        final_results = final_results[:10]

        embed = discord.Embed(
            title=f"🔍 Search Results: '{query}'",
            color=discord.Color.gold()
        )

        if final_results:
            desc_text = ""
            for cmd in final_results:
                name = f"/{cmd.name}"
                desc = getattr(cmd, "description", "No description.") or "No description."
                if len(desc) > 80: desc = desc[:77] + "..."
                desc_text += f"**`{name}`** - {desc}\n"
            embed.description = desc_text
        else:
            embed.description = "No matching commands found. Try a different term."

        return embed


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def generate_help_data(self, ctx):
        """
        Generates a dictionary of Category -> List of Commands.
        Dynamically discovers commands based on Cog membership.
        """
        help_data = {cat: [] for cat in set(COG_CATEGORY_MAP.values())}
        help_data["Other"] = [] # Ensure Other exists

        # Track seen commands to avoid duplicates (e.g. Slash vs Text)
        seen_commands = set()

        for cog_name, cog in self.bot.cogs.items():
            # Determine Category
            category = COG_CATEGORY_MAP.get(cog_name, "Other")
            if category not in help_data:
                help_data[category] = []

            # Get Commands (Slash/App Commands)
            app_cmds = cog.get_app_commands()
            for cmd in app_cmds:
                if cmd.name not in seen_commands:
                    help_data[category].append(cmd)
                    seen_commands.add(cmd.name)

            # Get Commands (Text/Hybrid)
            # Only add if not already added via app_commands (hybrid commands show up in both?)
            # Actually hybrid commands appear in get_commands() as HybridCommand objects
            text_cmds = cog.get_commands()
            for cmd in text_cmds:
                if cmd.hidden: continue

                # Check permission using our custom _can_run
                if not await self._can_run(cmd, ctx):
                    continue

                if cmd.name not in seen_commands:
                    help_data[category].append(cmd)
                    seen_commands.add(cmd.name)

        # Handle Orphaned Commands (No Cog)
        # Usually these are text commands added directly to bot
        # Or app commands added to tree without cog

        # We can inspect bot.commands for text commands without cog
        for cmd in self.bot.commands:
            if not cmd.cog and not cmd.hidden:
                 if await self._can_run(cmd, ctx):
                     if cmd.name not in seen_commands:
                         help_data["Other"].append(cmd)
                         seen_commands.add(cmd.name)

        # Remove empty categories
        return {k: v for k, v in help_data.items() if v}

    async def _can_run(self, cmd, ctx):
        # Permission check
        if isinstance(cmd, commands.Command):
            try:
                return await cmd.can_run(ctx)
            except:
                return False
        return True # Assume app commands are visible unless filtered elsewhere

    @app_commands.command(name="help", description="Show the interactive help dashboard.")
    async def help_command(self, interaction: discord.Interaction):
        """
        Shows the interactive help dashboard.
        """
        # Defer immediately ephemeral
        await interaction.response.defer(ephemeral=True)

        try:
            ctx = await self.bot.get_context(interaction)
            help_data = await self.generate_help_data(ctx)

            if not help_data:
                await interaction.followup.send("No commands available for you.")
                return

            view = HelpView(help_data, interaction.user, self.bot)
            embed = view.get_home_embed()

            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            print(f"Error generating help menu: {e}")
            traceback.print_exc()
            await interaction.followup.send("An error occurred while accessing the archives.")

async def setup(bot):
    await bot.add_cog(Help(bot))
