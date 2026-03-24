from services.metadata_service import MetadataService
from emojis import EmojiDictProxy

# Proxy for backward compatibility - delegates to MetadataService
occupation_emojis = EmojiDictProxy('Occupation')

def get_occupation_emoji(occupation_name):
    """Returns the emoji for a given occupation name, delegating to MetadataService."""
    val = MetadataService.get_emoji(occupation_name, 'Occupation')
    return val if val else "❓"
