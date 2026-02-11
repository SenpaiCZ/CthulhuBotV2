import discord, random
from discord.ext import commands
from loadnsave import load_loot_settings


class loot(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.hybrid_command(name="loot", aliases=["randomLoot", "randomloot", "rloot"], description="Generate random loot from 1920s.")
  async def loot(self, ctx):
    """
    `[p]loot` - Generate random loot from 1920s. Configurable in dashboard.
    """
    settings = await load_loot_settings()

    items = settings.get("items", [])
    if not items:
        # Fallback if list is empty
        items = ["Nothing found."]

    money_chance = settings.get("money_chance", 25)
    money_min = settings.get("money_min", 0.01)
    money_max = settings.get("money_max", 5.00)
    currency_symbol = settings.get("currency_symbol", "$")

    min_items = settings.get("num_items_min", 1)
    max_items = settings.get("num_items_max", 5)

    # Validate range
    if max_items < min_items:
        max_items = min_items

    # Money logic
    has_money = random.randint(1, 100) <= money_chance
    money = None
    if has_money:
      money = random.uniform(money_min, money_max)

    # Item logic
    # Ensure we don't try to pick more items than exist
    available_count = len(items)
    actual_max_items = min(max_items, available_count)
    actual_min_items = min(min_items, actual_max_items)

    if available_count > 0:
        num_items = random.randint(actual_min_items, actual_max_items)
        chosen_items = random.sample(items, num_items)
    else:
        chosen_items = []

    # Vytvoření embedu
    embed = discord.Embed(title="Random Loot", color=discord.Color.blue())
    for item in chosen_items:
      emoji = "\U0001F4E6"  # Emoji pro věc
      embed.add_field(name=f"{emoji} {item}", value='\u200b',
                      inline=False)  # '\u200b' je prázdný znak

    if money is not None:
      emoji_money = "\U0001F4B5"  # Emoji pro peníze
      embed.add_field(name=f"{emoji_money} Money",
                      value=f"{currency_symbol}{money:.2f}",
                      inline=False)

    ephemeral = False
    if ctx.interaction:
        ephemeral = True

    await ctx.send(embed=embed, ephemeral=ephemeral)


async def setup(bot):
  await bot.add_cog(loot(bot))
