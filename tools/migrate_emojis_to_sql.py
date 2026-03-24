import os
import sys
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

# Add project root to sys.path so we can import models and services
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.base import Base
from models.metadata import GlobalEmoji
from services.metadata_service import MetadataService
from emojis import stat_emojis
from occupation_emoji import occupation_emojis

DB_URL = "sqlite:///data/database.sqlite"

def categorize_stat_emoji(key):
    """
    Categorize stat_emojis into 'Stat', 'Skill', 'Language', 'Item', 'System'.
    """
    stats = {
        "STR", "DEX", "CON", "INT", "POW", "APP", "EDU", "SIZ", 
        "HP", "MP", "LUCK", "SAN", "Move", "Build", "Damage Bonus", "DB"
    }
    
    system = {"Age", "Residence", "Occupation"}
    
    items = {
        "Axe", "Sword", "Spear", "Bow", "Flamethrower", "Heavy Weapons", 
        "Machine Gun", "Submachine Gun", "Chainsaw"
    }
    
    # Languages list from stat_emojis
    languages = {
        "Arabic", "Bengali", "Chinese", "Czech", "Danish", "Dutch", "English", 
        "Finnish", "French", "German", "Greek", "Hindi", "Hungarian", "Italian", 
        "Japanese", "Korean", "Norwegian", "Polish", "Portuguese", "Romanian", 
        "Russian", "Spanish", "Swedish", "Turkish", "Vietnamese", "Hebrew", 
        "Thai", "Swahili", "Urdu", "Malay", "Filipino", "Indonesian", "Maltese", 
        "Nepali", "Slovak", "Slovenian", "Ukrainian", "Bulgarian", "Estonian", 
        "Icelandic", "Latvian", "Lithuanian", "Luxembourgish", "Samoan", "Tongan", 
        "Fijian", "Tahitian", "Hawaiian", "Maori", "Tibetan", "Kurdish", "Pashto", 
        "Dari", "Balinese", "Turkmen", "Bosnian", "Croatian", "Serbian", 
        "Macedonian", "Albanian", "Mongolian", "Armenian", "Georgian", 
        "Azerbaijani", "Kazakh", "Kyrgyz", "Tajik", "Uzbek", "Tatar", "Bashkir", 
        "Chechen", "Belarusian", "Moldovan", "Sami", "Faroese", "Irish", "Welsh", 
        "Scots Gaelic", "Basque", "Catalan", "Galician", "Yiddish", "Malayalam", 
        "Tamil", "Burmese", "Khmer", "Lao", "Bisaya", "Cebuano", "Ilocano", 
        "Hiligaynon", "Waray", "Chichewa", "Kinyarwanda", "Swazi", "Tigrinya", 
        "Haitian Creole", "Frisian", "Esperanto", "Latin", "Scots", "Pirate",
        "Language other", "Language own", "Language (Other)", "Language (Own)",
        "Language"
    }

    if key in stats:
        return 'Stat'
    if key in system:
        return 'System'
    if key in items:
        return 'Item'
    if key in languages or "Language" in key:
        return 'Language'
    
    # Default for the rest in stat_emojis is 'Skill'
    return 'Skill'

def migrate_emojis(db):
    print("Starting emoji migration...")
    
    total_stat_emojis = len(stat_emojis)
    total_occ_emojis = len(occupation_emojis)
    print(f"Source items: {total_stat_emojis} stat emojis, {total_occ_emojis} occupation emojis.")
    
    # 1. Migrate Occupation Emojis
    print("Migrating occupation emojis...")
    for key, value in occupation_emojis.items():
        MetadataService.update_emoji(db, key, 'Occupation', value)
        
    # 2. Migrate Stat Emojis
    print("Migrating and categorizing stat emojis...")
    for key, value in stat_emojis.items():
        category = categorize_stat_emoji(key)
        MetadataService.update_emoji(db, key, category, value)
    
    # 3. Migrate Health Bar (System)
    print("Migrating health bar emojis...")
    health_emojis = {
        'health_bar_green': '🟩',
        'health_bar_yellow': '🟨',
        'health_bar_red': '🟥',
        'health_bar_empty': '⬛'
    }
    for key, value in health_emojis.items():
        MetadataService.update_emoji(db, key, 'System', value)

    # 4. Migrate Item Keywords
    print("Migrating additional item keywords...")
    item_keywords = {
        "amulet": "🧿", "artifact": "🧿", "relic": "🧿", "idol": "🧿", "crystal": "🧿", "orb": "🧿",
        "watch": "⌚", "clock": "⌚", "time": "⌚",
        "cigarette": "🚬", "cigar": "🚬", "tobacco": "🚬", "pipe": "🚬", "smoke": "🚬",
        "glasses": "👓", "spectacles": "👓", "monocle": "👓",
        "mask": "🎭", "disguise": "🎭",
        "umbrella": "☂️",
        "gun": "🔫", "rifle": "🔫", "pistol": "🔫", "shotgun": "🔫", "revolver": "🔫", "carbine": "🔫", "smg": "🔫", "handgun": "🔫",
        "knife": "🗡️", "dagger": "🗡️", "blade": "🗡️", "machete": "🗡️", "hatchet": "🗡️", "razor": "🗡️", "kukri": "🗡️",
        "potion": "🧪", "vial": "🧪", "bottle": "🧪", "flask": "🧪", "elixir": "🧪", "medicine": "🧪", "pill": "🧪", "syringe": "🧪", "drug": "🧪",
        "book": "📖", "journal": "📖", "diary": "📖", "note": "📖", "paper": "📖", "map": "📖", "scroll": "📖", "letter": "📖", "document": "📖", "tome": "📖",
        "key": "🗝️", "lockpick": "🗝️", "pass": "🗝️", "card": "🗝️",
        "money": "💰", "cash": "💰", "wallet": "💰", "coin": "💰", "gold": "💰", "silver": "💰", "bill": "💰", "gem": "💰", "jewel": "💰", "diamond": "💰", "ruby": "💰", "emerald": "💰", "sapphire": "💰", "ring": "💰", "necklace": "💰",
        "food": "🥫", "ration": "🥫", "canned": "🥫", "meat": "🥫", "bread": "🥫", "water": "🥫", "drink": "🥫", "alcohol": "🥫", "wine": "🥫", "beer": "🥫",
        "clothes": "🧥", "coat": "🧥", "hat": "🧥", "gloves": "🧥", "boots": "🧥", "shoes": "🧥", "suit": "🧥", "dress": "🧥", "armor": "🧥", "helmet": "🧥", "vest": "🧥",
        "tool": "🛠️", "wrench": "🛠️", "hammer": "🛠️", "screwdriver": "🛠️", "pliers": "🛠️", "saw": "🛠️", "crowbar": "🛠️", "kit": "🛠️",
        "light": "🔦", "torch": "🔦", "lantern": "🔦", "lamp": "🔦", "candle": "🔦", "match": "🔦", "lighter": "🔦",
        "ammo": "🎒", "bullet": "🎒", "shell": "🎒", "clip": "🎒", "magazine": "🎒",
        "phone": "📷", "radio": "📷", "camera": "📷",
        "bag": "👜", "backpack": "👜", "suitcase": "👜", "briefcase": "👜", "purse": "👜",
        "ticket": "🎫", "permit": "🎫"
    }
    for key, value in item_keywords.items():
        MetadataService.update_emoji(db, key, 'Item', value)
        
    db.commit()
    print("Migration logic complete.")

def verify_migration(db):
    print("\nVerifying migration...")
    total_sql = db.query(GlobalEmoji).count()
    
    print(f"Total entries in SQL: {total_sql}")
    
    # Count unique keys in sources (adjusting for potential overlaps if any)
    # Actually, they are in different categories so they won't overlap in the DB (category, key) is unique.
    # In stat_emojis, "Occupation" is categorized as 'System'.
    # In occupation_emojis, "Accountant" etc are categorized as 'Occupation'.
    
    # Categories counts
    counts = db.query(GlobalEmoji.category, func.count(GlobalEmoji.id)).group_by(GlobalEmoji.category).all()
    for cat, count in counts:
        print(f"  - {cat}: {count}")
    
    expected_total = len(stat_emojis) + len(occupation_emojis)
    print(f"Expected total (sum of source dicts): {expected_total}")
    
    if total_sql >= expected_total:
        print("Verification SUCCESS: All source emojis migrated.")
    else:
        print(f"Verification WARNING: SQL count {total_sql} is less than source count {expected_total}.")

if __name__ == "__main__":
    engine = create_engine(DB_URL)
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        migrate_emojis(db)
        verify_migration(db)
    except Exception as e:
        print(f"Error during migration: {e}")
        db.rollback()
    finally:
        db.close()
