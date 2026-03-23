import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List
from sqlalchemy.orm import Session
from models.database import SessionLocal
from services.codex_service import CodexService
from views.codex_renderer import CodexRendererView

class Codex(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_category = "Codex"

    async def _handle_lookup(self, interaction: discord.Interaction, name: Optional[str], category: str):
        """Helper to handle codex lookups via service and renderer view."""
        db = SessionLocal()
        try:
            if name:
                # Search for entries matching the name
                entries = CodexService.search_entries(db, name, category)
                if not entries:
                    await interaction.response.send_message(f"No {category} found matching '{name}'.", ephemeral=True)
                    return
                
                view = CodexRendererView(entries)
                embed, file = view.get_embed_and_file()
                
                kwargs = {"embed": embed, "view": view, "ephemeral": True}
                if file:
                    kwargs["file"] = file
                
                await interaction.response.send_message(**kwargs)
            else:
                # Get a random entry if no name provided
                entry = CodexService.get_random_entry(db, category)
                if not entry:
                    await interaction.response.send_message(f"No entries found in category '{category}'.", ephemeral=True)
                    return
                
                view = CodexRendererView([entry])
                embed, file = view.get_embed_and_file()
                
                kwargs = {"embed": embed, "view": view, "ephemeral": True}
                if file:
                    kwargs["file"] = file
                
                await interaction.response.send_message(**kwargs)
        finally:
            db.close()

    async def _get_autocomplete(self, interaction: discord.Interaction, current: str, category: str) -> List[app_commands.Choice[str]]:
        db = SessionLocal()
        try:
            choices = CodexService.get_autocomplete(db, current, category)
            return [app_commands.Choice(name=name, value=name) for name in choices]
        finally:
            db.close()

    @app_commands.command(description="👹 Displays a monster sheet.")
    async def monster(self, interaction: discord.Interaction, name: str = None):
        await self._handle_lookup(interaction, name, "Monster")

    @monster.autocomplete('name')
    async def monster_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._get_autocomplete(interaction, current, "Monster")

    @app_commands.command(description="✨ Displays a spell.")
    async def spell(self, interaction: discord.Interaction, name: str = None):
        await self._handle_lookup(interaction, name, "Spell")

    @spell.autocomplete('name')
    async def spell_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._get_autocomplete(interaction, current, "Spell")

    @app_commands.command(description="⚡ Displays a deity sheet.")
    async def deity(self, interaction: discord.Interaction, name: str = None):
        await self._handle_lookup(interaction, name, "Deity")

    @deity.autocomplete('name')
    async def deity_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._get_autocomplete(interaction, current, "Deity")

    @app_commands.command(description="📔 Opens the Codex to view all entries.")
    async def codex(self, interaction: discord.Interaction, search: str = None):
        """Search the entire codex."""
        await self._handle_lookup(interaction, search, None)

    @app_commands.command(name="archetype", description="🎭 Displays a Pulp Cthulhu Archetype.")
    async def archetype(self, interaction: discord.Interaction, name: str = None):
        await self._handle_lookup(interaction, name, "Archetype")

    @archetype.autocomplete('name')
    async def archetype_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._get_autocomplete(interaction, current, "Archetype")

    @app_commands.command(name="weapon", description="🔫 Displays a weapon.")
    async def weapon(self, interaction: discord.Interaction, name: str = None):
        await self._handle_lookup(interaction, name, "Weapon")

    @weapon.autocomplete('name')
    async def weapon_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._get_autocomplete(interaction, current, "Weapon")

    @app_commands.command(name="occupation", description="🕵️ Displays an occupation.")
    async def occupation(self, interaction: discord.Interaction, name: str = None):
        await self._handle_lookup(interaction, name, "Occupation")

    @occupation.autocomplete('name')
    async def occupation_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._get_autocomplete(interaction, current, "Occupation")

async def setup(bot):
    await bot.add_cog(Codex(bot))
