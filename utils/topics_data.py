"""
Conversation starters for the `topic` command.

Add, remove or reword entries freely — one string per line. Three lists:
  GENERAL  - everyday ice-breakers
  WYR      - "would you rather" questions
  AVATAR   - Avatar-universe questions (delete the list contents if your server isn't into that)
`topic` with no argument picks from all of them; `topic general|wyr|avatar` picks from one list.
"""

GENERAL = [
    "What's a skill you wish you could learn instantly?",
    "If you could live in any fictional world for a year, which would you pick?",
    "What's the best meal you've ever had?",
    "What's a hill you'd happily die on — a harmless opinion you'll never change?",
    "Which song never gets old for you, no matter how many times you hear it?",
    "If you could have dinner with any three people, living or dead, who would they be?",
    "What's the most useless talent you have?",
    "Cats, dogs, or something more unusual? Make your case.",
    "What's the best trip you've ever taken, or the one you most want to take?",
    "Which book or series made you cry (or came very close)?",
    "What's a movie you can quote almost word for word?",
    "If you had to eat only one cuisine for the rest of your life, which would it be?",
    "What's your comfort show when you're having a bad day?",
    "Morning person or night owl? Defend your choice.",
    "What's the weirdest food combination you secretly love?",
    "Which video game world would you most like to explore in real life?",
    "What was your favorite thing to do as a kid?",
    "If you could instantly speak any language fluently, which would you choose?",
    "What's the best gift you've ever received?",
    "What's a small thing that always makes your day better?",
    "Which fictional character would be the worst roommate?",
    "What would your superpower be, and what would be its most annoying side effect?",
    "What's something you changed your mind about recently?",
    "Summer or winter? Why?",
    "What's the best piece of advice you've ever been given?",
    "If you could add one rule to every school in the world, what would it be?",
    "Which historical period would you visit if time travel were possible (and you could come back)?",
    "What's a hobby you've always wanted to try?",
    "What's your go-to karaoke song?",
    "If your life had a soundtrack, what would the opening track be?",
    "What's the most beautiful place you've ever seen?",
    "What's a food you hated as a kid but love now?",
    "Which animal would you want as a sidekick?",
    "If you could redesign the internet in one way, what would you change?",
    "What's your unpopular opinion about a popular show or game?",
    "Tea, coffee, hot chocolate, or something else?",
    "What's the best way to spend a rainy day?",
    "What's the most interesting thing you learned this week?",
    "If you could master any instrument overnight, which would it be?",
    "What's a tradition — family, friends or personal — that you really treasure?",
    "Which city would you move to tomorrow if money and work didn't matter?",
    "What's your most-used emoji, and what does it say about you?",
    "If you opened a café, what would it be called and what would be on the menu?",
    "What's a game you could play for hours without a break?",
    "Which fictional villain had the best point?",
    "What's something you're proud of that nobody ever asked about?",
    "If you could swap lives with any fictional character for a day, who would it be?",
    "What's the strangest dream you remember?",
    "What's the best use of a free Saturday?",
    "Pineapple on pizza: yes or no? Let the debate begin.",
]

WYR = [
    "Would you rather be able to talk to animals or speak every human language?",
    "Would you rather always be 10 minutes late or always 20 minutes early?",
    "Would you rather have unlimited free travel or unlimited free food?",
    "Would you rather never be cold again or never be too hot again?",
    "Would you rather live in a treehouse or on a houseboat?",
    "Would you rather only ever rewatch your favorite show, or only ever watch brand-new ones?",
    "Would you rather be able to fly or be invisible?",
    "Would you rather explore the deep ocean or outer space?",
    "Would you rather give up music or give up movies for a year?",
    "Would you rather have a rewind button or a pause button for your life?",
    "Would you rather always know when someone is lying or always get away with lying yourself?",
    "Would you rather live without your phone for a month or without your favorite food for a year?",
    "Would you rather be famous for something good but forgotten in a year, or unknown but deeply loved by a few?",
    "Would you rather have a personal chef or a personal chauffeur?",
    "Would you rather be able to teleport anywhere but only once a day, or run at 100 km/h whenever you like?",
]

AVATAR = [
    "Which bending art would you choose, and why?",
    "If you were born in one of the four nations, which would suit your personality best?",
    "Which Avatar would you most like to have tea with?",
    "What's your favorite episode of Avatar: The Last Airbender, and why?",
    "Who's the most underrated character in the Avatar universe?",
    "If you could add one more bending art, what would it be?",
    "Which Avatar villain had the most compelling backstory?",
    "Which animal companion — Appa, Momo, Naga, Pabu... — would you adopt?",
    "What's the best fight scene in the whole franchise?",
    "Which place in the Avatar world would you most like to visit?",
    "Toph or Azula in a fair fight? Defend your pick.",
    "What's the most emotional moment in The Last Airbender or The Legend of Korra?",
    "Which piece of the Avatar soundtrack gives you chills?",
    "If you were a bender, what would your job be?",
    "Which character's growth over their story impressed you most?",
    "What's a detail you only noticed after your fifth rewatch?",
    "Which Avatar character would make the best teacher?",
    "Which two characters would make the funniest travel companions?",
    "Which pro-bending team would you cheer for, and what would be your team name?",
    "Which Avatar-world food would you most want to try?",
    "What's the most iconic quote from the series?",
    "Which Avatar-world outfit would you wear every day?",
    "If you could have one lesson from any bending master, who would teach it?",
    "Which side character deserved a spin-off?",
    "What's your headcanon for a character's life after the show ends?",
]

CATEGORIES = {
    "general": GENERAL,
    "wyr": WYR,
    "avatar": AVATAR,
}

ALL_TOPICS = [t for topics in CATEGORIES.values() for t in topics]
