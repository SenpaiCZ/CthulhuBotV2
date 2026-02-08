import discord
from discord.ext import commands
import asyncio

class CustomHelpCommand(commands.DefaultHelpCommand):
    def __init__(self):
        super().__init__()
        self.per_page = 20 # Number of commands to display per page

    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot

        # Group commands by cog
        cogs = {
            "Character creation": [
                "newinvestigator",
                "mychar",
                "stat",
                "rename",
                "renameskill",
                "deleteinvestigator",
                "addbackstory",
                "updatebackstory",
                "removebackstory",
                "generatebackstory",
                "retire",
                "unretire"

            ],
            "Rolling die and session management": [
                "newroll",
                "roll",
                "newbonusroll",
                "newpenalityroll",
                "showluck",
                "startsession",
                "showsession",
                "wipesession",

            ],
            "For Keeper": [
                "changeluck",
                "occupationinfo",
                "skillinfo",
                "createnpc",
                "randomname",
                "macguffin",
                "loot",
                "archetypeinfo",
                "firearms",
                "inventions",
                "talents",
                "years",
                "madness",
                "madnessAlone",
                "insaneTalents",
                "phobia",
                "mania",
                "poisions",
            ],
            "Bot functions":[
                "autoroomkick",
                "autoroomlock",
                "autoroomunlock",
                "reportbug",
                "repeatafterme",
                "uptime"
            ],
            "Admin": [
                "autoroomset",
                "changeprefix",
                "ping",
                "repeatafterme",
                "addreaction",
                "removereaction",
                "listreactions",
                "deleter",
                "autodeleter",
                "stopdeleter",
                "rss"
            ],
            "NIU": [
            ],
        }

        # Add commands not assigned to a specific page to "Other"
        for cog, command_list in mapping.items():
            cog_name = getattr(cog, "qualified_name", "No Category")
            if cog_name not in cogs:
                pass
                #cogs["Other"].extend([command.name for command in command_list if not command.hidden])

        # Split commands into pages
        pages = []
        for page_name, cog_commands in cogs.items():
            commands = []
            for command_name in cog_commands:
                command = bot.get_command(command_name)
                if command:
                    commands.append(command)
                    if len(commands) >= self.per_page:
                        pages.append((page_name, commands))
                        commands = []
            if commands:
                pages.append((page_name, commands))

        # Display pages (same code as before)
        current_page = 0
        embed = self.create_page_embed(current_page, pages)
        message = await ctx.send(embed=embed)
        for emoji in ["⬅️", "➡️"]:
            await message.add_reaction(emoji)

        def check(reaction, user):
            return user == ctx.author and reaction.message.id == message.id and reaction.emoji in ["⬅️", "➡️"]

        while True:
            try:
                reaction, user = await bot.wait_for("reaction_add", timeout=60, check=check)
                if reaction.emoji == "⬅️":
                    current_page = max(0, current_page - 1)
                elif reaction.emoji == "➡️":
                    current_page = min(len(pages) - 1, current_page + 1)
                embed = self.create_page_embed(current_page, pages)
                await message.edit(embed=embed)
                await message.remove_reaction(reaction.emoji, ctx.author)  # Remove the user's reaction
            except asyncio.TimeoutError:
                await message.clear_reactions()
                break

    def create_page_embed(self, page_num, pages):
        page_name, page = pages[page_num]
        embed = discord.Embed(
            title=f"<:coc:1150679516650418216>Help<:coc:1150679516650418216> - {page_name}",
            description="This is **UNOFFICIAL** bot!\nIt's **not** associated with Chaosium Inc!\nTo be able to play **Call of Cthulhu** you will need [Call of Cthulhu Keeper Rulebook](https://www.chaosium.com/call-of-cthulhu-keeper-rulebook-hardcover/), [Call of Cthulhu Starter Set](https://www.chaosium.com/call-of-cthulhu-starter-set/) or [Pulp Cthulhu](https://www.chaosium.com/pulp-cthulhu-hardcover/) published by [Chaosium.inc](https://www.chaosium.com/)\n\nHere are the available commands, [p] is your prefix:",
            color=0x00ff00  # You can set a custom color for the embed
        )
        for command in page:
            signature = self.get_command_signature(command)
            description = command.help or "No description available"
            embed.add_field(name=signature, value=description, inline=False)
        embed.set_footer(text=f"Page {page_num + 1}/{len(pages)}")
        return embed
