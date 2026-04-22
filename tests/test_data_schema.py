import pytest
import os
import json
from unittest.mock import MagicMock, patch, AsyncMock
from loadnsave import load_player_stats, save_player_stats
import commands.newinvestigator

@pytest.mark.asyncio
async def test_new_investigator_wizard_initial_data():
    bot = MagicMock()
    cog = commands.newinvestigator.newinvestigator(bot)
    
    interaction = MagicMock()
    interaction.response.is_done.return_value = False
    # Mock the async method
    interaction.response.send_message = AsyncMock()
    
    player_stats = {}
    
    with patch("commands.newinvestigator.BasicInfoStartView") as MockView:
        await cog.start_wizard(interaction, player_stats)
        
        # Get the first call to BasicInfoStartView
        args, kwargs = MockView.call_args
        char_data = args[1] # second arg is char_data
        
        backstory = char_data.get("Backstory", {})
        required_fields = [
            "Personal Description",
            "Ideology/Beliefs",
            "Significant People",
            "Meaningful Locations",
            "Treasured Possessions",
            "Traits"
        ]
        
        for field in required_fields:
            assert field in backstory, f"Field '{field}' missing from Backstory in new character"
        
        assert "Connections" in char_data
        assert char_data["Connections"] == []

@pytest.fixture
def mock_player_stats(tmp_path, monkeypatch):
    # Create a temporary data directory
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    stats_file = data_dir / "player_stats.json"
    
    # Initial data with old schema
    initial_data = {
        "123456789": { # Server ID
            "987654321": { # User ID
                "NAME": "Old Man Henderson",
                "Age": 70,
                "Backstory": {
                    "Pulp Talents": ["Hardened"],
                    "Gear and Possessions": ["Shotgun"]
                }
            }
        }
    }
    stats_file.write_text(json.dumps(initial_data))
    
    # Monkeypatch DATA_FOLDER in loadnsave
    monkeypatch.setattr("loadnsave.DATA_FOLDER", str(data_dir))
    
    # Reset cache in loadnsave
    monkeypatch.setattr("loadnsave._PLAYER_STATS_CACHE", None)
    
    return initial_data

@pytest.mark.asyncio
async def test_backstory_fields_exist(mock_player_stats):
    stats = await load_player_stats()
    char_data = stats["123456789"]["987654321"]
    
    backstory = char_data.get("Backstory", {})
    
    required_fields = [
        "Personal Description",
        "Ideology/Beliefs",
        "Significant People",
        "Meaningful Locations",
        "Treasured Possessions",
        "Traits"
    ]
    
    for field in required_fields:
        assert field in backstory, f"Field '{field}' missing from Backstory"

@pytest.mark.asyncio
async def test_connections_field_exists(mock_player_stats):
    stats = await load_player_stats()
    char_data = stats["123456789"]["987654321"]
    
    assert "Connections" in char_data, "Field 'Connections' missing from character data"
    assert isinstance(char_data["Connections"], list), "'Connections' should be a list"
