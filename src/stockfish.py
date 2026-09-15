import shutil
import chess
import chess.engine

STOCKFISH_PATH = shutil.which("stockfish")

if not STOCKFISH_PATH:
    raise RuntimeError("Stockfish not found in PATH")


class StockfishEngine:
    def __init__(self, depth=16, multipv=5):
        self.depth = depth
        self.multipv = multipv
        self.engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)

    def close(self):
        if self.engine:
            self.engine.quit()

    def evaluate_position(self, fen):
        board = chess.Board(fen)

        infos = self.engine.analyse(
            board,
            chess.engine.Limit(depth=self.depth),
            multipv=self.multipv,
        )

        results = []

        for info in infos:
            pv = info.get("pv", [])
            score = info["score"].pov(board.turn)

            results.append({
                "move": board.san(pv[0]) if pv else None,
                "uci": pv[0].uci() if pv else None,
                "evaluation": score_to_float(score),
                "pv": [move.uci() for move in pv],
            })

        best = results[0] if results else None

        return {
            "fen": fen,
            "best_move": best["uci"] if best else None,
            "best_evaluation": best["evaluation"] if best else None,
            "top_moves": results,
        }

    def evaluate_specific_move(self, fen, move_uci):
        board = chess.Board(fen)

        move = chess.Move.from_uci(move_uci)

        if move not in board.legal_moves:
            raise ValueError(f"Illegal move: {move_uci}")

        mover = board.turn
        san = board.san(move)

        board.push(move)

        info = self.engine.analyse(
            board,
            chess.engine.Limit(depth=self.depth),
        )

        score = info["score"].pov(mover)

        pv = info.get("pv", [])

        return {
            "move": san,
            "uci": move_uci,
            "evaluation": score_to_float(score),
            "pv": [m.uci() for m in pv],
        }


def score_to_float(score):
    if score.is_mate():
        mate = score.mate()

        if mate is None:
            return 0.0

        return 100.0 if mate > 0 else -100.0

    return score.score(mate_score=10000) / 100.0