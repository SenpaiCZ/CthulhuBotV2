from sqlalchemy.orm import Session
from models.guild_settings import GuildSettings as GuildSettingsModel
from schemas.settings import GuildSettingsUpdate, GuildSettingsBase
from typing import Optional

class SettingsService:
    @staticmethod
    def get_guild_settings(db: Session, guild_id: str) -> GuildSettingsModel:
        """
        Retrieve settings for a guild. If not found, initializes with defaults.
        """
        settings = db.query(GuildSettingsModel).filter(GuildSettingsModel.guild_id == guild_id).first()
        if not settings:
            return SettingsService.initialize_guild(db, guild_id)
        return settings

    @staticmethod
    def update_guild_settings(db: Session, guild_id: str, data: GuildSettingsUpdate) -> GuildSettingsModel:
        """
        Update settings for a guild.
        """
        settings = db.query(GuildSettingsModel).filter(GuildSettingsModel.guild_id == guild_id).first()
        if not settings:
            settings = SettingsService.initialize_guild(db, guild_id)
            
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
        
        db.commit()
        db.refresh(settings)
        return settings

    @staticmethod
    def initialize_guild(db: Session, guild_id: str) -> GuildSettingsModel:
        """
        Initialize a guild with default settings.
        """
        defaults = GuildSettingsBase()
        settings = GuildSettingsModel(
            guild_id=guild_id,
            **defaults.model_dump()
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
        return settings
