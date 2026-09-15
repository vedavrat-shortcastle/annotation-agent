import json
import shutil

import chess
import chess.engine


STOCKFISH_PATH = shutil.which("stockfish")

if STOCKFISH_PATH is None:
    raise FileNotFoundError(
        "Stockfish was not found. Make sure it is installed and available in PATH."
    )


def evaluate_position(fen, depth=18, multipv=5):
    """
    Analyze a single chess position using Stockfish.

    Args:
        fen (str): FEN representation of the position.
        depth (int): Stockfish search depth.
        multipv (int): Number of top candidate moves to return.

    Returns:
        dict: Structured Stockfish analysis.
    """

    board = chess.Board(fen)

    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)

    try:
        infos = engine.analyse(
            board,
            chess.engine.Limit(depth=depth),
            multipv=multipv,
        )

        top_moves = []

        for info in infos:
            score = info["score"].pov(board.turn)

            top_moves.append(
          {
            "move": board.san(info["pv"][0]),
            "evaluation": score_to_float(score),
            "pv": board.variation_san(info["pv"]),
          }
)

        best = top_moves[0]

        return {
            "fen": fen,
            "evaluation": best["evaluation"],
            "best_move": best["move"],
            "top_moves": top_moves,
            "depth": depth,
        }

    finally:
        engine.quit()

def evaluate_specific_move(fen, move_uci, depth=18):
    """
    Evaluate a specific candidate move with Stockfish.

    Maia chooses the move.
    Stockfish evaluates the resulting position and provides
    the continuation.

    The returned evaluation is from the perspective of the
    player who made move_uci.
    """

    board = chess.Board(fen)
    original_turn = board.turn

    try:
        move = chess.Move.from_uci(move_uci)

        if move not in board.legal_moves:
            raise ValueError(f"Illegal move: {move_uci}")

        move_san = board.san(move)

        # Make the Maia-selected move.
        board.push(move)

        engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)

        try:
            info = engine.analyse(
                board,
                chess.engine.Limit(depth=depth),
            )

            # Convert Stockfish's score back to the player
            # who made the Maia move.
            score = info["score"].pov(original_turn)

            continuation = info.get("pv", [])

            # Convert the continuation to SAN.
            variation_board = board.copy()
            variation_san = []

            for pv_move in continuation:
                variation_san.append(variation_board.san(pv_move))
                variation_board.push(pv_move)

            # Full line starts with Maia's move.
            full_variation = [move_san] + variation_san

            return {
                "move": move_san,
                "uci": move_uci,
                "evaluation": score_to_float(score),
                "pv": full_variation,
            }

        finally:
            engine.quit()

    except chess.IllegalMoveError:
        raise ValueError(f"Illegal move: {move_uci}")
def score_to_float(score):
    """
    Convert Stockfish's score into a human-readable float.

    Normal positions:
        +1.50 = White advantage
        -1.50 = Black advantage

    Mate positions:
        Large positive/negative values are used to represent mate.
    """

    if score.is_mate():
        mate_in = score.mate()

        if mate_in is None:
            return None

        if mate_in > 0:
            return 100.0
        else:
            return -100.0

    return score.score(mate_score=100000) / 100.0


def main():
    print("\nEnter FEN:")
    fen = input().strip()

    try:
        result = evaluate_position(fen)

        print("\n" + "=" * 60)
        print("              STOCKFISH ANALYSIS")
        print("=" * 60)

        print("\nFEN:")
        print(result["fen"])

        print(f"\nBEST MOVE: {result['best_move']}")
        print(f"EVALUATION: {result['evaluation']:+.2f}")

        print("\n" + "-" * 60)
        print("TOP 5 MOVES")
        print("-" * 60)

        for i, move in enumerate(result["top_moves"], start=1):
            print(f"\n{i}. {move['move']}")
            print(f"   Evaluation: {move['evaluation']:+.2f}")
            print("   Principal Variation:")
            print(f"   {move["pv"]}")

        print("\n" + "=" * 60)

        print("\nJSON OUTPUT:")
        print(json.dumps(result, indent=2))

    except ValueError:
        print("Invalid FEN.")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()