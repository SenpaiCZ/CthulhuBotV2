import json, aiofiles, os


# Define an async function to load player_stats from a JSON file
async def load_player_stats():
  try:
    data_folder = "data"  # Replace with the actual folder name
    file_path = os.path.join(data_folder, 'player_stats.json')
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to save player_stats to a JSON file
async def save_player_stats(player_stats):
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'player_stats.json')
  async with aiofiles.open(file_path, 'w') as file:
    await file.write(json.dumps(player_stats, indent=4))


# Define a function to load settings from a JSON file
def load_settings():
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'settings.json')
  try:
    with open(file_path, 'r') as file:
      return json.load(file)
  except FileNotFoundError:
    return {}  # Default values if the file doesn't exist


# Define an async function to load server_stats from a JSON file
async def load_server_stats():
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'server_stats.json')
  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to save server_stats to a JSON file
async def save_server_stats(server_stats):
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'server_stats.json')
  async with aiofiles.open(file_path, 'w') as file:
    await file.write(json.dumps(server_stats, indent=4))


# Define an async function to load smart react data from a JSON file
async def smartreact_load():
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'smart_react.json')
  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to save smart_react data to a JSON file
async def smartreact_save(smart_react):
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'smart_react.json')
  async with aiofiles.open(file_path, 'w', encoding='utf-8') as file:
    await file.write(json.dumps(smart_react, ensure_ascii=False, indent=4))


# Define an async function to load autoroom data from a JSON file
async def autoroom_load():
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'autorooms.json')
  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to save autoroom data to a JSON file
async def autoroom_save(autorooms):
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'autorooms.json')
  async with aiofiles.open(file_path, 'w') as file:
    await file.write(json.dumps(autorooms, indent=4))


# Define an async function to load YouTube feed data from a JSON file
async def youtube_load():
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'youtube_feed.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to save YouTube feed data to a JSON file
async def youtube_save(youtube_feed):
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'youtube_feed.json')

  async with aiofiles.open(file_path, 'w') as file:
    await file.write(json.dumps(youtube_feed, indent=4))


# Define an async function to load session data from a JSON file
async def load_session_data():
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'session_data.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to save session data to a JSON file
async def save_session_data(session_data):
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'session_data.json')

  async with aiofiles.open(file_path, 'w') as file:
    await file.write(json.dumps(session_data, indent=4))


# Define an async function to load group madness data from a JSON file
async def load_madness_group_data():
  data_folder = "infodata"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'madness_with_group.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to load solo madness data from a JSON file
async def load_madness_solo_data():
  data_folder = "infodata"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'madness_alone.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to load insane talents data from a JSON file
async def load_madness_insane_talent_data():
  data_folder = "infodata"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'insane_talents.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to load phobias data from a JSON file
async def load_phobias_data():
  data_folder = "infodata"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'phobias.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to load manias data from a JSON file
async def load_manias_data():
  data_folder = "infodata"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'manias.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to load name data from a JSON file
async def load_names_male_data():
  data_folder = "infodata"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'names_male.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to load name data from a JSON file
async def load_names_female_data():
  data_folder = "infodata"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'names_female.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to load name data from a JSON file
async def load_names_last_data():
  data_folder = "infodata"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'names_last.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to load archetype data from a JSON file
async def load_archetype_data():
  data_folder = "infodata"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'archetype_info.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to load firearms data from a JSON file
async def load_firearms_data():
  data_folder = "infodata"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'firearms_info.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to load inventions data from a JSON file
async def load_inventions_data():
  data_folder = "infodata"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'inventions_info.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to load inventions data from a JSON file
async def load_occupations_data():
  data_folder = "infodata"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'occupations_info.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to load inventions data from a JSON file
async def load_skills_data():
  data_folder = "infodata"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'skills_info.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to load inventions data from a JSON file
async def load_years_data():
  data_folder = "infodata"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'years_info.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to load server_stats from a JSON file
async def load_luck_stats():
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'luck_stats.json')
  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to save server_stats to a JSON file
async def save_luck_stats(server_stats):
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'luck_stats.json')
  async with aiofiles.open(file_path, 'w') as file:
    await file.write(json.dumps(server_stats, indent=4))


# Define an async function to load inventions data from a JSON file
async def load_poisons_data():
  data_folder = "infodata"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'poisions_info.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to load session data from a JSON file
async def load_chase_data():
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'chase_data.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to save session data to a JSON file
async def save_chase_data(session_data):
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'chase_data.json')

  async with aiofiles.open(file_path, 'w') as file:
    await file.write(json.dumps(session_data, indent=4))


# Define an async function to load session data from a JSON file
async def load_deleter_data():
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'deleter_data.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to save session data to a JSON file
async def save_deleter_data(session_data):
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'deleter_data.json')

  async with aiofiles.open(file_path, 'w') as file:
    await file.write(json.dumps(session_data, indent=4))


# Define an async function to load session data from a JSON file
async def load_macguffin_data():
  data_folder = "infodata"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'macguffin_info.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}

# Define an async function to load session data from a JSON file
async def load_rss_data():
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'rss_data.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to save session data to a JSON file
async def save_rss_data(session_data):
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'rss_data.json')

  async with aiofiles.open(file_path, 'w') as file:
    await file.write(json.dumps(session_data, indent=4))



# Define an async function to load session data from a JSON file
async def load_reminder_data():
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'reminder_data.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to save session data to a JSON file
async def save_reminder_data(session_data):
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'reminder_data.json')

  async with aiofiles.open(file_path, 'w') as file:
    await file.write(json.dumps(session_data, indent=4))





# Define an async function to load session data from a JSON file
async def game_load_player_data():
  data_folder = "gamedata"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'player_data.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to save session data to a JSON file
async def game_save_player_data(session_data):
  data_folder = "gamedata"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'player_data.json')

  async with aiofiles.open(file_path, 'w') as file:
    await file.write(json.dumps(session_data, indent=4))


# Define an async function to load session data from a JSON file
async def game_load_questions_data():
  data_folder = "gamedata"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'questions_data.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to save session data to a JSON file
async def game_save_questions_data(session_data):
  data_folder = "gamedata"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'questions_data.json')

  async with aiofiles.open(file_path, 'w') as file:
    await file.write(json.dumps(session_data, indent=4))


# Define an async function to load session data from a JSON file
async def load_retired_characters_data():
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'retired_characters_data.json')

  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to save session data to a JSON file
async def save_retired_characters_data(session_data):
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'retired_characters_data.json')

  async with aiofiles.open(file_path, 'w') as file:
    await file.write(json.dumps(session_data, indent=4))
    
# Define an async function to load server_stats from a JSON file
async def load_gamemode_stats():
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'gamemode.json')
  try:
    async with aiofiles.open(file_path, 'r') as file:
      data = await file.read()
      return json.loads(data)
  except FileNotFoundError:
    return {}


# Define an async function to save server_stats to a JSON file
async def save_gamemode_stats(server_stats):
  data_folder = "data"  # Replace with the actual folder name
  file_path = os.path.join(data_folder, 'gamemode.json')
  async with aiofiles.open(file_path, 'w') as file:
    await file.write(json.dumps(server_stats, indent=4))