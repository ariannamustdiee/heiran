"""
A banned-word tracker, modeled closely on matthew-robertson/banned-word-tracker:
the bot watches every message for a server's banned words (case- and accent-
insensitive, matched on whole words only). Saying one resets how long the
server has gone without it, and publicly calls the user out — but after one
callout per word, the bot stays quiet about that word until a cooldown passes
(30 minutes by default), so one slip doesn't spam the channel repeatedly.
"""
import re
import time

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils.text_match import contains_word

DELAY_PATTERN = re.compile(r"^(\d{1,2}):([0-5]?\d):([0-5]?\d)$")
MAX_DELAY_SECONDS = 24 * 60 * 60  # 24:00:00, same ballpark as the reference bot's hh:mm:ss


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes or hours:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


class BannedWords(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_group(
        name="bannedwords",
        description="Track how long the server goes without saying banned words",
        invoke_without_command=True,
    )
    @commands.guild_only()
    async def bannedwords(self, ctx: commands.Context):
        await self.bannedwords_list(ctx)

    # ---------- everyone ----------

    @bannedwords.command(name="list", description="Show how long it's been since each banned word was last said")
    async def bannedwords_list(self, ctx: commands.Context):
        words = db.list_banned_words(ctx.guild.id)
        if not words:
            await ctx.send("No banned words are set up yet. An admin can add one with `bannedwords add <word>`.")
            return

        now = time.time()
        lines = []
        for w in words:
            since = _format_duration(now - w["last_said_ts"]) if w["last_said_ts"] else "forever (never said)"
            lines.append(f"**{w['word']}** — {since}")

        embed = discord.Embed(
            title="🤐 Banned words — time since last said",
            description="\n".join(lines),
            color=discord.Color.orange(),
        )
        await ctx.send(embed=embed)

    @bannedwords.command(name="cooldowns", description="Show when each banned word can next trigger a public callout")
    async def bannedwords_cooldowns(self, ctx: commands.Context):
        words = db.list_banned_words(ctx.guild.id)
        cfg = db.get_bannedword_config(ctx.guild.id)

        if not words:
            await ctx.send("No banned words are set up yet. An admin can add one with `bannedwords add <word>`.")
            return

        now = time.time()
        lines = []
        for w in words:
            ready_at = w["last_callout_ts"] + cfg["cooldown_seconds"]
            if now >= ready_at:
                lines.append(f"**{w['word']}** — ready to call out now")
            else:
                lines.append(f"**{w['word']}** — next callout possible <t:{int(ready_at) + 1}:R>")

        embed = discord.Embed(
            title="⏳ Banned words — callout cooldowns",
            description="\n".join(lines),
            color=discord.Color.orange(),
        )
        embed.set_footer(
            text=f"Callout cooldown: {_format_duration(cfg['cooldown_seconds'])} | "
            f"Alerts: {'on' if cfg['alerts_enabled'] else 'off'}"
        )
        await ctx.send(embed=embed)

    # ---------- admin ----------

    @bannedwords.command(name="add", description="Ban a word or short phrase (admin only)")
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(word="The word or short phrase to ban")
    async def bannedwords_add(self, ctx: commands.Context, *, word: str):
        word = word.strip()
        if not word:
            await ctx.send("Give me a word to ban.", ephemeral=True)
            return
        if len(word) > 100:
            await ctx.send("That's too long for a banned word/phrase.", ephemeral=True)
            return
        db.add_banned_word(ctx.guild.id, word)
        await ctx.send(f"✅ Now tracking **{word.lower()}** as a banned word.")

    @bannedwords.command(name="remove", description="Stop tracking a banned word (admin only)")
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(word="The word to remove from the banned list")
    async def bannedwords_remove(self, ctx: commands.Context, *, word: str):
        if db.remove_banned_word(ctx.guild.id, word.strip()):
            await ctx.send(f"✅ **{word.strip().lower()}** is no longer banned.")
        else:
            await ctx.send("That word wasn't on the banned list.", ephemeral=True)

    @bannedwords.command(name="silence", description="Stop the bot from publicly calling people out (admin only)")
    @commands.has_permissions(manage_guild=True)
    async def bannedwords_silence(self, ctx: commands.Context):
        db.set_bannedword_alerts(ctx.guild.id, False)
        await ctx.send("🔇 I'll keep tracking banned words quietly, without calling anyone out.")

    @bannedwords.command(name="alert", description="Let the bot publicly call people out again (admin only)")
    @commands.has_permissions(manage_guild=True)
    async def bannedwords_alert(self, ctx: commands.Context):
        db.set_bannedword_alerts(ctx.guild.id, True)
        await ctx.send("🔊 I'll call people out again when they say a banned word.")

    @bannedwords.command(name="delay", description="Set the minimum time between public callouts, as hh:mm:ss (admin only)")
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(duration="Format hh:mm:ss, e.g. 00:30:00 for 30 minutes")
    async def bannedwords_delay(self, ctx: commands.Context, duration: str):
        match = DELAY_PATTERN.match(duration.strip())
        if not match:
            await ctx.send("Use the format `hh:mm:ss`, e.g. `00:30:00` for 30 minutes.", ephemeral=True)
            return

        hours, minutes, seconds = (int(g) for g in match.groups())
        total = hours * 3600 + minutes * 60 + seconds
        if total > MAX_DELAY_SECONDS:
            await ctx.send("That's longer than 24:00:00 — pick something shorter.", ephemeral=True)
            return

        db.set_bannedword_cooldown(ctx.guild.id, total)
        await ctx.send(f"✅ Callout cooldown set to **{_format_duration(total)}**.")

    # ---------- detection ----------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        words = db.list_banned_words(message.guild.id)
        if not words:
            return

        # Don't let admins configuring the list trigger a callout on the word they just typed.
        prefix = db.get_prefix(message.guild.id)
        if message.content.startswith(prefix):
            return

        cfg = db.get_bannedword_config(message.guild.id)
        now = time.time()

        for w in words:
            if not contains_word(message.content, w["word"]):
                continue

            db.mark_banned_word_said(message.guild.id, w["word"], now)

            if cfg["alerts_enabled"] and now - w["last_callout_ts"] >= cfg["cooldown_seconds"]:
                db.mark_banned_word_called_out(message.guild.id, w["word"], now)
                await message.channel.send(
                    f"🚨 {message.author.mention} just said a banned word (**{w['word']}**)! "
                    "The streak without it has been reset."
                )


async def setup(bot: commands.Bot):
    await bot.add_cog(BannedWords(bot))
