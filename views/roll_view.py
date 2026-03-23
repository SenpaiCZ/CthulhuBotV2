import discord
import random
from typing import Optional, List, Dict, Any, Callable
from discord.ui import View, Button
from services.roll_service import RollService
from services.character_service import CharacterService
from schemas.roll import RollRequest, RollResult
from sqlalchemy.orm import Session

class RollView(View):
    """
    UI component for displaying and interacting with CoC roll results.
    Handles Bonus/Penalty dice, Pushing rolls, and Spending Luck.
    """
    def __init__(
        self,
        interaction: discord.Interaction,
        roll_result: RollResult,
        stat_name: str,
        stat_value: int,
        difficulty: str = "Regular",
        investigator: Any = None,
        db: Session = None,
        on_complete: Optional[Callable] = None
    ):
        super().__init__(timeout=300)
        self.interaction = interaction
        self.roll_result = roll_result
        self.stat_name = stat_name
        self.stat_value = stat_value
        self.difficulty = difficulty
        self.investigator = investigator
        self.db = db
        self.on_complete = on_complete
        
        self.luck_used = False
        self.pushed = False
        
        self._update_buttons()

    def _update_buttons(self):
        # Find buttons
        bonus_btn = next((c for c in self.children if isinstance(c, Button) and c.label == "Bonus Die"), None)
        penalty_btn = next((c for c in self.children if isinstance(c, Button) and c.label == "Penalty Die"), None)
        luck_btn = next((c for c in self.children if isinstance(c, Button) and "Luck" in (c.label or "")), None)
        push_btn = next((c for c in self.children if isinstance(c, Button) and c.label == "Push Roll"), None)

        if self.luck_used or self.pushed:
            if bonus_btn: bonus_btn.disabled = True
            if penalty_btn: penalty_btn.disabled = True
            if luck_btn: luck_btn.disabled = True
            if push_btn: push_btn.disabled = True
            return

        # Bonus/Penalty Die limits (max 2)
        if bonus_btn: bonus_btn.disabled = self.roll_result.net_dice >= 2
        if penalty_btn: penalty_btn.disabled = self.roll_result.net_dice <= -2

        # Push Roll (Only on Normal Fail, and not if already pushed)
        can_push = (
            self.roll_result.net_dice == 0 and 
            not self.roll_result.is_success and 
            not self.roll_result.is_fumble and
            self.stat_name.upper() != "LUCK"
        )
        if push_btn: push_btn.disabled = not can_push

        # Luck Spending
        can_luck = False
        luck_cost = 0
        if (
            self.investigator and 
            self.roll_result.net_dice == 0 and 
            self.stat_name.upper() != "LUCK" and
            not self.roll_result.is_success and
            not self.roll_result.is_fumble
        ):
            # Calculate cost to reach Regular Success
            target_value = self.stat_value
            if self.difficulty == "Hard":
                target_value = self.stat_value // 2
            elif self.difficulty == "Extreme":
                target_value = self.stat_value // 5
                
            luck_cost = self.roll_result.final_roll - target_value
            if 0 < luck_cost <= self.investigator.luck:
                can_luck = True

        if luck_btn:
            luck_btn.disabled = not can_luck
            if can_luck:
                luck_btn.label = f"Use Luck (-{luck_cost})"
            else:
                luck_btn.label = "Use Luck"

    async def _update_message(self, interaction: discord.Interaction):
        self._update_buttons()
        
        embed = interaction.message.embeds[0]
        
        # Update Description
        dice_text = "Normal"
        if self.roll_result.net_dice > 0: dice_text = f"Bonus ({self.roll_result.net_dice})"
        elif self.roll_result.net_dice < 0: dice_text = f"Penalty ({abs(self.roll_result.net_dice)})"

        # Note: In RollService.calculate_roll, 'rolls' contains [tens+ones, tens+ones, ...]
        # We need to extract the tens and ones for display if we want to match old UI exactly.
        # For now, let's just show the final roll and the pool.
        rolls_str = ", ".join(map(str, self.roll_result.rolls))
        
        description = f"{interaction.user.mention} :game_die: **{dice_text}** Check\n"
        description += f"Dice: [{rolls_str}] -> **{self.roll_result.final_roll}**\n\n"
        description += f"**{self.roll_result.result_text}**\n\n"
        description += f"**{self.stat_name}**: {self.stat_value} - {self.stat_value // 2} - {self.stat_value // 5}\n"
        
        if self.investigator:
            description += f":four_leaf_clover: LUCK: {self.investigator.luck}"

        embed.description = description
        
        # Color
        color = discord.Color.green()
        if self.roll_result.result_level >= 4: color = 0xF1C40F # Gold
        elif self.roll_result.result_level >= 2: color = 0x2ECC71 # Green
        elif self.roll_result.result_level == 1: color = 0xE74C3C # Red
        elif self.roll_result.result_level == 0: color = 0x992D22 # Dark Red
        embed.color = color

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Bonus Die", style=discord.ButtonStyle.success, emoji="🟢", row=0)
    async def add_bonus_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        request = RollRequest(
            stat_name=self.stat_name,
            bonus_dice=self.roll_result.net_dice + 1 if self.roll_result.net_dice >= 0 else 0,
            penalty_dice=abs(self.roll_result.net_dice - 1) if self.roll_result.net_dice < 0 else 0,
            difficulty=self.difficulty
        )
        # Fix: RollRequest expects absolute bonus/penalty
        new_bonus = 0
        new_penalty = 0
        net = self.roll_result.net_dice + 1
        if net > 0: new_bonus = net
        elif net < 0: new_penalty = abs(net)
        
        request = RollRequest(
            stat_name=self.stat_name,
            bonus_dice=new_bonus,
            penalty_dice=new_penalty,
            difficulty=self.difficulty
        )
        
        self.roll_result = RollService.calculate_roll(request, self.stat_value)
        await self._update_message(interaction)

    @discord.ui.button(label="Penalty Die", style=discord.ButtonStyle.danger, emoji="🔴", row=0)
    async def add_penalty_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        new_bonus = 0
        new_penalty = 0
        net = self.roll_result.net_dice - 1
        if net > 0: new_bonus = net
        elif net < 0: new_penalty = abs(net)
        
        request = RollRequest(
            stat_name=self.stat_name,
            bonus_dice=new_bonus,
            penalty_dice=new_penalty,
            difficulty=self.difficulty
        )
        
        self.roll_result = RollService.calculate_roll(request, self.stat_value)
        await self._update_message(interaction)

    @discord.ui.button(label="Use Luck", style=discord.ButtonStyle.primary, emoji="🍀", row=1)
    async def luck_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.investigator or not self.db:
            return await interaction.response.send_message("No investigator linked for luck spending.", ephemeral=True)

        target_value = self.stat_value
        if self.difficulty == "Hard":
            target_value = self.stat_value // 2
        elif self.difficulty == "Extreme":
            target_value = self.stat_value // 5
            
        cost = self.roll_result.final_roll - target_value
        
        # Update Investigator Luck
        new_luck = self.investigator.luck - cost
        CharacterService.update_investigator(self.db, self.investigator.id, {"luck": new_luck})
        
        # Update Roll Result to Success
        self.roll_result.final_roll = target_value
        self.roll_result.is_success = True
        self.roll_result.result_text = f"Success (LUCK Used: -{cost})"
        self.roll_result.result_level = 2 # Regular Success
        if self.difficulty == "Hard": self.roll_result.result_level = 3
        elif self.difficulty == "Extreme": self.roll_result.result_level = 4
        
        self.luck_used = True
        await self._update_message(interaction)

    @discord.ui.button(label="Push Roll", style=discord.ButtonStyle.secondary, emoji="🔄", row=1)
    async def push_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Pushing a roll is a completely new roll with no bonus/penalty
        request = RollRequest(
            stat_name=self.stat_name,
            bonus_dice=0,
            penalty_dice=0,
            difficulty=self.difficulty
        )
        self.roll_result = RollService.calculate_roll(request, self.stat_value)
        self.pushed = True
        
        self.roll_result.result_text = f"PUSHED: {self.roll_result.result_text}"
        if not self.roll_result.is_success:
            self.roll_result.result_text += "\n:warning: **DIRE CONSEQUENCES!**"
            
        await self._update_message(interaction)

    @discord.ui.button(label="Done", style=discord.ButtonStyle.secondary, row=1)
    async def done_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        if self.on_complete:
            await self.on_complete(self.roll_result)
            
        self.stop()
        # Disable all buttons
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await interaction.edit_original_response(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message("This is not your roll!", ephemeral=True)
            return False
        return True
