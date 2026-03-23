from pydantic import BaseModel, ConfigDict
from typing import Optional, Any, List

class CodexEntryBase(BaseModel):
    """
    Base schema for Codex entries shared across create and response models.
    """
    category: str
    name: str
    content: Any  # JSON content
    image_filename: Optional[str] = None

class CodexEntryCreate(CodexEntryBase):
    """
    Schema for creating a new Codex entry.
    """
    pass

class CodexEntry(CodexEntryBase):
    """
    Schema for a Codex entry as returned from the database, including its ID.
    """
    id: int
    
    model_config = ConfigDict(from_attributes=True)

class CodexSearchResult(BaseModel):
    """
    Schema for returning search matches with scores or relevance.
    """
    entry: CodexEntry
    score: float = 0.0
