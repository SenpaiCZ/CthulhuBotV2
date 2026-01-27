import discord
from discord.ext import commands


class inviteme(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.command()
  async def invite(self, ctx):
      """
      `[p]invite` - Generate a link to invite the bot to your server.
      """
      link="https://discord.com/api/oauth2/authorize?client_id=1149968613839749190&permissions=40666948693056&scope=bot"
      embed = discord.Embed(
          title="Invite Keeper to your server!",
          color=discord.Color.blue()
      )
      embed.add_field(
          name="Invite Bot",
          value=f"[Invite me]({link})",
          inline=False
      )
      embed.add_field(
          name="Buy books by Chaosium",
          value="[Call of Cthulhu Keeper Rulebook](https://www.chaosium.com/call-of-cthulhu-keeper-rulebook-hardcover/)\n[Call of Cthulhu Starter Set](https://www.chaosium.com/call-of-cthulhu-starter-set/)\n[Pulp Cthulhu](https://www.chaosium.com/pulp-cthulhu-hardcover/)",
          inline=False
      )
      embed.add_field(
      name="More on Chaosium",
      value="[Chaosium.inc](https://www.chaosium.com)",
      inline=False
      )
      embed.add_field(
      name="Disclaimer",
      value="This is **unofficial** Discord bot and its not associated with Chaosium Inc.",
      inline=False
      )
      await ctx.send(embed=embed)


async def setup(bot):
  await bot.add_cog(inviteme(bot))
