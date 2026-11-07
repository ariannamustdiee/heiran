import discord
from discord import app_commands
from discord.ext import commands

import database as db


class Settings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- prefix ----------

    @commands.hybrid_command(name="setprefix", description="Set the text-command prefix for this server (default: ?)")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(prefix="New prefix, e.g. ? or ! (max 5 characters)")
    async def setprefix(self, ctx: commands.Context, prefix: str):
        if len(prefix) > 5:
            await ctx.send("The prefix can be at most 5 characters long.", ephemeral=True)
            return
        db.set_prefix(ctx.guild.id, prefix)
        await ctx.send(f"✅ Prefix set to `{prefix}` — e.g. `{prefix}8ball will it work?`")

    @commands.hybrid_command(name="prefix", description="Show this server's current text-command prefix")
    @commands.guild_only()
    async def prefix(self, ctx: commands.Context):
        await ctx.send(f"Current prefix: `{db.get_prefix(ctx.guild.id)}`")

    # ---------- storage check ----------

    @commands.hybrid_command(name="dbinfo", description="Check where the bot stores its data and whether it survives restarts")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def dbinfo(self, ctx: commands.Context):
        persistent, explanation = db.storage_status()
        report = db.storage_report(ctx.guild.id)
        embed = discord.Embed(
            title="💾 Data storage",
            description=("✅ " if persistent else "⚠️ ") + explanation,
            color=discord.Color.green() if persistent else discord.Color.orange(),
        )
        embed.add_field(name="File", value=f"`{report['path']}`", inline=False)
        embed.add_field(name="Size", value=f"{report['size_bytes'] / 1024:.1f} KB")
        embed.add_field(name="Members with XP here", value=str(report["members_with_xp"]))
        embed.add_field(name="Members with points here", value=str(report["members_with_points"]))
        await ctx.send(embed=embed, ephemeral=True)

    # ---------- allowed channel ----------

    @commands.hybrid_group(name="botchannel", description="Restrict the bot commands to one channel", invoke_without_command=True)
    @commands.guild_only()
    async def botchannel(self, ctx: commands.Context):
        await self.botchannel_show(ctx)

    @botchannel.command(name="set", description="Only allow bot commands in this channel (or the one you choose)")
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(channel="Channel where members can use the bot (defaults to the current one)")
    async def botchannel_set(self, ctx: commands.Context, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        db.set_allowed_channel(ctx.guild.id, channel.id)
        await ctx.send(
            f"✅ Members can now use bot commands only in {channel.mention}. "
            "People with the Manage Server permission can still use them anywhere."
        )

    @botchannel.command(name="clear", description="Allow bot commands in every channel again")
    @commands.has_permissions(manage_guild=True)
    async def botchannel_clear(self, ctx: commands.Context):
        db.set_allowed_channel(ctx.guild.id, None)
        await ctx.send("✅ Bot commands are now allowed in every channel.")

    @botchannel.command(name="show", description="Show where bot commands are currently allowed")
    async def botchannel_show(self, ctx: commands.Context):
        channel_id = db.get_allowed_channel(ctx.guild.id)
        if channel_id:
            await ctx.send(f"Bot commands are allowed only in <#{channel_id}>.")
        else:
            await ctx.send("Bot commands are allowed in every channel.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Settings(bot))
