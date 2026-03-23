from sqlalchemy.orm import Session
from models.game_state import CombatSession, CombatParticipant
from models.investigator import Investigator
from services.character_service import CharacterService
from typing import Optional, List

class CombatService:
    @staticmethod
    def start_combat(db: Session, guild_id: str, channel_id: str) -> CombatSession:
        """
        Starts a new combat session for a given guild and channel.
        If an active session already exists, it is deactivated first.
        """
        # Deactivate any existing active session in this channel
        existing_session = db.query(CombatSession).filter(
            CombatSession.guild_id == guild_id,
            CombatSession.channel_id == channel_id,
            CombatSession.is_active == True
        ).first()
        
        if existing_session:
            existing_session.is_active = False
            db.commit()

        new_session = CombatSession(
            guild_id=guild_id,
            channel_id=channel_id,
            current_turn=0,
            is_active=True
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        return new_session

    @staticmethod
    def add_participant(db: Session, session_id: int, name: str, initiative: int, investigator_id: Optional[int] = None) -> CombatParticipant:
        """
        Adds a participant to an existing combat session.
        If investigator_id is provided, HP is calculated from the investigator's stats.
        """
        current_hp = 10 # Default HP for NPCs if not specified
        
        if investigator_id:
            investigator = db.query(Investigator).filter(Investigator.id == investigator_id).first()
            if investigator:
                stats = {
                    "con": investigator.con,
                    "siz": investigator.siz
                }
                derived = CharacterService.calculate_derived_stats(stats)
                current_hp = derived.get("hp", 10)
                if not name:
                    name = investigator.name

        participant = CombatParticipant(
            session_id=session_id,
            investigator_id=investigator_id,
            name=name,
            initiative=initiative,
            current_hp=current_hp
        )
        db.add(participant)
        db.commit()
        db.refresh(participant)
        return participant

    @staticmethod
    def next_turn(db: Session, session_id: int) -> Optional[CombatParticipant]:
        """
        Advances the turn to the next participant in initiative order.
        Returns the new active participant.
        """
        session = db.query(CombatSession).filter(CombatSession.id == session_id).first()
        if not session or not session.is_active:
            return None

        participants = db.query(CombatParticipant).filter(
            CombatParticipant.session_id == session_id
        ).order_by(CombatParticipant.initiative.desc(), CombatParticipant.id.asc()).all()

        if not participants:
            return None

        # Advance current_turn (1-based index)
        session.current_turn = (session.current_turn % len(participants)) + 1
        db.commit()
        db.refresh(session)

        return participants[session.current_turn - 1]

    @staticmethod
    def apply_damage(db: Session, participant_id: int, amount: int) -> CombatParticipant:
        """
        Applies damage (or healing if amount is negative) to a participant.
        """
        participant = db.query(CombatParticipant).filter(CombatParticipant.id == participant_id).first()
        if not participant:
            raise ValueError(f"Participant with ID {participant_id} not found")

        participant.current_hp -= amount
        db.commit()
        db.refresh(participant)
        return participant

    @staticmethod
    def end_combat(db: Session, session_id: int) -> bool:
        """
        Ends a combat session by setting is_active to False.
        """
        session = db.query(CombatSession).filter(CombatSession.id == session_id).first()
        if session:
            session.is_active = False
            db.commit()
            return True
        return False

    @staticmethod
    def get_active_session(db: Session, guild_id: str, channel_id: str) -> Optional[CombatSession]:
        """
        Retrieves the currently active combat session for a channel.
        """
        return db.query(CombatSession).filter(
            CombatSession.guild_id == guild_id,
            CombatSession.channel_id == channel_id,
            CombatSession.is_active == True
        ).first()
