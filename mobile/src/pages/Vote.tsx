import { useEffect, useState } from "react";
import type { RoomState, YouState } from "../types";

function useCountdown(deadlineMs: number | null): number {
  const [left, setLeft] = useState(() =>
    deadlineMs ? Math.max(0, Math.round((deadlineMs - Date.now()) / 1000)) : 0
  );
  useEffect(() => {
    if (!deadlineMs) return;
    const timer = setInterval(() => {
      setLeft(Math.max(0, Math.round((deadlineMs - Date.now()) / 1000)));
    }, 500);
    return () => clearInterval(timer);
  }, [deadlineMs]);
  return left;
}

export function Vote({
  room,
  you,
  onVote,
}: {
  room: RoomState;
  you: YouState;
  onVote: (candidateId: string) => void;
}) {
  const secondsLeft = useCountdown(room.voteDeadlineMs);
  const voted = you.voted ?? false;
  const { cast, total } = room.voteProgress;

  return (
    <div>
      <h1>Vote now 🗳️</h1>
      <p className="sub">
        {voted
          ? `Vote locked in. ${cast}/${total} in.`
          : `${secondsLeft}s left · ${cast}/${total} voted`}{" "}
        - the tally stays sealed until everyone is done.
      </p>
      {room.candidates.map((c) => (
        <div key={c.movie.id} className="card candidate">
          <div className="title-row">
            <h3>{c.movie.title}</h3>
            <span className="meta">{c.movie.year}</span>
          </div>
          <div className="meta">
            {c.movie.runtime_min} min · {c.movie.content_rating} · {c.movie.genres.join(", ")}
          </div>
          <div className="logline">{c.movie.logline}</div>
          {c.reasons.slice(0, 3).map((r, i) => (
            <div className="reason" key={i}>
              <span>·</span>
              <span>
                {r.for_member ? <b>{r.for_member}: </b> : null}
                {r.text}
              </span>
            </div>
          ))}
          {!voted && (
            <button className="btn" onClick={() => onVote(c.movie.id)}>
              This one
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
