import React, { useState } from "react";
import { analyzeGame } from "./api";

function App() {
  const [pgn, setPgn] = useState("");
  const [playerElo, setPlayerElo] = useState(1900);
  const [opponentElo, setOpponentElo] = useState(2100);

  const [result, setResult] = useState(null);
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

    try {
      const data = await analyzeGame({
        pgn,
        player_elo: playerElo,
        opponent_elo: opponentElo,
      });

      console.log("Analysis response:", data);

      setResult(data);
    } catch (err) {
      console.error(err);
      setError(err.message || "Analysis failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header className="header">
        <h1>Annotation Agent</h1>
        <p>
          Personalized chess analysis using
          Stockfish, Maia-3 and an AI coach.
        </p>
      </header>

      <main className="container">
        <section className="card">
          <h2>Analyze Game</h2>

          <div className="elo-row">
            <div>
              <label>Player Elo</label>
              <input
                type="number"
                value={playerElo}
                onChange={(e) =>
                  setPlayerElo(e.target.value)
                }
              />
            </div>

            <div>
              <label>Opponent Elo</label>
              <input
                type="number"
                value={opponentElo}
                onChange={(e) =>
                  setOpponentElo(e.target.value)
                }
              />
            </div>
          </div>

          <label>PGN</label>

          <textarea
            value={pgn}
            onChange={(e) => setPgn(e.target.value)}
            placeholder="Paste your chess game PGN here..."
            rows={14}
          />

          <button
            onClick={handleAnalyze}
            disabled={loading}
          >
            {loading
              ? "Analyzing..."
              : "Analyze Game"}
          </button>

          {error && (
            <div className="error">
              {error}
            </div>
          )}
        </section>

        {result && (
          <section className="results">
            <div className="card">
              <h2>Analysis</h2>

              {result.game && (
                <div className="game-info">
                  <strong>
                    {result.game.white || "White"}
                  </strong>
                  {" vs "}
                  <strong>
                    {result.game.black || "Black"}
                  </strong>

                  {result.game.result && (
                    <span>
                      {" "}({result.game.result})
                    </span>
                  )}
                </div>
              )}

              <div className="stats">
                <div>
                  <strong>
                    {result.anomaly_count ?? 0}
                  </strong>
                  <span>
                    Verified anomalies
                  </span>
                </div>

                <div>
                  <strong>
                    {result.annotations?.length ?? 0}
                  </strong>
                  <span>
                    Coaching annotations
                  </span>
                </div>
              </div>
            </div>

            <div className="card">
              <h2>Coach</h2>

              {result.annotations &&
              result.annotations.length > 0 ? (
                <div className="annotation-list">
                  {result.annotations.map(
                    (item) => (
                      <article
                        className="annotation"
                        key={item.ply}
                      >
                        <div className="annotation-header">
                          <strong>
                            {item.move}
                          </strong>

                          <span>
                            Ply {item.ply}
                          </span>
                        </div>

                        <div className="labels">
                          {item.stockfish_classification && (
                            <span className="label">
                              {
                                item.stockfish_classification
                              }
                            </span>
                          )}

                          {item.maia_classification && (
                            <span className="label">
                              {
                                item.maia_classification
                              }
                            </span>
                          )}
                        </div>

                        <p>
                          {item.annotation}
                        </p>
                      </article>
                    )
                  )}
                </div>
              ) : (
                <p>
                  No coaching annotations were
                  returned.
                </p>
              )}
            </div>

            {result.anomaly_count >
              (result.annotations?.length ?? 0) && (
              <div className="notice">
                Some detected anomalies did not
                receive coaching text.
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}

export default App;