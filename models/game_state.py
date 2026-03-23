from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime, ForeignKey
from datetime import datetime
from .base import Base

class CombatSession(Base):
    __tablename__ = 'combat_sessions'

    id = Column(Integer, primary_key=True)
    guild_id = Column(String, index=True)
    channel_id = Column(String)
    current_turn = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

class CombatParticipant(Base):
    __tablename__ = 'combat_participants'

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('combat_sessions.id'))
    investigator_id = Column(Integer, ForeignKey('investigators.id'), nullable=True)
    name = Column(String)
    initiative = Column(Integer)
    current_hp = Column(Integer)

class SessionLog(Base):
    __tablename__ = 'session_logs'

    id = Column(Integer, primary_key=True)
    guild_id = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    event_type = Column(String)
    description = Column(String) # Text type in SQLAlchemy is often String or Text
    metadata_json = Column(JSON)
