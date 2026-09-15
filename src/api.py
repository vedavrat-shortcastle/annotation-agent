from typing import Optional
from .maia import analyze_maia
import chess
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .stockfish import evaluate_position
import shutil
import subprocess


app = FastAPI(title="Chess AI Coach API")


# Local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MaiaRequest(BaseModel):
    fen: str
    elo: int = 1900
    self_elo: int = 1900
    oppo_elo: int = 2100
    multipv: int = 5
class AnalyzeRequest(BaseModel):
    fen: str
    depth: int = Field(default=18, ge=1, le=30)
    multipv: int = Field(default=5, ge=1, le=10)


class PGNRequest(BaseModel):
    pgn: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/stockfish/status")
def stockfish_status():
    path = shutil.which("stockfish")

    if path is None:
        return {
            "available": False,
            "version": None,
        }

    try:
        process = subprocess.run(
            [path],
            input="uci\nquit\n",
            text=True,
            capture_output=True,
            timeout=5,
        )

        version = None

        for line in process.stdout.splitlines():
            if line.startswith("Stockfish"):
                version = line.strip()
                break

        return {
            "available": True,
            "version": version or "Stockfish",
        }

    except Exception:
        return {
            "available": False,
            "version": None,
        }


@app.post("/stockfish/analyze")
def analyze_stockfish(request: AnalyzeRequest):
    try:
        # Validate FEN before calling Stockfish
        chess.Board(request.fen)

        result = evaluate_position(
            request.fen,
            depth=request.depth,
            multipv=request.multipv,
        )

        return result

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid FEN.",
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Stockfish analysis failed: {str(exc)}",
        )


@app.post("/games/parse")
def parse_game(request: PGNRequest):
    # Keep parsing logic in pgn_parser.py
    import io
    import chess.pgn

    try:
        game = chess.pgn.read_game(io.StringIO(request.pgn))

        if game is None:
            raise HTTPException(
                status_code=400,
                detail="Invalid PGN.",
            )

        # Import existing parser function
        from .pgn_parser import parse_game as parse_game_data

        return parse_game_data(game)

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"PGN parsing failed: {str(exc)}",
        )
@app.post("/maia/analyze")
def maia_analyze(request: MaiaRequest):
    try:
        return analyze_maia(
            fen=request.fen,
            elo=request.elo,
            self_elo=request.self_elo,
            oppo_elo=request.oppo_elo,
            multipv=request.multipv,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid FEN")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))