from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from .base import Base
from .investigator import Investigator
from .guild_settings import GuildSettings
from .campaign import JournalEntry, KarmaStat
from .inventory import InventoryItem, Handout

DB_URL = "sqlite:///data/database.sqlite"

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
