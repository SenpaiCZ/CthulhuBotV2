from sqlalchemy import Column, Integer, String, Boolean, JSON
from .base import Base

class Investigator(Base):
    __tablename__ = 'investigators'

    id = Column(Integer, primary_key=True)
    discord_user_id = Column(String, index=True)
    name = Column(String)
    occupation = Column(String)
    
    # Character Stats
    str = Column(Integer)
    con = Column(Integer)
    siz = Column(Integer)
    dex = Column(Integer)
    app = Column(Integer)
    int = Column(Integer)
    pow = Column(Integer)
    edu = Column(Integer)
    luck = Column(Integer)
    
    skills = Column(JSON)
    is_retired = Column(Boolean, default=False)
