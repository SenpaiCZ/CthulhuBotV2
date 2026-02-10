import discord, asyncio
from discord.ext import commands
from loadnsave import load_player_stats, save_player_stats, load_gamemode_stats
from emojis import get_stat_emoji
from descriptions import get_description
import occupation_emoji

class mychar(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    
  @commands.command(aliases=["mcs", "char", "inv"])
  async def mychar(self, ctx, *, member: discord.Member = None):
    """
    📜 Show your investigator's stats, skills, backstory and inventory.
    Usage: `[p]mychar` or `[p]mychar @User` to see another's.
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
      
    # loading game mode
    server_stats = await load_gamemode_stats()
    if server_id not in server_stats:
        server_stats[server_id] = {}
    if 'game_mode' not in server_stats[server_id]:
        server_stats[server_id]['game_mode'] = 'Call of Cthulhu'

    # Determine Character Game Mode
    # Priority: Character Sheet > Server Default
    char_data = player_stats[server_id][user_id]
    current_mode = char_data.get("Game Mode", server_stats[server_id]['game_mode'])

    # Normalize mode string just in case
    if "pulp" in current_mode.lower():
        current_mode = "Pulp of Cthulhu"
        mode_label = "Pulp of Cthulhu character"
    else:
        current_mode = "Call of Cthulhu"
        mode_label = "Call of Cthulhu character"
         
    name = char_data["NAME"]
    page = 1
    maxpage = 4

    async def generate_stats_page(page):
      limiter = 0
      limit = 18
      # Add Mode Label to Title or Description
      embed = discord.Embed(title=f"{name}'s stats and skills", description=f"**{mode_label}**\nStats - {page}/{maxpage}", color=discord.Color.green())

      if page == 1:  
        for i in char_data:
          if i == "Residence": continue
          if i == "Game Mode": continue # Skip internal field
          if i == "Archetype": continue
          stat_value = char_data[i]
          if isinstance(stat_value, dict): continue

          limiter = limiter + 1
          description = ""

          if i == "NAME":
            pass
          elif i == "Occupation":
            stat_value = char_data[i]
            occ_emoji = occupation_emoji.get_occupation_emoji(stat_value)
            stat_value = f"{stat_value} {occ_emoji}"
            embed.add_field(name=f"{i}{get_stat_emoji(i)}", value=f"{stat_value}\n ", inline=True)

            residence = char_data.get("Residence", "Unknown")
            embed.add_field(name=f"Residence{get_stat_emoji('Residence')}", value=f"{residence}\n ", inline=True)
            limiter += 1
            continue
          elif i == "Move":
            if char_data.get("DEX", 0) != 0 and \
                char_data.get("SIZ", 0) != 0 and \
                char_data.get("STR", 0) != 0 and \
                char_data.get("Age", 0) != 0:

                dex = char_data["DEX"]
                siz = char_data["SIZ"]
                str_stat = char_data["STR"]
                age = char_data["Age"]

                if dex < siz and str_stat < siz:
                    MOV = 7                            
                elif dex < siz or str_stat < siz:
                    MOV = 8
                elif dex == siz and str_stat == siz:
                    MOV = 8                           
                else:
                    MOV = 9

                if 40 <= age < 50: MOV -= 1
                elif 50 <= age < 60: MOV -= 2
                elif 60 <= age < 70: MOV -= 3
                elif 70 <= age < 80: MOV -= 4
                elif age >= 80: MOV -= 5
    
                stat_value = f"{max(0, MOV)}"
            else:
                stat_value = "Fill your DEX, STR, SIZ and Age."
            
          elif i in ["Build","Damage Bonus"]:
             # These are pre-calculated in finalize_character usually,
             # but legacy code recalculates here if STR/SIZ exist.
             # We'll trust the stored value if present, else calc?
             # The existing code logic calculated it. Let's keep it for robustness.
            if char_data.get("STR", 0) != 0 and char_data.get("SIZ", 0) != 0:
                STRSIZ = char_data["STR"] + char_data["SIZ"]
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
                    BUILD = "You are a CHONKER! (7+)"
                    BONUSDMG = "You are too strong! (6D6+)"
                if i == "Build":
                  stat_value = f"{BUILD}"
                if i == "Damage Bonus":
                  stat_value = f"{BONUSDMG}"
            else:
                stat_value = "Fill your STR and SIZ."

          elif i not in ["Age", "HP", "MP", "Occupation"] and limiter <= limit:
            stat_value = char_data[i]
            if i not in ["LUCK"]:
              description = get_description(i,stat_value)
            stat_value = f"**{stat_value}**/{stat_value//2}/{stat_value//5}"
          else:
            if limiter <= limit:
              if i == "HP":
                con = char_data.get('CON', 0)
                siz = char_data.get('SIZ', 0)
                if current_mode == 'Call of Cthulhu':
                     max_hp = (con + siz) // 10
                else: # Pulp
                     max_hp = (con + siz) // 5
                stat_value = f"{char_data[i]}/{max_hp}"

              elif i == "MP":
                stat_value = f"{char_data[i]}/{char_data['POW']//5}"
              elif i == "Age":
                stat_value = f"{char_data[i]} years old."
              else:
                stat_value = char_data[i]

          if i != "NAME" and limiter <= limit:
            embed.add_field(name=f"{i}{get_stat_emoji(i)}", value=f"{stat_value}\n {description}", inline=True)

      if page == 2:
        for i in char_data:
          if i == "Residence": continue
          if i == "Game Mode": continue
          if i == "Archetype": continue
          if isinstance(char_data[i], dict): continue
          limiter = limiter + 1
          if i == "NAME":
            pass
          else:
            if 18 < limiter <= 42:
              stat_value = char_data[i]
              if i not in ["Credit Rating"]:
                description = get_description("skill",stat_value)
              else:
                description = get_description("Credit Rating",stat_value)
              embed.add_field(name=f"{i}{get_stat_emoji(i)}", value=f"**{stat_value}**/{stat_value//2}/{stat_value//5}\n{description}", inline=True)
      if page == 3:
        for i in char_data:
          if i == "Residence": continue
          if i == "Game Mode": continue
          if i == "Archetype": continue
          if isinstance(char_data[i], dict): continue
          limiter = limiter + 1
          if i == "NAME":
            pass
          else:
            if 42 < limiter <= 66:
              stat_value = char_data[i]
              description = get_description("skill",stat_value)
              embed.add_field(name=f"{i}{get_stat_emoji(i)}", value=f"**{stat_value}**/{stat_value//2}/{stat_value//5}\n{description}", inline=True)
      if page == 4:
        backstory_data = char_data["Backstory"]

        # Display Archetype first if present
        if "Archetype" in char_data:
             embed.add_field(name="Archetype", value=char_data["Archetype"], inline=False)

        # Ensure Pulp Talents are shown first if present, assuming insertion order or explicit check
        # Explicit check to be safe
        if "Pulp Talents" in backstory_data:
             entries = backstory_data["Pulp Talents"]
             if entries:
                formatted_entries = "\n".join([f"{index + 1}. {entry}" for index, entry in enumerate(entries)])
                embed.add_field(name="Pulp Talents", value=formatted_entries, inline=False)

        for category, entries in backstory_data.items():
            if category == "Pulp Talents": continue # Already handled
            formatted_entries = "\n".join([f"{index + 1}. {entry}" for index, entry in enumerate(entries)])
            embed.add_field(name=category, value=formatted_entries, inline=False)
      return embed  # Return the embed
      
    message = await ctx.send(embed=await generate_stats_page(page))
    await message.add_reaction("⬅️")
    await message.add_reaction("➡️")
    
    def check(reaction, user):
        return user == ctx.author and reaction.message.id == message.id and reaction.emoji in ["⬅️", "➡️"]
    
    while True:
        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=60, check=check)
            if reaction.emoji == "⬅️":
                page = maxpage if page == 1 else page - 1  # Move to last page if on the first
            elif reaction.emoji == "➡️":
                page = 1 if page == maxpage else page + 1  # Move to first page if on the last
    
            await message.edit(embed=await generate_stats_page(page))
            try:
                await message.remove_reaction(reaction, ctx.author)
            except: pass
        except asyncio.TimeoutError:
            try: await message.clear_reactions()
            except: pass
            break

async def setup(bot):
  await bot.add_cog(mychar(bot))
