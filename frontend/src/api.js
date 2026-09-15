const API_BASE = "http://127.0.0.1:8000";

async function request(url, options = {}) {
  const response = await fetch(`${API_BASE}${url}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || "API request failed");
  }

  return data;
}

export async function getHealth() {
  return request("/health");
}

export async function getStockfishStatus() {
  return request("/stockfish/status");
}

export async function analyzeStockfish({ fen, depth, multipv }) {
  return request("/stockfish/analyze", {
    method: "POST",
    body: JSON.stringify({
      fen,
      depth,
      multipv,
    }),
  });
}
export async function analyzeMaia({
  fen,
  elo,
  self_elo,
  oppo_elo,
  multipv,
}) {
  return request("/maia/analyze", {
    method: "POST",
    body: JSON.stringify({
      fen,
      elo,
      self_elo,
      oppo_elo,
      multipv,
    }),
  });
}