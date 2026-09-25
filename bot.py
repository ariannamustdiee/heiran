import os
import asyncio
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")  # optional, for instant command sync while testing

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.message_content = True  # required for the counting game to read numbers
intents.members = True  # helps resolve display names for the leaderboard

bot = commands.Bot(command_prefix="!", intents=intents)

COGS = [
    "cogs.eightball",
    "cogs.counting",
    "cogs.sudoku",
    "cogs.economy",
    "cogs.minigames",
    "cogs.shop",
    "cogs.leveling",
]


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
            "DISCORD_TOKEN is not set. Copy .env.example to .env and add your bot token."
        )

    async with bot:
        for cog in COGS:
            await bot.load_extension(cog)
            print(f"Loaded {cog}")
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
