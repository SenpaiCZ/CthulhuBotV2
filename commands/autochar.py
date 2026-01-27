import discord, asyncio, random, math
from discord.ext import commands
from loadnsave import load_player_stats, save_player_stats, load_server_stats

class autochar(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.command(aliases=["autoChar"])
  async def autochar(self, ctx):
    """
    `[p]autoChar` - Generates random stats for your investigator. You can re-roll, dismiss or save stats.
    """
    user_id = str(ctx.author.id)  # Get the user's ID as a string
    server_id = str(ctx.guild.id)  # Get the server's ID as a string
    player_stats = await load_player_stats()
    server_prefixes = await load_server_stats()
    prefix = server_prefixes.get(server_id, "!") if server_id else "!"

    if user_id not in player_stats[server_id]:
        await ctx.send(f"{ctx.author.display_name} doesn't have an investigator. Use `{prefix}newInv` for creating a new investigator.")
        return
    
    # Check if the player has a character with all stats at 0
    if user_id in player_stats[server_id] and all(player_stats[server_id][user_id][stat] == 0 for stat in ["STR", "DEX", "CON", "INT", "POW", "APP", "EDU", "SIZ"]):
        # Generate stats
        BUILD = 0
        BONUSDMG = 0
        MOV = 0
        STR = 5 * sum(sorted([random.randint(1, 6) for _ in range(3)])[1:])
        CON = 5 * sum(sorted([random.randint(1, 6) for _ in range(3)])[1:])
        SIZ = 5 * (sum(sorted([random.randint(1, 6) for _ in range(2)])) + 6)
        DEX = 5 * sum(sorted([random.randint(1, 6) for _ in range(3)])[1:])
        APP = 5 * sum(sorted([random.randint(1, 6) for _ in range(3)])[1:])
        INT = 5 * (sum(sorted([random.randint(1, 6) for _ in range(2)])) + 6)
        POW = 5 * sum(sorted([random.randint(1, 6) for _ in range(3)])[1:])
        EDU = 5 * (sum(sorted([random.randint(1, 6) for _ in range(2)])) + 6)
        LUCK = 5 * sum(sorted([random.randint(1, 6) for _ in range(3)])[1:])
        HP = (CON + SIZ) // 10
        SAN = POW
        MP = POW // 5

        #Bonus DMG and Build
        STRSIZ = STR + SIZ
        if 2 <= STRSIZ <= 64:
            BONUSDMG = -2
            BUILD = -2
        elif 65 <= STRSIZ <= 84:
            BONUSDMG = -1
            BUILD = -1
        elif 85 <= STRSIZ <= 124:
            BONUSDMG = 0
            BUILD = 0
        elif 125 <= STRSIZ <= 164:
            BONUSDMG = "1D4"
            BUILD = 1
        elif 165 <= STRSIZ <= 204:
            BONUSDMG = "1D6"
            BUILD = 2
        elif 205 <= STRSIZ <= 284:
            BONUSDMG = "2D6"
            BUILD = 3
        elif 285 <= STRSIZ <= 364:
            BONUSDMG = "3D6"
            BUILD = 4
        elif 365 <= STRSIZ <= 444:
            BONUSDMG = "4D6"
            BUILD = 5
        elif 445 <= STRSIZ <= 524:
            BONUSDMG = "5D6"
            BUILD = 6
        else:
            # if fuking broken
            BONUSDMG = 0
            BUILD = 0
        #calculatin MOV
        if DEX < SIZ and STR < SIZ:
            MOV = 7
        elif DEX < SIZ or STR < SIZ or (DEX == STR == SIZ):
            MOV = 8
        elif DEX > SIZ and STR > SIZ:
            MOV = 9

        stats_embed = discord.Embed(
            title=":detective: Investigator Creation Assistant",
            description="New stats have been generated for your character.",
            color=discord.Color.green()
        )
        stats_embed.add_field(name="STR", value=f":muscle: 3D6 x 5 :game_die: {STR}", inline=True)
        stats_embed.add_field(name="DEX", value=f":runner: 3D6 x 5 :game_die: {DEX}", inline=True)
        stats_embed.add_field(name="CON", value=f":heart: 3D6 x 5 :game_die: {CON}", inline=True)
        stats_embed.add_field(name="INT", value=f":brain: 3D6 x 5 :game_die: {INT}", inline=True)
        stats_embed.add_field(name="POW", value=f":zap: 3D6 x 5 :game_die: {POW}", inline=True)
        stats_embed.add_field(name="APP", value=f":heart_eyes: 3D6 x 5 :game_die: {APP}", inline=True)
        stats_embed.add_field(name="EDU", value=f":mortar_board: 2D6 x 5 + 5 :game_die: {EDU}", inline=True)
        stats_embed.add_field(name="SIZ", value=f":bust_in_silhouette: 2D6 x 5 + 5 :game_die: {SIZ}", inline=True)
        stats_embed.add_field(name="HP", value=f":heartpulse: (CON + SIZ) / 5 :game_die: {HP}", inline=True)
        stats_embed.add_field(name="SAN", value=f":scales: POW :game_die: {SAN}", inline=True)
        stats_embed.add_field(name="MP", value=f":sparkles: POW / 5 :game_die: {MP}", inline=True)
        stats_embed.add_field(name="LUCK", value=f":four_leaf_clover: 3D6 x 5 :game_die: {LUCK}", inline=True)
        stats_embed.add_field(name="MOV", value=f":person_running: Based of DEX, STR & SIZ :game_die: {MOV}", inline=True)
        stats_embed.add_field(name="Damage Bonus", value=f":boxing_glove: Based of STR & SIZ :game_die: {BONUSDMG}", inline=True)
        stats_embed.add_field(name="Build", value=f":restroom: Based of STR & SIZ :game_die: {BUILD}", inline=True)
        

        message = await ctx.send(embed=stats_embed)
        await message.add_reaction("✅")  # Add checkmark emoji
        await message.add_reaction("❌")  # Add X emoji
        await message.add_reaction("🔁")  # Add loop emoji

        def check(reaction, user):
            return user == ctx.author and reaction.message.id == message.id and str(reaction.emoji) in ["✅", "❌", "🔁"]

        try:
            reaction, user = await self.bot.wait_for("reaction_add", timeout=60, check=check)
            if str(reaction.emoji) == "✅":
                player_stats[server_id][user_id]["STR"] = STR
                player_stats[server_id][user_id]["DEX"] = DEX
                player_stats[server_id][user_id]["CON"] = CON
                player_stats[server_id][user_id]["INT"] = INT
                player_stats[server_id][user_id]["POW"] = POW
                player_stats[server_id][user_id]["APP"] = APP
                player_stats[server_id][user_id]["EDU"] = EDU
                player_stats[server_id][user_id]["SIZ"] = SIZ
                player_stats[server_id][user_id]["HP"] = HP
                player_stats[server_id][user_id]["SAN"] = SAN
                player_stats[server_id][user_id]["MP"] = MP
                player_stats[server_id][user_id]["LUCK"] = LUCK
                player_stats[server_id][user_id]["Dodge"] = math.floor(DEX/5)
                player_stats[server_id][user_id]["Language (own)"] = EDU

                await save_player_stats(player_stats)  # Save the data to the JSON file
                await ctx.send(f"Your character's stats have been saved! You should set your Age with `{prefix}cstat Age` now.")
            elif str(reaction.emoji) == "❌":
                await ctx.send("Character creation canceled. Stats have not been saved.")
            elif str(reaction.emoji) == "🔁":
                await ctx.invoke(self.bot.get_command("autoChar"))  # Reinvoke the command to generate new stats
        except asyncio.TimeoutError:
            await ctx.send("You took too long to react. Automatic character stats creation canceled.")
    else:
        await ctx.send("You already have some stats assigned to your investigator.")


async def setup(bot):
  await bot.add_cog(autochar(bot))
