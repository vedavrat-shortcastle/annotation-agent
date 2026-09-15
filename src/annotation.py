import json
import os
import re
from typing import Any

from google import genai


MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")


SYSTEM_PROMPT = """
You are a human chess coach.

Your job is to explain only the chess anomalies identified by the supplied analysis.
Use the objective chess calculation evidence as factual evidence and the human-likelihood evidence as context about how natural or unusual the move is for the stated Elo.

Rules:
- Do not mention Stockfish, Maia, Gemini, engines, models, scores, ranks, MultiPV, centipawns, or WDL in the coaching text.
- Do not invent tactics, threats, variations, or positions that are not supported by the supplied board state and evidence.
- Explain the practical chess idea a player at the stated level should understand.
- Be specific about what the played move did and what kind of improvement would make sense when the evidence supports it.
- Keep each annotation to 2-5 sentences.
- No Markdown, headings, bullets, or numbering inside an annotation.
""".strip()


def get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    return genai.Client(api_key=api_key)


def build_prompt(move_data: dict[str, Any]) -> str:
    return json.dumps(move_data, ensure_ascii=False, indent=2)


def _extract_json(text: str) -> Any:
    """Parse JSON even when the model wraps it in a Markdown code fence."""
    text = (text or "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = re.search(
        r"```(?:json)?\s*(.*?)\s*```",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if fenced:
        return json.loads(fenced.group(1))

    array_start = text.find("[")
    array_end = text.rfind("]")
    if array_start != -1 and array_end > array_start:
        return json.loads(text[array_start:array_end + 1])

    object_start = text.find("{")
    object_end = text.rfind("}")
    if object_start != -1 and object_end > object_start:
        return json.loads(text[object_start:object_end + 1])

    raise ValueError("Gemini response did not contain valid JSON")


def generate_annotation(move_data: dict[str, Any]) -> str:
    """
    Backwards-compatible single-item annotation helper.
    The main pipeline uses generate_annotations_batch().
    """
    client = get_client()

    prompt = """
Return one coaching annotation for the supplied chess anomaly.
Return ONLY the annotation text, with no Markdown and no JSON.

ANOMALY:
""" + build_prompt(move_data)

    response = client.interactions.create(
        model=MODEL,
        system_instruction=SYSTEM_PROMPT,
        input=prompt,
    )

    annotation = (response.output_text or "").strip()
    if not annotation:
        raise RuntimeError("Gemini returned an empty annotation")

    return annotation


def generate_annotations_batch(move_data_list: list[dict[str, Any]]) -> dict[int, str]:
    """
    Generate all anomaly annotations in ONE Gemini request.

    Returns:
        {ply: annotation_text}
    """
    if not move_data_list:
        return {}

    client = get_client()

    payload = {
        "tasks": [
            {
                "ply": item["ply"],
                "move": item["move"],
                "fen_before": item.get("fen_before"),
                "fen_after": item.get("fen_after"),
                "uci": item.get("uci"),
                "move_number": item.get("move_number"),
                "player": item.get("player"),
                "player_elo": item.get("player_elo"),
                "opponent_elo": item.get("opponent_elo"),
                "anomaly_reasons": item.get("anomaly_reasons", []),
                "stockfish": item.get("stockfish", {}),
                "maia": item.get("maia", {}),
                "stockfish_anomaly": item.get("stockfish_anomaly", False),
                "maia_anomaly": item.get("maia_anomaly", False),
            }
            for item in move_data_list
        ]
    }

    prompt = """
Generate one coaching annotation for EVERY task below.

Return ONLY a JSON array.
The array must contain exactly one object for every task, in the same order.
Each object must have exactly these fields:
{"ply": <integer>, "annotation": "<2-5 sentence coaching annotation>"}

Do not omit tasks.
Do not add commentary before or after the JSON array.

TASKS:
""" + json.dumps(payload, ensure_ascii=False, indent=2)

    response = client.interactions.create(
        model=MODEL,
        system_instruction=SYSTEM_PROMPT,
        input=prompt,
    )

    raw = (response.output_text or "").strip()
    if not raw:
        raise RuntimeError("Gemini returned an empty batch response")

    parsed = _extract_json(raw)

    if isinstance(parsed, dict):
        parsed = parsed.get("annotations")

    if not isinstance(parsed, list):
        raise ValueError("Gemini batch response must be a JSON array")

    expected_plies = [int(item["ply"]) for item in move_data_list]
    annotations_by_ply: dict[int, str] = {}

    for item in parsed:
        if not isinstance(item, dict):
            raise ValueError("Gemini batch response contains a non-object item")

        if "ply" not in item or "annotation" not in item:
            raise ValueError("Gemini batch item is missing ply or annotation")

        ply = int(item["ply"])
        annotation = str(item["annotation"]).strip()

        if not annotation:
            raise ValueError(f"Empty Gemini annotation for ply {ply}")

        annotations_by_ply[ply] = annotation

    missing = [ply for ply in expected_plies if ply not in annotations_by_ply]
    extra = [ply for ply in annotations_by_ply if ply not in expected_plies]

    if missing:
        raise ValueError(
            f"Gemini batch response is missing annotations for plies: {missing}"
        )

    if extra:
        raise ValueError(
            f"Gemini batch response returned unexpected plies: {extra}"
        )

    return annotations_by_ply
