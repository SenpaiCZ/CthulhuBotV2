import discord
import random
import re
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select
from loadnsave import load_player_stats, load_weapons_data, save_player_stats
from commands.roll import RollResultView
from rapidfuzz import process, fuzz, utils
from emojis import get_health_bar
from support_functions import MockContext


class CombatView(View):
    def __init__(self, interaction, char_data, weapon_db, player_stats, server_id, user_id, initial_weapon_states=None, last_action=None):
        super().__init__(timeout=900) # 15 min timeout
        self.interaction = interaction
        self.char_data = char_data
        self.weapon_db = weapon_db
        self.player_stats = player_stats
        self.server_id = str(server_id)
        self.user_id = str(user_id)
        self.last_action = last_action or "Combat started."

        # Parse Inventory for Weapons
        # self.available_weapons is now a list of dicts:
        # [{'key': 'AK-47', 'display': 'AK-47 [30/30]', 'ammo': 30, 'cap': 30, 'original': 'AK-47 [30/30]'}, ...]
        self.available_weapons = self._parse_weapons()
        self.active_weapon_idx = 0 if self.available_weapons else -1

        # Initial State
        self.weapon_states = {} # key: idx, value: {ammo: int, jammed: bool, cap: int}

        if self.available_weapons:
            for i, w_obj in enumerate(self.available_weapons):
                # Default from parsed object
                self.weapon_states[i] = {
                    "ammo": w_obj['ammo'],
                    "cap": w_obj['cap'],
                    "jammed": w_obj.get('is_jammed', False)
                }
                # If we had previous state (e.g. preserving jammed status if view reloaded), apply it
                if initial_weapon_states and i in initial_weapon_states:
                     prev = initial_weapon_states[i]
                     self.weapon_states[i]["jammed"] = prev.get("jammed", False)

        self.message = None
        self.update_components()

    def _parse_weapons(self):
        # Scan Backstory -> Gear and Possessions / Weapons
        inventory = []
        backstory = self.char_data.get("Backstory", {})

        # Check specific keys
        sources = ["Gear and Possessions", "Weapons", "Equipment", "Assets"]
        for key in sources:
            items = backstory.get(key, [])
            if isinstance(items, list):
                inventory.extend(items)

        found_weapons = []
        weapon_keys = list(self.weapon_db.keys())

        for item in inventory:
            if not isinstance(item, str): continue

            # Regex parse Name [Current/Max] or Name [Capacity]
            # Updated to handle emoji prefix and (JAMMED) suffix
            match = re.match(r"^(?:🔴|🟢)?\s*(.*?)\s*\[(\d+)(?:/(\d+))?\](?:\s*\(JAMMED\))?\s*$", item)

            clean_name_candidate = item
            current_ammo = None
            max_ammo = None

            if match:
                clean_name_candidate = match.group(1).strip()
                current_ammo = int(match.group(2))
                if match.group(3):
                    max_ammo = int(match.group(3))
                else:
                    max_ammo = current_ammo # If just [30], assume 30/30

            # Clean "A " or "An " prefix
            clean_item = clean_name_candidate
            if clean_item.lower().startswith("a "): clean_item = clean_item[2:].strip()
            elif clean_item.lower().startswith("an "): clean_item = clean_item[3:].strip()

            # Identify Weapon in DB
            db_key = None
            if clean_item in weapon_keys:
                db_key = clean_item
            else:
                # Fuzzy match
                fuzzy = process.extractOne(clean_item, weapon_keys, scorer=fuzz.token_set_ratio)
                if fuzzy and fuzzy[1] > 85:
                    db_key = fuzzy[0]

            if db_key:
                w_data = self.weapon_db.get(db_key, {})

                # Determine Capacity if not parsed
                if max_ammo is None:
                    cap_str = w_data.get("capacity", "0")
                    try:
                        cap_match = re.search(r"(\d+)", str(cap_str))
                        if cap_match:
                            max_ammo = int(cap_match.group(1))
                        else:
                            max_ammo = 0
                    except:
                        max_ammo = 0

                if current_ammo is None:
                    current_ammo = max_ammo

                found_weapons.append({
                    "key": db_key,
                    "display": item, # The full original string
                    "clean_name": clean_name_candidate, # The name part of the string (e.g. "AK-47")
                    "ammo": current_ammo,
                    "cap": max_ammo,
                    "original": item, # Valid for finding and replacing
                    "is_jammed": "(JAMMED)" in item
                })

        return found_weapons

    def update_components(self):
        self.clear_items()

        # Row 0: Common Actions
        brawl_btn = Button(label="Brawl", style=discord.ButtonStyle.primary, row=0, emoji="👊")
        brawl_btn.callback = self.brawl_callback
        self.add_item(brawl_btn)

        dodge_btn = Button(label="Dodge", style=discord.ButtonStyle.secondary, row=0, emoji="💨")
        dodge_btn.callback = self.dodge_callback
        self.add_item(dodge_btn)

        maneuver_btn = Button(label="Maneuver", style=discord.ButtonStyle.secondary, row=0, emoji="🥋")
        maneuver_btn.callback = self.maneuver_callback
        self.add_item(maneuver_btn)

        # Row 1: Weapon Selection
        if self.available_weapons:
            options = []
            for i, w_obj in enumerate(self.available_weapons):
                state = self.weapon_states.get(i, {})
                ammo = state.get("ammo", 0)
                cap = state.get("cap", 0)
                jammed = state.get("jammed", False)

                # Emojis for Dropdown
                status_emoji = "🟩"
                if jammed: status_emoji = "🔴"
                elif ammo == 0: status_emoji = "🟡"

                label = f"{status_emoji} {w_obj['clean_name'][:50]} [{ammo}/{cap}]"
                if jammed: label += " (JAMMED)"

                options.append(discord.SelectOption(label=label, value=str(i), default=(i == self.active_weapon_idx)))

            select = Select(placeholder="Select Active Weapon", options=options[:25], row=1)
            select.callback = self.select_weapon_callback
            self.add_item(select)

            # Row 2: Active Weapon Controls
            if self.active_weapon_idx >= 0:
                current_state = self.weapon_states[self.active_weapon_idx]
                is_jammed = current_state["jammed"]
                ammo = current_state["ammo"]

                shoot_btn = Button(label="Shoot", style=discord.ButtonStyle.danger, row=2, emoji="🔫", disabled=is_jammed)
                shoot_btn.callback = self.shoot_callback
                self.add_item(shoot_btn)

                reload_btn = Button(label="Reload", style=discord.ButtonStyle.success, row=2, emoji="🔄")
                reload_btn.callback = self.reload_callback
                self.add_item(reload_btn)

                if is_jammed:
                    fix_btn = Button(label="Clear Jam", style=discord.ButtonStyle.primary, row=2, emoji="🛠️")
                    fix_btn.callback = self.fix_jam_callback
                    self.add_item(fix_btn)

        # Row 3: Exit
        exit_btn = Button(label="Exit Combat", style=discord.ButtonStyle.danger, row=3, emoji="🚪")
        exit_btn.callback = self.exit_callback
        self.add_item(exit_btn)

    def get_embed(self):
        embed = discord.Embed(title="Combat Mode", color=discord.Color.red())

        # Stats Summary
        hp = self.char_data.get("HP", 0)
        max_hp = (self.char_data.get("CON", 0) + self.char_data.get("SIZ", 0)) // 10
        if self.char_data.get("Game Mode") == "Pulp of Cthulhu": max_hp = (self.char_data.get("CON", 0) + self.char_data.get("SIZ", 0)) // 5
        hp_bar = get_health_bar(hp, max_hp)

        mp = self.char_data.get("MP", 0)
        max_mp = self.char_data.get("POW", 0) // 5
        mp_bar = get_health_bar(mp, max_mp)

        san = self.char_data.get("SAN", 0)
        max_san = 99 - self.char_data.get("Cthulhu Mythos", 0)
        san_bar = get_health_bar(san, max_san)

        mov = self.char_data.get("Move", 0)
        build = self.char_data.get("Build", 0)
        db = self.char_data.get("Damage Bonus", 0)

        stats_line = (
            f"❤️ **HP:** {hp}/{max_hp} {hp_bar}\n"
            f"🧠 **SAN:** {san}/{max_san} {san_bar}\n"
            f"✨ **MP:** {mp}/{max_mp} {mp_bar}\n"
            f"🏃 **MOV:** {mov} | 💪 **Build:** {build} | 💥 **DB:** {db}"
        )
        embed.description = stats_line

        # Active Weapon Info
        if self.active_weapon_idx >= 0 and self.available_weapons:
            w_obj = self.available_weapons[self.active_weapon_idx]
            w_key = w_obj["key"]
            w_data = self.weapon_db.get(w_key, {})
            state = self.weapon_states.get(self.active_weapon_idx, {})

            ammo = state.get("ammo", 0)
            cap = state.get("cap", 0)
            jammed = state.get("jammed", False)

            damage = w_data.get("damage", "Unknown")
            malf = w_data.get("malfunction", "100")
            shots = w_data.get("shots_per_round", "1")

            status = "🟢 Ready"
            if jammed: status = "🔴 **JAMMED**"
            elif ammo <= 0: status = "🟡 Empty"

            w_info = (f"**{w_obj['clean_name']}**\n"
                      f"Damage: `{damage}` | Malfunction: `{malf}` | ROF: `{shots}`\n"
                      f"Ammo: **{ammo}/{cap}** | Status: {status}")

            embed.add_field(name="Active Weapon", value=w_info, inline=False)
        elif not self.available_weapons:
             embed.add_field(name="Weapons", value="No weapons found in inventory.", inline=False)
        else:
             embed.add_field(name="Active Weapon", value="None selected.", inline=False)

        # Footer
        embed.set_footer(text=f"Last Action: {self.last_action}")

        return embed

    async def _update_view(self, interaction):
        self.update_components()
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=self.get_embed(), view=self)
        else:
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    # Callbacks
    async def brawl_callback(self, interaction: discord.Interaction):
        self.last_action = "Attempted Brawl."
        # Brawl Damage: 1D3 + DB
        damage_data = [{'label': 'Fighting (Brawl)', 'value': '1D3'}]
        damage_bonus = self.char_data.get("Damage Bonus", "0")

        await self.perform_roll(interaction, "Fighting (Brawl)",
                                custom_title="Fighting (Brawl)",
                                damage_data=damage_data,
                                damage_bonus=damage_bonus)

    async def dodge_callback(self, interaction: discord.Interaction):
        self.last_action = "Attempted Dodge."
        # Dodge usually doesn't do damage, but maybe counter-attack?
        # For now, no damage button on dodge.
        await self.perform_roll(interaction, "Dodge", custom_title="Dodge")

    async def maneuver_callback(self, interaction: discord.Interaction):
        self.last_action = "Attempted Maneuver."
        # Maneuvers might do damage or just effects.
        # We can add damage button as optional (same as Brawl).
        damage_data = [{'label': 'Maneuver', 'value': '1D3'}] # Base brawl damage if needed?
        damage_bonus = self.char_data.get("Damage Bonus", "0")

        await self.perform_roll(interaction, "Fighting (Brawl)",
                                custom_title="Maneuver",
                                damage_data=damage_data,
                                damage_bonus=damage_bonus)

    async def select_weapon_callback(self, interaction: discord.Interaction):
        self.active_weapon_idx = int(interaction.data["values"][0])
        self.last_action = f"Switched weapon."
        await self._update_view(interaction)

    async def _update_inventory_string(self, idx, new_ammo, max_ammo):
        # Helper to update the inventory string in char_data
        w_obj = self.available_weapons[idx]
        original_str = w_obj["original"]
        base_name = w_obj["clean_name"]

        is_jammed = self.weapon_states[idx]["jammed"]

        # Format: 🔴 Name [Am/Cap] (JAMMED) or Name [Am/Cap]
        if is_jammed:
            new_str = f"🔴 {base_name} [{new_ammo}/{max_ammo}] (JAMMED)"
        else:
            new_str = f"{base_name} [{new_ammo}/{max_ammo}]"

        # Find and replace in char_data["Backstory"]["Gear and Possessions"] (etc)
        # We search all possible keys again or just iterate
        sources = ["Gear and Possessions", "Weapons", "Equipment", "Assets"]
        updated = False

        backstory = self.char_data.get("Backstory", {})
        for key in sources:
            if key in backstory and isinstance(backstory[key], list):
                # Try to find index of original_str
                try:
                    list_idx = backstory[key].index(original_str)
                    backstory[key][list_idx] = new_str
                    updated = True
                    # Update local object so future updates find the new string
                    self.available_weapons[idx]["original"] = new_str
                    self.available_weapons[idx]["display"] = new_str # keeping consistent
                    break
                except ValueError:
                    continue

        if updated:
            # Save to disk
            # We need to update the main player_stats object
            # Note: self.player_stats must be initialized in __init__
            self.player_stats[self.server_id][self.user_id] = self.char_data
            await save_player_stats(self.player_stats)

    def _parse_damage_string(self, raw_damage, w_name):
        """
        Parses complex damage strings like "1D10+5 (slug) or 4D6 (buckshot)"
        Returns a list of dicts: [{'label': 'Slug', 'value': '1D10+5'}, ...]
        """
        if not raw_damage or raw_damage.lower() == "unknown":
            return []

        options = []
        # Split by " or "
        parts = re.split(r'\s+or\s+', raw_damage, flags=re.IGNORECASE)

        for part in parts:
            part = part.strip()
            # Check for parenthetical label: "1D10+5 (slug)"
            match = re.match(r"^(.*?)\s*\((.*?)\)$", part)
            if match:
                formula = match.group(1).strip()
                label = match.group(2).strip()
            else:
                formula = part
                label = w_name

            options.append({'label': label, 'value': formula})

        return options

    async def shoot_callback(self, interaction: discord.Interaction):
        idx = self.active_weapon_idx
        state = self.weapon_states[idx]
        w_obj = self.available_weapons[idx]

        if state["ammo"] <= 0:
            return await interaction.response.send_message("Click... (Out of Ammo!)", ephemeral=True)

        state["ammo"] -= 1

        # Determine Skill
        skill_name = self._get_firearm_skill(w_obj["key"])

        self.last_action = f"Fired {w_obj['clean_name']}."

        # Save Ammo Change
        await self._update_inventory_string(idx, state["ammo"], state["cap"])

        # Perform Roll
        w_data = self.weapon_db.get(w_obj["key"], {})

        # Parse Damage
        raw_damage = w_data.get("damage", "1D3")
        damage_data = self._parse_damage_string(raw_damage, w_obj['clean_name'])

        # Guns usually don't add DB unless thrown, but CoC rules say no DB for guns.
        damage_bonus = None

        async def on_shoot_done(roll, tier, is_malf):
            if is_malf:
                self.weapon_states[idx]["jammed"] = True
                self.last_action += " (JAMMED!)"
                await self._update_inventory_string(idx, state["ammo"], state["cap"])

                # We need to refresh the view to show the jam state
                if self.message:
                    self.update_components()
                    await self.message.edit(embed=self.get_embed(), view=self)

        await self.perform_roll(interaction, skill_name,
                                custom_title=f"Shoot ({w_obj['clean_name']})",
                                check_malfunction=True,
                                malfunction_val=w_data.get("malfunction", "100"),
                                on_complete=on_shoot_done,
                                damage_data=damage_data,
                                damage_bonus=damage_bonus)

    async def reload_callback(self, interaction: discord.Interaction):
        idx = self.active_weapon_idx
        state = self.weapon_states[idx]
        w_obj = self.available_weapons[idx]

        state["ammo"] = state["cap"]
        state["jammed"] = False

        self.last_action = f"Reloaded {w_obj['clean_name']}."

        # Save Ammo Change
        await self._update_inventory_string(idx, state["ammo"], state["cap"])

        await self._update_view(interaction)

    async def fix_jam_callback(self, interaction: discord.Interaction):
        idx = self.active_weapon_idx

        async def on_repair_done(roll, tier, is_malf):
            if tier >= 2: # Regular success or better
                self.weapon_states[idx]["jammed"] = False
                self.last_action = f"Cleared jam on {self.available_weapons[idx]['clean_name']}."
                await self._update_inventory_string(idx, self.weapon_states[idx]["ammo"], self.weapon_states[idx]["cap"])
            else:
                self.last_action = f"Failed to clear jam on {self.available_weapons[idx]['clean_name']}."

            if self.message:
                self.update_components()
                await self.message.edit(embed=self.get_embed(), view=self)

        await self.perform_roll(interaction, "Mech. Repair", custom_title="Fix Jam", on_complete=on_repair_done)

    async def exit_callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Combat ended.", view=None, embed=None)
        self.stop()

    def _get_firearm_skill(self, weapon_key):
        """
        Determines the correct skill name to use for rolling.
        Attempts to use simplified "Pistol" / "Rifle/Shotgun" if present on character.
        Falls back to legacy "Firearms (Handgun)" / "Firearms (Rifle/Shotgun)" if simplified not found.
        """
        w_data = self.weapon_db.get(weapon_key, {})
        target_skill = w_data.get("Skill", "Rifle/Shotgun") # Default new schema

        # Check if the character actually HAS this skill
        # If they do, return it.
        # If not, check if they have the legacy equivalent.

        # Logic:
        # 1. Exact match
        if target_skill in self.char_data:
            return target_skill

        # 2. Legacy Fallback
        legacy_map = {
            "Pistol": "Firearms (Handgun)",
            "Rifle/Shotgun": "Firearms (Rifle/Shotgun)"
        }

        if target_skill in legacy_map:
            legacy_name = legacy_map[target_skill]
            if legacy_name in self.char_data:
                return legacy_name

        # 3. Fallback (if they have neither, return new name and let fuzzy match fail/default to base chance)
        return target_skill

    async def perform_roll(self, interaction, skill_name, custom_title=None, check_malfunction=False, malfunction_val="100", on_complete=None, damage_data=None, damage_bonus=None):
        # Get Roll Cog
        roll_cog = interaction.client.get_cog("Roll")
        if not roll_cog:
            if not interaction.response.is_done():
                await interaction.response.send_message("Roll cog not found.", ephemeral=True)
            return

        # Get Skill Value
        skill_val = 0
        real_name = skill_name

        if skill_name in self.char_data:
            skill_val = self.char_data[skill_name]
        else:
            # Try fuzzy
            keys = list(self.char_data.keys())
            match = process.extractOne(skill_name, keys, scorer=fuzz.token_set_ratio, processor=utils.default_process)
            if match and match[1] > 70:
                real_name = match[0]
                skill_val = self.char_data[real_name]
            else:
                real_name = skill_name
                skill_val = self.char_data.get(skill_name, 0) # Fallback

        # Calculate Roll
        ones = random.randint(0, 9)
        tens = random.choice([0, 10, 20, 30, 40, 50, 60, 70, 80, 90])
        roll_val = tens + ones
        if roll_val == 0: roll_val = 100

        # Check Malfunction Limit
        malf_limit = None
        if check_malfunction:
            try:
                if "-" in str(malfunction_val):
                    parts = str(malfunction_val).split("-")
                    malf_limit = int(parts[0])
                else:
                    malf_limit = int(malfunction_val)
            except:
                malf_limit = 100

        # Use RollResultView
        ctx = MockContext(interaction)
        result_text, result_tier = roll_cog.calculate_roll_result(roll_val, skill_val)

        # Prepare View
        view = RollResultView(
            ctx=ctx,
            cog=roll_cog,
            player_stats=self.player_stats,
            server_id=self.server_id,
            user_id=self.user_id,
            stat_name=real_name,
            current_value=skill_val,
            ones_roll=ones,
            tens_rolls=[tens],
            net_dice=0,
            result_tier=result_tier,
            luck_threshold=10,
            malfunction_threshold=malf_limit,
            on_complete=on_complete,
            damage_data=damage_data,
            damage_bonus=damage_bonus
        )

        # Create Embed
        color = discord.Color.green()
        if result_tier == 5 or result_tier == 4: color = 0xF1C40F
        elif result_tier == 3 or result_tier == 2: color = 0x2ECC71
        elif result_tier == 1: color = 0xE74C3C
        elif result_tier == 0: color = 0x992D22

        # Initial check for display (view will handle dynamic updates)
        if malf_limit and roll_val >= malf_limit:
            result_text = "🔫 MALFUNCTION! (Weapon Jammed)"
            color = discord.Color.dark_red()

        desc = f"{interaction.user.mention} :game_die: **{custom_title or 'Roll'}**\n"
        desc += f"Dice: [{tens if tens!=0 else '00'}] + {ones} -> **{roll_val}**\n\n"
        desc += f"**{result_text}**\n\n"
        desc += f"**{real_name}**: {skill_val} - {skill_val//2} - {skill_val//5}"

        embed = discord.Embed(description=desc, color=color)

        # 1. Send Public Roll Result
        public_msg = await interaction.channel.send(embed=embed, view=view)
        view.message = public_msg

        # 2. Replace Old Dashboard with Text
        action_text = f"**{self.last_action}**"
        if not interaction.response.is_done():
            await interaction.response.edit_message(content=action_text, embed=None, view=None)
        else:
            await interaction.edit_original_response(content=action_text, embed=None, view=None)

        # 3. Send New Dashboard (Ephemeral)
        self.update_components()
        new_msg = await interaction.followup.send(embed=self.get_embed(), view=self, ephemeral=True)
        self.message = new_msg


class Combat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="combat", description="Opens the combat dashboard.")
    async def combat(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        player_stats = await load_player_stats()
        server_id = interaction.guild.id
        user_id = interaction.user.id

        if str(server_id) not in player_stats or str(user_id) not in player_stats[str(server_id)]:
            await interaction.followup.send("You don't have an investigator. Use `/newinvestigator`.", ephemeral=True)
            return

        char_data = player_stats[str(server_id)][str(user_id)]
        weapon_db = await load_weapons_data()

        view = CombatView(interaction, char_data, weapon_db, player_stats, server_id, user_id)
        msg = await interaction.followup.send(embed=view.get_embed(), view=view, ephemeral=True)
        view.message = msg

async def setup(bot):
    await bot.add_cog(Combat(bot))
