import random
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from models.codex import CodexEntry

class CodexService:
    @staticmethod
    def search_entries(db: Session, query: str, category: str = None) -> List[CodexEntry]:
        """
        Search for codex entries by name or content.
        Uses SQL ILIKE for fuzzy matching.
        """
        stmt = db.query(CodexEntry)
        if category:
            stmt = stmt.filter(CodexEntry.category == category)
        
        search_pattern = f"%{query}%"
        # Search in name or JSON content (cast to string for searching)
        stmt = stmt.filter(
            or_(
                CodexEntry.name.ilike(search_pattern),
                func.cast(CodexEntry.content, str).ilike(search_pattern)
            )
        )
        return stmt.all()

    @staticmethod
    def get_autocomplete(db: Session, query: str, category: str = None) -> List[str]:
        """
        Return a list of entry names for Discord autocomplete.
        Limited to 25 results as per Discord API limits.
        """
        stmt = db.query(CodexEntry.name)
        if category:
            stmt = stmt.filter(CodexEntry.category == category)
        
        stmt = stmt.filter(CodexEntry.name.ilike(f"%{query}%")).limit(25)
        # Flatten the result list of tuples to a list of strings
        return [row[0] for row in stmt.all()]

    @staticmethod
    def get_entry_by_name(db: Session, name: str, category: str = None) -> Optional[CodexEntry]:
        """
        Retrieve a single codex entry by its exact name.
        """
        stmt = db.query(CodexEntry).filter(CodexEntry.name == name)
        if category:
            stmt = stmt.filter(CodexEntry.category == category)
        return stmt.first()

    @staticmethod
    def get_random_entry(db: Session, category: str = None) -> Optional[CodexEntry]:
        """
        Retrieve a random codex entry, optionally filtered by category.
        """
        stmt = db.query(CodexEntry)
        if category:
            stmt = stmt.filter(CodexEntry.category == category)
        
        count = stmt.count()
        if count == 0:
            return None
        
        random_offset = random.randint(0, count - 1)
        return stmt.offset(random_offset).first()

    @staticmethod
    def generate_npc_stats() -> dict:
        """
        Generates random CoC 7e stats for an NPC.
        """
        def roll_3d6_x5():
            return 5 * sum([random.randint(1, 6) for _ in range(3)])

        def roll_2d6_plus_6_x5():
            return 5 * (sum([random.randint(1, 6) for _ in range(2)]) + 6)

        stats = {
            "STR": roll_3d6_x5(),
            "CON": roll_3d6_x5(),
            "DEX": roll_3d6_x5(),
            "APP": roll_3d6_x5(),
            "POW": roll_3d6_x5(),
            "LUCK": roll_3d6_x5(),
            "SIZ": roll_2d6_plus_6_x5(),
            "INT": roll_2d6_plus_6_x5(),
            "EDU": roll_2d6_plus_6_x5(),
        }

        # Derived Stats
        stats["HP"] = (stats["CON"] + stats["SIZ"]) // 10
        stats["MP"] = stats["POW"] // 5
        stats["SAN"] = stats["POW"]

        # Build and Damage Bonus
        str_siz = stats["STR"] + stats["SIZ"]
        if 2 <= str_siz <= 64: db="-2"; b=-2
        elif 65 <= str_siz <= 84: db="-1"; b=-1
        elif 85 <= str_siz <= 124: db="0"; b=0
        elif 125 <= str_siz <= 164: db="+1D4"; b=1
        elif 165 <= str_siz <= 204: db="+1D6"; b=2
        elif 205 <= str_siz <= 284: db="+2D6"; b=3
        elif 285 <= str_siz <= 364: db="+3D6"; b=4
        elif 365 <= str_siz <= 444: db="+4D6"; b=5
        elif 445 <= str_siz <= 524: db="+5D6"; b=6
        else: db="+6D6"; b=7
        stats["DB"] = db
        stats["Build"] = b

        # Move
        mov = 8
        if stats["DEX"] < stats["SIZ"] and stats["STR"] < stats["SIZ"]: mov = 7
        elif stats["DEX"] > stats["SIZ"] and stats["STR"] > stats["SIZ"]: mov = 9
        stats["Move"] = mov
        return stats

    @staticmethod
    async def generate_npc_name(gender: str, region: str) -> str:
        """
        Generates a random name for an NPC based on gender and region.
        """
        from loadnsave import load_names_data
        all_names = await load_names_data()
        region_names = all_names.get(region, all_names.get("english", {}))
        last_names = region_names.get("last", [])
        
        if gender == "male":
            first_names = region_names.get("male", [])
        else:
            first_names = region_names.get("female", [])

        if not first_names or not last_names:
             return "Unknown NPC"
        
        name = random.choice(first_names)
        if random.random() < 0.1:
            name += " " + random.choice(first_names)
        name += " " + random.choice(last_names)
        if random.random() < 0.1:
            name += "-" + random.choice(last_names)
        return name
