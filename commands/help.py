import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select
import traceback

# Mapping of Command Names to Categories
COMMAND_CATEGORIES = {
    "Player": [
        "newinvestigator", "mycharacter", "stat", "generatebackstory",
        "addbackstory", "removebackstory", "updatebackstory", "roll",
        "rename", "renameskill", "addskill", "printcharacter", "session",
        "retire", "unretire", "deleteinvestigator"
    ],
    "Codex": [
        "grimoire", "monster", "deity", "spell", "archetype", "talent",
        "insane", "poison", "skill", "occupation", "invention", "year",
        "weapon"
    ],
    "Keeper": [
        "loot", "mania", "phobia", "madness", "madnessalone", "handout",
        "macguffin", "randomname", "randomnpc", "chase"
    ],
    "Music": [
        "play", "skip", "stop", "volume", "loop", "queue", "nowplaying"
    ],
    "Other": [
        "karma", "leaderboard", "giveaway", "polls", "remind",
        "reportbug", "uptime"
    ],
    "Admin": [
        "enroll", "autoroom", "reactionrole", "gameroles", "rss",
        "autodeleter", "setupkarma", "purge"
    ]
}

COC_EMOJI_ID = 1472309439410344040

class HelpSelect(Select):
    def __init__(self, help_data):
        self.help_data = help_data
        options = []

        # Sort categories to ensure consistent order
        sorted_categories = sorted(help_data.keys())

        # Define category emojis
        # Use PartialEmoji for custom emojis
        coc_emoji = discord.PartialEmoji(name='coc', id=COC_EMOJI_ID)

        emoji_map = {
            "Player": coc_emoji,
            "Codex": coc_emoji,
            "Keeper": coc_emoji,
            "Music": "🎵",
            "Other": "📁",
            "Admin": "🛠️"
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
        # Defer immediately to prevent timeout on button click processing if needed,
        # though usually fast enough. But just in case.
        # Actually, editing a message doesn't need defer if response is fast,
        # but let's be safe if generating the embed is slow.
        # For Select callback, we use response.edit_message usually.

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

        # Sort commands alphabetically
        commands_list.sort(key=lambda c: c.name)

        if len(commands_list) > 25:
             # Just list names if too many
             command_names = []
             for cmd in commands_list:
                 name = cmd.name
                 if isinstance(cmd, (app_commands.Command, app_commands.Group)):
                     name = f"/{name}"
                 else:
                     # Hybrid or Text
                     name = f"/{name}" # Assume slash context mostly
                 command_names.append(f"`{name}`")

             embed.description += "\n" + ", ".join(command_names)
        else:
            for cmd in commands_list:
                name = cmd.name
                desc = cmd.description or "No description."

                # Check for hybrid commands which have help attribute
                if hasattr(cmd, 'help') and cmd.help:
                    desc = cmd.help

                # Truncate desc
                if len(desc) > 100: desc = desc[:97] + "..."

                prefix = "/"
                # Check if it's strictly a text command (unlikely given migration)
                if isinstance(cmd, commands.Command) and not isinstance(cmd, commands.HybridCommand):
                    prefix = "!"

                embed.add_field(name=f"{prefix}{name}", value=desc, inline=False)

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
        """
        help_data = {}

        # Iterate defined categories
        for category, cmd_names in COMMAND_CATEGORIES.items():
            category_commands = []

            for name in cmd_names:
                try:
                    # 1. Check for Slash Command (App Command)
                    # App commands are in self.bot.tree.get_command(name)
                    # Note: get_command only gets top-level commands/groups

                    app_cmd = self.bot.tree.get_command(name)

                    # 2. Check for Text/Hybrid Command
                    # Hybrid commands are also in bot.commands
                    text_cmd = self.bot.get_command(name)

                    cmd_obj = None

                    if app_cmd:
                        cmd_obj = app_cmd
                    elif text_cmd:
                        # Only if not hidden
                        if not text_cmd.hidden:
                            cmd_obj = text_cmd

                    if cmd_obj:
                        # Check permissions if possible
                        # For slash commands, checks are async and complex (interaction based)
                        # For text commands, await cmd.can_run(ctx)

                        can_run = True
                        if isinstance(cmd_obj, commands.Command):
                            try:
                                can_run = await cmd_obj.can_run(ctx)
                            except:
                                can_run = False

                        # For app commands, we can't easily check 'can_run' without an interaction
                        # We'll assume visible unless it's an owner command or guild only in DM
                        # But listing them is usually fine for help menu

                        if can_run:
                            category_commands.append(cmd_obj)

                except Exception as e:
                    print(f"Error processing command '{name}' for help menu: {e}")
                    traceback.print_exc()
                    continue

            if category_commands:
                help_data[category] = category_commands

        return help_data

    @app_commands.command(name="help", description="Show the Cthulhu Bot help menu.")
    async def help_command(self, interaction: discord.Interaction):
        """
        Shows the interactive help menu.
        """
        # Defer the interaction immediately to prevent timeout
        await interaction.response.defer(ephemeral=True)

        try:
            # Create a Context for permission checking (hybrid commands need it)
            ctx = await self.bot.get_context(interaction)

            help_data = await self.generate_help_data(ctx)

            if not help_data:
                await interaction.followup.send("No commands available for you.")
                return

            embed = discord.Embed(
                title="🐙 Cthulhu Bot Help",
                description="Greetings, Investigator.\nThe stars align for you to seek knowledge. Consult the archives below to uncover the secrets of this bot.",
                color=discord.Color.teal()
            )
            embed.set_footer(text="Only commands available to you are shown.")

            view = HelpView(help_data, interaction.user)
            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            print(f"Error generating help menu: {e}")
            traceback.print_exc()
            await interaction.followup.send("An error occurred while generating the help menu.")

async def setup(bot):
    await bot.add_cog(Help(bot))
