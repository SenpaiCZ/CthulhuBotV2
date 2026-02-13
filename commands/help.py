import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select

# Mapping of Cog Names (lowercase) to Categories
COG_GROUPS = {
    # Character Creation & Management
    "newinvestigator": "Character",
    "mychar": "Character",
    "stat": "Character",
    "printcharacter": "Character",
    "rename": "Character",
    "renameskill": "Character",
    "addbackstory": "Character",
    "removebackstory": "Character",
    "updatebackstory": "Character",
    "generatebackstory": "Character",
    "retire_character": "Character",
    "updatestats": "Character",

    # Rolling & Session
    "newroll": "Rolling",
    "changeluck": "Rolling",
    "sessionmanager": "Rolling",

    # Keeper Tools
    "codex": "Keeper",
    "loot": "Keeper",
    "macguffin": "Keeper",
    "madness": "Keeper",
    "randomname": "Keeper",
    "chase": "Keeper",
    "createnpc": "Keeper",
    "deleteinvestigator": "Keeper", # Arguably admin but fits keeper managing players

    # Server Administration
    "admin_slash": "Admin", # Includes Sync
    "deleter": "Server",
    "autoroom": "Server",
    "reactionroles": "Server",
    "gameroles": "Server",
    "smartreaction": "Server",
    "rss": "Server",
    "giveaway": "Server",
    "polls": "Server",
    "reminders": "Server",
    "backup": "Server",
    "updatebot": "Server",
    "botstatus": "Server",
    "changeprefix": "Server",
    "enroll": "Server",

    # Utility & Fun
    "ping": "Utility",
    "uptime": "Utility",
    "reportbug": "Utility",
    "pogo": "Fun",
    "music": "Fun",
}

class HelpSelect(Select):
    def __init__(self, help_data):
        self.help_data = help_data
        options = []

        # Sort categories to ensure consistent order
        sorted_categories = sorted(help_data.keys())

        emoji_map = {
            "Character": "👤",
            "Rolling": "🎲",
            "Keeper": "📜",
            "Server": "🛠️",
            "Admin": "🛡️",
            "Utility": "🔧",
            "Fun": "🎉",
            "Other": "📁"
        }

        for category in sorted_categories:
            description = f"{len(help_data[category])} commands"
            emoji = emoji_map.get(category, "📁")
            options.append(discord.SelectOption(
                label=category,
                description=description,
                value=category,
                emoji=emoji
            ))

        super().__init__(placeholder="Select a category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        commands_list = self.help_data.get(category, [])

        embed = discord.Embed(
            title=f"Help: {category}",
            description=f"Here are the commands for **{category}**:",
            color=discord.Color.blue()
        )

        # Iterate commands and add fields
        # If too many commands, we might need to truncate or list simply
        # Discord Embed Field Value Limit is 1024 chars.
        # We'll try to put multiple commands in one description or fields

        if len(commands_list) > 25:
             # Just list names if too many
             command_names = [f"`/{cmd.name}`" if isinstance(cmd, app_commands.Command) else f"`!{cmd.name}`" for cmd in commands_list]
             embed.description += "\n" + ", ".join(command_names)
        else:
            for cmd in commands_list:
                name = cmd.name
                if hasattr(cmd, 'app_command') and cmd.app_command:
                     # Hybrid
                     name = f"/{name}"
                elif isinstance(cmd, app_commands.Command):
                     name = f"/{name}"
                else:
                     name = f"!{name}"

                desc = cmd.description or cmd.help or "No description."
                # Truncate desc
                if len(desc) > 100: desc = desc[:97] + "..."

                embed.add_field(name=name, value=desc, inline=False)

        await interaction.response.edit_message(embed=embed, view=self.view)

class HelpView(View):
    def __init__(self, help_data, user):
        super().__init__(timeout=180)
        self.user = user
        self.add_item(HelpSelect(help_data))

    @discord.ui.button(label="Home", style=discord.ButtonStyle.secondary, row=1)
    async def home(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
             return await interaction.response.send_message("This menu is not for you.", ephemeral=True)

        # Reset to home embed
        embed = discord.Embed(
            title="🐙 Cthulhu Bot Help",
            description="Greetings, Investigator.\nThe stars align for you to seek knowledge. Consult the archives below to uncover the secrets of this bot.",
            color=discord.Color.teal()
        )
        embed.set_footer(text="Only commands available to you are shown.")
        await interaction.response.edit_message(embed=embed, view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.user:
            await interaction.response.send_message("This menu is not for you.", ephemeral=True)
            return False
        return True

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def generate_help_data(self, ctx):
        """
        Generates a dictionary of Category -> List of Commands.
        Filters commands based on user permissions in ctx.
        """
        help_data = {}

        # Iterate over all Cogs
        for cog_name, cog in self.bot.cogs.items():
            # Determine Category
            category = COG_GROUPS.get(cog_name.lower(), "Other")

            # Get commands for this Cog
            # We want to check both hybrid/text commands AND slash commands
            # cog.get_commands() returns text/hybrid commands
            # cog.get_app_commands() returns slash commands (if any are strictly slash)

            commands_to_check = list(cog.get_commands())
            # Note: Hybrid commands appear in get_commands().
            # Pure app_commands might be in get_app_commands()

            # We also need to check permissions
            visible_commands = []

            for cmd in commands_to_check:
                if cmd.hidden:
                    continue

                try:
                    if await cmd.can_run(ctx):
                        visible_commands.append(cmd)
                except:
                    # Permission check failed
                    continue

            # Also check app_commands (pure slash)
            # app_commands don't have 'can_run' in the same way, but usually have checks.
            # Checking checks on app_commands is harder without executing.
            # For now, we assume if it's strictly an app_command, we show it unless we can detect admin.
            # Most commands in this bot are Hybrid, so get_commands() covers 99%.
            # commands/rss.py uses @app_commands.command inside a Cog? No, usually @commands.hybrid_command
            # Let's rely on get_commands() for now as it covers Hybrid.

            if visible_commands:
                if category not in help_data:
                    help_data[category] = []
                help_data[category].extend(visible_commands)

        # Handle Uncategorized (Commands not in any Cog)
        # uncat = [c for c in self.bot.commands if not c.cog]
        # visible_uncat = []
        # for cmd in uncat:
        #     if not cmd.hidden:
        #          try:
        #              if await cmd.can_run(ctx):
        #                  visible_uncat.append(cmd)
        #          except: pass

        # if visible_uncat:
        #     if "Other" not in help_data: help_data["Other"] = []
        #     help_data["Other"].extend(visible_uncat)

        return help_data

    @app_commands.command(name="help", description="Show the Cthulhu Bot help menu.")
    async def help_command(self, interaction: discord.Interaction):
        """
        Shows the interactive help menu.
        """
        # Create a Context for permission checking
        # We need a Message to create a Context, but for interaction we use from_interaction
        ctx = await self.bot.get_context(interaction)

        help_data = await self.generate_help_data(ctx)

        if not help_data:
            await interaction.response.send_message("No commands available for you.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🐙 Cthulhu Bot Help",
            description="Greetings, Investigator.\nThe stars align for you to seek knowledge. Consult the archives below to uncover the secrets of this bot.",
            color=discord.Color.teal()
        )
        embed.set_footer(text="Only commands available to you are shown.")

        view = HelpView(help_data, interaction.user)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Help(bot))
