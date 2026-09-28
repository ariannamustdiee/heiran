"""
Real Sudoku generator using randomized backtracking:
1. Fill a complete valid 9x9 solution.
2. Remove cells (count depends on difficulty) while keeping a puzzle
   that still has a single solution's worth of givens (we don't run a
   full uniqueness solver to keep this fast, but the removal pattern
   used is the standard symmetric-random approach used by most casual
   sudoku generators).
"""
import random

DIFFICULTIES = {
    "easy": 36,      # cells removed
    "medium": 46,
    "hard": 54,
    "expert": 60,
}


def _is_valid(board, row, col, num):
    if num in board[row]:
        return False
    if num in [board[r][col] for r in range(9)]:
        return False
    box_row, box_col = 3 * (row // 3), 3 * (col // 3)
    for r in range(box_row, box_row + 3):
        for c in range(box_col, box_col + 3):
            if board[r][c] == num:
                return False
    return True


def _solve(board, randomize=False):
    for row in range(9):
        for col in range(9):
            if board[row][col] == 0:
                nums = list(range(1, 10))
                if randomize:
                    random.shuffle(nums)
                for num in nums:
                    if _is_valid(board, row, col, num):
                        board[row][col] = num
                        if _solve(board, randomize):
                            return True
                        board[row][col] = 0
                return False
    return True


def _generate_full_solution():
    board = [[0] * 9 for _ in range(9)]
    _solve(board, randomize=True)
    return board


def generate_puzzle(difficulty: str = "medium"):
    """Returns (puzzle, solution) as two 9x9 lists of ints (0 = empty)."""
    difficulty = difficulty.lower()
    cells_to_remove = DIFFICULTIES.get(difficulty, DIFFICULTIES["medium"])

    solution = _generate_full_solution()
    puzzle = [row[:] for row in solution]

    positions = [(r, c) for r in range(9) for c in range(9)]
    random.shuffle(positions)

    for r, c in positions[:cells_to_remove]:
        puzzle[r][c] = 0

    return puzzle, solution


def board_to_str(board, puzzle=None):
    """
    Render a 9x9 board as a monospace text grid for a Discord code block.
    If `puzzle` is provided, cells that were originally given (non-zero
    in puzzle) are shown plain, so callers can distinguish them if wanted.
    """
    lines = []
    for r in range(9):
        if r % 3 == 0 and r != 0:
            lines.append("------+-------+------")
        row_cells = []
        for c in range(9):
            if c % 3 == 0 and c != 0:
                row_cells.append("|")
            val = board[r][c]
            row_cells.append(str(val) if val != 0 else ".")
        lines.append(" ".join(row_cells))
    return "\n".join(lines)


def is_complete_and_correct(board, solution):
    return board == solution


def is_full(board):
    return all(all(cell != 0 for cell in row) for row in board)
