import React, { useEffect, useState } from "react";

import {
  analyzeStockfish,
  analyzeMaia,
  getHealth,
  getStockfishStatus,
} from "./api";


function App() {
  const [fen, setFen] = useState(
    "rn1qkb1r/pp3ppp/2pppn2/6Bb/3PP3/2N2N1P/PPP1BPP1/R2QK2R b KQkq - 2 7"
  );

  const [depth, setDepth] = useState(18);
  const [multipv, setMultipv] = useState(5);

  const [maiaSelfElo, setMaiaSelfElo] = useState(1900);
  const [maiaOppoElo, setMaiaOppoElo] = useState(2100);

  const [result, setResult] = useState(null);
  const [maiaResult, setMaiaResult] = useState(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [backendStatus, setBackendStatus] = useState("Checking...");
  const [stockfishStatus, setStockfishStatus] = useState("Checking...");


  useEffect(() => {
    async function checkStatus() {
      try {
        const health = await getHealth();

        setBackendStatus(
          health.status === "ok"
            ? "Online"
            : health.status || "Online"
        );

        const stockfish = await getStockfishStatus();

        setStockfishStatus(
          stockfish.installed
            ? "Installed"
            : "Not Found"
        );
      } catch (err) {
        setBackendStatus("Offline");
        setStockfishStatus("Unavailable");
      }
    }

    checkStatus();
  }, []);


  async function handleAnalyze() {
    setLoading(true);
    setError("");

    setResult(null);
    setMaiaResult(null);

    try {
      const [stockfishData, maiaData] =
        await Promise.all([
          analyzeStockfish({
            fen,
            depth: Number(depth),
            multipv: Number(multipv),
          }),

          analyzeMaia({
            fen,
            elo: Number(maiaSelfElo),
            self_elo: Number(maiaSelfElo),
            oppo_elo: Number(maiaOppoElo),
            multipv: Number(multipv),
          }),
        ]);

      setResult(stockfishData);
      setMaiaResult(maiaData);

    } catch (err) {
      setError(
        err.message || "Analysis failed."
      );
    } finally {
      setLoading(false);
    }
  }


  return (
    <div className="app">

      <header className="header">

        <div>
          <h1>Chess Analysis</h1>
          <p>
            Stockfish 19 + Maia-3
          </p>
        </div>


        <div className="status-container">

          <div className="status">
            <span
              className={
                backendStatus === "Online"
                  ? "dot online"
                  : "dot offline"
              }
            />

            Backend: {backendStatus}
          </div>


          <div className="status">
            <span
              className={
                stockfishStatus === "Installed"
                  ? "dot online"
                  : "dot offline"
              }
            />

            Stockfish: {stockfishStatus}
          </div>

        </div>

      </header>


      <main className="main">

        {/* INPUT PANEL */}

        <section className="panel input-panel">

          <h2>Position</h2>


          <label>FEN</label>

          <textarea
            value={fen}
            onChange={(e) =>
              setFen(e.target.value)
            }
            rows={4}
            placeholder="Enter FEN position..."
          />


          {/* STOCKFISH SETTINGS */}

          <div className="controls">

            <div>
              <label>
                Stockfish Depth
              </label>

              <input
                type="number"
                min="1"
                max="30"
                value={depth}
                onChange={(e) =>
                  setDepth(e.target.value)
                }
              />
            </div>


            <div>
              <label>
                Top Moves
              </label>

              <input
                type="number"
                min="1"
                max="10"
                value={multipv}
                onChange={(e) =>
                  setMultipv(e.target.value)
                }
              />
            </div>

          </div>


          {/* MAIA SETTINGS */}

          <div className="maia-controls">

            <h3>
              Maia-3 Human Model
            </h3>


            <div className="controls">

              <div>
                <label>
                  Player Elo
                </label>

                <input
                  type="number"
                  min="0"
                  max="5000"
                  step="50"
                  value={maiaSelfElo}
                  onChange={(e) =>
                    setMaiaSelfElo(
                      e.target.value
                    )
                  }
                />
              </div>


              <div>
                <label>
                  Opponent Elo
                </label>

                <input
                  type="number"
                  min="0"
                  max="5000"
                  step="50"
                  value={maiaOppoElo}
                  onChange={(e) =>
                    setMaiaOppoElo(
                      e.target.value
                    )
                  }
                />
              </div>

            </div>

          </div>


          <button
            className="analyze-button"
            onClick={handleAnalyze}
            disabled={loading}
          >
            {loading
              ? "Analyzing..."
              : "Analyze Position"}
          </button>


          {error && (
            <div className="error">
              {error}
            </div>
          )}

        </section>


        {/* RESULTS PANEL */}

        <section className="panel results-panel">

          <h2>Analysis</h2>


          {!result && !loading && (
            <div className="empty">
              Enter a FEN and click{" "}
              <strong>
                Analyze Position
              </strong>.
            </div>
          )}


          {loading && (
            <div className="empty">
              Stockfish and Maia-3 are
              analyzing...
            </div>
          )}


          {result && !loading && (
            <>

              {/* STOCKFISH */}

              <div className="section">

                <h3>
                  Stockfish
                </h3>


                <div className="summary">

                  <div className="metric">
                    <span>
                      Best Move
                    </span>

                    <strong>
                      {result.best_move}
                    </strong>
                  </div>


                  <div className="metric">
                    <span>
                      Evaluation
                    </span>

                    <strong>
                      {result.evaluation >= 0
                        ? "+"
                        : ""}
                      {Number(
                        result.evaluation
                      ).toFixed(2)}
                    </strong>
                  </div>


                  <div className="metric">
                    <span>
                      Depth
                    </span>

                    <strong>
                      {result.depth}
                    </strong>
                  </div>

                </div>


                <div className="section">

                  <h3>
                    Top Moves & Variations
                  </h3>


                  <div className="variations">

                    {result.top_moves?.map(
                      (move, index) => (
                        <div
                          className="variation-card"
                          key={index}
                        >

                          <div className="variation-header">

                            <span className="rank">
                              #{index + 1}
                            </span>


                            <strong className="move">
                              {move.move}
                            </strong>


                            <span className="evaluation">
                              {move.evaluation >= 0
                                ? "+"
                                : ""}
                              {Number(
                                move.evaluation
                              ).toFixed(2)}
                            </span>

                          </div>


                          <div className="pv">
                            {move.pv ||
                              "No variation available"}
                          </div>

                        </div>
                      )
                    )}

                  </div>

                </div>

              </div>


              {/* MAIA */}

              {maiaResult && (
                <div className="section">

                  <h3>
                    Maia-3 Human Moves
                  </h3>


                  <div className="maia-meta">

                    <span>
                      Player Elo:{" "}
                      <strong>
                        {maiaResult.self_elo}
                      </strong>
                    </span>


                    <span>
                      Opponent Elo:{" "}
                      <strong>
                        {maiaResult.oppo_elo}
                      </strong>
                    </span>

                  </div>


                  <p className="section-description">
                    Maia ranks the moves by
                    predicted human likelihood.
                    Stockfish evaluates those
                    exact Maia-selected moves.
                  </p>


                  <div className="variations">

                    {maiaResult.top_moves?.map(
                      (move) => (
                        <div
                          className="variation-card"
                          key={move.rank}
                        >

                          <div className="variation-header">

                            <span className="rank">
                              #{move.rank}
                            </span>


                            <strong className="move">
                              {move.move}
                            </strong>


                            <span className="evaluation">
                              {move.stockfish_evaluation !==
                                null &&
                              move.stockfish_evaluation !==
                                undefined
                                ? `${
                                    move.stockfish_evaluation >=
                                    0
                                      ? "+"
                                      : ""
                                  }${Number(
                                    move.stockfish_evaluation
                                  ).toFixed(2)}`
                                : "N/A"}
                            </span>

                          </div>


                          <div className="pv">

                            {move.stockfish_variation
                              ?.length
                              ? move.stockfish_variation.join(
                                  " "
                                )
                              : "No variation available"}

                          </div>

                        </div>
                      )
                    )}

                  </div>

                </div>
              )}

            </>
          )}

        </section>

      </main>

    </div>
  );
}

export default App;