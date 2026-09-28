"""
Extra trivia questions, answered by TYPING the answer (no multiple-choice buttons).

Paste questions between the triple quotes below in this format, one after the
other (new lines or just spaces between them both work):

    Question text? (Answer)

The answer goes in round brackets right after the question. Alternative
accepted answers can be separated with a slash: (Henry VIII / Henry 8)
"""
import re

OPEN_QUESTIONS_RAW = """
How many beats does a whole note last for? (4)
What is Mako and Bolin's mother's name? (Naoki)
What are Hyenas closely related to? (Cats)
What year did the American Civil War start? (1861)
Who was the English king with 6 wives? (Henry VIII)
When did Czar Nicholas II die? (1918)
"""

_LINE_RE = re.compile(r"([^\n()]{8,}?)\s*\(([^()\n]+)\)")


def parse_open_questions(raw: str):
    return [
        {"question": q.strip(), "answer": a.strip()}
        for q, a in _LINE_RE.findall(raw)
    ]


OPEN_QUESTIONS = parse_open_questions(OPEN_QUESTIONS_RAW)
