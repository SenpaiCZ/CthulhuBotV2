import os
import emoji
import emojis
from quart import Blueprint, render_template

from loadnsave import (
    load_archetype_data, load_pulp_talents_data, load_madness_insane_talent_data,
    load_manias_data, load_phobias_data, load_poisons_data, load_skills_data,
    load_inventions_data, load_years_data, load_occupations_data,
    _load_json_file, INFODATA_FOLDER
)

grimoire_bp = Blueprint('grimoire', __name__)


@grimoire_bp.route('/grimoire/')
@grimoire_bp.route('/grimoire')
async def grimoire_hub():
    return await render_template('index.html', scroll_to="grimoire")

@grimoire_bp.route('/monsters')
async def admin_monsters():
    monsters_data = await _load_json_file(INFODATA_FOLDER, 'monsters.json')
    stat_emojis = emojis.web_symbols
    return await render_template('monsters.html', data=monsters_data, stat_emojis=stat_emojis, type_slug="monster")

@grimoire_bp.route('/deities')
async def admin_deities():
    deities_data = await _load_json_file(INFODATA_FOLDER, 'deities.json')
    stat_emojis = emojis.web_symbols
    return await render_template('deities.html', data=deities_data, stat_emojis=stat_emojis, type_slug="deity")

@grimoire_bp.route('/spells')
async def admin_spells():
    spells_data = await _load_json_file(INFODATA_FOLDER, 'spells.json')
    stat_emojis = emojis.web_symbols
    return await render_template('spells.html', data=spells_data, stat_emojis=stat_emojis, type_slug="spell")

@grimoire_bp.route('/weapons')
async def admin_weapons():
    weapons_data = await _load_json_file(INFODATA_FOLDER, 'weapons.json')
    if not weapons_data:
        print(f"Warning: Weapons data is empty or file not found. Path: {os.path.join(INFODATA_FOLDER, 'weapons.json')} CWD: {os.getcwd()}")
    return await render_template('weapons.html', data=weapons_data, type_slug="weapon")

# --- New Admin Views ---

@grimoire_bp.route('/archetypes')
async def admin_archetypes():
    data = await load_archetype_data()
    # Process emojis in descriptions and adjustments
    for key, archetype in data.items():
        if 'description' in archetype:
            archetype['description'] = emoji.emojize(archetype['description'], language='alias')
        if 'adjustments' in archetype:
            archetype['adjustments'] = [emoji.emojize(adj, language='alias') for adj in archetype['adjustments']]
    return await render_template('archetypes.html', data=data, type_slug="archetype")

@grimoire_bp.route('/pulp_talents')
async def admin_pulp_talents():
    data = await load_pulp_talents_data()
    return await render_template('pulp_talents.html', data=data, type_slug="pulp_talent")

@grimoire_bp.route('/insane_talents')
async def admin_insane_talents():
    data = await load_madness_insane_talent_data()
    return await render_template('generic_list.html', data=data, title="Insane Talents", type_slug="insane_talent")

@grimoire_bp.route('/manias')
async def admin_manias():
    data = await load_manias_data()
    return await render_template('generic_list.html', data=data, title="Manias", type_slug="mania")

@grimoire_bp.route('/phobias')
async def admin_phobias():
    data = await load_phobias_data()
    return await render_template('generic_list.html', data=data, title="Phobias", type_slug="phobia")

@grimoire_bp.route('/poisons')
async def admin_poisons():
    data = await load_poisons_data()
    return await render_template('poisons.html', data=data, title="Poisons", type_slug="poison")

@grimoire_bp.route('/skills')
async def admin_skills():
    data = await load_skills_data()
    # Process emojis in descriptions
    processed_data = {}
    for key, description in data.items():
        processed_data[key] = emoji.emojize(description, language='alias')
    return await render_template('generic_list.html', data=processed_data, title="Skills", type_slug="skill")

@grimoire_bp.route('/inventions')
async def admin_inventions():
    data = await load_inventions_data()
    return await render_template('timeline_list.html', data=data, title="Inventions", type_slug="invention")

@grimoire_bp.route('/years')
async def admin_years():
    data = await load_years_data()
    return await render_template('timeline_list.html', data=data, title="Years Timeline", type_slug="year")

@grimoire_bp.route('/occupations')
async def admin_occupations():
    data = await load_occupations_data()
    return await render_template('occupations.html', data=data, type_slug="occupation")
