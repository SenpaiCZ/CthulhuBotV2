import discord
import asyncio
import random
from discord.ui import View, Button, Select
from loadnsave import load_player_stats, load_luck_stats
from emojis import get_stat_emoji
from support_functions import MockContext

class SessionView(View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.create_session = False
        self.message = None

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Not for you!", ephemeral=True)
        self.create_session = True
        self.stop()
        # Disable buttons
        for child in self.children: child.disabled = True
        try:
            await interaction.response.edit_message(view=self)
        except:
            pass

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary)
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Not for you!", ephemeral=True)
        self.create_session = False
        self.stop()
        # Disable buttons
        for child in self.children: child.disabled = True
        try:
            await interaction.response.edit_message(view=self)
        except:
            pass

class DisambiguationSelect(Select):
    def __init__(self, options):
        super().__init__(placeholder="Select a skill...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_stat = self.values[0]
        await interaction.response.defer()
        self.view.stop()

class DisambiguationView(View):
    def __init__(self, ctx, matching_stats):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.selected_stat = None

        options = [
            discord.SelectOption(label=stat, value=stat)
            for stat in matching_stats[:25]
        ]
        self.add_item(DisambiguationSelect(options))

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=1)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Not your session!", ephemeral=True)
            return False
        return True

class DamageSelect(Select):
    def __init__(self, damage_data, parent_view):
        self.parent_view = parent_view
        options = []
        for d in damage_data:
            lbl = d.get('label', 'Damage')
            val = d.get('value', '0')
            # Truncate if needed
            options.append(discord.SelectOption(label=lbl[:100], value=val, description=f"Rolls {val}"))
        super().__init__(placeholder="Select damage type...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        chosen_formula = self.values[0]
        # Find label for display
        chosen_label = next((d['label'] for d in self.parent_view.damage_data if d['value'] == chosen_formula), "Damage")
        await self.parent_view.perform_damage_roll(interaction, chosen_formula, chosen_label)

class DamageSelectView(View):
    def __init__(self, damage_data, parent_view):
        super().__init__(timeout=60)
        self.damage_data = damage_data
        self.parent_view = parent_view
        self.add_item(DamageSelect(damage_data, parent_view))

class RollResultView(View):
    def __init__(self, ctx, cog, player_stats, server_id, user_id, stat_name, current_value,
                 ones_roll, tens_rolls, net_dice, result_tier, luck_threshold,
                 malfunction_threshold=None, on_complete=None,
                 damage_data=None, damage_bonus=None):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.cog = cog
        self.player_stats = player_stats
        self.server_id = server_id
        self.user_id = user_id
        self.stat_name = stat_name
        self.current_value = current_value

        # Dice State
        self.ones_roll = ones_roll
        self.tens_rolls = tens_rolls # List of tens (0, 10, ... 90)
        self.net_dice = net_dice # >0 Bonus, <0 Penalty

        self.result_tier = result_tier
        self.luck_threshold = luck_threshold

        self.malfunction_threshold = malfunction_threshold
        self.on_complete = on_complete
        self.is_malfunction = False

        self.damage_data = damage_data
        self.damage_bonus = damage_bonus
        self.luck_used = False

        self.roll = self._calculate_current_roll() # Initial calculation
        self.success = False
        if self.result_tier >= 2:
            self.success = True

        # Initial Malfunction Check
        if self.malfunction_threshold is not None:
            try:
                limit = int(self.malfunction_threshold)
                if self.roll >= limit:
                    self.is_malfunction = True
                    self.success = False # Malfunction overrides success usually
            except:
                pass

        # Cleanup Context: Remove Damage Button if irrelevant
        if not self.damage_data:
            to_remove = []
            for child in self.children:
                if isinstance(child, Button) and child.label == "Roll Damage":
                    to_remove.append(child)
            for child in to_remove:
                self.remove_item(child)

        self.update_buttons()

    def _calculate_current_roll(self):
        # Calculate roll based on current dice state
        # Determine how many dice to use based on net_dice
        num_to_use = 1 + abs(self.net_dice)

        # Ensure we have enough dice (safeguard, though buttons handle this)
        while len(self.tens_rolls) < num_to_use:
            self.tens_rolls.append(random.choice([0, 10, 20, 30, 40, 50, 60, 70, 80, 90]))

        # Use only the required number of dice from the history
        active_tens = self.tens_rolls[:num_to_use]

        possible_rolls = []
        for tens in active_tens:
            val = tens + self.ones_roll
            if val == 0: val = 100
            possible_rolls.append(val)

        if self.net_dice > 0:
            # Bonus: Take lowest
            return min(possible_rolls)
        elif self.net_dice < 0:
            # Penalty: Take highest
            return max(possible_rolls)
        else:
            # Normal: Use the single result
            return possible_rolls[0]

    def update_buttons(self):
        # Locate buttons in children
        bonus_btn = None
        penalty_btn = None
        luck_btn = None
        push_btn = None
        damage_btn = None

        for child in self.children:
            if isinstance(child, Button):
                if child.label == "Bonus Die": bonus_btn = child
                elif child.label == "Penalty Die": penalty_btn = child
                elif "Use Luck" in (child.label or ""): luck_btn = child
                elif child.label == "Push Roll": push_btn = child
                elif child.label == "Roll Damage": damage_btn = child

        if self.luck_used:
            # If luck used, dice mods are locked
            if bonus_btn: bonus_btn.disabled = True
            if penalty_btn: penalty_btn.disabled = True
            if push_btn: push_btn.disabled = True
            if luck_btn: luck_btn.disabled = True

            # Damage is allowed if success
            if damage_btn:
                if self.success and not self.is_malfunction:
                    damage_btn.disabled = False
                else:
                    damage_btn.disabled = True
            return

        # --- Normal Logic (No Luck Used Yet) ---

        # LUCK Logic
        can_luck = False
        luck_cost = 0
        player_luck = self.player_stats[self.server_id][self.user_id].get('LUCK', 0)

        # Can only luck if Normal roll (net_dice == 0) and not LUCK roll itself
        if self.net_dice == 0 and self.stat_name != "LUCK" and self.result_tier != 0:
            target_val = 0
            if self.result_tier == 1: # Fail -> Regular
                target_val = self.current_value
            elif self.result_tier == 2: # Regular -> Hard
                target_val = self.current_value // 2
            elif self.result_tier == 3: # Hard -> Extreme
                target_val = self.current_value // 5

            if target_val > 0:
                cost = self.roll - target_val
                if player_luck >= cost and cost <= self.luck_threshold:
                    can_luck = True
                    luck_cost = cost

        if luck_btn:
            luck_btn.disabled = not can_luck
            if can_luck:
                luck_btn.label = f"Use Luck (-{luck_cost})"
            else:
                luck_btn.label = "Use Luck"

        # PUSH Logic (Only on Normal Fail)
        can_push = False
        if self.net_dice == 0 and self.stat_name != "LUCK" and self.result_tier == 1:
             can_push = True

        if push_btn:
            push_btn.disabled = not can_push

        # Max Dice Limit (CoC doesn't specify hard limit, but UI should)
        # Limit to +/- 2 dice
        if bonus_btn: bonus_btn.disabled = self.net_dice >= 2
        if penalty_btn: penalty_btn.disabled = self.net_dice <= -2

        # Damage Button Logic
        if damage_btn:
            if self.success and self.damage_data and not self.is_malfunction:
                 damage_btn.disabled = False
            else:
                 damage_btn.disabled = True

    async def _update_state_and_embed(self, interaction):
        self.roll = self._calculate_current_roll()

        result_text, result_tier = self.cog.calculate_roll_result(self.roll, self.current_value)
        self.result_tier = result_tier
        self.success = result_tier >= 2

        # Malfunction Check
        self.is_malfunction = False
        if self.malfunction_threshold is not None:
            try:
                limit = int(self.malfunction_threshold)
                if self.roll >= limit:
                    self.is_malfunction = True
                    self.success = False
                    result_text = "🔫 MALFUNCTION! (Weapon Jammed)"
            except:
                pass

        self.update_buttons()

        # Rebuild Embed
        embed = interaction.message.embeds[0]

        # Determine Color
        color = discord.Color.green() # Default Regular/Hard
        if result_tier == 5 or result_tier == 4: color = 0xF1C40F # Gold
        elif result_tier == 3 or result_tier == 2: color = 0x2ECC71 # Green
        elif result_tier == 1: color = 0xE74C3C # Red
        elif result_tier == 0: color = 0x992D22 # Dark Red

        if self.is_malfunction:
            color = discord.Color.dark_red()

        embed.color = color

        # Description
        num_to_use = 1 + abs(self.net_dice)
        active_tens = self.tens_rolls[:num_to_use]
        tens_str = ", ".join(str(t) if t != 0 else "00" for t in active_tens)
        ones_str = str(self.ones_roll)

        dice_text = "Normal"
        if self.net_dice > 0: dice_text = f"Bonus ({self.net_dice})"
        elif self.net_dice < 0: dice_text = f"Penalty ({abs(self.net_dice)})"

        description_roll_info = f"{self.ctx.author.mention} :game_die: **{dice_text}** Check\n"
        description_roll_info += f"Dice: [{tens_str}] + {ones_str} -> **{self.roll}**"

        formatted_luck = f":four_leaf_clover: LUCK: {self.player_stats[self.server_id][self.user_id]['LUCK']}"
        formatted_skill = f"**{self.stat_name}**: {self.current_value} - {self.current_value // 2} - {self.current_value // 5}"

        embed.description = f"{description_roll_info}\n\n**{result_text}**\n\n{formatted_skill}\n{formatted_luck}"

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Bonus Die", style=discord.ButtonStyle.success, emoji="🟢", row=0)
    async def add_bonus_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.net_dice += 1

        # Only add a new die if we don't have enough in history
        num_needed = 1 + abs(self.net_dice)
        while len(self.tens_rolls) < num_needed:
            self.tens_rolls.append(random.choice([0, 10, 20, 30, 40, 50, 60, 70, 80, 90]))

        await self._update_state_and_embed(interaction)

    @discord.ui.button(label="Penalty Die", style=discord.ButtonStyle.danger, emoji="🔴", row=0)
    async def add_penalty_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.net_dice -= 1

        # Only add a new die if we don't have enough in history
        num_needed = 1 + abs(self.net_dice)
        while len(self.tens_rolls) < num_needed:
            self.tens_rolls.append(random.choice([0, 10, 20, 30, 40, 50, 60, 70, 80, 90]))

        await self._update_state_and_embed(interaction)

    @discord.ui.button(label="Use Luck", style=discord.ButtonStyle.primary, emoji="🍀", row=1)
    async def luck_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        target_val = 0
        if self.result_tier == 1: target_val = self.current_value
        elif self.result_tier == 2: target_val = self.current_value // 2
        elif self.result_tier == 3: target_val = self.current_value // 5

        cost = self.roll - target_val

        self.player_stats[self.server_id][self.user_id]['LUCK'] -= cost
        self.roll = target_val
        self.result_tier += 1
        self.success = True
        self.luck_used = True

        # Visual Update
        result_text_map = {
            2: "Regular Success (LUCK Used) :heavy_check_mark:",
            3: "Hard Success (LUCK Used) :white_check_mark:",
            4: "Extreme Success (LUCK Used) :star:"
        }
        result_text = result_text_map.get(self.result_tier, "Success (LUCK Used)")

        # Update Buttons (Handles enabling Damage if valid)
        self.update_buttons()

        embed = interaction.message.embeds[0]
        formatted_luck = f":four_leaf_clover: LUCK: {self.player_stats[self.server_id][self.user_id]['LUCK']}"
        formatted_skill = f"**{self.stat_name}**: {self.current_value} - {self.current_value // 2} - {self.current_value // 5}"

        # Reconstruct description with updated Luck
        desc_parts = embed.description.split("\n\n")
        if len(desc_parts) >= 1:
            embed.description = f"{desc_parts[0]}\n\n**{result_text}**\n\n{formatted_skill}\n{formatted_luck}"

        embed.color = 0x2ECC71 # Green
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Push Roll", style=discord.ButtonStyle.secondary, emoji="🔄", row=1)
    async def push_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Pushing a roll is a completely new roll
        new_roll = random.randint(1, 100)
        result_text, new_tier = self.cog.calculate_roll_result(new_roll, self.current_value)

        msg = f"\n\n**PUSHED ROLL**: {new_roll}\nResult: {result_text}"
        if new_tier <= 1:
             msg += "\n:warning: **DIRE CONSEQUENCES!**"
             self.success = False
        else:
             self.success = True

        self.roll = new_roll
        self.result_tier = new_tier

        original_embed = interaction.message.embeds[0]
        original_embed.description += msg

        # Disable all
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(embed=original_embed, view=None)

    @discord.ui.button(label="Done", style=discord.ButtonStyle.secondary, row=1)
    async def done_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        # Trigger Callback if exists
        if self.on_complete:
            try:
                if asyncio.iscoroutinefunction(self.on_complete):
                    await self.on_complete(self.roll, self.result_tier, self.is_malfunction)
                else:
                    self.on_complete(self.roll, self.result_tier, self.is_malfunction)
            except Exception as e:
                print(f"Error in on_complete callback: {e}")

        self.stop()
        # Disable
        try:
            for child in self.children: child.disabled = True
            await interaction.message.edit(view=self)
        except: pass

    @discord.ui.button(label="Roll Damage", style=discord.ButtonStyle.danger, emoji="⚔️", row=2, disabled=True)
    async def damage_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.damage_data: return

        if len(self.damage_data) == 1:
            # Direct Roll
            item = self.damage_data[0]
            await self.perform_damage_roll(interaction, item['value'], item['label'])
        else:
            # Selection
            view = DamageSelectView(self.damage_data, self)
            await interaction.response.send_message("Select damage type:", view=view, ephemeral=True)

    async def perform_damage_roll(self, interaction, formula, label):
        # Add DB if applicable
        final_formula = formula
        if self.damage_bonus and str(self.damage_bonus) not in ["0", "+0", "-0"]:
             final_formula += f" + {self.damage_bonus}"
             # Clean up " + -" -> " - "
             final_formula = final_formula.replace("+ -", "- ")

        try:
             result, detail = self.cog.evaluate_dice_expression(final_formula)

             # Construct Result Embed
             embed = discord.Embed(title=f"⚔️ Damage Roll: {label}", description=f"**{result}** Damage", color=discord.Color.dark_red())
             embed.add_field(name="Formula", value=f"`{final_formula}`")
             embed.add_field(name="Detail", value=detail, inline=False)
             embed.set_footer(text="Combat Log")

             if not interaction.response.is_done():
                 await interaction.response.send_message(embed=embed)
             else:
                 await interaction.followup.send(embed=embed)

        except Exception as e:
             if not interaction.response.is_done():
                 await interaction.response.send_message(f"Error rolling damage: {e}", ephemeral=True)
             else:
                 await interaction.followup.send(f"Error rolling damage: {e}", ephemeral=True)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Not your session!", ephemeral=True)
            return False
        return True

class QuickSkillSelect(Select):
    def __init__(self, char_data, server_id, user_id):
        self.char_data = char_data
        self.server_id = server_id
        self.user_id = user_id

        # Get Skills and Sort
        ignored = [
            "Residence", "Game Mode", "Archetype", "NAME", "Occupation",
            "Age", "HP", "MP", "SAN", "LUCK", "Build", "Damage Bonus", "Move",
            "STR", "DEX", "INT", "CON", "APP", "POW", "SIZ", "EDU", "Dodge",
            "Backstory"
        ]
        skills = []
        for key, val in char_data.items():
            if key in ignored: continue
            if isinstance(val, (int, float)):
                skills.append((key, val))

        skills.sort(key=lambda x: x[1], reverse=True)
        top_skills = skills[:25]

        options = []
        for name, val in top_skills:
            emoji = get_stat_emoji(name)
            options.append(discord.SelectOption(label=f"{name} ({val}%)", value=name, emoji=emoji))

        super().__init__(placeholder="🎲 Quick Roll...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        skill_name = self.values[0]
        current_val = self.char_data.get(skill_name, 0)

        roll_cog = interaction.client.get_cog("Roll")
        if not roll_cog: return

        # Roll
        import random
        ones = random.randint(0, 9)
        tens = random.choice([0, 10, 20, 30, 40, 50, 60, 70, 80, 90])
        roll_val = tens + ones
        if roll_val == 0: roll_val = 100

        result_text, result_tier = roll_cog.calculate_roll_result(roll_val, current_val)
        luck_threshold = (await load_luck_stats()).get(self.server_id, 10)

        full_player_stats = await load_player_stats()
        ctx = MockContext(interaction)
        view = RollResultView(
            ctx=ctx,
            cog=roll_cog,
            player_stats=full_player_stats,
            server_id=self.server_id,
            user_id=self.user_id,
            stat_name=skill_name,
            current_value=current_val,
            ones_roll=ones,
            tens_rolls=[tens],
            net_dice=0,
            result_tier=result_tier,
            luck_threshold=luck_threshold
        )

        color = discord.Color.green()
        if result_tier <= 1: color = discord.Color.red()
        elif result_tier >= 4: color = discord.Color.gold()

        desc = f"{interaction.user.mention} rolled **{skill_name}**!\n"
        desc += f"Dice: [{tens if tens!=0 else '00'}] + {ones} -> **{roll_val}**\n\n"
        desc += f"**{result_text}**\n\n"
        desc += f"**{skill_name}**: {current_val} - {current_val//2} - {current_val//5}\n"

        embed = discord.Embed(description=desc, color=color)

        # Public
        msg = await interaction.channel.send(embed=embed, view=view)
        view.message = msg

        await interaction.response.send_message(f"✅ Rolled **{skill_name}** in channel.", ephemeral=True)

class DiceTrayView(View):
    def __init__(self, cog, user):
        super().__init__(timeout=300)
        self.cog = cog
        self.user = user
        self.expression = ""
        self.update_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.user:
            await interaction.response.send_message("This dice tray is not for you!", ephemeral=True)
            return False
        return True

    def update_buttons(self):
        # We don't need to rebuild buttons every time, just update embed via callback
        pass

    def get_embed(self):
        desc = "Click buttons to build your dice pool."
        if self.expression:
            desc = f"```\n{self.expression}\n```"

        embed = discord.Embed(title="🎲 Dice Tray", description=desc, color=discord.Color.gold())
        return embed

    async def update_display(self, interaction):
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def add_term(self, interaction, term):
        if self.expression:
            self.expression += f" + {term}"
        else:
            self.expression = term
        await self.update_display(interaction)

    @discord.ui.button(label="D4", style=discord.ButtonStyle.secondary, row=0)
    async def d4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_term(interaction, "1d4")

    @discord.ui.button(label="D6", style=discord.ButtonStyle.secondary, row=0)
    async def d6(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_term(interaction, "1d6")

    @discord.ui.button(label="D8", style=discord.ButtonStyle.secondary, row=0)
    async def d8(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_term(interaction, "1d8")

    @discord.ui.button(label="D10", style=discord.ButtonStyle.secondary, row=0)
    async def d10(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_term(interaction, "1d10")

    @discord.ui.button(label="D12", style=discord.ButtonStyle.secondary, row=0)
    async def d12(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_term(interaction, "1d12")

    @discord.ui.button(label="D20", style=discord.ButtonStyle.secondary, row=1)
    async def d20(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_term(interaction, "1d20")

    @discord.ui.button(label="D100", style=discord.ButtonStyle.secondary, row=1)
    async def d100(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_term(interaction, "1d100")

    @discord.ui.button(label="+1", style=discord.ButtonStyle.secondary, row=1)
    async def plus1(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression += " + 1"
        await self.update_display(interaction)

    @discord.ui.button(label="+5", style=discord.ButtonStyle.secondary, row=1)
    async def plus5(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression += " + 5"
        await self.update_display(interaction)

    @discord.ui.button(label="Clear", style=discord.ButtonStyle.danger, row=1)
    async def clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression = ""
        await self.update_display(interaction)

    @discord.ui.button(label="ROLL!", style=discord.ButtonStyle.success, row=2, emoji="🎲")
    async def roll_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.expression:
            return await interaction.response.send_message("Add dice first!", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.delete_original_response()
        except Exception:
            pass  # ephemeral deletion may fail — not critical

        await self.cog._perform_roll(interaction, self.expression, 0, 0, True, "Regular")
