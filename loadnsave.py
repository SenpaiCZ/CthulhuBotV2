import json
import aiofiles
import os
import shutil

DATA_FOLDER = "data"
INFODATA_FOLDER = "infodata"
GAMEDATA_FOLDER = "gamedata"

_INFODATA_CACHE = {}

async def _load_json_file(folder, filename):
    """Helper function to asynchronously load JSON data from a file."""
    file_path = os.path.join(folder, filename)
    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
            data = await file.read()
            return json.loads(data)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {file_path}: {e}")
        # Backup corrupted file
        try:
            shutil.copy2(file_path, file_path + ".bak")
            print(f"Backed up corrupted file to {file_path}.bak")
        except Exception as backup_error:
            print(f"Failed to backup corrupted file: {backup_error}")
        return {}

async def _load_infodata_cached(filename):
    """Helper function to load infodata from cache or disk."""
    if filename not in _INFODATA_CACHE:
        _INFODATA_CACHE[filename] = await _load_json_file(INFODATA_FOLDER, filename)
    return _INFODATA_CACHE[filename]

async def _save_json_file(folder, filename, data, ensure_ascii=True):
    """Helper function to asynchronously save JSON data to a file."""
    if not os.path.exists(folder):
        os.makedirs(folder)
    file_path = os.path.join(folder, filename)
    async with aiofiles.open(file_path, 'w', encoding='utf-8') as file:
        await file.write(json.dumps(data, indent=4, ensure_ascii=ensure_ascii))

    # Update cache if applicable
    if folder == INFODATA_FOLDER:
        _INFODATA_CACHE[filename] = data

# --- Player Stats ---
_PLAYER_STATS_CACHE = None

async def load_player_stats():
    global _PLAYER_STATS_CACHE
    if _PLAYER_STATS_CACHE is not None:
        return _PLAYER_STATS_CACHE

    _PLAYER_STATS_CACHE = await _load_json_file(DATA_FOLDER, 'player_stats.json')
    return _PLAYER_STATS_CACHE

async def save_player_stats(player_stats):
    global _PLAYER_STATS_CACHE
    _PLAYER_STATS_CACHE = player_stats
    await _save_json_file(DATA_FOLDER, 'player_stats.json', player_stats)

# --- Settings ---
def load_settings():
    """Synchronous load for settings with priority: ENV > config.json"""
    settings = {}

    # 1. Load config.json (Defaults)
    config_path = 'config.json'
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                settings.update(json.load(file))
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    # 2. Environment Variables
    if os.getenv("DISCORD_TOKEN"):
        settings["token"] = os.getenv("DISCORD_TOKEN")

    return settings

async def save_settings(settings_data):
    """Asynchronously save settings to config.json"""
    await _save_json_file('.', 'config.json', settings_data)

# --- Bot Status ---
async def load_bot_status():
    data = await _load_json_file(DATA_FOLDER, 'bot_status.json')
    if not data:
        return {"type": "playing", "text": "Call of Cthulhu"}
    return data

async def save_bot_status(data):
    await _save_json_file(DATA_FOLDER, 'bot_status.json', data)

# --- Server Stats ---
_SERVER_STATS_CACHE = None

async def load_server_stats():
    global _SERVER_STATS_CACHE
    if _SERVER_STATS_CACHE is None:
        _SERVER_STATS_CACHE = await _load_json_file(DATA_FOLDER, 'server_stats.json')
    return _SERVER_STATS_CACHE.copy()

async def save_server_stats(server_stats):
    global _SERVER_STATS_CACHE
    await _save_json_file(DATA_FOLDER, 'server_stats.json', server_stats)
    _SERVER_STATS_CACHE = server_stats.copy()

# --- Server Volumes ---
async def load_server_volumes():
    return await _load_json_file(DATA_FOLDER, 'server_volumes.json')

async def save_server_volumes(volumes):
    await _save_json_file(DATA_FOLDER, 'server_volumes.json', volumes)

# --- Smart React ---
async def smartreact_load():
    return await _load_json_file(DATA_FOLDER, 'smart_react.json')

async def smartreact_save(smart_react):
    await _save_json_file(DATA_FOLDER, 'smart_react.json', smart_react, ensure_ascii=False)

# --- Auto Room ---
async def autoroom_load():
    return await _load_json_file(DATA_FOLDER, 'autorooms.json')

async def autoroom_save(autorooms):
    await _save_json_file(DATA_FOLDER, 'autorooms.json', autorooms)

# --- Session Data ---
async def load_session_data():
    return await _load_json_file(DATA_FOLDER, 'session_data.json')

async def save_session_data(session_data):
    await _save_json_file(DATA_FOLDER, 'session_data.json', session_data)

# --- Info Data (Read-only mostly) ---
async def load_monsters_data():
    return await _load_infodata_cached('monsters.json')

async def load_spells_data():
    return await _load_infodata_cached('spells.json')

async def load_deities_data():
    return await _load_infodata_cached('deities.json')

async def load_madness_group_data():
    return await _load_infodata_cached('madness_with_group.json')

async def load_madness_solo_data():
    return await _load_infodata_cached('madness_alone.json')

async def load_madness_insane_talent_data():
    return await _load_infodata_cached('insane_talents.json')

async def load_pulp_talents_data():
    return await _load_infodata_cached('pulp_talents.json')

async def load_phobias_data():
    return await _load_infodata_cached('phobias.json')

async def load_manias_data():
    return await _load_infodata_cached('manias.json')

async def load_names_male_data():
    return await _load_infodata_cached('names_male.json')

async def load_names_female_data():
    return await _load_infodata_cached('names_female.json')

async def load_names_last_data():
    return await _load_infodata_cached('names_last.json')

async def load_archetype_data():
    return await _load_infodata_cached('archetype_info.json')

async def load_weapons_data():
    return await _load_infodata_cached('weapons.json')

async def load_inventions_data():
    return await _load_infodata_cached('inventions_info.json')

async def load_occupations_data():
    return await _load_infodata_cached('occupations_info.json')

async def load_skills_data():
    return await _load_infodata_cached('skills_info.json')

async def load_years_data():
    return await _load_infodata_cached('years_info.json')

async def load_poisons_data():
    return await _load_infodata_cached('poisions_info.json')

async def load_macguffin_data():
    return await _load_infodata_cached('macguffin_info.json')

# --- Luck Stats ---
async def load_luck_stats():
    return await _load_json_file(DATA_FOLDER, 'luck_stats.json')

async def save_luck_stats(server_stats):
    await _save_json_file(DATA_FOLDER, 'luck_stats.json', server_stats)

# --- Chase Data ---
async def load_chase_data():
    return await _load_json_file(DATA_FOLDER, 'chase_data.json')

async def save_chase_data(session_data):
    await _save_json_file(DATA_FOLDER, 'chase_data.json', session_data)

# --- Deleter Data ---
async def load_deleter_data():
    return await _load_json_file(DATA_FOLDER, 'deleter_data.json')

async def save_deleter_data(session_data):
    await _save_json_file(DATA_FOLDER, 'deleter_data.json', session_data)

# --- RSS Data ---
async def load_rss_data():
    return await _load_json_file(DATA_FOLDER, 'rss_data.json')

async def save_rss_data(session_data):
    await _save_json_file(DATA_FOLDER, 'rss_data.json', session_data)

# --- Soundboard Settings ---
async def load_soundboard_settings():
    return await _load_json_file(DATA_FOLDER, 'soundboard_settings.json')

async def save_soundboard_settings(settings_data):
    await _save_json_file(DATA_FOLDER, 'soundboard_settings.json', settings_data)

# --- Music Blacklist ---
async def load_music_blacklist():
    return await _load_json_file(DATA_FOLDER, 'music_blacklist.json')

async def save_music_blacklist(blacklist):
    await _save_json_file(DATA_FOLDER, 'music_blacklist.json', blacklist)

# --- Reminder Data ---
async def load_reminder_data():
    return await _load_json_file(DATA_FOLDER, 'reminder_data.json')

async def save_reminder_data(session_data):
    await _save_json_file(DATA_FOLDER, 'reminder_data.json', session_data)

# --- Game Data ---
async def game_load_player_data():
    return await _load_json_file(GAMEDATA_FOLDER, 'player_data.json')

async def game_save_player_data(session_data):
    await _save_json_file(GAMEDATA_FOLDER, 'player_data.json', session_data)

async def game_load_questions_data():
    return await _load_json_file(GAMEDATA_FOLDER, 'questions_data.json')

async def game_save_questions_data(session_data):
    await _save_json_file(GAMEDATA_FOLDER, 'questions_data.json', session_data)

# --- Retired Characters ---
async def load_retired_characters_data():
    return await _load_json_file(DATA_FOLDER, 'retired_characters_data.json')

async def save_retired_characters_data(session_data):
    await _save_json_file(DATA_FOLDER, 'retired_characters_data.json', session_data)

# --- Gamemode Stats ---
async def load_gamemode_stats():
    return await _load_json_file(DATA_FOLDER, 'gamemode.json')

async def save_gamemode_stats(server_stats):
    await _save_json_file(DATA_FOLDER, 'gamemode.json', server_stats)

# --- Karma System ---
async def load_karma_settings():
    return await _load_json_file(DATA_FOLDER, 'karma_settings.json')

async def save_karma_settings(settings):
    await _save_json_file(DATA_FOLDER, 'karma_settings.json', settings)

async def load_karma_stats():
    return await _load_json_file(DATA_FOLDER, 'karma_stats.json')

async def save_karma_stats(stats):
    await _save_json_file(DATA_FOLDER, 'karma_stats.json', stats)

# --- Reaction Roles ---
async def load_reaction_roles():
    return await _load_json_file(DATA_FOLDER, 'reaction_roles.json')

async def save_reaction_roles(roles_data):
    await _save_json_file(DATA_FOLDER, 'reaction_roles.json', roles_data)

# --- Pokemon GO Data ---
async def load_pogo_settings():
    return await _load_json_file(DATA_FOLDER, 'pogo_settings.json')

async def save_pogo_settings(settings):
    await _save_json_file(DATA_FOLDER, 'pogo_settings.json', settings)

async def load_pogo_events():
    return await _load_json_file(DATA_FOLDER, 'pogo_events.json')

async def save_pogo_events(events):
    await _save_json_file(DATA_FOLDER, 'pogo_events.json', events)

# --- Giveaway Data ---
async def load_giveaway_data():
    return await _load_json_file(DATA_FOLDER, 'giveaway_data.json')

async def save_giveaway_data(data):
    await _save_json_file(DATA_FOLDER, 'giveaway_data.json', data)

# --- Polls Data ---
async def load_polls_data():
    return await _load_json_file(DATA_FOLDER, 'polls_data.json')

async def save_polls_data(data):
    await _save_json_file(DATA_FOLDER, 'polls_data.json', data)

# --- Gamer Roles Data ---
async def load_gamerole_settings():
    return await _load_json_file(DATA_FOLDER, 'gamerole_settings.json')

async def save_gamerole_settings(data):
    await _save_json_file(DATA_FOLDER, 'gamerole_settings.json', data)

# --- Enroll Wizard Settings ---
async def load_enroll_settings():
    return await _load_json_file(DATA_FOLDER, 'enroll_settings.json')

async def save_enroll_settings(data):
    await _save_json_file(DATA_FOLDER, 'enroll_settings.json', data)

# --- Loot Settings ---
DEFAULT_LOOT_ITEMS = [
    "A Mysterious Journal", "A Cultist Robes", "A Whispering Locket",
    "A Mysterious Puzzle Box", "A Map of the area", "An Ornate dagger",
    "Binoculars", "An Old journal", "A Gas mask", "Handcuffs",
    "A Pocket watch", "A Police badge", "A Vial of poison",
    "A Rope (20 m)", "A Vial of holy water", "A Hunting knife",
    "A Lockpick", "A Vial of acid", "A Hammer", "Pliers", "A Bear trap",
    "A Bottle of poison", "A Perfume", "Flint and steel",
    "A Vial of blood", "A Round mirror", "A Pocket knife", "Matchsticks",
    "Cigarettes", "Sigars", "A Compass", "An Opium pipe",
    "A Vial of snake venom", "A Handkerchief", "A Personal diary",
    "A Wooden cross", "A Business card", "A Cultist's mask",
    "Cultist’s robes", "A Pocket watch", "A Bottle of absinthe",
    "A Vial of morphine", "A Vial of ether", "A Black candle",
    "A Flashlight", "A Baton", "A Bottle of whiskey", "A Bulletproof vest",
    "A First-aid kit", "A Baseball bat", "A Crowbar", "A Cigarillo case",
    "Brass knuckles", "A Switchblade knife", "A Bottle of chloroform",
    "Leather gloves", "A Sewing kit", "A Deck of cards", "Fishing Line",
    "An Axe", "A Saw", "A Rope (150 ft)", "A Water bottle", "A Lantern",
    "A Signaling mirror", "A Steel helmet", "A Waterproof cape",
    "A Colt 1911 Auto Handgun", "A Luger P08 Handgun",
    "A S&W .44 Double Action Handgun", "A Colt NS Revolver",
    "A Colt M1877 Pump-Action Rifle",
    "A Remington Model 12 Pump-Action Rifle",
    "A Savage Model 99 Lever-Action Rifle",
    "A Winchester M1897 Pump-Action Rifle", "A Browning Auto-5 Shotgun",
    "A Remington Model 11 Shotgun", "A Winchester Model 12 Shotgun",
    "A Beretta M1918 Submachine Gun", "An MP28 Submachine Gun",
    "Handgun Bullets (10)", "Handgun Bullets (20)", "Handgun Bullets (30)",
    "Rifle Bullets (10)", "Rifle Bullets (20)", "Rifle Bullets (30)",
    "Shotgun Shells (10)", "Shotgun Shells (20)", "Shotgun Shells (30)",
    "A Bowie Knife", "A Katana Sword", "Nunchucks", "A Tomahawk",
    "A Bayonet", "A Rifle Scope", "A Rifle Bipod", "A Shotgun Stock",
    "A Dynamite Stick", "A Dissecting Kit", "A Bolt Cutter", "A Hacksaw",
    "A Screwdriver Set", "A Sledge Hammer", "A Wire Cutter", "Canned Meat",
    "Dried Meat", "An Airmail Stamp", "A Postage Stamp", "A Camera",
    "A Chemical Test Kit", "A Codebreaking Kit", "A Geiger Counter",
    "A Magnifying Glass", "A Sextant", "Federal agent credentials",
    "Moonshine", "A Skeleton key", "A Can of tear gas", "A Trench coat",
    "Leather gloves", "A Fountain pen", "A Shoe shine kit",
    "A Straight razor", "Cufflinks", "A Snuff box", "A Perfume bottle",
    "Playing cards", "An Oil lantern", "A Mess kit", "A Folding shovel",
    "A Sewing kit", "A Grappling hook", "A Portable radio", "A Dice set",
    "Poker chips", "A Pipe", "Pipe tobacco", "A Hairbrush",
    "Reading glasses", "A Police whistle", "An Altimeter", "A Barometer",
    "A Scalpel", "A Chemistry set", "A Glass cutter", "A Trench periscope",
    "A Hand Grenade", "A Signal flare", "An Army ration",
    "A Can of kerosene", "A Butcher's knife", "A Pickaxe", "A Fishing kit",
    "An Antiseptic ointment", "Bandages", "A Cigarette Case", "A Matchbox",
    "A pair of Cufflinks", "A pair of Spectacles", "A pair of Sunglasses",
    "A set of Keys", "A tube of Lipstick", "A set of Hairpins",
    "A Checkbook", "An Address Book", "An Umbrella", "A pair of Gloves",
    "A Notebook", "A Gas cooker", "Rubber Bands", "A Water Bottle",
    "A Towel", "A Cigar Cutter", "A Magnifying Glass", "A Magnesium Flare",
    "A Hairbrush", "A Sketchbook", "A Police Badge",
    "A Fingerprinting Kit", "Lecture Notes", "A Measuring Tape",
    "Charcoal", "A Pencil Sharpener", "An Ink Bottle", "Research Notes",
    "A Crowbar", "A Fake ID", "A Stethoscope", "Bandages",
    "Business Cards", "A Leather-bound Journal", "A Prescription Pad",
    "Dog Tags", "A Pipe", "A Chocolate bar", "Strange bones",
    "A Prayer Book", "Surgical Instruments", "Fishing Lures",
    "Fishing Line", "Pliers", "A Bottle Opener", "A Wire Cutter",
    "A Wrench", "A Pocket Watch", "A Travel Guidebook", "A Passport",
    "Dental Tools", "A Surgical Mask", "A Bottle of red paint",
    "An Electricity cable (15 ft)", "A Smoke Grenade ",
    "A Heavy duty jacket", "A pair of Heavy duty trousers", "Motor Oil",
    "Army overalls", "A small scale", "A bottle of Snake Oil",
    "A Cane with a hidden sword", "A Monocle on a chain",
    "A Carved ivory chess piece", "Antique marbles", "A Bullwhip",
    "A Folding Fan", "A Folding Pocket Knife", "A Travel Chess Set",
    "A Pocket Book of Etiquette", "A Pocket Guide to Stars",
    "A Pocket Book of Flowers", "A Mandolin", "An Ukulele",
    "A Vial of Laudanum", "A Leather Bound Flask (empty)",
    "A Lock of Hair", "A Tobacco Pouch", "A flare gun", "A pipe bomb",
    "A Molotov cocktail", "An anti-personnel mine", "A machete",
    "A postcard", "A wristwatch", "A shovel", "A padlock",
    "A light chain (20 ft)", "A heavy chain (20 ft)", "A handsaw",
    "A telescope", "A water pipe", "A box of candles",
    "Aspirin (16 pills)", "Chewing Tobacco", "A Gentleman's Pocket Comb",
    "A Sailor's Knot Tying Guide", "A Leather Map Case", "A Camera",
    "Crystal Rosary Beads", "A Handmade Silver Bracelet",
    "Herbal Supplements", "A Bloodletting Tool",
    "A Spiritualist Seance Kit", "A Morphine Syringe",
    "A Bottle of Radioactive Water", "An Astrology Chart",
    "An Alchemy Kit", "A Mortar and Pestle", "A Scalpel",
    "An Erlenmeyer Flask", "A Chemistry Textbook", "Nautical Charts",
    "A Bottle of Sulfuric Acid", "Protective Gloves", "Safety Goggles",
    "A Kerosene Lamp", "Painkillers"
]

async def load_loot_settings():
    data = await _load_json_file(DATA_FOLDER, 'loot_settings.json')
    if not data:
        # Return defaults
        return {
            "items": DEFAULT_LOOT_ITEMS,
            "money_chance": 25,
            "money_min": 0.01,
            "money_max": 5.00,
            "currency_symbol": "$",
            "num_items_min": 1,
            "num_items_max": 5
        }
    return data

async def save_loot_settings(data):
    await _save_json_file(DATA_FOLDER, 'loot_settings.json', data)
