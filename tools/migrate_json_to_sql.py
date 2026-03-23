import json
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the project root to sys.path so we can import models and services
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.base import Base
from models.investigator import Investigator
from services.character_service import CharacterService
from schemas.investigator import InvestigatorCreate

DB_URL = "sqlite:///data/database.sqlite"
ACTIVE_JSON = os.path.join("data", "player_stats.json")
RETIRED_JSON = os.path.join("data", "retired_characters_data.json")

def migrate():
    print(f"Starting migration to {DB_URL}...")
    
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Initialize DB
    engine = create_engine(DB_URL)
    # Recreate tables to ensure clean state for migration
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    total_count = 0
    
    # Migrate Active Characters
    total_count += migrate_file(db, ACTIVE_JSON, is_retired_default=False)
    
    # Migrate Retired Characters
    total_count += migrate_file(db, RETIRED_JSON, is_retired_default=True)
            
    db.close()
    print(f"\nMigration complete. Total investigators migrated: {total_count}")
    
    # Verification
    verify_migration(total_count)

def migrate_file(db, file_path, is_retired_default=False):
    if not os.path.exists(file_path):
        print(f"Skipping {file_path}: File not found.")
        return 0
        
    print(f"Migrating {file_path}...")
    try:
        # User explicitly requested utf-16
        with open(file_path, 'r', encoding='utf-16') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        # Try utf-8 as fallback if utf-16 fails (just in case)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"Successfully loaded {file_path} with utf-8 instead.")
        except Exception:
            return 0
        
    count = 0
    for first_key, first_val in data.items():
        # Check if it's nested (server_id -> user_id -> data)
        # Some formats might be {server_id: {user_id: {data}}}
        if isinstance(first_val, dict) and any(isinstance(v, dict) and ("name" in v or "characteristics" in v) for v in first_val.values()):
            # Nested structure
            guild_id = str(first_key)
            for user_id, char_data in first_val.items():
                if isinstance(char_data, dict):
                    migrate_character(db, user_id, char_data, is_retired_default, guild_id=guild_id)
                    count += 1
        else:
            # Single level structure {user_id: {data}}
            if isinstance(first_val, dict):
                # Try to get guild_id from data if it's not nested
                guild_id = str(first_val.get("guild_id", "global"))
                migrate_character(db, first_key, first_val, is_retired_default, guild_id=guild_id)
                count += 1
    
    print(f"Migrated {count} investigators from {file_path}.")
    return count

def migrate_character(db, user_id, data, is_retired_default, guild_id="global"):
    characteristics = data.get("characteristics", {})
    
    # Helper to get stat from characteristics dict or top level
    def get_stat(name, default=50):
        val = characteristics.get(name, data.get(name, default))
        # Ensure it's an int and within reasonable bounds for Pydantic
        try:
            val = int(val)
            if val < 15: val = 15
            if val > 90: val = 90
            return val
        except:
            return default

    # Extract extra data (non-standard fields)
    standard_fields = ["name", "occupation", "characteristics", "skills", "is_retired", "guild_id", "backstory", "biography"]
    extra_data = {k: v for k, v in data.items() if k not in standard_fields}
    # Also add characteristics that might be extra
    for k, v in characteristics.items():
        if k not in ["str", "con", "siz", "dex", "app", "int", "pow", "edu", "luck"]:
            extra_data[k] = v

    try:
        investigator_data = InvestigatorCreate(
            guild_id=guild_id,
            discord_user_id=str(user_id),
            name=data.get("name", "Unknown"),
            occupation=data.get("occupation"),
            str=get_stat("str"),
            con=get_stat("con"),
            siz=get_stat("siz"),
            dex=get_stat("dex"),
            app=get_stat("app"),
            int=get_stat("int"),
            pow=get_stat("pow"),
            edu=get_stat("edu"),
            luck=get_stat("luck"),
            skills=data.get("skills", {}),
            extra_data=extra_data,
            is_retired=data.get("is_retired", is_retired_default),
            backstory=data.get("backstory", {}),
            biography=data.get("biography", {})
        )
        
        CharacterService.create_investigator(db, investigator_data)
    except Exception as e:
        print(f"Failed to migrate investigator {user_id}: {e}")

def verify_migration(expected_count):
    print("\nVerifying migration...")
    engine = create_engine(DB_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    count = db.query(Investigator).count()
    print(f"Found {count} investigators in SQL database.")
    
    if count == expected_count:
        print("✅ Verification passed: Count matches.")
    else:
        print(f"❌ Verification failed: Count mismatch (expected {expected_count}, got {count}).")
        
    # Spot check first entry
    first = db.query(Investigator).first()
    if first:
        print(f"Spot check: Investigator '{first.name}' (Discord ID: {first.discord_user_id})")
        print(f"Characteristics: STR={first.str}, INT={first.int}, POW={first.pow}")
        print(f"Skills: {first.skills}")
        print(f"Retired: {first.is_retired}")
        
    db.close()

if __name__ == "__main__":
    migrate()
