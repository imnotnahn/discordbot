import discord
from discord.ext import commands
from typing import Dict, List, Tuple, Optional

RED_PIECES = {
    'general': '帥',
    'advisor': '仕',
    'elephant': '相',
    'horse': '傌',
    'chariot': '俥',
    'cannon': '炮',
    'soldier': '兵'
}

BLACK_PIECES = {
    'general': '將',
    'advisor': '士',
    'elephant': '象',
    'horse': '馬',
    'chariot': '車',
    'cannon': '砲',
    'soldier': '卒'
}

# Emoji representations for pieces
PIECE_EMOJIS = {
    # Red pieces
    '帥': 'R-G ',  # General
    '仕': 'R-A ',  # Advisor
    '相': 'R-E ',  # Elephant
    '傌': 'R-H ',  # Horse
    '俥': 'R-C ',  # Chariot
    '炮': 'R-P ',  # Cannon
    '兵': 'R-S ',  # Soldier
    # Black pieces
    '將': 'B-G ',  # General
    '士': 'B-A ',  # Advisor
    '象': 'B-E ',  # Elephant
    '馬': 'B-H ',  # Horse
    '車': 'B-C ',  # Chariot
    '砲': 'B-P ',  # Cannon
    '卒': 'B-S ',  # Soldier
    # Empty
    '': '    '
}

# Chinese Chess piece definitions and game logic
class CoTuongGame:

    def __init__(self, player_red, player_black):
        self.player_red = player_red
        self.player_black = player_black
        self.current_player = player_red  # Red goes first
        self.board = self.init_board()
        self.game_over = False
        self.winner = None
        self.last_move = None

    def init_board(self):
        # Create empty 9x10 board
        board = [['' for _ in range(9)] for _ in range(10)]

        # Place red pieces (bottom side)
        # Chariots
        board[9][0] = '俥'
        board[9][8] = '俥'
        # Horses
        board[9][1] = '傌'
        board[9][7] = '傌'
        # Elephants
        board[9][2] = '相'
        board[9][6] = '相'
        # Advisors
        board[9][3] = '仕'
        board[9][5] = '仕'
        # General
        board[9][4] = '帥'
        # Cannons
        board[7][1] = '炮'
        board[7][7] = '炮'
        # Soldiers
        board[6][0] = '兵'
        board[6][2] = '兵'
        board[6][4] = '兵'
        board[6][6] = '兵'
        board[6][8] = '兵'

        # Place black pieces (top side)
        # Chariots
        board[0][0] = '車'
        board[0][8] = '車'
        # Horses
        board[0][1] = '馬'
        board[0][7] = '馬'
        # Elephants
        board[0][2] = '象'
        board[0][6] = '象'
        # Advisors
        board[0][3] = '士'
        board[0][5] = '士'
        # General
        board[0][4] = '將'
        # Cannons
        board[2][1] = '砲'
        board[2][7] = '砲'
        # Soldiers
        board[3][0] = '卒'
        board[3][2] = '卒'
        board[3][4] = '卒'
        board[3][6] = '卒'
        board[3][8] = '卒'

        return board

    def is_red_piece(self, piece):
        return piece in RED_PIECES.values()

    def is_black_piece(self, piece):
        return piece in BLACK_PIECES.values()

    def is_valid_move(self, piece, from_pos, to_pos):
        from_x, from_y = from_pos
        to_x, to_y = to_pos

        # Basic bounds check
        if not (0 <= to_x < 10 and 0 <= to_y < 9):
            return False, "Position is out of board bounds"

        if self.board[from_x][from_y] != piece:
            return False, "No such piece at the starting position"

        is_red_turn = self.current_player == self.player_red
        if is_red_turn and not self.is_red_piece(piece):
            return False, "Red player can only move red pieces"
        if not is_red_turn and not self.is_black_piece(piece):
            return False, "Black player can only move black pieces"

        to_piece = self.board[to_x][to_y]
        if to_piece:
            if is_red_turn and self.is_red_piece(to_piece):
                return False, "Cannot capture your own piece"
            if not is_red_turn and self.is_black_piece(to_piece):
                return False, "Cannot capture your own piece"

        # Specific piece movement rules
        if piece in ('帥', '將'):  
            return self.is_valid_general_move(from_pos, to_pos, is_red_turn)
        elif piece in ('仕', '士'):  
            return self.is_valid_advisor_move(from_pos, to_pos, is_red_turn)
        elif piece in ('相', '象'):  
            return self.is_valid_elephant_move(from_pos, to_pos, is_red_turn)
        elif piece in ('傌', '馬'): 
            return self.is_valid_horse_move(from_pos, to_pos)
        elif piece in ('俥', '車'):  
            return self.is_valid_chariot_move(from_pos, to_pos)
        elif piece in ('炮', '砲'):  
            return self.is_valid_cannon_move(from_pos, to_pos)
        elif piece in ('兵', '卒'):  
            return self.is_valid_soldier_move(from_pos, to_pos, is_red_turn)

        return False, "Unknown piece type"

    def is_valid_general_move(self, from_pos, to_pos, is_red):
        from_x, from_y = from_pos
        to_x, to_y = to_pos

        # General can only move one step horizontally or vertically
        if abs(from_x - to_x) + abs(from_y - to_y) != 1:
            return False, "General can only move one step horizontally or vertically"

        # General must stay in the palace (3x3 area)
        palace_x_range = range(7, 10) if is_red else range(0, 3)
        palace_y_range = range(3, 6)

        if to_x not in palace_x_range or to_y not in palace_y_range:
            return False, "General must stay in the palace"

        return True, ""

    def is_valid_advisor_move(self, from_pos, to_pos, is_red):
        from_x, from_y = from_pos
        to_x, to_y = to_pos

        # Advisor can only move one step diagonally
        if abs(from_x - to_x) != 1 or abs(from_y - to_y) != 1:
            return False, "Advisor can only move one step diagonally"

        palace_x_range = range(7, 10) if is_red else range(0, 3)
        palace_y_range = range(3, 6)

        if to_x not in palace_x_range or to_y not in palace_y_range:
            return False, "Advisor must stay in the palace"

        return True, ""

    def is_valid_elephant_move(self, from_pos, to_pos, is_red):
        from_x, from_y = from_pos
        to_x, to_y = to_pos

        # Elephant moves exactly two points diagonally
        if abs(from_x - to_x) != 2 or abs(from_y - to_y) != 2:
            return False, "Elephant must move exactly two steps diagonally"

        block_x = (from_x + to_x) // 2
        block_y = (from_y + to_y) // 2

        if self.board[block_x][block_y]:
            return False, "Elephant's move is blocked"

        # Elephant cannot cross the river
        river_boundary = 5
        if is_red and to_x < river_boundary:
            return False, "Elephant cannot cross the river"
        if not is_red and to_x >= river_boundary:
            return False, "Elephant cannot cross the river"

        return True, ""

    def is_valid_horse_move(self, from_pos, to_pos):
        from_x, from_y = from_pos
        to_x, to_y = to_pos

        # Horse moves in an L shape: 2 steps in one direction, then 1 step perpendicular
        dx = abs(from_x - to_x)
        dy = abs(from_y - to_y)

        if not ((dx == 1 and dy == 2) or (dx == 2 and dy == 1)):
            return False, "Horse must move in an L shape (2 steps then 1 step perpendicular)"

        # Check if the horse is blocked (hobbled)
        if dx == 1:  
            block_y = (from_y + to_y) // 2
            block_x = from_x
        else:  
            block_x = (from_x + to_x) // 2
            block_y = from_y

        if self.board[block_x][block_y]:
            return False, "Horse's move is blocked (hobbling point is occupied)"

        return True, ""

    def is_valid_chariot_move(self, from_pos, to_pos):
        from_x, from_y = from_pos
        to_x, to_y = to_pos

        # Chariot moves horizontally or vertically any distance
        if from_x != to_x and from_y != to_y:
            return False, "Chariot must move horizontally or vertically"

        if from_x == to_x: 
            min_y = min(from_y, to_y)
            max_y = max(from_y, to_y)
            for y in range(min_y + 1, max_y):
                if self.board[from_x][y]:
                    return False, "Chariot's path is blocked"
        else:  
            min_x = min(from_x, to_x)
            max_x = max(from_x, to_x)
            for x in range(min_x + 1, max_x):
                if self.board[x][from_y]:
                    return False, "Chariot's path is blocked"

        return True, ""

    def is_valid_cannon_move(self, from_pos, to_pos):
        from_x, from_y = from_pos
        to_x, to_y = to_pos

        # Cannon moves like the chariot, but jumps over exactly one piece to capture
        if from_x != to_x and from_y != to_y:
            return False, "Cannon must move horizontally or vertically"

        pieces_in_path = 0

        if from_x == to_x:  
            min_y = min(from_y, to_y)
            max_y = max(from_y, to_y)
            for y in range(min_y + 1, max_y):
                if self.board[from_x][y]:
                    pieces_in_path += 1
        else:  
            min_x = min(from_x, to_x)
            max_x = max(from_x, to_x)
            for x in range(min_x + 1, max_x):
                if self.board[x][from_y]:
                    pieces_in_path += 1

        target_piece = self.board[to_x][to_y]

        if target_piece: 
            if pieces_in_path != 1:
                return False, "Cannon must jump over exactly one piece to capture"
        else:  
            if pieces_in_path > 0:
                return False, "Cannon's path must be clear when not capturing"

        return True, ""

    def is_valid_soldier_move(self, from_pos, to_pos, is_red):
        from_x, from_y = from_pos
        to_x, to_y = to_pos

        if abs(from_x - to_x) + abs(from_y - to_y) != 1:
            return False, "Soldier can only move one step"

        if is_red and to_x > from_x:
            return False, "Soldier cannot move backward"
        if not is_red and to_x < from_x:
            return False, "Soldier cannot move backward"

        river_boundary = 5

        if is_red and from_x >= river_boundary:
            if from_y != to_y:
                return False, "Soldier can only move forward before crossing the river"
        elif not is_red and from_x < river_boundary:
            if from_y != to_y:
                return False, "Soldier can only move forward before crossing the river"

        return True, ""

    def make_move(self, piece, from_pos, to_pos):
        from_x, from_y = from_pos
        to_x, to_y = to_pos

        valid, message = self.is_valid_move(piece, from_pos, to_pos)
        if not valid:
            return False, message

        captured_piece = self.board[to_x][to_y]
        self.board[to_x][to_y] = piece
        self.board[from_x][from_y] = ''

        self.last_move = {
            'piece': piece,
            'from': from_pos,
            'to': to_pos,
            'captured': captured_piece
        }

        if captured_piece == '帥':
            self.game_over = True
            self.winner = self.player_black
        elif captured_piece == '將':
            self.game_over = True
            self.winner = self.player_red

        self.current_player = self.player_black if self.current_player == self.player_red else self.player_red

        return True, f"Moved {piece} from ({from_x},{from_y}) to ({to_x},{to_y})" + (
            f", captured {captured_piece}" if captured_piece else "")

    def render_board(self):
        rows = []

        header = "     "
        for y in range(9):
            header += f"  {y}  "
        rows.append(header)

        separator = "    +" + "----+" * 9
        rows.append(separator)

        for x in range(10):
            row = f" {x}  |"

            for y in range(9):
                piece = self.board[x][y]
                piece_str = PIECE_EMOJIS.get(piece, ' ·   ')

                row += f"{piece_str}|"

            rows.append(row)
            rows.append(separator)

        return "\n".join(rows)

class CoTuongCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Store active games
        self.active_games = {}

    @commands.hybrid_command(
        name="cotuong_play",
        description="Start a Co Tuong game with another player")
    async def cotuong(self, ctx, player1: discord.Member, player2: discord.Member):
        if player1.bot or player2.bot:
            return await ctx.send("You cannot include bots in the game!")

        if player1 == player2:
            return await ctx.send("You cannot have the same player twice!")

        # Check if either player is already in a game
        for game_id, game in self.active_games.items():
            if player1 in [game.player_red, game.player_black] or player2 in [game.player_red, game.player_black]:
                return await ctx.send(f"One or both players are already in a game!")

        # Create a new game
        new_game = CoTuongGame(player_red=player1, player_black=player2)
        game_id = f"{ctx.guild.id}-{ctx.channel.id}-{player1.id}-{player2.id}"
        self.active_games[game_id] = new_game

        embed = discord.Embed(
            title="Co Tuong Game Started",
            description=f"Game started between {player1.mention} (Red) and {player2.mention} (Black)",
            color=discord.Color.gold())

        embed.add_field(
            name="How to Play",
            value=(
                "Use `/move [piece] [from_x] [from_y] [to_x] [to_y]` to make a move.\n"
                "Example: `/move h 9 1 7 2` moves the Horse from (9,1) to (7,2)\n\n"
                "Piece shortcuts: g(eneral), a(dvisor), e(lephant), h(orse), c(hariot), p(annon), s(oldier)\n"
                "To resign, type `/end`\n\n"
                "Red pieces: 帥(G), 仕(A), 相(E), 傌(H), 俥(C), 炮(P), 兵(S)\n"
                "Black pieces: 將(G), 士(A), 象(E), 馬(H), 車(C), 砲(P), 卒(S)"
            ),
            inline=False
        )

        embed.add_field(name="Current Player",
                        value=f"{player1.mention} (Red)",
                        inline=False)

        # Send the board as text
        board_text = new_game.render_board()
        await ctx.send(embed=embed)
        await ctx.send(f"```\n{board_text}\n```")

    @commands.hybrid_command(
        name="cotuong_move",
        description="Make a move in an active Co Tuong game")
    async def move(self, ctx, piece_name: str, from_x: int, from_y: int, to_x: int, to_y: int):
        player_game = None
        game_id = None

        for gid, game in self.active_games.items():
            if ctx.author in [game.player_red, game.player_black]:
                player_game = game
                game_id = gid
                break

        if not player_game:
            return await ctx.send(
                "You are not in an active game! Start one with `/cotuong @player1 @player2`"
            )

        # Check if it's the player's turn
        if player_game.current_player != ctx.author:
            return await ctx.send(
                f"It's not your turn! Waiting for {player_game.current_player.mention} to move."
            )

        is_red = player_game.current_player == player_game.player_red
        piece_map = RED_PIECES if is_red else BLACK_PIECES

        piece_input = piece_name.lower().strip()
        piece_char = None

        if piece_input == "c":  
            piece_char = piece_map["chariot"]
        elif piece_input == "p":  
            piece_char = piece_map["cannon"]
        else:
            # Match by first letter
            for name, char in piece_map.items():
                if name.startswith(piece_input) or name[0].lower() == piece_input:
                    piece_char = char
                    break

        if not piece_char:
            valid_pieces = "g(eneral), a(dvisor), e(lephant), h(orse), c(hariot), p(annon), s(oldier)"
            return await ctx.send(
                f"Invalid piece name! Valid pieces for you are: {valid_pieces}")

        success, message = player_game.make_move(piece_char, (from_x, from_y), (to_x, to_y))

        if not success:
            return await ctx.send(f"Invalid move: {message}")

        board_text = player_game.render_board()

        await ctx.send(f"{message}")
        await ctx.send(f"```\n{board_text}\n```")

        current_player = "Red" if player_game.current_player == player_game.player_red else "Black"
        await ctx.send(
            f"It's now {player_game.current_player.mention}'s turn ({current_player})."
        )

        if player_game.game_over:
            await ctx.send(f"🎉 Game Over! {player_game.winner.mention} wins! 🎉")
            # Clean up the game
            del self.active_games[game_id]

    @commands.hybrid_command(
        name="cotuong_resign",
        description="Resign from your current Co Tuong game",
        aliases=["ct_resign"]
    )
    async def resign_cotuong(self, ctx):
        player_game = None
        game_id = None
        
        for gid, game in self.active_games.items():
            if ctx.author in [game.player_red, game.player_black]:
                player_game = game
                game_id = gid
                break
                
        if not player_game:
            return await ctx.send("You are not in an active Co Tuong game!")
                
        if ctx.author == player_game.player_red:
            player_game.winner = player_game.player_black
        else:
            player_game.winner = player_game.player_red
                
        player_game.game_over = True
            
        await ctx.send(f"**{ctx.author.display_name}** has resigned from the Co Tuong game!")
        await ctx.send(f"🎉 Game Over! {player_game.winner.mention} wins! 🎉")
            
        # Clean up the game
        del self.active_games[game_id]
async def setup(bot):
    await bot.add_cog(CoTuongCog(bot))