from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Dict, Optional, Any
from datetime import datetime

class InvestigatorBase(BaseModel):
    """
    Base schema for Investigator data shared across create and response models.
    """
    model_config = ConfigDict(populate_by_name=True)

    guild_id: str
    discord_user_id: str
    name: str
    occupation: Optional[str] = None
    
    # Character Characteristics (Standard CoC range is 15-90 for starting investigators)
    str_stat: int = Field(..., alias="str", ge=15, le=90, description="Strength")
    con: int = Field(..., ge=15, le=90, description="Constitution")
    siz: int = Field(..., ge=15, le=90, description="Size")
    dex: int = Field(..., ge=15, le=90, description="Dexterity")
    app: int = Field(..., ge=15, le=90, description="Appearance")
    int_stat: int = Field(..., alias="int", ge=15, le=90, description="Intelligence")
    pow_stat: int = Field(..., alias="pow", ge=15, le=90, description="Power")
    edu: int = Field(..., ge=15, le=90, description="Education")
    luck: int = Field(..., ge=15, le=90, description="Luck")
    
    # Skills are stored as a dictionary of skill name to its percentage value
    skills: Dict[str, int] = Field(default_factory=dict)
    extra_data: Dict[str, Any] = Field(default_factory=dict)
    backstory: Optional[Dict[str, Any]] = Field(default_factory=dict)
    biography: Optional[Dict[str, Any]] = Field(default_factory=dict)
    is_retired: bool = False
    retirement_date: Optional[datetime] = None
    last_played: Optional[datetime] = None

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

class InvestigatorUpdate(BaseModel):
    """
    Schema for updating an existing Investigator. All fields are optional.
    """
    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = None
    occupation: Optional[str] = None
    str_stat: Optional[int] = Field(None, alias="str", ge=15, le=90)
    con: Optional[int] = Field(None, ge=15, le=90)
    siz: Optional[int] = Field(None, ge=15, le=90)
    dex: Optional[int] = Field(None, ge=15, le=90)
    app: Optional[int] = Field(None, ge=15, le=90)
    int_stat: Optional[int] = Field(None, alias="int", ge=15, le=90)
    pow_stat: Optional[int] = Field(None, alias="pow", ge=15, le=90)
    edu: Optional[int] = Field(None, ge=15, le=90)
    luck: Optional[int] = Field(None, ge=15, le=90)
    skills: Optional[Dict[str, int]] = None
    extra_data: Optional[Dict[str, Any]] = None
    backstory: Optional[Dict[str, Any]] = None
    biography: Optional[Dict[str, Any]] = None
    is_retired: Optional[bool] = None
    retirement_date: Optional[datetime] = None
    last_played: Optional[datetime] = None

class Investigator(InvestigatorBase):
    """
    Schema for an Investigator as returned from the database, including its ID.
    """
    id: int
    
    model_config = ConfigDict(from_attributes=True)
