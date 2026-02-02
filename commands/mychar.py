import discord, asyncio
from discord.ext import commands
from loadnsave import load_player_stats, save_player_stats, load_gamemode_stats
from emojis import get_stat_emoji
from descriptions import get_description

class mychar(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    
  @commands.command(aliases=["mcs", "char", "inv"])
  async def mychar(self, ctx, *, member: discord.Member = None):
    """
    📜 Show your investigator's stats, skills, backstory and inventory.
    Usage: `[p]mychar` or `[p]mychar @User` to see others.
    """
    if not isinstance(ctx.channel, discord.TextChannel):
      await ctx.send("This command is not allowed in DMs.")
      return    
      
    if member is None:
      user_id = str(ctx.author.id)  # Get the user's ID as a string
    else:
      user_id = str(member.id)
    
    server_id = str(ctx.guild.id)  # Get the server's ID as a string
    player_stats = await load_player_stats()
    
    if user_id not in player_stats[server_id]:  # Initialize the user's stats if they don't exist
        await ctx.send(f"{member.display_name if member else ctx.author.display_name} doesn't have an investigator. Use `!newInv` for creating a new investigator.")
        return
      
    #loading game mode
    server_stats = await load_gamemode_stats()
    
    if server_id not in server_stats:
        server_stats[server_id] = {}

    if 'game_mode' not in server_stats[server_id]:
        server_stats[server_id]['game_mode'] = 'Call of Cthulhu'  # Default to Call of Cthulhu
        
    current_mode = server_stats[server_id]['game_mode'] 
         
    name = player_stats[server_id][user_id]["NAME"]
    page = 1
    maxpage = 4
    embed = discord.Embed(
            title=name,
            description="Investigator statistics:",
            color=discord.Color.green()
        )

    async def generate_stats_page(page):
      limiter = 0
      limit = 17
      embed = discord.Embed(title=f"{name}'s stats and skills", description=f"Stats - {page}/{maxpage}", color=discord.Color.green())
      if page == 1:  
        for i in player_stats[server_id][user_id]:
          stat_value = player_stats[server_id][user_id][i]
          if isinstance(stat_value, dict): continue
          limiter = limiter + 1
          description = ""
          if i == "NAME":
            pass
          elif i == "Move":
            if player_stats[server_id][user_id]["DEX"] != 0 and \
                player_stats[server_id][user_id]["SIZ"] != 0 and \
                player_stats[server_id][user_id]["STR"] != 0 and \
                player_stats[server_id][user_id]["Age"] != 0:
                if  player_stats[server_id][user_id]["DEX"] <  player_stats[server_id][user_id]["SIZ"] and \
                    player_stats[server_id][user_id]["STR"] <  player_stats[server_id][user_id]["SIZ"]:
                    MOV = 7                            
                elif player_stats[server_id][user_id]["DEX"] <  player_stats[server_id][user_id]["SIZ"] or \
                    player_stats[server_id][user_id]["STR"] <  player_stats[server_id][user_id]["SIZ"]:
                    MOV = 8
                elif player_stats[server_id][user_id]["DEX"] ==  player_stats[server_id][user_id]["SIZ"] and \
                    player_stats[server_id][user_id]["STR"] ==  player_stats[server_id][user_id]["SIZ"]:
                    MOV = 8                           
                else:
                    MOV = 9

                if 40 <= player_stats[server_id][user_id]["Age"] < 50:
                    MOV -= 1
                elif 50 <= player_stats[server_id][user_id]["Age"] < 60:
                    MOV -= 2
                elif 60 <= player_stats[server_id][user_id]["Age"] < 70:
                    MOV -= 3
                elif 70 <= player_stats[server_id][user_id]["Age"] < 80:
                    MOV -= 4
                elif player_stats[server_id][user_id]["Age"] >= 80:
                    MOV -= 5
    
                stat_value = f"{MOV}"
            else:
                stat_value = "Fill your DEX, STR, SIZ and Age."
            
          elif i in ["Build","Damage Bonus"]:
            if player_stats[server_id][user_id]["STR"] != 0 and player_stats[server_id][user_id]["SIZ"] != 0:
                STRSIZ = player_stats[server_id][user_id]["STR"] + player_stats[server_id][user_id]["SIZ"]
                if 2 <= STRSIZ <= 64:
                    BUILD = -2
                    BONUSDMG = -2
                elif 65 <= STRSIZ <= 84:
                    BUILD = -1
                    BONUSDMG = -1
                elif 85 <= STRSIZ <= 124:
                    BUILD = 0
                    BONUSDMG = 0
                elif 125 <= STRSIZ <= 164:
                    BUILD = 1
                    BONUSDMG = "1D4"
                elif 165 <= STRSIZ <= 204:
                    BUILD = 2
                    BONUSDMG = "1D6"
                elif 205 <= STRSIZ <= 284:
                    BUILD = 3
                    BONUSDMG = "2D6"
                elif 285 <= STRSIZ <= 364:
                    BUILD = 4
                    BONUSDMG = "3D6"
                elif 365 <= STRSIZ <= 444:
                    BUILD = 5
                    BONUSDMG = "4D6"
                elif 445 <= STRSIZ <= 524:
                    BUILD = 6
                    BONUSDMG = "5D6"
                else:
                    #Not posible if used correctly!
                    BUILD = "You are CHONKER! (7+)"
                    BONUSDMG = "You are too strong! (6D6+)"
                if i == "Build":
                  stat_value = f"{BUILD}"
                if i == "Damage Bonus":
                  stat_value = f"{BONUSDMG}"
            else:
                stat_value = "Fill your STR and SIZ."
          elif i not in ["Age", "HP", "MP"] and limiter <= limit:
            stat_value = player_stats[server_id][user_id][i]
            if i not in ["LUCK"]:
              description = get_description(i,stat_value)
            stat_value = f"**{stat_value}**/{stat_value//2}/{stat_value//5}"
          else:
            if limiter <= limit:
              if current_mode == 'Call of Cthulhu' and i == "HP":
                stat_value = f"{player_stats[server_id][user_id][i]}/{(player_stats[server_id][user_id]['CON']+player_stats[server_id][user_id]['SIZ'])//10}"
              elif current_mode == 'Pulp of Cthulhu' and i == "HP":
                stat_value = f"{player_stats[server_id][user_id][i]}/{(player_stats[server_id][user_id]['CON']+player_stats[server_id][user_id]['SIZ'])//5}"
              elif i == "MP":
                stat_value = f"{player_stats[server_id][user_id][i]}/{player_stats[server_id][user_id]['POW']//5}"
              elif i == "Age":
                stat_value = f"{player_stats[server_id][user_id][i]} years old."
              else:
                stat_value = player_stats[server_id][user_id][i]
          if i != "NAME" and limiter <= limit:
            embed.add_field(name=f"{i}{get_stat_emoji(i)}", value=f"{stat_value}\n {description}", inline=True)
      if page == 2:
        for i in player_stats[server_id][user_id]:
          if isinstance(player_stats[server_id][user_id][i], dict): continue
          limiter = limiter + 1
          if i == "NAME":
            pass
          else:
            if 17 < limiter <= 41:
              stat_value = player_stats[server_id][user_id][i]
              if i not in ["Credit Rating"]:
                description = get_description("skill",stat_value)
              else:
                description = get_description("Credit Rating",stat_value)
              embed.add_field(name=f"{i}{get_stat_emoji(i)}", value=f"**{stat_value}**/{stat_value//2}/{stat_value//5}\n{description}", inline=True)
      if page == 3:
        for i in player_stats[server_id][user_id]:
          if isinstance(player_stats[server_id][user_id][i], dict): continue
          limiter = limiter + 1
          if i == "NAME":
            pass
          else:
            if 41 < limiter <= 65:
              stat_value = player_stats[server_id][user_id][i]
              description = get_description("skill",stat_value)
              embed.add_field(name=f"{i}{get_stat_emoji(i)}", value=f"**{stat_value}**/{stat_value//2}/{stat_value//5}\n{description}", inline=True)
      if page == 4:
        backstory_data = player_stats[server_id][user_id]["Backstory"]
        for category, entries in backstory_data.items():
            formatted_entries = "\n".join([f"{index + 1}. {entry}" for index, entry in enumerate(entries)])
            embed.add_field(name=category, value=formatted_entries, inline=False)
      return embed  # Return the embed
      
    message = await ctx.send(embed=await generate_stats_page(page))
    await message.add_reaction("⬅️")
    await message.add_reaction("➡️")
    
    async def check(reaction, user):
        return user == ctx.author and reaction.message == message and reaction.emoji in ["⬅️", "➡️"]
    
    while True:
        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=60, check=check)
            if reaction.emoji == "⬅️":
                page = maxpage if page == 1 else page - 1  # Move to last page if on the first
            elif reaction.emoji == "➡️":
                page = 1 if page == maxpage else page + 1  # Move to first page if on the last
    
            await message.edit(embed=await generate_stats_page(page))
            await message.remove_reaction(reaction, ctx.author)
        except asyncio.TimeoutError:
            await message.clear_reactions()
            break

async def setup(bot):
  await bot.add_cog(mychar(bot))
