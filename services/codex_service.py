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
