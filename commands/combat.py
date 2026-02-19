import discord
import random
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select
from loadnsave import load_player_stats, load_weapons_data
from commands.roll import RollResultView
from rapidfuzz import process, fuzz

class MockContext:
    def __init__(self, interaction):
        self.interaction = interaction
        self.author = interaction.user
        self.guild = interaction.guild
        self.channel = interaction.channel

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
        self.available_weapons = self._parse_weapons()
        self.active_weapon_idx = 0 if self.available_weapons else -1

        # Initial State
        if initial_weapon_states:
            self.weapon_states = initial_weapon_states
        else:
            self.weapon_states = {} # key: idx, value: {ammo: int, jammed: bool}
            if self.available_weapons:
                for i, w_key in enumerate(self.available_weapons):
                    w_data = self.weapon_db.get(w_key, {})
                    cap_str = w_data.get("capacity", "0")
                    try:
                        cap = int(str(cap_str).split("/")[0].strip()) # Handle "20/30"
                    except:
                        cap = 0
                    self.weapon_states[i] = {"ammo": cap, "jammed": False, "cap": cap}

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

            # clean "A " or "An " prefix
            clean_item = item
            if clean_item.lower().startswith("a "): clean_item = clean_item[2:].strip()
            elif clean_item.lower().startswith("an "): clean_item = clean_item[3:].strip()

            # Exact match
            if clean_item in weapon_keys:
                found_weapons.append(clean_item)
                continue

            # Fuzzy match
            match = process.extractOne(clean_item, weapon_keys, scorer=fuzz.token_set_ratio)
            if match and match[1] > 85: # High confidence
                found_weapons.append(match[0])

        # Remove duplicates while preserving order
        seen = set()
        unique_weapons = []
        for w in found_weapons:
            if w not in seen:
                unique_weapons.append(w)
                seen.add(w)

        return unique_weapons

    def _generate_health_bar(self, current, max_val, length=8):
        if max_val <= 0: max_val = 1
        pct = current / max_val
        if pct < 0: pct = 0
        if pct > 1: pct = 1

        filled = int(pct * length)
        empty = length - filled

        # Color Logic
        # 🟩 Green for > 50%
        # 🟨 Yellow for > 20%
        # 🟥 Red for <= 20%

        fill_char = "🟩"
        if pct <= 0.2: fill_char = "🟥"
        elif pct <= 0.5: fill_char = "🟨"

        # Using Black Square for empty
        bar = (fill_char * filled) + ("⬛" * empty)
        return bar

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
            for i, w_key in enumerate(self.available_weapons):
                state = self.weapon_states.get(i, {})
                ammo = state.get("ammo", "?")
                cap = state.get("cap", "?")
                jammed = " (JAMMED)" if state.get("jammed") else ""
                label = f"{w_key[:50]} [{ammo}/{cap}]{jammed}"
                options.append(discord.SelectOption(label=label, value=str(i), default=(i == self.active_weapon_idx)))

            select = Select(placeholder="Select Active Weapon", options=options[:25], row=1)
            select.callback = self.select_weapon_callback
            self.add_item(select)

            # Row 2: Active Weapon Controls
            if self.active_weapon_idx >= 0:
                current_state = self.weapon_states[self.active_weapon_idx]
                is_jammed = current_state["jammed"]

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

        # Stats Summary with Bars
        hp = self.char_data.get("HP", 0)
        max_hp = (self.char_data.get("CON", 0) + self.char_data.get("SIZ", 0)) // 10
        if self.char_data.get("Game Mode") == "Pulp of Cthulhu": max_hp = (self.char_data.get("CON", 0) + self.char_data.get("SIZ", 0)) // 5

        hp_bar = self._generate_health_bar(hp, max_hp)

        mp = self.char_data.get("MP", 0)
        max_mp = self.char_data.get("POW", 0) // 5
        mp_bar = self._generate_health_bar(mp, max_mp)

        san = self.char_data.get("SAN", 0)
        max_san = 99 - self.char_data.get("Cthulhu Mythos", 0)
        san_bar = self._generate_health_bar(san, max_san)

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
        if self.active_weapon_idx >= 0:
            w_key = self.available_weapons[self.active_weapon_idx]
            w_data = self.weapon_db.get(w_key, {})
            state = self.weapon_states.get(self.active_weapon_idx, {})

            ammo = state.get("ammo", 0)
            cap = state.get("cap", 0)
            jammed = state.get("jammed", False)

            damage = w_data.get("damage", "Unknown")
            malf = w_data.get("malfunction", "100")
            shots = w_data.get("shots_per_round", "1")

            status = "🔴 **JAMMED**" if jammed else "🟢 Ready"
            if ammo <= 0 and not jammed: status = "🟡 Empty"

            w_info = (f"**{w_key}**\n"
                      f"Damage: `{damage}` | Malfunction: `{malf}` | ROF: `{shots}`\n"
                      f"Ammo: **{ammo}/{cap}** | Status: {status}")

            embed.add_field(name="Active Weapon", value=w_info, inline=False)
        elif not self.available_weapons:
             embed.add_field(name="Weapons", value="No weapons found in inventory.", inline=False)
        else:
             embed.add_field(name="Active Weapon", value="None selected.", inline=False)

        # Footer with Last Action
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
        await self.perform_roll(interaction, "Fighting (Brawl)", custom_title="Fighting (Brawl)")

    async def dodge_callback(self, interaction: discord.Interaction):
        self.last_action = "Attempted Dodge."
        await self.perform_roll(interaction, "Dodge", custom_title="Dodge")

    async def maneuver_callback(self, interaction: discord.Interaction):
        self.last_action = "Attempted Maneuver."
        await self.perform_roll(interaction, "Fighting (Brawl)", custom_title="Maneuver")

    async def select_weapon_callback(self, interaction: discord.Interaction):
        self.active_weapon_idx = int(interaction.data["values"][0])
        self.last_action = f"Switched weapon."
        await self._update_view(interaction)

    async def shoot_callback(self, interaction: discord.Interaction):
        idx = self.active_weapon_idx
        state = self.weapon_states[idx]

        if state["ammo"] <= 0:
            return await interaction.response.send_message("Click... (Out of Ammo!)", ephemeral=True)

        # Determine Skill
        w_key = self.available_weapons[idx]
        w_data = self.weapon_db.get(w_key, {})
        skill_name = self._get_firearm_skill(w_key)

        state["ammo"] -= 1
        self.last_action = f"Fired {w_key}."

        # Perform Roll
        await self.perform_roll(interaction, skill_name, custom_title=f"Shoot ({w_key})", check_malfunction=True, malfunction_val=w_data.get("malfunction", "100"))

    async def reload_callback(self, interaction: discord.Interaction):
        idx = self.active_weapon_idx
        state = self.weapon_states[idx]
        state["ammo"] = state["cap"]
        state["jammed"] = False

        self.last_action = f"Reloaded {self.available_weapons[idx]}."
        await self._update_view(interaction)

    async def fix_jam_callback(self, interaction: discord.Interaction):
        idx = self.active_weapon_idx
        state = self.weapon_states[idx]
        state["jammed"] = False

        self.last_action = f"Cleared jam on {self.available_weapons[idx]}."
        await self._update_view(interaction)

    async def exit_callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Combat ended.", view=None, embed=None)
        self.stop()

    def _get_firearm_skill(self, weapon_name):
        name_lower = weapon_name.lower()
        if "rifle" in name_lower or "carbine" in name_lower: return "Firearms (Rifle/Shotgun)"
        if "shotgun" in name_lower: return "Firearms (Rifle/Shotgun)"
        if "submachine" in name_lower or "smg" in name_lower or "tommy" in name_lower or "mp18" in name_lower or "mp40" in name_lower or "sten" in name_lower: return "Firearms (Submachine Gun)"
        if "machine gun" in name_lower or "lewis" in name_lower or "browning" in name_lower or "vickers" in name_lower or "mg42" in name_lower: return "Firearms (Machine Gun)"
        return "Firearms (Handgun)"

    async def perform_roll(self, interaction, skill_name, custom_title=None, check_malfunction=False, malfunction_val="100"):
        # Get Roll Cog
        roll_cog = interaction.client.get_cog("Roll")
        if not roll_cog:
            if not interaction.response.is_done():
                await interaction.response.send_message("Roll cog not found.", ephemeral=True)
            return

        # Get Skill Value
        # Fuzzy match skill name in char_data
        skill_val = 0
        real_name = skill_name

        # Try exact
        if skill_name in self.char_data:
            skill_val = self.char_data[skill_name]
        else:
            # Try fuzzy
            keys = list(self.char_data.keys())
            match = process.extractOne(skill_name, keys, scorer=fuzz.token_set_ratio)
            if match and match[1] > 80:
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

        # Check Malfunction
        is_malfunction = False
        malf_limit = 100
        try:
            if "-" in str(malfunction_val):
                parts = str(malfunction_val).split("-")
                malf_limit = int(parts[0])
            else:
                malf_limit = int(malfunction_val)
        except:
            malf_limit = 100

        if check_malfunction and roll_val >= malf_limit:
            is_malfunction = True
            self.weapon_states[self.active_weapon_idx]["jammed"] = True
            self.last_action += " (JAMMED!)"

        # Use RollResultView
        # We need a Mock Context
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
            ones_roll=ones_roll,
            tens_rolls=[tens],
            net_dice=0,
            result_tier=result_tier,
            luck_threshold=10
        )

        # Create Embed
        color = discord.Color.green()
        if result_tier == 5 or result_tier == 4: color = 0xF1C40F
        elif result_tier == 3 or result_tier == 2: color = 0x2ECC71
        elif result_tier == 1: color = 0xE74C3C
        elif result_tier == 0: color = 0x992D22

        if is_malfunction:
            result_text = "🔫 MALFUNCTION! (Weapon Jammed)"
            color = discord.Color.dark_red()

        desc = f"{interaction.user.mention} :game_die: **{custom_title or 'Roll'}**\n"
        desc += f"Dice: [{tens if tens!=0 else '00'}] + {ones} -> **{roll_val}**\n\n"
        desc += f"**{result_text}**\n\n"
        desc += f"**{real_name}**: {skill_val} - {skill_val//2} - {skill_val//5}"

        embed = discord.Embed(description=desc, color=color)

        # 1. Send Public Roll Result to Channel
        public_msg = await interaction.channel.send(embed=embed, view=view)
        view.message = public_msg

        # 2. Update Dashboard IN PLACE
        # This fulfills the button interaction (shoot, brawl, etc.)
        self.update_components()
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            # If already responded (unlikely unless defer called), modify original
            await interaction.edit_original_response(embed=self.get_embed(), view=self)


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
