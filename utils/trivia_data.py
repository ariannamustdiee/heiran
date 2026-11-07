"""
Extra trivia questions. They are shown with clickable buttons, like the built-in ones.

Paste questions between the triple quotes below in this format:

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

OPEN_QUESTIONS_RAW = """
How many beats does a whole note last for? (4) [2 | 3 | 8]
What is Mako and Bolin's mother's name? (Naoki) [Pema | Kya | Lin]
What are Hyenas closely related to? (Cats) [Dogs | Bears | Weasels]
What year did the American Civil War start? (1861) [1857 | 1863 | 1865]
Who was the English king with 6 wives? (Henry VIII) [Henry VII | Edward VI | Richard III]
When did Czar Nicholas II die? (1918) [1905 | 1917 | 1921]
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


EXTRA_QUESTIONS = parse_questions(OPEN_QUESTIONS_RAW)


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
