import json

def update_skills():
    with open('infodata/weapons.json', 'r') as f:
        data = json.load(f)

    for name, details in data.items():
        if details.get("Skill") == "Firearms (Handgun)":
            details["Skill"] = "Pistol"
        elif details.get("Skill") == "Firearms (Rifle/Shotgun)":
            details["Skill"] = "Rifle/Shotgun"

    with open('infodata/weapons.json', 'w') as f:
        json.dump(data, f, indent=4)

if __name__ == "__main__":
    update_skills()
