import json
import os
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
            is_retired=data.is_retired
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
