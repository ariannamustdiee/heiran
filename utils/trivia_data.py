"""
Trivia questions, in two categories: GENERAL_RAW (general knowledge) and AVATAR_RAW (Avatar).
Questions are shown with clickable buttons.

Add questions inside the triple quotes of the right list, one per line, in this format
(the question text can't contain round or square brackets):

    Question text? (Correct answer)

and, optionally, the wrong options right after it in square brackets:

    Who was the English king with 6 wives? (Henry VIII) [Henry VII | Edward VI | Richard III]

How the buttons are built:
  * answer is True/False (or Yes/No)  -> just those two buttons
  * wrong options given in [ ... ]    -> answer + those (up to 3 are used, picked at random)
  * answer is a whole number          -> nearby numbers as wrong options (e.g. years +/- a few)
  * anything else, no [ ... ] given   -> wrong options borrowed from other questions' answers
                                          (can be too easy, so adding [ ... ] is better)
"""
import random
import re

GENERAL_RAW = """
What is the capital of the Netherlands? (Amsterdam) [Rotterdam | The Hague | Utrecht]
Which planet is known as the Red Planet? (Mars) [Venus | Jupiter | Saturn]
What is the largest ocean on Earth? (Pacific) [Atlantic | Indian | Arctic]
In what year did World War II end? (1945) [1943 | 1947 | 1950]
What is the chemical symbol for gold? (Au) [Go | Gd | Ag]
Who painted the Mona Lisa? (Leonardo da Vinci) [Michelangelo | Raphael | Donatello]
How many legs does a spider have? (8) [6 | 10 | 12]
What is the smallest country in the world? (Vatican City) [Monaco | San Marino | Liechtenstein]
How many beats does a whole note last for? (4) [2 | 3 | 8]
What are Hyenas closely related to? (Cats) [Dogs | Bears | Weasels]
What year did the American Civil War start? (1861) [1857 | 1863 | 1865]
Who was the English king with 6 wives? (Henry VIII) [Henry VII | Edward VI | Richard III]
When did Czar Nicholas II die? (1918) [1905 | 1917 | 1921]
What is the capital of Australia? (Canberra) [Sydney | Melbourne | Perth]
Which element has the chemical symbol Fe? (Iron) [Fluorine | Lead | Tin]
How many continents are there? (7) [5 | 6 | 8]
Who wrote Romeo and Juliet? (William Shakespeare) [Charles Dickens | Jane Austen | Christopher Marlowe]
What is the largest planet in our solar system? (Jupiter) [Saturn | Neptune | Earth]
In which country would you find the Colosseum? (Italy) [Greece | Spain | Turkey]
What is the hardest natural substance? (Diamond) [Quartz | Granite | Steel]
How many strings does a standard guitar have? (6) [4 | 5 | 7]
What is the longest river in Africa? (Nile) [Congo | Niger | Zambezi]
Which gas do plants absorb from the atmosphere? (Carbon dioxide) [Oxygen | Nitrogen | Hydrogen]
Who painted The Starry Night? (Vincent van Gogh) [Claude Monet | Pablo Picasso | Paul Cezanne]
What is the currency of Japan? (Yen) [Won | Yuan | Ringgit]
In what year did the Berlin Wall fall? (1989) [1987 | 1991 | 1993]
How many players does each soccer team have on the pitch? (11) [9 | 10 | 12]
What is the smallest prime number? (2) [0 | 1 | 3]
What is the capital of Canada? (Ottawa) [Toronto | Vancouver | Montreal]
Which planet is famous for its bright rings? (Saturn) [Jupiter | Uranus | Mars]
Who discovered penicillin? (Alexander Fleming) [Louis Pasteur | Marie Curie | Joseph Lister]
What is the main language spoken in Brazil? (Portuguese) [Spanish | French | Italian]
How many bones does an adult human have? (206) [186 | 212 | 256]
What is the tallest mountain above sea level? (Mount Everest) [K2 | Kilimanjaro | Mont Blanc]
Which country gave the Statue of Liberty to the USA? (France) [England | Spain | Italy]
In which city is the Eiffel Tower? (Paris) [Lyon | Brussels | Rome]
Who was the first person to walk on the Moon? (Neil Armstrong) [Buzz Aldrin | Yuri Gagarin | John Glenn]
What is the largest mammal in the world? (Blue whale) [African elephant | Giraffe | Sperm whale]
How many sides does a hexagon have? (6) [5 | 7 | 8]
What is the capital of Spain? (Madrid) [Barcelona | Seville | Valencia]
Which musical instrument has 88 keys? (Piano) [Organ | Accordion | Harpsichord]
What is the freezing point of water in degrees Celsius? (0) [10 | -10 | 32]
Who wrote the novel 1984? (George Orwell) [Aldous Huxley | Ray Bradbury | H. G. Wells]
In what year did the Titanic sink? (1912) [1905 | 1915 | 1921]
What is the largest hot desert in the world? (Sahara) [Gobi | Kalahari | Arabian]
Which vitamin does sunlight help your body produce? (Vitamin D) [Vitamin C | Vitamin A | Vitamin B12]
Which planet is closest to the Sun? (Mercury) [Venus | Mars | Earth]
Who composed The Four Seasons? (Antonio Vivaldi) [Johann Sebastian Bach | Wolfgang Amadeus Mozart | Ludwig van Beethoven]
Which Italian city is famous for its canals? (Venice) [Verona | Florence | Naples]
What is the capital of Germany? (Berlin) [Munich | Hamburg | Frankfurt]
Which is the largest country in the world by area? (Russia) [Canada | China | United States]
Who developed the theory of general relativity? (Albert Einstein) [Isaac Newton | Niels Bohr | Galileo Galilei]
What is the chemical symbol for sodium? (Na) [So | Sd | S]
How many minutes are there in a day? (1440) [1240 | 1400 | 2400]
Which country is famous for tulips and windmills? (Netherlands) [Belgium | Denmark | Germany]
What is the capital of Portugal? (Lisbon) [Porto | Madrid | Faro]
How many hearts does an octopus have? (3) [1 | 2 | 4]
What is the largest organ of the human body? (Skin) [Liver | Lungs | Heart]
Which language has the most native speakers? (Mandarin Chinese) [English | Spanish | Hindi]
Who wrote the Harry Potter books? (J. K. Rowling) [Suzanne Collins | Stephenie Meyer | Roald Dahl]
What does a barometer measure? (Air pressure) [Temperature | Humidity | Wind speed]
Which city hosted the 2016 Summer Olympics? (Rio de Janeiro) [London | Beijing | Tokyo]
In what year did humans first land on the Moon? (1969) [1965 | 1971 | 1973]
Which country is the Pizza Margherita originally from? (Italy) [France | Greece | Spain]
The Great Wall of China is visible from the Moon with the naked eye. (False)
A tomato is botanically a fruit. (True)
Lightning never strikes the same place twice. (False)
Sharks are mammals. (False)
Venus is the hottest planet in our solar system. (True)
"""

AVATAR_RAW = """
What is the name of Aang's flying bison? (Appa) [Momo | Naga | Pabu]
Who is the Fire Lord at the start of the series? (Ozai) [Azulon | Zuko | Sozin]
Which tribe are Katara and Sokka from? (Southern Water Tribe) [Northern Water Tribe | Kyoshi Island | Foggy Swamp Tribe]
What new form of bending did Toph invent? (Metalbending) [Lavabending | Sandbending | Bloodbending]
Who is Zuko's uncle? (Iroh) [Ozai | Sozin | Piandao]
What is the name of the Earth Kingdom's great walled capital? (Ba Sing Se) [Omashu | Gaoling | Republic City]
Who teaches Katara waterbending at the Northern Water Tribe? (Pakku) [Hama | Arnook | Jee]
For how many years was Aang frozen in the iceberg? (100) [50 | 75 | 150]
Which nation was attacked first when the Hundred Year War began? (Air Nomads) [Earth Kingdom | Southern Water Tribe | Northern Water Tribe]
What material is Sokka's sword made from? (Meteorite) [Jade | Obsidian | Platinum]
Who is the masked hero known as the Blue Spirit? (Zuko) [Jet | Sokka | Aang]
What is the name of Aang's winged lemur? (Momo) [Pabu | Naga | Bosco]
Which Avatar lived right before Aang? (Roku) [Kyoshi | Kuruk | Yangchen]
Which Avatar lived right before Roku? (Kyoshi) [Kuruk | Yangchen | Szeto]
How many elements can the Avatar bend? (4) [3 | 5 | 6]
Who leads the Dai Li in Ba Sing Se? (Long Feng) [Zhao | Hama | Pakku]
How does Aang defeat Ozai? (By taking away his bending) [He kills him | He locks him up | He banishes him]
Which island is home to the Kyoshi Warriors? (Kyoshi Island) [Ember Island | Whale Tail Island | Roku Island]
Who is the leader of the Kyoshi Warriors? (Suki) [Ty Lee | Mai | Azula]
What is Mai's specialty? (Knife throwing) [Chi blocking | Acrobatics | Lightning generation]
What is Ty Lee known for? (Chi blocking) [Knife throwing | Lightning generation | Metalbending]
What is the name of Iroh's tea shop? (The Jasmine Dragon) [The Lotus Palace | The Tea Tiger | The Golden Leaf]
Which nickname does Iroh have? (The Dragon of the West) [Lord of Flames | The Tiger of the East | The Phoenix of the North]
Which creature teaches Aang energybending? (A lion turtle) [A dragon | A badgermole | A koi fish]
Who taught the first firebenders? (The dragons) [The badgermoles | The sky bison | The lion turtles]
Toph Beifong was born blind. (True)
Sokka is a bender. (False)
Momo is a fox. (False)
Iroh is Zuko's father. (False)
What is Mako and Bolin's mother's name? (Naoki) [Pema | Kya | Lin]
Who is the Avatar after Aang? (Korra) [Kya | Asami | Jinora]
Who is the Avatar before Aang? (Roku) [Korra | Szeto | Xian]
What is the name of Korra's polar bear dog? (Naga) [Appa | Pabu | Bosco]
In which city does The Legend of Korra mainly take place? (Republic City) [Ba Sing Se | Omashu | Kyoshi Island]
Who is Korra's airbending teacher? (Tenzin) [Bumi | Kai | Opal]
Who is the main villain of Book One of Korra? (Amon) [Unalaq | Ryu | Otaku]
Who is the main villain of Book Three of Korra? (Zaheer) [Amon | Unalaq | Kuvira]
Which sport do Mako, Bolin and Korra play? (Pro-bending) [Agni Kai | Earth Rumble | Sky Polo]
What is the name of Asami's family company? (Future Industries) [Sato Motors | Republic Tech | Cabbage Corp]
Who is Tenzin's oldest child? (Jinora) [Ikki | Meelo | Rohan]
"""

_LINE_RE = re.compile(r"([^\n()\[\]]{8,}?)\s*\(([^()\n]+)\)(?:[ \t]*\[([^\]\n]+)\])?")
_FIXED_CHOICES = {"true": ("True", "False"), "false": ("True", "False"),
                  "yes": ("Yes", "No"), "no": ("Yes", "No")}


def parse_questions(raw: str):
    items = []
    for question, answer, wrong in _LINE_RE.findall(raw):
        answer = answer.strip()
        if answer.lower() in _FIXED_CHOICES:
            answer = answer.capitalize()  # matches the button label exactly
        items.append({
            "question": question.strip(),
            "answer": answer,
            "wrong": [w.strip() for w in wrong.split("|") if w.strip()] if wrong else [],
        })
    return items


QUESTIONS = {
    "general": parse_questions(GENERAL_RAW),
    "avatar": parse_questions(AVATAR_RAW),
}


def _numeric_distractors(value: int, count: int):
    if 1000 <= value <= 2100:          # looks like a year
        offsets = [1, 2, 3, 4, 5, 8, 10, 12, 15, 20]
    elif abs(value) <= 20:
        offsets = [1, 2, 3, 4, 5]
    else:
        step = max(1, round(abs(value) * 0.1))
        offsets = [step * k for k in (1, 2, 3, 4, 5)]
    candidates = {value + o for o in offsets} | {value - o for o in offsets}
    candidates = [c for c in candidates if c != value and (value < 0 or c >= 0)]
    return [str(c) for c in random.sample(candidates, min(count, len(candidates)))]


def build_options(item: dict, other_answers):
    """Returns (options, shuffle). `other_answers` = answers of other questions, used as a fallback."""
    answer = item["answer"]

    fixed = _FIXED_CHOICES.get(answer.lower())
    if fixed:
        return list(fixed), False  # keep True/False in their natural order

    wrong = []
    seen = {answer.casefold()}

    def add(candidate):
        if candidate.casefold() not in seen:
            seen.add(candidate.casefold())
            wrong.append(candidate)

    given = list(item.get("wrong", []))
    random.shuffle(given)
    for w in given:
        add(w)
    wrong = wrong[:3]

    if len(wrong) < 3:
        if re.fullmatch(r"-?\d+", answer):
            for w in _numeric_distractors(int(answer), 6):
                if len(wrong) < 3:
                    add(w)
        else:
            pool = [a for a in other_answers
                    if not re.fullmatch(r"-?\d+", a) and a.lower() not in _FIXED_CHOICES]
            random.shuffle(pool)
            for a in pool:
                if len(wrong) < 3:
                    add(a)

    return [answer] + wrong, True
