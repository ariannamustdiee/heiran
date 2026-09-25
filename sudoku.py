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


class Sudoku(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    group = app_commands.Group(name="sudoku", description="Play sudoku")

    @group.command(name="new", description="Start a new sudoku puzzle")
    @app_commands.describe(difficulty="How hard the puzzle should be")
    @app_commands.choices(
        difficulty=[
            app_commands.Choice(name="Easy", value="easy"),
            app_commands.Choice(name="Medium", value="medium"),
            app_commands.Choice(name="Hard", value="hard"),
            app_commands.Choice(name="Expert", value="expert"),
        ]
    )
    async def new_game(self, interaction: discord.Interaction, difficulty: app_commands.Choice[str] = None):
        diff = difficulty.value if difficulty else "medium"
        puzzle, solution = sg.generate_puzzle(diff)
        board = [row[:] for row in puzzle]

        db.save_sudoku_game(interaction.guild_id, interaction.user.id, puzzle, solution, board, diff)

        text = sg.board_to_str(board)
        embed = discord.Embed(
            title=f"🧩 New Sudoku ({diff})",
            description=(
                f"```\n{text}\n```\n"
                "Use `/sudoku set row:<1-9> col:<1-9> value:<1-9>` to fill a cell.\n"
                "Use `/sudoku board` to see it again, `/sudoku check` when you think you're done."
            ),
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed)

    @group.command(name="board", description="Show your current sudoku board")
    async def show_board(self, interaction: discord.Interaction):
        game = db.get_sudoku_game(interaction.guild_id, interaction.user.id)
        if not game:
            await interaction.response.send_message(
                "You don't have an active game. Start one with `/sudoku new`.", ephemeral=True
            )
            return
        text = sg.board_to_str(game["board"])
        await interaction.response.send_message(f"```\n{text}\n```")

    @group.command(name="set", description="Fill in a cell of your sudoku board")
    @app_commands.describe(row="Row (1-9)", col="Column (1-9)", value="Value (1-9)")
    async def set_cell(self, interaction: discord.Interaction, row: app_commands.Range[int, 1, 9],
                        col: app_commands.Range[int, 1, 9], value: app_commands.Range[int, 1, 9]):
        game = db.get_sudoku_game(interaction.guild_id, interaction.user.id)
        if not game:
            await interaction.response.send_message(
                "You don't have an active game. Start one with `/sudoku new`.", ephemeral=True
            )
            return

        r, c = row - 1, col - 1
        if game["puzzle"][r][c] != 0:
            await interaction.response.send_message(
                "That cell was already given at the start — pick an empty one.", ephemeral=True
            )
            return

        game["board"][r][c] = value
        db.update_sudoku_board(interaction.guild_id, interaction.user.id, game["board"])

        text = sg.board_to_str(game["board"])
        await interaction.response.send_message(f"```\n{text}\n```")

    @group.command(name="check", description="Check whether your sudoku is complete and correct")
    async def check(self, interaction: discord.Interaction):
        game = db.get_sudoku_game(interaction.guild_id, interaction.user.id)
        if not game:
            await interaction.response.send_message(
                "You don't have an active game. Start one with `/sudoku new`.", ephemeral=True
            )
            return

        if not sg.is_full(game["board"]):
            await interaction.response.send_message(
                "The board isn't full yet — keep filling it in with `/sudoku set`.", ephemeral=True
            )
            return

        if sg.is_complete_and_correct(game["board"], game["solution"]):
            reward = REWARD_BY_DIFFICULTY.get(game["difficulty"], 60)
            new_total = db.add_points(interaction.guild_id, interaction.user.id, reward)
            db.delete_sudoku_game(interaction.guild_id, interaction.user.id)
            embed = discord.Embed(
                title="🎉 Solved!",
                description=(
                    f"Great job, {interaction.user.mention}! "
                    f"You earned **{reward}** points (total: {new_total})."
                ),
                color=discord.Color.green(),
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                "The board is full, but something's wrong — keep trying! "
                "(Use `/sudoku board` to review it.)",
                ephemeral=True,
            )

    @group.command(name="giveup", description="Abandon your current sudoku game")
    async def give_up(self, interaction: discord.Interaction):
        game = db.get_sudoku_game(interaction.guild_id, interaction.user.id)
        if not game:
            await interaction.response.send_message("You don't have an active game.", ephemeral=True)
            return
        db.delete_sudoku_game(interaction.guild_id, interaction.user.id)
        await interaction.response.send_message("Game abandoned. Start a new one anytime with `/sudoku new`.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Sudoku(bot))
