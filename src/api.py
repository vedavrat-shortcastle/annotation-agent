from pydantic import BaseModel

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .annotate import analyze_game
from .stockfish import StockfishEngine, STOCKFISH_PATH


app = FastAPI(
    title="Annotation Agent API"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GameAnalysisRequest(BaseModel):
    pgn: str
    player_elo: int = 1900
    opponent_elo: int = 2100


class StockfishRequest(BaseModel):
    fen: str
    depth: int = 18
    multipv: int = 5


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.get("/stockfish/status")
def stockfish_status():
    return {
        "installed": STOCKFISH_PATH is not None,
        "path": STOCKFISH_PATH,
    }


@app.post("/stockfish/analyze")
def stockfish_analyze(request: StockfishRequest):
    engine = None

    try:
        engine = StockfishEngine(
            depth=request.depth,
            multipv=request.multipv,
        )

        return engine.evaluate_position(request.fen)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid FEN",
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    finally:
        if engine is not None:
            engine.close()


@app.post("/games/analyze")
def game_analyze(request: GameAnalysisRequest):
    try:
        return analyze_game(
            pgn_text=request.pgn,
            player_elo=request.player_elo,
            opponent_elo=request.opponent_elo,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )