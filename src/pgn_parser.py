import io
import json
import re
import chess.pgn


def clean_pgn(pgn_text):
    """
    Clean common formatting issues when PGNs are pasted
    into the terminal.
    """

    # Add newlines before PGN headers
    pgn_text = re.sub(r"\[", "\n[", pgn_text)

    # Add a newline before move numbers like 1., 2., 10.
    pgn_text = re.sub(r"\s+(\d+\.)", r"\n\1", pgn_text)

    # Fix cases such as:
    # Bxf6Bxf6 -> Bxf6 Bxf6
    pgn_text = re.sub(
        r"([a-h][1-8])([KQRBN][a-h]?[1-8]?)",
        r"\1 \2",
        pgn_text
    )

    # Fix cases such as:
    # 15.Nf3 -> 15. Nf3
    pgn_text = re.sub(r"(\d+)\.([A-Za-z])", r"\1. \2", pgn_text)

    # Separate headers from moves
    pgn_text = re.sub(
        r'(\])\s*(\d+\.)',
        r'\1\n\n\2',
        pgn_text
    )

    return pgn_text.strip()


def parse_game(game):
    board = game.board()
    moves = []

    for ply, move in enumerate(game.mainline_moves(), start=1):
        fen_before = board.fen()
        san = board.san(move)

        board.push(move)

        moves.append({
            "ply": ply,
            "move_number": (ply + 1) // 2,
            "player": "white" if ply % 2 == 1 else "black",
            "move": san,
            "fen_before": fen_before,
            "fen_after": board.fen()
        })

    return {
        "white": game.headers.get("White"),
        "black": game.headers.get("Black"),
        "white_elo": game.headers.get("WhiteElo"),
        "black_elo": game.headers.get("BlackElo"),
        "result": game.headers.get("Result"),
        "event": game.headers.get("Event"),
        "date": game.headers.get("Date"),
        "moves": moves
    }


def main():
    print("Paste PGN below.")
    print("Press Ctrl+D when finished.\n")

    lines = []

    while True:
        try:
            lines.append(input())
        except EOFError:
            break

    pgn_text = "\n".join(lines)

    # Clean pasted formatting
    pgn_text = clean_pgn(pgn_text)

    # Optional: show what parser received
   # print("\n--- CLEANED PGN ---")
   # print(pgn_text)
    #print("-------------------\n")

    game = chess.pgn.read_game(io.StringIO(pgn_text))

    if game is None:
        print("ERROR: Could not parse PGN.")
        return

    result = parse_game(game)

    print("JSON OUTPUT:\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()