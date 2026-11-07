"""
Pieces shared by the two-player board games (chess and dama): challenge buttons,
sides, finishing a game and paying the (limited) point reward.
"""
import random
import time

import discord

import database as db

# ----- point rewards (tune freely) -----
GAME_REWARD = {"chess": 60, "dama": 50}   # points for a win
MIN_PLIES_FOR_REWARD = 20                # a "ply" is one move by one side; stops instant-win farming
DAILY_REWARD_CAP = 3                     # rewarded wins per member per 24h (chess + dama together)
SAME_OPPONENT_DAILY_CAP = 1              # rewarded wins against the same opponent per 24h
CHALLENGE_TIMEOUT_SECONDS = 120

_pending = set()  # (guild_id, game_type, challenger_id) with an unanswered challenge


def mention(user_id: int) -> str:
    return f"<@{user_id}>"


def side_of(game: dict, user_id: int) -> str:
    return "white" if game["white_id"] == user_id else "black"


def opponent_of(game: dict, user_id: int) -> int:
    return game["black_id"] if game["white_id"] == user_id else game["white_id"]


def player_to_move(game: dict) -> int:
    return game["white_id"] if game["turn"] == "white" else game["black_id"]


async def notice(ctx, text: str):
    """Short private-ish message: ephemeral for slash commands, auto-deleted for text commands."""
    await ctx.send(text, ephemeral=True, delete_after=None if ctx.interaction else 12)


def conclude(guild_id: int, game: dict, *, winner_id, reason: str) -> str:
    """Closes the game in the database, pays the reward if allowed, returns the announcement text."""
    if winner_id is None:
        db.finish_board_game(game["id"], "draw", reason)
        return f"🤝 **Draw** — {reason}."

    loser_id = opponent_of(game, winner_id)
    result = "white" if winner_id == game["white_id"] else "black"
    amount = GAME_REWARD[game["game_type"]]
    day_ago = time.time() - 24 * 3600

    note = ""
    rewarded = False
    if game["moves_played"] < MIN_PLIES_FOR_REWARD:
        note = " No points: the game was too short."
    elif db.count_rewarded_board_wins(guild_id, winner_id, day_ago) >= DAILY_REWARD_CAP:
        note = f" No points: {DAILY_REWARD_CAP} rewarded wins per day is the limit."
    elif db.count_rewarded_board_wins(guild_id, winner_id, day_ago, against_id=loser_id) >= SAME_OPPONENT_DAILY_CAP:
        note = " No points: you already got a reward against this opponent today."
    else:
        total = db.add_points(guild_id, winner_id, amount)
        rewarded = True
        note = f" **+{amount} points** (total: {total})."

    db.finish_board_game(game["id"], result, reason, winner_id=winner_id, rewarded=rewarded)
    return f"🏆 {mention(winner_id)} wins by {reason}!{note}"


class ChallengeView(discord.ui.View):
    """Accept / Decline buttons shown to the challenged member."""

    def __init__(self, *, key, challenger: discord.Member, opponent: discord.Member, on_accept):
        super().__init__(timeout=CHALLENGE_TIMEOUT_SECONDS)
        self.key = key
        self.challenger = challenger
        self.opponent = opponent
        self.on_accept = on_accept
        self.message = None
        self.resolved = False

    def _release(self):
        self.resolved = True
        _pending.discard(self.key)
        self.stop()

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message(
                f"Only {self.opponent.display_name} can accept this challenge.", ephemeral=True
            )
            return
        if self.resolved:
            await interaction.response.send_message("This challenge is no longer open.", ephemeral=True)
            return
        self._release()
        await self.on_accept(interaction)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="✖️")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.opponent.id, self.challenger.id):
            await interaction.response.send_message("This challenge isn't yours.", ephemeral=True)
            return
        if self.resolved:
            await interaction.response.send_message("This challenge is no longer open.", ephemeral=True)
            return
        self._release()
        who = "declined" if interaction.user.id == self.opponent.id else "cancelled"
        await interaction.response.edit_message(
            content=f"❌ The challenge was {who} by {interaction.user.display_name}.", view=None
        )

    async def on_timeout(self):
        if self.resolved:
            return
        self.resolved = True
        _pending.discard(self.key)
        if self.message:
            try:
                await self.message.edit(content="⌛ The challenge expired without an answer.", view=None)
            except discord.HTTPException:
                pass


async def start_challenge(ctx, *, game_type: str, label: str, opponent: discord.Member,
                          color: str, initial_state: str, post_board):
    """Validates a challenge, shows the buttons and — once accepted — creates the game.
    `post_board(send, game)` is the game-specific coroutine that shows the starting position."""
    challenger = ctx.author
    guild_id = ctx.guild.id

    if opponent.bot:
        return await notice(ctx, "Bots don't play — challenge a member instead.")
    if opponent.id == challenger.id:
        return await notice(ctx, "You can't challenge yourself.")
    if db.get_active_board_game(guild_id, game_type, challenger.id):
        return await notice(ctx, f"You already have a {label} game running. Finish it first (`resign` ends it).")
    if db.get_active_board_game(guild_id, game_type, opponent.id):
        return await notice(ctx, f"{opponent.display_name} is already in a {label} game.")

    key = (guild_id, game_type, challenger.id)
    if key in _pending:
        return await notice(ctx, "You already have an open challenge — wait for an answer first.")
    _pending.add(key)

    chosen = color if color in ("white", "black") else random.choice(["white", "black"])
    white, black = (challenger, opponent) if chosen == "white" else (opponent, challenger)

    async def on_accept(interaction: discord.Interaction):
        if (db.get_active_board_game(guild_id, game_type, challenger.id)
                or db.get_active_board_game(guild_id, game_type, opponent.id)):
            await interaction.response.edit_message(
                content="One of you started another game in the meantime — challenge cancelled.", view=None
            )
            return
        game_id = db.create_board_game(guild_id, game_type, white.id, black.id, initial_state, ctx.channel.id)
        game = db.get_board_game(game_id)
        await interaction.response.edit_message(
            content=f"✅ {opponent.mention} accepted! ⚪ {white.mention} plays White, ⚫ {black.mention} plays Black.",
            view=None,
        )
        await post_board(interaction.followup.send, game)

    view = ChallengeView(key=key, challenger=challenger, opponent=opponent, on_accept=on_accept)
    try:
        view.message = await ctx.send(
            f"⚔️ {opponent.mention}, {challenger.mention} challenges you to **{label}**! "
            f"They'd play **{chosen.capitalize()}** — do you accept?",
            view=view,
        )
    except Exception:
        _pending.discard(key)
        raise
