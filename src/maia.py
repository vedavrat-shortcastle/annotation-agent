import subprocess
from pathlib import Path

import chess

from .stockfish import evaluate_specific_move


# Direct Maia-3 installation
MAIA_ROOT = Path.home() / "chess" / "maia3-engine"
MAIA_PYTHON = MAIA_ROOT / "venv" / "bin" / "python"

MODEL = "maia3-79m"

DEFAULT_ELO = 1900
DEFAULT_SELF_ELO = 1900
DEFAULT_OPPO_ELO = 2100
DEFAULT_MULTIPV = 5
STOCKFISH_DEPTH = 18


def parse_info_line(line, board):
    """
    Parse one Maia-3 UCI MultiPV info line.

    Example:
        info depth 1 multipv 1 score cp -689
        wdl 148 15 837 pv f2g1
    """

    tokens = line.split()

    if "multipv" not in tokens or "pv" not in tokens:
        return None

    try:
        # Maia rank
        multipv_index = tokens.index("multipv")
        rank = int(tokens[multipv_index + 1])

        # Maia UCI compatibility score
        score_cp = None

        if "score" in tokens:
            score_index = tokens.index("score")

            if (
                score_index + 2 < len(tokens)
                and tokens[score_index + 1] == "cp"
            ):
                score_cp = int(tokens[score_index + 2])

        # Maia WDL
        wdl = None

        if "wdl" in tokens:
            wdl_index = tokens.index("wdl")

            if wdl_index + 3 < len(tokens):
                wdl = [
                    int(tokens[wdl_index + 1]),
                    int(tokens[wdl_index + 2]),
                    int(tokens[wdl_index + 3]),
                ]

        # Principal variation in UCI format
        pv_index = tokens.index("pv")
        pv_uci = tokens[pv_index + 1 :]

        if not pv_uci:
            return None

        first_move = chess.Move.from_uci(pv_uci[0])

        if first_move not in board.legal_moves:
            return None

        move_san = board.san(first_move)

        return {
            "rank": rank,
            "move": move_san,
            "uci": pv_uci[0],
            "score_cp": score_cp,
            "wdl": wdl,
            "maia_pv": pv_uci,
        }

    except (
        ValueError,
        IndexError,
        chess.InvalidMoveError,
    ):
        return None


def analyze_maia(
    fen,
    elo=DEFAULT_ELO,
    self_elo=DEFAULT_SELF_ELO,
    oppo_elo=DEFAULT_OPPO_ELO,
    multipv=DEFAULT_MULTIPV,
):
    """
    Analyze a chess position with Maia-3 79M.

    Maia determines the human-likely move ranking.

    Stockfish then evaluates each Maia-selected move and provides
    a chess evaluation and continuation for that exact move.

    Returns:
        dict: Combined Maia + Stockfish analysis.
    """

    if not MAIA_PYTHON.exists():
        raise FileNotFoundError(
            f"Maia Python executable not found: {MAIA_PYTHON}"
        )

    board = chess.Board(fen)

    process = subprocess.Popen(
        [
            str(MAIA_PYTHON),
            "-m",
            "maia3.uci",
            "--model",
            MODEL,
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    try:
        assert process.stdin is not None
        assert process.stdout is not None

        commands = [
            "uci",
            f"setoption name Elo value {elo}",
            f"setoption name SelfElo value {self_elo}",
            f"setoption name OppoElo value {oppo_elo}",
            f"setoption name MultiPV value {multipv}",
            "isready",
            f"position fen {fen}",
            "go",
        ]

        process.stdin.write("\n".join(commands) + "\n")
        process.stdin.flush()

        candidates = []

        for raw_line in process.stdout:
            line = raw_line.strip()

            if line.startswith("info ") and "multipv" in line:
                parsed = parse_info_line(line, board)

                if parsed is not None:
                    candidates.append(parsed)

            if line.startswith("bestmove "):
                break

        candidates.sort(key=lambda item: item["rank"])

        # Keep only requested number of Maia candidates.
        candidates = candidates[:multipv]

        # Maia chooses the moves.
        # Stockfish scores those exact moves.
        for candidate in candidates:
            try:
                stockfish_result = evaluate_specific_move(
                    fen=fen,
                    move_uci=candidate["uci"],
                    depth=STOCKFISH_DEPTH,
                )

                candidate["stockfish_evaluation"] = (
                    stockfish_result["evaluation"]
                )

                candidate["stockfish_variation"] = (
                    stockfish_result["pv"]
                )

            except Exception as exc:
                candidate["stockfish_evaluation"] = None
                candidate["stockfish_variation"] = []
                candidate["stockfish_error"] = str(exc)

        return {
            "fen": fen,
            "model": "Maia3-79M",
            "elo": elo,
            "self_elo": self_elo,
            "oppo_elo": oppo_elo,
            "best_move": (
                candidates[0]["move"]
                if candidates
                else None
            ),
            "top_moves": candidates,
        }

    finally:
        try:
            if process.stdin:
                process.stdin.write("quit\n")
                process.stdin.flush()
        except Exception:
            pass

        try:
            process.terminate()
            process.wait(timeout=2)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass


def main():
    print("\nEnter FEN:")
    fen = input().strip()

    try:
        result = analyze_maia(fen)

        print("\n" + "=" * 70)
        print("              MAIA-3 + STOCKFISH")
        print("=" * 70)

        print(f"\nMODEL: {result['model']}")
        print(f"PLAYER ELO: {result['self_elo']}")
        print(f"OPPONENT ELO: {result['oppo_elo']}")

        print(f"\nBEST HUMAN MOVE: {result['best_move']}")

        print("\n" + "-" * 70)
        print("MAIA HUMAN MOVES + STOCKFISH EVALUATION")
        print("-" * 70)

        for move in result["top_moves"]:
            print(f"\n#{move['rank']} {move['move']}")

            print(f"   Maia score: {move['score_cp']}")
            print(f"   Maia WDL: {move['wdl']}")

            stockfish_eval = move["stockfish_evaluation"]

            if stockfish_eval is not None:
                print(
                    f"   Stockfish evaluation: "
                    f"{stockfish_eval:+.2f}"
                )
            else:
                print("   Stockfish evaluation: unavailable")

            if move["stockfish_variation"]:
                print("   Stockfish variation:")
                print(
                    "   "
                    + " ".join(move["stockfish_variation"])
                )
            else:
                print("   Stockfish variation: unavailable")

        print("\n" + "=" * 70)

    except ValueError:
        print("Invalid FEN.")

    except Exception as exc:
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()