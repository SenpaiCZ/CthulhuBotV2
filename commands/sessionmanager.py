import discord, asyncio, random
from discord.ext import commands
from loadnsave import load_session_data, save_session_data, save_player_stats, load_player_stats
from emojis import get_stat_emoji


          
class sessionmanager(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.command()
  async def startsession(self, ctx):
      """
      `[p]startsession` - start recording you successful rolls for character development.
      """
      user_id = str(ctx.author.id)
      session_data = await load_session_data()
  
      if user_id not in session_data:
          session_data[user_id] = []
  
      await save_session_data(session_data)
      await ctx.send(f"Session started for {ctx.author.display_name}!")
    
  @commands.command()
  async def autosession(self, ctx):
      """
      `[p]autosession` - Automatically upgrade player's stats based on session rolls and asks for session wipe.
      """
      user_id = str(ctx.author.id)
      session_data = await load_session_data()
      player_stats = await load_player_stats()
      server_id = str(ctx.guild.id)

      if user_id not in session_data or user_id not in player_stats[server_id]:
          await ctx.send(f"No active session or character found for {ctx.author.display_name}.")
          return

      user_session = session_data[user_id]
      excluded_skills = ["HP", "MP", "STR", "DEX", "CON", "INT", "POW", "EDU", "SIZ", "APP", "SAN", "LUCK", "Credit Rating"]
      filtered_session = [entry for entry in user_session if not any(skill in entry for skill in excluded_skills)]

      if not filtered_session:
          await ctx.send("No skills to upgrade in this session.")
          return

      embed = discord.Embed(
          title=f"Session upgrade results for {ctx.author.display_name}",
          color=discord.Color.blue()
      )

      for skill in filtered_session:
          current_value = player_stats[server_id][user_id].get(skill, 0)
          roll = random.randint(1, 100)
          upgrade_value = 0

          if roll > current_value:
              upgrade_value = random.randint(1, 10)
              player_stats[server_id][user_id][skill] = current_value + upgrade_value

          emoji = get_stat_emoji(skill)
          embed.add_field(name=f"{skill} {emoji}", value=f"Current: {current_value}, Roll: {roll}, Upgrade: +{upgrade_value}", inline=False)

      await save_player_stats(player_stats)
      await ctx.send(embed=embed)

      # Dotaz na vymazání session dat
      confirmation_message = await ctx.send("Do you want to wipe your session data?")
      await confirmation_message.add_reaction("✅")
      await confirmation_message.add_reaction("❌")

      def check(reaction, user):
          return user == ctx.author and str(reaction.emoji) in ["✅", "❌"]

      try:
          reaction, _ = await self.bot.wait_for("reaction_add", timeout=30, check=check)
          if str(reaction.emoji) == "✅":
              del session_data[user_id]
              await save_session_data(session_data)
              await ctx.send("Session data wiped successfully.")
          else:
              await ctx.send("Session data not wiped.")
      except asyncio.TimeoutError:
          await ctx.send("You took too long to react. Session data not wiped.")
      
  @commands.command()
  async def showsession(self, ctx, member: discord.Member = None):
      """
      `[p]showsession [@player]` - Show list of successful rolls for character development.
      If no @player is provided, shows your session.
      """
      target_member = member or ctx.author
      user_id = str(target_member.id)
      session_data = await load_session_data()
      
      if user_id in session_data:
          user_session = session_data[user_id]
          
          # List of skills to exclude
          excluded_skills = ["STR", "DEX", "CON", "INT", "POW", "EDU", "SIZ", "APP", "SAN", "LUCK","Credit Rating"]
          
          # Filter out excluded skills from the session data
          filtered_session = [entry for entry in user_session if not any(skill in entry for skill in excluded_skills)]
          
          if filtered_session:
              # Create an embed
              embed = discord.Embed(
                  title=f"Upgradable skills for {target_member}",
                  color=discord.Color.green()  # You can customize the color
              )
              
              
              # Loop through filtered session entries and add them as fields
              for skill in filtered_session:
                  emoji = get_stat_emoji(skill)
                  embed.add_field(name=f"{emoji} {skill}", value="", inline=False)
                  # You can customize the value as needed
            
              embed.add_field(name="Upgrading skills", value="First roll for a stat with `d skill`. If you fail :x:, you can upgrade skill by :game_die:1D10. You can also use autosession", inline=False)    
              await ctx.send(embed=embed)
          else:
              await ctx.send("No session data to display.")
      else:
          await ctx.send("No active session for this user.")


  
  @commands.command()
  async def wipesession(self, ctx):
      """
      `[p]wipesession` - Delete your data from this session. You will be asked if you are sure.
      """
      user_id = str(ctx.author.id)
      session_data = await load_session_data()
  
      if user_id in session_data:
          confirmation_message = await ctx.send("Are you sure you want to wipe your session data?")
          await confirmation_message.add_reaction("✅")  # Add checkmark emoji
          await confirmation_message.add_reaction("❌")  # Add X emoji
  
          def check(reaction, user):
              return user == ctx.author and str(reaction.emoji) in ["✅", "❌"]
  
          try:
              reaction, _ = await self.bot.wait_for("reaction_add", timeout=30, check=check)
              if str(reaction.emoji) == "✅":
                  del session_data[user_id]
                  await save_session_data(session_data)
                  await ctx.send("Session data wiped successfully.")
              else:
                  await ctx.send("Session data not wiped.")
          except asyncio.TimeoutError:
              await ctx.send("You took too long to react. Session data not wiped.")
      else:
          await ctx.send("No active session for this user.")
  
async def setup(bot):
  await bot.add_cog(sessionmanager(bot))
