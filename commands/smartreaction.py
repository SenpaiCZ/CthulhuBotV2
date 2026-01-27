import discord
from discord.ext import commands
from loadnsave import smartreact_load, smartreact_save


class smartreaction(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    
  @commands.Cog.listener()
  async def on_message(self, message):
      if message.author == self.bot.user:
          return  # Don't react to the bot's own messages
  
      server_id = str(message.guild.id)
      reactions = await smartreact_load()  # Assuming you have a function for loading reactions
  
      if server_id in reactions:
          for word, emoji in reactions[server_id].items():
              if word.lower() in message.content.lower():
                  await message.add_reaction(emoji)

  @commands.command()
  async def addreaction(self, ctx, word=None, emoji=None):
      """
      `[p]addreaction word emoji` - Add a new word-emoji pair for smart reactions.
      """
      if ctx.author == ctx.guild.owner:
        await ctx.send("This command is limited for server owner only.")
        return
      if not isinstance(ctx.channel, discord.TextChannel):
        await ctx.send("This command is not allowed in DMs.")
        return
      # Input validation
      if not word or not emoji:
          await ctx.send("Please provide both a word and an emoji.")
          return
      server_id = str(ctx.guild.id)
      reactions = await smartreact_load()
  
      if server_id not in reactions:
          reactions[server_id] = {}
      word = word.lower()
  
      # Store the word and emoji in the server-specific list
      reactions[server_id][word] = emoji
      # Save the updated reactions to a JSON file (implement this part)
      await smartreact_save(reactions)
  
      await ctx.send(f"Added reaction: '{word}' -> {emoji}")
    
  @commands.command()
  async def removereaction(self, ctx, word, emoji):
      """
      `[p]removereaction word emoji` - Remove a smart reaction associated with a specific word and emoji.
      """
      if ctx.author == ctx.guild.owner:
        await ctx.send("This command is limited for server owner only.")
        return
      if not isinstance(ctx.channel, discord.TextChannel):
        await ctx.send("This command is not allowed in DMs.")
        return
      # Get the server's reactions (assuming you have a function to load reactions)
      server_id = str(ctx.guild.id)
      reactions = await smartreact_load()
      if server_id in reactions:
          word = word.lower()
  
          if word in reactions[server_id]:
              if reactions[server_id][word] == emoji:
                  # Remove the reaction associated with the specified word and emoji
                  removed_emoji = reactions[server_id].pop(word)
  
                  # Save the updated reactions (implement this part)
                  await smartreact_save(reactions)
  
                  await ctx.send(f"Removed reaction: '{word}' -> {removed_emoji}")
              else:
                  await ctx.send(f"The provided emoji does not match the existing reaction for '{word}'.")
          else:
              await ctx.send(f"No reaction found for the word: '{word}'")
      else:
          await ctx.send("No reactions set up for this server.")
  
  @commands.command()
  async def listreactions(self, ctx):
      """
      `[p]listreactions` - List all smart reactions for the server.
      """
      if not isinstance(ctx.channel, discord.TextChannel):
        await ctx.send("This command is not allowed in DMs.")
        return
      # Get the server's reactions (assuming you have a function to load reactions)
      server_id = str(ctx.guild.id)
      reactions = await smartreact_load()
  
      if server_id in reactions:
          reaction_list = reactions[server_id]
  
          if reaction_list:
              response = "Smart Reactions for this server:\n"
              for word, emoji in reaction_list.items():
                  response += f"'{word}' -> {emoji}\n"
  
              await ctx.send(response)
          else:
              await ctx.send("No smart reactions set up for this server.")
      else:
          await ctx.send("No smart reactions set up for this server.")
        
async def setup(bot):
  await bot.add_cog(smartreaction(bot))
