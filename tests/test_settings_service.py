import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from models.base import Base
from models.guild_settings import GuildSettings
from services.settings_service import SettingsService
from schemas.settings import GuildSettingsUpdate

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

def test_initialize_guild(db_session: Session):
    guild_id = "123456789"
    settings = SettingsService.initialize_guild(db_session, guild_id)
    
    assert settings.guild_id == guild_id
    assert settings.luck_threshold == 10
    assert settings.max_starting_skill == 75
    assert settings.game_mode == "Call of Cthulhu"
    assert settings.karma_settings == {}

def test_get_guild_settings_auto_init(db_session: Session):
    guild_id = "123456789"
    # Should automatically initialize if not found
    settings = SettingsService.get_guild_settings(db_session, guild_id)
    
    assert settings.guild_id == guild_id
    assert settings.luck_threshold == 10

def test_update_guild_settings(db_session: Session):
    guild_id = "123456789"
    # First get it (auto-init)
    SettingsService.get_guild_settings(db_session, guild_id)
    
    # Update luck threshold and game mode
    update_data = GuildSettingsUpdate(
        luck_threshold=20,
        game_mode="Pulp of Cthulhu",
        karma_settings={"enabled": True}
    )
    
    updated_settings = SettingsService.update_guild_settings(db_session, guild_id, update_data)
    
    assert updated_settings.luck_threshold == 20
    assert updated_settings.game_mode == "Pulp of Cthulhu"
    assert updated_settings.karma_settings == {"enabled": True}
    # Ensure other things didn't change
    assert updated_settings.max_starting_skill == 75

def test_update_guild_settings_partial(db_session: Session):
    guild_id = "123456789"
    SettingsService.get_guild_settings(db_session, guild_id)
    
    # Update only one field
    update_data = GuildSettingsUpdate(max_starting_skill=90)
    updated_settings = SettingsService.update_guild_settings(db_session, guild_id, update_data)
    
    assert updated_settings.max_starting_skill == 90
    assert updated_settings.luck_threshold == 10 # still default
