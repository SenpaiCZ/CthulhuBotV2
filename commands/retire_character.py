import discord
from discord.ext import commands
from loadnsave import load_player_stats, save_player_stats, load_retired_characters_data, save_retired_characters_data
import asyncio

class CharacterManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def retire(self, ctx):
        server_id = str(ctx.guild.id)
        player_id = str(ctx.author.id)
        player_stats = await load_player_stats()

        if server_id not in player_stats or player_id not in player_stats[server_id]:
            await ctx.send("You do not have an active character to retire.")
            return

        confirmation_message = await ctx.send("Are you sure you want to retire your character? Type 'yes' to confirm.")

        def check(m):
            return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id and m.content.lower() == "yes"

        try:
            await self.bot.wait_for("message", timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Retirement cancelled due to timeout.")
            return

        character_data = player_stats[server_id].pop(player_id)
        retired_characters = await load_retired_characters_data()

        if player_id not in retired_characters:
            retired_characters[player_id] = []

        retired_characters[player_id].append(character_data)
        await save_retired_characters_data(retired_characters)
        await save_player_stats(player_stats)

        await ctx.send("Your character has been retired successfully. You can now create a new character.")
      
    @commands.command()
    async def unretire(self, ctx):
        server_id = str(ctx.guild.id)
        player_id = str(ctx.author.id)
        player_stats = await load_player_stats()
    
        # Kontrola, zda hráč má aktivní postavu
        if server_id in player_stats and player_id in player_stats[server_id]:
            await ctx.send("You already have an active character. Please retire your current character first.")
            return
    
        retired_characters = await load_retired_characters_data()
        if player_id not in retired_characters or not retired_characters[player_id]:
            await ctx.send("You do not have any retired characters.")
            return
    
        # Zobrazení seznamu postav v důchodu
        characters_list = "\n".join([f"{i+1}. {char['NAME']}" for i, char in enumerate(retired_characters[player_id])])
        await ctx.send("Please select a character to unretire:\n" + characters_list)
    
        # Čekání na výběr hráče
        def check(m):
            return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id and m.content.isdigit()
    
        try:
            message = await self.bot.wait_for("message", timeout=60.0, check=check)
            selected_index = int(message.content) - 1
    
            if selected_index >= 0 and selected_index < len(retired_characters[player_id]):
                selected_character = retired_characters[player_id].pop(selected_index)
                player_stats.setdefault(server_id, {})[player_id] = selected_character
                await save_retired_characters_data(retired_characters)
                await save_player_stats(player_stats)
                await ctx.send(f"Character '{selected_character['NAME']}' has been unretired and is now active.")
            else:
                await ctx.send("Invalid selection.")
        except asyncio.TimeoutError:
            await ctx.send("No selection made.")
          
async def setup(bot):
    await bot.add_cog(CharacterManagement(bot))
