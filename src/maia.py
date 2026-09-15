from pathlib import Path

import chess
import chess.engine


# =========================================================
# Maia installation
# =========================================================

MAIA_DIR = Path.home() / "chess" / "maia3-engine"
MAIA_PYTHON = MAIA_DIR / "venv" / "bin" / "python"

if not MAIA_PYTHON.exists():
    raise RuntimeError(
        f"Maia Python interpreter not found: {MAIA_PYTHON}"
    )


class MaiaEngine:
    def __init__(
        self,
        model="maia3-79m",
        elo=1900,
        self_elo=1900,
        oppo_elo=1900,
        multipv=5,
    ):
        self.elo = elo
        self.self_elo = self_elo
        self.oppo_elo = oppo_elo
        self.multipv = multipv

        command = [
            str(MAIA_PYTHON),
            "-m",
            "maia3.uci",
            "--model",
            model,
        ]

        # Start Maia once and keep the UCI process alive.
        self.engine = chess.engine.SimpleEngine.popen_uci(
            command,
            cwd=str(MAIA_DIR),
        )

        self.configure(
            elo=elo,
            self_elo=self_elo,
            oppo_elo=oppo_elo,
        )

    def configure(
        self,
        elo=None,
        self_elo=None,
        oppo_elo=None,
    ):
        """
        Update Maia's Elo settings.

        MultiPV is intentionally NOT configured here.
        python-chess manages MultiPV through analyse(..., multipv=...).
        """

        if elo is not None:
            self.elo = elo

        if self_elo is not None:
            self.self_elo = self_elo

        if oppo_elo is not None:
            self.oppo_elo = oppo_elo

        self.engine.configure({
            "Elo": self.elo,
            "SelfElo": self.self_elo,
            "OppoElo": self.oppo_elo,
        })

    def close(self):
        """Shut down Maia cleanly."""
        if self.engine is not None:
            self.engine.quit()
            self.engine = None

    def analyze(self, fen):
        """
        Analyze one position and return Maia's top human-likely moves.
        """

        board = chess.Board(fen)

        infos = self.engine.analyse(
            board,
            chess.engine.Limit(depth=1),
            multipv=self.multipv,
        )

        candidates = []

        for rank, info in enumerate(infos, start=1):
            pv = info.get("pv", [])

            if not pv:
                continue

            move = pv[0]
            score = info["score"].pov(board.turn)

            if score.is_mate():
                mate = score.mate()

                if mate is not None and mate > 0:
                    score_cp = 10000
                else:
                    score_cp = -10000
            else:
                score_cp = score.score()

            candidates.append({
                "rank": rank,
                "move": board.san(move),
                "uci": move.uci(),
                "score_cp": score_cp,
                "wdl": None,
            })

        return {
            "fen": fen,
            "model": "Maia3-79M",
            "elo": self.elo,
            "self_elo": self.self_elo,
            "oppo_elo": self.oppo_elo,
            "best_move": (
                candidates[0]["uci"]
                if candidates
                else None
            ),
            "top_moves": candidates,
        }