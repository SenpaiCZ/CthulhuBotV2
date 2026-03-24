from sqlalchemy.orm import Session
from models.metadata import GlobalEmoji
from typing import Dict, Tuple, List, Optional

class MetadataService:
    """
    Service for managing global emoji metadata with in-memory caching.
    """
    _cache: Dict[Tuple[str, str], str] = {}
    _initialized: bool = False

    @staticmethod
    def sync_cache(db: Session):
        """
        Synchronize the in-memory cache with the database.
        Cache structure: { (category, key): value }
        """
        emojis = db.query(GlobalEmoji).all()
        MetadataService._cache = { (e.category, e.key): e.value for e in emojis }
        MetadataService._initialized = True

    @staticmethod
    def _ensure_cache(db: Session):
        """
        Ensure the cache is initialized from the database.
        """
        if not MetadataService._initialized:
            MetadataService.sync_cache(db)

    @staticmethod
    def get_emoji(db: Session, key: str, category: str) -> str:
        """
        Retrieve an emoji value by key and category.
        Checks cache first, then DB if not found (and updates cache).
        Returns an empty string if not found anywhere.
        """
        MetadataService._ensure_cache(db)
        
        # Try cache
        val = MetadataService._cache.get((category, key))
        if val is not None:
            return val
            
        # Try DB (if not in cache, fallback and update cache)
        db_emoji = db.query(GlobalEmoji).filter(
            GlobalEmoji.category == category,
            GlobalEmoji.key == key
        ).first()
        
        if db_emoji:
            MetadataService._cache[(category, key)] = db_emoji.value
            return db_emoji.value
            
        return ""

    @staticmethod
    def get_all_emojis(db: Session) -> List[GlobalEmoji]:
        """
        Retrieve all GlobalEmoji entries from the database.
        """
        return db.query(GlobalEmoji).all()

    @staticmethod
    def update_emoji(db: Session, key: str, category: str, value: str) -> GlobalEmoji:
        """
        Create or update an emoji entry in the database and synchronize the cache.
        """
        db_emoji = db.query(GlobalEmoji).filter(
            GlobalEmoji.category == category,
            GlobalEmoji.key == key
        ).first()
        
        if db_emoji:
            db_emoji.value = value
        else:
            db_emoji = GlobalEmoji(category=category, key=key, value=value)
            db.add(db_emoji)
            
        db.commit()
        db.refresh(db_emoji)
        
        # Update cache after successful DB update
        MetadataService._ensure_cache(db)
        MetadataService._cache[(category, key)] = value
        
        return db_emoji
