import io
import logging
from typing import Literal

import chess
import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import boardgames as bg
from utils.boardimage import chess_text, render_chess

log = logging.getLogger("bot.chess")

NO_GAME = "You don't have an active chess game. Start one with `chess challenge @member`."

HELP_TEXT = (
    "**Chess** — play against another member.\n"
    "`chess challenge @member [white|black|random]` — invite someone\n"
    "`chess move <move>` — e.g. `e4`, `Nf3`, `exd5`, `O-O`, or `e2e4`\n"
    "`chess board` — show your game · `chess resign` — give up · `chess draw` — offer/accept a draw\n"
    "Promotions default to a queen (`e7e8n` to choose a knight)."
)


def load_game(game: dict):
    """Rebuilds the position from the saved move list. Returns (board, last_move, last_san)."""
    board = chess.Board()
    last_move, last_san = None, None
    for uci in game["state"].split():
        move = chess.Move.from_uci(uci)
        last_san = board.san(move)
        board.push(move)
        last_move = move
    return board, last_move, last_san


def parse_move(board: chess.Board, text: str):
    """Understands SAN (Nf3, exd5, O-O, e8=Q) and UCI (e2e4, e7e8q). Returns (move, error)."""
    text = text.strip()
    if not text:
        return None, "Write your move, e.g. `e4`, `Nf3`, `O-O` or `e2e4`."

    ambiguous = False
    variants = [text, text.replace("0", "O")]
    if text[0] in "nrqk":
        variants.append(text[0].upper() + text[1:])
    if text[0] == "b":
        variants.append("B" + text[1:])
    if text[0] in "ACDEFGH":
        variants.append(text[0].lower() + text[1:])  # "E4" -> "e4"
    for variant in variants:
        try:
            return board.parse_san(variant), None
        except chess.AmbiguousMoveError:
            ambiguous = True
        except ValueError:
            continue
    if ambiguous:
        return None, "That move is ambiguous — say which piece, e.g. `Nbd2` or `R1e2`, or use `e2e4` style."

    uci = text.lower().replace("-", "").replace(" ", "").replace("x", "")
    for candidate in (uci, uci + "q" if len(uci) == 4 else None):
        if not candidate:
            continue
        try:
            move = chess.Move.from_uci(candidate)
        except ValueError:
            continue
        if move in board.legal_moves:
            return move, None

    return None, f"`{text}` isn't a legal move here. Try `e4`, `Nf3`, `O-O` or `e2e4`."


def _describe_outcome(outcome: chess.Outcome):
    """-> (winner_color or None, reason text)"""
    term = outcome.termination
    if term == chess.Termination.CHECKMATE:
        return outcome.winner, "checkmate"
    reasons = {
        chess.Termination.STALEMATE: "stalemate",
        chess.Termination.INSUFFICIENT_MATERIAL: "insufficient material",
        chess.Termination.SEVENTYFIVE_MOVES: "the 75-move rule",
        chess.Termination.FIVEFOLD_REPETITION: "fivefold repetition",
    }
    return None, reasons.get(term, "the rules of chess")


class ChessGame(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- showing the board ----------

    async def post_board(self, send, game: dict, *, headline: str = "", ping: bool = True):
        board, last_move, last_san = load_game(game)
        finished = game["status"] != "active"

        lines = [f"⚪ White: {bg.mention(game['white_id'])}", f"⚫ Black: {bg.mention(game['black_id'])}"]
        if last_san:
            lines.append(f"Last move: **{last_san}**")
        if headline:
            lines.append("")
            lines.append(headline)
        elif board.is_check() and not finished:
            lines.append("")
            lines.append("**Check!**")

        embed = discord.Embed(title="♟️ Chess", color=discord.Color.dark_gold())
        file = None
        try:
            file = discord.File(io.BytesIO(render_chess(board, last_move)), filename="board.png")
            embed.set_image(url="attachment://board.png")
        except Exception:
            log.exception("Could not draw the chess board, falling back to text")
            lines.append(f"```\n{chess_text(board)}\n```")
        embed.description = "\n".join(lines)

        if finished:
            embed.set_footer(text="Game over")
            content = None
        else:
            side = game["turn"]
            embed.set_footer(text=f"Move {board.fullmove_number} • {side.capitalize()} to move")
            content = f"{bg.mention(bg.player_to_move(game))} it's your move ({side})." if ping else None

        kwargs = {"embed": embed}
        if file:
            kwargs["file"] = file
        await send(content, **kwargs)

    # ---------- commands ----------

    @commands.hybrid_group(name="chess", description="Play chess against another member", invoke_without_command=True)
    @commands.guild_only()
    async def chess_cmd(self, ctx: commands.Context):
        await ctx.send(HELP_TEXT)

    @chess_cmd.command(name="challenge", description="Challenge a member to a game of chess")
    @app_commands.describe(opponent="Who you want to play against", color="The side you want to play")
    async def chess_challenge(self, ctx: commands.Context, opponent: discord.Member,
                              color: Literal["white", "black", "random"] = "random"):
        await bg.start_challenge(
            ctx, game_type="chess", label="chess", opponent=opponent, color=color,
            initial_state="", post_board=self.post_board,
        )

    @chess_cmd.command(name="move", description="Play a move in your game")
    @app_commands.describe(notation="Your move, e.g. e4, Nf3, O-O or e2e4")
    async def chess_move(self, ctx: commands.Context, *, notation: str):
        game = db.get_active_board_game(ctx.guild.id, "chess", ctx.author.id)
        if not game:
            return await bg.notice(ctx, NO_GAME)
        if bg.side_of(game, ctx.author.id) != game["turn"]:
            return await bg.notice(ctx, f"It's not your turn — waiting for {bg.mention(bg.player_to_move(game))}.")

        board, _, _ = load_game(game)
        move, error = parse_move(board, notation)
        if move is None:
            return await bg.notice(ctx, error)

        board.push(move)
        game["state"] = f"{game['state']} {move.uci()}".strip()
        game["turn"] = "white" if board.turn == chess.WHITE else "black"
        game["moves_played"] += 1
        game["last_move"] = move.uci()
        game["draw_offer_by"] = None
        db.save_board_game(game["id"], game["state"], game["turn"], game["moves_played"], game["last_move"])

        headline = ""
        outcome = board.outcome()
        if outcome:
            winner_color, reason = _describe_outcome(outcome)
            winner_id = None
            if winner_color is not None:
                winner_id = game["white_id"] if winner_color == chess.WHITE else game["black_id"]
            headline = bg.conclude(ctx.guild.id, game, winner_id=winner_id, reason=reason)
            game["status"] = "finished"
        await self.post_board(ctx.send, game, headline=headline)

    @chess_cmd.command(name="board", description="Show the board of your current game")
    async def chess_board(self, ctx: commands.Context):
        game = db.get_active_board_game(ctx.guild.id, "chess", ctx.author.id)
        if not game:
            return await bg.notice(ctx, NO_GAME)
        await self.post_board(ctx.send, game)

    @chess_cmd.command(name="resign", description="Resign your current game")
    async def chess_resign(self, ctx: commands.Context):
        game = db.get_active_board_game(ctx.guild.id, "chess", ctx.author.id)
        if not game:
            return await bg.notice(ctx, NO_GAME)
        headline = bg.conclude(ctx.guild.id, game, winner_id=bg.opponent_of(game, ctx.author.id), reason="resignation")
        game["status"] = "finished"
        await self.post_board(ctx.send, game, headline=headline)

    @chess_cmd.command(name="draw", description="Offer a draw, accept the offer, or claim one when the rules allow it")
    async def chess_draw(self, ctx: commands.Context):
        game = db.get_active_board_game(ctx.guild.id, "chess", ctx.author.id)
        if not game:
            return await bg.notice(ctx, NO_GAME)

        me, opp = ctx.author.id, bg.opponent_of(game, ctx.author.id)
        board, _, _ = load_game(game)

        reason = None
        if board.can_claim_draw():
            reason = "a claim (threefold repetition or the 50-move rule)"
        elif game["draw_offer_by"] == opp:
            reason = "agreement"
        elif game["draw_offer_by"] == me:
            return await bg.notice(ctx, f"You already offered a draw — waiting for {bg.mention(opp)}.")

        if reason:
            headline = bg.conclude(ctx.guild.id, game, winner_id=None, reason=reason)
            game["status"] = "finished"
            return await self.post_board(ctx.send, game, headline=headline)

        db.set_board_game_draw_offer(game["id"], me)
        await ctx.send(
            f"🤝 {bg.mention(me)} offers a draw. {bg.mention(opp)}: use `chess draw` to accept, "
            "or simply play your move to decline."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ChessGame(bot))
