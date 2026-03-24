import json
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to sys.path so we can import models and services
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.base import Base
from models.investigator import Investigator
from schemas.investigator import InvestigatorCreate
from services.character_service import CharacterService

DB_URL = "sqlite:///data/database.sqlite"
DATA_FOLDER = "data"

def load_json_safe(path):
    if not os.path.exists(path):
        return None
    for enc in ['utf-8', 'utf-16', 'windows-1252']:
        try:
            with open(path, 'r', encoding=enc) as f:
                return json.load(f)
        except Exception:
            continue
    return None

def migrate_investigators(db, data_folder):
    print(f"Starting migration to {DB_URL}...")
    
    # 1. Migrate Active Investigators
    player_stats_path = os.path.join(data_folder, 'player_stats.json')
    player_stats = load_json_safe(player_stats_path)
    
    total_migrated = 0
    if player_stats:
        print(f"Migrating {player_stats_path}...")
        for guild_id, users in player_stats.items():
            for user_id, char_data in users.items():
                # Correctly identify name and standard fields
                name = char_data.get('NAME', 'Unknown')
                
                # Standard stats mapping
                standard_fields = ["NAME", "STR", "CON", "SIZ", "DEX", "APP", "INT", "POW", "EDU", "LUCK", "Occupation", "is_retired", "Backstory", "Occupation Info"]
                
                skills = {}
                extra_data = {}
                for k, v in char_data.items():
                    if k not in standard_fields and isinstance(v, (int, float)):
                        skills[k] = v
                    elif k not in standard_fields:
                        extra_data[k] = v

                # Handle Backstory mapping
                backstory = char_data.get("Backstory", {})
                if not isinstance(backstory, dict):
                    backstory = {"content": backstory}

                new_inv = InvestigatorCreate(
                    guild_id=str(guild_id),
                    discord_user_id=str(user_id),
                    name=name,
                    occupation=char_data.get("Occupation", "Unknown"),
                    str_stat=int(char_data.get("STR", 50)),
                    con=int(char_data.get("CON", 50)),
                    siz=int(char_data.get("SIZ", 50)),
                    dex=int(char_data.get("DEX", 50)),
                    app=int(char_data.get("APP", 50)),
                    int_stat=int(char_data.get("INT", 50)),
                    pow_stat=int(char_data.get("POW", 50)),
                    edu=int(char_data.get("EDU", 50)),
                    luck=int(char_data.get("LUCK", 50)),
                    skills=skills,
                    extra_data=extra_data,
                    backstory=backstory,
                    is_retired=False
                )
                
                # Check if exists
                existing = CharacterService.get_investigator_by_guild_and_user(db, str(guild_id), str(user_id))
                if existing:
                    CharacterService.update_investigator(db, existing.id, new_inv.dict())
                else:
                    CharacterService.create_investigator(db, new_inv)
                total_migrated += 1
    
    db.commit()
    print(f"\nMigration complete. Total investigators migrated: {total_migrated}")

def verify_migration(db):
    print("\nVerifying migration...")
    count = db.query(Investigator).count()
    print(f"Found {count} investigators in SQL database.")
    
    # Spot check
    inv = db.query(Investigator).first()
    if inv:
        print(f"Spot check: Investigator '{inv.name}' (Discord ID: {inv.discord_user_id})")
        print(f"Skills Count: {len(inv.skills)}")
    return True

if __name__ == "__main__":
    engine = create_engine(DB_URL)
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        migrate_investigators(db, DATA_FOLDER)
        verify_migration(db)
    finally:
        db.close()
