import os
import subprocess
from datetime import datetime
from sqlalchemy.orm import Session
from models.social import Reminder
from models.admin import AutoRoom, DeleterJob
from schemas.admin import AutoRoomCreate, ReminderCreate, DeleterJobCreate
from typing import List, Optional

class AdminService:
    @staticmethod
    def create_reminder(db: Session, data: ReminderCreate) -> Reminder:
        """
        Create a new reminder for a user.
        """
        db_reminder = Reminder(
            user_id=data.user_id,
            guild_id=data.guild_id,
            channel_id=data.channel_id,
            message=data.message,
            due_at=data.due_at
        )
        db.add(db_reminder)
        db.commit()
        db.refresh(db_reminder)
        return db_reminder

    @staticmethod
    def get_pending_reminders(db: Session) -> List[Reminder]:
        """
        Retrieve all reminders that are due or overdue.
        """
        return db.query(Reminder).filter(Reminder.due_at <= datetime.utcnow()).all()

    @staticmethod
    def delete_reminder(db: Session, reminder_id: int) -> bool:
        """
        Delete a reminder.
        """
        db_reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        if db_reminder:
            db.delete(db_reminder)
            db.commit()
            return True
        return False

    @staticmethod
    def create_autoroom(db: Session, data: AutoRoomCreate) -> AutoRoom:
        """
        Create a new autoroom configuration.
        """
        db_autoroom = AutoRoom(
            guild_id=data.guild_id,
            creator_id=data.creator_id,
            channel_id=data.channel_id,
            name_format=data.name_format
        )
        db.add(db_autoroom)
        db.commit()
        db.refresh(db_autoroom)
        return db_autoroom

    @staticmethod
    def create_deleter_job(db: Session, data: DeleterJobCreate) -> DeleterJob:
        """
        Create a new deleter job.
        """
        db_job = DeleterJob(
            guild_id=data.guild_id,
            channel_id=data.channel_id,
            user_id=data.user_id,
            status=data.status
        )
        db.add(db_job)
        db.commit()
        db.refresh(db_job)
        return db_job

    @staticmethod
    def run_backup() -> bool:
        """
        Trigger a database backup.
        """
        try:
            # Assuming there's a backup.py or similar in the root
            subprocess.run(["python", "backup.py"], check=True)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    @staticmethod
    def trigger_restart() -> bool:
        """
        Trigger a bot restart.
        """
        try:
            subprocess.Popen(["python", "restarter.py"])
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    @staticmethod
    def trigger_update() -> bool:
        """
        Trigger a bot update.
        """
        try:
            subprocess.Popen(["python", "updater.py"])
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
