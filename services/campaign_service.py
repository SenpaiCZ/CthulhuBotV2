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

    @staticmethod
    async def generate_random_loot():
        """
        Generate random loot based on settings.
        """
        from loadnsave import load_loot_settings
        import random
        
        settings = await load_loot_settings()
        items_pool = settings.get("items", ["Nothing found."])
        money_chance = settings.get("money_chance", 25)
        money_min = settings.get("money_min", 0.01)
        money_max = settings.get("money_max", 5.00)
        currency_symbol = settings.get("currency_symbol", "$")
        min_items = settings.get("num_items_min", 1)
        max_items = settings.get("num_items_max", 5)

        money_str = None
        if random.randint(1, 100) <= money_chance:
            money_str = f"{currency_symbol}{random.uniform(money_min, money_max):.2f}"

        num_items = random.randint(min_items, max(min_items, min(max_items, len(items_pool))))
        chosen_items = random.sample(items_pool, num_items) if items_pool else []

        flavor_texts = [
            "You pry open the dusty crate...", "You search the body...",
            "Hidden under the floorboards...", "Inside the forgotten cabinet...",
            "Scattered on the table...", "In the pockets of the coat..."
        ]
        desc = random.choice(flavor_texts)
        if not chosen_items and not money_str:
            desc = "You search thoroughly, but find nothing of value."
            
        return chosen_items, money_str, desc

    @staticmethod
    def bulk_add_inventory_items(db: Session, investigator_id: int, items: List[InventoryItemCreate]):
        """
        Add multiple items to an investigator's inventory.
        """
        for item_data in items:
            db_item = InventoryItem(
                investigator_id=investigator_id,
                name=item_data.name,
                description=item_data.description,
                quantity=item_data.quantity,
                is_macguffin=item_data.is_macguffin
            )
            db.add(db_item)
        db.commit()
