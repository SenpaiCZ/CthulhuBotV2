import discord
from discord.ui import View, Select, Button, Modal, TextInput
from commands._roll_views import RollResultView
from support_functions import MockContext
from rapidfuzz import process, fuzz


class SkillSearchModal(Modal, title="Search Skill"):
    skill_name = TextInput(label="Skill Name", placeholder="e.g. Spot Hidden", min_length=2)

    def __init__(self, view):
        super().__init__()
        self.dashboard_view = view

    async def on_submit(self, interaction: discord.Interaction):
        term = self.skill_name.value
        all_skills = self.dashboard_view._get_skill_list() # list of (name, val)
        skill_names = [s[0] for s in all_skills]

        # Use rapidfuzz for matching
        # 1. Exact/Substring check first (fast)
        exact_matches = []
        term_lower = term.lower()
        for name, val in all_skills:
            if term_lower in name.lower():
                exact_matches.append((name, val))

        if exact_matches:
             final_matches = exact_matches
        else:
             # 2. Fuzzy Match
             results = process.extract(term, skill_names, scorer=fuzz.WRatio, limit=25, score_cutoff=50)
             final_matches = []
             for _, _, idx in results:
                 final_matches.append(all_skills[idx])

        if not final_matches:
            # Suggestion logic? Or just fail gracefully.
            return await interaction.response.send_message(f"No skills found similar to '{term}'.", ephemeral=True)

        # Re-render with matches
        # We can reuse SkillRollSelect with filtered options
        view = View(timeout=60)
        view.add_item(SkillRollSelect(self.dashboard_view, final_matches[:25]))

        # Add Back Button
        back_btn = Button(label="Back", style=discord.ButtonStyle.secondary, row=1)
        async def back_callback(interaction: discord.Interaction):
            await self.dashboard_view.refresh_dashboard(interaction)
        back_btn.callback = back_callback
        view.add_item(back_btn)

        await interaction.response.edit_message(content=f"Found {len(final_matches)} matches for '{term}':", embed=None, view=view)


class SkillRollSelect(Select):
    def __init__(self, view, skills_list):
        self.dashboard_view = view
        options = []
        for name, val in skills_list:
            emoji = view._get_skill_emoji(name)
            label = f"{name} ({val}%)"
            options.append(discord.SelectOption(label=label, value=name, emoji=emoji))

        super().__init__(placeholder="🎲 Choose a skill to roll...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        skill_name = self.values[0]
        char_data = self.dashboard_view.char_data

        # Determine value (handle specializations if needed, though they should be keys in char_data)
        current_val = char_data.get(skill_name, 0)

        # Get Roll Cog
        roll_cog = interaction.client.get_cog("Roll")
        if not roll_cog:
            return await interaction.response.send_message("Roll system unavailable.", ephemeral=True)

        # Perform Roll logic
        # We want to use RollResultView to show the result
        # Calculate Roll
        import random
        ones = random.randint(0, 9)
        tens = random.choice([0, 10, 20, 30, 40, 50, 60, 70, 80, 90])
        roll_val = tens + ones
        if roll_val == 0: roll_val = 100

        result_text, result_tier = roll_cog.calculate_roll_result(roll_val, current_val)

        # Check Malfunction (not applicable for generic skill rolls usually, unless firearm)
        # We'll skip complex malfunction checks here for simplicity, or default to 100

        ctx = MockContext(interaction)

        # Luck Threshold
        from loadnsave import load_luck_stats
        luck_threshold = (await load_luck_stats()).get(self.dashboard_view.server_id, 10)

        # Create View
        # Use owner_id for mock stats so Luck logic works correctly for the character owner
        view = RollResultView(
            ctx=ctx,
            cog=roll_cog,
            player_stats={self.dashboard_view.server_id: {str(self.dashboard_view.owner_id): char_data}}, # Mock full stats structure
            server_id=self.dashboard_view.server_id,
            user_id=str(self.dashboard_view.owner_id),
            stat_name=skill_name,
            current_value=current_val,
            ones_roll=ones,
            tens_rolls=[tens],
            net_dice=0,
            result_tier=result_tier,
            luck_threshold=luck_threshold
        )

        # Create Embed
        color = discord.Color.green()
        if result_tier == 5 or result_tier == 4: color = 0xF1C40F
        elif result_tier == 3 or result_tier == 2: color = 0x2ECC71
        elif result_tier == 1: color = 0xE74C3C
        elif result_tier == 0: color = 0x992D22

        desc = f"{interaction.user.mention} :game_die: **{skill_name}** Check\n"
        desc += f"Dice: [{tens if tens!=0 else '00'}] + {ones} -> **{roll_val}**\n\n"
        desc += f"**{result_text}**\n\n"
        desc += f"**{skill_name}**: {current_val} - {current_val//2} - {current_val//5}\n"
        desc += f":four_leaf_clover: LUCK: {char_data.get('LUCK', 0)}"

        embed = discord.Embed(description=desc, color=color)

        # Send Publicly (so group sees result)
        msg = await interaction.channel.send(embed=embed, view=view)
        view.message = msg

        # Update Ephemeral Dashboard to say "Rolled!" and provide Back button
        back_view = View()
        async def back_callback(inter: discord.Interaction):
            await self.dashboard_view.refresh_dashboard(inter)

        btn = Button(label="Back to Sheet", style=discord.ButtonStyle.secondary)
        btn.callback = back_callback
        back_view.add_item(btn)

        await interaction.response.edit_message(content=f"🎲 Rolled **{skill_name}**! Check the channel.", embed=None, view=back_view)
