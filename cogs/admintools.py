import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import leveling as lvl

MAX_LEVEL = 500
NO_MENTIONS = discord.AllowedMentions.none()


def is_staff(member: discord.Member) -> bool:
    """Admins, server managers and moderators (those who can time members out)."""
    perms = member.guild_permissions
    return perms.administrator or perms.manage_guild or perms.moderate_members


class AdminTools(commands.Cog):
    """Staff-only commands to adjust members' points and levels."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _guard(self, ctx: commands.Context, member: discord.Member) -> bool:
        """True if the command may go ahead; otherwise explains why and returns False."""
        if not is_staff(ctx.author):
            await ctx.send(
                "Only admins and moderators can use this command.",
                ephemeral=True, delete_after=None if ctx.interaction else 8,
            )
            return False
        if member.bot:
            await ctx.send("Bots don't have points or levels.", ephemeral=True,
                           delete_after=None if ctx.interaction else 8)
            return False
        return True

    # ---------- points ----------

    @commands.hybrid_command(name="addpoints", description="Staff: give points to a member")
    @commands.guild_only()
    @app_commands.describe(member="Who gets the points", amount="How many points to add")
    async def addpoints(self, ctx: commands.Context, member: discord.Member,
                        amount: commands.Range[int, 1, 1_000_000]):
        if not await self._guard(ctx, member):
            return
        total = db.add_points(ctx.guild.id, member.id, amount)
        await ctx.send(f"✅ Added **{amount}** points to {member.mention}. New total: **{total}**.",
                       allowed_mentions=NO_MENTIONS)

    @commands.hybrid_command(name="removepoints", description="Staff: take points away from a member")
    @commands.guild_only()
    @app_commands.describe(member="Who loses the points", amount="How many points to remove")
    async def removepoints(self, ctx: commands.Context, member: discord.Member,
                           amount: commands.Range[int, 1, 1_000_000]):
        if not await self._guard(ctx, member):
            return
        current = db.get_points(ctx.guild.id, member.id)
        taken = min(amount, current)  # never below zero
        total = db.add_points(ctx.guild.id, member.id, -taken)
        note = "" if taken == amount else f" (they only had {current})"
        await ctx.send(f"✅ Removed **{taken}** points from {member.mention}{note}. New total: **{total}**.",
                       allowed_mentions=NO_MENTIONS)

    # ---------- levels ----------

    def _change_level(self, guild_id: int, member: discord.Member, new_level: int):
        old_level, _ = lvl.level_from_total_xp(db.get_xp(guild_id, member.id))
        db.set_xp(guild_id, member.id, lvl.total_xp_for_level(new_level))
        return old_level

    @commands.hybrid_command(name="addlevel", description="Staff: raise a member's level")
    @commands.guild_only()
    @app_commands.describe(member="Who levels up", levels="How many levels to add (default 1)")
    async def addlevel(self, ctx: commands.Context, member: discord.Member,
                       levels: commands.Range[int, 1, MAX_LEVEL] = 1):
        if not await self._guard(ctx, member):
            return
        current, _ = lvl.level_from_total_xp(db.get_xp(ctx.guild.id, member.id))
        new_level = min(MAX_LEVEL, current + levels)
        self._change_level(ctx.guild.id, member, new_level)
        await ctx.send(f"✅ {member.mention} went from level **{current}** to level **{new_level}**.",
                       allowed_mentions=NO_MENTIONS)

    @commands.hybrid_command(name="removelevel", description="Staff: lower a member's level")
    @commands.guild_only()
    @app_commands.describe(member="Who loses levels", levels="How many levels to remove (default 1)")
    async def removelevel(self, ctx: commands.Context, member: discord.Member,
                          levels: commands.Range[int, 1, MAX_LEVEL] = 1):
        if not await self._guard(ctx, member):
            return
        current, _ = lvl.level_from_total_xp(db.get_xp(ctx.guild.id, member.id))
        new_level = max(0, current - levels)
        self._change_level(ctx.guild.id, member, new_level)
        await ctx.send(f"✅ {member.mention} went from level **{current}** to level **{new_level}**.",
                       allowed_mentions=NO_MENTIONS)

    @commands.hybrid_command(name="setlevel", description="Staff: set a member's level to an exact value")
    @commands.guild_only()
    @app_commands.describe(member="Whose level to set", level=f"The new level (0-{MAX_LEVEL})")
    async def setlevel(self, ctx: commands.Context, member: discord.Member,
                       level: commands.Range[int, 0, MAX_LEVEL]):
        if not await self._guard(ctx, member):
            return
        old = self._change_level(ctx.guild.id, member, level)
        await ctx.send(f"✅ {member.mention} went from level **{old}** to level **{level}**.",
                       allowed_mentions=NO_MENTIONS)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminTools(bot))
