import type { RoomState, YouState } from "../types";

export function Lobby({ room, you }: { room: RoomState; you: YouState }) {
  const me = room.members.find((m) => m.id === you.memberId);
  return (
    <div>
      <h1>You're in, {me?.name ?? "friend"} 👋</h1>
      <p className="sub">Waiting for everyone to gather on the couch.</p>
      <div className="card">
        <h2>In the room ({room.members.length})</h2>
        <div className="member-list">
          {room.members.map((m) => (
            <div key={m.id} className="member-row">
              <span>{m.name}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="center-note">
        The night starts on the TV{me ? " — hang tight" : ""}.
      </div>
    </div>
  );
}
