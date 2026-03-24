import json
import os
import sys
from sqlalchemy.orm import Session
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.database import SessionLocal
from models.codex import CodexEntry
from models.game_state import CombatSession, CombatParticipant
from services.codex_service import CodexService

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

def migrate_codex():
    db = SessionLocal()
    infodata_dir = "infodata"
    
    CODEX_FILES = {
        'monsters.json': ('Monster', 'monsters', 'monster_entry'),
        'spells.json': ('Spell', 'spells', 'spell_entry'),
        'deities.json': ('Deity', 'deities', 'deity_entry'),
        'weapons.json': ('Weapon', None, None),
        'occupations_info.json': ('Occupation', None, None),
        'skills_info.json': ('Skill', None, None),
        'pulp_talents.json': ('Pulp Talent', None, None),
        'archetype_info.json': ('Archetype', None, None),
        'insane_talents.json': ('Insane Talent', None, None),
        'inventions_info.json': ('Invention', None, None),
        'macguffin_info.json': ('MacGuffin', None, None),
        'manias.json': ('Mania', None, None),
        'phobias.json': ('Phobia', None, None),
        'poisions_info.json': ('Poison', None, None),
        'years_info.json': ('Year', None, None),
        'names.json': ('Name', None, None)
    }

    try:
        for filename, (category, root_key, entry_key) in CODEX_FILES.items():
            path = os.path.join(infodata_dir, filename)
            data = load_json_safe(path)
            if data is None:
                print(f"Skipping {filename}: Not found or invalid.")
                continue
            
            print(f"Migrating {filename} as {category}...")
            
            entries = []
            if root_key:
                # Handle cases where root_key is a list of entries
                raw_entries = data.get(root_key, [])
                if isinstance(raw_entries, list):
                    entries = raw_entries
                elif isinstance(raw_entries, dict):
                    # Handle cases where it's name: data
                    for name, content in raw_entries.items():
                        if isinstance(content, dict):
                            entries.append({'name': name, **content})
                        else:
                            entries.append({'name': name, 'value': content})
            elif isinstance(data, list):
                entries = data
            elif isinstance(data, dict):
                for name, content in data.items():
                    if isinstance(content, dict):
                        entries.append({'name': name, **content})
                    else:
                        # Case like names.json where it might be category: [names]
                        entries.append({'name': name, 'content': content})

            for entry in entries:
                if not isinstance(entry, dict):
                    # Skip primitive entries if they don't fit our model
                    continue

                if entry_key and entry_key in entry:
                    item = entry[entry_key]
                else:
                    item = entry
                
                if not isinstance(item, dict):
                    continue

                name = item.get('name') or item.get('NAME') or item.get('title')
                if not name: 
                    # Use name from iteration if available
                    name = entry.get('name')
                
                if not name: continue

                db_entry = CodexEntry(
                    category=category,
                    name=str(name),
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
        session_data = load_json_safe(session_path)
        if session_data:
            print(f"Migrating active games from {session_path}...")
            for guild_id, data in session_data.items():
                if not isinstance(data, dict) or not data.get("active"): continue
                
                combat = CombatSession(
                    guild_id=str(guild_id),
                    channel_id=str(data.get("channel_id", "Unknown")),
                    current_turn=data.get("current_turn", 0),
                    is_active=True
                )
                db.add(combat)
                db.flush()

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
