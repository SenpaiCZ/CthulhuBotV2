from emojis import stat_emojis, get_stat_emoji, get_emoji_for_item, get_health_bar
from occupation_emoji import occupation_emojis, get_occupation_emoji

print("--- Testing Stat Emojis ---")
print(f"STR: {stat_emojis['STR']} (expected 💪)")
print(f"Archaeology: {stat_emojis['Archaeology']} (expected ⛏️)")
print(f"Arabic: {stat_emojis['Arabic']} (expected 🇦🇪)")
print(f"Age: {stat_emojis['Age']} (expected 🎂)")

print("\n--- Testing get_stat_emoji (Specialization) ---")
print(f"Science (Biology): {get_stat_emoji('Science (Biology)')} (expected 🔬)")
print(f"Fighting (Brawl): {get_stat_emoji('Fighting (Brawl)')} (expected 🥊)")

print("\n--- Testing Item Keywords ---")
print(f"Amulet: {get_emoji_for_item('Ancient Amulet')} (expected 🧿)")
print(f"Machine Gun: {get_emoji_for_item('Tommy Gun Machine Gun')} (expected 🔫)")
print(f"Unknown: {get_emoji_for_item('Random Stuff')} (expected 📦)")

print("\n--- Testing Health Bar ---")
print(f"Full Health: {get_health_bar(10, 10)}")
print(f"Low Health (2/10): {get_health_bar(2, 10)}")

print("\n--- Testing Occupation Emojis ---")
print(f"Accountant: {occupation_emojis['Accountant']} (expected 🧮)")
print(f"Acrobat: {get_occupation_emoji('Acrobat')} (expected 🤸)")
print(f"Unknown: {get_occupation_emoji('Ghost Buster')} (expected ❓)")

print("\n--- Testing items() and len() ---")
print(f"Total Stat Emojis: {len(stat_emojis)}")
print(f"Total Occupation Emojis: {len(occupation_emojis)}")
print(f"First 5 Occupation items: {occupation_emojis.items()[:5]}")
