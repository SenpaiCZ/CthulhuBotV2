from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class AutoRoomCreate(BaseModel):
    """
    Schema for creating a new autoroom configuration.
    """
    guild_id: str
    creator_id: str
    channel_id: str
    name_format: str = "{user}'s room"

class RSSFeedCreate(BaseModel):
    """
    Schema for adding a new RSS feed.
    """
    guild_id: str
    channel_id: str
    url: str
    last_item_id: Optional[str] = None

class ReminderCreate(BaseModel):
    """
    Schema for creating a new user reminder.
    """
    user_id: str
    guild_id: str
    channel_id: str
    message: str
    due_at: datetime

class DeleterJobCreate(BaseModel):
    """
    Schema for creating a new deleter job.
    """
    guild_id: str
    channel_id: str
    user_id: str
    status: str = "active"
