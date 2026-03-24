import discord

class WizardSelect(discord.ui.Select):
    def __init__(self, view_parent, options, default_values):
        super().__init__(
            placeholder="Select your roles...",
            min_values=0,
            max_values=min(len(options), 25),
            options=options,
            row=0
        )
        self.view_parent = view_parent

    async def callback(self, interaction: discord.Interaction):
        self.view_parent.selections[self.view_parent.current_page] = self.values
        await interaction.response.defer()

class WizardButton(discord.ui.Button):
    def __init__(self, view_parent, label, style, action, row=1):
        super().__init__(label=label, style=style, row=row)
        self.view_parent = view_parent
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        if self.action == 'back': await self.view_parent.go_back(interaction)
        elif self.action == 'next': await self.view_parent.go_next(interaction)
        elif self.action == 'submit': await self.view_parent.submit(interaction)
        elif self.action == 'cancel': await self.view_parent.cancel(interaction)

class EnrollView(discord.ui.View):
    def __init__(self, pages, final_message):
        super().__init__(timeout=300)
        self.pages, self.final_message = pages, final_message
        self.current_page, self.selections = 0, {}
        self.setup_page()

    def setup_page(self):
        self.clear_items()
        page_data = self.pages[self.current_page]
        options_data = page_data.get('options', [])
        if options_data:
            current_selections = self.selections.get(self.current_page, [])
            select_options = [
                discord.SelectOption(
                    label=opt.get('label', 'Option')[:100],
                    value=str(opt.get('role_id')),
                    emoji=opt.get('emoji') or None,
                    default=str(opt.get('role_id')) in current_selections
                ) for opt in options_data[:25]
            ]
            if select_options: self.add_item(WizardSelect(self, select_options, current_selections))
        
        if self.current_page > 0: self.add_item(WizardButton(self, "Back", discord.ButtonStyle.secondary, 'back'))
        if self.current_page < len(self.pages) - 1: self.add_item(WizardButton(self, "Next", discord.ButtonStyle.primary, 'next'))
        else: self.add_item(WizardButton(self, "Finish", discord.ButtonStyle.success, 'submit'))
        self.add_item(WizardButton(self, "Cancel", discord.ButtonStyle.danger, 'cancel'))

    async def update_message(self, interaction: discord.Interaction):
        page_data = self.pages[self.current_page]
        embed = discord.Embed(title=f"Enrollment: {page_data.get('title', 'Step')}", description=page_data.get('description', ''), color=discord.Color.blue())
        embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)}")
        if interaction.response.is_done(): await interaction.edit_original_response(embed=embed, view=self)
        else: await interaction.response.edit_message(embed=embed, view=self)

    async def go_back(self, interaction: discord.Interaction):
        self.current_page -= 1
        self.setup_page()
        await self.update_message(interaction)

    async def go_next(self, interaction: discord.Interaction):
        self.current_page += 1
        self.setup_page()
        await self.update_message(interaction)

    async def cancel(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Enrollment cancelled.", embed=None, view=None)
        self.stop()

class AddSkillModal(discord.ui.Modal, title="Add Custom Skill"):
    skill_name_input = discord.ui.TextInput(label="Skill Name", placeholder="e.g. Drive (Tank)", min_length=1, max_length=100)
    skill_value_input = discord.ui.TextInput(label="Starting Value", placeholder="e.g. 40", min_length=1, max_length=3)

    def __init__(self, investigator_id):
        super().__init__()
        self.investigator_id = investigator_id

    async def on_submit(self, interaction: discord.Interaction):
        from models.database import SessionLocal
        from services.character_service import CharacterService
        val_str = self.skill_value_input.value.strip()
        if not val_str.isdigit(): return await interaction.response.send_message("Number required (0-100).", ephemeral=True)
        val = int(val_str)
        if val < 0: return await interaction.response.send_message("No negative values.", ephemeral=True)
        db = SessionLocal()
        try:
            inv = CharacterService.get_investigator(db, self.investigator_id)
            if any(k.lower() == self.skill_name_input.value.strip().lower() for k in (inv.skills or {}).keys()):
                return await interaction.response.send_message("Skill already exists.", ephemeral=True)
            CharacterService.add_skill(db, self.investigator_id, self.skill_name_input.value.strip(), val)
            await interaction.response.send_message(f"Added **{self.skill_name_input.value}** ({val}).", ephemeral=True)
        finally: db.close()

class RemoveSkillView(discord.ui.View):
    def __init__(self, investigator_id, skill_name, user_id):
        super().__init__(timeout=60)
        self.investigator_id, self.skill_name, self.user_id = investigator_id, skill_name, user_id

    @discord.ui.button(label="Confirm Remove", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id: return await interaction.response.send_message("Not yours!", ephemeral=True)
        from models.database import SessionLocal
        from services.character_service import CharacterService
        db = SessionLocal()
        try:
            CharacterService.remove_skill(db, self.investigator_id, self.skill_name)
            await interaction.response.edit_message(content=f"Removed **{self.skill_name}**.", view=None)
        finally: db.close()
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Cancelled.", view=None)
        self.stop()
