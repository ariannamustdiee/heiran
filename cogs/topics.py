import random
import time
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from utils.topics_data import ALL_TOPICS, CATEGORIES

TOPIC_COOLDOWN_SECONDS = 30  # per channel, so the chat doesn't get flooded with topics


class Topics(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._queues = {}   # (guild_id, category) -> topics not yet shown in the current round
        self._last = {}     # (guild_id, category) -> last topic shown
        self._last_used = {}  # channel_id -> unix time of the last topic

    def _next_topic(self, guild_id: int, category: str) -> str:
        """Goes through a shuffled list, so topics don't repeat until all have been shown."""
        key = (guild_id, category)
        pool = ALL_TOPICS if category == "any" else CATEGORIES[category]
        queue = self._queues.get(key)
        if not queue:
            queue = pool[:]
            random.shuffle(queue)
            if len(queue) > 1 and queue[-1] == self._last.get(key):
                queue[0], queue[-1] = queue[-1], queue[0]  # don't repeat the last one right after a reshuffle
            self._queues[key] = queue
        topic = queue.pop()
        self._last[key] = topic
        return topic

    @commands.hybrid_command(name="topic", description="Get a random topic to talk about")
    @commands.guild_only()
    @app_commands.describe(category="Kind of topic (leave empty for a mix)")
    async def topic(self, ctx: commands.Context, category: Literal["any", "general", "wyr", "avatar"] = "any"):
        now = time.time()
        ready_at = self._last_used.get(ctx.channel.id, 0) + TOPIC_COOLDOWN_SECONDS
        if now < ready_at:
            await ctx.send(
                f"⏳ A topic was just posted here — another one in {int(ready_at - now) + 1}s.",
                ephemeral=True,
                delete_after=None if ctx.interaction else 8,
            )
            return
        self._last_used[ctx.channel.id] = now

        text = self._next_topic(ctx.guild.id, category)
        embed = discord.Embed(title="💬 Let's talk about...", description=f"**{text}**", color=discord.Color.blurple())
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Topics(bot))
