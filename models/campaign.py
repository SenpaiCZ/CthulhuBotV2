from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, ForeignKey
from datetime import datetime
from .base import Base

class JournalEntry(Base):
    __tablename__ = 'journal_entries'

    id = Column(Integer, primary_key=True)
    guild_id = Column(String, index=True)
    journal_type = Column(String)  # 'master' or 'personal'
    author_id = Column(String)
    owner_id = Column(String, nullable=True)
    title = Column(String)
    content = Column(Text)
    images = Column(JSON, default=list)
    timestamp = Column(DateTime, default=datetime.utcnow)

class KarmaStat(Base):
    __tablename__ = 'karma_stats'

    id = Column(Integer, primary_key=True)
    guild_id = Column(String, index=True)
    user_id = Column(String, index=True)
    score = Column(Integer, default=0)
