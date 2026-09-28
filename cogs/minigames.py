import random
import time
from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils.trivia_data import EXTRA_QUESTIONS, build_options

TRIVIA_POINTS = 25
RPS_POINTS = 15


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
            button = discord.ui.Button(label=option[:80], style=discord.ButtonStyle.primary)

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
        self._last_trivia = {}  # (guild_id, user_id) -> unix time of their last question

    @commands.hybrid_command(name="triviacooldown", description="Set how many minutes members wait between trivia questions")
    @commands.guild_only()
    @app_commands.describe(minutes="Minutes between questions per member (0 = no limit). Leave empty to see the current value.")
    async def triviacooldown(self, ctx: commands.Context, minutes: Optional[commands.Range[int, 0, 1440]] = None):
        if minutes is None:
            current = db.get_trivia_cooldown(ctx.guild.id)
            text = "no limit" if current == 0 else f"{current} minute(s) per member"
            await ctx.send(f"Trivia slowdown: **{text}**.")
            return
        if not ctx.author.guild_permissions.manage_guild:
            await ctx.send("You need the **Manage Server** permission to change this.", ephemeral=True)
            return
        db.set_trivia_cooldown(ctx.guild.id, minutes)
        if minutes == 0:
            await ctx.send("✅ Trivia slowdown turned off.")
        else:
            await ctx.send(f"✅ Each member can now get one trivia question every **{minutes}** minute(s).")

    @commands.hybrid_command(name="trivia", description="Answer a random trivia question for points")
    @commands.guild_only()
    async def trivia(self, ctx: commands.Context):
        cooldown_seconds = db.get_trivia_cooldown(ctx.guild.id) * 60
        key = (ctx.guild.id, ctx.author.id)
        now = time.time()
        ready_at = self._last_trivia.get(key, 0) + cooldown_seconds
        if cooldown_seconds and now < ready_at:
            await ctx.send(
                f"⏳ Slow down! You can get your next trivia question <t:{int(ready_at) + 1}:R>.",
                ephemeral=True,
                delete_after=None if ctx.interaction else 10,
            )
            return
        self._last_trivia[key] = now

        q = random.choice(TRIVIA_QUESTIONS + EXTRA_QUESTIONS)

        if "options" in q:  # built-in question with its own options
            options, shuffle = q["options"][:], True
        else:               # question from utils/trivia_data.py
            other_answers = [x["answer"] for x in TRIVIA_QUESTIONS + EXTRA_QUESTIONS if x is not q]
            options, shuffle = build_options(q, other_answers)
        if shuffle:
            random.shuffle(options)

        view = TriviaView(correct_answer=q["answer"], asker_id=ctx.author.id)
        view.build_buttons(options)
        await ctx.send(f"🧠 **{q['question']}**", view=view)

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
