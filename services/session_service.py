from sqlalchemy.orm import Session
from models.game_state import SessionLog
from datetime import datetime
from typing import List, Optional, Any

class SessionService:
    @staticmethod
    def log_event(db: Session, guild_id: str, event_type: str, description: str, metadata: Optional[dict] = None) -> SessionLog:
        """
        Logs an event to the session_logs table.
        """
        log_entry = SessionLog(
            guild_id=guild_id,
            timestamp=datetime.utcnow(),
            event_type=event_type,
            description=description,
            metadata_json=metadata
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        return log_entry

    @staticmethod
    def get_recent_logs(db: Session, guild_id: str, limit: int = 20) -> List[SessionLog]:
        """
        Retrieves the most recent session logs for a guild.
        """
        return db.query(SessionLog).filter(
            SessionLog.guild_id == guild_id
        ).order_by(SessionLog.timestamp.desc()).limit(limit).all()

    @staticmethod
    def start_session(db: Session, guild_id: str) -> SessionLog:
        """
        Logs a 'Session Started' event for the guild.
        """
        return SessionService.log_event(
            db=db,
            guild_id=guild_id,
            event_type="Session Started",
            description=f"A new gaming session has started."
        )
