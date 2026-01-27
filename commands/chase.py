import discord
from discord.ext import commands
from loadnsave import load_chase_data, save_chase_data, load_player_stats
import asyncio, random

class chase(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group()
    async def chase(self, ctx):
        """
        `[p]chase` - Complex autochase command that will walk you through the chase at ease
        """
        if ctx.invoked_subcommand is None:
            await ctx.send("Invalid subcommand. Use `[p]help chase` for usage instructions.")

    @chase.command(name="create")
    async def create_chase(self, ctx):
        """
        `[p]chase create` - Create a chase session in the current channel
        """
        server_id = str(ctx.guild.id)
        channel_id = str(ctx.channel.id)
        keeper_id = str(ctx.author.id)

        chase_data = await load_chase_data()

        if server_id in chase_data and channel_id in chase_data[server_id]:
            await ctx.send("Chase already started in this channel.")
        else:
            if server_id not in chase_data:
                chase_data[server_id] = {}
            chase_data[server_id][channel_id] = {}

            await ctx.send("Are we on `foot` or in a `car`?")

            def check_type(message):
                return message.author == ctx.author and message.content.lower() in ["foot", "car"]

            try:
                response_type = await self.bot.wait_for("message", timeout=60, check=check_type)

                chase_type = response_type.content.lower()
                chase_data[server_id][channel_id]["type"] = chase_type

                await ctx.send("Are we `following` or `running away`?")
                
                def check_pursuit(message):
                    return message.author == ctx.author and message.content.lower() in ["following", "running away"]

                response_pursuit = await self.bot.wait_for("message", timeout=60, check=check_pursuit)

                chase_pursuit = response_pursuit.content.lower()
                chase_data[server_id][channel_id]["pursuit"] = chase_pursuit
                chase_data[server_id][channel_id]["keeper"] = keeper_id
                chase_data[server_id][channel_id]["enemy_data"] = {}

                await save_chase_data(chase_data)
                await ctx.send(f"Chase session created in this channel. Type: {chase_type}, Pursuit: {chase_pursuit}, Keeper: {ctx.author.display_name}")
            except asyncio.TimeoutError:
                await ctx.send("You took too long to react. Chase creation canceled.")


       
    @chase.command(name="join")
    async def join_chase(self, ctx):
        """
        `[p]chase join` - Join the chase session in the current channel
        """
        server_id = str(ctx.guild.id)
        channel_id = str(ctx.channel.id)
        user_id = str(ctx.author.id)
        player_stats = await load_player_stats()  # Load player stats
        chase_data = await load_chase_data()
    
        if server_id in chase_data and channel_id in chase_data[server_id]:
            if "participants" not in chase_data[server_id][channel_id]:
                chase_data[server_id][channel_id]["participants"] = {}
    
            if user_id not in chase_data[server_id][channel_id]["participants"]:
                if user_id in player_stats[server_id]:
                    print("if user data")
                    if (
                        player_stats[server_id][user_id]["DEX"] < player_stats[server_id][user_id]["SIZ"]
                        and player_stats[server_id][user_id]["STR"] < player_stats[server_id][user_id]["SIZ"]
                    ):
                        MOV = 7
                    elif (
                        player_stats[server_id][user_id]["DEX"] < player_stats[server_id][user_id]["SIZ"]
                        or player_stats[server_id][user_id]["STR"] < player_stats[server_id][user_id]["SIZ"]
                    ):
                        MOV = 8
                    elif (
                        player_stats[server_id][user_id]["DEX"] == player_stats[server_id][user_id]["SIZ"]
                        and player_stats[server_id][user_id]["STR"] == player_stats[server_id][user_id]["SIZ"]
                    ):
                        MOV = 8
                    else:
                        MOV = 9
    
                    roll = random.randint(1, 100)
                    print(roll)
                    typeOfChase = chase_data[server_id][channel_id]["type"]
                    print(typeOfChase)
                    drivingSkill = player_stats[server_id][user_id]["Drive Auto"]
                    print(drivingSkill)
                    CONstat = player_stats[server_id][user_id]["CON"]
                    print(CONstat)
                    skill = "potato"  # Initialize as a placeholder value
    
                    embed = discord.Embed(
                        title=":game_die: ROLL FOR BONUS MOV :game_die:",
                        description=f"{ctx.author.display_name} is joining the car chase.",
                        color=discord.Color.blue()
                    )
    
                    if typeOfChase == "car":
                        embed.add_field(name='Chase is in cars', value=f"To calculate your bonus MOV we will use **Drive Auto**.", inline=False)
                        embed.add_field(name=f"{ctx.author.display_name}'s  :blue_car:Drive auto", value=f"**{drivingSkill}**.", inline=False)
    
                        skill = drivingSkill
                    if typeOfChase == "foot":
                        embed.add_field(name='Chase is on foot', value=f"To calculate your bonus MOV we will use **CON**.", inline=False)
                        embed.add_field(name=f"{ctx.author.display_name}'s :heart:CON", value=f"**{CONstat}**.", inline=False)
                        skill = CONstat
    
                    embed.add_field(name=':game_die:ROLL:game_die:', value=f"{ctx.author.display_name} rolled **{roll}**.", inline=False)
                    if roll > skill:
                        MOV = MOV - 1
                        embed.add_field(name=':game_die: Roll failed :x:', value=f"MOV reduced to **{MOV}**.", inline=False)
                        embed.color = discord.Color.red()
                    elif roll <= skill / 5:
                        MOV = MOV + 1
                        embed.add_field(name=':game_die: Rolled extreme success :star:', value=f"MOV raised to **{MOV}**.", inline=False)
                        embed.color = discord.Color.green()
                    else:
                        embed.add_field(name=':game_die: Rolled success or hard success :white_check_mark:', value=f"MOV **{MOV}** is unchanged.", inline=False)
                        embed.color = discord.Color.blue()
                    
                    chase_data[server_id][channel_id]["participants"][user_id] = {"MOV": MOV, "POSITION": None}
                    await save_chase_data(chase_data)
    
                    await ctx.send(embed=embed)
            else:
                await ctx.send(f"{ctx.author.display_name} is already part of the chase.")
        else:
            await ctx.send("There is no active chase session in this channel. Use `[p]chase create` to start one.")


    @chase.command(name="addEnemy")
    async def addEnemy_chase(self, ctx):
        server_id = str(ctx.guild.id)
        channel_id = str(ctx.channel.id)
        user_id = str(ctx.author.id)
        chase_data = await load_chase_data()
        if server_id in chase_data and channel_id in chase_data[server_id]:
          if user_id == chase_data[server_id][channel_id]["keeper"]:
            await ctx.send(f"{ctx.author.display_name} is adding enemy to the chase.")
            
            def is_integer(message):
                try:
                    value = int(message.content)
                    return 5 <= value <= 10
                except ValueError:
                    return False
        
            try:
                await ctx.send("Please, enter enemy's MOV:")
                response = await self.bot.wait_for("message", timeout=60, check=is_integer)
                chase_data[server_id][channel_id]["enemy_data"] = {"MOV": int(response.content), "POSITION": None}
                await ctx.send(f"Enemy's MOV is set to {int(response.content)}")
                await save_chase_data(chase_data)
                
            except asyncio.TimeoutError:
                await ctx.send("You took too long to respond or didn't provide valid number.")
          else:
            await ctx.send(f"{ctx.author.display_name} is not keeper and cant add enemy to the chase!")          
        else:
            await ctx.send("There is no active chase session in this channel. Use `[p]chase create` to start one.")
  
    @chase.command(name="start")
    async def start_chase(self, ctx):
        server_id = str(ctx.guild.id)
        channel_id = str(ctx.channel.id)
        chase_data = await load_chase_data()
        player_stats = await load_player_stats()  # Load player stats
        enemy_MOV = chase_data[server_id][channel_id]["enemy_data"]["MOV"]
        participants = chase_data[server_id][channel_id]["participants"]
        user_id = str(ctx.author.id)
        
        if user_id == chase_data[server_id][channel_id]["keeper"]:
            users_to_remove = []  # Create a list to store users to remove
    
            for user_id, participant_data in participants.items():
                participant_MOV = participant_data["MOV"]
                
                if participant_MOV > enemy_MOV:
                    await ctx.send(f"User {ctx.guild.get_member(int(user_id))} has higher MOV ({participant_MOV}) than the enemy ({enemy_MOV}). Chase will be instantly ended, you catch up with the enemy.")
                elif participant_MOV < enemy_MOV:
                    await ctx.send(f"User {ctx.guild.get_member(int(user_id))} has lower MOV ({participant_MOV}) than the enemy ({enemy_MOV}). Enemy is running away. {ctx.guild.get_member(int(user_id))} is removed from chase.")
                    users_to_remove.append(user_id)  # Add user to removal list
                else:
                    await ctx.send(f"User {ctx.guild.get_member(int(user_id))} has the same MOV ({participant_MOV}) as the enemy ({enemy_MOV}). You are in pursuit.")
            
            # Remove users from chase_data
            for user_id in users_to_remove:
                participants.pop(user_id, None)
            await save_chase_data(chase_data)
        else:
            await ctx.send(f"{ctx.author.display_name} is not the keeper and can't start the chase!")

      
async def setup(bot):
  await bot.add_cog(chase(bot))
