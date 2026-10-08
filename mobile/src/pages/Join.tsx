import { useState } from "react";

export function Join({
  roomCode,
  onRoomCode,
  onJoin,
}: {
  roomCode: string;
  onRoomCode: (code: string) => void;
  onJoin: (name: string) => void;
}) {
  const [name, setName] = useState("");
  const validRoom = /^[A-Z0-9]{4}$/.test(roomCode);
  const canJoin = name.trim().length > 0 && validRoom;

  return (
    <div>
      <div className="big-emoji">🌙🍿</div>
      <h1>Join movie night</h1>
      <p className="sub">
        Scan the code on the TV, tell us who you are, and get ready to negotiate.
      </p>
      <div className="card">
        <label className="field-label">Your name</label>
        <input
          type="text"
          placeholder="e.g. Dad"
          value={name}
          maxLength={20}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && canJoin && onJoin(name.trim())}
        />
        <label className="field-label">Room code</label>
        <input
          type="text"
          placeholder="ABCD"
          value={roomCode}
          maxLength={4}
          onChange={(e) => onRoomCode(e.target.value.toUpperCase())}
        />
        <br />
        <br />
        <button className="btn" disabled={!canJoin} onClick={() => onJoin(name.trim())}>
          Let's go
        </button>
      </div>
    </div>
  );
}
