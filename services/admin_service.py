import os
import subprocess
import sys
import discord
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
    async def perform_backup(bot: discord.Client, target_user: discord.User = None) -> tuple[bool, str]:
        """
        Zips the data/ folder and sends it to the target user (default: bot owner).
        """
        import io
        import zipfile
        try:
            # If no target user is specified, default to the bot owner
            if target_user is None:
                app_info = await bot.application_info()
                target_user = app_info.owner

            # Create a zip buffer
            zip_buffer = io.BytesIO()

            # current date/time for filename
            now = datetime.now()
            filename = f"backup_{now.strftime('%Y-%m-%d_%H-%M')}.zip"

            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Walk through data directory
                if os.path.exists('data'):
                    for root, dirs, files in os.walk('data'):
                        for file in files:
                            file_path = os.path.join(root, file)
                            # Add file to zip, arcname makes it relative to current directory (so it includes data/)
                            zip_file.write(file_path, os.path.relpath(file_path, '.'))

            zip_buffer.seek(0)

            await target_user.send(file=discord.File(zip_buffer, filename))
            return True, filename
        except Exception as e:
            return False, str(e)

    @staticmethod
    def trigger_restart(pid: int) -> bool:
        """
        Trigger a bot restart.
        """
        try:
            subprocess.Popen([sys.executable, "restarter.py", str(pid)])
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
@staticmethod
def trigger_update(pid: int, update_infodata: bool = False) -> bool:
    """
    Trigger a bot update.
    """
    try:
        cmd = [sys.executable, "updater.py", str(pid)]
        if update_infodata:
            cmd.append("--update-infodata")

        if os.name == 'nt':
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen(cmd)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

