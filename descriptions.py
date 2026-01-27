def get_description(name, value):
  descriptions = {
    'STR': {
        0: "Enfeebled: unable to even stand up or lift a cup of tea.",
        15: "Puny, weak.",
        50: "Average human strength.",
        90: "One of the strongest people you’ve ever met.",
        99: "World-class (Olympic weightlifter). Human maximum.",
        140: "Beyond human strength (gorilla or horse).",
    },
    'CON': {
        0: "Dead.",
        1: "Sickly, prone to prolonged illness and probably unable to operate without assistance.",
        15: "Weak health, prone to bouts of ill health, great propensity for feeling pain.",
        50: "Average healthy human.",
        90: "Shrugs off colds, hardy and hale.",
        99: "Iron constitution, able to withstand great amounts of pain. Human maximum.",
        140: "Beyond human constitution (e.g. elephant).",
    },
    'DEX': {
        0: "Unable to move without assistance.",
        15: "Slow, clumsy with poor motor skills for fine manipulation.",
        50: "Average human dexterity.",
        90: "Fast, nimble and able to perform feats of fine manipulation (e.g. acrobat, great dancer).",
        99: "World-class athlete (e.g. Olympic standard). Human maximum.",
        120: "Beyond human dexterity (e.g. tiger).",
    },
    'APP': {
        0: "So unsightly that others are affected by fear, revulsion, or pity.",
        15: "Ugly, possibly disfigured due to injury or at birth.",
        50: "Average human appearance.",
        90: "One of the most charming people you could meet, natural magnetism.",
        99: "The height of glamour and cool (supermodel or world-renowned film star). Human maximum.",
    },
    'SIZ': {
        1: "A baby (1 to 12 pounds).",
        15: "Child, very short in stature (dwarf) (33 pounds / 15 kg).",
        65: "Average human size (moderate height and weight) (170 pounds / 75 kg).",
        80: "Very tall, strongly built, or obese. (240 pounds / 110 kg).",
        99: "Oversize in some respect (330 pounds / 150 kg).",
        150: "Horse or cow (960 pounds / 436 kg).",
        180: "Heaviest human ever recorded (1400 pounds / 634 kg).",
    },
    'INT': {
        0: "No intellect, unable to comprehend the world around them.",
        15: "Slow learner, able to undertake only the most basic math, or read beginner-level books.",
        50: "Average human intellect.",
        90: "Quick-witted, probably able to comprehend multiple languages or theorems.",
        99: "Genius (Einstein, Da Vinci, Tesla, etc.). Human maximum.",
    },
    'POW': {
        0: "Enfeebled mind, no willpower or drive, no magical potential.",
        15: "Weak-willed, easily dominated by those with a greater intellect or willpower.",
        50: "Average human.",
        90: "Strong-willed, driven, a high potential to connect with the unseen and magical.",
        100: "Iron will, strong connection to the spiritual 'realm' or unseen world.",
        140: "Beyond human, possibly alien.",
    },
    'EDU': {
        0: "A newborn baby.",
        15: "Completely uneducated in every way.",
        60: "High school graduate.",
        70: "College graduate (Bachelor degree).",
        80: "Degree level graduate (Master's degree).",
        90: "Doctorate, professor.",
        96: "World-class authority in their field of study.",
        99: "Human maximum.",
    },
    'skill': {
        0: "Novice",
        6: "Neophyte",
        20: "Amateur",
        50: "Professional",
        75: "Expert",
        90: "Master",
    },
    'Credit Rating': {
        0: "Penniless",
        1: "Poor",
        10: "Average",
        50: "Wealthy",
        90: "Rich",
        99: "Super Rich",
    },
    'SAN': {
        0: "Insane, completely detached from reality.",
        15: "Severely disturbed, unable to distinguish between reality and delusion.",
        50: "Average human sanity.",
        80: "Strong mental resilience, able to cope with stress and horrors.",
        99: "Exceptional sanity, unshaken even by the most terrifying experiences. Human maximum.",
    }
  }
  if name in descriptions:
    descriptions = descriptions[name]
    nearest_value = min(descriptions.keys(), key=lambda x: abs(x - value))
    return descriptions[nearest_value]
  else:
    return "Invalid name"