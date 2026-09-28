import os
import asyncio
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()  # must run before importing database (it reads DB_PATH at import time)

import database as db

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")  # optional, for instant command sync while testing

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

intents = discord.Intents.default()
intents.message_content = True  # required for the counting game and for text (prefix) commands
intents.members = True  # helps resolve display names for the leaderboard


def get_prefix(bot: commands.Bot, message: discord.Message):
    """Per-server text-command prefix (default '?'), configurable with /setprefix."""
    prefix = db.get_prefix(message.guild.id) if message.guild else db.DEFAULT_PREFIX
    return commands.when_mentioned_or(prefix)(bot, message)


bot = commands.Bot(command_prefix=get_prefix, intents=intents)

COGS = [
    "cogs.eightball",
    "cogs.counting",
    "cogs.sudoku",
    "cogs.economy",
    "cogs.minigames",
    "cogs.shop",
    "cogs.leveling",
    "cogs.settings",
]


class WrongChannel(commands.CheckFailure):
    def __init__(self, channel_id: int):
        self.channel_id = channel_id
        super().__init__(f"Commands are only allowed in <#{channel_id}>")


@bot.check
async def only_in_allowed_channel(ctx: commands.Context) -> bool:
    """If an allowed channel is configured (/botchannel set), block commands elsewhere.
    Members with Manage Server can always use commands (so they can configure things)."""
    if not ctx.guild:
        return True
    allowed = db.get_allowed_channel(ctx.guild.id)
    if not allowed or ctx.channel.id == allowed:
        return True
    if ctx.author.guild_permissions.manage_guild:
        return True
    raise WrongChannel(allowed)


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    error = getattr(error, "original", error)
    # For text commands, tidy up the notice after a few seconds; slash replies are ephemeral.
    cleanup = 8 if ctx.interaction is None else None

    if isinstance(error, commands.CommandNotFound):
        return  # e.g. someone typing "?? lol" — ignore silently
    if isinstance(error, WrongChannel):
        await ctx.send(f"Please use bot commands in <#{error.channel_id}>.", ephemeral=True, delete_after=cleanup)
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You need the **Manage Server** permission to use this command.", ephemeral=True, delete_after=cleanup)
    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.send("This command only works inside a server.", ephemeral=True)
    elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument, commands.BadLiteralArgument)):
        usage = f"{ctx.clean_prefix}{ctx.command.qualified_name} {ctx.command.signature}".strip()
        await ctx.send(f"Invalid usage. Try: `{usage}`", ephemeral=True, delete_after=cleanup)
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("You can't use this command here.", ephemeral=True, delete_after=cleanup)
    else:
        log.error("Unhandled command error in %s", ctx.command, exc_info=error)
        await ctx.send("Something went wrong running that command.", ephemeral=True, delete_after=cleanup)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            bot.tree.copy_global_to(guild=guild)  # copy globally-defined commands into this guild
            synced = await bot.tree.sync(guild=guild)
            print(f"Synced {len(synced)} commands to guild {GUILD_ID}")
        else:
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} global commands (may take up to 1 hour to appear)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    print("Bot is ready.")


async def main():
    if not TOKEN:
        raise RuntimeError(
            "DISCORD_TOKEN is not set. Add it as an environment variable (or in a .env file)."
        )

    async with bot:
        for cog in COGS:
            await bot.load_extension(cog)
            print(f"Loaded {cog}")
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
