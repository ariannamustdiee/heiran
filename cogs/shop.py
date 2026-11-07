import re
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import leveling as lvl

MOVIE_NIGHT_COST = 1000
XP_BOOST_COST = 1200
CUSTOM_ROLE_COST = 1600
MUTE_COST = 2000
EMOTE_COST = 3000
KICK_COST = 100000

EMOJI_MOVIE = "<:rangismirk:1541763237656268822>"
EMOJI_XP = "<:rangi_stare:1511115873379684573>"
EMOJI_ROLE = "<:cuterangi:1551963950130925760>"
EMOJI_MUTE = "<:angryrangi:1551963280388395078>"
EMOJI_EMOTE = "<:gayassrangshi:1532799198301524191>"
EMOJI_KICK = "<:anykasideeye:1550863025760636998>"

HEX_PATTERN = re.compile(r"^#?([0-9a-fA-F]{6})$")
EMOJI_NAME_PATTERN = re.compile(r"[^a-zA-Z0-9_]")
MAX_EMOJI_BYTES = 256 * 1024  # Discord's per-emoji upload limit


def _sanitize_emoji_name(raw: str) -> str:
    name = EMOJI_NAME_PATTERN.sub("", raw)[:32]
    if len(name) < 2:
        name = (name + "emote")[:32]
    return name


def _is_protected_target(member: discord.Member) -> bool:
    """Staff, the server owner, and bots can't be muted/kicked through the shop."""
    if member.bot:
        return True
    if member == member.guild.owner:
        return True
    perms = member.guild_permissions
    return perms.administrator or perms.manage_guild or perms.kick_members or perms.moderate_members


class KickConfirmView(discord.ui.View):
    def __init__(self, buyer: discord.Member, target: discord.Member, cost: int):
        super().__init__(timeout=30)
        self.buyer = buyer
        self.target = target
        self.cost = cost
        self.done = False

    async def _guard(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.buyer.id:
            await interaction.response.send_message("This isn't your purchase to confirm.", ephemeral=True)
            return False
        if self.done:
            await interaction.response.send_message("This purchase was already resolved.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm kick", style=discord.ButtonStyle.danger, emoji="👢")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._guard(interaction):
            return
        self.done = True
        for child in self.children:
            child.disabled = True

        guild = interaction.guild
        points = db.get_points(guild.id, self.buyer.id)
        if points < self.cost:
            await interaction.response.edit_message(
                content=f"You no longer have **{self.cost}** points for this.", view=self
            )
            return

        try:
            await self.target.kick(reason=f"Shop purchase by {self.buyer} ({self.buyer.id})")
        except discord.Forbidden:
            await interaction.response.edit_message(
                content="I don't have permission to kick that member (I need **Kick Members**, "
                "and my top role must be above theirs).",
                view=self,
            )
            return

        db.set_xp(guild.id, self.target.id, 0)
        db.add_points(guild.id, self.buyer.id, -self.cost)
        await interaction.response.edit_message(
            content=f"{EMOJI_KICK} {self.target.mention} was kicked and lost all their levels. "
            f"(-{self.cost} points)",
            view=self,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._guard(interaction):
            return
        self.done = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="Cancelled — no points spent.", view=self)


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

        embed = discord.Embed(
            title="🛒 Server Shop",
            description=f"You have **{points}** points to spend.",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name=f"{EMOJI_MOVIE} movie night — {MOVIE_NIGHT_COST} pts",
            value="you can decide what we are going to watch for movie night "
            "(only available when we have movie nights)\n`shop movienight`",
            inline=False,
        )
        embed.add_field(
            name=f"{EMOJI_XP} XP boost — {XP_BOOST_COST} pts",
            value="it will boost you up one level\n`shop xpboost`",
            inline=False,
        )
        embed.add_field(
            name=f"{EMOJI_ROLE} custom role — {CUSTOM_ROLE_COST} pts",
            value="you can have your own custom role\n`shop role <RRGGBB>` — e.g. `shop role FF00AA`",
            inline=False,
        )
        embed.add_field(
            name=f"{EMOJI_MUTE} wanna mute someone? — {MUTE_COST} pts",
            value="you can mute someone for one minute.\n`shop mute <member>`",
            inline=False,
        )
        embed.add_field(
            name=f"{EMOJI_EMOTE} personal emotes — {EMOTE_COST} pts",
            value="we will add to the server an animated emoji just for you\n"
            "`shop emote` with an image attached",
            inline=False,
        )
        embed.add_field(
            name=f"{EMOJI_KICK} wanna kick someone? — {KICK_COST} pts",
            value="you can kick someone, but they will lose all their levels.\n`shop kick <member>`",
            inline=False,
        )
        await ctx.send(embed=embed)

    # ---------- movie night ----------

    @shop.command(name="movienight", description=f"Spend {MOVIE_NIGHT_COST} points to pick what we watch for movie night")
    async def shop_movienight(self, ctx: commands.Context):
        points = db.get_points(ctx.guild.id, ctx.author.id)
        if points < MOVIE_NIGHT_COST:
            await ctx.send(f"You need **{MOVIE_NIGHT_COST}** points for this, you have **{points}**.", ephemeral=True)
            return

        db.add_points(ctx.guild.id, ctx.author.id, -MOVIE_NIGHT_COST)
        await ctx.send(
            f"{EMOJI_MOVIE} {ctx.author.mention} just bought movie night picking rights! "
            f"(-{MOVIE_NIGHT_COST} points) Let the staff know what you want to watch."
        )

    # ---------- XP boost ----------

    @shop.command(name="xpboost", description=f"Spend {XP_BOOST_COST} points to instantly go up one level")
    async def shop_xpboost(self, ctx: commands.Context):
        guild_id, user_id = ctx.guild.id, ctx.author.id

        points = db.get_points(guild_id, user_id)
        if points < XP_BOOST_COST:
            await ctx.send(f"You need **{XP_BOOST_COST}** points for this, you have **{points}**.", ephemeral=True)
            return

        current_xp = db.get_xp(guild_id, user_id)
        current_level, _ = lvl.level_from_total_xp(current_xp)
        db.set_xp(guild_id, user_id, lvl.total_xp_for_level(current_level + 1))
        db.add_points(guild_id, user_id, -XP_BOOST_COST)
        await ctx.send(
            f"{EMOJI_XP} {ctx.author.mention} boosted up to **level {current_level + 1}**! "
            f"(-{XP_BOOST_COST} points)"
        )

    # ---------- custom role ----------

    @shop.command(name="role", description=f"Spend {CUSTOM_ROLE_COST} points on your own custom colored role")
    @app_commands.describe(hex="6-digit hex color code, e.g. FF00AA")
    async def shop_role(self, ctx: commands.Context, hex: str):
        match = HEX_PATTERN.match(hex.strip())
        if not match:
            await ctx.send(
                "That's not a valid hex color. Use a 6-digit code like `FF00AA` or `#1abc9c`.",
                ephemeral=True,
            )
            return

        points = db.get_points(ctx.guild.id, ctx.author.id)
        if points < CUSTOM_ROLE_COST:
            await ctx.send(f"You need **{CUSTOM_ROLE_COST}** points for this, you have **{points}**.", ephemeral=True)
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
                    name=f"{member.display_name}",
                    colour=colour,
                    reason="Shop purchase: custom role",
                )
                await member.add_roles(role, reason="Shop purchase: custom role")
                db.set_custom_role(guild.id, member.id, role.id)
        except discord.Forbidden:
            await ctx.send(
                "I don't have permission to manage roles here (I need the **Manage Roles** permission, "
                "and my top role must be above where this new role would go).",
                ephemeral=True,
            )
            return

        db.add_points(guild.id, member.id, -CUSTOM_ROLE_COST)
        await ctx.send(
            f"{EMOJI_ROLE} Your custom role is ready, colored `#{match.group(1).upper()}` "
            f"(-{CUSTOM_ROLE_COST} points)."
        )

    # ---------- mute ----------

    @shop.command(name="mute", description=f"Spend {MUTE_COST} points to mute a member for 1 minute")
    @app_commands.describe(member="Who to mute for 1 minute")
    async def shop_mute(self, ctx: commands.Context, member: discord.Member):
        if member.id == ctx.author.id:
            await ctx.send("You can't mute yourself.", ephemeral=True)
            return
        if _is_protected_target(member):
            await ctx.send("That member can't be targeted.", ephemeral=True)
            return

        points = db.get_points(ctx.guild.id, ctx.author.id)
        if points < MUTE_COST:
            await ctx.send(f"You need **{MUTE_COST}** points for this, you have **{points}**.", ephemeral=True)
            return

        try:
            await member.timeout(
                discord.utils.utcnow() + timedelta(minutes=1),
                reason=f"Shop purchase by {ctx.author} ({ctx.author.id})",
            )
        except discord.Forbidden:
            await ctx.send(
                "I don't have permission to mute that member (I need **Moderate Members** / "
                "**Timeout Members**, and my top role must be above theirs).",
                ephemeral=True,
            )
            return

        db.add_points(ctx.guild.id, ctx.author.id, -MUTE_COST)
        await ctx.send(
            f"{EMOJI_MUTE} {member.mention} has been muted for 1 minute, courtesy of "
            f"{ctx.author.mention}. (-{MUTE_COST} points)"
        )

    # ---------- personal emote ----------

    @shop.command(name="emote", description=f"Spend {EMOTE_COST} points to add a personal server emoji")
    @app_commands.describe(image="The emoji image — PNG, JPG, or an animated GIF, max 256 KB")
    async def shop_emote(self, ctx: commands.Context, image: discord.Attachment):
        if not (image.content_type or "").startswith("image/"):
            await ctx.send("That attachment doesn't look like an image.", ephemeral=True)
            return
        if image.size > MAX_EMOJI_BYTES:
            await ctx.send(
                f"That image is too big — Discord emojis must be under {MAX_EMOJI_BYTES // 1024} KB.",
                ephemeral=True,
            )
            return

        points = db.get_points(ctx.guild.id, ctx.author.id)
        if points < EMOTE_COST:
            await ctx.send(f"You need **{EMOTE_COST}** points for this, you have **{points}**.", ephemeral=True)
            return

        image_bytes = await image.read()
        name = _sanitize_emoji_name(ctx.author.display_name)

        try:
            emoji = await ctx.guild.create_custom_emoji(
                name=name,
                image=image_bytes,
                reason=f"Shop purchase by {ctx.author} ({ctx.author.id})",
            )
        except discord.Forbidden:
            await ctx.send(
                "I don't have permission to add emojis here (I need **Manage Expressions** / "
                "**Manage Emojis and Stickers**).",
                ephemeral=True,
            )
            return
        except discord.HTTPException as e:
            await ctx.send(
                f"Couldn't add that emoji — {e.text if hasattr(e, 'text') else e} "
                "(the server's emoji slots might be full).",
                ephemeral=True,
            )
            return

        db.add_points(ctx.guild.id, ctx.author.id, -EMOTE_COST)
        await ctx.send(
            f"{EMOJI_EMOTE} Added your personal emote: {emoji} (-{EMOTE_COST} points)"
        )

    # ---------- kick ----------

    @shop.command(name="kick", description=f"Spend {KICK_COST} points to kick a member (they lose all their levels)")
    @app_commands.describe(member="Who to kick")
    async def shop_kick(self, ctx: commands.Context, member: discord.Member):
        if member.id == ctx.author.id:
            await ctx.send("You can't kick yourself.", ephemeral=True)
            return
        if _is_protected_target(member):
            await ctx.send("That member can't be targeted.", ephemeral=True)
            return

        points = db.get_points(ctx.guild.id, ctx.author.id)
        if points < KICK_COST:
            await ctx.send(f"You need **{KICK_COST}** points for this, you have **{points}**.", ephemeral=True)
            return

        view = KickConfirmView(ctx.author, member, KICK_COST)
        await ctx.send(
            f"⚠️ This will kick {member.mention} from the server and reset all their levels, "
            f"for **{KICK_COST}** points. Are you sure?",
            view=view,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Shop(bot))
