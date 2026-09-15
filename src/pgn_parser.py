import io

import chess.pgn


def parse_game(game):
    """
    Convert a python-chess Game into structured move data.
    """

    board = game.board()
    moves = []

    for ply, move in enumerate(
        game.mainline_moves(),
        start=1,
    ):
        fen_before = board.fen()
        san = board.san(move)

        board.push(move)

        moves.append(
            {
                "ply": ply,
                "move_number": (ply + 1) // 2,
                "player": (
                    "white"
                    if ply % 2 == 1
                    else "black"
                ),
                "move": san,
                "uci": move.uci(),
                "fen_before": fen_before,
                "fen_after": board.fen(),
            }
        )

    return {
        "white": game.headers.get("White"),
        "black": game.headers.get("Black"),
        "white_elo": game.headers.get("WhiteElo"),
        "black_elo": game.headers.get("BlackElo"),
        "result": game.headers.get("Result"),
        "event": game.headers.get("Event"),
        "date": game.headers.get("Date"),
        "moves": moves,
    }


def parse_pgn_text(pgn_text):
    """
    Parse one PGN string into structured game data.
    """

    game = chess.pgn.read_game(
        io.StringIO(pgn_text)
    )

    if game is None:
        raise ValueError("Could not parse PGN.")

    return parse_game(game)