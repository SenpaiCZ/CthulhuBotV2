from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey
from .base import Base

class InventoryItem(Base):
    __tablename__ = 'inventory_items'

    id = Column(Integer, primary_key=True)
    investigator_id = Column(Integer, ForeignKey('investigators.id'))
    name = Column(String)
    description = Column(Text)
    quantity = Column(Integer, default=1)
    is_macguffin = Column(Boolean, default=False)

class Handout(Base):
    __tablename__ = 'handouts'

    id = Column(Integer, primary_key=True)
    guild_id = Column(String, index=True)
    title = Column(String)
    content = Column(Text)
    image_url = Column(String, nullable=True)
