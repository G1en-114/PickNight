import type { RoomState } from "../types";

export function Result({ room }: { room: RoomState }) {
  const result = room.result;
  if (!result) return <div className="center-note">Counting…</div>;

  if (result.no_pick) {
    return (
      <div>
        <div className="big-emoji">🤷</div>
        <h1>No pick tonight</h1>
        <div className="card">
          <p className="explanation">{result.explanation}</p>
        </div>
        <div className="center-note">The TV can start a fresh round.</div>
      </div>
    );
  }

  const winner = result.winner!;
  const totalVotes = Math.max(
    1,
    result.tally.reduce((sum, e) => sum + e.votes, 0)
  );

  return (
    <div>
      <div className="big-emoji">🎉🍿</div>
      <h1>Tonight we watch</h1>
      <div className="card candidate winner-card">
        <div className="title-row">
          <h3>{winner.movie.title}</h3>
          <span className="meta">{winner.movie.year}</span>
        </div>
        <div className="meta">
          {winner.movie.runtime_min} min · {winner.movie.content_rating} ·{" "}
          {winner.movie.genres.join(", ")}
        </div>
        <div className="logline">{winner.movie.logline}</div>
        <div className="meta">Watch on: {winner.movie.providers.join(", ")}</div>
      </div>

      <div className="card">
        <h2>Why this won</h2>
        <p className="explanation">{result.explanation}</p>
      </div>

      <div className="card">
        <h2>Tally</h2>
        {result.tally.map((e) => (
          <div className="tally-row" key={e.candidate_id}>
            <span style={{ minWidth: 90 }}>{e.title}</span>
            <div className="tally-bar">
              <div
                className="tally-fill"
                style={{ width: `${(e.votes / totalVotes) * 100}%` }}
              />
            </div>
            <span>{e.votes}</span>
          </div>
        ))}
      </div>

      <div className="center-note">Enjoy 🌙</div>
    </div>
  );
}
