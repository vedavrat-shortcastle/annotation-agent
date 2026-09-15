# Chess Annotation Agent

A personalized chess game annotation system that combines **Stockfish**, **Maia-3**, and an LLM-based coaching layer to identify unusual moves and explain them in human-friendly language.

## Overview

The system analyzes a complete chess game from PGN and identifies moves that are worth explaining.

It combines two different perspectives:

* **Stockfish** evaluates the objective chess quality of a move.
* **Maia-3** estimates how natural or unexpected a move is for a human player at a given Elo.
* **Gemini** converts the structured chess evidence into a short coaching explanation.

The goal is not to annotate every move. The system focuses only on **meaningful anomalies** so that the final output is concise and personalized.

## Architecture

```text
                         PGN
                          │
                          ▼
                    PGN Parser
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
         Stockfish                  Maia-3
     Objective evaluation      Human move prediction
              │                       │
              └───────────┬───────────┘
                          ▼
                  Anomaly Detection
                          │
                          ▼
                 Verified Candidates
                          │
                          ▼
                  Coaching Layer
                        Gemini
                          │
                          ▼
                 Human-readable
                    annotations
                          │
                          ▼
                    React UI
```

## What each component does

### Stockfish

Stockfish is responsible for objective chess analysis.

It is used to detect:

* Inaccuracies
* Mistakes
* Blunders
* Great moves
* Brilliant moves

The system first screens positions at a lower depth and then deep-verifies potential anomalies.

### Maia-3

Maia-3 is a human chess move-prediction model.

It is used to determine whether the played move is:

* Natural for the player's Elo
* Among the most likely human moves
* Unexpected for the player's Elo

Maia is **not** used as the final chess evaluator. Its purpose is to provide a human-likelihood perspective.

### Gemini

Gemini acts as the coaching/explanation layer.

It receives structured evidence from Stockfish and Maia and converts it into a short explanation.

The user-facing annotation does not expose raw engine terminology, model names, ranks, or evaluation values.

Example:

> This move gives up an important defensive resource and allows your opponent to take control of the position. A better approach was to preserve the piece and address the immediate threat first.

## Anomaly Detection

The current thresholds are:

```text
Inaccuracy: 0.30+
Mistake:    0.80+
Blunder:    1.50+

Great move:     0.75+ gap to second-best move
Brilliant move: 1.50+ gap to second-best move
```

A move becomes an annotation candidate when either:

1. Stockfish identifies an anomaly, or
2. Maia considers the move unexpected for the player's Elo.

The final candidate is therefore based on both **objective chess quality** and **human-likelihood**.

## Personalized Elo

The Maia analysis is conditioned on player strength.

The system accepts:

```text
player_elo
opponent_elo
```

This allows the same move to be interpreted differently depending on the expected playing strength.

## Project Structure

```text
annotation-agent/
│
├── src/
│   ├── pgn_parser.py
│   ├── stockfish.py
│   ├── maia.py
│   ├── annotation.py
│   ├── annotate.py
│   └── api.py
│
├── frontend/
│   └── src/
│       ├── App.jsx
│       ├── api.js
│       ├── index.css
│       └── main.jsx
│
├── data/
├── requirements.txt
└── README.md
```

## Backend

The backend is built with **FastAPI**.

Start it with:

```bash
cd "/Users/pranavthobhani/annotation agent"
python3 -m uvicorn src.api:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Useful endpoints:

```text
GET  /health
GET  /stockfish/status
POST /stockfish/analyze
POST /games/analyze
```

### Analyze a game

`POST /games/analyze`

Example request:

```json
{
  "pgn": "YOUR_PGN_HERE",
  "player_elo": 1900,
  "opponent_elo": 2100
}
```

The response contains the game information, detected anomaly counts, and generated annotations.

## Frontend

The frontend is a React application using Vite.

Start it with:

```bash
cd "/Users/pranavthobhani/annotation agent/frontend"
npm install
npm run dev
```

Then open:

```text
http://localhost:5173
```

The interface allows the user to enter:

* Player Elo
* Opponent Elo
* PGN

and submit the game for analysis.

The frontend displays the resulting coaching annotations.

## Stockfish Setup

The current development environment expects Stockfish at:

```text
/opt/homebrew/bin/stockfish
```

This is the standard Homebrew installation path on Apple Silicon macOS.

To verify:

```bash
which stockfish
```

## Maia-3 Setup

The current development setup uses the local Maia-3 stack.

Expected location:

```text
~/chess/maia3-engine
```

The Maia environment is launched using:

```text
~/chess/maia3-engine/venv/bin/python
```

The project currently uses the:

```text
maia3-79m
```

model.

Maia is configured with the player's Elo and opponent's Elo to estimate human move likelihood.

## Gemini Configuration

Set your Gemini API key as an environment variable:

```bash
export GEMINI_API_KEY="YOUR_API_KEY"
```

Then start the backend.

Gemini is currently used through the Google GenAI Python SDK.

### Free-tier limitation

The coaching layer depends on Gemini API quota. When the quota or rate limit is reached, Gemini may generate zero annotations even though the Stockfish and Maia analysis succeeds.

The chess-analysis pipeline therefore remains independent from the LLM layer.

## Current Pipeline

The complete workflow is:

```text
1. Parse PGN
2. Reconstruct game positions
3. Screen moves with Stockfish
4. Identify preliminary anomalies
5. Deep-verify candidate moves
6. Analyze human-likelihood with Maia-3
7. Combine Stockfish + Maia evidence
8. Send verified anomalies to Gemini
9. Generate coaching annotations
10. Return results through FastAPI
11. Display annotations in React
```

## Example Output

For a game containing several unusual moves, the system may identify candidates such as:

```text
Nxc6   - Inaccuracy
Rxb2   - Great move
Bxc3   - Brilliant move
Bxd2   - Blunder
Rxc8+  - Brilliant move
```

Only the detected anomalies are sent to the coaching layer.

## Design Principles

### Objective + Human perspectives

Traditional chess engines answer:

> What is the best move?

This project also asks:

> What move would a human player at this Elo be expected to play?

Combining these perspectives allows the system to identify moves that are both objectively significant and interesting from a human-learning perspective.

### Explain, don't overload

The frontend is intended to show coaching explanations rather than engine output.

The goal is to help a player understand:

* What went wrong
* Why the move mattered
* What idea they should recognize next time

### Analyze selectively

The system does not generate commentary for every move.

Only moves that satisfy the anomaly criteria are passed to the coaching layer, reducing unnecessary analysis and keeping the final feedback focused.

## Current Status

The current prototype has:

```text
✅ PGN parsing
✅ Stockfish integration
✅ Maia-3 integration
✅ Elo-conditioned human move prediction
✅ Anomaly detection
✅ Candidate verification
✅ Batch Gemini annotation pipeline
✅ FastAPI backend
✅ React frontend
```

The main external limitation is Gemini API quota on the free tier.

## Future Direction

A planned next step is to replace the hosted LLM dependency with a **small chess-specific language model**.

Rather than training a foundation model from scratch, the intended approach is to fine-tune a small open-weight language model on chess annotation examples generated from:

```text
Stockfish + Maia-3
        ↓
structured chess evidence
        ↓
coaching annotations
        ↓
training dataset
        ↓
small local chess coach
```

This would make the coaching layer cheaper to run locally and allow the project to become more self-contained.

## License

This project is currently intended as a research/prototype project.
