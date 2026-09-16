from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI


# =========================================================
# Configuration
# =========================================================

MODEL = "gpt-5.6-luna"
MAX_OUTPUT_TOKENS = 4000


# =========================================================
# OpenAI client
# =========================================================

_api_key = os.getenv("OPENAI_API_KEY")

if not _api_key:
    raise RuntimeError(
        "OPENAI_API_KEY environment variable is not set."
    )

client = OpenAI(api_key=_api_key)


# =========================================================
# System prompt
# =========================================================

SYSTEM_PROMPT = """
You are a strong, friendly chess coach.

Your job is to explain specific moves from a real chess game using BOTH
objective chess analysis and human-move analysis.

You will receive:

1. Stockfish evidence
   - Use this to understand the objective chess quality of the played move.
   - Use it to explain concrete tactical, positional, or strategic consequences.
   - A supplied best move may be mentioned when it is useful and verified by the
     supplied evidence.

2. Maia evidence
   - Use this to understand what a human player around the supplied Elo would
     naturally consider.
   - Maia's top_moves are human-like candidate moves.
   - When useful, naturally mention one of those human-like alternatives in the
     coaching explanation.

IMPORTANT:

- Never mention Stockfish.
- Never mention Maia.
- Never mention engines or models.
- Never mention evaluation scores.
- Never mention engine rankings.
- Never mention predicted Elo.
- Never mention internal classifications such as "blunder", "mistake",
  "inaccuracy", "unexpected", "natural", or "most_natural".
- Do not expose probabilities or ranks.
- Do not invent a move, square, piece, tactic, or variation.
- Only use moves and chess ideas supported by the supplied data.
- Do not contradict the supplied evidence.
- Do not automatically suggest an alternative unless the supplied evidence
  contains that move.
- Prefer a human-like alternative from the supplied Maia top_moves when such
  an alternative helps the explanation.
- Prefer the supplied objective best move when explaining what would have been
  objectively stronger.
- If both Maia and Stockfish provide useful alternatives, combine them naturally
  rather than listing them mechanically.
- Explain what happened and what the player can learn.
- Focus on the specific move and position.
- Do not give generic praise or criticism.

Write exactly 2–4 natural sentences per annotation.

Sound like a human chess coach reviewing the player's game.

Do not use headings, bullets, labels, metadata, or JSON inside each comment.
Return only the requested structured JSON.
"""


# =========================================================
# Structured output schema
# =========================================================

ANNOTATION_SCHEMA = {
    "type": "object",
    "properties": {
        "annotations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ply": {"type": "integer"},
                    "comment": {"type": "string"},
                },
                "required": ["ply", "comment"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["annotations"],
    "additionalProperties": False,
}


# =========================================================
# Helpers
# =========================================================

def _safe_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    return {}


def _clean_comment(comment: Any) -> str:
    if comment is None:
        return ""

    text = str(comment).strip()

    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1].strip()

    return text


def _move_summary(move: dict) -> str:
    parts = []

    if move.get("rank") is not None:
        parts.append(f"rank={move.get('rank')}")

    if move.get("uci"):
        parts.append(f"uci={move.get('uci')}")

    if move.get("move"):
        parts.append(f"move={move.get('move')}")

    if move.get("evaluation") is not None:
        parts.append(f"evaluation={move.get('evaluation')}")

    return ", ".join(parts)


# =========================================================
# Build annotation input
# =========================================================

def build_annotation_input(
    candidate: dict,
    player_elo: int,
    opponent_elo: int,
) -> dict:
    """Build the complete evidence package sent to OpenAI."""

    move_data = _safe_dict(candidate.get("move"))
    stockfish = _safe_dict(candidate.get("stockfish"))
    maia = _safe_dict(candidate.get("maia"))

    stockfish_top_moves = stockfish.get("top_moves", [])
    maia_top_moves = maia.get("top_moves", [])

    compact_stockfish_moves = []
    for move in stockfish_top_moves:
        move = _safe_dict(move)
        compact_stockfish_moves.append(
            {
                "rank": move.get("rank"),
                "uci": move.get("uci"),
                "move": move.get("move"),
                "evaluation": move.get("evaluation"),
            }
        )

    compact_maia_moves = []
    for move in maia_top_moves:
        move = _safe_dict(move)
        compact_maia_moves.append(
            {
                "rank": move.get("rank"),
                "uci": move.get("uci"),
                "move": move.get("move"),
            }
        )

    return {
        "ply": move_data.get("ply"),
        "move_number": move_data.get("move_number"),
        "player": move_data.get("player"),
        "move": move_data.get("move"),
        "uci": move_data.get("uci"),
        "fen_before": move_data.get("fen_before"),
        "fen_after": move_data.get("fen_after"),
        "player_elo": player_elo,
        "opponent_elo": opponent_elo,
        "stockfish": {
            "classification": stockfish.get("classification"),
            "best_move": stockfish.get("best_move"),
            "best_evaluation": stockfish.get("best_evaluation"),
            "played_evaluation": stockfish.get("played_evaluation"),
            "evaluation_loss": stockfish.get("evaluation_loss"),
            "gap_to_second": stockfish.get("gap_to_second"),
            "top_moves": compact_stockfish_moves,
        },
        "maia": {
            "classification": maia.get("classification"),
            "rank": maia.get("rank"),
            "best_move": maia.get("best_move"),
            "elo": maia.get("elo"),
            "self_elo": maia.get("self_elo"),
            "oppo_elo": maia.get("oppo_elo"),
            "top_moves": compact_maia_moves,
        },
        "stockfish_anomaly": candidate.get("stockfish_anomaly"),
        "maia_anomaly": candidate.get("maia_anomaly"),
    }


# =========================================================
# Build batch prompt
# =========================================================

def _build_batch_prompt(annotation_inputs: list[dict]) -> str:
    blocks = []

    for item in annotation_inputs:
        stockfish = _safe_dict(item.get("stockfish"))
        maia = _safe_dict(item.get("maia"))

        sf_alternatives = []
        for sf_move in stockfish.get("top_moves", []):
            summary = _move_summary(_safe_dict(sf_move))
            if summary:
                sf_alternatives.append(summary)

        maia_alternatives = []
        for maia_move in maia.get("top_moves", []):
            summary = _move_summary(_safe_dict(maia_move))
            if summary:
                maia_alternatives.append(summary)

        block = {
            "ply": item.get("ply"),
            "move_number": item.get("move_number"),
            "player": item.get("player"),
            "played_move": item.get("move"),
            "uci": item.get("uci"),
            "fen_before": item.get("fen_before"),
            "fen_after": item.get("fen_after"),
            "player_elo": item.get("player_elo"),
            "opponent_elo": item.get("opponent_elo"),
            "stockfish": {
                "classification": stockfish.get("classification"),
                "best_move": stockfish.get("best_move"),
                "best_evaluation": stockfish.get("best_evaluation"),
                "played_evaluation": stockfish.get("played_evaluation"),
                "evaluation_loss": stockfish.get("evaluation_loss"),
                "gap_to_second": stockfish.get("gap_to_second"),
                "top_moves": sf_alternatives,
            },
            "maia": {
                "classification": maia.get("classification"),
                "best_move": maia.get("best_move"),
                "human_likely_moves": maia_alternatives,
            },
            "stockfish_anomaly": item.get("stockfish_anomaly"),
            "maia_anomaly": item.get("maia_anomaly"),
        }

        blocks.append(
            json.dumps(block, ensure_ascii=False, indent=2)
        )

    return (
        "Analyze the following chess moves.\n\n"
        "For EACH candidate, use BOTH the objective chess evidence "
        "and the human-move evidence.\n\n"
        "The Stockfish section describes objective chess quality.\n"
        "The Maia section describes moves a human around the configured Elo "
        "would naturally consider.\n\n"
        "When appropriate, make the coaching explanation include a natural "
        "human-level alternative from Maia's supplied human_likely_moves.\n\n"
        "Do not mention the names of the systems or any internal labels in the comments.\n\n"
        "Return exactly one annotation for every supplied ply.\n\n"
        "CANDIDATES:\n\n"
        + "\n\n--- CANDIDATE ---\n\n".join(blocks)
    )


# =========================================================
# Batch annotation generation
# =========================================================

def generate_annotations_batch(annotation_inputs: list[dict]) -> dict[int, str]:
    """Generate all coaching annotations in one OpenAI request."""

    if not annotation_inputs:
        return {}

    prompt = _build_batch_prompt(annotation_inputs)

    print(
        f"Generating {len(annotation_inputs)} coaching annotations "
        "with OpenAI in one request..."
    )

    response = client.responses.create(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        input=prompt,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        reasoning={"effort": "none"},
        text={
            "format": {
                "type": "json_schema",
                "name": "chess_annotations",
                "strict": True,
                "schema": ANNOTATION_SCHEMA,
            }
        },
    )

    output_text = getattr(response, "output_text", None)

    if not output_text:
        raise RuntimeError("OpenAI returned no output_text.")

    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenAI returned invalid JSON.") from exc

    raw_annotations = parsed.get("annotations")
    if not isinstance(raw_annotations, list):
        raise RuntimeError(
            "OpenAI response does not contain an annotations array."
        )

    annotations_by_ply: dict[int, str] = {}

    for item in raw_annotations:
        if not isinstance(item, dict):
            continue

        ply = item.get("ply")
        comment = _clean_comment(item.get("comment"))

        if not isinstance(ply, int):
            continue

        if not comment:
            continue

        annotations_by_ply[ply] = comment

    expected_plies = {
        item.get("ply")
        for item in annotation_inputs
        if isinstance(item.get("ply"), int)
    }

    actual_plies = set(annotations_by_ply.keys())
    missing = expected_plies - actual_plies
    extras = actual_plies - expected_plies

    if extras:
        print(
            "Warning: OpenAI returned unexpected plies: "
            f"{sorted(extras)}"
        )

    if missing:
        print(
            "Warning: OpenAI did not return annotations for plies: "
            f"{sorted(missing)}"
        )

    print(
        f"OpenAI generated {len(annotations_by_ply)} of "
        f"{len(expected_plies)} annotations in one request."
    )

    return annotations_by_ply


# =========================================================
# Single annotation compatibility wrapper
# =========================================================

def generate_annotation(
    annotation_input: dict | None = None,
    *,
    move: str | None = None,
    fen: str | None = None,
    played_move: str | None = None,
    stockfish: dict | None = None,
    maia: dict | None = None,
    player_elo: int | None = None,
    opponent_elo: int | None = None,
) -> str:
    """Compatibility wrapper for older calling code."""

    if annotation_input is None:
        annotation_input = {
            "ply": 1,
            "move": move,
            "uci": played_move,
            "fen_before": fen,
            "player_elo": player_elo,
            "opponent_elo": opponent_elo,
            "stockfish": stockfish or {},
            "maia": maia or {},
            "stockfish_anomaly": True,
            "maia_anomaly": False,
        }

    annotations = generate_annotations_batch([annotation_input])
    ply = annotation_input.get("ply")

    if ply in annotations:
        return annotations[ply]

    raise RuntimeError(
        f"OpenAI did not return an annotation for ply {ply}."
    )

