import re
from services.metadata_service import MetadataService

class EmojiDictProxy(dict):
    """
    A proxy class that intercepts dictionary access and fetches from MetadataService.
    Supports backward compatibility for stat_emojis.
    """
    def __init__(self, categories=None):
        # We store the categories we want to search in
        self.categories = categories if isinstance(categories, list) else ([categories] if categories else [])
        super().__init__()

    def __getitem__(self, key):
        # Search in the specified categories
        cats = self.categories or ['Stat', 'Skill', 'Language', 'Item', 'System']
        for cat in cats:
            val = MetadataService.get_emoji(key, cat)
            if val:
                return val
        return ""

    def get(self, key, default=None):
        val = self[key]
        return val if val else default

    def items(self):
        cats = self.categories or ['Stat', 'Skill', 'Language', 'Item', 'System']
        res = []
        for cat in cats:
            for e in MetadataService.get_all_emojis_by_category(cat):
                res.append((e.key, e.value))
        return res

    def __contains__(self, key):
        return bool(self[key])

    def __iter__(self):
        return iter([k for k, v in self.items()])

    def __len__(self):
        return len(self.items())

# Replace the static dict with a proxy
stat_emojis = EmojiDictProxy(['Stat', 'Skill', 'Language', 'Item', 'System'])

def get_stat_emoji(stat_name):
  # 1. Exact match
  if stat_name in stat_emojis:
      return stat_emojis[stat_name]

  # 2. Check for "Name (Specialization)" pattern
  match = re.match(r"(.+?) \((.+)\)$", stat_name)
  if match:
      base = match.group(1)
      spec = match.group(2)

      # Try looking up the specialization directly
      if spec in stat_emojis:
           return stat_emojis[spec]

      # Try looking up the base name
      if base in stat_emojis:
           return stat_emojis[base]

  return "❓"

def get_emoji_for_item(item_name):
    """Returns a relevant emoji based on item name keywords pulling from MetadataService."""
    name_lower = item_name.lower()
    
    # Fetch all item keywords from MetadataService
    items = MetadataService.get_all_emojis_by_category('Item')
    
    # Sort by key length descending to ensure longest matches first (e.g. 'machine gun' before 'gun')
    items_sorted = sorted(items, key=lambda x: len(x.key), reverse=True)
    
    for item in items_sorted:
        if item.key.lower() in name_lower:
            return item.value
            
    return "📦"

def get_health_bar(current, max_val, length=8):
    if max_val <= 0: max_val = 1
    pct = current / max_val
    if pct < 0: pct = 0
    if pct > 1: pct = 1

    filled = int(pct * length)
    empty = length - filled

    # Color Logic - Pull from MetadataService
    green_char = MetadataService.get_emoji('health_bar_green', 'System') or "🟩"
    yellow_char = MetadataService.get_emoji('health_bar_yellow', 'System') or "🟨"
    red_char = MetadataService.get_emoji('health_bar_red', 'System') or "🟥"
    empty_char = MetadataService.get_emoji('health_bar_empty', 'System') or "⬛"

    fill_char = green_char
    if pct <= 0.2: 
        fill_char = red_char
    elif pct <= 0.5: 
        fill_char = yellow_char

    bar = (fill_char * filled) + (empty_char * empty)
    return bar
