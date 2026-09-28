import discord
from discord import app_commands
from discord.ext import commands

import database as db


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="balance", description="Check your (or someone else's) points")
    @commands.guild_only()
    @app_commands.describe(member="Whose balance to check (defaults to you)")
    async def balance(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        points = db.get_points(ctx.guild.id, member.id)
        embed = discord.Embed(
            description=f"💰 **{member.display_name}** has **{points}** points.",
            color=discord.Color.gold(),
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="leaderboard", description="Show the server's points leaderboard")
    @commands.guild_only()
    async def leaderboard(self, ctx: commands.Context):
        rows = db.get_leaderboard(ctx.guild.id, limit=10)
        if not rows:
            await ctx.send("No points recorded yet — go play a minigame!")
            return

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (user_id, points) in enumerate(rows):
            prefix = medals[i] if i < 3 else f"{i + 1}."
            member = ctx.guild.get_member(user_id)
            name = member.display_name if member else f"User {user_id}"
            lines.append(f"{prefix} **{name}** — {points} pts")

        embed = discord.Embed(
            title="🏆 Leaderboard",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
