const API_BASE_URL = "http://127.0.0.1:8000";

export async function analyzeGame({
  pgn,
  player_elo,
  opponent_elo,
}) {
  const response = await fetch(
    `${API_BASE_URL}/games/analyze`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        pgn,
        player_elo: Number(player_elo),
        opponent_elo: Number(opponent_elo),
      }),
    }
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(
      data.detail || "Game analysis failed."
    );
  }

  return data;
}