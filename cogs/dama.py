import io
import logging
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import boardgames as bg
from utils import dama_engine as eng
from utils.boardimage import checkers_text, render_checkers

log = logging.getLogger("bot.dama")

NO_GAME = "You don't have an active checkers game. Start one with `checkers challenge @member`."

HELP_TEXT = (
    "**Checkers** (Italian rules) — play against another member.\n"
    "`checkers challenge @member [white|black|random]` — invite someone\n"
    "`checkers move <from> <to>` — e.g. `c3 d4`; for a multi-jump write the whole path: `c3 e5 g7`\n"
    "`checkers board` — show your game · `checkers resign` — give up · `checkers draw` — offer/accept a draw\n"
    "Rules: men move and capture forward only, kings one step in any direction, a man can't capture "
    "a king, capturing is compulsory and you must take the biggest capture available."
)


def _last_path(game: dict):
    if not game.get("last_move"):
        return ()
    return tuple(eng.parse_square(s) for s in eng.SQUARE_RE.findall(game["last_move"]))


class Dama(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def post_board(self, send, game: dict, *, headline: str = "", ping: bool = True):
        pieces, _, _ = eng.load_state(game["state"])
        finished = game["status"] != "active"

        lines = [f"⚪ White: {bg.mention(game['white_id'])}", f"⚫ Black: {bg.mention(game['black_id'])}"]
        if game.get("last_move"):
            lines.append(f"Last move: **{game['last_move']}**")
        if headline:
            lines.append("")
            lines.append(headline)
        elif not finished:
            legal = eng.legal_moves(pieces, game["turn"])
            if legal and legal[0].captured:
                lines.append("")
                lines.append("⚠️ **A capture is compulsory.**")

        embed = discord.Embed(title="⚫⚪ Checkers", color=discord.Color.dark_green())
        file = None
        try:
            file = discord.File(io.BytesIO(render_checkers(pieces, _last_path(game))), filename="board.png")
            embed.set_image(url="attachment://board.png")
        except Exception:
            log.exception("Could not draw the dama board, falling back to text")
            lines.append(f"```\n{checkers_text(pieces)}\n```")
        embed.description = "\n".join(lines)

        if finished:
            embed.set_footer(text="Game over")
            content = None
        else:
            side = game["turn"]
            embed.set_footer(text=f"Move {game['moves_played'] // 2 + 1} • {side.capitalize()} to move")
            content = f"{bg.mention(bg.player_to_move(game))} it's your move ({side})." if ping else None

        kwargs = {"embed": embed}
        if file:
            kwargs["file"] = file
        await send(content, **kwargs)

    @commands.hybrid_group(name="checkers", aliases=["dama", "draughts"],
                           description="Play checkers (Italian rules) against another member",
                           invoke_without_command=True)
    @commands.guild_only()
    async def dama_cmd(self, ctx: commands.Context):
        await ctx.send(HELP_TEXT)

    @dama_cmd.command(name="challenge", description="Challenge a member to a game of checkers")
    @app_commands.describe(opponent="Who you want to play against", color="The side you want to play")
    async def dama_challenge(self, ctx: commands.Context, opponent: discord.Member,
                             color: Literal["white", "black", "random"] = "random"):
        await bg.start_challenge(
            ctx, game_type="dama", label="checkers", opponent=opponent, color=color,
            initial_state=eng.initial_state(), post_board=self.post_board,
        )

    @dama_cmd.command(name="move", description="Play a move in your game")
    @app_commands.describe(squares="Your move, e.g. c3 d4 — or the whole path for a multi-jump: c3 e5 g7")
    async def dama_move(self, ctx: commands.Context, *, squares: str):
        game = db.get_active_board_game(ctx.guild.id, "dama", ctx.author.id)
        if not game:
            return await bg.notice(ctx, NO_GAME)
        if bg.side_of(game, ctx.author.id) != game["turn"]:
            return await bg.notice(ctx, f"It's not your turn — waiting for {bg.mention(bg.player_to_move(game))}.")

        pieces, _, _ = eng.load_state(game["state"])
        legal = eng.legal_moves(pieces, game["turn"])
        move, error = eng.find_move(legal, squares)
        if move is None:
            if error is None:
                if legal[0].captured:
                    error = f"That's not allowed — you must capture. Possible moves: {eng.legal_summary(legal)}"
                else:
                    error = f"`{squares.strip()}` isn't a legal move. Possible moves: {eng.legal_summary(legal)}"
            return await bg.notice(ctx, error)

        result = eng.play(game["state"], game["turn"], move)
        game["state"] = result.state
        game["turn"] = "black" if game["turn"] == "white" else "white"
        game["moves_played"] += 1
        game["last_move"] = eng.describe(move)
        game["draw_offer_by"] = None
        db.save_board_game(game["id"], game["state"], game["turn"], game["moves_played"], game["last_move"])

        headline = ""
        if result.outcome == "win":
            headline = bg.conclude(ctx.guild.id, game, winner_id=ctx.author.id, reason=result.reason)
            game["status"] = "finished"
        elif result.outcome == "draw":
            headline = bg.conclude(ctx.guild.id, game, winner_id=None, reason=result.reason)
            game["status"] = "finished"
        await self.post_board(ctx.send, game, headline=headline)

    @dama_cmd.command(name="board", description="Show the board of your current game")
    async def dama_board(self, ctx: commands.Context):
        game = db.get_active_board_game(ctx.guild.id, "dama", ctx.author.id)
        if not game:
            return await bg.notice(ctx, NO_GAME)
        await self.post_board(ctx.send, game)

    @dama_cmd.command(name="resign", description="Resign your current game")
    async def dama_resign(self, ctx: commands.Context):
        game = db.get_active_board_game(ctx.guild.id, "dama", ctx.author.id)
        if not game:
            return await bg.notice(ctx, NO_GAME)
        headline = bg.conclude(ctx.guild.id, game, winner_id=bg.opponent_of(game, ctx.author.id), reason="resignation")
        game["status"] = "finished"
        await self.post_board(ctx.send, game, headline=headline)

    @dama_cmd.command(name="draw", description="Offer a draw or accept the one your opponent offered")
    async def dama_draw(self, ctx: commands.Context):
        game = db.get_active_board_game(ctx.guild.id, "dama", ctx.author.id)
        if not game:
            return await bg.notice(ctx, NO_GAME)

        me, opp = ctx.author.id, bg.opponent_of(game, ctx.author.id)
        if game["draw_offer_by"] == opp:
            headline = bg.conclude(ctx.guild.id, game, winner_id=None, reason="agreement")
            game["status"] = "finished"
            return await self.post_board(ctx.send, game, headline=headline)
        if game["draw_offer_by"] == me:
            return await bg.notice(ctx, f"You already offered a draw — waiting for {bg.mention(opp)}.")

        db.set_board_game_draw_offer(game["id"], me)
        await ctx.send(
            f"🤝 {bg.mention(me)} offers a draw. {bg.mention(opp)}: use `checkers draw` to accept, "
            "or simply play your move to decline."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Dama(bot))
