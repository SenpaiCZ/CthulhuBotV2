import discord
from discord.ext import commands
import asyncio
from playwright.async_api import async_playwright
import io
import urllib.parse
import traceback
import re
import random
from loadnsave import (
    load_monsters_data, load_deities_data, load_spells_data, load_settings,
    load_archetype_data, load_pulp_talents_data, load_madness_insane_talent_data,
    load_manias_data, load_phobias_data, load_poisons_data, load_skills_data,
    load_inventions_data, load_years_data, load_weapons_data, load_occupations_data
)
import difflib

class Codex(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.playwright = None
        self.browser = None

    async def cog_load(self):
        """Initialize Playwright and Browser on Cog Load."""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch()
            print("Codex: Playwright browser launched.")
        except Exception as e:
            print(f"Codex: Failed to launch Playwright browser: {e}")

    async def cog_unload(self):
        """Clean up Playwright resources on Cog Unload."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print("Codex: Playwright browser closed.")

    async def _get_browser(self):
        """Ensure a valid browser instance is available."""
        if self.browser and self.browser.is_connected():
            return self.browser

        # Re-launch if not connected
        if self.playwright:
            await self.playwright.stop()

        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch()
            return self.browser
        except Exception as e:
            print(f"Codex: Failed to re-launch browser: {e}")
            raise e

    async def _render_and_send(self, ctx, url, name, type_name, interaction=None):
        msg = None
        if interaction:
             # If invoked from a component (SelectionView), we use followup
             # The view has likely already been disabled/edited by the caller
             pass
        elif ctx.interaction:
             # Slash Command
             await ctx.defer()
        else:
             # Prefix Command
             msg = await ctx.send(f"Consulting the archives for **{name}**... 📜")

        page = None
        try:
            settings = load_settings()
            port = settings.get('dashboard_port', 5000)
            full_url = f"http://127.0.0.1:{port}{url}"

            browser = await self._get_browser()
            # Viewport matching the CSS width + padding
            page = await browser.new_page(viewport={'width': 850, 'height': 1200})

            try:
                response = await page.goto(full_url, timeout=10000)
            except Exception as e:
                error_text = f"Error: Failed to load internal dashboard URL. Is the dashboard running?"
                if interaction: await interaction.followup.send(error_text, ephemeral=True)
                elif ctx.interaction: await ctx.send(error_text, ephemeral=True)
                elif msg: await msg.edit(content=error_text)
                print(f"Codex Navigation Error: {e}")
                return

            if not response or not response.ok:
                status = response.status if response else "Unknown"
                error_text = f"Error: Failed to find {type_name} '{name}' (Status: {status})."
                if interaction: await interaction.followup.send(error_text, ephemeral=True)
                elif ctx.interaction: await ctx.send(error_text, ephemeral=True)
                elif msg: await msg.edit(content=error_text)
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

            if interaction:
                await interaction.followup.send(content=f"Here is the entry for **{name}**:", file=file)
            elif ctx.interaction:
                await ctx.send(content=f"Here is the entry for **{name}**:", file=file)
            elif msg:
                await msg.delete()
                await ctx.send(content=f"Here is the entry for **{name}**:", file=file)

        except Exception as e:
            error_msg = f"An error occurred while generating the image: {e}"
            if interaction: await interaction.followup.send(error_msg, ephemeral=True)
            elif ctx.interaction: await ctx.send(error_msg, ephemeral=True)
            elif msg: await msg.edit(content=error_msg)
            print(f"Codex Error: {e}")
        finally:
            if page:
                try:
                    await page.close()
                except:
                    pass

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

    async def _handle_no_arg_lookup(self, ctx, loader_func, type_slug, data_key=None, flatten_pulp=False, title=None):
        """
        Handles the case where no argument is provided.
        Shows OptionsView: [List all] [Random one] [Cancel]
        """
        if not title:
            title = f"{type_slug.replace('_', ' ').capitalize()} List"

        view = OptionsView(ctx, loader_func, type_slug, data_key, flatten_pulp, self, title)
        ephemeral = False
        if ctx.interaction:
            ephemeral = True

        msg = await ctx.send(f"What would you like to do with {type_slug.replace('_', ' ')}s?", view=view, ephemeral=ephemeral)
        view.message = msg

    async def _handle_lookup(self, ctx, name, loader_func, type_slug, data_key=None, keys_only=False, flatten_pulp=False):
        """
        Generic lookup handler.
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

        kwargs = {}
        if ctx.interaction:
            kwargs['ephemeral'] = True

        if not matches:
            await ctx.send(f"No {type_slug.replace('_', ' ')} found matching '{name}'.", **kwargs)
            return

        if len(matches) == 1:
            target_name = matches[0]
            quoted_name = urllib.parse.quote(target_name)
            url = f"/render/{type_slug}?name={quoted_name}"
            await self._render_and_send(ctx, url, target_name, type_slug)
        elif len(matches) < 25:
             view = SelectionView(ctx, matches, type_slug, self)
             msg = await ctx.send(f"Multiple {type_slug.replace('_', ' ')}s found for '{name}'. Please select one:", view=view)
             view.message = msg
        else:
            response = f"Found {len(matches)} matches for '{name}'. Please be more specific:\n"
            match_list = ", ".join(matches)
            if len(match_list) > 1900:
                match_list = match_list[:1900] + "..."
            await ctx.send(response + match_list, **kwargs)

    @commands.hybrid_command(description="Displays a monster sheet.")
    async def monster(self, ctx, *, name: str = None):
        """Displays a monster sheet."""
        if name:
            await self._handle_lookup(ctx, name, load_monsters_data, "monster", data_key="monsters")
        else:
            await self._handle_no_arg_lookup(ctx, load_monsters_data, "monster", data_key="monsters")

    @commands.hybrid_command(description="Displays a spell.")
    async def spell(self, ctx, *, name: str = None):
        """Displays a spell."""
        if name:
            await self._handle_lookup(ctx, name, load_spells_data, "spell", data_key="spells")
        else:
            await self._handle_no_arg_lookup(ctx, load_spells_data, "spell", data_key="spells")

    @commands.hybrid_command(description="Displays a deity sheet.")
    async def deity(self, ctx, *, name: str = None):
        """Displays a deity sheet."""
        if name:
            await self._handle_lookup(ctx, name, load_deities_data, "deity", data_key="deities")
        else:
            await self._handle_no_arg_lookup(ctx, load_deities_data, "deity", data_key="deities")

    @commands.hybrid_command(description="Opens the Grimoire to view lists of all Codex entries.")
    async def grimoire(self, ctx):
        """Opens the Grimoire to view lists of all Codex entries."""
        view = GrimoireView(ctx, self)
        ephemeral = False
        if ctx.interaction:
            ephemeral = True
        msg = await ctx.send("What list would you like to see?", view=view, ephemeral=ephemeral)
        view.message = msg

    @commands.hybrid_command(aliases=['cArchetype', 'ainfo', 'archetypeinfo'], description="Displays a Pulp Cthulhu Archetype.")
    async def archetype(self, ctx, *, name: str = None):
        """Displays a Pulp Cthulhu Archetype."""
        if name:
            await self._handle_lookup(ctx, name, load_archetype_data, "archetype", keys_only=True)
        else:
            await self._handle_no_arg_lookup(ctx, load_archetype_data, "archetype")

    @commands.hybrid_command(aliases=['cTalents', 'tinfo', 'talents'], description="Displays a Pulp Talent.")
    async def talent(self, ctx, *, name: str = None):
        """Displays a Pulp Talent."""
        if name:
            await self._handle_lookup(ctx, name, load_pulp_talents_data, "pulp_talent", flatten_pulp=True)
        else:
            await self._handle_no_arg_lookup(ctx, load_pulp_talents_data, "pulp_talent", flatten_pulp=True)

    @commands.hybrid_command(aliases=['italent', 'insanetalent'], description="Displays an Insane Talent.")
    async def insane(self, ctx, *, name: str = None):
        """Displays an Insane Talent."""
        if name:
            await self._handle_lookup(ctx, name, load_madness_insane_talent_data, "insane_talent", keys_only=True)
        else:
            await self._handle_no_arg_lookup(ctx, load_madness_insane_talent_data, "insane_talent")

    @commands.hybrid_command(description="Displays a Mania.")
    async def mania(self, ctx, *, name: str = None):
        """Displays a Mania."""
        if name:
            await self._handle_lookup(ctx, name, load_manias_data, "mania", keys_only=True)
        else:
            await self._handle_no_arg_lookup(ctx, load_manias_data, "mania")

    @commands.hybrid_command(description="Displays a Phobia.")
    async def phobia(self, ctx, *, name: str = None):
        """Displays a Phobia."""
        if name:
            await self._handle_lookup(ctx, name, load_phobias_data, "phobia", keys_only=True)
        else:
            await self._handle_no_arg_lookup(ctx, load_phobias_data, "phobia")

    @commands.hybrid_command(aliases=['poisons'], description="Displays a Poison.")
    async def poison(self, ctx, *, name: str = None):
        """Displays a Poison."""
        if name:
            await self._handle_lookup(ctx, name, load_poisons_data, "poison", keys_only=True)
        else:
            await self._handle_no_arg_lookup(ctx, load_poisons_data, "poison")

    @commands.hybrid_command(aliases=['skillinfo'], description="Displays a Skill description.")
    async def skill(self, ctx, *, name: str = None):
        """Displays a Skill description."""
        if name:
            await self._handle_lookup(ctx, name, load_skills_data, "skill", keys_only=True)
        else:
            await self._handle_no_arg_lookup(ctx, load_skills_data, "skill")

    @commands.hybrid_command(aliases=['inventions'], description="Displays Inventions for a specific decade (e.g., 1920s).")
    async def invention(self, ctx, *, decade: str = None):
        """Displays Inventions for a specific decade (e.g., 1920s)."""
        if decade:
            # Handle "1925" -> "1920s" logic
            # Strip non-digits to handle "1920s" or "c. 1920" if users get creative, though simple is better
            # Just take digits
            year_match = re.search(r'\d{3,4}', decade)
            if year_match:
                try:
                    year_val = int(year_match.group(0))
                    # Round down to nearest decade
                    decade_val = (year_val // 10) * 10
                    decade = f"{decade_val}s"
                except ValueError:
                    pass

            await self._handle_lookup(ctx, decade, load_inventions_data, "invention", keys_only=True)
        else:
            await self._handle_no_arg_lookup(ctx, load_inventions_data, "invention")

    @commands.hybrid_command(aliases=['years'], description="Displays events for a specific year (e.g., 1920).")
    async def year(self, ctx, *, year: str = None):
        """Displays events for a specific year (e.g., 1920)."""
        if year:
            await self._handle_lookup(ctx, year, load_years_data, "year", keys_only=True)
        else:
            await self._handle_no_arg_lookup(ctx, load_years_data, "year")

    @commands.hybrid_command(aliases=["firearm", "firearms", "weapons"], description="Displays a weapon.")
    async def weapon(self, ctx, *, name: str = None):
        """Displays a weapon."""
        if name:
            await self._handle_lookup(ctx, name, load_weapons_data, "weapon", keys_only=True)
        else:
             await self._handle_no_arg_lookup(ctx, load_weapons_data, "weapon")

    @commands.hybrid_command(aliases=["cocc","oinfo", "occupations"], description="Displays an occupation.")
    async def occupation(self, ctx, *, name: str = None):
        """Displays an occupation."""
        if name:
            await self._handle_lookup(ctx, name, load_occupations_data, "occupation", keys_only=True)
        else:
            await self._handle_no_arg_lookup(ctx, load_occupations_data, "occupation")

class PaginatedListView(discord.ui.View):
    def __init__(self, ctx, items, title, per_page=20):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.items = items
        self.title = title
        self.per_page = per_page
        self.current_page = 0
        self.total_pages = max(1, (len(items) + per_page - 1) // per_page)
        self.message = None

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == self.total_pages - 1
        self.page_counter.label = f"Page {self.current_page + 1}/{self.total_pages}"

    def get_embed(self):
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_items = self.items[start:end]
        description = "\n".join(page_items)
        if not description:
            description = "No items found."
        embed = discord.Embed(title=self.title, description=description, color=discord.Color.blue())
        embed.set_footer(text=f"Total: {len(self.items)}")
        return embed

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
             return await interaction.response.send_message("This isn't for you!", ephemeral=True)
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Page 1/1", style=discord.ButtonStyle.secondary, disabled=True)
    async def page_counter(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
             return await interaction.response.send_message("This isn't for you!", ephemeral=True)
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
             return await interaction.response.send_message("This isn't for you!", ephemeral=True)

        if self.ctx.interaction:
            # Ephemeral messages cannot be deleted by bots, so we edit them to "close" the view.
            await interaction.response.edit_message(content="List closed.", embed=None, view=None)
        else:
            try:
                await interaction.message.delete()
            except:
                pass
        self.stop()

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.delete()
            except:
                pass
        self.stop()

class OptionsView(discord.ui.View):
    def __init__(self, ctx, loader_func, type_slug, data_key, flatten_pulp, cog, title):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.loader_func = loader_func
        self.type_slug = type_slug
        self.data_key = data_key
        self.flatten_pulp = flatten_pulp
        self.cog = cog
        self.title = title
        self.message = None

    @discord.ui.button(label="List all", style=discord.ButtonStyle.success)
    async def list_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
             return await interaction.response.send_message("This isn't for you!", ephemeral=True)

        data = await self.loader_func()
        choices = []
        if self.flatten_pulp:
            # Pulp talents logic
            pulp_map = {}
            for category, talents in data.items():
                for t_str in talents:
                    match = re.match(r'\*\*(.*?)\*\*:\s*(.*)', t_str)
                    if match:
                         pulp_map[match.group(1)] = match.group(1)
            choices = list(pulp_map.keys())
        elif self.data_key:
             items = data.get(self.data_key, [])
             entry_key = self.type_slug + "_entry"
             for item in items:
                entry = item.get(entry_key)
                if entry and entry.get('name'):
                    choices.append(entry['name'])
        else:
             # For inventions, include the count
             if self.type_slug == "invention":
                 choices = []
                 for k, v in data.items():
                     choices.append(f"{k} ({len(v)} entries)")
             else:
                 choices = list(data.keys())

        choices.sort()
        view = PaginatedListView(self.ctx, choices, self.title)
        view.update_buttons()
        embed = view.get_embed()
        await interaction.response.edit_message(content=None, embed=embed, view=view)
        view.message = interaction.message

    @discord.ui.button(label="Random one", style=discord.ButtonStyle.primary)
    async def random_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
             return await interaction.response.send_message("This isn't for you!", ephemeral=True)

        data = await self.loader_func()
        choices = []
        if self.flatten_pulp:
            for category, talents in data.items():
                for t_str in talents:
                    match = re.match(r'\*\*(.*?)\*\*:\s*(.*)', t_str)
                    if match:
                        choices.append(match.group(1))
        elif self.data_key:
             items = data.get(self.data_key, [])
             entry_key = self.type_slug + "_entry"
             for item in items:
                entry = item.get(entry_key)
                if entry and entry.get('name'):
                    choices.append(entry['name'])
        else:
             choices = list(data.keys())

        if not choices:
            await interaction.response.send_message("No entries found.", ephemeral=True)
            return

        target_name = random.choice(choices)

        # Disable view
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        # Trigger render
        quoted_name = urllib.parse.quote(target_name)
        url = f"/render/{self.type_slug}?name={quoted_name}"
        await self.cog._render_and_send(self.ctx, url, target_name, self.type_slug, interaction=interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
             return await interaction.response.send_message("This isn't for you!", ephemeral=True)

        if self.ctx.interaction:
            await interaction.response.edit_message(content="Dismissed.", embed=None, view=None)
        else:
            try:
                await interaction.message.delete()
            except:
                pass
        self.stop()

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.delete()
            except:
                pass
        self.stop()

class ConfirmationView(discord.ui.View):
    def __init__(self, ctx, items, title):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.items = items
        self.title = title
        self.message = None

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
             return await interaction.response.send_message("This isn't for you!", ephemeral=True)

        view = PaginatedListView(self.ctx, self.items, self.title)
        view.update_buttons()
        embed = view.get_embed()
        await interaction.response.edit_message(content=None, embed=embed, view=view)
        # Store message for timeout handling
        view.message = interaction.message

    @discord.ui.button(label="No", style=discord.ButtonStyle.danger)
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
             return await interaction.response.send_message("This isn't for you!", ephemeral=True)

        if self.ctx.interaction:
            # Ephemeral messages cannot be deleted by bots, so we edit them to "close" the view.
            await interaction.response.edit_message(content="Dismissed.", embed=None, view=None)
        else:
            try:
                await interaction.message.delete()
            except:
                pass
        self.stop()

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.delete()
            except:
                pass
        self.stop()

class GrimoireView(discord.ui.View):
    def __init__(self, ctx, cog):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.cog = cog
        self.message = None

    async def _launch_list(self, interaction, loader, title, data_key=None, flatten_pulp=False, type_slug=None):
        data = await loader()
        choices = []
        if flatten_pulp:
            # Pulp talents logic
            pulp_map = {}
            for category, talents in data.items():
                for t_str in talents:
                    match = re.match(r'\*\*(.*?)\*\*:\s*(.*)', t_str)
                    if match:
                         pulp_map[match.group(1)] = match.group(1)
            choices = list(pulp_map.keys())
        elif data_key:
             items = data.get(data_key, [])
             # Assuming standard structure
             if data_key == "monsters":
                 entry_key = "monster_entry"
             elif data_key == "spells":
                 entry_key = "spell_entry"
             elif data_key == "deities":
                 entry_key = "deity_entry"
             else:
                 entry_key = data_key[:-1] + "_entry"

             for item in items:
                entry = item.get(entry_key)
                if entry and entry.get('name'):
                    choices.append(entry['name'])
        else:
             # For inventions, include the count
             if type_slug == "invention":
                 for k, v in data.items():
                     choices.append(f"{k} ({len(v)} entries)")
             else:
                 choices = list(data.keys())

        choices.sort()
        view = PaginatedListView(self.ctx, choices, title)
        view.update_buttons()
        embed = view.get_embed()
        await interaction.response.edit_message(content=None, embed=embed, view=view)
        view.message = interaction.message

    # Row 0
    @discord.ui.button(label="Monsters", style=discord.ButtonStyle.primary, row=0)
    async def monsters_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return
        await self._launch_list(interaction, load_monsters_data, "Monsters List", data_key="monsters")

    @discord.ui.button(label="Deities", style=discord.ButtonStyle.primary, row=0)
    async def deities_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return
        await self._launch_list(interaction, load_deities_data, "Deities List", data_key="deities")

    @discord.ui.button(label="Archetypes", style=discord.ButtonStyle.secondary, row=0)
    async def archetypes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return
        await self._launch_list(interaction, load_archetype_data, "Archetypes List")

    @discord.ui.button(label="Occupations", style=discord.ButtonStyle.secondary, row=0)
    async def occupations_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return
        await self._launch_list(interaction, load_occupations_data, "Occupations List")

    # Row 1
    @discord.ui.button(label="Spells", style=discord.ButtonStyle.primary, row=1)
    async def spells_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return
        await self._launch_list(interaction, load_spells_data, "Spells List", data_key="spells")

    @discord.ui.button(label="Talents", style=discord.ButtonStyle.secondary, row=1)
    async def talents_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return
        await self._launch_list(interaction, load_pulp_talents_data, "Pulp Talents List", flatten_pulp=True)

    @discord.ui.button(label="Insane Talents", style=discord.ButtonStyle.danger, row=1)
    async def insane_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return
        await self._launch_list(interaction, load_madness_insane_talent_data, "Insane Talents List")

    @discord.ui.button(label="Skills", style=discord.ButtonStyle.secondary, row=1)
    async def skills_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return
        await self._launch_list(interaction, load_skills_data, "Skills List")

    # Row 2
    @discord.ui.button(label="Weapons", style=discord.ButtonStyle.secondary, row=2)
    async def weapons_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return
        await self._launch_list(interaction, load_weapons_data, "Weapons List")

    @discord.ui.button(label="Poisons", style=discord.ButtonStyle.secondary, row=2)
    async def poisons_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return
        await self._launch_list(interaction, load_poisons_data, "Poisons List")

    @discord.ui.button(label="Inventions", style=discord.ButtonStyle.secondary, row=2)
    async def inventions_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return
        await self._launch_list(interaction, load_inventions_data, "Inventions List", type_slug="invention")

    # Row 3
    @discord.ui.button(label="Manias", style=discord.ButtonStyle.danger, row=3)
    async def manias_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return
        await self._launch_list(interaction, load_manias_data, "Manias List")

    @discord.ui.button(label="Phobias", style=discord.ButtonStyle.danger, row=3)
    async def phobias_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return
        await self._launch_list(interaction, load_phobias_data, "Phobias List")

    @discord.ui.button(label="Years", style=discord.ButtonStyle.secondary, row=3)
    async def years_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return
        await self._launch_list(interaction, load_years_data, "Years List")

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.delete()
            except:
                pass
        self.stop()


class SelectionView(discord.ui.View):
    def __init__(self, ctx, options, type_name, cog):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.cog = cog
        self.type_name = type_name
        self.message = None

        # Create select menu
        select = discord.ui.Select(placeholder=f"Select a {type_name.replace('_', ' ')}...", min_values=1, max_values=1)

        for option in options:
            # Select options have a max length of 100 chars for label
            label = option[:100]
            select.add_option(label=label, value=option)

        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        # Allow only the author to select
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("This selection is not for you.", ephemeral=True)
            return

        selected_name = interaction.data['values'][0]

        # Disable view and acknowledge interaction
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        # Trigger render, passing interaction so we can followup
        quoted_name = urllib.parse.quote(selected_name)
        url = f"/render/{self.type_name}?name={quoted_name}"

        # We pass interaction to handle the followup response
        await self.cog._render_and_send(self.ctx, url, selected_name, self.type_name, interaction=interaction)

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.delete()
            except:
                pass
        self.stop()

async def setup(bot):
    await bot.add_cog(Codex(bot))
