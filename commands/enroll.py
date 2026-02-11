import discord
from discord.ext import commands
from discord import app_commands
from loadnsave import load_enroll_settings

class WizardSelect(discord.ui.Select):
    def __init__(self, view_parent, options, default_values):
        # Filter options to ensure valid length and formatting
        super().__init__(
            placeholder="Select your roles...",
            min_values=0,
            max_values=min(len(options), 25),
            options=options,
            row=0
        )
        self.view_parent = view_parent

        # Pre-select defaults if any (this sets the UI state)
        # However, the library handles rendering defaults based on the options passed.
        # We just need to make sure the options passed have 'default=True' set.
        pass

    async def callback(self, interaction: discord.Interaction):
        # Save state
        self.view_parent.selections[self.view_parent.current_page] = self.values
        await interaction.response.defer()

class WizardButton(discord.ui.Button):
    def __init__(self, view_parent, label, style, action, row=1):
        super().__init__(label=label, style=style, row=row)
        self.view_parent = view_parent
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        if self.action == 'back':
            await self.view_parent.go_back(interaction)
        elif self.action == 'next':
            await self.view_parent.go_next(interaction)
        elif self.action == 'submit':
            await self.view_parent.submit(interaction)
        elif self.action == 'cancel':
            await self.view_parent.cancel(interaction)

class EnrollView(discord.ui.View):
    def __init__(self, ctx, pages, final_message):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.pages = pages
        self.final_message = final_message
        self.current_page = 0
        self.selections = {} # page_index -> list of values

        self.setup_page()

    def setup_page(self):
        self.clear_items()

        page_data = self.pages[self.current_page]
        options_data = page_data.get('options', [])

        # 1. Add Select Menu if options exist
        if options_data:
            safe_options_data = options_data[:25]
            select_options = []

            current_selections = self.selections.get(self.current_page, [])

            for opt in safe_options_data:
                val = str(opt.get('role_id'))
                label = opt.get('label', 'Option')[:100]
                emoji = opt.get('emoji') or None
                is_default = val in current_selections

                select_options.append(discord.SelectOption(
                    label=label,
                    value=val,
                    emoji=emoji,
                    default=is_default
                ))

            if select_options:
                self.add_item(WizardSelect(self, select_options, current_selections))

        # 2. Add Navigation Buttons
        # Back
        if self.current_page > 0:
            self.add_item(WizardButton(self, "Back", discord.ButtonStyle.secondary, 'back'))

        # Next / Finish
        if self.current_page < len(self.pages) - 1:
            self.add_item(WizardButton(self, "Next", discord.ButtonStyle.primary, 'next'))
        else:
            self.add_item(WizardButton(self, "Finish", discord.ButtonStyle.success, 'submit'))

        # Cancel
        self.add_item(WizardButton(self, "Cancel", discord.ButtonStyle.danger, 'cancel'))

    async def update_message(self, interaction: discord.Interaction):
        page_data = self.pages[self.current_page]
        title = page_data.get('title', f"Step {self.current_page + 1}")
        desc = page_data.get('description', '')

        embed = discord.Embed(
            title=f"Enrollment: {title}",
            description=desc,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)}")

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

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

    async def submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)

        all_role_ids = set()
        for values in self.selections.values():
            for val in values:
                if val: all_role_ids.add(int(val))

        guild = interaction.guild
        member = interaction.user

        added_roles = []
        failed_roles = []

        for role_id in all_role_ids:
            role = guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role, reason="Enrollment Wizard")
                    added_roles.append(role.name)
                except discord.Forbidden:
                    failed_roles.append(role.name)
                except Exception as e:
                    print(f"Failed to add role {role_id}: {e}")
                    failed_roles.append(role.name)

        msg = self.final_message
        if failed_roles:
            msg += f"\n\nCould not assign the following roles (Permission Denied): {', '.join(failed_roles)}"

        await interaction.followup.send(msg, ephemeral=True)

        # Cleanup original message
        try:
            # We can't delete ephemeral messages usually, but if this was a slash command response,
            # we can edit it to remove content.
            # If it was a text command response, we can delete.
            if self.ctx.interaction:
                 await interaction.edit_original_response(content="Enrollment Complete.", embed=None, view=None)
            else:
                 await self.ctx.message.delete() # Delete command message
                 # We can't easily delete the bot's response message if we don't have handle to it easily
                 # But we can edit the interaction message (which is the bot's response)
                 await interaction.message.delete()
        except:
            pass

        self.stop()

class Enroll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="enroll", description="Start the new user enrollment process.")
    async def enroll(self, ctx):
        settings = await load_enroll_settings()
        guild_id = str(ctx.guild.id)

        guild_config = settings.get(guild_id, {})

        if not guild_config.get('enabled', False):
            msg = "Enrollment is not enabled on this server."
            if ctx.interaction:
                await ctx.send(msg, ephemeral=True)
            else:
                await ctx.send(msg)
            return

        pages = guild_config.get('pages', [])
        if not pages:
            msg = "No enrollment pages configured."
            if ctx.interaction:
                await ctx.send(msg, ephemeral=True)
            else:
                await ctx.send(msg)
            return

        final_msg = guild_config.get('final_message', "Enrollment complete!")

        view = EnrollView(ctx, pages, final_msg)

        first_page = pages[0]
        title = first_page.get('title', 'Start')
        desc = first_page.get('description', '')

        embed = discord.Embed(
            title=f"Enrollment: {title}",
            description=desc,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Page 1/{len(pages)}")

        if ctx.interaction:
            await ctx.send(embed=embed, view=view, ephemeral=True)
        else:
            await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Enroll(bot))
