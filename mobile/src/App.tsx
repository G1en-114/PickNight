import { useCallback, useEffect, useMemo, useState } from "react";
import { newRequestId, PickNightClient } from "./api";
import type { ConcessionRequest, RoomState, ServerMessage, YouState } from "./types";
import { Join } from "./pages/Join";
import { Lobby } from "./pages/Lobby";
import { Preferences } from "./pages/Preferences";
import { Negotiation } from "./pages/Negotiation";
import { Vote } from "./pages/Vote";
import { Result } from "./pages/Result";

// During dev the phone and the TV talk to the same local backend.
const SERVER_BASE = import.meta.env.VITE_SERVER_BASE ?? "http://localhost:8000";

export default function App() {
  const params = new URLSearchParams(window.location.search);
  const initialRoom = (params.get("room") ?? "").toUpperCase();

  const [roomCode, setRoomCode] = useState(initialRoom);
  const [joined, setJoined] = useState(false);
  const [status, setStatus] = useState<"connecting" | "open" | "closed">("connecting");
  const [room, setRoom] = useState<RoomState | null>(null);
  const [you, setYou] = useState<YouState>({});
  const [concession, setConcession] = useState<ConcessionRequest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [client, setClient] = useState<PickNightClient | null>(null);

  const onMessage = useCallback((msg: ServerMessage) => {
    switch (msg.type) {
      case "joined":
        setJoined(true);
        setRoom(msg.room);
        break;
      case "snapshot":
        setRoom(msg.room);
        setYou(msg.you);
        setConcession(msg.you.pendingConcession ?? null);
        break;
      case "concession_request":
        setConcession({
          id: msg.concessionId,
          member_id: "",
          ask_text: msg.askText,
          relax_summary: msg.relaxSummary,
          deadline_ms: msg.deadlineMs ?? null,
        });
        break;
      case "concession_resolved":
        setConcession(null);
        break;
      case "candidates_ready":
        setRoom((prev) => (prev ? { ...prev, candidates: msg.candidates } : prev));
        break;
      case "result":
        setRoom((prev) => (prev ? { ...prev, result: msg.result } : prev));
        break;
      case "error":
        setError(`${msg.code}: ${msg.message}`);
        setTimeout(() => setError(null), 4000);
        break;
      default:
        break;
    }
  }, []);

  const handleJoin = useCallback(
    (name: string) => {
      const c = new PickNightClient(roomCode, SERVER_BASE, {
        onMessage,
        onStatus: setStatus,
      });
      setClient(c);
      c.connect(name);
    },
    [roomCode, onMessage]
  );

  useEffect(() => () => client?.close(), [client]);

  const submitPreferences = useCallback(
    (hard: Record<string, unknown>, soft: Record<string, unknown>, freeText: string) => {
      client?.send({
        type: "submit_preferences",
        requestId: newRequestId(),
        hard,
        soft,
        freeText,
      });
    },
    [client]
  );

  const respondConcession = useCallback(
    (concessionId: string, accepted: boolean) => {
      client?.send({
        type: "concession_response",
        requestId: newRequestId(),
        concessionId,
        accepted,
      });
    },
    [client]
  );

  const castVote = useCallback(
    (candidateId: string) => {
      client?.send({ type: "cast_vote", requestId: newRequestId(), candidateId });
    },
    [client]
  );

  const page = useMemo(() => {
    if (!joined) return <Join roomCode={roomCode} onRoomCode={setRoomCode} onJoin={handleJoin} />;
    if (!room) return <div className="center-note">Connecting…</div>;
    switch (room.phase) {
      case "lobby":
        return <Lobby room={room} you={you} />;
      case "preferences":
        return (
          <Preferences
            room={room}
            you={you}
            onSubmit={submitPreferences}
          />
        );
      case "matching":
        return (
          <div className="center-note">
            <div className="pulse">🍿</div>
            Matching everyone's taste…
          </div>
        );
      case "negotiation":
        return (
          <Negotiation room={room} concession={concession} onRespond={respondConcession} />
        );
      case "voting":
        return <Vote room={room} you={you} onVote={castVote} />;
      case "result":
        return <Result room={room} />;
      default:
        return <div className="center-note">Unknown phase</div>;
    }
  }, [joined, room, you, concession, handleJoin, submitPreferences, respondConcession, castVote, roomCode]);

  return (
    <div className="app">
      <header className="topbar">
        <span className="logo">PickNight 🌙</span>
        {joined && room && <span className="room-chip">{room.code}</span>}
        {joined && status === "closed" && <span className="status-warn">reconnecting…</span>}
      </header>
      {error && <div className="error-toast">{error}</div>}
      <main className="content">{page}</main>
    </div>
  );
}
