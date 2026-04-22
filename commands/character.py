import discord
from discord.ext import commands
from discord import app_commands
from loadnsave import load_player_stats, load_gamemode_stats, save_player_stats
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

        # Show Connections
        connections = char_data.get("Connections", [])
        if connections:
             content = "\n".join([f"🔗 {entry}" for entry in connections])
             if len(content) > 1024: content = content[:1021] + "..."
             embed.add_field(name="🤝 Connections", value=content, inline=False)

        view = None
        if can_edit:
            view = BackstoryCategorySelectView(interaction.user, server_id, user_id, mode="add")
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- Connections Sub-commands ---
    connections_group = app_commands.Group(name="connections", description="🤝 Manage character connections.")

    @connections_group.command(name="add", description="➕ Add a new connection/relationship.")
    @app_commands.describe(text="Description of the connection (e.g., 'Friend with Harvey')")
    async def connections_add(self, interaction: discord.Interaction, text: str):
        server_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        
        success, msg = await self._add_connection_logic(server_id, user_id, text)
        await interaction.response.send_message(msg, ephemeral=True)

    @connections_group.command(name="remove", description="➖ Remove a connection.")
    async def connections_remove(self, interaction: discord.Interaction):
        server_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        
        player_stats = await load_player_stats()
        if server_id not in player_stats or user_id not in player_stats[server_id]:
             return await interaction.response.send_message("You don't have an investigator.", ephemeral=True)
        
        connections = player_stats[server_id][user_id].get("Connections", [])
        if not connections:
             return await interaction.response.send_message("No connections to remove.", ephemeral=True)

        # Select Menu for removal
        class ConnectionRemoveSelect(discord.ui.Select):
            def __init__(self, cog, server_id, user_id, connections):
                self.cog = cog
                self.server_id = server_id
                self.user_id = user_id
                options = [discord.SelectOption(label=c[:100], value=str(i)) for i, c in enumerate(connections[:25])]
                super().__init__(placeholder="Select connection to remove...", options=options)

            async def callback(self, inter: discord.Interaction):
                idx = int(self.values[0])
                success, msg = await self.cog._remove_connection_logic(self.server_id, self.user_id, idx)
                await inter.response.send_message(msg, ephemeral=True)
                self.view.stop()

        view = discord.ui.View()
        view.add_item(ConnectionRemoveSelect(self, server_id, user_id, connections))
        await interaction.response.send_message("Select a connection to remove:", view=view, ephemeral=True)

    # --- Logic Helpers (Testable) ---
    async def _add_connection_logic(self, server_id, user_id, text):
        player_stats = await load_player_stats()
        if server_id not in player_stats or user_id not in player_stats[server_id]:
             return False, "Investigator not found."
        
        char_data = player_stats[server_id][user_id]
        if "Connections" not in char_data:
             char_data["Connections"] = []
        
        char_data["Connections"].append(text)
        await save_player_stats(player_stats)
        return True, f"✅ Added connection: **{text}**"

    async def _remove_connection_logic(self, server_id, user_id, index):
        player_stats = await load_player_stats()
        if server_id not in player_stats or user_id not in player_stats[server_id]:
             return False, "Investigator not found."
        
        char_data = player_stats[server_id][user_id]
        connections = char_data.get("Connections", [])
        
        if 0 <= index < len(connections):
             removed = connections.pop(index)
             await save_player_stats(player_stats)
             return True, f"🗑️ Removed connection: **{removed}**"
        return False, "Connection index out of range."

async def setup(bot):
    await bot.add_cog(Character(bot))
