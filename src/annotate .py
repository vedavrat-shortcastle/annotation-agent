import sys
import re

from src.pgn_parser import parse_pgn_text
from src.stockfish import StockfishEngine
from src.maia import MaiaEngine
from src.annotation import generate_annotations_batch


# =========================================================
# Configuration
# =========================================================

# Fast scan for all moves.
STOCKFISH_SCREEN_DEPTH = 10
STOCKFISH_SCREEN_MULTIPV = 2

# Deep verification only for preliminary candidates.
STOCKFISH_DEEP_DEPTH = 16
STOCKFISH_DEEP_MULTIPV = 2

# Maia always needs the top 5 human-likely moves.
MAIA_MULTIPV = 5

# Chess.com-style heuristic thresholds requested for this project.
INACCURACY_THRESHOLD = 0.30
MISTAKE_THRESHOLD = 0.80
BLUNDER_THRESHOLD = 1.50

GREAT_MOVE_GAP = 0.75
BRILLIANT_MOVE_GAP = 1.50

# Maia anomaly definition.
MAIA_TOP_K = 5

# =========================================================
# Helpers
# =========================================================

def find_played_move_uci(move_data):
    return move_data["uci"]


def get_move_player(move_data):
    player = str(move_data.get("player", "")).strip().lower()

    if player in {"white", "w"}:
        return "White"

    if player in {"black", "b"}:
        return "Black"

    raise ValueError(
        f"Unknown player/side in move data: {move_data}"
    )


def configure_maia_for_move(
    maia,
    move_data,
    player_elo,
    opponent_elo,
):
    """
    Configure Maia relative to the side that actually made
    the move.

    White move:
        self = player Elo
        opponent = opponent Elo

    Black move:
        self = opponent Elo
        opponent = player Elo
    """
    side = get_move_player(move_data)

    if side == "White":
        self_elo = player_elo
        oppo_elo = opponent_elo
    else:
        self_elo = opponent_elo
        oppo_elo = player_elo

    maia.configure(
        elo=self_elo,
        self_elo=self_elo,
        oppo_elo=oppo_elo,
    )


def get_gap_to_second(top_moves):
    if len(top_moves) < 2:
        return 0.0

    best_eval = top_moves[0].get("evaluation")
    second_eval = top_moves[1].get("evaluation")

    if best_eval is None or second_eval is None:
        return 0.0

    return abs(best_eval - second_eval)


def get_played_evaluation(
    stockfish,
    fen,
    played_uci,
    top_moves,
):
    """
    Reuse the MultiPV evaluation when the played move is already
    among the returned moves. Otherwise evaluate that exact move.
    """
    for candidate in top_moves:
        if candidate.get("uci") == played_uci:
            return candidate.get("evaluation")

    exact = stockfish.evaluate_specific_move(
        fen,
        played_uci,
    )

    return exact.get("evaluation")


# =========================================================
# Classifiers
# =========================================================

def classify_stockfish(
    eval_loss,
    played_uci,
    best_move,
    gap_to_second,
):
    # Bad moves.
    if eval_loss >= BLUNDER_THRESHOLD:
        return "blunder"

    if eval_loss >= MISTAKE_THRESHOLD:
        return "mistake"

    if eval_loss >= INACCURACY_THRESHOLD:
        return "inaccuracy"

    # Exceptional moves.
    if played_uci == best_move:
        if gap_to_second >= BRILLIANT_MOVE_GAP:
            return "brilliant"

        if gap_to_second >= GREAT_MOVE_GAP:
            return "great"

    return None


def classify_maia(played_uci, maia_result):
    top_moves = maia_result.get("top_moves", [])

    if not top_moves:
        return {
            "label": None,
            "rank": None,
        }

    played_rank = None

    for candidate in top_moves:
        if candidate.get("uci") == played_uci:
            played_rank = candidate.get("rank")
            break

    if played_rank is None:
        return {
            "label": "unexpected",
            "rank": None,
        }

    if played_rank == 1:
        return {
            "label": "most_natural",
            "rank": 1,
        }

    if played_rank <= MAIA_TOP_K:
        return {
            "label": "natural",
            "rank": played_rank,
        }

    return {
        "label": "unexpected",
        "rank": played_rank,
    }


# =========================================================
# Stockfish analysis for one move
# =========================================================

def analyze_stockfish_move(
    move_data,
    stockfish,
):
    fen_before = move_data["fen_before"]
    played_uci = find_played_move_uci(move_data)

    position = stockfish.evaluate_position(fen_before)

    top_moves = position.get("top_moves", [])
    best_move = position.get("best_move")
    best_eval = position.get("best_evaluation")

    played_eval = get_played_evaluation(
        stockfish=stockfish,
        fen=fen_before,
        played_uci=played_uci,
        top_moves=top_moves,
    )

    eval_loss = 0.0

    if best_eval is not None and played_eval is not None:
        eval_loss = max(
            0.0,
            best_eval - played_eval,
        )

    gap_to_second = get_gap_to_second(top_moves)

    classification = classify_stockfish(
        eval_loss=eval_loss,
        played_uci=played_uci,
        best_move=best_move,
        gap_to_second=gap_to_second,
    )

    return {
        "classification": classification,
        "best_move": best_move,
        "best_evaluation": best_eval,
        "played_evaluation": played_eval,
        "evaluation_loss": eval_loss,
        "gap_to_second": gap_to_second,
        "top_moves": top_moves,
    }


# =========================================================
# Maia analysis for one move
# =========================================================

def analyze_maia_move(
    move_data,
    maia,
    player_elo,
    opponent_elo,
):
    configure_maia_for_move(
        maia=maia,
        move_data=move_data,
        player_elo=player_elo,
        opponent_elo=opponent_elo,
    )

    maia_result = maia.analyze(
        move_data["fen_before"]
    )

    classification = classify_maia(
        played_uci=find_played_move_uci(move_data),
        maia_result=maia_result,
    )

    return {
        "classification": classification["label"],
        "rank": classification["rank"],
        "best_move": maia_result.get("best_move"),
        "top_moves": maia_result.get("top_moves", []),
        "elo": maia_result.get("elo"),
        "self_elo": maia_result.get("self_elo"),
        "oppo_elo": maia_result.get("oppo_elo"),
    }


# =========================================================
# Preliminary screening
# =========================================================

def screen_move(
    move_data,
    stockfish,
    maia,
    player_elo,
    opponent_elo,
):
    """
    Fast first-pass detector.

    A move becomes a preliminary candidate when either:
      1. Stockfish classifies it as an anomaly, or
      2. Maia marks it as human-unusual.

    These candidates are NOT final. They must pass deep
    Stockfish verification before Gemini is called.
    """
    stockfish_result = analyze_stockfish_move(
        move_data,
        stockfish,
    )

    maia_result = analyze_maia_move(
        move_data=move_data,
        maia=maia,
        player_elo=player_elo,
        opponent_elo=opponent_elo,
    )

    stockfish_anomaly = (
        stockfish_result["classification"] is not None
    )

    maia_anomaly = (
        maia_result["classification"] == "unexpected"
    )

    return {
        "move": move_data,
        "played_uci": move_data["uci"],
        "stockfish": stockfish_result,
        "maia": maia_result,
        "stockfish_anomaly": stockfish_anomaly,
        "maia_anomaly": maia_anomaly,
        "should_annotate": (
            stockfish_anomaly or maia_anomaly
        ),
    }


# =========================================================
# Deep verification
# =========================================================

def verify_stockfish_candidate(
    candidate,
    deep_stockfish,
):
    """
    Re-evaluate a preliminary candidate at the deeper
    Stockfish depth.

    IMPORTANT:
    - Maia evidence is kept unchanged.
    - Stockfish classification is REPLACED by the deep result.
    - A candidate survives if:
        deep Stockfish still finds an anomaly, OR
        Maia independently says the move is unexpected.
    """
    move_data = candidate["move"]

    deep_stockfish_result = analyze_stockfish_move(
        move_data=move_data,
        stockfish=deep_stockfish,
    )

    final_stockfish_anomaly = (
        deep_stockfish_result["classification"] is not None
    )

    final_maia_anomaly = candidate["maia_anomaly"]

    candidate["stockfish"] = deep_stockfish_result
    candidate["stockfish_anomaly"] = final_stockfish_anomaly
    candidate["maia_anomaly"] = final_maia_anomaly
    candidate["should_annotate"] = (
        final_stockfish_anomaly
        or final_maia_anomaly
    )

    return candidate


# =========================================================
# Gemini input
# =========================================================

def build_annotation_input(
    candidate,
    player_elo,
    opponent_elo,
):
    move_data = candidate["move"]

    anomaly_reasons = []

    if candidate["stockfish_anomaly"]:
        label = candidate["stockfish"]["classification"]

        if label:
            anomaly_reasons.append(
                f"Stockfish: {label}"
            )

    if candidate["maia_anomaly"]:
        anomaly_reasons.append("human-unusual")

    return {
        "fen": move_data["fen_before"],
        "fen_before": move_data["fen_before"],
        "fen_after": move_data.get("fen_after"),
        "move": move_data["move"],
        "uci": move_data["uci"],
        "ply": move_data["ply"],
        "move_number": move_data["move_number"],
        "player": move_data["player"],
        "player_elo": player_elo,
        "opponent_elo": opponent_elo,
        "anomaly_reasons": anomaly_reasons,
        "stockfish": candidate["stockfish"],
        "maia": candidate["maia"],
        "stockfish_anomaly": candidate["stockfish_anomaly"],
        "maia_anomaly": candidate["maia_anomaly"],
    }


# =========================================================
# PGN header extraction
# =========================================================

def extract_pgn_headers(pgn_text):
    """Extract standard PGN [Key "Value"] headers directly from text."""
    headers = {}

    for line in pgn_text.splitlines():
        line = line.strip()

        if not line.startswith("[") or not line.endswith("]"):
            continue

        match = re.match(r'^\[([^\s]+)\s+"(.*)"\]$', line)
        if match:
            key, value = match.groups()
            headers[key] = value

    return headers


# =========================================================
# Full game analysis
# =========================================================

def analyze_game(
    pgn_text,
    player_elo,
    opponent_elo,
    progress_callback=None,
):
    game = parse_pgn_text(pgn_text)
    headers = extract_pgn_headers(pgn_text)

    preliminary_candidates = []

    screen_stockfish = None
    screen_maia = None

    total_moves = len(game["moves"])

    try:
        # ---------------------------------------------------
        # Phase 1: Fast screening
        # ---------------------------------------------------
        screen_stockfish = StockfishEngine(
            depth=STOCKFISH_SCREEN_DEPTH,
            multipv=STOCKFISH_SCREEN_MULTIPV,
        )

        screen_maia = MaiaEngine(
            model="maia3-79m",
            elo=player_elo,
            self_elo=player_elo,
            oppo_elo=opponent_elo,
            multipv=MAIA_MULTIPV,
        )

        for index, move_data in enumerate(
            game["moves"],
            start=1,
        ):
            result = screen_move(
                move_data=move_data,
                stockfish=screen_stockfish,
                maia=screen_maia,
                player_elo=player_elo,
                opponent_elo=opponent_elo,
            )

            if result["should_annotate"]:
                preliminary_candidates.append(result)

            if progress_callback:
                progress_callback(
                    index,
                    total_moves,
                )

    finally:
        if screen_stockfish is not None:
            screen_stockfish.close()

        if screen_maia is not None:
            screen_maia.close()

    print(
        f"\nScreening produced "
        f"{len(preliminary_candidates)} "
        f"preliminary candidates."
    )

    # -------------------------------------------------------
    # Phase 2: Deep verification
    # -------------------------------------------------------

    verified_candidates = []

    if preliminary_candidates:
        deep_stockfish = StockfishEngine(
            depth=STOCKFISH_DEEP_DEPTH,
            multipv=STOCKFISH_DEEP_MULTIPV,
        )

        try:
            total_candidates = len(
                preliminary_candidates
            )

            for index, candidate in enumerate(
                preliminary_candidates,
                start=1,
            ):
                verified = verify_stockfish_candidate(
                    candidate=candidate,
                    deep_stockfish=deep_stockfish,
                )

                if verified["should_annotate"]:
                    verified_candidates.append(verified)

                print(
                    f"Deep verification "
                    f"{index}/{total_candidates}..."
                )

        finally:
            deep_stockfish.close()

    candidates = verified_candidates

    # -------------------------------------------------------
    # Final candidate list
    # -------------------------------------------------------

    print(
        f"\nVerified "
        f"{len(candidates)} "
        f"final anomaly candidates."
    )

    if candidates:
        print("\nCandidates:\n")

        for index, candidate in enumerate(
            candidates,
            start=1,
        ):
            move_data = candidate["move"]

            reasons = []

            if candidate["stockfish_anomaly"]:
                label = candidate["stockfish"].get(
                    "classification"
                )

                if label:
                    reasons.append(
                        f"Stockfish: {label}"
                    )

            if candidate["maia_anomaly"]:
                reasons.append("human-unusual")

            reason_text = ", ".join(reasons)

            print(
                f"  {index}. "
                f"{move_data['move']} "
                f"(ply {move_data['ply']})"
                f" - {reason_text}"
            )

    # -------------------------------------------------------
    # Phase 3: Gemini annotations
    # -------------------------------------------------------

    annotations = []

    if candidates:
        annotation_inputs = [
            build_annotation_input(
                candidate=candidate,
                player_elo=player_elo,
                opponent_elo=opponent_elo,
            )
            for candidate in candidates
        ]

        print(
            f"\nGenerating {len(annotation_inputs)} coaching "
            "annotations in one Gemini request..."
        )

        try:
            annotations_by_ply = generate_annotations_batch(
                annotation_inputs
            )

        except Exception as exc:
            message = str(exc)

            if (
                "429" in message
                or "quota" in message.lower()
                or "rate limit" in message.lower()
            ):
                print(
                    "\nGemini quota/rate limit reached. "
                    "No batch annotations were generated in this run."
                )
                annotations_by_ply = {}
            else:
                raise

        for candidate in candidates:
            move_data = candidate["move"]
            ply = move_data["ply"]
            annotation = annotations_by_ply.get(ply)

            if not annotation:
                continue

            annotations.append({
                "ply": ply,
                "move_number": move_data["move_number"],
                "player": move_data["player"],
                "move": move_data["move"],
                "stockfish_classification":
                    candidate["stockfish"]["classification"],
                "maia_classification":
                    candidate["maia"]["classification"],
                "annotation": annotation,
            })

        print(
            f"Gemini generated {len(annotations)} of "
            f"{len(candidates)} annotations in 1 request."
        )


    return {
        "game": {
            "white": headers.get("White"),
            "black": headers.get("Black"),
            "result": headers.get("Result"),
        },
        "annotations": annotations,
        "anomaly_count": len(candidates),
        "preliminary_candidate_count":
            len(preliminary_candidates),
        "verified_candidate_count":
            len(candidates),
    }


# =========================================================
# CLI
# =========================================================

def show_progress(current, total):
    if (
        current == 1
        or current == total
        or current % 4 == 0
    ):
        print(
            f"Scanning {current}/{total} moves..."
        )


def main():
    print("Paste the complete PGN.")
    print(
        "When finished, press Ctrl+D "
        "(macOS) on a new line.\n"
    )

    try:
        pgn_text = sys.stdin.read().strip()

    except KeyboardInterrupt:
        print("\nInput cancelled.")
        return

    if not pgn_text:
        print("No PGN provided.")
        return

    try:
        player_elo = int(
            input("\nPlayer Elo: ").strip()
        )

        opponent_elo = int(
            input("Opponent Elo: ").strip()
        )

    except ValueError:
        print("Elo must be an integer.")
        return

    print("\nAnalyzing game...\n")

    try:
        result = analyze_game(
            pgn_text=pgn_text,
            player_elo=player_elo,
            opponent_elo=opponent_elo,
            progress_callback=show_progress,
        )

    except Exception as exc:
        print(f"\nAnalysis failed: {exc}")
        raise

    print("\n========================================")
    print("COACH")
    print("========================================\n")

    if not result["annotations"]:
        if result["verified_candidate_count"] > 0:
            print(
                "Anomalies were detected, but "
                "Gemini did not return annotations."
            )
        else:
            print("No significant anomalies detected.")
        return

    for item in result["annotations"]:
        print(item["move"])
        print(item["annotation"])
        print()


if __name__ == "__main__":
    main()
