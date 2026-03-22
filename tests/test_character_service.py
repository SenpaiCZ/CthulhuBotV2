import pytest
import os
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from models.base import Base
from models.investigator import Investigator
from services.character_service import CharacterService
from schemas.investigator import InvestigatorCreate

# In-memory SQLite for testing
@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_create_investigator(db_session: Session):
    data = InvestigatorCreate(
        discord_user_id="123456789",
        name="Test Investigator",
        occupation="Professor",
        str=50,
        con=50,
        siz=50,
        dex=50,
        app=50,
        int=50,
        pow=50,
        edu=50,
        luck=50,
        skills={"Library Use": 40},
        is_retired=False
    )
    
    investigator = CharacterService.create_investigator(db_session, data)
    
    assert investigator.id is not None
    assert investigator.name == "Test Investigator"
    assert investigator.discord_user_id == "123456789"
    assert investigator.skills == {"Library Use": 40}

def test_calculate_skill_points():
    # Mock data for character service to use
    characteristics = {
        "edu": 70,
        "dex": 50,
        "str": 40,
        "app": 60,
        "pow": 50
    }
    
    # Since we might not have the json file in the environment,
    # we'll test the default behavior (EDU * 4)
    points = CharacterService.calculate_skill_points(characteristics, "Unknown Occupation")
    assert points == 70 * 4

def test_update_investigator(db_session: Session):
    # First create one
    data = InvestigatorCreate(
        discord_user_id="123456789",
        name="Test Investigator",
        occupation="Professor",
        str=50,
        con=50,
        siz=50,
        dex=50,
        app=50,
        int=50,
        pow=50,
        edu=50,
        luck=50,
        skills={"Library Use": 40},
        is_retired=False
    )
    investigator = CharacterService.create_investigator(db_session, data)
    
    # Now update it
    update_data = {"name": "Updated Name", "is_retired": True}
    updated_investigator = CharacterService.update_investigator(db_session, investigator.id, update_data)
    
    assert updated_investigator.name == "Updated Name"
    assert updated_investigator.is_retired is True
    
    # Verify it's actually in the DB
    db_investigator = db_session.query(Investigator).filter(Investigator.id == investigator.id).first()
    assert db_investigator.name == "Updated Name"
