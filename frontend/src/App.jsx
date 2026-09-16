import React, { useState } from "react";
import { analyzeGame } from "./api";

function App() {
  const [pgn, setPgn] = useState("");
  const [playerElo, setPlayerElo] = useState(1900);
  const [opponentElo, setOpponentElo] = useState(2100);

  const [result, setResult] = useState(null);
  const [annotatedPgn, setAnnotatedPgn] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleAnalyze() {
    if (!pgn.trim()) {
      setError("Please paste a PGN first.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);
    setAnnotatedPgn("");

    try {
      const data = await analyzeGame({
        pgn,
        player_elo: playerElo,
        opponent_elo: opponentElo,
      });

      setResult(data);
      setAnnotatedPgn(data.annotated_pgn || "");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Game analysis failed."
      );
    } finally {
      setLoading(false);
    }
  }

  function downloadAnnotatedPgn() {
    if (!annotatedPgn) return;

    const blob = new Blob(
      [annotatedPgn],
      {
        type: "application/x-chess-pgn;charset=utf-8",
      }
    );

    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.href = url;
    link.download = "annotated_game.pgn";

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    URL.revokeObjectURL(url);
  }

  function formatPlayerName(name, fallback) {
    return name && name !== "?" ? name : fallback;
  }

  return (
    <div className="app">
      {/* =====================================================
          Header
          ===================================================== */}
      <header className="header">
        <div>
          <div className="eyebrow">SHORTCASTLE</div>
          <h1>Chess Annotation Agent</h1>
          <p>
            Personalized chess coaching from your own game.
          </p>
        </div>
      </header>

      <main className="main">
        {/* =================================================
            Input section
            ================================================= */}
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Analyze a game</h2>
              <p>
                Paste a complete PGN and add the player ratings.
              </p>
            </div>
          </div>

          <div className="elo-row">
            <div className="field">
              <label htmlFor="player-elo">
                Player Elo
              </label>

              <input
                id="player-elo"
                type="number"
                min="1"
                value={playerElo}
                onChange={(event) =>
                  setPlayerElo(event.target.value)
                }
              />
            </div>

            <div className="field">
              <label htmlFor="opponent-elo">
                Opponent Elo
              </label>

              <input
                id="opponent-elo"
                type="number"
                min="1"
                value={opponentElo}
                onChange={(event) =>
                  setOpponentElo(event.target.value)
                }
              />
            </div>
          </div>

          <div className="field">
            <label htmlFor="pgn">
              PGN
            </label>

            <textarea
              id="pgn"
              value={pgn}
              onChange={(event) =>
                setPgn(event.target.value)
              }
              placeholder={`[Event "Live Chess"]
[Site "Chess.com"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 ...`}
              rows={15}
            />
          </div>

          {error && (
            <div className="error">
              {error}
            </div>
          )}

          <button
            className="analyze-button"
            onClick={handleAnalyze}
            disabled={loading}
          >
            {loading ? "Analyzing..." : "Analyze Game"}
          </button>
        </section>

        {/* =================================================
            Results
            ================================================= */}
        {result && (
          <section className="results">
            {/* Game summary */}
            <div className="results-header">
              <div>
                <div className="eyebrow">
                  ANALYSIS COMPLETE
                </div>

                <h2>Coach Notes</h2>

                <p>
                  {formatPlayerName(
                    result.game?.white,
                    "White"
                  )}{" "}
                  vs{" "}
                  {formatPlayerName(
                    result.game?.black,
                    "Black"
                  )}
                </p>
              </div>

              <button
                className="download-button"
                onClick={downloadAnnotatedPgn}
                disabled={!annotatedPgn}
              >
                Download Annotated PGN
              </button>
            </div>

            {/* =================================================
                Stats
                ================================================= */}
            <div className="stats-grid">
              <div className="stat-card">
                <span className="stat-label">
                  Anomalies
                </span>

                <strong>
                  {result.anomaly_count ?? 0}
                </strong>
              </div>

              <div className="stat-card">
                <span className="stat-label">
                  Screened
                </span>

                <strong>
                  {result.preliminary_candidate_count ??
                    0}
                </strong>
              </div>

              <div className="stat-card">
                <span className="stat-label">
                  Verified
                </span>

                <strong>
                  {result.verified_candidate_count ??
                    0}
                </strong>
              </div>

              <div className="stat-card">
                <span className="stat-label">
                  Result
                </span>

                <strong>
                  {result.game?.result || "—"}
                </strong>
              </div>
            </div>

            {/* =================================================
                Annotation cards
                ================================================= */}
            <div className="annotations">
              {result.annotations &&
              result.annotations.length > 0 ? (
                result.annotations.map(
                  (item, index) => {
                    const moveNumber =
                      item.move_number ??
                      Math.ceil(item.ply / 2);

                    return (
                      <article
                        className="annotation-card"
                        key={`${item.ply}-${index}`}
                      >
                        <div className="move-number">
                          {moveNumber}
                          {item.player === "Black"
                            ? "..."
                            : "."}
                        </div>

                        <div className="annotation-content">
                          <div className="move-name">
                            {item.move}
                          </div>

                          <p>
                            {item.annotation}
                          </p>
                        </div>
                      </article>
                    );
                  }
                )
              ) : (
                <div className="empty-state">
                  No significant anomalies were detected
                  in this game.
                </div>
              )}
            </div>

            {/* =================================================
                Download section
                ================================================= */}
            {annotatedPgn && (
              <div className="download-panel">
                <div>
                  <h3>
                    Annotated PGN ready
                  </h3>

                  <p>
                    Your coaching comments have been
                    inserted directly into the PGN.
                  </p>
                </div>

                <button
                  className="download-button"
                  onClick={downloadAnnotatedPgn}
                >
                  Download annotated_game.pgn
                </button>
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}

export default App;