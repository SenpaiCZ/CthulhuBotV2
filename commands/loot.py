import discord, random
from discord.ext import commands


class loot(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.hybrid_command(name="loot", aliases=["randomLoot", "randomloot", "rloot"], description="Generate random loot from 1920s.")
  async def loot(self, ctx):
    """
    `[p]loot` - Generate random loot from 1920s. 25% chance of finding $0.1-$5. This will not be saved.
    """
    items = [
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
    # Pravděpodobnost 25% na získání peněz
    has_money = random.choice([True, False, False, False])
    money = None
    if has_money:
      money = random.randint(1, 500) / 100  # Peníze od 0.01 do 10.00

    # Náhodně vyber počet předmětů od 1 do 7
    num_items = random.randint(1, 5)
    # Náhodně vyber předměty
    chosen_items = random.sample(items, num_items)

    # Vytvoření embedu
    embed = discord.Embed(title="Random Loot", color=discord.Color.blue())
    for item in chosen_items:
      emoji = "\U0001F4E6"  # Emoji pro věc
      embed.add_field(name=f"{emoji} {item}", value='\u200b',
                      inline=False)  # '\u200b' je prázdný znak

    if money is not None:
      emoji_money = "\U0001F4B5"  # Emoji pro peníze
      embed.add_field(name=f"{emoji_money} Money",
                      value=f"${money:.2f}",
                      inline=False)

    ephemeral = False
    if ctx.interaction:
        ephemeral = True

    await ctx.send(embed=embed, ephemeral=ephemeral)


async def setup(bot):
  await bot.add_cog(loot(bot))
