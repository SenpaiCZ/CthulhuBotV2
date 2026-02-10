import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from playwright.async_api import async_playwright
import io
from loadnsave import load_player_stats, load_settings

class PrintCharacter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(aliases=['pchar', 'printchar'])
    @app_commands.describe(user="The user whose character you want to print (defaults to you)")
    async def printcharacter(self, ctx, user: discord.Member = None):
        """
        Prints the character sheet of the user as an image.
        Usage: !printcharacter [@user]
        """
        if not ctx.guild:
            await ctx.send("This command can only be used in a server.")
            return

        if user is None:
            user = ctx.author

        guild_id = str(ctx.guild.id)
        user_id = str(user.id)

        # Check if character exists
        stats = await load_player_stats()
        if guild_id not in stats or user_id not in stats[guild_id]:
             await ctx.send(f"No active character found for {user.display_name}.")
             return

        # Notify user we are working on it
        msg = await ctx.send(f"Generating character sheet for {user.display_name}... 🖼️")

        # Get dashboard port
        settings = load_settings()
        port = settings.get('dashboard_port', 5000)

        # Local URL
        url = f"http://127.0.0.1:{port}/render/character/{guild_id}/{user_id}"

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                try:
                    # Set viewport size to ensure good resolution/layout if needed,
                    # though we screenshot the element.
                    page = await browser.new_page(viewport={'width': 1000, 'height': 1200})

                    # Navigate
                    try:
                        response = await page.goto(url, timeout=10000) # 10s timeout
                    except Exception as e:
                        await msg.edit(content=f"Error: Failed to load internal dashboard URL. Is the dashboard running?")
                        print(f"PrintCharacter Navigation Error: {e}")
                        return

                    if not response or not response.ok:
                        status = response.status if response else "Unknown"
                        await msg.edit(content=f"Error: Failed to load character sheet (Status: {status}).")
                        return

                    # Wait for element to be visible
                    try:
                        element = await page.wait_for_selector('.coc-sheet', timeout=5000)
                    except:
                        element = None

                    if not element:
                        # Fallback to full page if element not found
                        screenshot_bytes = await page.screenshot(full_page=True)
                    else:
                        screenshot_bytes = await element.screenshot()

                    # Send
                    file = discord.File(io.BytesIO(screenshot_bytes), filename=f"{user.display_name}_sheet.png")
                    await ctx.send(content=f"Here is the character sheet for {user.mention}:", file=file)
                    await msg.delete()
                finally:
                    await browser.close()

        except Exception as e:
            await msg.edit(content=f"An error occurred while generating the image: {e}")
            print(f"PrintCharacter Error: {e}")

async def setup(bot):
    await bot.add_cog(PrintCharacter(bot))
