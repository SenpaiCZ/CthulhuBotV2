from pydantic import BaseModel, ConfigDict
from typing import Optional

class EmojiBase(BaseModel):
    """
    Base schema for emoji metadata.
    """
    category: str
    key: str
    value: str

class EmojiCreate(EmojiBase):
    """
    Schema for creating a new emoji entry.
    """
    pass

class Emoji(EmojiBase):
    """
    Schema for an emoji entry as returned from the database.
    """
    id: int
    
    model_config = ConfigDict(from_attributes=True)
