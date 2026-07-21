import discord
import random
import re
import urllib.parse

from loadnsave import (
    load_monsters_data, load_deities_data, load_spells_data,
    load_archetype_data, load_pulp_talents_data, load_madness_insane_talent_data,
    load_manias_data, load_phobias_data, load_poisons_data, load_skills_data,
    load_inventions_data, load_years_data, load_weapons_data, load_occupations_data,
    load_player_stats, save_player_stats
)

class PaginatedListView(discord.ui.View):
    def __init__(self, user, items, title, per_page=20, data=None, cog=None, type_slug=None, data_key=None, flatten_pulp=False, keys_only=False):
        super().__init__(timeout=60)
        self.user = user
        self.items = items
        self.title = title
        self.per_page = per_page
        self.current_page = 0
        self.total_pages = max(1, (len(items) + per_page - 1) // per_page)
        self.message = None

        # Data context for dropdown selection
        self.data = data
        self.cog = cog
        self.type_slug = type_slug
        self.data_key = data_key
        self.flatten_pulp = flatten_pulp
        self.keys_only = keys_only

        # Initialize Select Menu if data context is available
        self.select_menu = None
        if self.data is not None and self.cog is not None and self.type_slug is not None:
             self.select_menu = discord.ui.Select(placeholder="Select an item to view...", min_values=1, max_values=1)
             self.select_menu.callback = self.select_callback
             self.add_item(self.select_menu)
             self.update_select_options()

    def update_select_options(self):
        if not self.select_menu:
            return

        start = self.current_page * self.per_page
        end = start + self.per_page
        page_items = self.items[start:end]

        self.select_menu.options.clear()
        if not page_items:
            # Discord requires at least 1 option — add a placeholder
            self.select_menu.add_option(label="(no entries)", value="__none__", description="No entries on this page")
            self.select_menu.disabled = True
            return

        self.select_menu.disabled = False
        for item in page_items:
            label = item[:100]
            value = item[:100]
            if self.type_slug == "invention":
                value = item.split(' (')[0]
            self.select_menu.add_option(label=label, value=value)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user != self.user:
             return await interaction.response.send_message("This isn't for you!", ephemeral=True)

        selected_name = interaction.data['values'][0]
        if selected_name == "__none__":
            return await interaction.response.defer()

        loading_embed = discord.Embed(title=f"Loading {selected_name}…", color=discord.Color.dark_green())
        await interaction.response.edit_message(content=None, embed=loading_embed, view=None)

        try:
            entry_data = self.cog._get_entry_data(self.data, selected_name, self.type_slug, self.data_key, self.flatten_pulp, self.keys_only)

            if entry_data:
                await self.cog._display_entry(interaction, selected_name, self.type_slug, entry_data, ephemeral=True)
            else:
                quoted_name = urllib.parse.quote(selected_name)
                url = f"/render/{self.type_slug}?name={quoted_name}"
                await self.cog._render_poster(interaction, url, selected_name, self.type_slug, ephemeral=True)
        except Exception as e:
            print(f"[Codex] select_callback error for '{selected_name}': {e}")
            try:
                await interaction.edit_original_response(content=f"Error: {e}", embed=None, view=None)
            except Exception:
                pass

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == self.total_pages - 1
        self.page_counter.label = f"Page {self.current_page + 1}/{self.total_pages}"
        self.update_select_options()

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
        if interaction.user != self.user:
             return await interaction.response.send_message("This isn't for you!", ephemeral=True)
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Page 1/1", style=discord.ButtonStyle.secondary, disabled=True)
    async def page_counter(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
             return await interaction.response.send_message("This isn't for you!", ephemeral=True)
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
             return await interaction.response.send_message("This isn't for you!", ephemeral=True)

        await interaction.response.edit_message(content="List closed.", embed=None, view=None)
        self.stop()

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.delete()
            except:
                pass
        self.stop()

class OptionsView(discord.ui.View):
    def __init__(self, user, loader_func, type_slug, data_key, flatten_pulp, cog, title, keys_only=False):
        super().__init__(timeout=60)
        self.user = user
        self.loader_func = loader_func
        self.type_slug = type_slug
        self.data_key = data_key
        self.flatten_pulp = flatten_pulp
        self.keys_only = keys_only
        self.cog = cog
        self.title = title
        self.message = None

    @discord.ui.button(label="List all", style=discord.ButtonStyle.success)
    async def list_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
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
        view = PaginatedListView(
            self.user, choices, self.title,
            data=data, cog=self.cog, type_slug=self.type_slug,
            data_key=self.data_key, flatten_pulp=self.flatten_pulp, keys_only=self.keys_only
        )
        view.update_buttons()
        embed = view.get_embed()
        await interaction.response.edit_message(content=None, embed=embed, view=view)
        view.message = interaction.message

    @discord.ui.button(label="Random one", style=discord.ButtonStyle.primary)
    async def random_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
             return await interaction.response.send_message("This isn't for you!", ephemeral=True)

        loading_embed = discord.Embed(title="Finding a random entry…", color=discord.Color.dark_green())
        await interaction.response.edit_message(content=None, embed=loading_embed, view=None)

        try:
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
                await interaction.edit_original_response(content="No entries found.", embed=None, view=None)
                return

            target_name = random.choice(choices)

            entry_data = self.cog._get_entry_data(data, target_name, self.type_slug, self.data_key, self.flatten_pulp, self.keys_only)

            if entry_data:
                await self.cog._display_entry(interaction, target_name, self.type_slug, entry_data, ephemeral=True)
            else:
                quoted_name = urllib.parse.quote(target_name)
                url = f"/render/{self.type_slug}?name={quoted_name}"
                await self.cog._render_poster(interaction, url, target_name, self.type_slug, ephemeral=True)
        except Exception as e:
            print(f"[Codex] random_button error: {e}")
            try:
                await interaction.edit_original_response(content=f"Error: {e}", embed=None, view=None)
            except Exception:
                pass

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
             return await interaction.response.send_message("This isn't for you!", ephemeral=True)

        await interaction.response.edit_message(content="Dismissed.", embed=None, view=None)
        self.stop()

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.delete()
            except:
                pass
        self.stop()

class RenderView(discord.ui.View):
    def __init__(self, user, cog, name, type_slug):
        super().__init__(timeout=60)
        self.user = user
        self.cog = cog
        self.name = name
        self.type_slug = type_slug
        self.message = None

        if self.type_slug == "weapon":
             btn = discord.ui.Button(label="Add to Inventory", style=discord.ButtonStyle.success, emoji="🎒", row=1)
             btn.callback = self.add_to_inventory_button
             self.add_item(btn)

        if self.type_slug in ["monster", "deity", "spell"]:
             btn = discord.ui.Button(label="📜 View Origin", style=discord.ButtonStyle.secondary)
             btn.callback = self.origin_poster_button
             self.add_item(btn)

    @discord.ui.button(label="📜 View Poster", style=discord.ButtonStyle.secondary)
    async def poster_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
             return await interaction.response.send_message("This isn't for you!", ephemeral=True)

        # Defer ephemeral to prevent timeout while rendering
        # Interaction might already be deferred? No, new interaction.
        # _render_poster handles defer.

        quoted_name = urllib.parse.quote(self.name)
        url = f"/render/{self.type_slug}?name={quoted_name}"

        await self.cog._render_poster(interaction, url, self.name, self.type_slug, ephemeral=True)

    async def origin_poster_button(self, interaction: discord.Interaction):
        if interaction.user != self.user:
             return await interaction.response.send_message("This isn't for you!", ephemeral=True)

        quoted_name = urllib.parse.quote(self.name)
        url = f"/render/{self.type_slug}?name={quoted_name}&style=origin"

        await self.cog._render_poster(interaction, url, self.name, f"{self.type_slug}_origin", ephemeral=True)

    async def add_to_inventory_button(self, interaction: discord.Interaction):
        if not interaction.guild:
             return await interaction.response.send_message("This action can only be performed in a server.", ephemeral=True)

        server_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        player_stats = await load_player_stats()

        if server_id not in player_stats or user_id not in player_stats[server_id]:
            return await interaction.response.send_message("You don't have an investigator! Use `/newinvestigator` to create one.", ephemeral=True)

        char_data = player_stats[server_id][user_id]

        if "Backstory" not in char_data:
            char_data["Backstory"] = {}

        if "Gear and Possessions" not in char_data["Backstory"]:
            char_data["Backstory"]["Gear and Possessions"] = []

        char_data["Backstory"]["Gear and Possessions"].append(self.name)

        await save_player_stats(player_stats)

        await interaction.response.send_message(f"Added **{self.name}** to your inventory (Gear and Possessions).", ephemeral=True)

    async def on_timeout(self):
        # Disable buttons
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass
        self.stop()

class CodexView(discord.ui.View):
    def __init__(self, user, cog):
        super().__init__(timeout=60)
        self.user = user
        self.cog = cog
        self.message = None

    async def _launch_list(self, interaction, loader, title, data_key=None, flatten_pulp=False, type_slug=None, keys_only=False):
        # Respond immediately (satisfies 3s window), show loading state
        loading_embed = discord.Embed(title=f"Loading {title}…", color=discord.Color.dark_green())
        await interaction.response.edit_message(content=None, embed=loading_embed, view=None)

        try:
            data = await loader()
            choices = []
            if flatten_pulp:
                pulp_map = {}
                for category, talents in data.items():
                    for t_str in talents:
                        match = re.match(r'\*\*(.*?)\*\*:\s*(.*)', t_str)
                        if match:
                            pulp_map[match.group(1)] = match.group(1)
                choices = list(pulp_map.keys())
            elif data_key:
                items = data.get(data_key, [])
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
                if type_slug == "invention":
                    for k, v in data.items():
                        choices.append(f"{k} ({len(v)} entries)")
                else:
                    choices = list(data.keys())

            choices.sort()
            print(f"[Codex] _launch_list '{title}': {len(choices)} choices, data type={type(data).__name__}, data_key={data_key}")

            if not choices:
                err_embed = discord.Embed(
                    title="No entries found",
                    description=f"No entries could be loaded for **{title}**. The data file may be missing or empty.",
                    color=discord.Color.orange()
                )
                await interaction.edit_original_response(content=None, embed=err_embed, view=None)
                return

            view = PaginatedListView(
                self.user, choices, title,
                data=data, cog=self.cog, type_slug=type_slug,
                data_key=data_key, flatten_pulp=flatten_pulp, keys_only=keys_only
            )
            view.update_buttons()
            embed = view.get_embed()
            msg = await interaction.edit_original_response(content=None, embed=embed, view=view)
            view.message = msg
        except Exception as e:
            print(f"[Codex] _launch_list error ({title}): {e}")
            import traceback; traceback.print_exc()
            err_embed = discord.Embed(title="Error", description=str(e), color=discord.Color.red())
            try:
                await interaction.edit_original_response(content=None, embed=err_embed, view=None)
            except Exception:
                pass

    async def _check_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.user:
            await interaction.response.send_message("This menu isn't for you.", ephemeral=True)
            return False
        return True

    # Row 0
    @discord.ui.button(label="Monsters", style=discord.ButtonStyle.danger, row=0)
    async def monsters_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction): return
        await self._launch_list(interaction, load_monsters_data, "Monsters List", data_key="monsters", type_slug="monster")

    @discord.ui.button(label="Deities", style=discord.ButtonStyle.danger, row=0)
    async def deities_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction): return
        await self._launch_list(interaction, load_deities_data, "Deities List", data_key="deities", type_slug="deity")

    @discord.ui.button(label="Archetypes", style=discord.ButtonStyle.danger, row=0)
    async def archetypes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction): return
        await self._launch_list(interaction, load_archetype_data, "Archetypes List", type_slug="archetype", keys_only=True)

    @discord.ui.button(label="Occupations", style=discord.ButtonStyle.danger, row=0)
    async def occupations_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction): return
        await self._launch_list(interaction, load_occupations_data, "Occupations List", type_slug="occupation", keys_only=True)

    # Row 1
    @discord.ui.button(label="Spells", style=discord.ButtonStyle.danger, row=1)
    async def spells_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction): return
        await self._launch_list(interaction, load_spells_data, "Spells List", data_key="spells", type_slug="spell")

    @discord.ui.button(label="Talents", style=discord.ButtonStyle.danger, row=1)
    async def talents_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction): return
        await self._launch_list(interaction, load_pulp_talents_data, "Pulp Talents List", flatten_pulp=True, type_slug="pulp_talent")

    @discord.ui.button(label="Insane Talents", style=discord.ButtonStyle.danger, row=1)
    async def insane_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction): return
        await self._launch_list(interaction, load_madness_insane_talent_data, "Insane Talents List", type_slug="insane_talent", keys_only=True)

    @discord.ui.button(label="Skills", style=discord.ButtonStyle.danger, row=1)
    async def skills_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction): return
        await self._launch_list(interaction, load_skills_data, "Skills List", type_slug="skill", keys_only=True)

    # Row 2
    @discord.ui.button(label="Weapons", style=discord.ButtonStyle.danger, row=2)
    async def weapons_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction): return
        await self._launch_list(interaction, load_weapons_data, "Weapons List", type_slug="weapon", keys_only=True)

    @discord.ui.button(label="Poisons", style=discord.ButtonStyle.danger, row=2)
    async def poisons_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction): return
        await self._launch_list(interaction, load_poisons_data, "Poisons List", type_slug="poison", keys_only=True)

    @discord.ui.button(label="Inventions", style=discord.ButtonStyle.danger, row=2)
    async def inventions_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction): return
        await self._launch_list(interaction, load_inventions_data, "Inventions List", type_slug="invention")

    # Row 3
    @discord.ui.button(label="Manias", style=discord.ButtonStyle.danger, row=3)
    async def manias_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction): return
        await self._launch_list(interaction, load_manias_data, "Manias List", type_slug="mania", keys_only=True)

    @discord.ui.button(label="Phobias", style=discord.ButtonStyle.danger, row=3)
    async def phobias_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction): return
        await self._launch_list(interaction, load_phobias_data, "Phobias List", type_slug="phobia", keys_only=True)

    @discord.ui.button(label="Years", style=discord.ButtonStyle.danger, row=3)
    async def years_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_owner(interaction): return
        await self._launch_list(interaction, load_years_data, "Years List", type_slug="year", keys_only=True)

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.delete()
            except:
                pass
        self.stop()


class SelectionView(discord.ui.View):
    def __init__(self, user, options, type_name, loader_func, cog, data_key=None, flatten_pulp=False, keys_only=False):
        super().__init__(timeout=60)
        self.user = user
        self.cog = cog
        self.type_name = type_name
        self.loader_func = loader_func
        self.data_key = data_key
        self.flatten_pulp = flatten_pulp
        self.keys_only = keys_only
        self.options = options  # Keep full list for index-based lookup
        self.message = None

        # Create select menu — use index as value to avoid 100-char limit on long names
        select = discord.ui.Select(placeholder=f"Select a {type_name.replace('_', ' ')}...", min_values=1, max_values=1)

        for i, option in enumerate(options):
            label = option[:100]
            select.add_option(label=label, value=str(i))

        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("This selection is not for you.", ephemeral=True)
            return

        # Resolve full name from index
        idx = int(interaction.data['values'][0])
        selected_name = self.options[idx]

        # Disable view and acknowledge interaction
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        # Load data for rendering
        data = await self.loader_func()
        entry_data = self.cog._get_entry_data(data, selected_name, self.type_name, self.data_key, self.flatten_pulp, self.keys_only)

        if entry_data:
            await self.cog._display_entry(interaction, selected_name, self.type_name, entry_data, ephemeral=True)
        else:
            # Fallback
            quoted_name = urllib.parse.quote(selected_name)
            url = f"/render/{self.type_name}?name={quoted_name}"
            await self.cog._render_poster(interaction, url, selected_name, self.type_name, ephemeral=True)

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.delete()
            except:
                pass
        self.stop()
