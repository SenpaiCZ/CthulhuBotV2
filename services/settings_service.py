from sqlalchemy.orm import Session
from models.guild_settings import GuildSettings as GuildSettingsModel
from schemas.settings import GuildSettingsUpdate, GuildSettingsBase
from typing import Optional, Any, Dict

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

    @staticmethod
    def get_setting(db: Session, guild_id: str, key: str, default: Any = None) -> Any:
        """
        Retrieve a specific setting value for a guild.
        """
        settings = SettingsService.get_guild_settings(db, guild_id)
        return getattr(settings, key, default)

    @staticmethod
    def set_setting(db: Session, guild_id: str, key: str, value: Any) -> GuildSettingsModel:
        """
        Set a specific setting value for a guild.
        """
        settings = SettingsService.get_guild_settings(db, guild_id)
        if hasattr(settings, key):
            setattr(settings, key, value)
            db.commit()
            db.refresh(settings)
        return settings

    @staticmethod
    def get_all_guild_settings(db: Session, key: str) -> Dict[str, Any]:
        """
        Returns a dict of guild_id -> value for a specific setting key across all guilds.
        """
        results = db.query(GuildSettingsModel).all()
        return {r.guild_id: getattr(r, key) for r in results if hasattr(r, key)}

    @staticmethod
    def get_all_settings(db: Session, guild_id: str) -> Dict[str, Any]:
        """
        Returns all settings for a guild as a dictionary.
        """
        settings = SettingsService.get_guild_settings(db, guild_id)
        # Convert SQLAlchemy model to dict
        return {c.name: getattr(settings, c.name) for c in settings.__table__.columns}
