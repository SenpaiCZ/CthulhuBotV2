import discord
from discord.ext import commands
import asyncio
from playwright.async_api import async_playwright
import io
import urllib.parse
import re
from loadnsave import (
    load_monsters_data, load_deities_data, load_spells_data, load_settings,
    load_archetype_data, load_pulp_talents_data, load_madness_insane_talent_data,
    load_manias_data, load_phobias_data, load_poisons_data, load_skills_data,
    load_inventions_data, load_years_data
)
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

        if not partial_matches:
            # difflib.get_close_matches(word, possibilities, n, cutoff)
            fuzzy = difflib.get_close_matches(query, choices, n=5, cutoff=0.6)
            return fuzzy

        partial_matches.sort()
        return partial_matches

    async def _handle_lookup(self, ctx, name, loader_func, type_slug, data_key=None, keys_only=False, flatten_pulp=False):
        """
        Generic lookup handler.
        loader_func: async function to load data
        type_slug: url slug part (e.g. 'monster', 'spell')
        data_key: if the loaded json has a wrapper key (e.g. 'monsters'), provide it.
        keys_only: if the data is a flat dict, use keys as choices.
        flatten_pulp: special handling for pulp talents (Dict[Category, List[String]])
        """
        data = await loader_func()

        choices = []
        if flatten_pulp:
            # Pulp talents: Dict[Category, List[String "Name: Desc"]]
            pulp_map = {} # Name -> Full String (or Name)
            for category, talents in data.items():
                for t_str in talents:
                    match = re.match(r'\*\*(.*?)\*\*:\s*(.*)', t_str)
                    if match:
                        t_name = match.group(1)
                        pulp_map[t_name] = t_name # Just store name for matching
            choices = list(pulp_map.keys())
        elif data_key:
            # List of objects
            items = data.get(data_key, [])
            # Assuming standard structure {entry: {name: ...}}
            # Need custom logic if different
            entry_key = type_slug + "_entry"
            for item in items:
                entry = item.get(entry_key)
                if entry and entry.get('name'):
                    choices.append(entry['name'])
        elif keys_only:
            # Dict[Name, Data]
            choices = list(data.keys())
        else:
            # Should not happen with current usage, but fallback
            choices = list(data.keys())

        matches = self._find_matches(name, choices)

        if not matches:
            await ctx.send(f"No {type_slug.replace('_', ' ')} found matching '{name}'.")
            return

        if len(matches) == 1:
            target_name = matches[0]
            quoted_name = urllib.parse.quote(target_name)
            url = f"/render/{type_slug}?name={quoted_name}"
            await self._render_and_send(ctx, url, target_name, type_slug)
        elif len(matches) < 25:
             view = SelectionView(ctx, matches, type_slug, self)
             await ctx.send(f"Multiple {type_slug.replace('_', ' ')}s found for '{name}'. Please select one:", view=view)
        else:
            response = f"Found {len(matches)} matches for '{name}'. Please be more specific:\n"
            match_list = ", ".join(matches)
            if len(match_list) > 1900:
                match_list = match_list[:1900] + "..."
            await ctx.send(response + match_list)

    @commands.command()
    async def monster(self, ctx, *, name: str):
        """Displays a monster sheet."""
        await self._handle_lookup(ctx, name, load_monsters_data, "monster", data_key="monsters")

    @commands.command()
    async def spell(self, ctx, *, name: str):
        """Displays a spell."""
        await self._handle_lookup(ctx, name, load_spells_data, "spell", data_key="spells")

    @commands.command()
    async def deity(self, ctx, *, name: str):
        """Displays a deity sheet."""
        await self._handle_lookup(ctx, name, load_deities_data, "deity", data_key="deities")

    @commands.command(aliases=['cArchetype', 'ainfo', 'archetypeinfo'])
    async def archetype(self, ctx, *, name: str):
        """Displays a Pulp Cthulhu Archetype."""
        await self._handle_lookup(ctx, name, load_archetype_data, "archetype", keys_only=True)

    @commands.command(aliases=['cTalents', 'tinfo', 'talents'])
    async def talent(self, ctx, *, name: str):
        """Displays a Pulp Talent."""
        await self._handle_lookup(ctx, name, load_pulp_talents_data, "pulp_talent", flatten_pulp=True)

    @commands.command(aliases=['italent', 'insanetalent'])
    async def insane(self, ctx, *, name: str):
        """Displays an Insane Talent."""
        await self._handle_lookup(ctx, name, load_madness_insane_talent_data, "insane_talent", keys_only=True)

    @commands.command()
    async def mania(self, ctx, *, name: str):
        """Displays a Mania."""
        await self._handle_lookup(ctx, name, load_manias_data, "mania", keys_only=True)

    @commands.command()
    async def phobia(self, ctx, *, name: str):
        """Displays a Phobia."""
        await self._handle_lookup(ctx, name, load_phobias_data, "phobia", keys_only=True)

    @commands.command(aliases=['poisons'])
    async def poison(self, ctx, *, name: str):
        """Displays a Poison."""
        await self._handle_lookup(ctx, name, load_poisons_data, "poison", keys_only=True)

    @commands.command(aliases=['skillinfo'])
    async def skill(self, ctx, *, name: str):
        """Displays a Skill description."""
        await self._handle_lookup(ctx, name, load_skills_data, "skill", keys_only=True)

    @commands.command(aliases=['inventions'])
    async def invention(self, ctx, *, decade: str):
        """Displays Inventions for a specific decade (e.g., 1920s)."""
        # "1920" -> try "1920s"
        if not decade.endswith('s') and decade.isdigit():
             decade += 's'
        await self._handle_lookup(ctx, decade, load_inventions_data, "invention", keys_only=True)

    @commands.command(aliases=['years'])
    async def year(self, ctx, *, year: str):
        """Displays events for a specific year (e.g., 1920)."""
        await self._handle_lookup(ctx, year, load_years_data, "year", keys_only=True)


class SelectionView(discord.ui.View):
    def __init__(self, ctx, options, type_name, cog):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.cog = cog
        self.type_name = type_name

        # Create select menu
        select = discord.ui.Select(placeholder=f"Select a {type_name.replace('_', ' ')}...", min_values=1, max_values=1)

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
