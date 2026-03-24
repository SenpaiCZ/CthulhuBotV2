from sqlalchemy import Column, Integer, String
from .base import Base

class AutoRoom(Base):
    __tablename__ = 'autorooms'

    id = Column(Integer, primary_key=True)
    guild_id = Column(String, index=True)
    creator_id = Column(String)
    channel_id = Column(String)
    name_format = Column(String)

class DeleterJob(Base):
    __tablename__ = 'deleter_jobs'

    id = Column(Integer, primary_key=True)
    guild_id = Column(String, index=True)
    channel_id = Column(String)
    user_id = Column(String)
    status = Column(String)

class RSSFeed(Base):
    __tablename__ = 'rss_feeds'

    id = Column(Integer, primary_key=True)
    guild_id = Column(String, index=True)
    channel_id = Column(String)
    url = Column(String)
    last_item_id = Column(String)
