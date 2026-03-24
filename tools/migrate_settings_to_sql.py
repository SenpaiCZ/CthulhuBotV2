import json
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to sys.path so we can import models and services
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.base import Base
from models.guild_settings import GuildSettings
from schemas.settings import GuildSettingsUpdate
from services.settings_service import SettingsService

DB_URL = "sqlite:///data/database.sqlite"
DATA_FOLDER = "data"

# Mapping of file names to GuildSettings fields
FILE_FIELD_MAP = {
    'karma_settings.json': 'karma_settings',
    'loot_settings.json': 'loot_settings',
    'pogo_settings.json': 'pogo_settings',
    'autorooms.json': 'autorooms',
    'rss_data.json': 'rss_data',
    'gamerole_settings.json': 'gamerole_settings',
    'enroll_settings.json': 'enroll_settings',
    'skill_sound_settings.json': 'skill_sound_settings',
    'fonts_config.json': 'fonts_config',
    'soundboard_settings.json': 'soundboard_settings',
    'server_volumes.json': 'server_volumes',
    'smart_react.json': 'smart_react',
    'reaction_roles.json': 'reaction_roles',
    'luck_stats.json': 'luck_threshold', 
    'skill_settings.json': 'max_starting_skill',
    'gamemode.json': 'game_mode',
    'server_stats.json': 'prefix',
    'bot_status.json': 'bot_status'
}

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

def migrate_all_settings(db, data_folder):
    print("Starting settings migration...")
    
    # Aggregate all settings by guild_id
    guild_data = {}

    for filename, field in FILE_FIELD_MAP.items():
        file_path = os.path.join(data_folder, filename)
        data = load_json_safe(file_path)
        if data is None:
            continue
        
        print(f"Processing {filename}...")
        
        # Handle cases where the whole file is one setting (like bot_status)
        if filename in ['bot_status.json', 'loot_settings.json']:
            if 'global' not in guild_data: guild_data['global'] = {}
            guild_data['global'][field] = data
            continue

        if isinstance(data, dict):
            for guild_id, value in data.items():
                if guild_id not in guild_data:
                    guild_data[guild_id] = {}
                
                # Special handling for flattened fields
                if field == 'luck_threshold':
                    try: guild_data[guild_id]['luck_threshold'] = int(value)
                    except: pass
                elif field == 'max_starting_skill':
                    if isinstance(value, dict):
                        guild_data[guild_id]['max_starting_skill'] = value.get('max_starting_skill', 75)
                    else:
                        try: guild_data[guild_id]['max_starting_skill'] = int(value)
                        except: pass
                elif field == 'game_mode':
                    guild_data[guild_id]['game_mode'] = str(value)
                elif field == 'prefix':
                    guild_data[guild_id]['prefix'] = str(value)
                else:
                    # Direct JSON mapping
                    guild_data[guild_id][field] = value

    for guild_id, settings in guild_data.items():
        print(f"Migrating settings for guild {guild_id}...")
        try:
            # We use set_setting instead of full object update to be safer
            for key, val in settings.items():
                SettingsService.set_setting(db, str(guild_id), key, val)
        except Exception as e:
            print(f"Failed to migrate guild {guild_id}: {e}")

def verify_settings_migration(db, data_folder):
    print("\nVerifying migration...")
    passed = True
    for filename, field in FILE_FIELD_MAP.items():
        json_data = load_json_safe(os.path.join(data_folder, filename))
        if json_data is None: continue

        if filename in ['bot_status.json', 'loot_settings.json']:
            actual_val = SettingsService.get_setting(db, "global", field)
            if actual_val != json_data:
                print(f"❌ Mismatch in {field} for global")
                passed = False
            continue

        for guild_id, expected_val in json_data.items():
            actual_val = SettingsService.get_setting(db, str(guild_id), field)
            
            match = False
            if field == 'luck_threshold':
                try: match = int(expected_val) == actual_val
                except: match = actual_val is None
            elif field == 'max_starting_skill':
                if isinstance(expected_val, dict):
                    match = expected_val.get('max_starting_skill', 75) == actual_val
                else:
                    try: match = int(expected_val) == actual_val
                    except: match = actual_val is None
            elif field == 'game_mode':
                match = str(expected_val) == actual_val
            elif field == 'prefix':
                match = str(expected_val) == actual_val
            else:
                match = expected_val == actual_val
            
            if not match:
                print(f"❌ Mismatch in {field} for guild {guild_id}")
                passed = False
    
    if passed:
        print("✅ All settings verified successfully.")
    return passed

if __name__ == "__main__":
    engine = create_engine(DB_URL)
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        migrate_all_settings(db, DATA_FOLDER)
        verify_settings_migration(db, DATA_FOLDER)
    finally:
        db.close()
