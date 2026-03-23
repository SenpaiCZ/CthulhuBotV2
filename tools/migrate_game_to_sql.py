import json
import os
import sys
from sqlalchemy.orm import Session
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.database import SessionLocal
from models.codex import CodexEntry
from models.game_state import CombatSession, CombatParticipant
from services.codex_service import CodexService

def migrate_codex():
    db = SessionLocal()
    infodata_dir = "infodata"
    
    # Mapping of filename to category and key
    CODEX_FILES = {
        'monsters.json': ('Monster', 'monsters', 'monster_entry'),
        'spells.json': ('Spell', 'spells', 'spell_entry'),
        'deities.json': ('Deity', 'deities', 'deity_entry'),
        'weapons.json': ('Weapon', None, None), # Flat dict or list
        'occupations_info.json': ('Occupation', None, None),
        'skills_info.json': ('Skill', None, None),
        'pulp_talents.json': ('Pulp Talent', None, None)
    }

    try:
        for filename, (category, root_key, entry_key) in CODEX_FILES.items():
            path = os.path.join(infodata_dir, filename)
            if not os.path.exists(path):
                print(f"Skipping {filename}: Not found.")
                continue
            
            print(f"Migrating {filename} as {category}...")
            with open(path, 'r', encoding='utf-16') as f:
                data = json.load(f)
            
            entries = []
            if root_key:
                entries = data.get(root_key, [])
            elif isinstance(data, list):
                entries = data
            elif isinstance(data, dict):
                # For weapons or skills where it might be name: data
                for name, content in data.items():
                    entries.append({'name': name, **content})

            for entry in entries:
                if entry_key and entry_key in entry:
                    item = entry[entry_key]
                else:
                    item = entry
                
                name = item.get('name') or item.get('NAME')
                if not name: continue

                db_entry = CodexEntry(
                    category=category,
                    name=name,
                    content=item,
                    image_filename=item.get('image')
                )
                db.add(db_entry)
        
        db.commit()
        print("Codex migration successful.")
    except Exception as e:
        print(f"Error during codex migration: {e}")
        db.rollback()
    finally:
        db.close()

def migrate_active_games():
    db = SessionLocal()
    session_path = os.path.join("data", "session_data.json")
    try:
        if os.path.exists(session_path):
            print(f"Migrating active games from {session_path}...")
            with open(session_path, 'r', encoding='utf-16') as f:
                session_data = json.load(f)
            
            for guild_id, data in session_data.items():
                if not data.get("active"): continue
                
                combat = CombatSession(
                    guild_id=guild_id,
                    channel_id=data.get("channel_id", "Unknown"),
                    current_turn=data.get("current_turn", 0),
                    is_active=True
                )
                db.add(combat)
                db.flush() # Get combat.id

                for p in data.get("participants", []):
                    participant = CombatParticipant(
                        session_id=combat.id,
                        name=p.get("name"),
                        initiative=p.get("initiative", 0),
                        current_hp=p.get("hp"),
                        investigator_id=p.get("investigator_id")
                    )
                    db.add(participant)
            
            db.commit()
            print("Active game migration successful.")
    except Exception as e:
        print(f"Error during game migration: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    from models.base import Base
    engine = SessionLocal().get_bind()
    Base.metadata.create_all(bind=engine)
    
    migrate_codex()
    migrate_active_games()
