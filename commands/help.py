import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput, Select
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

class OnboardingView(View):
    def __init__(self, user, help_view):
        super().__init__(timeout=300)
        self.user = user
        self.help_view = help_view # Return to main help
        self.current_step = 0
        self.steps = [
            self.step_welcome,
            self.step_character,
            self.step_rolling,
            self.step_codex,
            self.step_tips
        ]
        self.update_buttons()

    def update_buttons(self):
        self.prev_btn.disabled = (self.current_step == 0)
        self.next_btn.disabled = (self.current_step == len(self.steps) - 1)
        self.page_indicator.label = f"{self.current_step + 1}/{len(self.steps)}"

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, row=1)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user: return
        self.current_step = max(0, self.current_step - 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.steps[self.current_step](), view=self)

    @discord.ui.button(label="1/5", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def page_indicator(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, row=1)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user: return
        self.current_step = min(len(self.steps) - 1, self.current_step + 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.steps[self.current_step](), view=self)

    @discord.ui.button(label="🏠 Home", style=discord.ButtonStyle.success, row=0)
    async def home_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user: return
        await interaction.response.edit_message(embed=self.help_view.get_home_embed(), view=self.help_view)

    # --- Step Embeds ---

    def step_welcome(self):
        embed = discord.Embed(title="👋 Welcome to CthulhuBot", color=discord.Color.gold())
        embed.description = (
            "You have entered a world of cosmic horror and investigation.\n"
            "This bot is your companion for managing characters, rolling dice, and looking up rules."
        )
        embed.add_field(name="🚀 Getting Started", value="Click **Next** to learn the basics.", inline=False)
        return embed

    def step_character(self):
        embed = discord.Embed(title="🕵️ Character Management", color=discord.Color.blue())
        embed.description = "Your investigator is your lifeline."
        embed.add_field(name="`/newinvestigator`", value="Launch the character creation wizard.", inline=False)
        embed.add_field(name="`/mycharacter`", value="View your interactive character sheet.", inline=False)
        embed.add_field(name="`/stat`", value="Quickly view or edit specific stats like HP or SAN.", inline=False)
        return embed

    def step_rolling(self):
        embed = discord.Embed(title="🎲 Dice Rolling", color=discord.Color.green())
        embed.description = "The dice decide your fate."
        embed.add_field(name="`/roll [skill]`", value="Roll a skill check. Example: `/roll Spot Hidden`.", inline=False)
        embed.add_field(name="Bonus/Penalty", value="The roll menu allows you to add Bonus/Penalty dice interactively.", inline=False)
        embed.add_field(name="Luck & Pushing", value="You can Spend Luck or Push the roll directly from the result card.", inline=False)
        return embed

    def step_codex(self):
        embed = discord.Embed(title="📜 The Codex", color=discord.Color.purple())
        embed.description = "Knowledge is power (and madness)."
        embed.add_field(name="`/codex`", value="Browse the entire library of monsters, spells, and items.", inline=False)
        embed.add_field(name="`/monster [name]`", value="Look up a monster stat block.", inline=False)
        embed.add_field(name="`/weapon [name]`", value="Check weapon stats.", inline=False)
        return embed

    def step_tips(self):
        embed = discord.Embed(title="💡 Pro Tips", color=discord.Color.teal())
        embed.add_field(name="Quick Search", value="Use the **Search** button on the main menu to find commands fast.", inline=False)
        embed.add_field(name="Combat", value="Use `/combat` to open a dedicated combat dashboard.", inline=False)
        embed.add_field(name="Session Tracking", value="Use `/session` to log skill checks for improvement rolls later.", inline=False)
        embed.set_footer(text="You are ready. Good luck.")
        return embed


class HelpSearchSelect(Select):
    def __init__(self, commands_list, help_view):
        self.help_view = help_view
        options = []
        for cmd in commands_list[:25]:
            prefix = "/"
            if isinstance(cmd, commands.Command): prefix = "!"
            elif isinstance(cmd, app_commands.ContextMenu): prefix = "🖱️ "

            label = f"{prefix}{cmd.name}"[:100]
            desc = getattr(cmd, "description", "No description.") or "No description."
            if len(desc) > 100: desc = desc[:97] + "..."

            options.append(discord.SelectOption(label=label, value=cmd.name, description=desc))

        super().__init__(placeholder="Select a command...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        cmd_name = self.values[0]
        # Find the command object again
        cmd_obj = None
        for cat_cmds in self.help_view.help_data.values():
            for cmd in cat_cmds:
                if cmd.name == cmd_name:
                    cmd_obj = cmd
                    break
            if cmd_obj: break

        if cmd_obj:
            embed = self.help_view.get_command_embed(cmd_obj)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("Command not found.", ephemeral=True)

class HelpSearchSelectView(View):
    def __init__(self, commands_list, help_view):
        super().__init__(timeout=60)
        self.add_item(HelpSearchSelect(commands_list, help_view))


class SearchModal(Modal, title="Search Commands"):
    query = TextInput(label="What are you looking for?", placeholder="e.g. roll, madness, sanity...", min_length=2, max_length=50)

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        query = self.query.value.strip()

        # Collect all commands
        all_commands = []
        for cat_cmds in self.view.help_data.values():
            all_commands.extend(cat_cmds)

        unique_commands = {cmd.name: cmd for cmd in all_commands}
        names = list(unique_commands.keys())

        # 1. Exact Match
        exact = [cmd for cmd in all_commands if query.lower() == cmd.name.lower()]
        if exact:
            # Show detail directly
            embed = self.view.get_command_embed(exact[0])
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 2. Fuzzy Match
        results = process.extract(query, names, scorer=fuzz.WRatio, limit=25, score_cutoff=60)
        matches = [unique_commands[res[0]] for res in results]

        if not matches:
             # Try description search
             desc_matches = []
             for cmd in all_commands:
                 desc = getattr(cmd, "description", "") or ""
                 if query.lower() in desc.lower():
                     desc_matches.append(cmd)

             matches = desc_matches[:25]

        if not matches:
            await interaction.response.send_message(f"❌ No commands found for '{query}'. Try 'roll', 'monster', or 'loot'.", ephemeral=True)
            return

        if len(matches) == 1:
             embed = self.view.get_command_embed(matches[0])
             await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
             # Multiple matches -> Dropdown
             select_view = HelpSearchSelectView(matches, self.view)
             await interaction.response.send_message(f"🔍 Found {len(matches)} matches for '{query}':", view=select_view, ephemeral=True)

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
        # Switch to Onboarding View
        view = OnboardingView(self.user, self)
        await interaction.response.edit_message(embed=view.steps[0](), view=view)

    async def search_callback(self, interaction: discord.Interaction):
        # Modals require response.send_modal, cannot be deferred beforehand
        await interaction.response.send_modal(SearchModal(self))

    async def category_button_callback(self, interaction: discord.Interaction):
        # Extract category from custom_id
        custom_id = interaction.data["custom_id"]
        category = custom_id.replace("btn_cat_", "")
        await interaction.response.edit_message(embed=self.get_category_embed(category), view=self)

    # --- Embed Generators ---

    def get_command_embed(self, cmd):
        prefix = "/"
        if isinstance(cmd, commands.Command): prefix = "!"
        elif isinstance(cmd, app_commands.ContextMenu): prefix = "🖱️ "

        name = f"{prefix}{cmd.name}"
        desc = getattr(cmd, "description", "No description.") or "No description."

        embed = discord.Embed(title=f"📖 Command: {name}", description=desc, color=discord.Color.gold())

        # Add usage/params if possible
        if isinstance(cmd, app_commands.Command):
             params = []
             for param in cmd.parameters:
                 req = "Required" if param.required else "Optional"
                 params.append(f"`{param.name}` ({req}): {param.description}")

             if params:
                 embed.add_field(name="Parameters", value="\n".join(params), inline=False)

        return embed

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

    # get_onboarding_embed is no longer used but kept for compatibility if needed (or can be removed)
    def get_onboarding_embed(self):
         # This is replaced by OnboardingView, but we can keep it as a fallback or remove it.
         # For safety, I'll leave it returning the first step of the view.
         view = OnboardingView(self.user, self)
         return view.steps[0]()

    def get_category_embed(self, category):
        commands_list = self.help_data.get(category, [])
        commands_list.sort(key=lambda c: c.name)

        embed = discord.Embed(
            title=f"{CATEGORY_EMOJIS.get(category, '')} {category} Commands",
            color=discord.Color.blue()
        )

        description = ""
        for cmd in commands_list:
            # Handle slash commands vs context menus vs text commands
            prefix = "/"
            if isinstance(cmd, commands.Command):
                prefix = "!" # Assuming prefix commands
            elif isinstance(cmd, app_commands.ContextMenu):
                prefix = "🖱️ " # Right click

            name = f"{prefix}{cmd.name}"
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


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def generate_help_data(self, ctx):
        """
        Generates a dictionary of Category -> List of Commands.
        Dynamically discovers commands based on bot.tree and binding.
        """
        help_data = {cat: [] for cat in set(COG_CATEGORY_MAP.values())}
        help_data["Other"] = [] # Ensure Other exists

        # Build Cog Category Cache
        # Check if Cogs have a 'category' attribute
        cog_categories = {}
        for cog_name, cog in self.bot.cogs.items():
            if hasattr(cog, 'category'):
                cog_categories[cog_name] = cog.category
            else:
                cog_categories[cog_name] = COG_CATEGORY_MAP.get(cog_name, "Other")

        # Track seen commands to avoid duplicates
        seen_commands = set()

        # 1. Iterate App Commands (Slash + Context Menus) from Tree
        # This is the Source of Truth for slash commands
        app_cmds = self.bot.tree.get_commands()

        for cmd in app_cmds:
            # Determine Category
            category = "Other"

            # Check Binding (The Cog)
            if cmd.binding:
                # Try getting category from the instance directly if possible
                if hasattr(cmd.binding, 'category'):
                    category = cmd.binding.category
                else:
                    cog_name = type(cmd.binding).__name__
                    category = cog_categories.get(cog_name, COG_CATEGORY_MAP.get(cog_name, "Other"))

            if cmd.name not in seen_commands:
                if category not in help_data: help_data[category] = []
                help_data[category].append(cmd)
                seen_commands.add(cmd.name)

        # 2. Iterate Text Commands (Legacy)
        # Some commands might still be text-only (e.g. !sync)
        for cmd in self.bot.commands:
            if cmd.hidden: continue

            # Permission check
            if not await self._can_run(cmd, ctx):
                continue

            if cmd.name not in seen_commands:
                # Determine Category
                category = "Other"
                if cmd.cog:
                    if hasattr(cmd.cog, 'category'):
                        category = cmd.cog.category
                    else:
                        cog_name = cmd.cog.qualified_name
                        category = cog_categories.get(cog_name, COG_CATEGORY_MAP.get(cog_name, "Other"))
                        if category == "Other":
                             category = COG_CATEGORY_MAP.get(type(cmd.cog).__name__, "Other")

                if category not in help_data: help_data[category] = []
                help_data[category].append(cmd)
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
