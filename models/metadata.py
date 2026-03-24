from sqlalchemy import Column, Integer, String
from .base import Base

class GlobalEmoji(Base):
    __tablename__ = 'global_emojis'

    id = Column(Integer, primary_key=True)
    category = Column(String) # e.g., 'Stat', 'Skill', 'Occupation', 'Language', 'Item', 'System'
    key = Column(String, index=True)
    value = Column(String) # The emoji character
