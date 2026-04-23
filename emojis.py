import re

stat_emojis = {
      "STR": "💪",
      "DEX": "🏃",
      "CON": "❤️",
      "INT": "🧠",
      "POW": "⚡",
      "APP": "😍",
      "EDU": "🎓",
      "SIZ": "👤",
      "HP": "💗",
      "MP": "✨",
      "LUCK": "🍀",
      "SAN": "⚖️",
      "Age": "🎂",
      "Residence": "🏠",
      "Occupation": "💼",
      "Move": "🏃",
      "Build": "🚻",
      "Damage Bonus": "❤️‍🩹",
      "DB": "❤️‍🩹",
      "Accounting": "📒",
      "Anthropology": "🌎",
      "Appraise": "🔍",
      "Archaeology": "⛏️",
      "Charm": "💟",
      "Photography": "📸",
      "Art/Craft": "🎨",
      "Climb": "⛰️",
      "Credit Rating": "💰",
      "Cthulhu Mythos": "🐙",
      "Demolitions": "💥",
      "Disguise": "👗",
      "Diving": "🤿",
      "Dodge": "⚠️",
      "Drive Auto": "🚙",
      "Elec. Repair": "🔧",
      "Fast Talk": "🤌",
      "Fighting Brawl": "🥊",
      "Firearms Handgun": "🔫",
      "Firearms Rifle/Shotgun": "🔫",
      "First Aid": "🚑",
      "History": "📜",
      "Intimidate": "😨",
      "Jump": "👟",
      "Language other": "🌐",
      "Language own": "💬",
      "Law": "⚖️",
      "Library Use": "📚",
      "Listen": "👂",
      "Locksmith": "🔑",
      "Mech. Repair": "🔧",
      "Medicine": "💊",
      "Natural World": "🌳",
      "Navigate": "🧭",
      "Occult": "🔮",
      "Persuade": "💬",
      "Pilot": "✈️",
      "Psychoanalysis": "🧠",
      "Psychology": "🧠",
      "Read Lips": "👄",
      "Ride": "🏇",
      "Science specific": "🔬",
      "Sleight of Hand": "🧙",
      "Spot Hidden": "👀",
      "Stealth": "👣",
      "Survival": "🏕️",
      "Swim": "🏊",
      "Throw": "🎯",
      "Track": "🔎",
      "Arabic": "🇦🇪",
      "Bengali": "🇧🇩",
      "Chinese": "🇨🇳",
      "Czech": "🇨🇿",
      "Danish": "🇩🇰",
      "Dutch": "🇳🇱",
      "English": "🇬🇧",
      "Finnish": "🇫🇮",
      "French": "🇫🇷",
      "German": "🇩🇪",
      "Greek": "🇬🇷",
      "Hindi": "🇮🇳",
      "Hungarian": "🇭🇺",
      "Italian": "🇮🇹",
      "Japanese": "🇯🇵",
      "Korean": "🇰🇷",
      "Norwegian": "🇳🇴",
      "Polish": "🇵🇱",
      "Portuguese": "🇵🇹",
      "Romanian": "🇷🇴",
      "Russian": "🇷🇺",
      "Spanish": "🇪🇸",
      "Swedish": "🇸🇪",
      "Turkish": "🇹🇷",
      "Vietnamese": "🇻🇳",
      "Hebrew": "🇮🇱",
      "Thai": "🇹🇭",
      "Swahili": "🇰🇪",
      "Urdu": "🇵🇰",
      "Malay": "🇲🇾",
      "Filipino": "🇵🇭",
      "Indonesian": "🇮🇩",
      "Maltese": "🇲🇹",
      "Nepali": "🇳🇵",
      "Slovak": "🇸🇰",
      "Slovenian": "🇸🇮",
      "Ukrainian": "🇺🇦",
      "Bulgarian": "🇧🇬",
      "Estonian": "🇪🇪",
      "Icelandic": "🇮🇸",
      "Latvian": "🇱🇻",
      "Lithuanian": "🇱🇹",
      "Luxembourgish": "🇱🇺",
      "Samoan": "🇼🇸",
      "Tongan": "🇹🇴",
      "Fijian": "🇫🇯",
      "Tahitian": "🇵🇫",
      "Hawaiian": "🇺🇸",
      "Maori": "🇳🇿",
      "Tibetan": "🇨🇳",
      "Kurdish": "🇮🇶",
      "Pashto": "🇦🇫",
      "Dari": "🇦🇫",
      "Balinese": "🇮🇩",
      "Turkmen": "🇹🇲",
      "Bosnian": "🇧🇦",
      "Croatian": "🇭🇷",
      "Serbian": "🇷🇸",
      "Macedonian": "🇲🇰",
      "Albanian": "🇦🇱",
      "Mongolian": "🇲🇳",
      "Armenian": "🇦🇲",
      "Georgian": "🇬🇪",
      "Azerbaijani": "🇦🇿",
      "Kazakh": "🇰🇿",
      "Kyrgyz": "🇰🇬",
      "Tajik": "🇹🇯",
      "Uzbek": "🇺🇿",
      "Tatar": "🇷🇺",
      "Bashkir": "🇷🇺",
      "Chechen": "🇷🇺",
      "Belarusian": "🇧🇾",
      "Moldovan": "🇲🇩",
      "Sami": "🇳🇴",
      "Faroese": "🇫🇴",
      "Irish": "🇮🇪",
      "Welsh": "🇬🇧",
      "Scots Gaelic": "🇬🇧",
      "Basque": "🇪🇸",
      "Catalan": "🇪🇸",
      "Galician": "🇪🇸",
      "Yiddish": "🇮🇱",
      "Malayalam": "🇮🇳",
      "Tamil": "🇮🇳",
      "Burmese": "🇲🇲",
      "Khmer": "🇰🇭",
      "Lao": "🇱🇦",
      "Bisaya": "🇵🇭",
      "Cebuano": "🇵🇭",
      "Ilocano": "🇵🇭",
      "Hiligaynon": "🇵🇭",
      "Waray": "🇵🇭",
      "Chichewa": "🇲🇼",
      "Kinyarwanda": "🇷🇼",
      "Swazi": "🇸🇿",
      "Tigrinya": "🇪🇷",
      "Haitian Creole": "🇭🇹",
      "Frisian": "🇳🇱",
      "Esperanto": "🏳️",
      "Latin": "🏳️",
      "Scots": "🇬🇧",
      "Pirate": "🏴‍☠️",
      "Astronomy": "🔭",
      "Biology": "🔬",
      "Botany": "🌿",
      "Chemistry": "🧪",
      "Cryptography": "🔒",
      "Engineering": "⚙️",
      "Forensics": "🔎",
      "Geology": "🌎",
      "Mathematics": "🔢",
      "Meteorology": "⛈️",
      "Pharmacy": "💊",
      "Physics": "⚛️",
      "Weird Science": "🧑‍🔬",
      "Zoology": "🐾",

      # New Explicit Mappings
      "Art / Craft (any)": "🎨",
      "Fighting (Brawl)": "🥊",
      "Firearms (Handgun)": "🔫",
      "Firearms (Rifle/Shotgun)": "🔫",
      "Language (Other)": "🌐",
      "Language (Own)": "💬",
      "Pilot (any)": "✈️",
      "Science (any)": "🔬",
      "Survival (any)": "🏕️",

      # Base Keys for Fuzzy Matching
      "Science": "🔬",
      "Fighting": "🥊",
      "Firearms": "🔫",
      "Art / Craft": "🎨",
      "Language": "🌐",
      "Drive": "🚙",
      "Survival": "🏕️",
      "Pilot": "✈️",

      # Era Specific / New Skills
      "Computer Use": "💻",
      "Electronics": "🔌",
      "Alienism": "🧠",
      "Drive Carriage": "🐴",
      "Operate Heavy Machinery": "🚅",
      "Reassure": "🤝",
      "Religion": "🛐",
      "Animal Handling": "🦁",
      "Drive Wagon/Coach": "🐴",
      "Gambling": "🎲",
      "Rope Use": "🪢",
      "Trap": "🪤",
      "Drive (Horses/Oxen)": "🐂",
      "Insight": "💡",
      "Other Kingdoms (any)": "🗺️",
      "Kingdom (Own)": "🏰",
      "Pilot Boat": "⛵",
      "Read/Write Language (any)": "📝",
      "Repair/Devise": "🛠️",
      "Ride Horse": "🏇",
      "Status": "👑",
      "Natural World (any)": "🌳",
      "Hypnosis": "😵‍💫",
      "Lore": "📜",
      "Artillery": "⚔️",

      # Weapons
      "Axe": "🪓",
      "Sword": "⚔️",
      "Spear": "🗡️",
      "Bow": "🏹",
      "Flamethrower": "🔥",
      "Heavy Weapons": "🚀",
      "Machine Gun": "🔫",
      "Submachine Gun": "🔫",
      "Chainsaw": "🪓",
  }

web_symbols = {
      "STR": "✶",
      "DEX": "⌁",
      "CON": "⚖",
      "INT": "◎",
      "POW": "⚡",
      "APP": "✧",
      "EDU": "✎",
      "SIZ": "👤",
      "HP": "❣",
      "MP": "✧",
      "LUCK": "✦",
      "SAN": "⚖",
      "Age": "⧗",
      "Residence": "◎",
      "Occupation": "✶",
      "Move": "✶",
      "Build": "✶",
      "Damage Bonus": "⚔",
      "DB": "⚔",
      "History": "Ψ",
      "Occult": "✷",
      "Library Use": "✎",
      "Cthulhu Mythos": "Ψ",
      "Default": "✶"
}

def get_stat_emoji(stat_name, web_mode=False):
  # 1. Exact match
  source = web_symbols if web_mode else stat_emojis
  
  if stat_name in source:
      return source[stat_name]
  
  if not web_mode and stat_name in stat_emojis:
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
    """Returns a relevant emoji based on item name keywords."""
    name_lower = item_name.lower()

    # Specific items (High Priority)
    if any(x in name_lower for x in ["amulet", "artifact", "relic", "idol", "crystal", "orb"]):
        return "🧿"
    if any(x in name_lower for x in ["watch", "clock", "time"]):
        return "⌚"
    if any(x in name_lower for x in ["cigarette", "cigar", "tobacco", "pipe", "smoke"]):
        return "🚬"
    if any(x in name_lower for x in ["glasses", "spectacles", "monocle"]):
        return "👓"
    if any(x in name_lower for x in ["mask", "disguise"]):
        return "🎭"
    if any(x in name_lower for x in ["umbrella"]):
        return "☂️"

    if any(x in name_lower for x in ["gun", "rifle", "pistol", "shotgun", "revolver", "carbine", "smg", "machine gun", "handgun"]):
        return "🔫"
    if any(x in name_lower for x in ["knife", "dagger", "sword", "blade", "machete", "axe", "hatchet", "razor", "kukri", "spear"]):
        return "🗡️"
    if any(x in name_lower for x in ["potion", "vial", "bottle", "flask", "elixir", "medicine", "pill", "syringe", "drug"]):
        return "🧪"
    if any(x in name_lower for x in ["book", "journal", "diary", "note", "paper", "map", "scroll", "letter", "document", "tome"]):
        return "📖"
    if any(x in name_lower for x in ["key", "lockpick", "pass", "card"]):
        return "🗝️"
    if any(x in name_lower for x in ["money", "cash", "wallet", "coin", "gold", "silver", "bill", "gem", "jewel", "diamond", "ruby", "emerald", "sapphire", "ring", "necklace"]):
        return "💰"
    if any(x in name_lower for x in ["food", "ration", "canned", "meat", "bread", "water", "drink", "alcohol", "wine", "beer"]):
        return "🥫"
    if any(x in name_lower for x in ["clothes", "coat", "hat", "gloves", "boots", "shoes", "suit", "dress", "armor", "helmet", "vest"]):
        return "🧥"
    if any(x in name_lower for x in ["tool", "wrench", "hammer", "screwdriver", "pliers", "saw", "crowbar", "kit"]):
        return "🛠️"
    if any(x in name_lower for x in ["light", "torch", "lantern", "lamp", "candle", "match", "lighter"]):
        return "🔦"
    if any(x in name_lower for x in ["ammo", "bullet", "shell", "clip", "magazine"]):
        return "🎒"
    if any(x in name_lower for x in ["phone", "radio", "camera"]):
        return "📷"
    if any(x in name_lower for x in ["bag", "backpack", "suitcase", "briefcase", "purse"]):
        return "👜"
    if any(x in name_lower for x in ["ticket", "pass", "permit"]):
        return "🎫"
    return "📦"

def get_health_bar(current, max_val, length=8):
    if max_val <= 0: max_val = 1
    pct = current / max_val
    if pct < 0: pct = 0
    if pct > 1: pct = 1

    filled = int(pct * length)
    empty = length - filled

    # Color Logic
    fill_char = "🟩"
    if pct <= 0.2: fill_char = "🟥"
    elif pct <= 0.5: fill_char = "🟨"

    bar = (fill_char * filled) + ("⬛" * empty)
    return bar
