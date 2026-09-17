# Chess Annotation Agent

> **Personalized chess analysis that combines objective chess evaluation with human-move modeling to produce actionable coaching.**

Chess Annotation Agent analyzes complete chess games from PGN and identifies meaningful moments using two complementary perspectives:

* **Stockfish** — objective chess evaluation
* **Maia-3** — human-like move prediction conditioned on player rating
* **OpenAI** — natural-language coaching based on both signals

The system is designed to answer not only **“What was objectively better?”**, but also **“What would a human around this rating naturally consider?”**

---

## Overview

Traditional engine analysis is excellent at finding strong moves, but raw engine output is often difficult to translate into useful lessons for a human player.

This project separates the problem into three layers:

```text
Objective Chess Analysis
        +
Human-Move Modeling
        ↓
Natural-Language Coaching
```

The final interface presents coaching explanations rather than raw engine output.

---

## System Architecture

```text
                                ┌──────────────────────┐
                                │         PGN          │
                                │                      │
                                │ Chess.com / Lichess │
                                │ / standard PGN       │
                                └──────────┬───────────┘
                                           │
                                           ▼
                                ┌──────────────────────┐
                                │      PGN Parser       │
                                │                      │
                                │ Headers              │
                                │ Moves                │
                                │ SAN / UCI            │
                                │ FEN before/after     │
                                │ Ply information      │
                                └──────────┬───────────┘
                                           │
                         ┌─────────────────┴─────────────────┐
                         │                                   │
                         ▼                                   ▼
                ┌──────────────────┐                ┌──────────────────┐
                │    Stockfish     │                │     Maia-3       │
                │                  │                │                  │
                │ Objective chess  │                │ Human-like move  │
                │ evaluation       │                │ prediction       │
                │                  │                │                  │
                │ Best move        │                │ Elo conditioned  │
                │ Evaluation loss  │                │ Human candidates │
                │ Move comparison  │                │                  │
                └────────┬─────────┘                └────────┬─────────┘
                         │                                   │
                         └─────────────────┬─────────────────┘
                                           │
                                           ▼
                                ┌──────────────────────┐
                                │  Anomaly Detection   │
                                │                      │
                                │ Stockfish anomaly    │
                                │          OR          │
                                │ Maia anomaly         │
                                └──────────┬───────────┘
                                           │
                                  Final candidates
                                           │
                                           ▼
                                ┌──────────────────────┐
                                │       OpenAI         │
                                │                      │
                                │ Receives BOTH:       │
                                │ • Stockfish evidence │
                                │ • Maia evidence      │
                                │                      │
                                │ Produces coaching    │
                                └──────────┬───────────┘
                                           │
                                           ▼
                                ┌──────────────────────┐
                                │    Annotated PGN     │
                                │                      │
                                │ Comments inserted    │
                                │ after relevant moves │
                                └──────────┬───────────┘
                                           │
                              ┌────────────┴────────────┐
                              │                         │
                              ▼                         ▼
                    ┌──────────────────┐      ┌──────────────────┐
                    │    React UI      │      │   PGN Download   │
                    │                  │      │                  │
                    │ Game summary     │      │ annotated_game   │
                    │ Coach notes      │      │      .pgn        │
                    └──────────────────┘      └──────────────────┘
```

---

## Core Design

### Stockfish: objective perspective

Stockfish is responsible for determining the objective chess characteristics of a move.

It is used to identify:

* meaningful evaluation loss
* inaccuracies
* mistakes
* blunders
* unusually strong moves
* best-move candidates
* differences between the best and played move

Stockfish is the source of **objective chess evidence**.

---

### Maia-3: human perspective

Maia-3 is used to model human move choices rather than objective engine strength.

It is conditioned on player rating and provides human-like candidate moves.

This allows the system to reason about:

```text
"What would a player around this level naturally consider?"
```

This is deliberately different from asking what the engine considers best.

---

### OpenAI: coaching layer

OpenAI does not replace the chess analysis.

Instead, it receives the already computed evidence from **both Stockfish and Maia-3** and translates it into natural coaching language.

For each candidate move, the coaching layer receives information such as:

```text
Move context
├── Move
├── UCI
├── Ply
├── Move number
├── Player
├── FEN before
└── FEN after

Stockfish evidence
├── Best move
├── Evaluation
├── Evaluation loss
├── Gap to second move
└── Top candidate moves

Maia evidence
├── Human-move classification
├── Human-like candidate moves
└── Rating context
```

The final output should explain the chess idea without exposing internal model terminology.

---

# End-to-End Pipeline

## 1. PGN ingestion

The system starts with a complete PGN.

The parser extracts structured information for each move:

```text
PGN
 ↓
Move list
 ↓
FEN + UCI + SAN + player + ply
```

---

## 2. Stockfish screening

The full game is first processed using a lightweight Stockfish configuration.

Current configuration:

```python
STOCKFISH_SCREEN_DEPTH = 10
STOCKFISH_SCREEN_MULTIPV = 2
```

The purpose of this stage is to eliminate routine moves quickly and identify moves that deserve further analysis.

```text
All moves
    ↓
Cheap Stockfish screening
    ↓
Preliminary candidates
```

---

## 3. Deep Stockfish verification

Only preliminary candidates are analyzed more deeply.

Current configuration:

```python
STOCKFISH_DEEP_DEPTH = 16
STOCKFISH_DEEP_MULTIPV = 2
```

This reduces unnecessary computation while retaining deeper verification for potentially meaningful positions.

---

## 4. Maia-3 analysis

Maia-3 is run on the candidate positions.

Current configuration:

```python
MAIA_MULTIPV = 3
MAIA_TOP_K = 5
```

The candidate move is compared against Maia's human-like candidate set.

Conceptually:

```text
Played move
     ↓
Does it appear among likely human moves?
     ↓
Yes → human-like
No  → potentially human-unexpected
```

---

## 5. Combined anomaly detection

A move becomes a final candidate when either analysis source identifies something worth explaining.

```python
stockfish_anomaly = stockfish_label is not None
maia_anomaly = maia_label == "unexpected"

should_annotate = (
    stockfish_anomaly
    or maia_anomaly
)
```

However, the system **does not discard the other source**.

When a move becomes a candidate:

```text
Stockfish evidence ─┐
                    ├──→ OpenAI
Maia evidence ──────┘
```

This is important because the two systems answer different questions.

---

# Stockfish Classification

The current internal thresholds are:

```python
INACCURACY_THRESHOLD = 0.30
MISTAKE_THRESHOLD = 0.80
BLUNDER_THRESHOLD = 1.50

GREAT_MOVE_GAP = 0.75
BRILLIANT_MOVE_GAP = 1.50
```

These classifications are treated as **internal analysis signals** rather than frontend-facing labels.

---

# Maia Human-Move Modeling

The Maia analysis is used to provide human context.

For example, a move could be objectively problematic while another move is more representative of what a human at the player's level would naturally consider.

This gives the coaching layer two distinct sources of context:

```text
Stockfish
"What is objectively happening?"

Maia
"What is a human likely to consider?"
```

---

# Batch Coaching

OpenAI annotations are generated in a **single batch request** for all final candidates.

Instead of:

```text
37 candidates
 ↓
37 API requests
```

the system uses:

```text
37 candidates
 ↓
1 structured OpenAI request
 ↓
37 coaching annotations
```

The response follows a strict JSON schema and maps each comment to its corresponding ply.

Example:

```json
{
  "annotations": [
    {
      "ply": 10,
      "comment": "..."
    },
    {
      "ply": 17,
      "comment": "..."
    }
  ]
}
```

---

# Coaching Output

The coaching layer is instructed to avoid exposing internal analysis details.

The user should see something like:

> This move makes the position harder to coordinate because the knight loses an active developing square. A more natural choice here would be Nc6, keeping your pieces connected and preserving flexibility.

Rather than:

```text
Stockfish says this is a blunder.
Maia ranks Nc6 highly.
```

The analysis remains internal; the output is written as coaching.

---

# Annotated PGN

Once coaching comments have been generated, the system inserts them directly into the original PGN.

Example:

```text
1. e4 e6
2. Nf3 d5
3. e5 {This commits the center and gives Black a clear target...}
3... c5
```

The resulting PGN:

* preserves the original game
* retains the original headers
* inserts comments at the correct plies
* can be imported into a chess application

---

# Frontend

The frontend is built with:

* React
* Vite
* JavaScript
* CSS

The current interface supports:

* Player Elo input
* Opponent Elo input
* PGN input
* Game analysis
* Game summary
* Annotation cards
* Candidate statistics
* Annotated PGN download

The UI intentionally avoids exposing raw engine terminology.

---

# Download

After analysis, the API returns the generated annotated PGN:

```text
annotated_pgn
```

The frontend converts this into a `.pgn` file locally in the browser.

Downloading the file does **not** trigger another analysis.

The resulting filename is:

```text
annotated_game.pgn
```

---

# Project Structure

```text
annotation-agent/
│
├── src/
│   ├── pgn_parser.py
│   ├── stockfish.py
│   ├── maia.py
│   ├── annotation.py
│   ├── annotate.py
│   ├── pgn_annotator.py
│   └── api.py
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js
│   │   ├── index.css
│   │   └── main.jsx
│   ├── package.json
│   └── ...
│
├── data/
├── requirements.txt
├── README.md
└── ...
```

---

# Component Responsibilities

| File               | Responsibility                             |
| ------------------ | ------------------------------------------ |
| `pgn_parser.py`    | Parse PGN into structured move/FEN data    |
| `stockfish.py`     | Local Stockfish integration                |
| `maia.py`          | Local Maia-3 integration                   |
| `annotation.py`    | Build OpenAI inputs and generate coaching  |
| `annotate.py`      | Orchestrate the complete analysis pipeline |
| `pgn_annotator.py` | Insert comments into PGN                   |
| `api.py`           | FastAPI backend                            |
| `App.jsx`          | React user interface                       |
| `api.js`           | Frontend → backend API communication       |
| `index.css`        | Frontend styling                           |

---

# Tech Stack

## Backend

```text
Python
FastAPI
python-chess
Stockfish
Maia-3
OpenAI API
```

## Frontend

```text
React
Vite
JavaScript
CSS
```

---

# Local Setup

## Clone

```bash
git clone https://github.com/vedavrat-shortcastle/annotation-agent.git
cd annotation-agent
```

## Python dependencies

```bash
pip install -r requirements.txt
```

## Frontend dependencies

```bash
cd frontend
npm install
cd ..
```

## OpenAI API key

Set the API key:

```bash
export OPENAI_API_KEY="your_api_key_here"
```

---

# Local Development

## Start backend

From the project root:

```bash
python3 -m uvicorn src.api:app --reload
```

Backend:

```text
http://127.0.0.1:8000
```

Health endpoint:

```text
http://127.0.0.1:8000/health
```

---

## Start frontend

In another terminal:

```bash
cd frontend
npm run dev
```

Frontend:

```text
http://localhost:5173
```

---

# API

## Health

```http
GET /health
```

Example response:

```json
{
  "status": "ok"
}
```

---

## Stockfish Status

```http
GET /stockfish/status
```

Returns Stockfish availability and configured executable path.

---

## Stockfish Analysis

```http
POST /stockfish/analyze
```

Request:

```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
  "depth": 18,
  "multipv": 5
}
```

---

## Game Analysis

```http
POST /games/analyze
```

Request:

```json
{
  "pgn": "complete PGN",
  "player_elo": 1900,
  "opponent_elo": 2100
}
```

Response:

```json
{
  "game": {
    "white": "...",
    "black": "...",
    "result": "..."
  },
  "annotations": [],
  "anomaly_count": 0,
  "annotated_pgn": "...",
  "preliminary_candidate_count": 0,
  "verified_candidate_count": 0
}
```

---

# Performance Strategy

The main performance optimization is **selective analysis**.

Instead of deeply analyzing every move:

```text
Every move
    ↓
Deep analysis
```

the system uses:

```text
Every move
    ↓
Cheap screening
    ↓
Suspicious candidates only
    ↓
Deep verification
    ↓
Maia analysis
    ↓
OpenAI coaching
```

The pipeline also uses persistent local engine processes during each analysis phase and batches the OpenAI annotation request.

---

# Development Status

### Phase 1 — Analysis Optimization

* [x] PGN parsing
* [x] Fast Stockfish screening
* [x] Preliminary candidate generation
* [x] Deep Stockfish verification
* [x] Maia-3 candidate analysis
* [x] Persistent engine processes
* [x] Runtime instrumentation

### Phase 2 — AI Coaching

* [x] OpenAI integration
* [x] Batch annotation generation
* [x] Structured JSON response
* [x] Stockfish evidence passed to OpenAI
* [x] Maia evidence passed to OpenAI
* [x] Human-like Maia candidate moves passed to OpenAI
* [x] Annotation validation

### Phase 3 — Annotated PGN

* [x] Generate annotated PGN
* [x] Preserve original move order
* [x] Insert comments by ply
* [x] Return annotated PGN through API

### Phase 4 — User Download

* [x] Frontend receives annotated PGN
* [x] Browser-side `.pgn` generation
* [x] Download `annotated_game.pgn`

---

# Design Principles

### Separation of responsibility

```text
Stockfish → objective chess analysis
Maia-3    → human-move modeling
OpenAI    → coaching explanation
```

### Evidence before language

OpenAI should explain evidence that has already been computed rather than inventing chess analysis independently.

### Human-oriented output

The goal is to turn analysis into lessons that are understandable to a player.

### Selective annotation

Not every move deserves a comment.

The system prioritizes moves that provide meaningful learning opportunities.

### No silent errors

When a stage cannot reliably produce the required information, the system should fail explicitly or preserve enough information for diagnosis rather than silently producing misleading output.

---

# Future Work

Planned extensions include:

* Interactive chessboard
* Move-to-comment navigation
* Position visualization
* Player mistake pattern analysis
* Multi-game coaching history
* Personalized recurring weaknesses
* Opening / middlegame / endgame segmentation
* Streaming analysis progress
* More sophisticated human-vs-objective move comparisons
* Deployment for remote analysis

---

# Project Goal

Chess Annotation Agent is built around a simple principle:

```text
Good chess coaching needs more than
"the engine says this was the best move."

It should also explain:
"what happened, why it mattered,
and what a human player could naturally consider."
```

The system combines objective analysis, human-move modeling, and language generation into one pipeline:

```text
PGN
 ↓
Stockfish + Maia-3
 ↓
Anomaly Detection
 ↓
OpenAI Coaching
 ↓
Annotated PGN
 ↓
Interactive Review
```

The result is a focused chess analysis workflow designed to turn individual games into useful, understandable learning moments.

