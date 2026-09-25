import random
import discord
from discord import app_commands
from discord.ext import commands

import database as db

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

    @app_commands.command(name="trivia", description="Answer a random trivia question for points")
    async def trivia(self, interaction: discord.Interaction):
        q = random.choice(TRIVIA_QUESTIONS)
        options = q["options"][:]
        random.shuffle(options)

        view = TriviaView(correct_answer=q["answer"], asker_id=interaction.user.id)
        view.build_buttons(options)

        await interaction.response.send_message(f"🧠 **{q['question']}**", view=view)

    @app_commands.command(name="rps", description="Play rock-paper-scissors against the bot")
    async def rps(self, interaction: discord.Interaction):
        view = RPSView(player_id=interaction.user.id)
        await interaction.response.send_message("Choose your move:", view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Minigames(bot))
