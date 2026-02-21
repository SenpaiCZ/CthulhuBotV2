import re

stat_emojis = {
      "STR": ":muscle:",
      "DEX": ":runner:",
      "CON": ":heart:",
      "INT": ":brain:",
      "POW": ":zap:",
      "APP": ":heart_eyes:",
      "EDU": ":mortar_board:",
      "SIZ": ":bust_in_silhouette:",
      "HP": ":heartpulse:",
      "MP": ":sparkles:",
      "LUCK": ":four_leaf_clover:",
      "SAN": ":scales:",
      "Age": ":birthday:",
      "Residence": ":house:",
      "Occupation": ":briefcase:",
      "Move": ":person_running:",
      "Build": ":restroom:",
      "Damage Bonus": ":mending_heart:",
      "DB": ":mending_heart:",
      "Accounting": ":ledger:",
      "Anthropology": ":earth_americas:",
      "Appraise": ":mag:",
      "Archaeology": ":pick:",
      "Charm": ":heart_decoration:",
      "Photography": ":camera_with_flash:",
      "Art/Craft": ":art:",
      "Climb": ":mountain:",
      "Credit Rating": ":moneybag:",
      "Cthulhu Mythos": ":octopus:",
      "Demolitions": ":boom:",
      "Disguise": ":dress:",
      "Diving": ":diving_mask:",
      "Dodge": ":warning:",
      "Drive Auto": ":blue_car:",
      "Elec. Repair": ":wrench:",
      "Fast Talk": ":pinched_fingers:",
      "Fighting Brawl": ":boxing_glove:",
      "Firearms Handgun": ":gun:",
      "Firearms Rifle/Shotgun": ":gun:",
      "First Aid": ":ambulance:",
      "History": ":scroll:",
      "Intimidate": ":fearful:",
      "Jump": ":athletic_shoe:",
      "Language other": ":globe_with_meridians:",
      "Language own": ":speech_balloon:",
      "Law": ":scales:",
      "Library Use": ":books:",
      "Listen": ":ear:",
      "Locksmith": ":key:",
      "Mech. Repair": ":wrench:",
      "Medicine": ":pill:",
      "Natural World": ":deciduous_tree:",
      "Navigate": ":compass:",
      "Occult": ":crystal_ball:",
      "Persuade": ":speech_balloon:",
      "Pilot": ":airplane:",
      "Psychoanalysis": ":brain:",
      "Psychology": ":brain:",
      "Read Lips": ":lips:",
      "Ride": ":horse_racing:",
      "Science specific": ":microscope:",
      "Sleight of Hand": ":mage:",
      "Spot Hidden": ":eyes:",
      "Stealth": ":footprints:",
      "Survival": ":camping:",
      "Swim": ":swimmer:",
      "Throw": ":dart:",
      "Track": ":mag_right:",
      "Arabic": ":flag_ae:",
      "Bengali": ":flag_bd:",
      "Chinese": ":flag_cn:",
      "Czech": ":flag_cz:",
      "Danish": ":flag_dk:",
      "Dutch": ":flag_nl:",
      "English": ":flag_gb:",
      "Finnish": ":flag_fi:",
      "French": ":flag_fr:",
      "German": ":flag_de:",
      "Greek": ":flag_gr:",
      "Hindi": ":flag_in:",
      "Hungarian": ":flag_hu:",
      "Italian": ":flag_it:",
      "Japanese": ":flag_jp:",
      "Korean": ":flag_kr:",
      "Norwegian": ":flag_no:",
      "Polish": ":flag_pl:",
      "Portuguese": ":flag_pt:",
      "Romanian": ":flag_ro:",
      "Russian": ":flag_ru:",
      "Spanish": ":flag_es:",
      "Swedish": ":flag_se:",
      "Turkish": ":flag_tr:",
      "Vietnamese": ":flag_vn:",
      "Hebrew": ":flag_il:",
      "Thai": ":flag_th:",
      "Swahili": ":flag_ke:",
      "Urdu": ":flag_pk:",
      "Malay": ":flag_my:",
      "Filipino": ":flag_ph:",
      "Indonesian": ":flag_id:",
      "Maltese": ":flag_mt:",
      "Nepali": ":flag_np:",
      "Slovak": ":flag_sk:",
      "Slovenian": ":flag_si:",
      "Ukrainian": ":flag_ua:",
      "Bulgarian": ":flag_bg:",
      "Estonian": ":flag_ee:",
      "Icelandic": ":flag_is:",
      "Latvian": ":flag_lv:",
      "Lithuanian": ":flag_lt:",
      "Luxembourgish": ":flag_lu:",
      "Samoan": ":flag_ws:",
      "Tongan": ":flag_to:",
      "Fijian": ":flag_fj:",
      "Tahitian": ":flag_pf:",
      "Hawaiian": ":flag_us:",
      "Maori": ":flag_nz:",
      "Tibetan": ":flag_cn:",
      "Kurdish": ":flag_iq:",
      "Pashto": ":flag_af:",
      "Dari": ":flag_af:",
      "Balinese": ":flag_id:",
      "Turkmen": ":flag_tm:",
      "Bosnian": ":flag_ba:",
      "Croatian": ":flag_hr:",
      "Serbian": ":flag_rs:",
      "Macedonian": ":flag_mk:",
      "Albanian": ":flag_al:",
      "Mongolian": ":flag_mn:",
      "Armenian": ":flag_am:",
      "Georgian": ":flag_ge:",
      "Azerbaijani": ":flag_az:",
      "Kazakh": ":flag_kz:",
      "Kyrgyz": ":flag_kg:",
      "Tajik": ":flag_tj:",
      "Uzbek": ":flag_uz:",
      "Tatar": ":flag_ru:",
      "Bashkir": ":flag_ru:",
      "Chechen": ":flag_ru:",
      "Belarusian": ":flag_by:",
      "Moldovan": ":flag_md:",
      "Sami": ":flag_no:",
      "Faroese": ":flag_fo:",
      "Irish": ":flag_ie:",
      "Welsh": ":flag_gb:",
      "Scots Gaelic": ":flag_gb:",
      "Basque": ":flag_es:",
      "Catalan": ":flag_es:",
      "Galician": ":flag_es:",
      "Yiddish": ":flag_il:",
      "Malayalam": ":flag_in:",
      "Tamil": ":flag_in:",
      "Burmese": ":flag_mm:",
      "Khmer": ":flag_kh:",
      "Lao": ":flag_la:",
      "Bisaya": ":flag_ph:",
      "Cebuano": ":flag_ph:",
      "Ilocano": ":flag_ph:",
      "Hiligaynon": ":flag_ph:",
      "Waray": ":flag_ph:",
      "Chichewa": ":flag_mw:",
      "Kinyarwanda": ":flag_rw:",
      "Swazi": ":flag_sz:",
      "Tigrinya": ":flag_er:",
      "Haitian Creole": ":flag_ht:",
      "Frisian": ":flag_nl:",
      "Esperanto": ":white_flag:",
      "Latin": ":white_flag:",
      "Scots": ":flag_gb:",
      "Pirate": ":pirate_flag:",
      "Astronomy":":telescope:",
      "Biology":":microscope:",
      "Botany":":herb:",
      "Chemistry":":test_tube:",
      "Cryptography":":lock:",
      "Engineering":":gear:",
      "Forensics":":mag_right:",
      "Geology":":earth_americas:",
      "Mathematics":":1234:",
      "Meteorology":":cloud_with_lightning_and_rain:",
      "Pharmacy":":pill:",
      "Physics":":atom_symbol:",
      "Weird Science": ":scientist:",
      "Zoology":":paw_prints:",

      # New Explicit Mappings
      "Art / Craft (any)": ":art:",
      "Fighting (Brawl)": ":boxing_glove:",
      "Firearms (Handgun)": ":gun:",
      "Firearms (Rifle/Shotgun)": ":gun:",
      "Language (Other)": ":globe_with_meridians:",
      "Language (Own)": ":speech_balloon:",
      "Pilot (any)": ":airplane:",
      "Science (any)": ":microscope:",
      "Survival (any)": ":camping:",

      # Base Keys for Fuzzy Matching
      "Science": ":microscope:",
      "Fighting": ":boxing_glove:",
      "Firearms": ":gun:",
      "Art / Craft": ":art:",
      "Language": ":globe_with_meridians:",
      "Drive": ":blue_car:",
      "Survival": ":camping:",
      "Pilot": ":airplane:",

      # Era Specific / New Skills
      "Computer Use": ":computer:",
      "Electronics": ":electric_plug:",
      "Alienism": ":brain:",
      "Drive Carriage": ":horse:",
      "Operate Heavy Machinery": ":bullettrain_front:",
      "Reassure": ":handshake:",
      "Religion": ":place_of_worship:",
      "Animal Handling": ":lion_face:",
      "Drive Wagon/Coach": ":horse:",
      "Gambling": ":game_die:",
      "Rope Use": ":knot:",
      "Trap": ":mouse_trap:",
      "Drive (Horses/Oxen)": ":ox:",
      "Insight": ":bulb:",
      "Other Kingdoms (any)": ":world_map:",
      "Kingdom (Own)": ":castle:",
      "Pilot Boat": ":sailboat:",
      "Read/Write Language (any)": ":pencil:",
      "Repair/Devise": ":hammer_and_wrench:",
      "Ride Horse": ":horse_racing:",
      "Status": ":crown:",
      "Natural World (any)": ":deciduous_tree:",
      "Hypnosis": ":face_with_spiral_eyes:",
      "Lore": ":scroll:",
      "Artillery": ":crossed_swords:",

      # Weapons
      "Axe": ":axe:",
      "Sword": ":crossed_swords:",
      "Spear": ":dagger:",
      "Bow": ":bow_and_arrow:",
      "Flamethrower": ":fire:",
      "Heavy Weapons": ":rocket:",
      "Machine Gun": ":gun:",
      "Submachine Gun": ":gun:",
      "Chainsaw": ":axe:",
  }

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

  return ":question:"

def get_emoji_for_item(item_name):
    """Returns a relevant emoji based on item name keywords."""
    name_lower = item_name.lower()
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
