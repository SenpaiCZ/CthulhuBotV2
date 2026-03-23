from sqlalchemy.orm import Session
from models.campaign import JournalEntry, KarmaStat
from models.inventory import InventoryItem, Handout
from schemas.campaign import JournalEntryCreate, InventoryItemCreate, HandoutCreate
from typing import List, Optional
from datetime import datetime

class CampaignService:
    """
    Service for managing campaign-related data including journals, inventory, karma, and handouts.
    """
    @staticmethod
    def add_journal_entry(db: Session, data: JournalEntryCreate) -> JournalEntry:
        """
        Create a new journal entry (Master or Personal).
        """
        db_entry = JournalEntry(
            guild_id=data.guild_id,
            journal_type=data.journal_type,
            author_id=data.author_id,
            owner_id=data.owner_id,
            title=data.title,
            content=data.content,
            images=data.images,
            timestamp=datetime.utcnow()
        )
        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)
        return db_entry

    @staticmethod
    def get_journal_entries(db: Session, guild_id: str, journal_type: str, owner_id: Optional[str] = None) -> List[JournalEntry]:
        """
        Retrieve journal entries for a specific guild and type, optionally filtered by owner.
        """
        query = db.query(JournalEntry).filter(
            JournalEntry.guild_id == guild_id,
            JournalEntry.journal_type == journal_type
        )
        if owner_id:
            query = query.filter(JournalEntry.owner_id == owner_id)
        
        return query.order_by(JournalEntry.timestamp.desc()).all()

    @staticmethod
    def add_inventory_item(db: Session, data: InventoryItemCreate) -> InventoryItem:
        """
        Add a new item to an investigator's inventory.
        """
        db_item = InventoryItem(
            investigator_id=data.investigator_id,
            name=data.name,
            description=data.description,
            quantity=data.quantity,
            is_macguffin=data.is_macguffin
        )
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return db_item

    @staticmethod
    def get_investigator_inventory(db: Session, investigator_id: int) -> List[InventoryItem]:
        """
        Retrieve all inventory items for a specific investigator.
        """
        return db.query(InventoryItem).filter(InventoryItem.investigator_id == investigator_id).all()

    @staticmethod
    def add_karma(db: Session, guild_id: str, user_id: str, amount: int) -> KarmaStat:
        """
        Update or create karma statistics for a user in a guild.
        """
        db_karma = db.query(KarmaStat).filter(
            KarmaStat.guild_id == guild_id,
            KarmaStat.user_id == user_id
        ).first()

        if db_karma:
            db_karma.score += amount
        else:
            db_karma = KarmaStat(
                guild_id=guild_id,
                user_id=user_id,
                score=amount
            )
            db.add(db_karma)
        
        db.commit()
        db.refresh(db_karma)
        return db_karma

    @staticmethod
    def get_karma_leaderboard(db: Session, guild_id: str) -> List[KarmaStat]:
        """
        Retrieve the karma leaderboard for a guild, sorted by score.
        """
        return db.query(KarmaStat).filter(
            KarmaStat.guild_id == guild_id
        ).order_by(KarmaStat.score.desc()).all()

    @staticmethod
    def create_handout(db: Session, data: HandoutCreate) -> Handout:
        """
        Create a new campaign handout.
        """
        db_handout = Handout(
            guild_id=data.guild_id,
            title=data.title,
            content=data.content,
            image_url=data.image_url
        )
        db.add(db_handout)
        db.commit()
        db.refresh(db_handout)
        return db_handout

    @staticmethod
    def get_guild_handouts(db: Session, guild_id: str) -> List[Handout]:
        """
        Retrieve all handouts for a specific guild.
        """
        return db.query(Handout).filter(Handout.guild_id == guild_id).all()
