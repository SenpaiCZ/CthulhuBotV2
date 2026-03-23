import discord
from discord.ui import View, Button
from typing import List, Optional
import os
from dashboard.file_utils import sanitize_filename
from commands._codex_embeds import (
    create_monster_embed, create_deity_embed, create_spell_embed,
    create_weapon_embed, create_occupation_embed, create_archetype_embed,
    create_generic_embed, create_timeline_embed
)
from models.codex import CodexEntry

class CodexRendererView(View):
    def __init__(self, entries: List[CodexEntry], current_index: int = 0):
        super().__init__(timeout=300)
        self.entries = entries
        self.current_index = current_index
        self._update_buttons()

    def _update_buttons(self):
        self.prev_button.disabled = self.current_index == 0
        self.next_button.disabled = self.current_index >= len(self.entries) - 1
        
        # Only show pagination if there's more than one entry
        if len(self.entries) <= 1:
            self.remove_item(self.prev_button)
            self.remove_item(self.next_button)

    def get_image_file(self, type_slug: str, name: str) -> Optional[discord.File]:
        """Checks if a local image exists and returns a discord.File object."""
        safe_name = sanitize_filename(name)
        target_dir = os.path.join("images", type_slug.lower())
        
        if not os.path.exists(target_dir):
            return None

        for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
            filename = f"{safe_name}{ext}"
            path = os.path.join(target_dir, filename)
            if os.path.exists(path):
                return discord.File(path, filename=filename)
        return None

    def get_embed_and_file(self):
        entry = self.entries[self.current_index]
        category = entry.category.lower()
        data = entry.content
        name = entry.name
        
        # Handle images
        file = self.get_image_file(category, name)
        
        embed = None
        if category == "monster":
            embed = create_monster_embed(data, name, file)
        elif category == "deity":
            embed = create_deity_embed(data, name, file)
        elif category == "spell":
            embed = create_spell_embed(data, name, file)
        elif category == "weapon":
            embed = create_weapon_embed(data, name, file)
        elif category == "occupation":
            embed = create_occupation_embed(data, name, file)
        elif category == "archetype":
            embed = create_archetype_embed(data, name, file)
        elif category in ["invention", "year"]:
            embed = create_timeline_embed(data, name, category, file)
        else:
            embed = create_generic_embed(data, name, category, file)
            
        if len(self.entries) > 1:
            embed.set_footer(text=f"Result {self.current_index + 1} of {len(self.entries)}")
            
        return embed, file

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.grey, emoji="⬅️")
    async def prev_button(self, interaction: discord.Interaction, button: Button):
        if self.current_index > 0:
            self.current_index -= 1
            self._update_buttons()
            embed, file = self.get_embed_and_file()
            if file:
                await interaction.response.edit_message(embed=embed, view=self, attachments=[file])
            else:
                await interaction.response.edit_message(embed=embed, view=self, attachments=[])

    @discord.ui.button(label="Next", style=discord.ButtonStyle.grey, emoji="➡️")
    async def next_button(self, interaction: discord.Interaction, button: Button):
        if self.current_index < len(self.entries) - 1:
            self.current_index += 1
            self._update_buttons()
            embed, file = self.get_embed_and_file()
            if file:
                await interaction.response.edit_message(embed=embed, view=self, attachments=[file])
            else:
                await interaction.response.edit_message(embed=embed, view=self, attachments=[])
