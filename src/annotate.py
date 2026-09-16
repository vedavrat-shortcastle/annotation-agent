from __future__ import annotations
from src.pgn_annotator import generate_annotated_pgn
import sys
import time

from src.pgn_parser import parse_pgn_text
from src.stockfish import StockfishEngine
from src.maia import MaiaEngine
from src.annotation import generate_annotations_batch


# =========================================================
# Configuration
# =========================================================

# Phase 1 speed optimization
STOCKFISH_SCREEN_DEPTH = 10
STOCKFISH_SCREEN_MULTIPV = 2

STOCKFISH_DEEP_DEPTH = 16
STOCKFISH_DEEP_MULTIPV = 2

MAIA_MULTIPV = 3

# Chess.com-style thresholds
INACCURACY_THRESHOLD = 0.30
MISTAKE_THRESHOLD = 0.80
BLUNDER_THRESHOLD = 1.50

GREAT_MOVE_GAP = 0.75
BRILLIANT_MOVE_GAP = 1.50

# Maia anomaly detection
MAIA_TOP_K = 5


# =========================================================
# Helpers
# =========================================================

def find_played_move_uci(move_data):
    """Return the UCI move played in the PGN."""
    return move_data["uci"]


def get_move_player(move_data):
    """
    Normalize the player/side field from the PGN parser.

    Returns:
        "White" or "Black"
    """
    player = str(
        move_data.get("player", "")
    ).strip().lower()

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
    Configure Maia so self/opponent Elo corresponds
    to the side that made this move.
    """

    side = get_move_player(
        move_data
    )

    if side == "White":
        self_elo = player_elo
        oppo_elo = opponent_elo
    else:
        self_elo = opponent_elo
        oppo_elo = player_elo

    maia.elo = self_elo
    maia.self_elo = self_elo
    maia.oppo_elo = oppo_elo

    maia.configure(
        elo=self_elo,
        self_elo=self_elo,
        oppo_elo=oppo_elo,
    )


def get_gap_to_second(top_moves):
    """
    Return the evaluation gap between Stockfish's best
    and second-best moves.
    """

    if len(top_moves) < 2:
        return 0.0

    best_eval = top_moves[0].get(
        "evaluation"
    )

    second_eval = top_moves[1].get(
        "evaluation"
    )

    if (
        best_eval is None
        or second_eval is None
    ):
        return 0.0

    return abs(
        best_eval - second_eval
    )


# =========================================================
# Stockfish classification
# =========================================================

def classify_stockfish(
    eval_loss,
    played_uci,
    best_move,
    gap_to_second,
):
    """
    Classify the move from objective evaluation.

    Bad moves:
        inaccuracy >= 0.30
        mistake    >= 0.80
        blunder    >= 1.50

    Exceptional moves:
        great      = best move and gap >= 0.75
        brilliant  = best move and gap >= 1.50
    """

    if eval_loss >= BLUNDER_THRESHOLD:
        return "blunder"

    if eval_loss >= MISTAKE_THRESHOLD:
        return "mistake"

    if eval_loss >= INACCURACY_THRESHOLD:
        return "inaccuracy"

    is_best_move = (
        played_uci == best_move
    )

    if is_best_move:
        if gap_to_second >= BRILLIANT_MOVE_GAP:
            return "brilliant"

        if gap_to_second >= GREAT_MOVE_GAP:
            return "great"

    return None


# =========================================================
# Maia classification
# =========================================================

def classify_maia(
    played_uci,
    maia_result,
):
    """
    Determine whether the played move is unusual
    for the configured human Elo.
    """

    top_moves = maia_result.get(
        "top_moves",
        [],
    )

    if not top_moves:
        return {
            "label": None,
            "rank": None,
        }

    played_rank = None

    for candidate in top_moves:
        if candidate.get("uci") == played_uci:
            played_rank = candidate.get(
                "rank"
            )
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
# Stockfish screening
# =========================================================

def screen_move(
    move_data,
    stockfish,
):
    """
    Cheap Stockfish pass.

    Uses depth 10 / MultiPV 2.

    A move becomes a preliminary candidate when:
      - Stockfish finds an objective anomaly, OR
      - the move is the best move with a large gap to #2.

    This pass intentionally does NOT run deep analysis.
    """

    fen_before = move_data[
        "fen_before"
    ]

    played_uci = find_played_move_uci(
        move_data
    )

    position_result = (
        stockfish.evaluate_position(
            fen_before
        )
    )

    top_moves = position_result.get(
        "top_moves",
        [],
    )

    best_move = position_result.get(
        "best_move"
    )

    best_eval = position_result.get(
        "best_evaluation"
    )

    played_eval = None

    # First try to obtain the played move
    # directly from the MultiPV result.
    for candidate in top_moves:
        if candidate.get("uci") == played_uci:
            played_eval = candidate.get(
                "evaluation"
            )
            break

    # If it wasn't in the top 2, evaluate
    # that specific move at the cheap depth.
    if played_eval is None:
        played_result = (
            stockfish.evaluate_specific_move(
                fen_before,
                played_uci,
            )
        )

        played_eval = played_result.get(
            "evaluation"
        )

    eval_loss = 0.0

    if (
        best_eval is not None
        and played_eval is not None
    ):
        eval_loss = max(
            0.0,
            best_eval - played_eval,
        )

    gap_to_second = get_gap_to_second(
        top_moves
    )

    classification = classify_stockfish(
        eval_loss=eval_loss,
        played_uci=played_uci,
        best_move=best_move,
        gap_to_second=gap_to_second,
    )

    return {
        "move": move_data,
        "played_uci": played_uci,
        "stockfish": {
            "classification": classification,
            "best_move": best_move,
            "best_evaluation": best_eval,
            "played_evaluation": played_eval,
            "evaluation_loss": eval_loss,
            "gap_to_second": gap_to_second,
            "top_moves": top_moves,
        },
    }


def is_preliminary_candidate(
    screen_result,
):
    """
    Decide whether a move deserves expensive
    deep Stockfish verification.
    """

    stockfish = (
        screen_result["stockfish"]
    )

    classification = stockfish.get(
        "classification"
    )

    return classification is not None


# =========================================================
# Deep verification
# =========================================================

def verify_candidate(
    screen_result,
    deep_stockfish,
    maia,
    player_elo,
    opponent_elo,
):
    """
    Deeply verify a preliminary Stockfish candidate
    and then run Maia.

    Maia remains available for every preliminary
    candidate, preserving the anomaly logic.
    """

    move_data = screen_result[
        "move"
    ]

    fen_before = move_data[
        "fen_before"
    ]

    played_uci = find_played_move_uci(
        move_data
    )

    # -------------------------------------------------------
    # Deep Stockfish
    # -------------------------------------------------------

    deep_result = (
        deep_stockfish.evaluate_position(
            fen_before
        )
    )

    top_moves = deep_result.get(
        "top_moves",
        [],
    )

    best_move = deep_result.get(
        "best_move"
    )

    best_eval = deep_result.get(
        "best_evaluation"
    )

    played_eval = None

    for candidate in top_moves:
        if candidate.get("uci") == played_uci:
            played_eval = candidate.get(
                "evaluation"
            )
            break

    if played_eval is None:
        played_result = (
            deep_stockfish.evaluate_specific_move(
                fen_before,
                played_uci,
            )
        )

        played_eval = played_result.get(
            "evaluation"
        )

    eval_loss = 0.0

    if (
        best_eval is not None
        and played_eval is not None
    ):
        eval_loss = max(
            0.0,
            best_eval - played_eval,
        )

    gap_to_second = get_gap_to_second(
        top_moves
    )

    stockfish_label = classify_stockfish(
        eval_loss=eval_loss,
        played_uci=played_uci,
        best_move=best_move,
        gap_to_second=gap_to_second,
    )

    # -------------------------------------------------------
    # Maia
    # -------------------------------------------------------

    configure_maia_for_move(
        maia=maia,
        move_data=move_data,
        player_elo=player_elo,
        opponent_elo=opponent_elo,
    )

    maia_result = maia.analyze(
        fen_before
    )

    maia_classification = classify_maia(
        played_uci,
        maia_result,
    )

    maia_label = maia_classification[
        "label"
    ]

    # -------------------------------------------------------
    # Combined anomaly decision
    # -------------------------------------------------------

    stockfish_anomaly = (
        stockfish_label is not None
    )

    maia_anomaly = (
        maia_label == "unexpected"
    )

    should_annotate = (
        stockfish_anomaly
        or maia_anomaly
    )

    return {
        "move": move_data,
        "played_uci": played_uci,

        "stockfish": {
            "classification": stockfish_label,
            "best_move": best_move,
            "best_evaluation": best_eval,
            "played_evaluation": played_eval,
            "evaluation_loss": eval_loss,
            "gap_to_second": gap_to_second,
            "top_moves": top_moves,
        },

        "maia": {
            "classification": maia_label,
            "rank": maia_classification[
                "rank"
            ],
            "best_move": maia_result.get(
                "best_move"
            ),
            "top_moves": maia_result.get(
                "top_moves",
                [],
            ),
            "elo": maia_result.get(
                "elo"
            ),
            "self_elo": maia_result.get(
                "self_elo"
            ),
            "oppo_elo": maia_result.get(
                "oppo_elo"
            ),
        },

        "stockfish_anomaly": (
            stockfish_anomaly
        ),
        "maia_anomaly": maia_anomaly,
        "should_annotate": (
            should_annotate
        ),
    }


# =========================================================
# Annotation input
# =========================================================

def build_annotation_input(
    candidate,
    player_elo,
    opponent_elo,
):
    """
    Build the stable structure consumed by
    src.annotation.generate_annotations_batch().
    """

    move_data = candidate["move"]

    return {
        "fen": move_data.get("fen"),
        "fen_before": move_data.get(
            "fen_before"
        ),
        "fen_after": move_data.get(
            "fen_after"
        ),

        "played_move": (
            move_data.get("played_move")
            or move_data.get("move")
        ),

        "move": move_data.get(
            "move"
        ),

        "uci": move_data.get(
            "uci"
        ),

        "ply": move_data.get(
            "ply"
        ),

        "move_number": move_data.get(
            "move_number"
        ),

        "player": move_data.get(
            "player"
        ),

        "player_elo": player_elo,

        "opponent_elo": opponent_elo,

        "anomaly_reasons": [],

        "stockfish": candidate[
            "stockfish"
        ],

        "maia": candidate[
            "maia"
        ],

        "stockfish_anomaly": candidate[
            "stockfish_anomaly"
        ],

        "maia_anomaly": candidate[
            "maia_anomaly"
        ],

        "stockfish_classification":
            candidate["stockfish"][
                "classification"
            ],

        "maia_classification":
            candidate["maia"][
                "classification"
            ],
    }


# =========================================================
# Full game analysis
# =========================================================

def analyze_game(
    pgn_text,
    player_elo,
    opponent_elo,
    progress_callback=None,
):
    """
    Phase 1 optimized game pipeline:

        PGN
         ↓
        Stockfish screening
         ↓
        Preliminary candidates
         ↓
        Deep Stockfish verification
         ↓
        Maia analysis
         ↓
        Final anomaly candidates
         ↓
        OpenAI annotations
         ↓
        Annotated PGN
    """

    total_start = time.perf_counter()

    # =========================================================
    # Parse PGN
    # =========================================================

    game = parse_pgn_text(pgn_text)

    moves = game["moves"]

    # Support either "headers" or legacy "metadata"
    headers = game.get(
        "headers",
        game.get("metadata", {}),
    )

    if not moves:
        return {
            "game": {
                "white": headers.get("White"),
                "black": headers.get("Black"),
                "result": headers.get("Result"),
            },
            "annotations": [],
            "annotated_pgn": pgn_text,
            "anomaly_count": 0,
            "preliminary_candidate_count": 0,
            "verified_candidate_count": 0,
        }

    preliminary_candidates = []
    candidates = []

    # =========================================================
    # Phase 1A: Cheap Stockfish screening
    # =========================================================

    screen_start = time.perf_counter()

    screen_stockfish = None

    try:
        screen_stockfish = StockfishEngine(
            depth=STOCKFISH_SCREEN_DEPTH,
            multipv=STOCKFISH_SCREEN_MULTIPV,
        )

        print(
            f"\nScreening {len(moves)} moves "
            "with Stockfish..."
        )

        for index, move_data in enumerate(
            moves,
            start=1,
        ):
            screen_result = screen_move(
                move_data=move_data,
                stockfish=screen_stockfish,
            )

            if is_preliminary_candidate(
                screen_result
            ):
                preliminary_candidates.append(
                    screen_result
                )

            if progress_callback is not None:
                progress_callback(
                    index,
                    len(moves),
                )

    finally:
        if screen_stockfish is not None:
            screen_stockfish.close()

    screen_time = (
        time.perf_counter()
        - screen_start
    )

    print(
        f"\nStockfish screening time: "
        f"{screen_time:.2f}s"
    )

    print(
        f"Screening produced "
        f"{len(preliminary_candidates)} "
        "preliminary candidates."
    )

    # =========================================================
    # Phase 1B: Deep Stockfish + Maia
    # =========================================================

    deep_start = time.perf_counter()

    deep_stockfish = None
    maia = None

    try:
        # -----------------------------------------------------
        # Start deep Stockfish
        # -----------------------------------------------------

        deep_stockfish = StockfishEngine(
            depth=STOCKFISH_DEEP_DEPTH,
            multipv=STOCKFISH_DEEP_MULTIPV,
        )

        # -----------------------------------------------------
        # Start Maia only if candidates exist
        # -----------------------------------------------------

        if preliminary_candidates:
            maia = MaiaEngine(
                model="maia3-79m",
                elo=player_elo,
                self_elo=player_elo,
                oppo_elo=opponent_elo,
                multipv=MAIA_MULTIPV,
            )

        # -----------------------------------------------------
        # Deep verification
        # -----------------------------------------------------

        if preliminary_candidates:
            print(
                f"\nDeep verification of "
                f"{len(preliminary_candidates)} "
                "preliminary candidates..."
            )

        for index, screen_result in enumerate(
            preliminary_candidates,
            start=1,
        ):
            print(
                f"\nDeep verification "
                f"{index}/"
                f"{len(preliminary_candidates)}..."
            )

            try:
                verified = verify_candidate(
                    screen_result=screen_result,
                    deep_stockfish=deep_stockfish,
                    maia=maia,
                    player_elo=player_elo,
                    opponent_elo=opponent_elo,
                )

            except Exception as exc:
                move_data = screen_result["move"]

                print(
                    f"Deep verification failed for "
                    f"ply {move_data.get('ply')}: "
                    f"{type(exc).__name__}: {exc}"
                )

                continue

            if verified["should_annotate"]:
                candidates.append(
                    verified
                )

    finally:
        if deep_stockfish is not None:
            deep_stockfish.close()

        if maia is not None:
            maia.close()

    deep_time = (
        time.perf_counter()
        - deep_start
    )

    print(
        f"\nDeep verification + Maia time: "
        f"{deep_time:.2f}s"
    )

    # =========================================================
    # Final candidates
    # =========================================================

    print(
        f"\nVerified "
        f"{len(candidates)} "
        "final anomaly candidates."
    )

    if candidates:
        print("\nCandidates:")

        for index, candidate in enumerate(
            candidates,
            start=1,
        ):
            move_data = candidate["move"]

            print(
                f"  {index}. "
                f"{move_data['move']} "
                f"(ply {move_data['ply']}) "
                f"- Stockfish: "
                f"{candidate['stockfish']['classification']}"
            )

    # =========================================================
    # Phase 2: OpenAI annotations
    # =========================================================

    annotations = []
    annotations_by_ply = {}

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
            f"\nGenerating "
            f"{len(annotation_inputs)} "
            "coaching annotations "
            "with OpenAI..."
        )

        try:
            annotations_by_ply = (
                generate_annotations_batch(
                    annotation_inputs
                )
            )

        except Exception as exc:
            print(
                f"\nOpenAI annotation generation "
                f"failed: {type(exc).__name__}: {exc}"
            )

            annotations_by_ply = {}

        for candidate in candidates:
            move_data = candidate["move"]
            ply = move_data["ply"]

            annotation = annotations_by_ply.get(
                ply
            )

            if not annotation:
                continue

            annotations.append({
                "ply": ply,

                "move_number":
                    move_data["move_number"],

                "player":
                    move_data["player"],

                "move":
                    move_data["move"],

                "stockfish_classification":
                    candidate[
                        "stockfish"
                    ][
                        "classification"
                    ],

                "maia_classification":
                    candidate[
                        "maia"
                    ][
                        "classification"
                    ],

                "annotation":
                    annotation,
            })

        print(
            f"OpenAI generated "
            f"{len(annotations)} of "
            f"{len(candidates)} "
            "annotations."
        )

    # =========================================================
    # Phase 3: Generate annotated PGN
    # =========================================================

    print(
        "\nGenerating annotated PGN..."
    )

    annotated_pgn = generate_annotated_pgn(
        pgn_text=pgn_text,
        annotations_by_ply=annotations_by_ply,
    )

    print(
        "Annotated PGN generated."
    )

    # =========================================================
    # Total time
    # =========================================================

    total_time = (
        time.perf_counter()
        - total_start
    )

    print(
        f"\nTotal analysis time: "
        f"{total_time:.2f}s"
    )

    # =========================================================
    # Final API response
    # =========================================================

    return {
        "game": {
            "white": headers.get("White"),
            "black": headers.get("Black"),
            "result": headers.get("Result"),
        },

        "annotations": annotations,

        "anomaly_count": len(candidates),

        "annotated_pgn": annotated_pgn,

        "preliminary_candidate_count": len(
            preliminary_candidates
        ),

        "verified_candidate_count": len(
            candidates
        ),
    }
# =========================================================
# CLI
# =========================================================

def show_progress(
    current,
    total,
):
    if (
        current == 1
        or current == total
        or current % 4 == 0
    ):
        print(
            f"Scanning "
            f"{current}/{total} moves..."
        )


def main():
    print(
        "Paste the complete PGN."
    )

    print(
        "When finished, press Ctrl+D "
        "(macOS) on a new line.\n"
    )

    try:
        pgn_text = sys.stdin.read().strip()

    except KeyboardInterrupt:
        print(
            "\nInput cancelled."
        )
        return

    if not pgn_text:
        print(
            "No PGN provided."
        )
        return

    try:
        player_elo = int(
            input(
                "\nPlayer Elo: "
            ).strip()
        )

        opponent_elo = int(
            input(
                "Opponent Elo: "
            ).strip()
        )

    except ValueError:
        print(
            "Elo must be an integer."
        )
        return

    print(
        "\nAnalyzing game...\n"
    )

    try:
        result = analyze_game(
            pgn_text=pgn_text,
            player_elo=player_elo,
            opponent_elo=opponent_elo,
            progress_callback=show_progress,
        )

    except Exception as exc:
        print(
            f"\nAnalysis failed: {exc}"
        )
        raise

    print(
        "\n========================================"
    )
    print("COACH")
    print(
        "========================================\n"
    )

    if not result["annotations"]:
        if (
            result[
                "verified_candidate_count"
            ] > 0
        ):
            print(
                "Anomalies were detected, "
                "but no coaching annotations "
                "were generated."
            )
        else:
            print(
                "No significant anomalies detected."
            )

        return

    for item in result["annotations"]:
        print(
            f"Move "
            f"{item['move_number']}: "
            f"{item['move']}"
        )

        print(
            item["annotation"]
        )

        print()


if __name__ == "__main__":
    main()