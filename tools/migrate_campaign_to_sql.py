import json
import os
import sys
from sqlalchemy.orm import Session
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.database import SessionLocal
from models.investigator import Investigator
from models.campaign import JournalEntry, KarmaStat
from models.inventory import InventoryItem
from services.campaign_service import CampaignService
from schemas.campaign import JournalEntryCreate, InventoryItemCreate

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

def migrate_campaign_data():
    db = SessionLocal()
    try:
        # 1. Migrate Journal Data
        journal_path = os.path.join("data", "journal_data.json")
        journal_data = load_json_safe(journal_path)
        if journal_data:
            print(f"Migrating journal data from {journal_path}...")
            for guild_id, data in journal_data.items():
                # Master entries
                master_data = data.get("master", {})
                master_entries = master_data.get("entries", []) if isinstance(master_data, dict) else master_data
                
                for entry in master_entries:
                    db_entry = JournalEntry(
                        guild_id=guild_id, journal_type="Master",
                        author_id=entry.get("author_id") or entry.get("author"), 
                        title=entry["title"],
                        content=entry["content"], images=entry.get("images", [])
                    )
                    db.add(db_entry)
                # Personal entries
                for user_id, user_data in data.get("personal", {}).items():
                    personal_entries = user_data.get("entries", []) if isinstance(user_data, dict) else user_data
                        
                    for entry in personal_entries:
                        db_entry = JournalEntry(
                            guild_id=guild_id, journal_type="Personal",
                            author_id=entry.get("author_id") or entry.get("author"), 
                            owner_id=user_id,
                            title=entry["title"], content=entry["content"],
                            images=entry.get("images", [])
                        )
                        db.add(db_entry)

        # 2. Migrate Karma Stats
        karma_path = os.path.join("data", "karma_stats.json")
        karma_data = load_json_safe(karma_path)
        if karma_data:
            print(f"Migrating karma stats from {karma_path}...")
            for guild_id, users in karma_data.items():
                for user_id, score in users.items():
                    db_karma = KarmaStat(guild_id=guild_id, user_id=user_id, score=score)
                    db.add(db_karma)

        # 3. Migrate Gear to Inventory
        print("Migrating gear to inventory_items...")
        investigators = db.query(Investigator).all()
        for inv in investigators:
            # Check extra_data or backstory for gear
            gear = None
            if inv.backstory and isinstance(inv.backstory, dict):
                gear = inv.backstory.get("Gear and Possessions")
            
            if gear and isinstance(gear, list):
                for item_name in gear:
                    if not item_name: continue
                    db_item = InventoryItem(investigator_id=inv.id, name=item_name, quantity=1)
                    db.add(db_item)
            elif gear and isinstance(gear, str):
                items = [i.strip() for i in gear.split(",")]
                for item_name in items:
                    if not item_name: continue
                    db_item = InventoryItem(investigator_id=inv.id, name=item_name, quantity=1)
                    db.add(db_item)
        
        db.commit()
        print("Campaign data migration successful.")
    except Exception as e:
        print(f"Error during migration: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate_campaign_data()
