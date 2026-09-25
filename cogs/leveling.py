import random
import time

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import leveling as lvl

XP_MIN = 15
XP_MAX = 25
MESSAGE_COOLDOWN_SECONDS = 60


class Leveling(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        now = time.time()
        last_ts = db.get_last_message_ts(message.guild.id, message.author.id)
        if now - last_ts < MESSAGE_COOLDOWN_SECONDS:
            return  # still on cooldown, no XP for this message

        old_xp = db.get_xp(message.guild.id, message.author.id)
        old_level, _ = lvl.level_from_total_xp(old_xp)

        gained = random.randint(XP_MIN, XP_MAX)
        new_xp = db.add_xp(message.guild.id, message.author.id, gained, now)
        new_level, _ = lvl.level_from_total_xp(new_xp)

        if new_level > old_level:
            await message.channel.send(
                f"🎉 {message.author.mention} leveled up to **level {new_level}**!"
            )

    @app_commands.command(name="rank", description="Show your (or someone else's) level and XP")
    @app_commands.describe(member="Whose rank to check (defaults to you)")
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        total_xp = db.get_xp(interaction.guild_id, member.id)
        level, xp_into_level = lvl.level_from_total_xp(total_xp)
        needed = lvl.xp_for_next_level(level)
        bar = lvl.progress_bar(xp_into_level, needed)

        embed = discord.Embed(title=f"📊 Rank — {member.display_name}", color=discord.Color.teal())
        embed.add_field(name="Level", value=str(level), inline=True)
        embed.add_field(name="Total XP", value=str(total_xp), inline=True)
        embed.add_field(
            name="Progress to next level",
            value=f"`{bar}` {xp_into_level}/{needed} XP",
            inline=False,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ranks", description="Show the server's level leaderboard")
    async def ranks(self, interaction: discord.Interaction):
        rows = db.get_xp_leaderboard(interaction.guild_id, limit=10)
        if not rows:
            await interaction.response.send_message("Nobody has earned XP yet — start chatting!")
            return

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (user_id, total_xp) in enumerate(rows):
            level, _ = lvl.level_from_total_xp(total_xp)
            prefix = medals[i] if i < 3 else f"{i + 1}."
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else f"User {user_id}"
            lines.append(f"{prefix} **{name}** — level {level} ({total_xp} XP)")

        embed = discord.Embed(
            title="📈 Level Leaderboard",
            description="\n".join(lines),
            color=discord.Color.teal(),
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))
