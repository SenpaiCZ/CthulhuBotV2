from sqlalchemy import Column, Integer, String, JSON
from .base import Base

class CodexEntry(Base):
    __tablename__ = 'codex_entries'

    id = Column(Integer, primary_key=True)
    category = Column(String) # 'Monster', 'Spell', etc.
    name = Column(String, index=True)
    content = Column(JSON)
    image_filename = Column(String, nullable=True)
