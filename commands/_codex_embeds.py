import discord
import emojis
import emoji

FIELD_LIMIT = 1024
DESC_LIMIT = 4096


def _trunc(text: str, limit: int = FIELD_LIMIT) -> str:
    """Truncate to Discord embed limit."""
    text = str(text)
    return text if len(text) <= limit else text[:limit - 3] + "…"


def _join_trunc(lines: list[str], sep: str = "\n", limit: int = FIELD_LIMIT) -> str:
    """Join lines, stopping before the limit and appending '…and more'."""
    result = []
    total = 0
    for line in lines:
        needed = len(line) + (len(sep) if result else 0)
        if total + needed > limit - 20:
            result.append("*…and more*")
            break
        result.append(line)
        total += needed
    return sep.join(result)


def _add_image_field(embed, file):
    """Helper to attach an image file as a thumbnail to the embed."""
    if file:
        embed.set_thumbnail(url=f"attachment://{file.filename}")

def create_monster_embed(data, title, file=None):
    embed = discord.Embed(title=title, color=discord.Color.dark_green())
    _add_image_field(embed, file)

    monster = data.get('monster_entry', data) # Handle nested structure if present

    if monster.get('subtitle'):
        embed.description = f"*{monster['subtitle']}*"

    if monster.get('description'):
        embed.add_field(name="Description", value=_trunc(monster['description']), inline=False)

    # Characteristics
    chars = monster.get('characteristics', {})
    if chars:
        char_lines = []
        for key, val in chars.items():
            emoji_str = emoji.emojize(emojis.get_stat_emoji(key), language='alias')
            val_str = str(val)
            if isinstance(val, dict):
                 val_str = f"{val.get('average', '?')} ({val.get('roll', '')})"
            char_lines.append(f"{emoji_str} **{key}**: {val_str}")
        embed.add_field(name="Characteristics", value=_join_trunc(char_lines), inline=False)

    # Derived Stats
    derived = monster.get('derived_stats', {})
    if derived:
        stats_line = []
        for key, val in derived.items():
             label = key.replace('_', ' ').title()
             emoji_key = "Move" if key == "move" else "Build" if key == "build" else "DB" if key == "damage_bonus" else "HP" if key == "hit_points" else "MP" if key == "magic_points" else key
             emoji_str = emoji.emojize(emojis.get_stat_emoji(emoji_key), language='alias')

             val_str = str(val)
             if isinstance(val, dict): # Move logic
                 val_str = f"{val.get('base', '?')}"
                 if val.get('special'): val_str += f" ({val['special']})"

             stats_line.append(f"{emoji_str} **{label}**: {val_str}")
        embed.add_field(name="Derived Stats", value=_trunc(" | ".join(stats_line)), inline=False)

    # Combat
    combat = monster.get('combat', {})
    if combat:
        combat_desc = f"**Attacks per Round**: {combat.get('attacks_per_round', '1')}\n"
        if combat.get('damage_bonus'):
             combat_desc += f"**Damage Bonus**: {combat['damage_bonus']}\n"

        attacks = combat.get('attacks', [])
        if attacks:
            combat_desc += "\n**Attacks**:\n"
            for atk in attacks:
                atk_line = f"• **{atk.get('name', 'Attack')}** ({atk.get('success_chance', 'Auto')}%): {atk.get('damage', '?')}"
                if atk.get('special_effect'):
                    atk_line += f" *{atk['special_effect']}*"
                combat_desc += atk_line + "\n"

        dodge = combat.get('dodge')
        if dodge:
             combat_desc += f"\n**Dodge**: {dodge.get('success_chance', 'N/A')}%"

        embed.add_field(name="Combat", value=_trunc(combat_desc), inline=False)

    # Skills & Powers
    skills = monster.get('skills', [])
    if skills:
        try:
            if isinstance(skills, list) and skills and isinstance(skills[0], dict):
                skill_list = [f"{s.get('name', '?')} {s.get('value', '?')}%" for s in skills]
            elif isinstance(skills, dict):
                skill_list = [f"{k}: {v}" for k, v in skills.items()]
            else:
                skill_list = [str(s) for s in skills]
            embed.add_field(name="Skills", value=_trunc(", ".join(skill_list)), inline=False)
        except Exception:
            pass

    powers = monster.get('powers_and_abilities', [])
    if powers:
        try:
            power_lines = [f"**{p.get('name', '?')}**: {p.get('description', '')}" for p in powers if isinstance(p, dict)]
            if not power_lines:
                power_lines = [str(p) for p in powers]
            embed.add_field(name="Powers", value=_join_trunc(power_lines), inline=False)
        except Exception:
            pass

    # Defenses & Magic
    armor = monster.get('armor', {})
    if armor:
        armor_text = f"{armor.get('rating', 'None')}"
        if armor.get('modifiers'): armor_text += f" ({armor['modifiers']})"
        embed.add_field(name="Armor", value=armor_text, inline=True)

    spells = monster.get('spells')
    if spells:
        spells_str = spells if isinstance(spells, str) else ", ".join(str(s) for s in spells) if isinstance(spells, list) else str(spells)
        embed.add_field(name="Spells", value=_trunc(spells_str), inline=True)

    san = monster.get('sanity_loss')
    if san:
        embed.add_field(name="Sanity Loss", value=_trunc(str(san)), inline=True)

    return embed

def create_deity_embed(data, title, file=None):
    embed = discord.Embed(title=title, color=discord.Color.dark_red())
    _add_image_field(embed, file)

    deity = data.get('deity_entry', data)

    if deity.get('classification'):
        embed.description = f"*{deity['classification']}*"

    if deity.get('main_entry_text'):
        embed.add_field(name="Description", value=_trunc(deity['main_entry_text']), inline=False)

    if deity.get('description_quote'):
        embed.add_field(name="Quote", value=_trunc(f"*{deity['description_quote']}*"), inline=False)

    # Cult
    cult = deity.get('cult', {})
    if cult:
        cult_text = cult.get('text', '')
        if len(cult_text) > 500: cult_text = cult_text[:497] + "..."
        if cult_text:
             embed.add_field(name="Cult", value=cult_text, inline=False)

        blessings = cult.get('possible_blessings', [])
        if blessings:
            try:
                bless_lines = [f"**{b.get('name', '?')}**: {b.get('description', '')}" for b in blessings if isinstance(b, dict)]
                embed.add_field(name="Blessings", value=_join_trunc(bless_lines), inline=False)
            except Exception:
                pass

    # Encounters & Magic
    if deity.get('encounters'):
        embed.add_field(name="Encounters", value=_trunc(str(deity['encounters'])), inline=True)
    if deity.get('aura'):
        embed.add_field(name="Aura", value=_trunc(str(deity['aura'])), inline=True)

    magic = deity.get('magic', {})
    if magic:
        magic_line = f"**POW**: {magic.get('pow', 'N/A')} | **MP**: {magic.get('magic_points', 'N/A')}"
        if magic.get('spells'):
            magic_line += f"\n**Spells**: {magic['spells']}"
        embed.add_field(name="Magic", value=_trunc(magic_line), inline=False)

    if deity.get('sanity_loss'):
        embed.add_field(name="Sanity Loss", value=_trunc(str(deity['sanity_loss'])), inline=True)

    # Physical Manifestation
    pm = deity.get('physical_manifestation', {})
    if pm:
        pm_title = pm.get('title', 'Physical Manifestation')

        chars = pm.get('characteristics', {})
        if chars:
            char_lines = []
            for key, val in chars.items():
                emoji_str = emoji.emojize(emojis.get_stat_emoji(key), language='alias')
                char_lines.append(f"{emoji_str} **{key}**: {val}")
            embed.add_field(name=f"{pm_title} - Stats", value=_trunc(" | ".join(char_lines)), inline=False)

        combat = pm.get('combat', {})
        if combat:
            combat_text = ""
            if combat.get('description'): combat_text += f"{combat['description']}\n"
            combat_text += f"**Attacks**: {combat.get('attacks_per_round', 'N/A')}\n"
            for atk in combat.get('attacks', []):
                combat_text += f"• **{atk.get('name', 'Attack')}**: {atk.get('damage', '?')} ({atk.get('success_chance', '')})\n"
            embed.add_field(name="Combat", value=_trunc(combat_text), inline=False)

        armor = pm.get('armor', {})
        if armor:
            armor_text = f"**Rating**: {armor.get('rating', 'None')}\n{armor.get('notes', '')}"
            embed.add_field(name="Armor", value=_trunc(armor_text), inline=True)

    return embed

def create_spell_embed(data, title, file=None):
    embed = discord.Embed(title=title, color=discord.Color.purple())
    _add_image_field(embed, file)

    spell = data.get('spell_entry', data)

    if spell.get('category'):
        embed.description = f"*{spell['category']}*"

    effect = spell.get('effect', {})
    if effect and effect.get('description'):
        embed.add_field(name="Effect", value=_trunc(effect['description']), inline=False)

    # Costs
    costs = spell.get('costs', {})
    cost_parts = []
    if costs.get('magic_points'): cost_parts.append(f"**MP**: {costs['magic_points']}")
    if costs.get('sanity'): cost_parts.append(f"**Sanity**: {costs['sanity']}")
    if spell.get('casting_time'): cost_parts.append(f"**Time**: {spell['casting_time']}")
    if spell.get('range'): cost_parts.append(f"**Range**: {spell['range']}")

    if cost_parts:
        embed.add_field(name="Costs & Casting", value=" | ".join(cost_parts), inline=False)

    if costs.get('components'):
        embed.add_field(name="Components", value=_trunc(str(costs['components'])), inline=False)

    if effect.get('damage'):
        embed.add_field(name="Damage", value=_trunc(str(effect['damage'])), inline=True)
    if effect.get('opposed_roll'):
        embed.add_field(name="Opposed Roll", value=_trunc(str(effect['opposed_roll'])), inline=True)

    if spell.get('deeper_magic'):
        embed.add_field(name="Deeper Magic", value=_trunc(spell['deeper_magic']), inline=False)

    return embed

def create_weapon_embed(data, title, file=None):
    embed = discord.Embed(title=title, color=discord.Color.dark_grey())
    _add_image_field(embed, file)

    # Weapon data structure is usually flat but might need adjustment
    # Looking at load_weapons_data, it returns a dict of key->dict
    weapon = data

    desc_parts = []
    if weapon.get('year'): desc_parts.append(f"Year: {weapon['year']}")
    if weapon.get('cost'): desc_parts.append(f"Cost: {weapon['cost']}")

    if desc_parts:
        embed.description = " | ".join(desc_parts)

    if weapon.get('description'):
        embed.add_field(name="Description", value=_trunc(weapon['description']), inline=False)

    stats = []
    if weapon.get('damage'): stats.append(f"**Damage**: {weapon['damage']}")
    if weapon.get('range'): stats.append(f"**Range**: {weapon['range']}")
    if weapon.get('capacity'): stats.append(f"**Capacity**: {weapon['capacity']}")
    if weapon.get('shots_per_round'): stats.append(f"**Shots/Round**: {weapon['shots_per_round']}")
    if weapon.get('malfunction'): stats.append(f"**Malfunction**: {weapon['malfunction']}")
    if weapon.get('skill'): stats.append(f"**Skill**: {weapon['skill']}")

    if stats:
        embed.add_field(name="Statistics", value="\n".join(stats), inline=False)

    return embed

def create_occupation_embed(data, title, file=None):
    embed = discord.Embed(title=title, color=discord.Color.blue())
    _add_image_field(embed, file)

    occ = data
    if occ.get('description'):
        embed.description = _trunc(occ['description'], DESC_LIMIT)

    if occ.get('skills'):
        skills = occ['skills']
        skills_str = ", ".join(skills) if isinstance(skills, list) else str(skills)
        embed.add_field(name="Skills", value=_trunc(skills_str), inline=False)

    if occ.get('credit_rating'):
        embed.add_field(name="Credit Rating", value=_trunc(str(occ['credit_rating'])), inline=True)

    if occ.get('suggested_contacts'):
        embed.add_field(name="Contacts", value=_trunc(str(occ['suggested_contacts'])), inline=True)

    return embed

def create_archetype_embed(data, title, file=None):
    embed = discord.Embed(title=title, color=discord.Color.gold())
    _add_image_field(embed, file)

    arch = data
    if arch.get('description'):
        embed.description = _trunc(emoji.emojize(arch['description'], language='alias'), DESC_LIMIT)

    if arch.get('adjustments'):
        adj_lines = [emoji.emojize(a, language='alias') for a in arch['adjustments']]
        embed.add_field(name="Adjustments", value=_join_trunc(adj_lines), inline=False)

    if arch.get('talents'):
        talents = arch['talents']
        talents_str = talents if isinstance(talents, str) else "\n".join(str(t) for t in talents) if isinstance(talents, list) else str(talents)
        embed.add_field(name="Talents", value=_trunc(talents_str), inline=False)

    return embed

def create_generic_embed(data, title, type_slug, file=None):
    embed = discord.Embed(title=title, color=discord.Color.dark_teal())
    _add_image_field(embed, file)

    description = ""

    # Handle simple description string
    if isinstance(data, str):
        description = data
    elif isinstance(data, dict):
        if 'description' in data:
            description = data['description']
        elif 'effect' in data:
            description = data['effect']
        else:
             # Try to format dict key-values
             for k, v in data.items():
                 if isinstance(v, (str, int, float)):
                     description += f"**{k.title()}**: {v}\n"

    if description:
        description = emoji.emojize(str(description), language='alias')
        embed.description = _trunc(description, DESC_LIMIT)

    return embed

def create_timeline_embed(data, title, type_slug, file=None):
    embed = discord.Embed(title=title, color=discord.Color.dark_blue())
    _add_image_field(embed, file)

    # Data is likely a list of dicts (events)
    if isinstance(data, list):
        events_text = ""
        for event in data:
            # Assume 'text' or 'event' key, or just string
            if isinstance(event, str):
                events_text += f"• {event}\n"
            elif isinstance(event, dict):
                 t = event.get('text', event.get('description', ''))
                 if t: events_text += f"• {t}\n"

        if len(events_text) > DESC_LIMIT:
            events_text = events_text[:DESC_LIMIT - 3] + "…"

        embed.description = events_text

    return embed
