import discord
import math
import re
from discord.ui import View, Select, Button
from emojis import get_stat_emoji, stat_emojis
from descriptions import get_description
import occupation_emoji
from commands._backstory_common import BackstoryCategorySelectView
from loadnsave import load_player_stats

class CharacterDashboardView(View):
    def __init__(self, user, char_data, mode_label, current_mode, server_id):
        super().__init__(timeout=300) # 5 minute timeout
        self.user = user
        self.char_data = char_data
        self.mode_label = mode_label
        self.current_mode = current_mode
        self.server_id = server_id
        self.current_section = "stats"
        self.page = 0
        self.items_per_page = 24 # Safe limit for embed fields
        self.message = None

        # Build the initial Select Menu
        self.update_components()

    def update_components(self):
        self.clear_items()

        # Section Selector
        select = Select(
            placeholder="Navigate Character Sheet",
            options=[
                discord.SelectOption(label="📊 Attributes & Bio", value="stats", description="Core stats, HP, SAN, Move, etc.", emoji="📊", default=(self.current_section == "stats")),
                discord.SelectOption(label="🛠️ Skills", value="skills", description="List of all skills and probabilities", emoji="🛠️", default=(self.current_section == "skills")),
                discord.SelectOption(label="📜 Backstory & Inventory", value="backstory", description="History, Ideology, Assets, Gear", emoji="📜", default=(self.current_section == "backstory"))
            ],
            row=0
        )
        select.callback = self.select_callback
        self.add_item(select)

        # Pagination Buttons (Only for Skills/Backstory if needed)
        if self.current_section == "skills":
            skill_list = self._get_skill_list()
            max_pages = math.ceil(len(skill_list) / self.items_per_page)

            if max_pages > 1:
                prev_btn = Button(label="Previous", style=discord.ButtonStyle.secondary, row=1, disabled=(self.page == 0))
                prev_btn.callback = self.prev_page_callback
                self.add_item(prev_btn)

                indicator = Button(label=f"Page {self.page + 1}/{max_pages}", style=discord.ButtonStyle.secondary, disabled=True, row=1)
                self.add_item(indicator)

                next_btn = Button(label="Next", style=discord.ButtonStyle.secondary, row=1, disabled=(self.page >= max_pages - 1))
                next_btn.callback = self.next_page_callback
                self.add_item(next_btn)

        # Interactive Buttons for Backstory
        if self.current_section == "backstory":
             add_btn = Button(label="Add Entry", style=discord.ButtonStyle.success, row=1, emoji="➕")
             add_btn.callback = self.add_entry_callback
             self.add_item(add_btn)

             remove_btn = Button(label="Remove Entry", style=discord.ButtonStyle.danger, row=1, emoji="➖")
             remove_btn.callback = self.remove_entry_callback
             self.add_item(remove_btn)

        # Dismiss Button (Always available)
        dismiss_btn = Button(label="Dismiss", style=discord.ButtonStyle.danger, row=2)
        dismiss_btn.callback = self.dismiss_callback
        self.add_item(dismiss_btn)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("This dashboard is not for you!", ephemeral=True)
            return

        self.current_section = interaction.data["values"][0]
        self.page = 0 # Reset page on section change
        self.update_components()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
        self.message = interaction.message

    async def prev_page_callback(self, interaction: discord.Interaction):
        if interaction.user != self.user: return
        if self.page > 0:
            self.page -= 1
            self.update_components()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
            self.message = interaction.message

    async def next_page_callback(self, interaction: discord.Interaction):
        if interaction.user != self.user: return
        self.page += 1
        self.update_components()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
        self.message = interaction.message

    async def dismiss_callback(self, interaction: discord.Interaction):
        if interaction.user == self.user:
            await interaction.message.delete()
        else:
            await interaction.response.send_message("You cannot dismiss this.", ephemeral=True)

    async def refresh_dashboard(self, interaction: discord.Interaction):
        # Refresh dashboard view
        if not self.message:
            return

        try:
            # Re-fetch data to ensure we have the latest updates
            player_stats = await load_player_stats()
            # server_id and user.id are used to get the specific char_data
            if self.server_id in player_stats and str(self.user.id) in player_stats[self.server_id]:
                self.char_data = player_stats[self.server_id][str(self.user.id)]

            self.update_components()
            await self.message.edit(embed=self.get_embed(), view=self)
        except discord.NotFound:
            pass
        except Exception as e:
            print(f"Error refreshing dashboard: {e}")

    async def add_entry_callback(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            return await interaction.response.send_message("Not your dashboard!", ephemeral=True)

        view = BackstoryCategorySelectView(self.user, self.server_id, str(self.user.id), mode="add", callback=self.refresh_dashboard)
        await interaction.response.send_message("Select a category to add to:", view=view, ephemeral=True)

    async def remove_entry_callback(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            return await interaction.response.send_message("Not your dashboard!", ephemeral=True)

        view = BackstoryCategorySelectView(self.user, self.server_id, str(self.user.id), mode="remove", callback=self.refresh_dashboard)
        await interaction.response.send_message("Select a category to remove from:", view=view, ephemeral=True)

    def get_embed(self):
        if self.current_section == "stats":
            return self._get_stats_embed()
        elif self.current_section == "skills":
            return self._get_skills_embed()
        elif self.current_section == "backstory":
            return self._get_backstory_embed()
        return discord.Embed(title="Error", description="Unknown section")

    def _get_stats_embed(self):
        embed = discord.Embed(
            title=f"{self.char_data.get('NAME', 'Unknown')}",
            description=f"**{self.mode_label}**",
            color=discord.Color.dark_teal()
        )

        # --- 1. Bio Section ---
        occupation = self.char_data.get("Occupation", "Unknown")
        occ_emoji = occupation_emoji.get_occupation_emoji(occupation)
        residence = self.char_data.get("Residence", "Unknown")
        age = self.char_data.get("Age", "Unknown")
        archetype = self.char_data.get("Archetype", None)

        bio_desc = f"**Occupation:** {occupation} {occ_emoji}\n**Age:** {age}\n**Residence:** {residence}"
        if archetype:
            bio_desc += f"\n**Archetype:** {archetype}"

        embed.add_field(name="📜 Biography", value=bio_desc, inline=False)

        # --- 2. Attributes (STR, DEX, etc.) ---
        # We want a nice grid.
        attributes = ["STR", "DEX", "INT", "CON", "APP", "POW", "SIZ", "EDU", "LUCK"]

        attr_text = ""
        for attr in attributes:
            val = self.char_data.get(attr, 0)
            emoji = get_stat_emoji(attr)
            # Format: **STR** 50 (25/10)
            attr_text += f"{emoji} **{attr}:** {val} ({val//2}/{val//5})\n"

        embed.add_field(name="📊 Characteristics", value=attr_text, inline=True)

        # --- 3. Derived Stats (HP, MP, SAN, Move, Build, DB) ---
        derived_text = ""

        # HP
        hp = self.char_data.get("HP", 0)
        con = self.char_data.get("CON", 0)
        siz = self.char_data.get("SIZ", 0)
        max_hp = (con + siz) // 10 if self.current_mode == "Call of Cthulhu" else (con + siz) // 5
        derived_text += f"❤️ **HP:** {hp}/{max_hp}\n"

        # MP
        mp = self.char_data.get("MP", 0)
        pow_stat = self.char_data.get("POW", 0)
        max_mp = pow_stat // 5
        derived_text += f"✨ **MP:** {mp}/{max_mp}\n"

        # SAN
        san = self.char_data.get("SAN", 0)
        start_san = pow_stat
        mythos = self.char_data.get("Cthulhu Mythos", 0)
        max_san = 99 - mythos
        derived_text += f"🧠 **SAN:** {san}/{max_san}\n"

        # Move
        move = self._calculate_move()
        derived_text += f"🏃 **Move:** {move}\n"

        # Build & DB
        build, db = self._calculate_build_db()
        derived_text += f"💪 **Build:** {build}\n💥 **DB:** {db}\n"

        # Dodge (Often considered a core combat stat)
        dodge = self.char_data.get("Dodge", 0)
        derived_text += f"💨 **Dodge:** {dodge} ({dodge//2}/{dodge//5})\n"

        embed.add_field(name="⚖️ Derived Stats", value=derived_text, inline=True)

        return embed

    def _get_skills_embed(self):
        embed = discord.Embed(
            title=f"🛠️ Skills - {self.char_data.get('NAME', 'Unknown')}",
            color=discord.Color.dark_green()
        )

        all_skills = self._get_skill_list()

        # Pagination logic
        start_idx = self.page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        current_page_skills = all_skills[start_idx:end_idx]

        if not current_page_skills:
            embed.description = "No skills found."
            return embed

        for skill, val in current_page_skills:
            # Format: Value (Hard/Extreme)
            val_text = f"**{val}** ({val//2}/{val//5})"
            emoji = self._get_skill_emoji(skill)
            embed.add_field(name=f"{emoji} {skill}", value=val_text, inline=True)

        embed.set_footer(text=f"Page {self.page + 1}/{math.ceil(len(all_skills)/self.items_per_page)}")
        return embed

    def _get_backstory_embed(self):
        embed = discord.Embed(
            title=f"📜 Backstory & Inventory - {self.char_data.get('NAME', 'Unknown')}",
            color=discord.Color.gold()
        )

        backstory = self.char_data.get("Backstory", {})

        # Helper to format list entries
        def format_entries(entries):
            if isinstance(entries, list):
                if not entries: return "None"
                return "\n".join([f"• {entry}" for entry in entries])
            return str(entries)

        # Inventory / Assets specific handling
        # Usually keys like "Assets", "Gear", "Possessions", "Cash"
        # We will try to group them or highlight them.

        inventory_keys = ["Assets", "Gear", "Possessions", "Cash", "Equipment", "Weapons"]
        inventory_text = ""

        for key, value in backstory.items():
            if key in inventory_keys:
                inventory_text += f"**{key}:**\n{format_entries(value)}\n\n"

        if inventory_text:
            embed.add_field(name="🎒 Inventory & Assets", value=inventory_text, inline=False)

        # Other Backstory elements
        for key, value in backstory.items():
            if key in inventory_keys or key == "Pulp Talents": continue
            # Pulp talents handled separately or just skipped if standard mode

            content = format_entries(value)
            # Truncate if too long
            if len(content) > 1000:
                content = content[:1000] + "..."

            embed.add_field(name=key, value=content, inline=False)

        # Pulp Talents if applicable
        if "Pulp Talents" in backstory:
            embed.add_field(name="🦸 Pulp Talents", value=format_entries(backstory["Pulp Talents"]), inline=False)

        return embed

    def _get_skill_list(self):
        # Filters out core stats and returns a list of (Name, Value) tuples sorted alphabetically
        ignored = [
            "Residence", "Game Mode", "Archetype", "NAME", "Occupation",
            "Age", "HP", "MP", "SAN", "LUCK", "Build", "Damage Bonus", "Move",
            "STR", "DEX", "INT", "CON", "APP", "POW", "SIZ", "EDU", "Dodge",
            "Backstory"
        ]

        skills = []
        for key, val in self.char_data.items():
            if key in ignored: continue
            if isinstance(val, dict): continue # Skip nested dicts if any
            if isinstance(val, str): continue # Skip string fields that aren't stats

            skills.append((key, val))

        return sorted(skills, key=lambda item: item[0])

    def _get_skill_emoji(self, skill_name):
        custom_emojis = self.char_data.get("Custom Emojis", {})
        if skill_name in custom_emojis:
            return custom_emojis[skill_name]

        if skill_name in stat_emojis:
            return stat_emojis[skill_name]

        # Normalized Match (strip parens and extra spaces)
        normalized_skill = skill_name.replace("(", " ").replace(")", " ").replace("/", " ").strip()
        # Collapse multiple spaces
        normalized_skill = re.sub(r'\s+', ' ', normalized_skill)

        if normalized_skill in stat_emojis:
            return stat_emojis[normalized_skill]

        # Partial Match
        sorted_keys = sorted(stat_emojis.keys(), key=len, reverse=True)
        for key in sorted_keys:
            if key.lower() in skill_name.lower():
                return stat_emojis[key]

        return "❓"

    def _calculate_move(self):
        dex = self.char_data.get("DEX", 0)
        siz = self.char_data.get("SIZ", 0)
        str_stat = self.char_data.get("STR", 0)
        age = self.char_data.get("Age", 0)

        if dex == 0 or siz == 0 or str_stat == 0 or age == 0:
            return "N/A"

        if dex < siz and str_stat < siz:
            mov = 7
        elif dex < siz or str_stat < siz:
            mov = 8
        elif dex == siz and str_stat == siz:
            mov = 8
        else:
            mov = 9

        if 40 <= age < 50: mov -= 1
        elif 50 <= age < 60: mov -= 2
        elif 60 <= age < 70: mov -= 3
        elif 70 <= age < 80: mov -= 4
        elif age >= 80: mov -= 5

        return max(0, mov)

    def _calculate_build_db(self):
        str_stat = self.char_data.get("STR", 0)
        siz = self.char_data.get("SIZ", 0)

        if str_stat == 0 or siz == 0:
            return "N/A", "N/A"

        str_siz = str_stat + siz

        if 2 <= str_siz <= 64: return -2, "-2"
        elif 65 <= str_siz <= 84: return -1, "-1"
        elif 85 <= str_siz <= 124: return 0, "0"
        elif 125 <= str_siz <= 164: return 1, "1D4"
        elif 165 <= str_siz <= 204: return 2, "1D6"
        elif 205 <= str_siz <= 284: return 3, "2D6"
        elif 285 <= str_siz <= 364: return 4, "3D6"
        elif 365 <= str_siz <= 444: return 5, "4D6"
        elif 445 <= str_siz <= 524: return 6, "5D6"
        else: return "7+", "6D6+" # Simplified for >524
