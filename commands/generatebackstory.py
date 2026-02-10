import discord, random
from discord.ext import commands
from discord import app_commands


class generatebackstory(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @commands.hybrid_command(aliases=["gbackstory"], description="Generate random backstory for your investigator.")
  async def generatebackstory(self, ctx):
      """
      `[p]gbackstory` - Generate random backstory for your investigator. This will not be saved.
      """
      personal_descriptions = [
          "Adventurous", "Athletic", "Awkward", "Baby-faced", "Bookish", "Brawny", "Charming",
          "Cheerful", "Dainty", "Dazzling", "Delicate", "Dirty", "Determined", "Dull", "Elegant",
          "Ethereal", "Exquisite", "Frail", "Gawky", "Glamorous", "Gentle", "Groomed", "Handsome",
          "Hairy", "Ingenious", "Jovial", "Mousy", "Muscular", "Mysterious", "Ordinary", "Pale",
          "Plump", "Pretty", "Resilient", "Robust", "Rosy", "Rugged", "Scruffy", "Sharp", "Slim",
          "Sloppy", "Smart", "Sophisticated", "Stoic", "Stocky", "Strapping", "Sturdy", "Sullen",
          "Tanned", "Untidy", "Ungainly", "Weary", "Wrinkled", "Youthful"
      ]


      
      personal_description_text = ""
      for description in personal_descriptions:
          personal_description_text += f"{description}, "
  
      ideology_beliefs = [
          "You devoutly follow a higher power and engage in regular worship and prayer (e.g. Vishnu, Jesus Christ, Haile Selassie I).",
          "You firmly believe that mankind can thrive without the influence of religions, embracing atheism, humanism, or secularism.",
          "You are a dedicated follower of science, putting your faith in its ability to provide answers. Choose a specific scientific area of interest (e.g. evolution, cryogenics, space exploration).",
          "You hold a strong belief in fate, whether through concepts like karma, class systems, or superstitions.",
          "You are a member of a society or secret organization, such as the Freemasons, Women's Institute, or Anonymous.",
          "You are deeply convinced that there is inherent evil in society that needs to be eradicated. Identify this societal evil (e.g. drugs, violence, racism).",
          "You are deeply involved in the occult, exploring practices like astrology, spiritualism, or tarot card readings.",
          "Your ideology revolves around politics, and you align yourself with conservative, socialist, or liberal principles.",
          "You firmly believe in the adage that \"money is power,\" and you are determined to accumulate as much wealth as possible, often seen as greedy, enterprising, or ruthless.",
          "You are a passionate campaigner or activist, advocating for causes such as feminism, gay rights, or union power.",
          "You are a staunch environmentalist, deeply concerned about the state of the planet and dedicated to conservation efforts.",
          "You are a pacifist, opposing all forms of violence and promoting peaceful conflict resolution.",
          "You are a staunch traditionalist, valuing long-standing customs and practices over modern innovations.",
          "You are a technology enthusiast, believing that advancements in science and technology hold the key to a better future.",
          "You are a hedonist, seeking pleasure and enjoyment above all else and often indulging in various vices.",
          "You are an advocate for social justice, fighting against discrimination, inequality, and injustice in society.",
      ]

      selected_ideology_beliefs = random.choice(ideology_beliefs)
  
      significant_people_first = [
          "Your mentor (e.g. a wise old wizard, a seasoned warrior).",
          "A childhood bully who made your life miserable (e.g. schoolyard tormentor, neighborhood tough).",
          "A long-lost relative who suddenly reappeared in your life (e.g. estranged cousin, mysterious uncle).",
          "A professional rival who constantly challenges you (e.g. a competing journalist, a rival scientist).",
          "A loyal pet or animal companion that has been with you through thick and thin (e.g. a faithful dog, a wise owl).",
          "A spiritual leader or guru who has profoundly influenced your beliefs (e.g. a wise monk, a New Age mystic).",
          "A former business partner who betrayed you (e.g. a scheming colleague, a duplicitous friend).",
          "A supernatural being or entity that haunts your dreams and visions (e.g. a vengeful ghost, an enigmatic cosmic entity).",
          "A mysterious informant who provides you with cryptic clues and valuable information (e.g. a cryptic letter writer, an anonymous hacker).",
          "A celebrity you once crossed paths with, leaving a lasting impression (e.g. a chance encounter with a famous actor, a brief conversation with a renowned author).",
          "A legendary figure from history or mythology who you believe holds the key to unraveling mysteries (e.g. King Arthur, Cleopatra, Sherlock Holmes).",
          "An influential political figure or leader who you admire or despise (e.g. a charismatic statesperson, a corrupt politician).",
          "A fellow explorer or adventurer who shared perilous journeys with you (e.g. an intrepid mountaineer, a daring deep-sea diver).",
          "A mysterious guardian spirit or protector who watches over you from the shadows (e.g. a shadowy figure, an otherworldly guardian).",
          "A wise old sage who imparts cryptic wisdom and guidance (e.g. an ancient sage, a mystical hermit).",
          "A childhood pen pal or online friend who vanished without a trace (e.g. a pen pal from a foreign land, an online gaming buddy).",
      ]

      selected_significant_people_first = random.choice(significant_people_first)
      
      significant_people_why = [
          "You are indebted to them because they lent you a substantial amount of money when you were in a financial crisis.",
          "They taught you the art of survival in the urban jungle, showing you how to navigate the streets and avoid trouble.",
          "They give your life meaning by being your source of inspiration; you strive to honor their memory in everything you do.",
          "You wronged them years ago by spreading false rumors about them that damaged their reputation; now, you want to make amends.",
          "You both served together in a military unit during a dangerous conflict, forging a deep bond through shared experiences.",
          "You seek to prove yourself to them by achieving success in your chosen field, hoping to earn their respect and admiration.",
          "You idolize them for their unparalleled musical talent, which has left a lasting impact on your life.",
          "A feeling of regret haunts you because you once failed to support them when they needed it most, and you've carried the guilt ever since.",
          "You wish to prove yourself as a better parent than they were, driven by the memory of their neglectful and distant behavior.",
          "They crossed you by betraying your trust, leading to the collapse of your once-thriving business; now, you harbor a deep desire for revenge.",
          "You owe them for saving your life when you were on the brink of death, forever grateful for their timely intervention.",
          "They taught you the art of craftsmanship, instilling in you a passion for creating beautiful and intricate objects.",
          "They give your life meaning by being the person who introduced you to your lifelong hobby or interest, shaping your identity.",
          "You wronged them by betraying a confidence they shared with you, causing significant harm to their personal and professional life; now, you seek redemption.",
          "Your shared experience involved surviving a natural disaster together, creating an unbreakable bond forged in the face of death.",
          "You aim to prove yourself by outshining their achievements in the field they excel in, eager to prove your superiority.",
      ]

      selected_significant_people_why = random.choice(significant_people_why)
  
      meaningful_locations = [
          "The hidden cave where you discovered an ancient relic that changed your life's course.",
          "The remote mountain cabin where you found solitude and clarity during a difficult period.",
          "The bustling city square where you once witnessed a life-changing event or protest.",
          "The abandoned factory that holds a secret you've been trying to unravel for years.",
          "The quaint seaside town where you spent idyllic summers as a child, forming cherished memories.",
          "The eerie cemetery where you had a paranormal encounter that still haunts your dreams.",
          "The sacred temple atop a mist-covered mountain, where you found spiritual enlightenment.",
          "The forgotten underground tunnel system you stumbled upon, filled with mysteries waiting to be explored.",
          "The historic battlefield where you uncovered artifacts that shed new light on a famous historical event.",
          "The hidden garden behind an old mansion, where you once made a promise that changed the course of your life.",
      ]
      selected_meaningful_locations = random.choice(meaningful_locations)
  
      treasured_possessions = [
          "A handwritten journal filled with your thoughts and observations from your travels.",
          "A mysterious ancient artifact that you acquired during an expedition and can't decipher its purpose.",
          "A locket containing a picture of a loved one who mysteriously disappeared years ago.",
          "A rare and valuable first edition book that you cherish as a symbol of knowledge.",
          "A vintage typewriter that you use to document your investigations and thoughts.",
          "A small vial of peculiar, glowing liquid that you believe has mysterious properties.",
          "A worn and weathered map that hints at the location of a hidden treasure or secret society.",
          "A pocket watch passed down through generations, said to have mystical qualities.",
          "A peculiar amulet with intricate symbols that you found in a remote temple.",
          "A loyal animal companion, such as a trained raven or a mystical cat with unusual powers."
      ]

      selected_treasured_possessions = random.choice(treasured_possessions)
  
      traits = [
          "Meticulous Planner (e.g. always has a backup plan, never leaves things to chance, highly organized).",
          "Adventurous Spirit (e.g. always seeking new experiences, loves exploring the unknown, embraces challenges).",
          "Keen Observer (e.g. notices the smallest details, excellent at solving puzzles, perceptive).",
          "Empathetic (e.g. sensitive to others' emotions, a good listener, always lends a sympathetic ear).",
          "Resourceful (e.g. can make the most of limited resources, great problem solver, creative thinker).",
          "Eloquent Speaker (e.g. persuasive communicator, excellent public speaker, can charm with words).",
          "Fearless (e.g. unflinching in the face of danger, never backs down from a challenge, courageous).",
          "Eccentric (e.g. marches to the beat of their own drum, unconventional, delightfully quirky).",
          "Resilient (e.g. bounces back from setbacks, mentally tough, unwavering determination).",
          "Charismatic Leader (e.g. natural leader, inspires others, commands respect and loyalty)."
      ]

      selected_traits = random.choice(traits)
  
      embed = discord.Embed(title="Character Backstory Generator", color=0x00ff00)
      embed.add_field(name=":biting_lip: Personal Description (chose one):", value=personal_description_text, inline=False)
      embed.add_field(name=":church: Ideology/Beliefs:", value=selected_ideology_beliefs, inline=False)
      embed.add_field(name=":bust_in_silhouette: Significant People:", value=f":grey_question: First, who?\n {selected_significant_people_first}\n :grey_question: Why?\n {selected_significant_people_why}", inline=False)
      embed.add_field(name=":map: Meaningful Locations:", value=selected_meaningful_locations, inline=False)
      embed.add_field(name=":gem: Treasured Possessions:", value=selected_treasured_possessions, inline=False)
      embed.add_field(name=":beginner: Traits:", value=selected_traits, inline=False)
  
      await ctx.send(embed=embed)


async def setup(bot):
  await bot.add_cog(generatebackstory(bot))
