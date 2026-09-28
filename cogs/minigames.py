import asyncio
import difflib
import random
import re
from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils.trivia_data import OPEN_QUESTIONS

TRIVIA_POINTS = 25
RPS_POINTS = 15
OPEN_ANSWER_TIMEOUT = 30


def _normalize(text: str) -> str:
    text = re.sub(r"[^\w\s]", "", text.lower())
    text = re.sub(r"\b(the|a|an)\b", "", text)
    return re.sub(r"\s+", " ", text).strip()


def is_correct_answer(given: str, answer: str) -> bool:
    """Case/punctuation-insensitive match, with alternatives split by '/' and small typo tolerance."""
    g = _normalize(given)
    if not g:
        return False
    candidates = [answer] + [a for a in re.split(r"\s*/\s*", answer) if a]
    for candidate in candidates:
        a = _normalize(candidate)
        if g == a:
            return True
        if len(a) > 4 and not a.isdigit():
            if difflib.SequenceMatcher(None, g, a).ratio() >= 0.85:
                return True
    return False


TRIVIA_QUESTIONS = [
    {
        "question": "What is the capital of the Netherlands?",
        "options": ["Rotterdam", "Amsterdam", "The Hague", "Utrecht"],
        "answer": "Amsterdam",
    },
    {
        "question": "Which planet is known as the Red Planet?",
        "options": ["Venus", "Mars", "Jupiter", "Saturn"],
        "answer": "Mars",
    },
    {
        "question": "What is the largest ocean on Earth?",
        "options": ["Atlantic", "Indian", "Arctic", "Pacific"],
        "answer": "Pacific",
    },
    {
        "question": "In what year did World War II end?",
        "options": ["1943", "1945", "1947", "1950"],
        "answer": "1945",
    },
    {
        "question": "What is the chemical symbol for gold?",
        "options": ["Go", "Gd", "Au", "Ag"],
        "answer": "Au",
    },
    {
        "question": "Who painted the Mona Lisa?",
        "options": ["Michelangelo", "Raphael", "Leonardo da Vinci", "Donatello"],
        "answer": "Leonardo da Vinci",
    },
    {
        "question": "How many legs does a spider have?",
        "options": ["6", "8", "10", "12"],
        "answer": "8",
    },
    {
        "question": "What is the smallest country in the world?",
        "options": ["Monaco", "San Marino", "Vatican City", "Liechtenstein"],
        "answer": "Vatican City",
    },
]


class TriviaView(discord.ui.View):
    def __init__(self, correct_answer: str, asker_id: int):
        super().__init__(timeout=30)
        self.correct_answer = correct_answer
        self.asker_id = asker_id
        self.answered = False

    async def _handle_answer(self, interaction: discord.Interaction, choice: str):
        if self.answered:
            await interaction.response.send_message("This question was already answered!", ephemeral=True)
            return
        if interaction.user.id != self.asker_id:
            await interaction.response.send_message(
                "This isn't your trivia question — start your own with `/trivia`!", ephemeral=True
            )
            return

        self.answered = True
        for child in self.children:
            child.disabled = True

        if choice == self.correct_answer:
            new_total = db.add_points(interaction.guild_id, interaction.user.id, TRIVIA_POINTS)
            text = f"✅ Correct! **{self.correct_answer}** (+{TRIVIA_POINTS} points, total: {new_total})"
        else:
            text = f"❌ Wrong! The correct answer was **{self.correct_answer}**."

        await interaction.response.edit_message(content=text, view=self)
        self.stop()

    def build_buttons(self, options):
        for option in options:
            button = discord.ui.Button(label=option, style=discord.ButtonStyle.primary)

            async def callback(interaction: discord.Interaction, option=option):
                await self._handle_answer(interaction, option)

            button.callback = callback
            self.add_item(button)


class RPSView(discord.ui.View):
    CHOICES = ["Rock", "Paper", "Scissors"]
    BEATS = {"Rock": "Scissors", "Paper": "Rock", "Scissors": "Paper"}

    def __init__(self, player_id: int):
        super().__init__(timeout=30)
        self.player_id = player_id
        self.answered = False

        for choice in self.CHOICES:
            button = discord.ui.Button(label=choice, style=discord.ButtonStyle.secondary)

            async def callback(interaction: discord.Interaction, choice=choice):
                await self._play(interaction, choice)

            button.callback = callback
            self.add_item(button)

    async def _play(self, interaction: discord.Interaction, player_choice: str):
        if self.answered:
            await interaction.response.send_message("Already played!", ephemeral=True)
            return
        if interaction.user.id != self.player_id:
            await interaction.response.send_message(
                "This isn't your game — start your own with `/rps`!", ephemeral=True
            )
            return

        self.answered = True
        for child in self.children:
            child.disabled = True

        bot_choice = random.choice(self.CHOICES)

        if player_choice == bot_choice:
            result = "🤝 It's a tie!"
        elif self.BEATS[player_choice] == bot_choice:
            new_total = db.add_points(interaction.guild_id, interaction.user.id, RPS_POINTS)
            result = f"🎉 You win! (+{RPS_POINTS} points, total: {new_total})"
        else:
            result = "💀 You lose!"

        await interaction.response.edit_message(
            content=f"You picked **{player_choice}**, I picked **{bot_choice}**.\n{result}",
            view=self,
        )
        self.stop()


class Minigames(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="trivia", description="Answer a random trivia question for points")
    @commands.guild_only()
    async def trivia(self, ctx: commands.Context):
        pool = [("mc", q) for q in TRIVIA_QUESTIONS] + [("open", q) for q in OPEN_QUESTIONS]
        kind, q = random.choice(pool)

        if kind == "mc":
            options = q["options"][:]
            random.shuffle(options)
            view = TriviaView(correct_answer=q["answer"], asker_id=ctx.author.id)
            view.build_buttons(options)
            await ctx.send(f"🧠 **{q['question']}**", view=view)
            return

        await ctx.send(
            f"🧠 **{q['question']}**\n"
            f"-# {ctx.author.display_name}, type your answer in this channel within {OPEN_ANSWER_TIMEOUT} seconds."
        )

        def check(m: discord.Message):
            return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id

        try:
            reply = await self.bot.wait_for("message", check=check, timeout=OPEN_ANSWER_TIMEOUT)
        except asyncio.TimeoutError:
            await ctx.send(f"⏰ Time's up! The answer was **{q['answer']}**.")
            return

        if is_correct_answer(reply.content, q["answer"]):
            new_total = db.add_points(ctx.guild.id, ctx.author.id, TRIVIA_POINTS)
            await reply.reply(f"✅ Correct! **{q['answer']}** (+{TRIVIA_POINTS} points, total: {new_total})")
        else:
            await reply.reply(f"❌ Wrong! The correct answer was **{q['answer']}**.")

    @commands.hybrid_command(name="rps", description="Play rock-paper-scissors against the bot")
    @commands.guild_only()
    @app_commands.describe(choice="Your move (leave empty to use buttons)")
    async def rps(self, ctx: commands.Context, choice: Optional[Literal["rock", "paper", "scissors"]] = None):
        if choice is None:
            await ctx.send("Choose your move:", view=RPSView(player_id=ctx.author.id))
            return

        player = choice.capitalize()
        bot_choice = random.choice(RPSView.CHOICES)
        if player == bot_choice:
            result = "🤝 It's a tie!"
        elif RPSView.BEATS[player] == bot_choice:
            new_total = db.add_points(ctx.guild.id, ctx.author.id, RPS_POINTS)
            result = f"🎉 You win! (+{RPS_POINTS} points, total: {new_total})"
        else:
            result = "💀 You lose!"
        await ctx.send(f"You picked **{player}**, I picked **{bot_choice}**.\n{result}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Minigames(bot))
