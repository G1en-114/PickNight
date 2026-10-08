import type { ConcessionRequest, RoomState } from "../types";

export function Negotiation({
  room,
  concession,
  onRespond,
}: {
  room: RoomState;
  concession: ConcessionRequest | null;
  onRespond: (concessionId: string, accepted: boolean) => void;
}) {
  if (concession) {
    return (
      <div>
        <h1>A tiny ask 🤝</h1>
        <p className="sub">The group is stuck - and only you can unlock it.</p>
        <div className="card concession-card">
          <p>{concession.ask_text}</p>
          <span className="relax">{concession.relax_summary}</span>
          <div className="row">
            <button
              className="btn"
              onClick={() => onRespond(concession.id, true)}
            >
              Fine, I'll bend
            </button>
            <button
              className="btn secondary"
              onClick={() => onRespond(concession.id, false)}
            >
              Nope
            </button>
          </div>
          <p className="explanation" style={{ marginTop: 10 }}>
            Declining is totally OK - your bottom lines stay yours.
          </p>
        </div>
      </div>
    );
  }

  const target = room.negotiation?.targetName;
  return (
    <div className="center-note">
      <div className="pulse">🤝</div>
      {target
        ? `PickNight is negotiating with ${target}…`
        : "PickNight is working out a deal…"}
      <p className="explanation">
        No movie fits everyone's bottom lines right now. We only ask the person
        who can fix it - never force anyone.
      </p>
    </div>
  );
}
