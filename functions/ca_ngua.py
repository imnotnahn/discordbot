import discord
from discord.ext import commands
from typing import Dict, List, Tuple, Optional
import random
import asyncio

# Colors for the game - in order: Red, Green, Blue, Yellow
COLORS = ["🔴", "🟢", "🔵", "🟡"]
COLOR_NAMES = ["Red", "Green", "Blue", "Yellow"]

class LudoGame:
    """Represents a Cờ Cá Ngựa (Ludo) game instance."""
    
    def __init__(self, players: List[discord.Member]):
        """Initialize a new Ludo game with the given players."""
        self.players = players
        self.current_player_idx = 0
        self.current_player = players[0]
        self.game_over = False
        self.winner = None
        self.last_roll = 0
        
        # Game board representation
        # - Each player has 4 pieces
        # - Each piece can be in: home (-1), start (0), or on the track (1-56)
        # - 57 represents the final position (safe)
        self.pieces = {}
        for i, player in enumerate(players):
            self.pieces[player.id] = [-1, -1, -1, -1]  # All pieces start in home
        
        # Track who has already won
        self.finished_players = []
        
        # Track whether player has had an extra turn due to rolling a 6
        self.extra_turn = False
        
        # Path offsets for each player
        self.path_offsets = [0, 14, 28, 42]  # Red starts at 0, Green at 14, etc.
        
        # Flag to track if player rolled a 6 (can move pieces out of home)
        self.rolled_six = False

    def roll_dice(self) -> int:
        """Roll a dice and return the result (1-6)."""
        self.last_roll = random.randint(1, 6)
        self.rolled_six = (self.last_roll == 6)
        return self.last_roll
    
    def can_move_piece(self, piece_idx: int) -> bool:
        """Check if the given piece can be moved."""
        player_id = self.current_player.id
        piece_pos = self.pieces[player_id][piece_idx]
        
        # If piece is in home, need a 6 to move out
        if piece_pos == -1:
            return self.rolled_six
        
        # If piece would go beyond finish, not a valid move
        if piece_pos + self.last_roll > 57:
            return False
            
        # Check if destination is blocked by own piece
        player_offset = self.path_offsets[self.players.index(self.current_player)]
        destination = piece_pos + self.last_roll
        
        if destination < 51:  # Before final straight
            for i, pos in enumerate(self.pieces[player_id]):
                if i != piece_idx and pos != -1 and pos != 57:
                    # Convert to absolute board position
                    abs_pos = (pos + player_offset) % 56
                    abs_dest = (destination + player_offset) % 56
                    if abs_pos == abs_dest:
                        return False
            
        return True
    
    def get_movable_pieces(self) -> List[int]:
        """Return indices of pieces that can be moved."""
        return [i for i in range(4) if self.can_move_piece(i)]
    
    def move_piece(self, piece_idx: int) -> Tuple[bool, str, List[Tuple[int, int]]]:
        """
        Move the specified piece. Returns (success, message, captures)
        where captures is a list of (player_index, piece_index) tuples.
        """
        if not self.can_move_piece(piece_idx):
            return False, "Cannot move this piece", []
        
        player_id = self.current_player.id
        player_idx = self.players.index(self.current_player)
        piece_pos = self.pieces[player_id][piece_idx]
        
        # Handle moving out of home
        if piece_pos == -1:
            self.pieces[player_id][piece_idx] = 0
            captures = self.check_capture(0, player_idx)
            return True, f"Piece {piece_idx+1} moved out to start", captures
        
        # Regular move
        new_pos = piece_pos + self.last_roll
        self.pieces[player_id][piece_idx] = new_pos
        
        # Check if piece has finished
        if new_pos == 57:
            message = f"Piece {piece_idx+1} has reached home safely!"
            
            # Check if player has finished the game
            if all(pos == 57 for pos in self.pieces[player_id]):
                self.finished_players.append(self.current_player)
                if len(self.finished_players) == len(self.players) - 1:
                    # Game is over when all but one player has finished
                    self.game_over = True
                    self.winner = self.finished_players[0]  # First player to finish wins
            
            return True, message, []
        
        # Check for captures
        captures = self.check_capture(new_pos, player_idx)
        
        return True, f"Piece {piece_idx+1} moved to position {new_pos}", captures
    
    def check_capture(self, pos: int, player_idx: int) -> List[Tuple[int, int]]:
        """Check if a piece at pos captures any opponent pieces. Return list of captures."""
        # Can't capture on safe spots (multiples of 14)
        if pos == 0 or pos % 14 == 0:
            return []
            
        captures = []
        player_offset = self.path_offsets[player_idx]
        abs_pos = (pos + player_offset) % 56
        
        # Check if any opponent pieces are at this position
        for opp_idx, player in enumerate(self.players):
            if opp_idx == player_idx:
                continue  # Skip current player
                
            opp_offset = self.path_offsets[opp_idx]
            
            for piece_idx, piece_pos in enumerate(self.pieces[player.id]):
                if piece_pos == -1 or piece_pos == 57:
                    continue  # Skip home and finished pieces
                
                # Convert opponent piece position to absolute board position
                opp_abs_pos = (piece_pos + opp_offset) % 56
                
                if opp_abs_pos == abs_pos:
                    # Capture!
                    self.pieces[player.id][piece_idx] = -1  # Send back to home
                    captures.append((opp_idx, piece_idx))
        
        return captures
    
    def next_turn(self):
        """Move to the next player's turn, handling 6s (extra turns)."""
        if self.rolled_six and not self.extra_turn:
            # Player gets another turn for rolling a 6
            self.extra_turn = True
            return
            
        # Reset extra turn flag
        self.extra_turn = False
        
        # Find next player who hasn't finished
        next_idx = self.current_player_idx
        while True:
            next_idx = (next_idx + 1) % len(self.players)
            if self.players[next_idx] not in self.finished_players:
                break
                
        self.current_player_idx = next_idx
        self.current_player = self.players[next_idx]
    
    def render_board(self) -> str:
        """
        Render the current game state as a string representation of the board.
        """
        # Create a 15x15 grid representation
        board = [[" " for _ in range(15)] for _ in range(15)]
        
        # Define the board layout
        # First, mark all valid cells
        
        # Horizontal paths
        for y in [6, 8]:
            for x in range(15):
                board[y][x] = "·"
        
        # Vertical paths
        for x in [6, 8]:
            for y in range(15):
                board[y][x] = "·"
        
        # Home columns
        for color_idx in range(4):
            if color_idx == 0:  # Red
                for i in range(1, 6):
                    board[7][i] = "·"
            elif color_idx == 1:  # Green
                for i in range(1, 6):
                    board[i][7] = "·"
            elif color_idx == 2:  # Blue
                for i in range(9, 14):
                    board[7][i] = "·"
            elif color_idx == 3:  # Yellow
                for i in range(9, 14):
                    board[i][7] = "·"
        
        # Starting positions (different for each color)
        start_positions = [(6, 1), (1, 8), (8, 13), (13, 6)]
        
        # Home bases (corners)
        home_areas = [
            [(2, 2), (2, 3), (3, 2), (3, 3)],  # Red
            [(2, 11), (2, 12), (3, 11), (3, 12)],  # Green
            [(11, 11), (11, 12), (12, 11), (12, 12)],  # Blue
            [(11, 2), (11, 3), (12, 2), (12, 3)]  # Yellow
        ]
        
        # Place symbols for each player's home and end areas
        for i, color in enumerate(COLORS):
            # Mark start position
            start_y, start_x = start_positions[i]
            board[start_y][start_x] = "S" + str(i)
            
            # Mark home base
            for y, x in home_areas[i]:
                board[y][x] = "H" + str(i)
        
        # Now place the pieces on the board
        path_coords = [
            # Common track coordinates (simplified)
            (6, 0), (6, 1), (6, 2), (6, 3), (6, 4), (6, 5),
            (5, 6), (4, 6), (3, 6), (2, 6), (1, 6), (0, 6),
            (0, 8), (1, 8), (2, 8), (3, 8), (4, 8), (5, 8),
            (6, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14),
            (8, 14), (8, 13), (8, 12), (8, 11), (8, 10), (8, 9),
            (9, 8), (10, 8), (11, 8), (12, 8), (13, 8), (14, 8),
            (14, 6), (13, 6), (12, 6), (11, 6), (10, 6), (9, 6),
            (8, 5), (8, 4), (8, 3), (8, 2), (8, 1), (8, 0),
            (6, 0)  # Loop back
        ]
        
        # Paths to home (final stretch for each color)
        home_paths = [
            [(7, 1), (7, 2), (7, 3), (7, 4), (7, 5)],  # Red
            [(1, 7), (2, 7), (3, 7), (4, 7), (5, 7)],  # Green
            [(7, 13), (7, 12), (7, 11), (7, 10), (7, 9)],  # Blue
            [(13, 7), (12, 7), (11, 7), (10, 7), (9, 7)]   # Yellow
        ]
        
        # Place pieces on the board
        for player_idx, player in enumerate(self.players):
            color = COLORS[player_idx]
            offset = self.path_offsets[player_idx]
            
            # Place each piece
            for piece_idx, pos in enumerate(self.pieces[player.id]):
                piece_symbol = color + str(piece_idx + 1)
                
                if pos == -1:  # In home base
                    y, x = home_areas[player_idx][piece_idx]
                    board[y][x] = piece_symbol
                elif pos == 0:  # At start
                    y, x = start_positions[player_idx]
                    board[y][x] = piece_symbol
                elif pos == 57:  # Finished
                    # Center of board for finished pieces
                    if player_idx == 0:
                        board[7][6] = piece_symbol
                    elif player_idx == 1:
                        board[6][7] = piece_symbol
                    elif player_idx == 2:
                        board[7][8] = piece_symbol
                    else:
                        board[8][7] = piece_symbol
                elif pos > 50:  # In home stretch
                    idx = pos - 51
                    if idx < len(home_paths[player_idx]):
                        y, x = home_paths[player_idx][idx]
                        board[y][x] = piece_symbol
                else:  # On the main track
                    abs_pos = (pos + offset) % 52
                    if abs_pos < len(path_coords):
                        y, x = path_coords[abs_pos]
                        board[y][x] = piece_symbol
        
        # Convert the board to a string
        rows = []
        for i, row in enumerate(board):
            rows.append("".join(f" {cell:^3}" for cell in row))
        
        return "```\n" + "\n".join(rows) + "\n```"

    def player_status(self) -> str:
        """Return a string showing the status of each player's pieces."""
        status = []
        for i, player in enumerate(self.players):
            pieces_status = []
            
            for j, pos in enumerate(self.pieces[player.id]):
                if pos == -1:
                    status_text = "at home"
                elif pos == 0:
                    status_text = "at start"
                elif pos == 57:
                    status_text = "finished"
                elif pos > 50:
                    status_text = f"in final stretch ({pos-50}/7)"
                else:
                    status_text = f"on space {pos}"
                
                pieces_status.append(f"Piece {j+1}: {status_text}")
            
            status.append(f"{COLORS[i]} **{player.display_name}**: " + 
                         ", ".join(pieces_status))
        
        return "\n".join(status)


class LudoCog(commands.Cog):
    """Discord Cog for managing Cờ Cá Ngựa (Ludo) games."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_games: Dict[str, LudoGame] = {}
    
    @commands.hybrid_command(
        name="cangua_play",
        description="Start a Cờ Cá Ngựa (Ludo) game with 2-4 players"
    )
    async def start_cangua(self, ctx: commands.Context, player1: discord.Member, 
                         player2: discord.Member, player3: Optional[discord.Member] = None, 
                         player4: Optional[discord.Member] = None):
        """Begin a new Cờ Cá Ngựa (Ludo) game."""
        players = [player1, player2]
        
        if player3:
            players.append(player3)
        if player4:
            players.append(player4)
            
        # Check for bots
        if any(player.bot for player in players):
            return await ctx.send("You cannot include bots in the game!")
        
        # Check for duplicates
        if len(set(player.id for player in players)) != len(players):
            return await ctx.send("Each player must be unique!")
        
        # Check if players are already in a game
        for player in players:
            for game_id, game in self.active_games.items():
                if player in game.players:
                    return await ctx.send(f"{player.mention} is already in a game!")
        
        # Create game ID
        game_id = f"{ctx.guild.id}-{ctx.channel.id}-{'-'.join(str(p.id) for p in players)}"
        
        # Create the game
        new_game = LudoGame(players)
        self.active_games[game_id] = new_game
        
        # Create embed
        embed = discord.Embed(
            title="Cờ Cá Ngựa Game Started",
            description="A new game has been started!",
            color=discord.Color.blue()
        )
        
        # Add player info
        player_info = []
        for i, player in enumerate(players):
            player_info.append(f"{COLORS[i]} {player.mention} ({COLOR_NAMES[i]})")
        
        embed.add_field(
            name="Players",
            value="\n".join(player_info),
            inline=False
        )
        
        embed.add_field(
            name="How to Play",
            value=(
                "• `/cangua_roll` - Roll the dice on your turn\n"
                "• `/cangua_move [piece]` - Move a piece (1-4)\n"
                "• `/cangua_resign` - Resign from the game\n"
                "• Roll a 6 to move pieces out of home\n"
                "• Landing on an opponent's piece sends it back home\n"
                "• First player to get all pieces to the end wins"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Current Turn",
            value=f"{COLORS[0]} {players[0].mention}'s turn to roll",
            inline=False
        )
        
        # Send initial board
        await ctx.send(embed=embed)
        board = new_game.render_board()
        await ctx.send(board)
        
    @commands.hybrid_command(
        name="cangua_roll",
        description="Roll the dice in your Cờ Cá Ngựa game"
    )
    async def roll_dice(self, ctx: commands.Context):
        """Roll the dice for your turn."""
        player_game, game_id = None, None
        
        # Find the player's active game
        for gid, game in self.active_games.items():
            if ctx.author in game.players:
                player_game, game_id = game, gid
                break
                
        if not player_game:
            return await ctx.send("You are not in an active game!")
            
        if player_game.current_player != ctx.author:
            return await ctx.send(f"It's not your turn! Waiting for {player_game.current_player.mention} to play.")
        
        # Roll the dice
        roll = player_game.roll_dice()
        
        # Send dice result
        dice_emojis = {
            1: "1️⃣",
            2: "2️⃣",
            3: "3️⃣",
            4: "4️⃣",
            5: "5️⃣",
            6: "6️⃣"
        }
        
        color_idx = player_game.players.index(ctx.author)
        color = COLORS[color_idx]
        
        # Check if player can move any pieces
        movable_pieces = player_game.get_movable_pieces()
        
        if not movable_pieces:
            await ctx.send(f"{color} {ctx.author.mention} rolled a {dice_emojis[roll]} but cannot move any pieces!")
            
            # Move to next player
            player_game.next_turn()
            next_player = player_game.current_player
            next_color = COLORS[player_game.players.index(next_player)]
            
            await ctx.send(f"It's now {next_color} {next_player.mention}'s turn to roll.")
            return
            
        # Player can move
        if roll == 6:
            message = f"{color} {ctx.author.mention} rolled a {dice_emojis[roll]} and gets an extra turn!"
        else:
            message = f"{color} {ctx.author.mention} rolled a {dice_emojis[roll]}!"
            
        message += f"\nYou can move piece(s): {', '.join(str(i+1) for i in movable_pieces)}"
        message += "\nUse `/cangua_move [piece]` to move a piece."
        
        await ctx.send(message)
        
    @commands.hybrid_command(
        name="cangua_move",
        description="Move a piece in your Cờ Cá Ngựa game"
    )
    async def move_piece(self, ctx: commands.Context, piece: int):
        """Move a piece based on your dice roll."""
        if piece < 1 or piece > 4:
            return await ctx.send("Piece number must be between 1 and 4.")
            
        player_game, game_id = None, None
        
        # Find the player's active game
        for gid, game in self.active_games.items():
            if ctx.author in game.players:
                player_game, game_id = game, gid
                break
                
        if not player_game:
            return await ctx.send("You are not in an active game!")
            
        if player_game.current_player != ctx.author:
            return await ctx.send(f"It's not your turn! Waiting for {player_game.current_player.mention} to play.")
        
        # Get piece index (0-based)
        piece_idx = piece - 1
        
        # Check if this piece can be moved
        if not player_game.can_move_piece(piece_idx):
            return await ctx.send(f"You cannot move piece {piece} with your current roll!")
        
        # Move the piece
        success, message, captures = player_game.move_piece(piece_idx)
        
        if not success:
            return await ctx.send(message)
            
        color_idx = player_game.players.index(ctx.author)
        color = COLORS[color_idx]
        
        # Handle captures
        capture_messages = []
        for opp_idx, piece_idx in captures:
            opp_player = player_game.players[opp_idx]
            opp_color = COLORS[opp_idx]
            capture_messages.append(f"{color} captured {opp_color} {opp_player.mention}'s piece {piece_idx+1}!")
        
        # Send move result
        await ctx.send(f"{color} {ctx.author.mention}: {message}")
        
        if capture_messages:
            await ctx.send("\n".join(capture_messages))
        
        # Show updated board
        board = player_game.render_board()
        await ctx.send(board)
        
        # Check for game over
        if player_game.game_over:
            await ctx.send(f"🎉 **GAME OVER!** 🎉\n{COLORS[player_game.players.index(player_game.winner)]} {player_game.winner.mention} wins!")
            # Remove the game
            del self.active_games[game_id]
            return
            
        # Move to next player if it's not an extra turn with a 6
        was_six = player_game.rolled_six
        player_game.next_turn()
        
        # Show whose turn it is now
        if was_six and player_game.current_player == ctx.author:
            await ctx.send(f"{color} {ctx.author.mention} gets another turn for rolling a 6!")
        else:
            next_player = player_game.current_player
            next_color = COLORS[player_game.players.index(next_player)]
            await ctx.send(f"It's now {next_color} {next_player.mention}'s turn to roll.")
            
    @commands.hybrid_command(
        name="cangua_resign",
        description="Resign from your current Cờ Cá Ngựa game"
    )
    async def resign(self, ctx: commands.Context):
        """Resign from the game."""
        player_game, game_id = None, None
        
        # Find the player's active game
        for gid, game in self.active_games.items():
            if ctx.author in game.players:
                player_game, game_id = game, gid
                break
                
        if not player_game:
            return await ctx.send("You are not in an active game!")
            
        # Get player color
        color_idx = player_game.players.index(ctx.author)
        color = COLORS[color_idx]
        
        # Announce resignation
        await ctx.send(f"{color} {ctx.author.mention} has resigned from the game!")
        
        # Remove the player from active players if it's their turn
        if player_game.current_player == ctx.author:
            player_game.next_turn()
            
        # Add player to finished players so they're skipped
        if ctx.author not in player_game.finished_players:
            player_game.finished_players.append(ctx.author)
            
        # Check if only one player remains
        active_players = [p for p in player_game.players if p not in player_game.finished_players]
        
        if len(active_players) == 1:
            # Game is over, declare the remaining player as winner
            winner = active_players[0]
            winner_color = COLORS[player_game.players.index(winner)]
            await ctx.send(f"🎉 **GAME OVER!** 🎉\n{winner_color} {winner.mention} wins!")
            # Remove the game
            del self.active_games[game_id]
        else:
            # Game continues
            next_player = player_game.current_player
            next_color = COLORS[player_game.players.index(next_player)]
            await ctx.send(f"It's now {next_color} {next_player.mention}'s turn to roll.")
    
    @commands.hybrid_command(
        name="cangua_status",
        description="Show the status of your current Cờ Cá Ngựa game"
    )
    async def status(self, ctx: commands.Context):
        """Show the current game status."""
        player_game = None
        
        # Find the player's active game
        for game in self.active_games.values():
            if ctx.author in game.players:
                player_game = game
                break
                
        if not player_game:
            return await ctx.send("You are not in an active game!")
            
        # Show the board
        board = player_game.render_board()
        await ctx.send(board)
        
        # Show player status
        status = player_game.player_status()
        await ctx.send(status)
        
        # Show whose turn it is
        current_player = player_game.current_player
        current_color = COLORS[player_game.players.index(current_player)]
        await ctx.send(f"It's {current_color} {current_player.mention}'s turn.")


async def setup(bot: commands.Bot):
    """Setup function required by discord.py to load the cog."""
    await bot.add_cog(LudoCog(bot))