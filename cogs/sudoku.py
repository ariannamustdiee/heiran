from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import sudoku_generator as sg

REWARD_BY_DIFFICULTY = {
    "easy": 30,
    "medium": 60,
    "hard": 100,
    "expert": 150,
}

NO_GAME = "You don't have an active game. Start one with `sudoku new`."


class Sudoku(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_group(name="sudoku", description="Play sudoku", invoke_without_command=True)
    @commands.guild_only()
    async def sudoku(self, ctx: commands.Context):
        await ctx.send("Use `sudoku new`, `sudoku board`, `sudoku set`, `sudoku check` or `sudoku giveup`.")

    @sudoku.command(name="new", description="Start a new sudoku puzzle")
    @app_commands.describe(difficulty="How hard the puzzle should be")
    async def sudoku_new(self, ctx: commands.Context, difficulty: Literal["easy", "medium", "hard", "expert"] = "medium"):
        puzzle, solution = sg.generate_puzzle(difficulty)
        board = [row[:] for row in puzzle]
        db.save_sudoku_game(ctx.guild.id, ctx.author.id, puzzle, solution, board, difficulty)

        text = sg.board_to_str(board)
        embed = discord.Embed(
            title=f"🧩 New Sudoku ({difficulty})",
            description=(
                f"```\n{text}\n```\n"
                "Fill a cell with `sudoku set <row> <col> <value>` (all 1-9).\n"
                "Use `sudoku board` to see it again, `sudoku check` when you think you're done."
            ),
            color=discord.Color.green(),
        )
        await ctx.send(embed=embed)

    @sudoku.command(name="board", description="Show your current sudoku board")
    async def sudoku_board(self, ctx: commands.Context):
        game = db.get_sudoku_game(ctx.guild.id, ctx.author.id)
        if not game:
            await ctx.send(NO_GAME, ephemeral=True)
            return
        await ctx.send(f"```\n{sg.board_to_str(game['board'])}\n```")

    @sudoku.command(name="set", description="Fill in a cell of your sudoku board")
    @app_commands.describe(row="Row (1-9)", col="Column (1-9)", value="Value (1-9)")
    async def sudoku_set(self, ctx: commands.Context, row: commands.Range[int, 1, 9],
                         col: commands.Range[int, 1, 9], value: commands.Range[int, 1, 9]):
        game = db.get_sudoku_game(ctx.guild.id, ctx.author.id)
        if not game:
            await ctx.send(NO_GAME, ephemeral=True)
            return

        r, c = row - 1, col - 1
        if game["puzzle"][r][c] != 0:
            await ctx.send("That cell was already given at the start — pick an empty one.", ephemeral=True)
            return

        game["board"][r][c] = value
        db.update_sudoku_board(ctx.guild.id, ctx.author.id, game["board"])
        await ctx.send(f"```\n{sg.board_to_str(game['board'])}\n```")

    @sudoku.command(name="check", description="Check whether your sudoku is complete and correct")
    async def sudoku_check(self, ctx: commands.Context):
        game = db.get_sudoku_game(ctx.guild.id, ctx.author.id)
        if not game:
            await ctx.send(NO_GAME, ephemeral=True)
            return

        if not sg.is_full(game["board"]):
            await ctx.send("The board isn't full yet — keep filling it in with `sudoku set`.", ephemeral=True)
            return

        if sg.is_complete_and_correct(game["board"], game["solution"]):
            reward = REWARD_BY_DIFFICULTY.get(game["difficulty"], 60)
            new_total = db.add_points(ctx.guild.id, ctx.author.id, reward)
            db.delete_sudoku_game(ctx.guild.id, ctx.author.id)
            embed = discord.Embed(
                title="🎉 Solved!",
                description=(
                    f"Great job, {ctx.author.mention}! "
                    f"You earned **{reward}** points (total: {new_total})."
                ),
                color=discord.Color.green(),
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(
                "The board is full, but something's wrong — keep trying! (Use `sudoku board` to review it.)",
                ephemeral=True,
            )

    @sudoku.command(name="giveup", description="Abandon your current sudoku game")
    async def sudoku_giveup(self, ctx: commands.Context):
        game = db.get_sudoku_game(ctx.guild.id, ctx.author.id)
        if not game:
            await ctx.send("You don't have an active game.", ephemeral=True)
            return
        db.delete_sudoku_game(ctx.guild.id, ctx.author.id)
        await ctx.send("Game abandoned. Start a new one anytime with `sudoku new`.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Sudoku(bot))
