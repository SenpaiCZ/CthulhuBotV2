import discord
import random
import re
from discord.ext import commands

class roll(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["diceroll", "D", "d"], guild_only=True)
    async def roll(self, ctx, *, dice_expression):
        """
        `[p]d XDY + Z - W * V` - Roll dice with addition, subtraction, and multiplication (e.g. `[p]d 3D6 + 10 - 2 * 2`)
        """
        try:
            result, detail = self.evaluate_dice_expression(dice_expression)
            embed = discord.Embed(
                title=f":game_die: Dice Roll Result",
                description=f"{ctx.author.mention} :game_die: Rolling: `{dice_expression}`",
                color=discord.Color.blue()
            )
            embed.add_field(name="Detail", value=detail, inline=False)
            embed.add_field(name="Total", value=f":game_die: {result}", inline=False)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f":warning: Invalid dice expression: {str(e)}")

    def evaluate_dice_expression(self, expression):
        # Replace D with 'd' and remove spaces
        expression = expression.replace('D', 'd').replace(' ', '')
        detail_parts = []

        # Define a function to handle dice rolls
        def roll_dice(match):
            num, size = map(int, match.groups())
            rolls = [random.randint(1, size) for _ in range(num)]
            detail_parts.append(f":game_die: {num}d{size}: {' + '.join(map(str, rolls))} = {sum(rolls)}")
            return sum(rolls)

        # Replace dice roll expressions with their results
        dice_pattern = re.compile(r'(\d+)d(\d+)')
        expression = dice_pattern.sub(lambda m: str(roll_dice(m)), expression)

        # Evaluate the expression
        result = eval(expression, {"__builtins__": None})
        detail = "\n".join(detail_parts) + f"\nExpression: {expression}"
        return result, detail

async def setup(bot):
    await bot.add_cog(roll(bot))
