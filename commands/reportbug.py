import discord
from discord.ext import commands
from discord import app_commands
from discord import ui


class ReportBugModal(ui.Modal, title="Report a Bug"):
    def __init__(self, bot, author, guild, context_message=None):
        super().__init__()
        self.bot = bot
        self.author = author
        self.guild = guild
        self.context_message = context_message

        # Add fields
        self.bug_title = ui.TextInput(label="Bug Title", placeholder="Short summary...", max_length=100)
        self.bug_desc = ui.TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Detailed description...", max_length=1000)
        self.bug_steps = ui.TextInput(label="Steps to Reproduce", style=discord.TextStyle.paragraph, placeholder="1. Do X\n2. See Y...", required=False, max_length=1000)

        # Pre-fill context if any (e.g. from context menu)
        if context_message:
             content_preview = context_message.content
             if len(content_preview) > 900:
                 content_preview = content_preview[:900] + "..."
             self.bug_desc.default = f"Context: {content_preview}"

        self.add_item(self.bug_title)
        self.add_item(self.bug_desc)
        self.add_item(self.bug_steps)

    async def on_submit(self, interaction: discord.Interaction):
        # Construct the report message
        report_msg = (
            f"**Bug Report** from {self.author} (ID: {self.author.id})\n"
            f"**Server**: {self.guild} (ID: {self.guild.id})\n"
            f"**Title**: {self.bug_title.value}\n"
            f"**Description**: {self.bug_desc.value}\n"
        )
        if self.bug_steps.value:
            report_msg += f"**Steps**: {self.bug_steps.value}"

        if self.context_message:
            report_msg += f"\n**Context Message ID**: {self.context_message.id}"
            report_msg += f"\n**Context Channel**: {self.context_message.channel.mention}"

        # Send to developer
        dev_user = self.bot.get_user(214351769243877376)
        if dev_user:
            try:
                await dev_user.send(report_msg)
                await interaction.response.send_message("✅ Bug report sent successfully. Thank you!", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("❌ Failed to send report: Developer DMs are closed.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Error sending report: {e}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Developer not found. Please contact the bot owner directly.", ephemeral=True)


class reportbug(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    self.help_category = "Admin"
    # Register Context Menu
    self.ctx_menu = app_commands.ContextMenu(
        name='Report Message',
        callback=self.report_message_context,
    )
    self.ctx_menu.binding = self
    self.bot.tree.add_command(self.ctx_menu)

  def cog_unload(self):
    self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

  async def report_message_context(self, interaction: discord.Interaction, message: discord.Message):
      modal = ReportBugModal(self.bot, interaction.user, interaction.guild, context_message=message)
      await interaction.response.send_modal(modal)

  @app_commands.command(description="🐛 Send a bug report to the bot creator.")
  async def reportbug(self, interaction: discord.Interaction):
      """
      Send a bug report to the bot creator.
      """
      modal = ReportBugModal(self.bot, interaction.user, interaction.guild)
      await interaction.response.send_modal(modal)


async def setup(bot):
  await bot.add_cog(reportbug(bot))
