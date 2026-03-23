import json
import os
from datetime import datetime
from sqlalchemy.orm import Session
from models.investigator import Investigator
from schemas.investigator import InvestigatorCreate
from typing import Dict, Any, Optional

class CharacterService:
    @staticmethod
    def create_investigator(db: Session, data: InvestigatorCreate) -> Investigator:
        """
        Create a new investigator in the database.
        """
        db_investigator = Investigator(
            guild_id=data.guild_id,
            discord_user_id=data.discord_user_id,
            name=data.name,
            occupation=data.occupation,
            str=data.str_stat,
            con=data.con,
            siz=data.siz,
            dex=data.dex,
            app=data.app,
            int=data.int_stat,
            pow=data.pow_stat,
            edu=data.edu,
            luck=data.luck,
            skills=data.skills,
            extra_data=data.extra_data,
            backstory=data.backstory,
            biography=data.biography,
            is_retired=data.is_retired,
            retirement_date=data.retirement_date,
            last_played=data.last_played or datetime.utcnow()
        )
        db.add(db_investigator)
        db.commit()
        db.refresh(db_investigator)
        return db_investigator

    @staticmethod
    def get_investigator(db: Session, investigator_id: int) -> Investigator:
        """
        Retrieve an investigator by their ID.
        Raises ValueError if not found.
        """
        db_investigator = db.query(Investigator).filter(Investigator.id == investigator_id).first()
        if not db_investigator:
            raise ValueError(f"Investigator with ID {investigator_id} not found")
        return db_investigator

    @staticmethod
    def rename_investigator(db: Session, investigator_id: int, new_name: str) -> Investigator:
        """
        Update the name of an investigator and refresh their last_played timestamp.
        """
        db_investigator = CharacterService.get_investigator(db, investigator_id)
        db_investigator.name = new_name
        db_investigator.last_played = datetime.utcnow()
        db.commit()
        db.refresh(db_investigator)
        return db_investigator

    @staticmethod
    def rename_skill(db: Session, investigator_id: int, old_skill: str, new_skill: str) -> Investigator:
        """
        Safely rename a skill in the investigator's skills JSON column.
        """
        db_investigator = CharacterService.get_investigator(db, investigator_id)
        if db_investigator.skills and old_skill in db_investigator.skills:
            # Create a copy to trigger SQLAlchemy JSON change detection
            skills = dict(db_investigator.skills)
            skills[new_skill] = skills.pop(old_skill)
            db_investigator.skills = skills
            db.commit()
            db.refresh(db_investigator)
        return db_investigator

    @staticmethod
    def add_skill(db: Session, investigator_id: int, skill_name: str, value: int) -> Investigator:
        """
        Add a new skill or update an existing one.
        """
        db_investigator = CharacterService.get_investigator(db, investigator_id)
        skills = dict(db_investigator.skills) if db_investigator.skills else {}
        skills[skill_name] = value
        db_investigator.skills = skills
        db.commit()
        db.refresh(db_investigator)
        return db_investigator

    @staticmethod
    def remove_skill(db: Session, investigator_id: int, skill_name: str) -> Investigator:
        """
        Remove a skill from the investigator's skills.
        """
        db_investigator = CharacterService.get_investigator(db, investigator_id)
        if db_investigator.skills and skill_name in db_investigator.skills:
            skills = dict(db_investigator.skills)
            del skills[skill_name]
            db_investigator.skills = skills
            db.commit()
            db.refresh(db_investigator)
        return db_investigator

    @staticmethod
    def manage_backstory(db: Session, investigator_id: int, category: str, entry: Any, action: str) -> Investigator:
        """
        Manage backstory entries. 
        Actions: 'add', 'remove', 'edit'.
        For 'edit', entry can be a tuple of (index_or_old_value, new_value).
        Backstory structure: {category: [list of entries]}.
        """
        db_investigator = CharacterService.get_investigator(db, investigator_id)
        # Create a copy to ensure SQLAlchemy detects changes in the JSON column
        backstory = dict(db_investigator.backstory) if db_investigator.backstory else {}
        
        if category not in backstory:
            backstory[category] = []
        elif not isinstance(backstory[category], list):
            # Migration/Cleanup: convert single string entries to list
            backstory[category] = [str(backstory[category])]
            
        if action == "add":
            backstory[category].append(str(entry))
        elif action == "remove":
            if isinstance(entry, int) and 0 <= entry < len(backstory[category]):
                backstory[category].pop(entry)
            elif str(entry) in backstory[category]:
                backstory[category].remove(str(entry))
        elif action == "edit":
            if isinstance(entry, (list, tuple)) and len(entry) == 2:
                target, new_value = entry
                if isinstance(target, int) and 0 <= target < len(backstory[category]):
                    backstory[category][target] = str(new_value)
                elif str(target) in backstory[category]:
                    idx = backstory[category].index(str(target))
                    backstory[category][idx] = str(new_value)
        
        db_investigator.backstory = backstory
        db.commit()
        db.refresh(db_investigator)
        return db_investigator

    @staticmethod
    def toggle_retirement(db: Session, investigator_id: int, status: bool) -> Investigator:
        """
        Toggle the retirement status of an investigator and update retirement_date.
        """
        db_investigator = CharacterService.get_investigator(db, investigator_id)
        db_investigator.is_retired = status
        db_investigator.retirement_date = datetime.utcnow() if status else None
        db.commit()
        db.refresh(db_investigator)
        return db_investigator

    @staticmethod
    def get_investigator_by_guild_and_user(db: Session, guild_id: str, discord_user_id: str) -> Optional[Investigator]:
        """
        Retrieve an active (non-retired) investigator by guild ID and Discord user ID.
        """
        return db.query(Investigator).filter(
            Investigator.guild_id == guild_id,
            Investigator.discord_user_id == discord_user_id,
            Investigator.is_retired == False
        ).first()

    @staticmethod
    def get_all_investigators(db: Session) -> list[Investigator]:
        """
        Retrieve all non-retired investigators.
        """
        return db.query(Investigator).filter(Investigator.is_retired == False).all()

    @staticmethod
    def get_retired_investigators(db: Session) -> list[Investigator]:
        """
        Retrieve all retired investigators.
        """
        return db.query(Investigator).filter(Investigator.is_retired == True).all()

    @staticmethod
    def get_retired_investigators_by_guild_and_user(db: Session, guild_id: str, discord_user_id: str) -> list[Investigator]:
        """
        Retrieve all retired investigators for a specific user in a guild.
        """
        return db.query(Investigator).filter(
            Investigator.guild_id == guild_id,
            Investigator.discord_user_id == discord_user_id,
            Investigator.is_retired == True
        ).all()

    @staticmethod
    def calculate_derived_stats(characteristics: dict, game_mode: str = "Call of Cthulhu") -> dict:
        """
        Calculates derived stats (HP, MP, SAN, DB, Build, Move) from characteristics.
        """
        # Standardize keys to lowercase for internal processing
        stats = {k.lower(): v for k, v in characteristics.items() if isinstance(v, int)}
        
        # Use aliases if common ones aren't present
        str_stat = stats.get("str", stats.get("str_stat", 0))
        con = stats.get("con", 0)
        siz = stats.get("siz", 0)
        dex = stats.get("dex", 0)
        pow_stat = stats.get("pow", stats.get("pow_stat", 0))
        app = stats.get("app", 0)
        age = characteristics.get("age", characteristics.get("Age", 20))

        # HP
        if game_mode == "Pulp of Cthulhu":
            hp = (con + siz) // 5
        else:
            hp = (con + siz) // 10
            
        # MP, SAN
        mp = pow_stat // 5
        san = pow_stat
        
        # Damage Bonus (DB) & Build
        str_siz = str_stat + siz
        if 2 <= str_siz <= 64:
            db = "-2"; build = -2
        elif 65 <= str_siz <= 84:
            db = "-1"; build = -1
        elif 85 <= str_siz <= 124:
            db = "0"; build = 0
        elif 125 <= str_siz <= 164:
            db = "+1D4"; build = 1
        elif 165 <= str_siz <= 204:
            db = "+1D6"; build = 2
        elif 205 <= str_siz <= 284:
            db = "+2D6"; build = 3
        elif 285 <= str_siz <= 364:
            db = "+3D6"; build = 4
        elif 365 <= str_siz <= 444:
            db = "+4D6"; build = 5
        elif 445 <= str_siz <= 524:
            db = "+5D6"; build = 6
        else:
            db = "+6D6"; build = 7
            
        # Movement
        mov = 8
        if dex < siz and str_stat < siz:
            mov = 7
        elif dex > siz and str_stat > siz:
            mov = 9
            
        # Age penalties to Move
        if 40 <= age <= 49: mov -= 1
        elif 50 <= age <= 59: mov -= 2
        elif 60 <= age <= 69: mov -= 3
        elif 70 <= age <= 79: mov -= 4
        elif age >= 80: mov -= 5
        
        return {
            "hp": hp,
            "mp": mp,
            "san": san,
            "damage_bonus": db,
            "build": build,
            "move": max(0, mov)
        }

    @staticmethod
    def update_investigator(db: Session, investigator_id: int, data: dict) -> Investigator:
        """
        Update an existing investigator's data.
        Raises ValueError if not found.
        """
        db_investigator = db.query(Investigator).filter(Investigator.id == investigator_id).first()
        if not db_investigator:
            raise ValueError(f"Investigator with ID {investigator_id} not found")
            
        for key, value in data.items():
            if hasattr(db_investigator, key):
                setattr(db_investigator, key, value)
                
        db.commit()
        db.refresh(db_investigator)
        return db_investigator

    @staticmethod
    def delete_investigator(db: Session, investigator_id: int) -> bool:
        """
        Permanently delete an investigator from the database.
        """
        db_investigator = db.query(Investigator).filter(Investigator.id == investigator_id).first()
        if db_investigator:
            db.delete(db_investigator)
            db.commit()
            return True
        return False

    @staticmethod
    def calculate_skill_points(characteristics: dict, occupation: str) -> int:
        """
        Calculates occupation skill points based on characteristics and occupation formula.
        Logic moved from newinvestigator.py.
        """
        # Load occupation data to get formula
        infodata_path = os.path.join("infodata", "occupations_info.json")
        occupation_info = {}
        if os.path.exists(infodata_path):
            try:
                with open(infodata_path, 'r', encoding='utf-8') as f:
                    all_occupations = json.load(f)
                    occupation_info = all_occupations.get(occupation, {})
            except (json.JSONDecodeError, FileNotFoundError):
                pass

        # Support both lowercase (model/schema) and uppercase (legacy) keys
        edu = characteristics.get("edu", characteristics.get("EDU", 0))
        dex = characteristics.get("dex", characteristics.get("DEX", 0))
        str_stat = characteristics.get("str", characteristics.get("STR", 0))
        app = characteristics.get("app", characteristics.get("APP", 0))
        pow_stat = characteristics.get("pow", characteristics.get("POW", 0))
        
        formula = occupation_info.get("skill_points", "EDU × 4")
        formula = formula.replace("x", "×").replace("X", "×").replace("*", "×").replace("–", "-")
        
        if "Varies" in formula:
            return 0
            
        try:
            if formula == "EDU × 4":
                return edu * 4
            
            parts = formula.split("+")
            total = 0
            for part in parts:
                part = part.strip()
                if "or" in part:
                    clean_part = part.replace("(", "").replace(")", "")
                    options = clean_part.split("or")
                    best_val = 0
                    for opt in options:
                        val = CharacterService._evaluate_term(opt.strip(), edu, dex, str_stat, app, pow_stat)
                        if val > best_val:
                            best_val = val
                    total += best_val
                else:
                    total += CharacterService._evaluate_term(part, edu, dex, str_stat, app, pow_stat)
            return total
        except Exception:
            return edu * 4

    @staticmethod
    def _evaluate_term(term: str, edu: int, dex: int, str_stat: int, app: int, pow_stat: int) -> int:
        """Helper to evaluate individual terms in skill point formulas (e.g. 'EDU × 4' or 'STR × 2')."""
        try:
            if "×" not in term:
                return 0
            stat_name, mult_str = term.split("×")
            stat_name = stat_name.strip()
            mult = int(mult_str.strip())
            if stat_name == "EDU": return edu * mult
            if stat_name == "DEX": return dex * mult
            if stat_name == "STR": return str_stat * mult
            if stat_name == "APP": return app * mult
            if stat_name == "POW": return pow_stat * mult
        except Exception:
            return 0
        return 0
