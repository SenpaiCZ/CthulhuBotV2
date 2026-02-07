import discord
from discord.ext import commands
import asyncio
from playwright.async_api import async_playwright
import io
import urllib.parse
from loadnsave import load_monsters_data, load_deities_data, load_settings

class Codex(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _render_and_send(self, ctx, url, name, type_name):
        msg = await ctx.send(f"Consulting the archives for {name}... 📜")

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                try:
                    # Viewport slightly wider than the element (800px) + padding
                    page = await browser.new_page(viewport={'width': 850, 'height': 1200})

                    try:
                        response = await page.goto(url, timeout=10000) # 10s timeout
                    except Exception as e:
                         await msg.edit(content=f"Error: Failed to load internal dashboard URL. Is the dashboard running?")
                         print(f"Codex Navigation Error: {e}")
                         return

                    if not response or not response.ok:
                         status = response.status if response else "Unknown"
                         await msg.edit(content=f"Error: Failed to find {type_name} '{name}' (Status: {status}).")
                         return

                    # Wait for element to be visible
                    try:
                        element = await page.wait_for_selector('.coc-sheet', timeout=5000)
                    except:
                        element = None

                    if not element:
                         # Fallback to full page if selector fails
                         screenshot_bytes = await page.screenshot(full_page=True)
                    else:
                         screenshot_bytes = await element.screenshot()

                    file = discord.File(io.BytesIO(screenshot_bytes), filename=f"{name.replace(' ', '_')}_{type_name}.png")
                    await ctx.send(content=f"Here is the entry for **{name}**:", file=file)
                    await msg.delete()

                finally:
                    await browser.close()
        except Exception as e:
            await msg.edit(content=f"An error occurred while generating the image: {e}")
            print(f"Codex Error: {e}")

    @commands.command()
    async def monster(self, ctx, *, name: str):
        """
        Displays a monster sheet from the grimoire.
        Usage: !monster <name>
        """
        if not ctx.guild:
            # Allow in DMs too? Why not.
            pass

        data = await load_monsters_data()
        monsters = data.get('monsters', [])

        matches = []
        exact_match = None
        name_lower = name.lower()

        for item in monsters:
            m = item.get('monster_entry')
            if not m: continue

            m_name = m.get('name', '')
            if m_name.lower() == name_lower:
                exact_match = m_name
                break

            if name_lower in m_name.lower():
                matches.append(m_name)

        target_name = None
        if exact_match:
            target_name = exact_match
        elif len(matches) == 1:
            target_name = matches[0]
        elif len(matches) > 1:
            # Too many matches
            matches = matches[:10]
            await ctx.send(f"Multiple monsters found for '{name}'. Did you mean:\n" + "\n".join([f"- {m}" for m in matches]))
            return
        else:
            await ctx.send(f"No monster found matching '{name}'.")
            return

        settings = load_settings()
        port = settings.get('dashboard_port', 5000)

        # Use quoted name
        quoted_name = urllib.parse.quote(target_name)
        url = f"http://127.0.0.1:{port}/render/monster?name={quoted_name}"

        await self._render_and_send(ctx, url, target_name, "monster")

    @commands.command()
    async def deity(self, ctx, *, name: str):
        """
        Displays a deity sheet from the pantheon.
        Usage: !deity <name>
        """
        data = await load_deities_data()
        deities = data.get('deities', [])

        matches = []
        exact_match = None
        name_lower = name.lower()

        for item in deities:
            d = item.get('deity_entry')
            if not d: continue

            d_name = d.get('name', '')
            if d_name.lower() == name_lower:
                exact_match = d_name
                break

            if name_lower in d_name.lower():
                matches.append(d_name)

        target_name = None
        if exact_match:
            target_name = exact_match
        elif len(matches) == 1:
            target_name = matches[0]
        elif len(matches) > 1:
             matches = matches[:10]
             await ctx.send(f"Multiple deities found for '{name}'. Did you mean:\n" + "\n".join([f"- {m}" for m in matches]))
             return
        else:
            await ctx.send(f"No deity found matching '{name}'.")
            return

        settings = load_settings()
        port = settings.get('dashboard_port', 5000)

        quoted_name = urllib.parse.quote(target_name)
        url = f"http://127.0.0.1:{port}/render/deity?name={quoted_name}"

        await self._render_and_send(ctx, url, target_name, "deity")

async def setup(bot):
    await bot.add_cog(Codex(bot))
