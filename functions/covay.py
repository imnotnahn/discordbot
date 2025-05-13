import discord
from discord.ext import commands
from typing import Dict, List, Tuple, Optional

class CoVayGame:
    """Represents a Go (Cờ vây) game instance with basic captures and rules."""
    def __init__(self, black_player: discord.Member, white_player: discord.Member, size: int = 19):
        """Initialize the Go board and essential game variables."""
        self.size = size
        self.board = [[0 for _ in range(size)] for _ in range(size)]  # 0=empty, 1=black, 2=white
        self.black_player = black_player
        self.white_player = white_player
        self.current_player = black_player  # Black goes first
        self.game_over = False
        self.winner = None
        self.last_move = None
        self.ko_point = None
        self.captured_black = 0
        self.captured_white = 0
        self.consecutive_passes = 0

    def is_valid_move(self, x: int, y: int, player_color: int) -> Tuple[bool, str]:
        """Check if placing a stone at (x, y) is valid for the current player."""
        if not (0 <= x < self.size and 0 <= y < self.size):
            return False, "Position is outside the board"

        if self.board[x][y] != 0:
            return False, "That position is already occupied"

        if (x, y) == self.ko_point:
            return False, "Cannot play at the ko point"

        # Temporarily place the stone for checks
        self.board[x][y] = player_color
        opposing_color = 3 - player_color
        captured_groups = []

        # Check if move captures any opponent stones
        for nx, ny in [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]:
            if 0 <= nx < self.size and 0 <= ny < self.size:
                if self.board[nx][ny] == opposing_color:
                    group = self.find_connected_group(nx, ny)
                    if self.count_liberties(group) == 0:
                        captured_groups.append(group)

        # If move captures stones, it's valid
        if captured_groups:
            self.board[x][y] = 0
            return True, ""

        # Otherwise check for suicide
        group = self.find_connected_group(x, y)
        liberties = self.count_liberties(group)

        # Undo the temporary move
        self.board[x][y] = 0

        if liberties == 0:
            return False, "Suicide moves are not allowed"

        return True, ""

    def find_connected_group(self, x: int, y: int) -> set:
        """Return all stones connected to (x, y) with the same color."""
        color = self.board[x][y]
        group = set()
        queue = [(x, y)]
        visited = {(x, y)}

        while queue:
            cx, cy = queue.pop(0)
            group.add((cx, cy))
            for nx, ny in [(cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)]:
                if 0 <= nx < self.size and 0 <= ny < self.size:
                    if self.board[nx][ny] == color and (nx, ny) not in visited:
                        queue.append((nx, ny))
                        visited.add((nx, ny))

        return group

    def count_liberties(self, group: set) -> int:
        """Count the number of empty adjacent points (liberties) for a group."""
        liberties = set()
        for x, y in group:
            for nx, ny in [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]:
                if 0 <= nx < self.size and 0 <= ny < self.size:
                    if self.board[nx][ny] == 0:
                        liberties.add((nx, ny))
        return len(liberties)

    def make_move(self, x: int, y: int) -> Tuple[bool, str]:
        """Place a stone at (x, y) if valid and handle captures."""
        player_color = 1 if self.current_player == self.black_player else 2
        valid, message = self.is_valid_move(x, y, player_color)
        if not valid:
            return False, message

        # Reset pass count and place the stone
        self.consecutive_passes = 0
        self.board[x][y] = player_color
        self.last_move = (x, y)

        # Capture any opponent stones
        opposing_color = 3 - player_color
        captured_groups = []
        for nx, ny in [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]:
            if 0 <= nx < self.size and 0 <= ny < self.size:
                if self.board[nx][ny] == opposing_color:
                    group = self.find_connected_group(nx, ny)
                    if self.count_liberties(group) == 0:
                        captured_groups.append(group)

        captured_stones = 0
        for group in captured_groups:
            for cx, cy in group:
                self.board[cx][cy] = 0
                captured_stones += 1

        if player_color == 1:
            self.captured_white += captured_stones
        else:
            self.captured_black += captured_stones

        # Handle ko (single-stone capture)
        self.ko_point = None
        if len(captured_groups) == 1 and len(captured_groups[0]) == 1:
            cx, cy = next(iter(captured_groups[0]))
            # Check if the captured stone was alone
            if all(
                self.board[nx][ny] != player_color
                for nx, ny in [(cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)]
                if 0 <= nx < self.size and 0 <= ny < self.size
            ):
                self.ko_point = (cx, cy)

        # Switch player
        self.current_player = (
            self.white_player if self.current_player == self.black_player
            else self.black_player
        )

        msg_extra = f" and captured {captured_stones} stones" if captured_stones else ""
        return True, f"{'Black' if player_color == 1 else 'White'} placed a stone at ({x},{y}){msg_extra}"

    def pass_move(self) -> Tuple[bool, str]:
        """Pass the turn, checking if the game is over after two consecutive passes."""
        self.consecutive_passes += 1
        if self.consecutive_passes >= 2:
            self.game_over = True

        self.current_player = (
            self.white_player if self.current_player == self.black_player
            else self.black_player
        )
        return True, f"{'Black' if self.current_player == self.white_player else 'White'} passed"

    def render_board(self) -> str:
        """Render the current board state in a grid with row and column numbers."""
        BLACK_STONE = "●"
        WHITE_STONE = "○"
        EMPTY = "·"
        header = "     " + "".join(f" {y+1:2d} " for y in range(self.size))
        rows = [header]
        separator = "    +" + "---+" * self.size
        rows.append(separator)

        for x in range(self.size):
            row = f" {x+1:2d} |"
            for y in range(self.size):
                cell = self.board[x][y]
                if cell == 1:
                    row += f" {BLACK_STONE} |"
                elif cell == 2:
                    row += f" {WHITE_STONE} |"
                else:
                    row += f" {EMPTY} |"
            rows.append(row)
            rows.append(separator)

        return "\n".join(rows)


class GoCog(commands.Cog):
    """Discord Cog for managing Go (Cờ vây) games."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_games: Dict[str, CoVayGame] = {}

    @commands.hybrid_command(
        name="covay_play",
        description="Start a Go (Cờ vây) game with another player"
    )
    async def covay(self, ctx: commands.Context, player1: discord.Member, player2: discord.Member, size: int):
        """Begin a new Go game with a given board size."""
        if player1.bot or player2.bot:
            return await ctx.send("You cannot include bots in the game!")

        if player1 == player2:
            return await ctx.send("You cannot play against yourself!")

        # Check if either player is already in a game
        for game_id, game in self.active_games.items():
            if player1 in [game.black_player, game.white_player] or player2 in [game.black_player, game.white_player]:
                return await ctx.send("One or both players are already in a game!")

        if size not in [9, 13, 19]:
            return await ctx.send("Board size must be 9, 13, or 19!")

        # Create a new game
        new_game = CoVayGame(black_player=player1, white_player=player2, size=size)
        game_id = f"{ctx.guild.id}-{ctx.channel.id}-{player1.id}-{player2.id}"
        self.active_games[game_id] = new_game

        embed = discord.Embed(
            title=f"Cờ vây Game Started - {size}x{size}",
            description=f"Game started between {player1.mention} (Black) and {player2.mention} (White)",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="How to Play",
            value=(
                "• `/covay @player1 @player2 [size]` to start a game (size must be 9,13,19).\n"
                "• `/play [x] [y]` to place a stone (coordinates start at 1).\n"
                "• `/pass` to pass your turn.\n"
                "• `/resign_covay` to resign.\n"
                "• The game ends when both players pass consecutively."
            ),
            inline=False
        )
        embed.add_field(
            name="Current Player",
            value=f"{player1.mention} (Black)",
            inline=False
        )

        board_text = new_game.render_board()
        await ctx.send(embed=embed)
        await ctx.send(f"```\n{board_text}\n```")

    @commands.hybrid_command(
        name="covay_move",
        description="Place a stone in an active Go game"
    )
    async def play(self, ctx: commands.Context, x: int, y: int):
        """Place a stone on the board at (x, y)."""
        player_game, game_id = None, None

        for gid, game in self.active_games.items():
            if ctx.author in [game.black_player, game.white_player]:
                player_game, game_id = game, gid
                break

        if not player_game:
            return await ctx.send("You are not in an active game! Start one with `/covay @player1 @player2`.")

        if player_game.current_player != ctx.author:
            return await ctx.send(f"It's not your turn! Waiting for {player_game.current_player.mention} to move.")

        board_x, board_y = x - 1, y - 1
        success, message = player_game.make_move(board_x, board_y)
        if not success:
            return await ctx.send(f"Invalid move: {message}")

        board_text = player_game.render_board()
        await ctx.send(message)
        await ctx.send(f"```\n{board_text}\n```")

        if player_game.game_over:
            await ctx.send("Game over by consecutive passes. (Scoring not implemented.)")
        else:
            current_player = "Black" if player_game.current_player == player_game.black_player else "White"
            await ctx.send(f"It's now {player_game.current_player.mention}'s turn ({current_player}).")

    @commands.hybrid_command(
        name="covay_pass",
        description="Pass your turn in an active Go game"
    )
    async def pass_turn(self, ctx: commands.Context):
        """Pass your current turn."""
        player_game, game_id = None, None

        for gid, game in self.active_games.items():
            if ctx.author in [game.black_player, game.white_player]:
                player_game, game_id = game, gid
                break

        if not player_game:
            return await ctx.send("You are not in an active game!")

        if player_game.current_player != ctx.author:
            return await ctx.send(f"It's not your turn! Waiting for {player_game.current_player.mention} to move.")

        success, message = player_game.pass_move()
        await ctx.send(f"{ctx.author.mention} passes their turn.")

        if player_game.game_over:
            await ctx.send("Both players have passed. The game is over! (No scoring implemented.)")
        else:
            current_player = "Black" if player_game.current_player == player_game.black_player else "White"
            await ctx.send(f"It's now {player_game.current_player.mention}'s turn ({current_player}).")

    @commands.hybrid_command(
        name="covay_resign",
        description="Resign from your current Go game",
        aliases=["go_resign"]
    )
    async def resign_covay(self, ctx: commands.Context):
        """Resign from the game, ending it immediately."""
        player_game, game_id = None, None

        for gid, game in self.active_games.items():
            if ctx.author in [game.black_player, game.white_player]:
                player_game, game_id = game, gid
                break

        if not player_game:
            return await ctx.send("You are not in an active Go game!")

        if ctx.author == player_game.black_player:
            player_game.winner = player_game.white_player
        else:
            player_game.winner = player_game.black_player

        player_game.game_over = True
        await ctx.send(f"**{ctx.author.display_name}** has resigned from the Go game!")
        await ctx.send(f"🎉 Game Over! {player_game.winner.mention} wins! 🎉")

        del self.active_games[game_id]


async def setup(bot: commands.Bot):
    """Setup function required by discord.py to load the cog."""
    await bot.add_cog(GoCog(bot))