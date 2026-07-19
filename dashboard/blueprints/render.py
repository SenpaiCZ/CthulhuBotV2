import os
import re
import emoji
import emojis
from quart import Blueprint, request, render_template
from markupsafe import escape

from dashboard.app import app, get_image_url
from dashboard.state import FONTS_FOLDER, MORSE_CODE_MAP
from ..file_utils import sanitize_filename
from loadnsave import (
    load_player_stats,
    load_monsters_data, load_deities_data, load_spells_data,
    load_archetype_data, load_pulp_talents_data, load_madness_insane_talent_data,
    load_manias_data, load_phobias_data, load_poisons_data, load_skills_data,
    load_inventions_data, load_years_data, load_occupations_data,
    _load_json_file, INFODATA_FOLDER
)

render_bp = Blueprint('render', __name__, url_prefix='/render')


@render_bp.route('/character/<guild_id>/<user_id>')
async def render_character_view(guild_id, user_id):
    # This endpoint is intended for local bot use
    stats = await load_player_stats()

    guild_data = stats.get(str(guild_id))
    if not guild_data:
        return "Guild not found", 404

    char_data = guild_data.get(str(user_id))
    if not char_data:
        return "Character not found", 404

    return await render_template(
        'render_character.html',
        char=char_data,
        emojis=emojis,
        emoji_lib=emoji
    )

@render_bp.route('/karma/<guild_id>/<user_id>')
async def render_karma_notification(guild_id, user_id):
    # Fetch User data
    username = "Unknown User"
    avatar_url = "https://cdn.discordapp.com/embed/avatars/0.png"

    if app.bot:
        try:
            guild = app.bot.get_guild(int(guild_id))
            if guild:
                member = guild.get_member(int(user_id))
                if not member:
                    # Try fetching user if not in cache (though member implies in guild)
                    try:
                         member = await guild.fetch_member(int(user_id))
                    except:
                         pass

                if member:
                    username = member.display_name
                    if member.display_avatar:
                        avatar_url = str(member.display_avatar.url)
        except Exception as e:
            print(f"Error fetching user for karma render: {e}")

    rank_name = request.args.get('rank', 'New Rank')
    change_type = request.args.get('type', 'up')

    return await render_template(
        'karma_notification.html',
        username=username,
        avatar_url=avatar_url,
        rank_name=rank_name,
        change_type=change_type
    )

@render_bp.route('/monster')
async def render_monster_view():
    name = request.args.get('name')
    style = request.args.get('style')
    if not name:
        return "Missing name parameter", 400

    data = await load_monsters_data()
    monsters = data.get('monsters', [])

    # Find monster
    target = None
    name_lower = name.lower()

    for item in monsters:
        m = item.get('monster_entry')
        if m and m.get('name', '').lower() == name_lower:
            target = m
            break

    if not target:
        return f"Monster '{escape(name)}' not found", 404

    image_url = get_image_url("monster", target['name'])
    template = 'render_monster_origin.html' if style == 'origin' else 'render_monster.html'
    return await render_template(template, monster=target, emojis=emojis, emoji_lib=emoji, image_url=image_url)

@render_bp.route('/deity')
async def render_deity_view():
    name = request.args.get('name')
    style = request.args.get('style')
    if not name:
        return "Missing name parameter", 400

    data = await load_deities_data()
    deities = data.get('deities', [])

    # Find deity
    target = None
    name_lower = name.lower()

    for item in deities:
        d = item.get('deity_entry')
        if d and d.get('name', '').lower() == name_lower:
            target = d
            break

    if not target:
        return f"Deity '{escape(name)}' not found", 404

    image_url = get_image_url("deity", target['name'])
    template = 'render_deity_origin.html' if style == 'origin' else 'render_deity.html'
    return await render_template(template, deity=target, emojis=emojis, emoji_lib=emoji, image_url=image_url)

@render_bp.route('/spell')
async def render_spell_view():
    name = request.args.get('name')
    style = request.args.get('style')
    if not name:
        return "Missing name parameter", 400

    data = await load_spells_data()
    spells = data.get('spells', [])

    # Find spell
    target = None
    name_lower = name.lower()

    for item in spells:
        s = item.get('spell_entry')
        if s and s.get('name', '').lower() == name_lower:
            target = s
            break

    if not target:
        return f"Spell '{escape(name)}' not found", 404

    image_url = get_image_url("spell", target['name'])
    template = 'render_spell_origin.html' if style == 'origin' else 'render_spell.html'
    return await render_template(template, spell=target, emojis=emojis, emoji_lib=emoji, image_url=image_url)

@render_bp.route('/weapon')
async def render_weapon_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await _load_json_file(INFODATA_FOLDER, 'weapons.json')

    # Find weapon (case-insensitive lookup in dict keys)
    target_key = None
    name_lower = name.lower()

    for key in data.keys():
        if key.lower() == name_lower:
            target_key = key
            break

    if not target_key:
        return f"Weapon '{escape(name)}' not found", 404

    weapon = data[target_key]
    image_url = get_image_url("weapon", target_key)
    return await render_template('render_weapon.html', weapon=weapon, weapon_name=target_key, image_url=image_url)

# --- New Render Routes ---

@render_bp.route('/archetype')
async def render_archetype_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_archetype_data()
    # Archetype data is Dict[Name, Info]

    target_key = None
    name_lower = name.lower()

    for key in data.keys():
        if key.lower() == name_lower:
            target_key = key
            break

    if not target_key:
        return f"Archetype '{escape(name)}' not found", 404

    # Process emojis
    archetype = data[target_key]
    if 'description' in archetype:
        archetype['description'] = emoji.emojize(archetype['description'], language='alias')
    if 'adjustments' in archetype:
        archetype['adjustments'] = [emoji.emojize(adj, language='alias') for adj in archetype['adjustments']]

    image_url = get_image_url("archetype", target_key)
    return await render_template('render_archetype.html', archetype=archetype, name=target_key, emojis=emojis, emoji_lib=emoji, image_url=image_url)

@render_bp.route('/pulp_talent')
async def render_pulp_talent_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_pulp_talents_data()
    # Dict[Category, List[String]]

    target_talent = None
    name_lower = name.lower()

    for category, talents in data.items():
        for t_str in talents:
            # Parse "**Name**: Desc"
            match = re.match(r'\*\*(.*?)\*\*:\s*(.*)', t_str)
            if match:
                t_name = match.group(1)
                t_desc = match.group(2)
                if t_name.lower() == name_lower:
                    target_talent = {
                        "name": t_name,
                        "description": t_desc,
                        "category": category
                    }
                    break
        if target_talent:
            break

    if not target_talent:
        return f"Talent '{escape(name)}' not found", 404

    image_url = get_image_url("pulp_talent", target_talent['name'])
    return await render_template('render_pulp_talent.html', talent=target_talent, emojis=emojis, emoji_lib=emoji, image_url=image_url)

@render_bp.route('/insane_talent')
async def render_insane_talent_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_madness_insane_talent_data()

    target_key = None
    name_lower = name.lower()
    for key in data.keys():
        if key.lower() == name_lower:
            target_key = key
            break

    if not target_key:
        return f"Insane Talent '{escape(name)}' not found", 404

    image_url = get_image_url("insane_talent", target_key)
    return await render_template('render_simple_entry.html', title=target_key, description=data[target_key], type="Insane Talent", emojis=emojis, emoji_lib=emoji, image_url=image_url)

@render_bp.route('/mania')
async def render_mania_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_manias_data()

    target_key = None
    name_lower = name.lower()
    for key in data.keys():
        if key.lower() == name_lower:
            target_key = key
            break

    if not target_key:
        return f"Mania '{escape(name)}' not found", 404

    image_url = get_image_url("mania", target_key)
    return await render_template('render_simple_entry.html', title=target_key, description=data[target_key], type="Mania", emojis=emojis, emoji_lib=emoji, image_url=image_url)

@render_bp.route('/phobia')
async def render_phobia_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_phobias_data()

    target_key = None
    name_lower = name.lower()
    for key in data.keys():
        if key.lower() == name_lower:
            target_key = key
            break

    if not target_key:
        return f"Phobia '{escape(name)}' not found", 404

    image_url = get_image_url("phobia", target_key)
    return await render_template('render_simple_entry.html', title=target_key, description=data[target_key], type="Phobia", emojis=emojis, emoji_lib=emoji, image_url=image_url)

@render_bp.route('/poison')
async def render_poison_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_poisons_data()

    target_key = None
    name_lower = name.lower()
    for key in data.keys():
        if key.lower() == name_lower:
            target_key = key
            break

    if not target_key:
        return f"Poison '{escape(name)}' not found", 404

    image_url = get_image_url("poison", target_key)
    return await render_template('render_poison.html', title=target_key, poison=data[target_key], type="Poison", emojis=emojis, emoji_lib=emoji, image_url=image_url)

@render_bp.route('/skill')
async def render_skill_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_skills_data()

    target_key = None
    name_lower = name.lower()
    for key in data.keys():
        if key.lower() == name_lower:
            target_key = key
            break

    if not target_key:
        return f"Skill '{escape(name)}' not found", 404

    image_url = get_image_url("skill", target_key)
    return await render_template('render_simple_entry.html', title=target_key, description=data[target_key], type="Skill", emojis=emojis, emoji_lib=emoji, image_url=image_url)

@render_bp.route('/invention')
async def render_invention_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_inventions_data()

    target_key = None
    name_lower = name.lower()
    # Inventions keys are decades (e.g. "1920s")
    for key in data.keys():
        if key.lower() == name_lower:
            target_key = key
            break

    if not target_key:
        return f"Invention decade '{escape(name)}' not found", 404

    image_url = get_image_url("invention", target_key)
    return await render_template('render_timeline.html', title=target_key, events=data[target_key], type="Inventions", emojis=emojis, emoji_lib=emoji, image_url=image_url)

@render_bp.route('/year')
async def render_year_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_years_data()

    target_key = None
    name_lower = name.lower()
    # Keys are years (e.g. "1920")
    for key in data.keys():
        if key.lower() == name_lower:
            target_key = key
            break

    if not target_key:
        return f"Year '{escape(name)}' not found", 404

    image_url = get_image_url("year", target_key)
    return await render_template('render_timeline.html', title=target_key, events=data[target_key], type="Timeline", emojis=emojis, emoji_lib=emoji, image_url=image_url)

@render_bp.route('/occupation')
async def render_occupation_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_occupations_data()

    target_key = None
    name_lower = name.lower()

    for key in data.keys():
        if key.lower() == name_lower:
            target_key = key
            break

    if not target_key:
        return f"Occupation '{escape(name)}' not found", 404

    image_url = get_image_url("occupation", target_key)
    return await render_template('render_occupation.html', occupation=data[target_key], name=target_key, image_url=image_url)


def text_to_morse(text):
    if not text: return ""
    text = text.upper()
    morse_output = []

    for char in text:
        if char in ['.', '!', '?', '\n']: # Sentence Terminator
             # If previous token was // (word break), replace with ///
             if morse_output and morse_output[-1] == '//':
                 morse_output[-1] = '///'
             elif not morse_output or morse_output[-1] != '///':
                 morse_output.append('///')
        elif char.isspace(): # Word Terminator
             # Only add word break if previous token wasn't a break
             if morse_output and morse_output[-1] not in ['//', '///']:
                 morse_output.append('//')
        elif char in MORSE_CODE_MAP: # Letter
             # If previous token was a letter (not a break), add letter separator /
             if morse_output and morse_output[-1] not in ['//', '///']:
                 morse_output.append('/')
             morse_output.append(MORSE_CODE_MAP[char])

    return "".join(morse_output)

@render_bp.route('/morse')
async def render_morse_view():
    text = request.args.get('text', 'SOS')
    font = request.args.get('font', 'default')

    font_filename = None
    if font and font != 'default':
        safe_font = sanitize_filename(font)
        for ext in ['.ttf', '.otf', '.woff', '.woff2']:
             if os.path.exists(os.path.join(FONTS_FOLDER, safe_font + ext)):
                 font_filename = safe_font + ext
                 break
             if os.path.exists(os.path.join(FONTS_FOLDER, safe_font)):
                 font_filename = safe_font
                 break

    morse_text = text_to_morse(text)

    return await render_template(
        'render_morse.html',
        text=morse_text,
        font_filename=font_filename
    )

@render_bp.route('/newspaper')
async def render_newspaper_view():
    headline = request.args.get('headline', 'Extra! Extra!')
    body = request.args.get('body', 'No content provided.')
    date = request.args.get('date', 'October 24, 1929')
    city = request.args.get('city', 'Arkham')
    name = request.args.get('name', 'The Arkham Advertiser')
    width = request.args.get('width', '500')
    clip_path = request.args.get('clip_path', '0% 0%, 100% 0%, 100% 100%, 0% 100%')

    return await render_template(
        'render_newspaper.html',
        headline=headline,
        body=body,
        date=date,
        city=city,
        name=name,
        width=width,
        clip_path=clip_path
    )

@render_bp.route('/telegram')
async def render_telegram_view():
    body = request.args.get('body', 'STOP')
    date = request.args.get('date', 'OCT 24 1929')
    origin = request.args.get('origin', 'ARKHAM')
    recipient = request.args.get('recipient', 'INVESTIGATOR')
    sender = request.args.get('sender', 'UNKNOWN')

    return await render_template(
        'render_telegram.html',
        body=body,
        date=date,
        origin=origin,
        recipient=recipient,
        sender=sender
    )

@render_bp.route('/letter')
async def render_letter_view():
    body = request.args.get('body', 'Dearest Friend...')
    date = request.args.get('date', 'October 24, 1929')
    salutation = request.args.get('salutation', 'To whom it may concern,')
    signature = request.args.get('signature', 'Sincerely, Unknown')

    return await render_template(
        'render_letter.html',
        body=body,
        date=date,
        salutation=salutation,
        signature=signature
    )

@render_bp.route('/script')
async def render_script_view():
    text = request.args.get('text', 'Ph\'nglui mglw\'nafh Cthulhu R\'lyeh wgah\'nagl fhtagn')
    font = request.args.get('font', 'default') # Font filename or key

    # Verify font exists in FONTS_FOLDER
    font_filename = None
    if font != 'default':
        safe_font = sanitize_filename(font)
        # Check extensions
        for ext in ['.ttf', '.otf', '.woff', '.woff2']:
             if os.path.exists(os.path.join(FONTS_FOLDER, safe_font + ext)):
                 font_filename = safe_font + ext
                 break
             # Also check if exact filename passed
             if os.path.exists(os.path.join(FONTS_FOLDER, safe_font)):
                 font_filename = safe_font
                 break

    return await render_template(
        'render_script.html',
        text=text,
        font_filename=font_filename,
        font_name=font if font_filename else 'Default'
    )
