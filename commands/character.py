import discord
from discord.ext import commands
from discord import app_commands
from loadnsave import load_player_stats, load_gamemode_stats
from commands._backstory_common import BackstoryCategorySelectView

class Character(commands.GroupCog, name="character"):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Player"

    @app_commands.command(name="backstory", description="📜 View or edit your character's backstory.")
    @app_commands.describe(member="The member whose backstory you want to see")
    async def backstory(self, interaction: discord.Interaction, member: discord.Member = None):
        if interaction.guild is None:
            await interaction.response.send_message("This command is not allowed in DMs.", ephemeral=True)
            return

        if member is None:
            user_id = str(interaction.user.id)
            member = interaction.user
        else:
            user_id = str(member.id)

        server_id = str(interaction.guild.id)
        player_stats = await load_player_stats()

        if server_id not in player_stats or user_id not in player_stats[server_id]:
            await interaction.response.send_message(f"{member.display_name} doesn't have an investigator.", ephemeral=True)
            return

        char_data = player_stats[server_id][user_id]
        backstory = char_data.get("Backstory", {})

        # Determine if the requester can edit
        can_edit = (str(interaction.user.id) == user_id) or interaction.user.guild_permissions.administrator

        embed = discord.Embed(
            title=f"📜 Backstory: {char_data.get('NAME', 'Unknown')}",
            color=discord.Color.gold()
        )

        def format_entries(entries):
            if isinstance(entries, list):
                if not entries: return "*None*"
                return "\n".join([f"• {entry}" for entry in entries])
            return str(entries)

        # Show Core Backstory Fields first
        core_fields = [
            "Personal Description", "Ideology/Beliefs", "Significant People",
            "Meaningful Locations", "Treasured Possessions", "Traits"
        ]
        
        # Compatibility check for "Ideology and Beliefs" vs "Ideology/Beliefs"
        legacy_map = {
            "Ideology/Beliefs": "Ideology and Beliefs"
        }

        for field in core_fields:
            val = backstory.get(field)
            if not val and field in legacy_map:
                val = backstory.get(legacy_map[field])
            
            content = format_entries(val)
            if len(content) > 1024: content = content[:1021] + "..."
            embed.add_field(name=field, value=content, inline=False)

        view = None
        if can_edit:
            # We reuse BackstoryCategorySelectView for editing
            # But we need to make sure it includes our specific core fields
            # BackstoryCategorySelectView uses CATEGORIES from _backstory_common.py
            view = BackstoryCategorySelectView(interaction.user, server_id, user_id, mode="add")
            # We can add more buttons to the view if needed, but for now reuse existing logic
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Character(bot))
