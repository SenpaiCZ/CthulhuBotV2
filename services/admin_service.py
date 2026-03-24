import os
import subprocess
import sys
import discord
from discord.ext import commands
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
    def parse_duration(duration_str: str) -> int:
        """
        Parses a duration string (e.g. 1h 30m) into seconds.
        """
        import re
        total_seconds = 0
        text = duration_str.lower().strip()

        # Keyword support
        if text in ['tomorrow', 'tmrw']:
            return 86400
        if text in ['week', 'next week']:
            return 604800
        if text in ['hour', '1h']:
            return 3600

        # Regex for structured duration
        matches = re.findall(r'(\d+)\s*([dhms])', text)
        for amount, unit in matches:
            amount = int(amount)
            if unit == 'd': total_seconds += amount * 86400
            elif unit == 'h': total_seconds += amount * 3600
            elif unit == 'm': total_seconds += amount * 60
            elif unit == 's': total_seconds += amount

        return total_seconds

    @staticmethod
    async def create_reminder_api(reminders_dict, guild_id, channel_id, user_id, message, seconds):
        """
        Legacy JSON-based reminder creation.
        """
        from loadnsave import save_reminder_data
        from datetime import datetime, timezone
        due_time = datetime.now(timezone.utc).timestamp() + seconds
        reminder = {
            "id": str(int(datetime.now(timezone.utc).timestamp() * 1000)),
            "user_id": int(user_id),
            "channel_id": int(channel_id),
            "message": message,
            "due_timestamp": due_time,
            "created_at": datetime.now(timezone.utc).timestamp()
        }
        reminders_dict.setdefault(str(guild_id), []).append(reminder)
        await save_reminder_data(reminders_dict)
        return True, reminder

    @staticmethod
    async def delete_reminder_api(reminders_dict, guild_id, reminder_id):
        """
        Legacy JSON-based reminder deletion.
        """
        from loadnsave import save_reminder_data
        if str(guild_id) in reminders_dict:
            old_len = len(reminders_dict[str(guild_id)])
            reminders_dict[str(guild_id)] = [r for r in reminders_dict[str(guild_id)] if r.get('id') != reminder_id]
            if len(reminders_dict[str(guild_id)]) < old_len:
                await save_reminder_data(reminders_dict)
                return True, "Deleted"
        return False, "Not found"

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
    async def setup_autoroom(db: Session, guild_id: str, channel_id: int, category_id: int):
        from models.admin import AutoRoom
        # We might need a more flexible model or handle it in guild_settings
        # For now, let's assume we use the AutoRoom model or save to JSON bridge via loadnsave
        from loadnsave import autoroom_load, autoroom_save
        data = await autoroom_load()
        if guild_id not in data: data[guild_id] = {}
        data[guild_id]["channel_id"] = channel_id
        data[guild_id]["category_id"] = category_id
        await autoroom_save(data)
        return True

    @staticmethod
    async def get_autoroom_config(guild_id: str):
        from loadnsave import autoroom_load
        data = await autoroom_load()
        return data.get(guild_id, {})

    @staticmethod
    async def save_autoroom_user_channel(guild_id: str, user_id: str, channel_id: int):
        from loadnsave import autoroom_load, autoroom_save
        data = await autoroom_load()
        if guild_id not in data: data[guild_id] = {}
        data[guild_id][user_id] = channel_id
        await autoroom_save(data)

    @staticmethod
    async def add_reaction_role(guild_id, message_id, emoji_str, role_id, channel_id=None):
        from loadnsave import load_reaction_roles, save_reaction_roles
        data = await load_reaction_roles()
        sid, mid, rid = str(guild_id), str(message_id), str(role_id)
        data.setdefault(sid, {}).setdefault(mid, {"roles": {}})
        if "roles" not in data[sid][mid]: # Migration check
            data[sid][mid] = {"roles": data[sid][mid].copy()}
        if channel_id: data[sid][mid]["channel_id"] = str(channel_id)
        data[sid][mid]["roles"][emoji_str] = rid
        await save_reaction_roles(data)
        return True

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

    LEGACY_CATEGORY_MAP = {
        # Player
        "newinvestigator": "Player",
        "mycharacter": "Player",
        "Roll": "Player",
        "stat": "Player",
        "Backstory": "Player",
        "Session": "Player",
        "Retire": "Player", # Legacy text command
        "DeleteInvestigator": "Player", # Legacy text command
        "PrintCharacter": "Player",
        "Versus": "Player",
        "AddSkill": "Player",
        "Rename": "Player", # Legacy
        "RenameSkill": "Player", # Legacy

        # New Player Mappings
        "addbackstory": "Player",
        "Combat": "Player",
        "deleteinvestigator": "Player",
        "rename": "Player",
        "renameskill": "Player",
        "CharacterManagement": "Player", # retire, unretire
        "updatebackstory": "Player",
        "generatebackstory": "Player",

        # Codex
        "Codex": "Codex",

        # Keeper
        "Loot": "Keeper",
        "Madness": "Keeper",
        "Handout": "Keeper",
        "MacGuffin": "Keeper",
        "RandomNPC": "Keeper",
        "RandomName": "Keeper",
        "Chase": "Keeper",
        "macguffin": "Keeper", # New mapping for Keeper command

        # Music
        "Music": "Music",

        # Admin
        "Admin": "Admin",
        "Enroll": "Admin",
        "AutoRoom": "Admin", # Legacy
        "ReactionRole": "Admin", # Legacy
        "GameRoles": "Admin", # Legacy
        "RSS": "Admin", # Legacy
        "Karma": "Admin",
        "Ping": "Admin",
        "Restart": "Admin",
        "UpdateBot": "Admin",

        # New Admin Mappings
        "Deleter": "Admin",
        "Autoroom": "Admin",
        "backup": "Admin",
        "GamerRoles": "Admin",
        "ReactionRoles": "Admin",
        "rss": "Admin",
        "smartreaction": "Admin",
        "BotStatus": "Admin",
        "ChangeLuck": "Admin", # Command override for showluck handles Player cat

        # Other
        "Help": "Other",
        "Polls": "Other",
        "Reminders": "Other",
        "ReportBug": "Other",
        "Uptime": "Other",
        "Giveaway": "Other"
    }

    @staticmethod
    async def generate_help_data(bot, ctx):
        """
        Generates a dictionary of Category -> List of Commands.
        Dynamically discovers commands based on bot.cogs and bot.tree.
        """
        help_data = {cat: [] for cat in set(AdminService.LEGACY_CATEGORY_MAP.values())}
        # Ensure categories exist
        for cat in ["Player", "Codex", "Keeper", "Music", "Admin", "Other"]:
             if cat not in help_data: help_data[cat] = []

        # Track seen commands to avoid duplicates (by name)
        seen_commands = set()

        # 1. Iterate over Cogs to get categorized commands
        for cog_name, cog in bot.cogs.items():
            # Priority: Attribute -> Legacy Map -> Other
            cog_category = getattr(cog, "help_category", None)

            if not cog_category:
                cog_category = AdminService.LEGACY_CATEGORY_MAP.get(cog_name, "Other")
                if cog_category == "Other":
                     # Try class name if cog name didn't match
                     cog_category = AdminService.LEGACY_CATEGORY_MAP.get(type(cog).__name__, "Other")

            # Get App Commands from Cog
            if hasattr(cog, "get_app_commands"):
                for cmd in cog.get_app_commands():
                    if cmd.name == 'help': continue
                    # Determine command category: Check for override via extras, else use cog category
                    cmd_category = cog_category
                    if hasattr(cmd, "extras") and "help_category" in cmd.extras:
                         cmd_category = cmd.extras["help_category"]

                    if cmd.name not in seen_commands:
                        if cmd_category not in help_data: help_data[cmd_category] = []
                        help_data[cmd_category].append(cmd)
                        seen_commands.add(cmd.name)

            # Get Text Commands (Legacy)
            if hasattr(cog, "get_commands"):
                for cmd in cog.get_commands():
                    if cmd.name == 'help': continue
                    if cmd.hidden: continue
                    if not await AdminService._can_run(cmd, ctx): continue

                    if cmd.name not in seen_commands:
                        if cog_category not in help_data: help_data[cog_category] = []
                        help_data[cog_category].append(cmd)
                        seen_commands.add(cmd.name)

        # 2. Iterate remaining App Commands (Slash + Context Menus) from Tree
        app_cmds = bot.tree.get_commands()
        for cmd in app_cmds:
            if cmd.name == 'help': continue
            if cmd.name not in seen_commands:
                # Try to determine category from binding if present
                category = "Other"

                # Check extras first for tree commands
                if hasattr(cmd, "extras") and "help_category" in cmd.extras:
                     category = cmd.extras["help_category"]
                else:
                    binding = getattr(cmd, "binding", None)
                    if binding:
                        # Check if binding is a Cog instance
                        if isinstance(binding, commands.Cog):
                             cog = binding
                             category = getattr(cog, "help_category", None) or AdminService.LEGACY_CATEGORY_MAP.get(type(cog).__name__, "Other")
                        else:
                            cog_name = type(binding).__name__
                            category = AdminService.LEGACY_CATEGORY_MAP.get(cog_name, "Other")

                if category not in help_data: help_data[category] = []
                help_data[category].append(cmd)
                seen_commands.add(cmd.name)

        # Remove empty categories
        return {k: v for k, v in help_data.items() if v}

    @staticmethod
    async def _can_run(cmd, ctx):
        # Permission check
        if isinstance(cmd, commands.Command):
            try:
                return await cmd.can_run(ctx)
            except:
                return False
        return True # Assume app commands are visible unless filtered elsewhere

