import discord
from discord.ext import commands
from loadnsave import load_player_stats, save_player_stats, load_server_stats


class newinvestigator(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.command(aliases=["newInv", "newinv"])
  async def newinvestigator(self, ctx, *, investigator_name=None):
    """
    `[p]newInv Inv-name` - Create a new investigator (e.g. `[p]newInv Oswald Chester Razner`)
    """
    server_id = str(ctx.guild.id)  # Get the server's ID as a string
    server_prefixes = await load_server_stats()
    prefix = server_prefixes.get(server_id, "!") if server_id else "!"
    if not isinstance(ctx.channel, discord.TextChannel):
      await ctx.send("This command is not allowed in DMs.")
      return
    user_id = str(ctx.author.id)  # Get the user's ID as a string

    player_stats = await load_player_stats()

    if investigator_name is None:
      await ctx.message.channel.send(
          f"Please add a name for your investigator. (e.g. `{prefix}newInv Mr. Pickles`)"
      )
      return
    # Check if the server has an entry in player_stats
    if server_id not in player_stats:
      player_stats[server_id] = {
      }  # Initialize a new server entry if it doesn't exist

    if user_id not in player_stats[server_id]:
      player_stats[server_id][user_id] = {
          "NAME": investigator_name,
          "STR": 0,
          "DEX": 0,
          "CON": 0,
          "INT": 0,
          "POW": 0,
          "EDU": 0,
          "SIZ": 0,
          "APP": 0,
          "SAN": 0,
          "HP": 0,
          "MP": 0,
          "LUCK": 0,
          "Move": "Calculated on the fly by !myChar",
          "Build": "Calculated on the fly by !myChar",
          "Damage Bonus": "Calculated on the fly by !myChar",
          "Age": 0,
          "Accounting": 5,
          "Anthropology": 1,
          "Appraise": 5,
          "Archaeology": 1,
          "Charm": 15,
          "Art/Craft": 5,
          "Climb": 20,
          "Credit Rating": 0,
          "Cthulhu Mythos": 0,
          "Disguise": 5,
          "Dodge": 0,
          "Drive Auto": 20,
          "Elec. Repair": 10,
          "Fast Talk": 5,
          "Fighting Brawl": 25,
          "Firearms Handgun": 20,
          "Firearms Rifle/Shotgun": 25,
          "First Aid": 30,
          "History": 5,
          "Intimidate": 15,
          "Jump": 10,
          "Language other": 1,
          "Language own": 0,
          "Law": 5,
          "Library Use": 20,
          "Listen": 20,
          "Locksmith": 1,
          "Mech. Repair": 10,
          "Medicine": 1,
          "Natural World": 10,
          "Navigate": 10,
          "Occult": 5,
          "Persuade": 10,
          "Pilot": 1,
          "Psychoanalysis": 1,
          "Psychology": 10,
          "Ride": 5,
          "Science specific": 1,
          "Sleight of Hand": 10,
          "Spot Hidden": 25,
          "Stealth": 20,
          "Survival": 10,
          "Swim": 20,
          "Throw": 20,
          "Track": 10,
          "CustomSkill": 0,
          "CustomSkills": 0,
          "CustomSkillss": 0,
          "Backstory": {
              'My Story': [],
              'Personal Description': [],
              'Ideology and Beliefs': [],
              'Significant People': [],
              'Meaningful Locations': [],
              'Treasured Possessions': [],
              'Traits': [],
              'Injuries and Scars': [],
              'Phobias and Manias': [],
              'Arcane Tome and Spells': [],
              'Encounters with Strange Entities': [],
              'Fellow Investigators': [],
              'Gear and Possessions': [],
              'Spending Level': [],
              'Cash': [],
              'Assets': [],
          }
      }
      await ctx.send(
          f"Investigator '{investigator_name}' has been created with default stats. You can generate random stats by using `{prefix}autoChar` or you can fill your stats with `{prefix}cstat`"
      )
      await save_player_stats(player_stats)  # Save the data to the JSON file
    else:
      await ctx.send(
          f"You already have an investigator. You can't create a new one until you delete the existing one with `{prefix}deleteInvestigator`."
      )


async def setup(bot):
  await bot.add_cog(newinvestigator(bot))
