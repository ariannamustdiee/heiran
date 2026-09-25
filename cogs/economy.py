import discord
from discord import app_commands
from discord.ext import commands

import database as db


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="balance", description="Check your (or someone else's) points")
    @app_commands.describe(member="Whose balance to check (defaults to you)")
    async def balance(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        points = db.get_points(interaction.guild_id, member.id)
        embed = discord.Embed(
            description=f"💰 **{member.display_name}** has **{points}** points.",
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Show the server's points leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        rows = db.get_leaderboard(interaction.guild_id, limit=10)
        if not rows:
            await interaction.response.send_message("No points recorded yet — go play a minigame!")
            return

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (user_id, points) in enumerate(rows):
            prefix = medals[i] if i < 3 else f"{i + 1}."
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else f"User {user_id}"
            lines.append(f"{prefix} **{name}** — {points} pts")

        embed = discord.Embed(
            title="🏆 Leaderboard",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
