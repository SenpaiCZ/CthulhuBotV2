from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Optional, Any

class GuildSettingsBase(BaseModel):
    """
    Base schema for Guild Settings data shared across models.
    """
    luck_threshold: int = Field(default=10, ge=0, description="Luck threshold for spending luck.")
    max_starting_skill: int = Field(default=75, ge=1, le=99, description="Max percentage for starting skills.")
    game_mode: str = Field(default="Call of Cthulhu", description="Game mode: 'Call of Cthulhu' or 'Pulp of Cthulhu'.")
    
    # JSON fields
    karma_settings: Dict[str, Any] = Field(default_factory=dict)
    loot_settings: Dict[str, Any] = Field(default_factory=dict)
    pogo_settings: Dict[str, Any] = Field(default_factory=dict)
    autorooms: Dict[str, Any] = Field(default_factory=dict)
    rss_data: Dict[str, Any] = Field(default_factory=dict)
    gamerole_settings: Dict[str, Any] = Field(default_factory=dict)
    enroll_settings: Dict[str, Any] = Field(default_factory=dict)
    skill_sound_settings: Dict[str, Any] = Field(default_factory=dict)
    fonts_config: Dict[str, Any] = Field(default_factory=dict)
    soundboard_settings: Dict[str, Any] = Field(default_factory=dict)
    server_volumes: Dict[str, Any] = Field(default_factory=dict)
    smart_react: Dict[str, Any] = Field(default_factory=dict)
    reaction_roles: Dict[str, Any] = Field(default_factory=dict)
    luck_stats: Dict[str, Any] = Field(default_factory=dict)
    skill_settings: Dict[str, Any] = Field(default_factory=dict)

class GuildSettingsUpdate(BaseModel):
    """
    Schema for updating Guild Settings. All fields are optional.
    """
    luck_threshold: Optional[int] = Field(None, ge=0)
    max_starting_skill: Optional[int] = Field(None, ge=1, le=99)
    game_mode: Optional[str] = None
    karma_settings: Optional[Dict[str, Any]] = None
    loot_settings: Optional[Dict[str, Any]] = None
    pogo_settings: Optional[Dict[str, Any]] = None
    autorooms: Optional[Dict[str, Any]] = None
    rss_data: Optional[Dict[str, Any]] = None
    gamerole_settings: Optional[Dict[str, Any]] = None
    enroll_settings: Optional[Dict[str, Any]] = None
    skill_sound_settings: Optional[Dict[str, Any]] = None
    fonts_config: Optional[Dict[str, Any]] = None
    soundboard_settings: Optional[Dict[str, Any]] = None
    server_volumes: Optional[Dict[str, Any]] = None
    smart_react: Optional[Dict[str, Any]] = None
    reaction_roles: Optional[Dict[str, Any]] = None
    luck_stats: Optional[Dict[str, Any]] = None
    skill_settings: Optional[Dict[str, Any]] = None

class GuildSettings(GuildSettingsBase):
    """
    Schema for Guild Settings as returned from the database, including the primary key.
    """
    guild_id: str
    
    model_config = ConfigDict(from_attributes=True)
