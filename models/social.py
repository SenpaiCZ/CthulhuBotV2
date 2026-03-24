from sqlalchemy import Column, Integer, String, JSON, DateTime, Text
from .base import Base

class Poll(Base):
    __tablename__ = 'polls'

    message_id = Column(String, primary_key=True)
    guild_id = Column(String, index=True)
    question = Column(String)
    options = Column(JSON)
    votes = Column(JSON)

class Giveaway(Base):
    __tablename__ = 'giveaways'

    message_id = Column(String, primary_key=True)
    guild_id = Column(String, index=True)
    title = Column(String)
    prize = Column(String)
    end_time = Column(DateTime)
    participants = Column(JSON)

class Reminder(Base):
    __tablename__ = 'reminders'

    id = Column(Integer, primary_key=True)
    user_id = Column(String, index=True)
    guild_id = Column(String)
    channel_id = Column(String)
    message = Column(Text)
    due_at = Column(DateTime)

class PogoEvent(Base):
    __tablename__ = 'pogo_events'

    id = Column(Integer, primary_key=True)
    guild_id = Column(String, index=True)
    name = Column(String)
    timestamp = Column(DateTime)
    location = Column(String)

class GamerRole(Base):
    __tablename__ = 'gamer_roles'

    id = Column(Integer, primary_key=True)
    guild_id = Column(String, index=True)
    role_id = Column(String)
    category = Column(String)
