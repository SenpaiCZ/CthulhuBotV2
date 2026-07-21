import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from playwright.async_api import async_playwright
import io
import os
import urllib.parse
import traceback
import re
from commands._codex_embeds import (
    create_monster_embed, create_deity_embed, create_spell_embed,
    create_weapon_embed, create_occupation_embed, create_archetype_embed,
    create_generic_embed, create_timeline_embed
)
from commands._codex_views import RenderView, OptionsView, SelectionView, CodexView
from loadnsave import (
    load_monsters_data, load_deities_data, load_spells_data, load_settings,
    load_archetype_data, load_pulp_talents_data, load_madness_insane_talent_data,
    load_manias_data, load_phobias_data, load_poisons_data, load_skills_data,
    load_inventions_data, load_years_data, load_weapons_data, load_occupations_data,
    load_player_stats, save_player_stats
)
from rapidfuzz import process, fuzz
from dashboard.file_utils import sanitize_filename

class Codex(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Codex"
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

    async def _get_autocomplete_choices(self, current: str, loader_func, data_key=None, flatten_pulp=False, keys_only=False, is_invention=False):
        """Helper to generate autocomplete choices using RapidFuzz."""
        data = await loader_func()
        raw_choices = []

        if flatten_pulp:
             pulp_map = {}
             for category, talents in data.items():
                 for t_str in talents:
                     match = re.match(r'\*\*(.*?)\*\*:\s*(.*)', t_str)
                     if match:
                          pulp_map[match.group(1)] = match.group(1)
             raw_choices = list(pulp_map.keys())
        elif data_key:
             items = data.get(data_key, [])
             if data_key == "monsters": entry_key = "monster_entry"
             elif data_key == "spells": entry_key = "spell_entry"
             elif data_key == "deities": entry_key = "deity_entry"
             else: entry_key = data_key[:-1] + "_entry"

             for item in items:
                entry = item.get(entry_key)
                if entry and entry.get('name'):
                    raw_choices.append(entry['name'])
        elif keys_only or is_invention:
             raw_choices = list(data.keys())
        else:
             raw_choices = list(data.keys())

        if not current:
            # Return first 25 sorted alphabetically
            sorted_choices = sorted(raw_choices)[:25]
            if is_invention:
                return [app_commands.Choice(name=f"{c} ({len(data.get(c, []))} entries)", value=c) for c in sorted_choices]
            return [app_commands.Choice(name=c[:100], value=c[:100]) for c in sorted_choices]

        # Use rapidfuzz to find best matches
        matches = process.extract(current, raw_choices, scorer=fuzz.WRatio, limit=25)

        results = []
        for m in matches:
            name = m[0]
            value = m[0]
            if is_invention:
                name = f"{value} ({len(data.get(value, []))} entries)"
            results.append(app_commands.Choice(name=name[:100], value=value[:100]))

        return results

    def _get_image_file(self, type_slug, name):
        """Checks if a local image exists and returns a discord.File object."""
        # Sanitize filename to match dashboard/file_utils logic
        safe_name = sanitize_filename(name)

        # Dashboard uses 'images' folder at root
        target_dir = os.path.join("images", type_slug)
        if not os.path.exists(target_dir):
            return None

        # Check extensions
        for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
            filename = f"{safe_name}{ext}"
            path = os.path.join(target_dir, filename)
            if os.path.exists(path):
                return discord.File(path, filename=filename)

        return None

    def _get_entry_data(self, data, name, type_slug, data_key=None, flatten_pulp=False, keys_only=False):
        """Extracts the specific data dictionary for the named entry."""
        if flatten_pulp:
             for category, talents in data.items():
                 for t_str in talents:
                     match = re.match(r'\*\*(.*?)\*\*:\s*(.*)', t_str)
                     if match:
                          t_name = match.group(1)
                          if t_name == name:
                              return {"name": t_name, "description": match.group(2), "category": category}
        elif data_key:
             items = data.get(data_key, [])
             entry_key = type_slug + "_entry"
             if type_slug == "monster": entry_key = "monster_entry"
             elif type_slug == "spell": entry_key = "spell_entry"
             elif type_slug == "deity": entry_key = "deity_entry"

             for item in items:
                entry = item.get(entry_key)
                if entry and entry.get('name') == name:
                    return entry
        elif keys_only:
             # keys_only implies the data is Dict[Name, Info] or List[Name]
             if isinstance(data, dict):
                 return data.get(name)
        elif type_slug == "invention": # Inventions are Dict[decade, list]
             return data.get(name)
        else:
             # Default dict lookup
             return data.get(name)
        return None

    async def _display_entry(self, interaction: discord.Interaction, name, type_slug, data, ephemeral=False):
        """Generates an Embed and sends it with a view to show the poster."""

        # 1. Get Image File
        file = self._get_image_file(type_slug, name)

        # 2. Build Embed
        embed = None
        if type_slug == "monster":
            embed = create_monster_embed(data, name, file)
        elif type_slug == "deity":
            embed = create_deity_embed(data, name, file)
        elif type_slug == "spell":
            embed = create_spell_embed(data, name, file)
        elif type_slug == "weapon":
            embed = create_weapon_embed(data, name, file)
        elif type_slug == "occupation":
            embed = create_occupation_embed(data, name, file)
        elif type_slug == "archetype":
            embed = create_archetype_embed(data, name, file)
        elif type_slug in ["invention", "year"]:
            embed = create_timeline_embed(data, name, type_slug, file)
        else:
            embed = create_generic_embed(data, name, type_slug, file)

        # 3. Create View
        view = RenderView(interaction.user, self, name, type_slug)

        # 4. Send
        kwargs = {"embed": embed, "view": view, "ephemeral": ephemeral}
        if file:
            kwargs["file"] = file

        if not interaction.response.is_done():
            await interaction.response.send_message(**kwargs)
            view.message = await interaction.original_response()
        else:
            # remove ephemeral if it's a kwarg to send_message but not followup?
            # followup.send supports ephemeral
            msg = await interaction.followup.send(**kwargs)
            view.message = msg

    async def _render_poster(self, interaction: discord.Interaction, url, name, type_name, ephemeral=True):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)

        # Send a placeholder if using followup, but deferred implies loading state on client side usually.
        # But if we are called from a button that deferred, we are good.

        page = None
        try:
            settings = load_settings()
            port = settings.get('dashboard_port', 5000)
            full_url = f"http://127.0.0.1:{port}{url}"

            browser = await self._get_browser()
            page = await browser.new_page(viewport={'width': 1100, 'height': 1200})

            try:
                response = await page.goto(full_url, timeout=10000)
            except Exception as e:
                error_text = f"Error: Failed to load internal dashboard URL. Is the dashboard running?"
                await interaction.followup.send(error_text, ephemeral=True)
                print(f"Codex Navigation Error: {e}")
                return

            if not response or not response.ok:
                status = response.status if response else "Unknown"
                error_text = f"Error: Failed to find {type_name} '{name}' (Status: {status})."
                await interaction.followup.send(error_text, ephemeral=True)
                return

            try:
                element = await page.wait_for_selector('.coc-sheet, .origin-sheet', timeout=5000)
            except:
                element = None

            if not element:
                screenshot_bytes = await page.screenshot(full_page=True, omit_background=True)
            else:
                screenshot_bytes = await element.screenshot(omit_background=True)

            file = discord.File(io.BytesIO(screenshot_bytes), filename=f"{name.replace(' ', '_')}_{type_name}.png")

            await interaction.followup.send(content=f"Here is the poster for **{name}**:", file=file, ephemeral=ephemeral)

        except Exception as e:
            error_msg = f"An error occurred while generating the image: {e}"
            await interaction.followup.send(error_msg, ephemeral=True)
            print(f"Codex Error: {e}")
        finally:
            if page:
                try:
                    await page.close()
                except:
                    pass

    def _find_matches(self, query, choices):
        """Find matches using RapidFuzz."""
        query_lower = query.lower()
        exact_match = None

        # Check for exact match first (case-insensitive)
        for choice in choices:
            if choice.lower() == query_lower:
                exact_match = choice
                break

        if exact_match:
            return [exact_match]

        # Use RapidFuzz for fuzzy matching
        matches = process.extract(query, choices, scorer=fuzz.WRatio, limit=5, score_cutoff=60)
        return [m[0] for m in matches]

    async def _handle_no_arg_lookup(self, interaction: discord.Interaction, loader_func, type_slug, data_key=None, flatten_pulp=False, keys_only=False, title=None):
        if not title:
            title = f"{type_slug.replace('_', ' ').capitalize()} List"

        view = OptionsView(interaction.user, loader_func, type_slug, data_key, flatten_pulp, self, title, keys_only=keys_only)

        if not interaction.response.is_done():
             await interaction.response.send_message(f"What would you like to do with {type_slug.replace('_', ' ')}s?", view=view, ephemeral=True)
             view.message = await interaction.original_response()
        else:
             msg = await interaction.followup.send(f"What would you like to do with {type_slug.replace('_', ' ')}s?", view=view, ephemeral=True)
             view.message = msg

    async def _handle_lookup(self, interaction: discord.Interaction, name, loader_func, type_slug, data_key=None, keys_only=False, flatten_pulp=False):
        # We assume command handler deferred already if needed, or we use response.send_message

        data = await loader_func()

        choices = []
        if flatten_pulp:
            pulp_map = {}
            for category, talents in data.items():
                for t_str in talents:
                    match = re.match(r'\*\*(.*?)\*\*:\s*(.*)', t_str)
                    if match:
                        t_name = match.group(1)
                        pulp_map[t_name] = t_name
            choices = list(pulp_map.keys())
        elif data_key:
            items = data.get(data_key, [])
            entry_key = type_slug + "_entry"
            if type_slug == "monster": entry_key = "monster_entry"
            elif type_slug == "spell": entry_key = "spell_entry"
            elif type_slug == "deity": entry_key = "deity_entry"

            for item in items:
                entry = item.get(entry_key)
                if entry and entry.get('name'):
                    choices.append(entry['name'])
        elif keys_only:
            choices = list(data.keys())
        else:
            choices = list(data.keys())

        matches = self._find_matches(name, choices)

        kwargs = {"ephemeral": True}

        if not matches:
            if not interaction.response.is_done():
                 await interaction.response.send_message(f"No {type_slug.replace('_', ' ')} found matching '{name}'.", **kwargs)
            else:
                 await interaction.followup.send(f"No {type_slug.replace('_', ' ')} found matching '{name}'.", **kwargs)
            return

        if len(matches) == 1:
            target_name = matches[0]
            entry_data = self._get_entry_data(data, target_name, type_slug, data_key, flatten_pulp, keys_only)

            if entry_data:
                await self._display_entry(interaction, target_name, type_slug, entry_data, ephemeral=True)
            else:
                # Fallback if extraction failed (shouldn't happen if match exists)
                quoted_name = urllib.parse.quote(target_name)
                url = f"/render/{type_slug}?name={quoted_name}"
                await self._render_poster(interaction, url, target_name, type_slug, ephemeral=True)

        elif len(matches) < 25:
             view = SelectionView(interaction.user, matches, type_slug, loader_func, self, data_key=data_key, flatten_pulp=flatten_pulp, keys_only=keys_only)
             msg = None
             if not interaction.response.is_done():
                 await interaction.response.send_message(f"Multiple {type_slug.replace('_', ' ')}s found for '{name}'. Please select one:", view=view, ephemeral=True)
                 msg = await interaction.original_response()
             else:
                 msg = await interaction.followup.send(f"Multiple {type_slug.replace('_', ' ')}s found for '{name}'. Please select one:", view=view, ephemeral=True)
             view.message = msg
        else:
            response = f"Found {len(matches)} matches for '{name}'. Please be more specific:\n"
            match_list = ", ".join(matches)
            if len(match_list) > 1900:
                match_list = match_list[:1900] + "..."

            if not interaction.response.is_done():
                 await interaction.response.send_message(response + match_list, **kwargs)
            else:
                 await interaction.followup.send(response + match_list, **kwargs)

    @app_commands.command(description="👹 Displays a monster sheet.")
    async def monster(self, interaction: discord.Interaction, name: str = None):
        """Displays a monster sheet."""
        if name:
            await self._handle_lookup(interaction, name, load_monsters_data, "monster", data_key="monsters")
        else:
            await self._handle_no_arg_lookup(interaction, load_monsters_data, "monster", data_key="monsters")

    @monster.autocomplete('name')
    async def monster_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._get_autocomplete_choices(current, load_monsters_data, data_key="monsters")

    @app_commands.command(description="✨ Displays a spell.")
    async def spell(self, interaction: discord.Interaction, name: str = None):
        """Displays a spell."""
        if name:
            await self._handle_lookup(interaction, name, load_spells_data, "spell", data_key="spells")
        else:
            await self._handle_no_arg_lookup(interaction, load_spells_data, "spell", data_key="spells")

    @spell.autocomplete('name')
    async def spell_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._get_autocomplete_choices(current, load_spells_data, data_key="spells")

    @app_commands.command(description="⚡ Displays a deity sheet.")
    async def deity(self, interaction: discord.Interaction, name: str = None):
        """Displays a deity sheet."""
        if name:
            await self._handle_lookup(interaction, name, load_deities_data, "deity", data_key="deities")
        else:
            await self._handle_no_arg_lookup(interaction, load_deities_data, "deity", data_key="deities")

    @deity.autocomplete('name')
    async def deity_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._get_autocomplete_choices(current, load_deities_data, data_key="deities")

    @app_commands.command(description="📔 Opens the Codex to view lists of all entries.")
    async def codex(self, interaction: discord.Interaction):
        """Opens the Codex to view lists of all entries."""
        view = CodexView(interaction.user, self)
        await interaction.response.send_message("What list would you like to see?", view=view, ephemeral=True)
        view.message = await interaction.original_response()

    @app_commands.command(description="📜 Opens the Grimoire (Codex) to view all game data.")
    async def grimoire(self, interaction: discord.Interaction):
        """Opens the Grimoire (Codex) to view all game data."""
        await self.codex(interaction)

    @app_commands.command(name="archetype", description="🎭 Displays a Pulp Cthulhu Archetype.")
    async def archetype(self, interaction: discord.Interaction, name: str = None):
        """Displays a Pulp Cthulhu Archetype."""
        if name:
            await self._handle_lookup(interaction, name, load_archetype_data, "archetype", keys_only=True)
        else:
            await self._handle_no_arg_lookup(interaction, load_archetype_data, "archetype")

    @archetype.autocomplete('name')
    async def archetype_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._get_autocomplete_choices(current, load_archetype_data, keys_only=True)

    @app_commands.command(name="talent", description="🌟 Displays a Pulp Talent.")
    async def talent(self, interaction: discord.Interaction, name: str = None):
        """Displays a Pulp Talent."""
        if name:
            await self._handle_lookup(interaction, name, load_pulp_talents_data, "pulp_talent", flatten_pulp=True)
        else:
            await self._handle_no_arg_lookup(interaction, load_pulp_talents_data, "pulp_talent", flatten_pulp=True)

    @talent.autocomplete('name')
    async def talent_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._get_autocomplete_choices(current, load_pulp_talents_data, flatten_pulp=True)

    @app_commands.command(name="insane", description="👁️ Displays an Insane Talent.")
    async def insane(self, interaction: discord.Interaction, name: str = None):
        """Displays an Insane Talent."""
        if name:
            await self._handle_lookup(interaction, name, load_madness_insane_talent_data, "insane_talent", keys_only=True)
        else:
            await self._handle_no_arg_lookup(interaction, load_madness_insane_talent_data, "insane_talent")

    @insane.autocomplete('name')
    async def insane_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._get_autocomplete_choices(current, load_madness_insane_talent_data, keys_only=True)

    @app_commands.command(description="🌪️ Displays a Mania.")
    async def mania(self, interaction: discord.Interaction, name: str = None):
        """Displays a Mania."""
        if name:
            await self._handle_lookup(interaction, name, load_manias_data, "mania", keys_only=True)
        else:
            await self._handle_no_arg_lookup(interaction, load_manias_data, "mania")

    @mania.autocomplete('name')
    async def mania_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._get_autocomplete_choices(current, load_manias_data, keys_only=True)

    @app_commands.command(description="😱 Displays a Phobia.")
    async def phobia(self, interaction: discord.Interaction, name: str = None):
        """Displays a Phobia."""
        if name:
            await self._handle_lookup(interaction, name, load_phobias_data, "phobia", keys_only=True)
        else:
            await self._handle_no_arg_lookup(interaction, load_phobias_data, "phobia")

    @phobia.autocomplete('name')
    async def phobia_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._get_autocomplete_choices(current, load_phobias_data, keys_only=True)

    @app_commands.command(name="poison", description="🧪 Displays a Poison.")
    async def poison(self, interaction: discord.Interaction, name: str = None):
        """Displays a Poison."""
        if name:
            await self._handle_lookup(interaction, name, load_poisons_data, "poison", keys_only=True)
        else:
            await self._handle_no_arg_lookup(interaction, load_poisons_data, "poison")

    @poison.autocomplete('name')
    async def poison_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._get_autocomplete_choices(current, load_poisons_data, keys_only=True)

    @app_commands.command(name="skill", description="📚 Displays a Skill description.")
    async def skill(self, interaction: discord.Interaction, name: str = None):
        """Displays a Skill description."""
        if name:
            await self._handle_lookup(interaction, name, load_skills_data, "skill", keys_only=True)
        else:
            await self._handle_no_arg_lookup(interaction, load_skills_data, "skill")

    @skill.autocomplete('name')
    async def skill_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._get_autocomplete_choices(current, load_skills_data, keys_only=True)

    @app_commands.command(name="invention", description="💡 Displays Inventions for a specific decade (e.g., 1920s).")
    async def invention(self, interaction: discord.Interaction, decade: str = None):
        """Displays Inventions for a specific decade (e.g., 1920s)."""
        if decade:
            # Handle "1925" -> "1920s" logic
            year_match = re.search(r'\d{3,4}', decade)
            if year_match:
                try:
                    year_val = int(year_match.group(0))
                    # Round down to nearest decade
                    decade_val = (year_val // 10) * 10
                    decade = f"{decade_val}s"
                except ValueError:
                    pass

            await self._handle_lookup(interaction, decade, load_inventions_data, "invention", keys_only=True)
        else:
            await self._handle_no_arg_lookup(interaction, load_inventions_data, "invention")

    @invention.autocomplete('decade')
    async def invention_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._get_autocomplete_choices(current, load_inventions_data, is_invention=True)

    @app_commands.command(name="year", description="📅 Displays events for a specific year (e.g., 1920).")
    async def year(self, interaction: discord.Interaction, year: str = None):
        """Displays events for a specific year (e.g., 1920)."""
        if year:
            await self._handle_lookup(interaction, year, load_years_data, "year", keys_only=True)
        else:
            await self._handle_no_arg_lookup(interaction, load_years_data, "year")

    @year.autocomplete('year')
    async def year_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._get_autocomplete_choices(current, load_years_data, keys_only=True)

    @app_commands.command(name="weapon", description="🔫 Displays a weapon.")
    async def weapon(self, interaction: discord.Interaction, name: str = None):
        """Displays a weapon."""
        if name:
            await self._handle_lookup(interaction, name, load_weapons_data, "weapon", keys_only=True)
        else:
             await self._handle_no_arg_lookup(interaction, load_weapons_data, "weapon")

    @weapon.autocomplete('name')
    async def weapon_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._get_autocomplete_choices(current, load_weapons_data, keys_only=True)

    @app_commands.command(name="occupation", description="🕵️ Displays an occupation.")
    async def occupation(self, interaction: discord.Interaction, name: str = None):
        """Displays an occupation."""
        if name:
            await self._handle_lookup(interaction, name, load_occupations_data, "occupation", keys_only=True)
        else:
            await self._handle_no_arg_lookup(interaction, load_occupations_data, "occupation")

    @occupation.autocomplete('name')
    async def occupation_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._get_autocomplete_choices(current, load_occupations_data, keys_only=True)

async def setup(bot):
    await bot.add_cog(Codex(bot))
