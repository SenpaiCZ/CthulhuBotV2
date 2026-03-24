from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime

class PollCreate(BaseModel):
    """
    Schema for creating a new poll.
    """
    message_id: str
    guild_id: str
    question: str
    options: List[str]
    votes: Dict[str, List[str]] = Field(default_factory=dict)

class GiveawayCreate(BaseModel):
    """
    Schema for creating a new giveaway.
    """
    message_id: str
    guild_id: str
    title: str
    prize: str
    end_time: datetime
    participants: List[str] = Field(default_factory=list)

class PogoEventCreate(BaseModel):
    """
    Schema for creating a new Pokemon GO event.
    """
    guild_id: str
    name: str
    timestamp: datetime
    location: Optional[str] = None

class GamerRoleCreate(BaseModel):
    """
    Schema for creating a new gamer role assignment.
    """
    guild_id: str
    role_id: str
    category: str
