import discord
from discord.ext import commands
from discord import app_commands
from loadnsave import smartreact_load, smartreact_save
import io

class smartreaction(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    group = app_commands.Group(name="smartreaction", description="Manage smart reactions", guild_only=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return  # Don't react to the bot's own messages

        if not message.guild:
            return

        server_id = str(message.guild.id)
        reactions = await smartreact_load()

        if server_id in reactions:
            for word, emoji in reactions[server_id].items():
                if word.lower() in message.content.lower():
                    try:
                        await message.add_reaction(emoji)
                    except discord.HTTPException:
                        pass # Ignore if emoji is invalid or bot has no permission

    @group.command(name="add", description="Add a new word-emoji pair for smart reactions.")
    @app_commands.describe(word="The word to trigger the reaction", emoji="The emoji to react with")
    @app_commands.checks.has_permissions(administrator=True)
    async def add(self, interaction: discord.Interaction, word: str, emoji: str):
        await interaction.response.defer(ephemeral=True)

        server_id = str(interaction.guild.id)
        reactions = await smartreact_load()

        if server_id not in reactions:
            reactions[server_id] = {}

        word_lower = word.lower()
        reactions[server_id][word_lower] = emoji
        await smartreact_save(reactions)

        await interaction.followup.send(f"Added reaction: '{word_lower}' -> {emoji}")

    @group.command(name="remove", description="Remove a smart reaction.")
    @app_commands.describe(word="The word to remove the reaction for", emoji="The emoji that was associated")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove(self, interaction: discord.Interaction, word: str, emoji: str):
        await interaction.response.defer(ephemeral=True)
        
        server_id = str(interaction.guild.id)
        reactions = await smartreact_load()

        if server_id in reactions:
            word_lower = word.lower()
            if word_lower in reactions[server_id]:
                # Check if emoji matches
                current_emoji = reactions[server_id][word_lower]
                if current_emoji != emoji:
                     await interaction.followup.send(f"The stored emoji for '{word_lower}' is {current_emoji}, but you provided {emoji}. Removal aborted.")
                     return

                removed_emoji = reactions[server_id].pop(word_lower)
                await smartreact_save(reactions)
                await interaction.followup.send(f"Removed reaction: '{word_lower}' -> {removed_emoji}")
            else:
                await interaction.followup.send(f"No reaction found for the word: '{word_lower}'")
        else:
            await interaction.followup.send("No reactions set up for this server.")

    @group.command(name="list", description="List all smart reactions for the server.")
    async def list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        server_id = str(interaction.guild.id)
        reactions = await smartreact_load()

        if server_id in reactions:
            reaction_list = reactions[server_id]
            if reaction_list:
                response = "Smart Reactions for this server:\n"
                for word, emoji in reaction_list.items():
                    response += f"'{word}' -> {emoji}\n"

                if len(response) > 2000:
                    f = io.BytesIO(response.encode('utf-8'))
                    await interaction.followup.send("Reaction list is too long, sent as file.", file=discord.File(f, "reactions.txt"))
                else:
                    await interaction.followup.send(response)
            else:
                await interaction.followup.send("No smart reactions set up for this server.")
        else:
            await interaction.followup.send("No smart reactions set up for this server.")

async def setup(bot):
    await bot.add_cog(smartreaction(bot))
