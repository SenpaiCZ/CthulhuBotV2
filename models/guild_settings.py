from sqlalchemy import Column, Integer, String, JSON
from .base import Base

class GuildSettings(Base):
    __tablename__ = 'guild_settings'

    guild_id = Column(String, primary_key=True)
    luck_threshold = Column(Integer)
    max_starting_skill = Column(Integer)
    game_mode = Column(String)
    karma_settings = Column(JSON)
    loot_settings = Column(JSON)
    pogo_settings = Column(JSON)
    autorooms = Column(JSON)
    rss_data = Column(JSON)
    gamerole_settings = Column(JSON)
    enroll_settings = Column(JSON)
    skill_sound_settings = Column(JSON)
    fonts_config = Column(JSON)
    soundboard_settings = Column(JSON)
    server_volumes = Column(JSON)
    smart_react = Column(JSON)
    reaction_roles = Column(JSON)
    luck_stats = Column(JSON)
    skill_settings = Column(JSON)

    # New fields for overhaul
    admin_password = Column(String)
    dashboard_theme = Column(String)
    dashboard_fonts = Column(JSON)
    origin_fonts = Column(JSON)
    prefix = Column(String)
