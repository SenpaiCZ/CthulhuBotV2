from pydantic import BaseModel, Field
from typing import Optional, List

class RollRequest(BaseModel):
    stat_name: Optional[str] = Field(None, description="The name of the stat or skill being rolled")
    bonus_dice: int = Field(0, ge=0, le=2, description="Number of bonus dice (0-2)")
    penalty_dice: int = Field(0, ge=0, le=2, description="Number of penalty dice (0-2)")
    difficulty: str = Field("Regular", description="The difficulty level (Regular, Hard, Extreme)")
    dice_expression: Optional[str] = Field(None, description="A dice expression like '3d6+4' if not a skill check")

class RollResult(BaseModel):
    final_roll: int = Field(..., description="The final result of the roll (1-100 for skill checks)")
    result_level: int = Field(..., description="Success level: 0=Fumble, 1=Fail, 2=Regular, 3=Hard, 4=Extreme, 5=Critical")
    result_text: str = Field(..., description="Human-readable result (e.g., 'Hard Success')")
    is_success: bool = Field(..., description="True if the roll passed the required difficulty")
    is_failure: bool = Field(..., description="True if the roll failed")
    is_fumble: bool = Field(..., description="True if the roll was a fumble")
    is_critical: bool = Field(..., description="True if the roll was a critical success")
    rolls: List[int] = Field(default_factory=list, description="All individual rolls (for bonus/penalty dice)")
    net_dice: int = Field(0, description="The net bonus/penalty dice applied")
    detail: Optional[str] = Field(None, description="Detailed breakdown of the roll (e.g. '[5, 3] + 4')")
