from commands._newinvestigator_data import ERA_SKILLS, BASE_SKILLS

EXPECTED_ERAS = {
    "1920s Era", "1930s Era", "Modern Era",
    "Cthulhu by Gaslight", "Down Darker Trails", "Dark Ages",
}


def test_all_expected_eras_present():
    assert set(ERA_SKILLS.keys()) == EXPECTED_ERAS


def test_base_skills_is_alias_for_1920s_era():
    assert BASE_SKILLS == ERA_SKILLS["1920s Era"]
    assert BASE_SKILLS is ERA_SKILLS["1920s Era"]


def test_every_era_skill_map_has_string_keys_and_int_values_in_range():
    for era_name, skills in ERA_SKILLS.items():
        assert isinstance(skills, dict) and skills, f"{era_name} has no skills"
        for skill_name, base_value in skills.items():
            assert isinstance(skill_name, str) and skill_name
            assert isinstance(base_value, int), f"{era_name}.{skill_name} base value is not an int"
            assert 0 <= base_value <= 99, f"{era_name}.{skill_name} base value {base_value} out of range"


def test_every_era_defines_core_universal_skills():
    # "Credit Rating" is deliberately excluded here: Dark Ages (a medieval-era
    # sourcebook variant) has no Credit Rating skill, using "Status" instead --
    # this is intentional game-content design, not an omission.
    universal_skills = {"Dodge", "Cthulhu Mythos", "Fighting (Brawl)", "First Aid", "Stealth"}
    for era_name, skills in ERA_SKILLS.items():
        missing = universal_skills - skills.keys()
        assert not missing, f"{era_name} is missing universal skills: {missing}"


def test_cthulhu_mythos_and_dodge_base_at_zero_in_every_era():
    for era_name, skills in ERA_SKILLS.items():
        assert skills["Cthulhu Mythos"] == 0, f"{era_name}.Cthulhu Mythos should base at 0"
        assert skills["Dodge"] == 0, f"{era_name}.Dodge should base at 0"
