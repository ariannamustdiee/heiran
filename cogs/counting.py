import discord
from discord import app_commands
from discord.ext import commands

import database as db

# Points awarded per correct number, plus a bonus every MILESTONE numbers
POINTS_PER_NUMBER = 1
MILESTONE = 50
MILESTONE_BONUS = 20


class Counting(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    group = app_commands.Group(name="counting", description="Counting game commands")

    @group.command(name="setup", description="Set the current channel as the counting channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_channel(self, interaction: discord.Interaction):
        db.set_counting_channel(interaction.guild_id, interaction.channel_id)
        await interaction.response.send_message(
            f"✅ This channel is now the counting channel. The next number is **1**."
        )

    @group.command(name="stats", description="Show the current counting stats")
    async def stats(self, interaction: discord.Interaction):
        cfg = db.get_counting_config(interaction.guild_id)
        if not cfg:
            await interaction.response.send_message(
                "No counting channel has been set up yet. Use `/counting setup`.",
                ephemeral=True,
            )
            return
        embed = discord.Embed(title="🔢 Counting stats", color=discord.Color.blue())
        embed.add_field(name="Current count", value=str(cfg["current_count"]))
        embed.add_field(name="Best streak this run", value=str(cfg["high_score"]))
        embed.add_field(name="Channel", value=f"<#{cfg['channel_id']}>", inline=False)
        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        cfg = db.get_counting_config(message.guild.id)
        if not cfg or message.channel.id != cfg["channel_id"]:
            return

        content = message.content.strip()
        if not content.lstrip("-").isdigit():
            return  # ignore non-number messages in the channel entirely

        number = int(content)
        expected = cfg["current_count"] + 1

        # Same user can't count twice in a row
        if cfg["last_user_id"] == message.author.id:
            await message.add_reaction("🚫")
            await message.channel.send(
                f"{message.author.mention} you can't count twice in a row! "
                f"The count has been reset to **1**."
            )
            db.reset_counting(message.guild.id)
            return

        if number == expected:
            db.update_counting(message.guild.id, number, message.author.id)
            await message.add_reaction("✅")

            points = POINTS_PER_NUMBER
            if number % MILESTONE == 0:
                points += MILESTONE_BONUS
                await message.channel.send(
                    f"🎉 Milestone! **{number}** reached by {message.author.mention} "
                    f"(+{MILESTONE_BONUS} bonus points)"
                )
            db.add_points(message.guild.id, message.author.id, points)
        else:
            await message.add_reaction("❌")
            await message.channel.send(
                f"{message.author.mention} broke the count at **{number}** "
                f"(expected **{expected}**). Back to **1**!"
            )
            db.reset_counting(message.guild.id)


async def setup(bot: commands.Bot):
    await bot.add_cog(Counting(bot))
