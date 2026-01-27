import discord
from discord.ext import commands, tasks
from loadnsave import autoroom_load, autoroom_save

class autoroom(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

  @commands.command()
  async def autoroomset(self, ctx, channel_id: int, category_id: int):
    """
    `[p]autoroomset entry_channel category_channel` - This command allows users to create personalized voice channels in the specified category when they join the designated entry channel.
    
    Use this command to set up an automatic voice channel system.
    entry_channel is the channel where users join to create their own voice channels.
    category_channel is the category where new voice channels will be created for users.
    
    `[p]autoroomset 123456789123 123456789123`
    """
    if ctx.author != ctx.guild.owner:
        await ctx.send("This command is limited to the server owner only.")
        return

    if not isinstance(ctx.channel, discord.TextChannel):
      await ctx.send("This command is not allowed in DMs.")
      return

    server_id = str(ctx.guild.id)
    autorooms = await autoroom_load()

    if server_id not in autorooms:
        autorooms[server_id] = {}

    autorooms[server_id]["channel_id"] = channel_id
    autorooms[server_id]["category_id"] = category_id
    await ctx.send(f'Successfully set the voice channel (ID: {channel_id}) in category (ID: {category_id}).')

    await autoroom_save(autorooms)

  @commands.Cog.listener()
  async def on_voice_state_update(self, member, before, after):
      server_id = str(member.guild.id)
      user_id = str(member.id)
      autorooms = await autoroom_load()
  
      if server_id not in autorooms:
          return
  
      if before.channel is None and after.channel is not None and after.channel.id == autorooms[server_id].get("channel_id"):
          # Create a new voice channel in the specified category
          category_id = autorooms[server_id].get("category_id")
          if category_id:
              guild = member.guild
              category = guild.get_channel(category_id)
  
              if category and isinstance(category, discord.CategoryChannel):
                  new_channel_name = f"{member.display_name}'s Channel"
                  new_channel = await guild.create_voice_channel(new_channel_name, category=category)
                  autorooms[server_id][user_id] = new_channel.id
                  await member.move_to(new_channel)
                  await autoroom_save(autorooms)
  
      # Check if the user left their own created channel
      if (
          user_id in autorooms[server_id]
          and before.channel.id == autorooms[server_id][user_id]  # Compare channel IDs
          and after.channel is None
      ):
          # Get the user's created channel ID and delete it
          created_channel_id = autorooms[server_id][user_id]
          created_channel = member.guild.get_channel(created_channel_id)
  
          if created_channel:
              await created_channel.delete()
              del autorooms[server_id][user_id]
              await autoroom_save(autorooms)

  @commands.Cog.listener()
  async def on_ready(self):
      for guild in self.bot.guilds:
          server_id = str(guild.id)
          autorooms = await autoroom_load()
  
          if server_id not in autorooms:
              continue
  
          channel_id_to_keep = autorooms[server_id].get("channel_id")
          category_id_to_keep = autorooms[server_id].get("category_id")
  
          for user_id, channel_id in autorooms[server_id].items():
              # Skip the channel and category you want to keep
              if channel_id == channel_id_to_keep or channel_id == category_id_to_keep:
                  continue
  
              # Check if the user's channel exists and is empty
              user_channel = guild.get_channel(channel_id)
  
              if user_channel and len(user_channel.members) == 0:
                  await user_channel.delete()
                  del autorooms[server_id][user_id]
  
          await autoroom_save(autorooms)
        
  @commands.command()
  async def autoroomkick(self, ctx, member: discord.Member):
      """
      `[p]autoroomkick @ user` - Remove user from your autoroom
      """
      server_id = str(ctx.guild.id)
      user_id = str(ctx.author.id)
      autorooms = await autoroom_load()

      if server_id not in autorooms:
          await ctx.send("The autoroom feature is not set up for this server.")
          return

      if user_id not in autorooms[server_id]:
          await ctx.send("You are not the owner of an autoroom in this server.")
          return

      user_channel_id = autorooms[server_id][user_id]

      if user_channel_id == ctx.voice_client.channel.id:
          # The user who issued the command is in their own room
          try:
              member_channel = ctx.voice_client.channel
              await member.move_to(None)  # Disconnect the mentioned user from the room
              await ctx.send(f"{member.display_name} has been kicked from your room.")
          except discord.errors.Forbidden:
              await ctx.send("I don't have permission to move that user.")
      else:
          await ctx.send("You can only kick users from your own room.")  

  @commands.command()
  async def autoroomlock(self, ctx):
    
      """
      `[p]autoroomlock` - Prevents anyone from joining your autorom
      """

      server_id = str(ctx.guild.id)
      user_id = str(ctx.author.id)
      autorooms = await autoroom_load()

      if server_id not in autorooms:
          await ctx.send("The autoroom feature is not set up for this server.")
          return

      if user_id not in autorooms[server_id]:
          await ctx.send("You are not the owner of an autoroom in this server.")
          return

      user_channel_id = autorooms[server_id][user_id]

      if user_channel_id == ctx.author.voice.channel.id:
          # The user who issued the command is in their own room
          user_channel = ctx.author.voice.channel
          await user_channel.set_permissions(ctx.guild.default_role, connect=False)
          await ctx.send("Your room has been locked. No one can join now.")
      else:
          await ctx.send("You can only lock your own room.")

  @commands.command()
  async def autoroomunlock(self, ctx):

      """
      `[p]autoroomunlock` - Opens your room so anyone can join in
      """
    
      server_id = str(ctx.guild.id)
      user_id = str(ctx.author.id)
      autorooms = await autoroom_load()

      if server_id not in autorooms:
          await ctx.send("The autoroom feature is not set up for this server.")
          return

      if user_id not in autorooms[server_id]:
          await ctx.send("You are not the owner of an autoroom in this server.")
          return

      user_channel_id = autorooms[server_id][user_id]

      if user_channel_id == ctx.author.voice.channel.id:
          # The user who issued the command is in their own room
          user_channel = ctx.author.voice.channel
          await user_channel.set_permissions(ctx.guild.default_role, connect=True)
          await ctx.send("Your room has been unlocked. Anyone can join now.")
      else:
          await ctx.send("You can only unlock your own room.")



async def setup(bot):
  await bot.add_cog(autoroom(bot))
