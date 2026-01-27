import discord, random
from discord.ext import commands


class talents(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.command(aliases=["cTalents","tinfo"])
  async def talents(self, ctx, category: str = None):
      """
      `[p]cTalents` - Generate two random talents or get a list of talents. You can get list of tallent if you chose category (physical, mental, combat or miscellaneous) (e. g. `[p]cTalents mental`)
      """       
      physical_talents = ["**Keen Vision**: gain a bonus die to Spot Hidden rolls",
                          "**Quick Healer**: natural healing is increased to +3 hit points per day.",
                          "**Night Vision**: in darkness, reduce the difficulty level of Spot Hidden rolls and ignore penalty die for shooting in the dark.",
                          "**Endurance**: gain a bonus die when making CON rolls (including to determine MOV rate for chases)",
                          "**Power Lifter**: gain a bonus die when making STR rolls to lift objects or People.",
                          "**Iron Liver**: may spend 5 Luck to avoid the effects of drinking excessive amounts of alcohol (negating penalty applied to skill rolls).",
                          "**Stout Constitution**: may spend 10 Luck to reduce poison or disease damage and effects by half.",
                          "**Tough Guy**: soaks up damage, may spend 10 Luck points to shrug off up to 5 hit points worth of damage taken in one combat round.",
                          "**Keen Hearing**: gain a bonus die to Listen rolls",
                          "**Smooth Talker**: gain a bonus die to Charm rolls.",]
      
      mental_talents = ["**Hardened**: ignores Sanity point loss from attacking other humans, viewing horrific injuries, or deceased.",
                          "**Resilient**: may spend Luck points to shrug-off points of Sanity loss, on a one-for-one basis.",
                          "**Strong Willed**: gains a bonus die when making POW rolls",
                          "**Quick Study**: halve the time pərinbər for Initial and Full Reading JO Mythos tomes, as well as other books.",
                          "**Linguist**: able to determine what language is being spoken (or what is written); gains a bonus die to Language rolls.",
                          "**Arcane Insight**: halve the time required to learn spells and gains bonus die to spell casting rolls.",
                          "**Photographic Memory**: can remember many details, gains a bonus die when making Know rolls.",
                          "**Lore**: has knowledge of a lore specialization skill (e.g. Dream Lore, Vampire Lore, Werewolf Lore, etc.). Note that occupational and/or personal interest skill points should be invested in this skill.",
                          "**Psychic Power**: may choose one psychic power (Clairvoyance, Divination, Medium, Psychometry, or Telekinesis). Note that occupational and/or personal interest skill points should be invested in this skill.",
                          "**Sharp Witted**: able to collate facts quickly; gain a bonus die when making Intelligence (but not Idea) rolls.",]
      
      combat_talents = ["**Alert**: never surprised in combat.",
                          "**Heavy Hitter**: may spend 10 Luck points to add an additional damage die when dealing out melee combat (die type depends on the weapon being used, e.g. 1D3 for unarmed combat, 1D6 for a sword, etc.)",
                          "**Fast Load**: choose a Firearm specialism; ignore penalty die for loading and frring in the same round.",
                          "**Nimble**: does not lose next action when \"diving for cover\" versus firearms.",
                          "**Beady Eye**: does not suffer penalty die when \"aiming\" at a small target (Build -2), and may also fire into melee without a penalty die.",
                          "**Outmaneuver**: character is considered to have one point higher Build when initiating a combat maneuver (e.g. Build 1 becomes Build 2 when comparing their hero to the target in a maneuver, reducing the likelihood of suffering a penalty on their Fighting roll).",
                          "**Rapid Attack**: may spend 10 Luck points to gain one further melee attack in a single combat round.",
                          "**Fleet Footed**: may spend 10 Luck to avoid being \"outnumbered\" in melee combat for one combat encounter.",
                          "**Quick Draw**: does not need to have their firearm \"readied\" to gain +50 DEX when determining position in the DEX order for combat.",
                          "**Rapid Fire**: ignores penalty die for multiple handgun shots.",]
      
      miscellaneous_talents = ["**Scary**: reduces difficulty by one level or gains bonus die (at the Keeper's discretion) to Intimidate rolls.",
                          "**Gadget**: starts game with one weird science gadget.",
                          "**Lucky**: regains an additional +1 D10 Luck points when Luck Recovery rolls are made.",
                          "**Mythos Knowledge**: begins the game with a Cthulhu Mythos Skill of 10 points",
                          "**Weird Science**: may build and repair weird science devices.",
                          "**Shadow**: reduces difficulty by one level or gains bonus die (at the Keeper's discretion) to Stealth rolls and if currently unseen is able to make two surprise attacks before their location is discovered.",
                          "**Handy**: reduces difficulty by one level or gains bonus die (at the Keeper's discretion) when making Electrical Repair, Mechanical Repair, and Operate Heavy Machinery rolls.",
                          "**Animal Companion**: starts game with a faithful animal companion (e.g. dog, cat, parrot) and gains a bonus die when making Animal Handling rolls.",
                          "**Master of Disguise**: may spend 10 Luck points to gain a bonus die to Disguise or Art/Craft (Acting) rolls; includes ventriloquism (able to throw voice over long distances so it appears that the sound is emanating from somewhere other than the hero). Note that if someone is trying to detect the disguise their Spot Hidden or Psychology roll's difficulty is raised to Hard.",
                          "**Resourceful**: always seems to have what they need to hand; may spend 10 Luck points (rather than make Luck roll) to find a certain useful piece of equipment (e.g. a flashlight, length of rope, a weapon etc.) in their current location.",]

      if not category:
          # Pokud hráč neposkytne žádnou kategorii, vrátíme dvě náhodné položky.
          selected_talents = random.sample(physical_talents + mental_talents + combat_talents + miscellaneous_talents, 2)
          category = "Random Talents"
      else:
          # Jinak vybereme položky z dané kategorie.
          category = category.lower()
          if category == "physical":
              selected_talents = physical_talents
              category = "Physical Talents"
          elif category == "mental":
              selected_talents = mental_talents
              category = "Mental Talents"
          elif category == "combat":
              selected_talents = combat_talents
              category = "Combat Talents"
          elif category == "miscellaneous":
              selected_talents = miscellaneous_talents
              category = "Miscellaneous Talents"
          else:
              await ctx.send("Invalid category. Available categories: Physical, Mental, Combat, Miscellaneous")
              return

      # Nyní můžeme sestavit výstupní embed.
      embed = discord.Embed(title=f"{category}", color=discord.Color.blue())
      for index, talent in enumerate(selected_talents, 1):
          embed.add_field(name=f"Talent {index}", value=talent, inline=False)

      await ctx.send(embed=embed)


async def setup(bot):
  await bot.add_cog(talents(bot))
