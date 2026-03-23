from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime

class JournalEntryCreate(BaseModel):
    """
    Schema for creating a new journal entry.
    """
    guild_id: str
    journal_type: str  # 'master' or 'personal'
    author_id: str
    owner_id: Optional[str] = None
    title: str
    content: str
    images: List[str] = Field(default_factory=list)

class InventoryItemCreate(BaseModel):
    """
    Schema for adding an item to an investigator's inventory.
    """
    investigator_id: int
    name: str
    description: Optional[str] = None
    quantity: int = 1
    is_macguffin: bool = False

class KarmaUpdate(BaseModel):
    """
    Schema for updating a user's karma.
    """
    guild_id: str
    user_id: str
    amount: int

class HandoutCreate(BaseModel):
    """
    Schema for creating a new campaign handout.
    """
    guild_id: str
    title: str
    content: str
    image_url: Optional[str] = None
