import discord
from discord.ext import commands
import asyncio
from playwright.async_api import async_playwright
import io
import urllib.parse
from loadnsave import load_monsters_data, load_deities_data, load_spells_data, load_settings
import difflib

class Codex(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _render_and_send(self, ctx, url, name, type_name):
        msg = await ctx.send(f"Consulting the archives for **{name}**... 📜")

        try:
            settings = load_settings()
            port = settings.get('dashboard_port', 5000)
            full_url = f"http://127.0.0.1:{port}{url}"

            async with async_playwright() as p:
                browser = await p.chromium.launch()
                try:
                    # Viewport matching the CSS width + padding
                    page = await browser.new_page(viewport={'width': 850, 'height': 1200})

                    try:
                        response = await page.goto(full_url, timeout=10000)
                    except Exception as e:
                        await msg.edit(content=f"Error: Failed to load internal dashboard URL. Is the dashboard running?")
                        print(f"Codex Navigation Error: {e}")
                        return

                    if not response or not response.ok:
                        status = response.status if response else "Unknown"
                        await msg.edit(content=f"Error: Failed to find {type_name} '{name}' (Status: {status}).")
                        return

                    try:
                        element = await page.wait_for_selector('.coc-sheet', timeout=5000)
                    except:
                        element = None

                    if not element:
                        screenshot_bytes = await page.screenshot(full_page=True)
                    else:
                        screenshot_bytes = await element.screenshot()

                    file = discord.File(io.BytesIO(screenshot_bytes), filename=f"{name.replace(' ', '_')}_{type_name}.png")
                    await msg.delete()
                    await ctx.send(content=f"Here is the entry for **{name}**:", file=file)

                finally:
                    await browser.close()
        except Exception as e:
            try:
                await msg.edit(content=f"An error occurred while generating the image: {e}")
            except:
                await ctx.send(f"An error occurred while generating the image: {e}")
            print(f"Codex Error: {e}")

    @commands.command()
    async def monster(self, ctx, *, name: str):
        """
        Displays a monster sheet from the grimoire.
        Usage: !monster <name>
        """
        data = await load_monsters_data()
        monsters = data.get('monsters', [])

        # Build map of name -> full object
        monster_map = {}
        for item in monsters:
            m = item.get('monster_entry')
            if m and m.get('name'):
                monster_map[m['name']] = m

        matches = self._find_matches(name, list(monster_map.keys()))

        if not matches:
            await ctx.send(f"No monster found matching '{name}'.")
            return

        if len(matches) == 1:
            target_name = matches[0]
            quoted_name = urllib.parse.quote(target_name)
            url = f"/render/monster?name={quoted_name}"
            await self._render_and_send(ctx, url, target_name, "monster")
        elif len(matches) < 25:
            # Dropdown Selector
            view = SelectionView(ctx, matches, "monster", self)
            await ctx.send(f"Multiple monsters found for '{name}'. Please select one:", view=view)
        else:
            # Too many matches, list them textually
            response = f"Found {len(matches)} matches for '{name}'. Please be more specific:\n"
            # Join as many as fit
            match_list = ", ".join(matches)
            if len(match_list) > 1900:
                match_list = match_list[:1900] + "..."
            await ctx.send(response + match_list)

    @commands.command()
    async def spell(self, ctx, *, name: str):
        """
        Displays a spell from the archives.
        Usage: !spell <name>
        """
        data = await load_spells_data()
        spells = data.get('spells', [])

        spell_map = {}
        for item in spells:
            s = item.get('spell_entry')
            if s and s.get('name'):
                spell_map[s['name']] = s

        matches = self._find_matches(name, list(spell_map.keys()))

        if not matches:
            await ctx.send(f"No spell found matching '{name}'.")
            return

        if len(matches) == 1:
            target_name = matches[0]
            quoted_name = urllib.parse.quote(target_name)
            url = f"/render/spell?name={quoted_name}"
            await self._render_and_send(ctx, url, target_name, "spell")
        elif len(matches) < 25:
             view = SelectionView(ctx, matches, "spell", self)
             await ctx.send(f"Multiple spells found for '{name}'. Please select one:", view=view)
        else:
            response = f"Found {len(matches)} matches for '{name}'. Please be more specific:\n"
            match_list = ", ".join(matches)
            if len(match_list) > 1900:
                match_list = match_list[:1900] + "..."
            await ctx.send(response + match_list)

    @commands.command()
    async def deity(self, ctx, *, name: str):
        """
        Displays a deity sheet from the pantheon.
        Usage: !deity <name>
        """
        data = await load_deities_data()
        deities = data.get('deities', [])

        deity_map = {}
        for item in deities:
            d = item.get('deity_entry')
            if d and d.get('name'):
                deity_map[d['name']] = d

        matches = self._find_matches(name, list(deity_map.keys()))

        if not matches:
            await ctx.send(f"No deity found matching '{name}'.")
            return

        if len(matches) == 1:
            target_name = matches[0]
            quoted_name = urllib.parse.quote(target_name)
            url = f"/render/deity?name={quoted_name}"
            await self._render_and_send(ctx, url, target_name, "deity")
        elif len(matches) < 25:
             view = SelectionView(ctx, matches, "deity", self)
             await ctx.send(f"Multiple deities found for '{name}'. Please select one:", view=view)
        else:
            response = f"Found {len(matches)} matches for '{name}'. Please be more specific:\n"
            match_list = ", ".join(matches)
            if len(match_list) > 1900:
                match_list = match_list[:1900] + "..."
            await ctx.send(response + match_list)

    def _find_matches(self, query, choices):
        query_lower = query.lower()
        exact_match = None
        partial_matches = []

        for choice in choices:
            choice_lower = choice.lower()
            if choice_lower == query_lower:
                exact_match = choice
                break # Prioritize exact match
            if query_lower in choice_lower:
                partial_matches.append(choice)

        if exact_match:
            return [exact_match]

        # If no substring matches, try fuzzy? Or just stick to substring?
        # User asked for "Fuzzy/partial matching".
        # Usually substring is "partial".
        # Let's add fuzzy if no partial matches found.
        if not partial_matches:
            # difflib.get_close_matches(word, possibilities, n, cutoff)
            fuzzy = difflib.get_close_matches(query, choices, n=5, cutoff=0.6)
            return fuzzy

        partial_matches.sort()
        return partial_matches

class SelectionView(discord.ui.View):
    def __init__(self, ctx, options, type_name, cog):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.cog = cog
        self.type_name = type_name

        # Create select menu
        select = discord.ui.Select(placeholder=f"Select a {type_name}...", min_values=1, max_values=1)

        for option in options:
            # Select options have a max length of 100 chars for label
            label = option[:100]
            select.add_option(label=label, value=option)

        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("This selection is not for you.", ephemeral=True)
            return

        selected_name = interaction.data['values'][0]

        # Disable view
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        # Trigger render
        quoted_name = urllib.parse.quote(selected_name)
        url = f"/render/{self.type_name}?name={quoted_name}"
        await self.cog._render_and_send(self.ctx, url, selected_name, self.type_name)

    async def on_timeout(self):
        # Disable select on timeout
        for child in self.children:
            child.disabled = True
        try:
            # Need to fetch original message to edit it?
            # View is attached to the message.
            # discord.ui.View doesn't store the message by default unless we do.
            pass
        except:
            pass

async def setup(bot):
    await bot.add_cog(Codex(bot))
