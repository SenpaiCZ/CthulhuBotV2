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

def migrate_campaign_data():
    db = SessionLocal()
    try:
        # 1. Migrate Journal Data
        journal_path = os.path.join("data", "journal_data.json")
        if os.path.exists(journal_path):
            print(f"Migrating journal data from {journal_path}...")
            with open(journal_path, 'r', encoding='utf-8') as f:
                journal_data = json.load(f)
            for guild_id, data in journal_data.items():
                # Master entries
                master_data = data.get("master", [])
                if isinstance(master_data, dict): # Handle possible { 'entries': [] } wrapper
                    master_entries = master_data.get("entries", [])
                else:
                    master_entries = master_data
                
                for entry in master_entries:
                    db_entry = JournalEntry(
                        guild_id=guild_id, journal_type="Master",
                        author_id=entry["author"], title=entry["title"],
                        content=entry["content"], images=entry.get("images", [])
                    )
                    db.add(db_entry)
                # Personal entries
                for user_id, user_data in data.get("personal", {}).items():
                    if isinstance(user_data, dict):
                        personal_entries = user_data.get("entries", [])
                    else:
                        personal_entries = user_data
                        
                    for entry in personal_entries:
                        db_entry = JournalEntry(
                            guild_id=guild_id, journal_type="Personal",
                            author_id=entry["author"], owner_id=user_id,
                            title=entry["title"], content=entry["content"],
                            images=entry.get("images", [])
                        )
                        db.add(db_entry)

        # 2. Migrate Karma Stats
        karma_path = os.path.join("data", "karma_stats.json")
        if os.path.exists(karma_path):
            print(f"Migrating karma stats from {karma_path}...")
            with open(karma_path, 'r', encoding='utf-8') as f:
                karma_data = json.load(f)
            for guild_id, users in karma_data.items():
                for user_id, score in users.items():
                    db_karma = KarmaStat(guild_id=guild_id, user_id=user_id, score=score)
                    db.add(db_karma)

        # 3. Migrate Gear to Inventory
        print("Migrating gear to inventory_items...")
        investigators = db.query(Investigator).all()
        for inv in investigators:
            gear = inv.extra_data.get("gear") if inv.extra_data else None
            if gear:
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
