import json
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the project root to sys.path so we can import models and services
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.base import Base
from models.codex import CodexEntry
from models.database import DB_URL

INFODATA_FOLDER = "infodata"

def migrate_codex():
    print(f"Starting codex migration to {DB_URL}...")
    
    engine = create_engine(DB_URL)
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    # 1. Migrate Monsters
    migrate_category(db, "monsters.json", "Monster", "monster_entry")
    
    # 2. Migrate Deities
    migrate_category(db, "deities.json", "Deity", "deity_entry")
    
    # 3. Migrate Spells
    migrate_category(db, "spells.json", "Spell", "spell_entry")
    
    # 4. Migrate Weapons
    migrate_dict_category(db, "weapons.json", "Weapon")
    
    # 5. Migrate Archetypes
    migrate_dict_category(db, "archetype_info.json", "Archetype")
    
    # 6. Migrate Occupations
    migrate_dict_category(db, "occupations_info.json", "Occupation")
    
    # 7. Migrate Names
    migrate_names(db)
    
    db.close()
    print("Codex migration complete.")

def migrate_category(db, filename, category, wrapper_key):
    path = os.path.join(INFODATA_FOLDER, filename)
    if not os.path.exists(path):
        print(f"Skipping {filename}: Not found.")
        return

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        items = data.get(filename.split('.')[0], [])
        for item in items:
            entry_data = item.get(wrapper_key)
            if entry_data:
                name = entry_data.get('name')
                if name:
                    # Check if exists
                    existing = db.query(CodexEntry).filter(CodexEntry.category == category, CodexEntry.name == name).first()
                    if not existing:
                        db.add(CodexEntry(category=category, name=name, content=entry_data))
        db.commit()
        print(f"Migrated {category} entries from {filename}.")
    except Exception as e:
        print(f"Error migrating {filename}: {e}")

def migrate_dict_category(db, filename, category):
    path = os.path.join(INFODATA_FOLDER, filename)
    if not os.path.exists(path):
        print(f"Skipping {filename}: Not found.")
        return

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for name, entry_data in data.items():
            # Check if exists
            existing = db.query(CodexEntry).filter(CodexEntry.category == category, CodexEntry.name == name).first()
            if not existing:
                db.add(CodexEntry(category=category, name=name, content=entry_data))
        db.commit()
        print(f"Migrated {category} entries from {filename}.")
    except Exception as e:
        print(f"Error migrating {filename}: {e}")

def migrate_names(db):
    path = os.path.join(INFODATA_FOLDER, "names.json")
    if not os.path.exists(path):
        print("Skipping names.json: Not found.")
        return

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for region, region_data in data.items():
            # For names, we can store the whole region data as one entry
            # or store each name. Storing each name might be too much.
            # But the task says "Use CodexService.get_random_entry (for names)".
            # If we want a random name, maybe we should have entries like "Name:English:Male:John"?
            # Or just "Name" category and pick one.
            
            # Let's try storing each name as a separate entry for maximum compatibility with get_random_entry
            count = 0
            for gender in ["male", "female"]:
                names = region_data.get(gender, [])
                for first_name in names:
                    # We'll store it as "Name" category, and put region/gender in content
                    name_val = first_name
                    content = {"region": region, "gender": gender, "type": "first"}
                    # To avoid duplicates and keep it simple, we might just use name=first_name
                    # But John could be English and German.
                    # entry_name = f"{region}:{gender}:{first_name}"
                    
                    # Wait, if I use get_random_entry(db, category="Name"), I want it to be a name.
                    db.add(CodexEntry(category="Name", name=name_val, content=content))
                    count += 1
            
            last_names = region_data.get("last", [])
            for last_name in last_names:
                db.add(CodexEntry(category="Name", name=last_name, content={"region": region, "type": "last"}))
                count += 1
                
        db.commit()
        print(f"Migrated {count} name entries.")
    except Exception as e:
        print(f"Error migrating names: {e}")

if __name__ == "__main__":
    migrate_codex()
