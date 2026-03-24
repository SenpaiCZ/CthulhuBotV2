from sqlalchemy.orm import Session
from models.social import Poll, Giveaway, PogoEvent, GamerRole
from models.admin import RSSFeed
from schemas.social import PollCreate, GiveawayCreate, PogoEventCreate, GamerRoleCreate
from schemas.admin import RSSFeedCreate
from typing import List, Optional

class EngagementService:
    @staticmethod
    def create_poll(db: Session, data: PollCreate) -> Poll:
        """
        Create a new poll in the database.
        """
        db_poll = Poll(
            message_id=data.message_id,
            guild_id=data.guild_id,
            question=data.question,
            options=data.options,
            votes=data.votes
        )
        db.add(db_poll)
        db.commit()
        db.refresh(db_poll)
        return db_poll

    @staticmethod
    def get_poll(db: Session, message_id: str) -> Optional[Poll]:
        """
        Retrieve a poll by its message ID.
        """
        return db.query(Poll).filter(Poll.message_id == message_id).first()

    @staticmethod
    def create_giveaway(db: Session, data: GiveawayCreate) -> Giveaway:
        """
        Create a new giveaway in the database.
        """
        db_giveaway = Giveaway(
            message_id=data.message_id,
            guild_id=data.guild_id,
            title=data.title,
            prize=data.prize,
            end_time=data.end_time,
            participants=data.participants
        )
        db.add(db_giveaway)
        db.commit()
        db.refresh(db_giveaway)
        return db_giveaway

    @staticmethod
    def get_giveaway(db: Session, message_id: str) -> Optional[Giveaway]:
        """
        Retrieve a giveaway by its message ID.
        """
        return db.query(Giveaway).filter(Giveaway.message_id == message_id).first()

    @staticmethod
    def add_rss_feed(db: Session, data: RSSFeedCreate) -> RSSFeed:
        """
        Add a new RSS feed subscription.
        """
        db_feed = RSSFeed(
            guild_id=data.guild_id,
            channel_id=data.channel_id,
            url=data.url,
            last_item_id=data.last_item_id
        )
        db.add(db_feed)
        db.commit()
        db.refresh(db_feed)
        return db_feed

    @staticmethod
    def get_rss_feeds(db: Session, guild_id: Optional[str] = None) -> List[RSSFeed]:
        """
        Retrieve RSS feeds, optionally filtered by guild.
        """
        query = db.query(RSSFeed)
        if guild_id:
            query = query.filter(RSSFeed.guild_id == guild_id)
        return query.all()

    @staticmethod
    def create_pogo_event(db: Session, data: PogoEventCreate) -> PogoEvent:
        """
        Create a new Pokemon GO event.
        """
        db_event = PogoEvent(
            guild_id=data.guild_id,
            name=data.name,
            timestamp=data.timestamp,
            location=data.location
        )
        db.add(db_event)
        db.commit()
        db.refresh(db_event)
        return db_event

    @staticmethod
    def create_gamer_role(db: Session, data: GamerRoleCreate) -> GamerRole:
        """
        Register a new gamer role.
        """
        db_role = GamerRole(
            guild_id=data.guild_id,
            role_id=data.role_id,
            category=data.category
        )
        db.add(db_role)
        db.commit()
        db.refresh(db_role)
        return db_role

    @staticmethod
    def get_gamer_roles(db: Session, guild_id: str) -> List[GamerRole]:
        """
        Retrieve all gamer roles for a guild.
        """
        return db.query(GamerRole).filter(GamerRole.guild_id == guild_id).all()
