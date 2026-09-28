import discord
from discord.ext import commands

import database as db

# Points awarded per correct number, plus a bonus every MILESTONE numbers
POINTS_PER_NUMBER = 1
MILESTONE = 50
MILESTONE_BONUS = 20


class Counting(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_group(name="counting", description="Counting game commands", invoke_without_command=True)
    @commands.guild_only()
    async def counting(self, ctx: commands.Context):
        await ctx.send("Use `counting setup` (admins) or `counting stats`.")

    @counting.command(name="setup", description="Set the current channel as the counting channel")
    @commands.has_permissions(manage_guild=True)
    async def counting_setup(self, ctx: commands.Context):
        db.set_counting_channel(ctx.guild.id, ctx.channel.id)
        await ctx.send("✅ This channel is now the counting channel. The next number is **1**.")

    @counting.command(name="stats", description="Show the current counting stats")
    async def counting_stats(self, ctx: commands.Context):
        cfg = db.get_counting_config(ctx.guild.id)
        if not cfg:
            await ctx.send("No counting channel has been set up yet. Use `counting setup`.", ephemeral=True)
            return
        embed = discord.Embed(title="🔢 Counting stats", color=discord.Color.blue())
        embed.add_field(name="Current count", value=str(cfg["current_count"]))
        embed.add_field(name="Best streak this run", value=str(cfg["high_score"]))
        embed.add_field(name="Channel", value=f"<#{cfg['channel_id']}>", inline=False)
        await ctx.send(embed=embed)

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
