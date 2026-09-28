import re

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import leveling as lvl

NICKNAME_COST = 75
COLOR_ROLE_COST = 150
LEVEL_UP_BASE_COST = 120
LEVEL_UP_COST_PER_LEVEL = 60

HEX_PATTERN = re.compile(r"^#?([0-9a-fA-F]{6})$")


def level_up_cost(current_level: int) -> int:
    return LEVEL_UP_BASE_COST + current_level * LEVEL_UP_COST_PER_LEVEL


class Shop(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_group(name="shop", description="Spend your points on perks", invoke_without_command=True)
    @commands.guild_only()
    async def shop(self, ctx: commands.Context):
        await self.shop_view(ctx)

    @shop.command(name="view", description="See what you can buy with your points")
    async def shop_view(self, ctx: commands.Context):
        points = db.get_points(ctx.guild.id, ctx.author.id)
        current_xp = db.get_xp(ctx.guild.id, ctx.author.id)
        current_level, _ = lvl.level_from_total_xp(current_xp)
        next_level_cost = level_up_cost(current_level)

        embed = discord.Embed(
            title="🛒 Server Shop",
            description=f"You have **{points}** points to spend.",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name=f"✏️ Custom nickname — {NICKNAME_COST} pts",
            value="`shop nickname <new nickname>`",
            inline=False,
        )
        embed.add_field(
            name=f"🎨 Custom color role — {COLOR_ROLE_COST} pts",
            value="`shop color <RRGGBB>` — e.g. `shop color FF00AA`",
            inline=False,
        )
        embed.add_field(
            name=f"⬆️ Skip to level {current_level + 1} — {next_level_cost} pts",
            value="`shop levelup` — cost rises the higher your level already is",
            inline=False,
        )
        embed.set_footer(
            text="Note: Discord doesn't allow bots to change a member's global "
            "avatar, banner or username — only server nickname and roles."
        )
        await ctx.send(embed=embed)

    @shop.command(name="nickname", description=f"Spend {NICKNAME_COST} points to set a custom server nickname")
    @app_commands.describe(new_nick="The nickname you want (max 32 characters)")
    async def shop_nickname(self, ctx: commands.Context, *, new_nick: str):
        if len(new_nick) > 32:
            await ctx.send("Nicknames can be at most 32 characters long.", ephemeral=True)
            return

        points = db.get_points(ctx.guild.id, ctx.author.id)
        if points < NICKNAME_COST:
            await ctx.send(f"You need **{NICKNAME_COST}** points for this, you have **{points}**.", ephemeral=True)
            return

        try:
            await ctx.author.edit(nick=new_nick, reason="Shop purchase: nickname")
        except discord.Forbidden:
            await ctx.send(
                "I don't have permission to change your nickname (I need the **Manage Nicknames** "
                "permission, and my top role must be above yours).",
                ephemeral=True,
            )
            return

        db.add_points(ctx.guild.id, ctx.author.id, -NICKNAME_COST)
        await ctx.send(f"✅ Nickname changed to **{new_nick}** (-{NICKNAME_COST} points).")

    @shop.command(name="color", description=f"Spend {COLOR_ROLE_COST} points on a custom colored role")
    @app_commands.describe(hex="6-digit hex color code, e.g. FF00AA")
    async def shop_color(self, ctx: commands.Context, hex: str):
        match = HEX_PATTERN.match(hex.strip())
        if not match:
            await ctx.send(
                "That's not a valid hex color. Use a 6-digit code like `FF00AA` or `#1abc9c`.",
                ephemeral=True,
            )
            return

        points = db.get_points(ctx.guild.id, ctx.author.id)
        if points < COLOR_ROLE_COST:
            await ctx.send(f"You need **{COLOR_ROLE_COST}** points for this, you have **{points}**.", ephemeral=True)
            return

        colour = discord.Colour(int(match.group(1), 16))
        guild, member = ctx.guild, ctx.author

        try:
            role_id = db.get_custom_role(guild.id, member.id)
            role = guild.get_role(role_id) if role_id else None

            if role:
                await role.edit(colour=colour, reason="Shop purchase: recolor")
            else:
                role = await guild.create_role(
                    name=f"🎨 {member.display_name}",
                    colour=colour,
                    reason="Shop purchase: custom color role",
                )
                await member.add_roles(role, reason="Shop purchase: custom color role")
                db.set_custom_role(guild.id, member.id, role.id)
        except discord.Forbidden:
            await ctx.send(
                "I don't have permission to manage roles here (I need the **Manage Roles** permission, "
                "and my top role must be above where this new role would go).",
                ephemeral=True,
            )
            return

        db.add_points(guild.id, member.id, -COLOR_ROLE_COST)
        await ctx.send(f"✅ Your color role is now `#{match.group(1).upper()}` (-{COLOR_ROLE_COST} points).")

    @shop.command(name="levelup", description="Spend points to instantly skip to the next level")
    async def shop_levelup(self, ctx: commands.Context):
        guild_id, user_id = ctx.guild.id, ctx.author.id

        current_xp = db.get_xp(guild_id, user_id)
        current_level, _ = lvl.level_from_total_xp(current_xp)
        cost = level_up_cost(current_level)

        points = db.get_points(guild_id, user_id)
        if points < cost:
            await ctx.send(
                f"You need **{cost}** points to skip to level **{current_level + 1}**, you have **{points}**.",
                ephemeral=True,
            )
            return

        db.set_xp(guild_id, user_id, lvl.total_xp_for_level(current_level + 1))
        db.add_points(guild_id, user_id, -cost)
        await ctx.send(
            f"⬆️ {ctx.author.mention} bought their way to **level {current_level + 1}** (-{cost} points)!"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Shop(bot))
