import random
import discord
from discord import app_commands
from discord.ext import commands

RESPONSES = [
    # Affirmative
    "It is certain.",
    "It is decidedly so.",
    "Without a doubt.",
    "Yes, definitely.",
    "You may rely on it.",
    "As I see it, yes.",
    "Most likely.",
    "Outlook good.",
    "Yes.",
    "Signs point to yes.",
    # Non-committal
    "Reply hazy, try again.",
    "Ask again later.",
    "Better not tell you now.",
    "Cannot predict now.",
    "Concentrate and ask again.",
    # Negative
    "Don't count on it.",
    "My reply is no.",
    "My sources say no.",
    "Outlook not so good.",
    "Very doubtful.",
]


class EightBall(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="8ball", description="Ask the magic 8ball a question")
    @app_commands.describe(question="The question you want to ask")
    async def eightball(self, interaction: discord.Interaction, question: str):
        answer = random.choice(RESPONSES)
        embed = discord.Embed(color=discord.Color.dark_purple())
        embed.add_field(name="🎱 Question", value=question, inline=False)
        embed.add_field(name="Answer", value=answer, inline=False)
        embed.set_footer(text=f"Asked by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(EightBall(bot))
