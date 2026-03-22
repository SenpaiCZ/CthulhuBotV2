from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Dict, Optional

class InvestigatorBase(BaseModel):
    """
    Base schema for Investigator data shared across create and response models.
    """
    discord_user_id: str
    name: str
    occupation: Optional[str] = None
    
    # Character Characteristics (Standard CoC range is 15-90 for starting investigators)
    str: int = Field(..., ge=15, le=90, description="Strength")
    con: int = Field(..., ge=15, le=90, description="Constitution")
    siz: int = Field(..., ge=15, le=90, description="Size")
    dex: int = Field(..., ge=15, le=90, description="Dexterity")
    app: int = Field(..., ge=15, le=90, description="Appearance")
    int: int = Field(..., ge=15, le=90, description="Intelligence")
    pow: int = Field(..., ge=15, le=90, description="Power")
    edu: int = Field(..., ge=15, le=90, description="Education")
    luck: int = Field(..., ge=15, le=90, description="Luck")
    
    # Skills are stored as a dictionary of skill name to its percentage value
    skills: Dict[str, int] = Field(default_factory=dict)
    is_retired: bool = False

    @field_validator("skills")
    @classmethod
    def validate_skill_values(cls, v: Dict[str, int]) -> Dict[str, int]:
        """
        Validate that each skill value is within the 0-99% range.
        """
        for skill, value in v.items():
            if not (0 <= value <= 99):
                raise ValueError(f"Skill '{skill}' value {value} must be between 0 and 99.")
        return v

class InvestigatorCreate(InvestigatorBase):
    """
    Schema for creating a new Investigator.
    """
    pass

class Investigator(InvestigatorBase):
    """
    Schema for an Investigator as returned from the database, including its ID.
    """
    id: int
    
    model_config = ConfigDict(from_attributes=True)
