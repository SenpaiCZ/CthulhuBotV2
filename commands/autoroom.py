import discord
from discord.ext import commands
from discord import app_commands
from loadnsave import autoroom_load, autoroom_save

class Autoroom(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

  # Create a slash command group
  autoroom_group = app_commands.Group(name="autoroom", description="Manage auto-rooms")

  @autoroom_group.command(name="setup", description="Configure Auto Room source channel and target category.")
  @app_commands.describe(channel="Source Voice Channel", category="Target Category")
  @app_commands.checks.has_permissions(administrator=True)
  async def setup(self, interaction: discord.Interaction, channel: discord.VoiceChannel, category: discord.CategoryChannel):
      """Configures the source voice channel and target category for Auto Rooms."""
      await interaction.response.defer()

      server_id = str(interaction.guild.id)
      autorooms = await autoroom_load()
      if server_id not in autorooms:
          autorooms[server_id] = {}

      autorooms[server_id]["channel_id"] = channel.id
      autorooms[server_id]["category_id"] = category.id
      await autoroom_save(autorooms)

      await interaction.followup.send(
          f"**Auto Room Setup Complete!**\n"
          f"Source Channel: {channel.mention}\n"
          f"Target Category: {category.mention}"
      )

  @autoroom_group.command(name="kick", description="Kick a user from your auto-room.")
  @app_commands.describe(member="The user to kick")
  async def kick(self, interaction: discord.Interaction, member: discord.Member):
      """Remove a user from your auto-room."""
      server_id = str(interaction.guild.id)
      user_id = str(interaction.user.id)
      autorooms = await autoroom_load()

      if server_id not in autorooms:
          await interaction.response.send_message("The autoroom feature is not set up for this server.", ephemeral=True)
          return

      if user_id not in autorooms[server_id]:
          await interaction.response.send_message("You are not the owner of an autoroom in this server.", ephemeral=True)
          return

      user_channel_id = autorooms[server_id][user_id]

      if not interaction.user.voice or interaction.user.voice.channel.id != user_channel_id:
           await interaction.response.send_message("You must be in your own autoroom to use this command.", ephemeral=True)
           return

      if member.voice and member.voice.channel and member.voice.channel.id == user_channel_id:
          try:
              await member.move_to(None)  # Disconnect
              await interaction.response.send_message(f"{member.display_name} has been kicked from your room.")
          except discord.errors.Forbidden:
              await interaction.response.send_message("I don't have permission to move that user.", ephemeral=True)
      else:
          await interaction.response.send_message("That user is not in your room.", ephemeral=True)

  @autoroom_group.command(name="lock", description="Lock your auto-room so no one can join.")
  async def lock(self, interaction: discord.Interaction):
      """Prevents anyone from joining your auto-room."""
      server_id = str(interaction.guild.id)
      user_id = str(interaction.user.id)
      autorooms = await autoroom_load()

      if server_id not in autorooms:
          await interaction.response.send_message("The autoroom feature is not set up for this server.", ephemeral=True)
          return

      if user_id not in autorooms[server_id]:
          await interaction.response.send_message("You are not the owner of an autoroom in this server.", ephemeral=True)
          return

      user_channel_id = autorooms[server_id][user_id]

      if interaction.user.voice and interaction.user.voice.channel.id == user_channel_id:
          user_channel = interaction.user.voice.channel
          await user_channel.set_permissions(interaction.guild.default_role, connect=False)
          await interaction.response.send_message("Your room has been locked. No one can join now.")
      else:
          await interaction.response.send_message("You need to be in your autoroom to lock it.", ephemeral=True)

  @autoroom_group.command(name="unlock", description="Unlock your auto-room so anyone can join.")
  async def unlock(self, interaction: discord.Interaction):
      """Opens your room so anyone can join in."""
      server_id = str(interaction.guild.id)
      user_id = str(interaction.user.id)
      autorooms = await autoroom_load()

      if server_id not in autorooms:
          await interaction.response.send_message("The autoroom feature is not set up for this server.", ephemeral=True)
          return

      if user_id not in autorooms[server_id]:
          await interaction.response.send_message("You are not the owner of an autoroom in this server.", ephemeral=True)
          return

      user_channel_id = autorooms[server_id][user_id]

      if interaction.user.voice and interaction.user.voice.channel.id == user_channel_id:
          user_channel = interaction.user.voice.channel
          await user_channel.set_permissions(interaction.guild.default_role, connect=True)
          await interaction.response.send_message("Your room has been unlocked. Anyone can join now.")
      else:
          await interaction.response.send_message("You need to be in your autoroom to unlock it.", ephemeral=True)

  @commands.Cog.listener()
  async def on_voice_state_update(self, member, before, after):
      server_id = str(member.guild.id)
      user_id = str(member.id)
      autorooms = await autoroom_load()
  
      if server_id not in autorooms:
          return
  
      # Trigger if user joins the configured channel (even if switching from another)
      target_channel_id = autorooms[server_id].get("channel_id")

      if after.channel is not None and after.channel.id == target_channel_id:
          # Check if they just moved within the same channel (mute/deaf update)
          if before.channel and before.channel.id == target_channel_id:
               return

          # Create a new voice channel in the specified category
          category_id = autorooms[server_id].get("category_id")
          if category_id:
              guild = member.guild
              category = guild.get_channel(category_id)
  
              if category and isinstance(category, discord.CategoryChannel):
                  # Ensure permissions are synced with category (public by default usually)
                  overwrites = category.overwrites
                  new_channel_name = f"{member.display_name}'s Channel"

                  try:
                      new_channel = await guild.create_voice_channel(new_channel_name, category=category, overwrites=overwrites)
                      autorooms[server_id][user_id] = new_channel.id
                      await member.move_to(new_channel)
                      await autoroom_save(autorooms)
                  except Exception as e:
                      print(f"Error creating autoroom: {e}")
  
      # Check if the user left their own created channel
      if (
          user_id in autorooms[server_id]
          and before.channel
          and before.channel.id == autorooms[server_id][user_id]  # Compare channel IDs
          and (after.channel is None or after.channel.id != before.channel.id)
      ):
          # Get the user's created channel ID and delete it
          created_channel_id = autorooms[server_id][user_id]
          created_channel = member.guild.get_channel(created_channel_id)
  
          if created_channel:
              try:
                  await created_channel.delete()
              except:
                  pass # Already deleted?
              del autorooms[server_id][user_id]
              await autoroom_save(autorooms)

  @commands.Cog.listener()
  async def on_ready(self):
      for guild in self.bot.guilds:
          server_id = str(guild.id)
          autorooms = await autoroom_load()
  
          if server_id not in autorooms:
              continue
  
          # Iterate over a copy of items to allow modification during iteration
          for user_id, channel_id in list(autorooms[server_id].items()):
              # Skip the configuration keys
              if user_id in ["channel_id", "category_id"]:
                  continue

              # Ensure channel_id is int
              if isinstance(channel_id, int):
                  # Check if the user's channel exists and is empty
                  user_channel = guild.get_channel(channel_id)

                  if user_channel:
                      if len(user_channel.members) == 0:
                          try:
                              await user_channel.delete()
                          except:
                              pass
                          del autorooms[server_id][user_id]
                  else:
                      # Channel doesn't exist anymore, cleanup
                      del autorooms[server_id][user_id]
  
          await autoroom_save(autorooms)

async def setup(bot):
  await bot.add_cog(Autoroom(bot))
