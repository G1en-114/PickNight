/**
 * PickNight TV app skeleton (React Native for Vega).
 *
 * State-driven single surface: the TV renders the room's public state and
 * hosts the flow (start / restart). All logic lives on the server; the TV
 * is a big, readable stage. Private member input never appears here.
 *
 * TODO(vega-machine): verify on a real Vega environment -
 *  - replace placeholder styles with kepler-ui-components theming
 *  - D-pad focus + press on HostButton (see TODOs)
 *  - QR code rendering for the join URL
 */

import React, { useCallback, useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

// The backend base URL lives in env on the Vega machine (see .env.example).
const SERVER_BASE = process.env.PICKNIGHT_SERVER ?? "http://localhost:8000";
const MOBILE_JOIN_BASE = process.env.PICKNIGHT_MOBILE_BASE ?? "http://localhost:5173";

type Phase = "lobby" | "preferences" | "matching" | "negotiation" | "voting" | "result";

interface MemberView { id: string; name: string; submitted: boolean }
interface Reason { for_member: string | null; text: string }
interface Candidate {
  movie: { id: string; title: string; year: number; runtime_min: number; content_rating: string; genres: string[]; logline: string };
  score: number;
  reasons: Reason[];
}
interface RoomState {
  code: string;
  phase: Phase;
  members: MemberView[];
  candidates: Candidate[];
  voteProgress: { cast: number; total: number };
  voteDeadlineMs: number | null;
  negotiation: { targetName: string } | null;
  result: { no_pick: boolean; winner: Candidate | null; explanation: string;
            tally: { candidate_id: string; title: string; votes: number }[] } | null;
}

export default function App() {
  const [room, setRoom] = useState<RoomState | null>(null);
  const [hostToken, setHostToken] = useState<string | null>(null);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);

  const hostAction = useCallback((type: string) => {
    ws?.send(JSON.stringify({ type }));
  }, [ws]);

  // Create a room on launch, then keep a websocket open as the TV.
  useEffect(() => {
    let cancelled = false;
    let socket: WebSocket | null = null;

    (async () => {
      try {
        const resp = await fetch(`${SERVER_BASE}/api/rooms`, { method: "POST" });
        const body = await resp.json();
        if (cancelled) return;
        setHostToken(body.host_token);
        socket = new WebSocket(`${SERVER_BASE.replace(/^http/, "ws")}/ws/${body.room_code}`);
        socket.onopen = () => {
          setConnected(true);
          socket!.send(JSON.stringify({ type: "join", role: "tv", token: body.host_token }));
        };
        socket.onclose = () => setConnected(false);
        socket.onmessage = (event) => {
          const msg = JSON.parse(event.data);
          if (msg.type === "joined" || msg.type === "snapshot") setRoom(msg.room);
          else if (msg.type === "candidates_ready")
            setRoom((prev) => (prev ? { ...prev, candidates: msg.candidates } : prev));
          else if (msg.type === "result")
            setRoom((prev) => (prev ? { ...prev, result: msg.result } : prev));
        };
        setWs(socket);
      } catch (e) {
        console.warn("backend unreachable", e);
      }
    })();

    return () => {
      cancelled = true;
      socket?.close();
    };
  }, []);

  const joinUrl = room ? `${MOBILE_JOIN_BASE}/?room=${room.code}` : "";

  return (
    <View style={styles.screen}>
      <View style={styles.topbar}>
        <Text style={styles.logo}>PickNight 🌙</Text>
        <View style={styles.row}>
          {!connected && <Text style={styles.warn}>connecting… </Text>}
          {room && <Text style={styles.roomCode}>{room.code}</Text>}
        </View>
      </View>

      {!room ? (
        <Center text="Talking to the PickNight server…" />
      ) : (
        <ScrollView style={styles.body}>
          {room.phase === "lobby" && (
            <Lobby room={room} joinUrl={joinUrl} onStart={() => hostAction("start_preferences")} />
          )}
          {room.phase === "preferences" && <Preferences room={room} />}
          {room.phase === "matching" && <Center text="Matching everyone's taste… 🍿" />}
          {room.phase === "negotiation" && (
            <Center
              text={
                room.negotiation
                  ? `Negotiating with ${room.negotiation.targetName}… 🤝`
                  : "Working out a deal… 🤝"
              }
            />
          )}
          {room.phase === "voting" && <Voting room={room} />}
          {room.phase === "result" && (
            <ResultView room={room} onRestart={() => hostAction("restart")} />
          )}
        </ScrollView>
      )}
    </View>
  );
}

function HostButton({ label, onPress, disabled }: { label: string; onPress: () => void; disabled?: boolean }) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      // TODO(vega-machine): add D-pad focus styles (focus rings must be
      // obvious at 10 feet) - kepler-ui-components has TVFocus helpers.
      style={({ focused }) => [
        styles.hostButton,
        (focused || !disabled) && styles.hostButtonFocus,
        disabled && styles.hostButtonDisabled,
      ]}
    >
      <Text style={styles.hostButtonText}>{label}</Text>
    </Pressable>
  );
}

function Lobby({ room, joinUrl, onStart }: { room: RoomState; joinUrl: string; onStart: () => void }) {
  const enough = room.members.length >= 2;
  return (
    <View>
      <Text style={styles.h1}>Everyone, grab your phone</Text>
      <View style={styles.qrPlaceholder}>
        {/* TODO(vega-machine): render a real QR code for joinUrl */}
        <Text style={styles.joinUrl}>{joinUrl}</Text>
        <Text style={styles.roomCodeBig}>{room.code}</Text>
      </View>
      <Text style={styles.h2}>
        In the room ({room.members.length} {enough ? "" : "- need 2 to start"})
      </Text>
      {room.members.map((m) => (
        <Text key={m.id} style={styles.memberRow}>
          👤 {m.name}
        </Text>
      ))}
      <View style={{ height: 24 }} />
      <HostButton label={enough ? "Start the night ▶" : "Waiting for 2+ members…"} onPress={onStart} disabled={!enough} />
    </View>
  );
}

function Preferences({ room }: { room: RoomState }) {
  const done = room.members.filter((m) => m.submitted).length;
  return (
    <View>
      <Text style={styles.h1}>Secret ballot of taste</Text>
      <Text style={styles.h2}>
        {done}/{room.members.length} have told us their bottom lines
      </Text>
      {room.members.map((m) => (
        <Text key={m.id} style={styles.memberRow}>
          {m.submitted ? "✅" : "⏳"} {m.name}
        </Text>
      ))}
    </View>
  );
}

function Voting({ room }: { room: RoomState }) {
  const secondsLeft = room.voteDeadlineMs
    ? Math.max(0, Math.round((room.voteDeadlineMs - Date.now()) / 1000))
    : null;
  return (
    <View>
      <Text style={styles.h1}>
        Vote on your phones · {room.voteProgress.cast}/{room.voteProgress.total}
        {secondsLeft !== null ? ` · ${secondsLeft}s` : ""}
      </Text>
      {room.candidates.map((c, i) => (
        <View key={c.movie.id} style={styles.candidate}>
          <Text style={styles.candidateTitle}>
            {i + 1}. {c.movie.title} ({c.movie.year})
          </Text>
          <Text style={styles.candidateMeta}>
            {c.movie.runtime_min} min · {c.movie.content_rating} · {c.movie.genres.join(", ")}
          </Text>
        </View>
      ))}
    </View>
  );
}

function ResultView({ room, onRestart }: { room: RoomState; onRestart: () => void }) {
  const result = room.result;
  if (!result) return <Center text="Counting…" />;
  if (result.no_pick) {
    return (
      <View>
        <Text style={styles.h1}>No pick tonight 🤷</Text>
        <Text style={styles.body}>{result.explanation}</Text>
        <View style={{ height: 24 }} />
        <HostButton label="Try again ↺" onPress={onRestart} />
      </View>
    );
  }
  const winner = result.winner!;
  return (
    <View>
      <Text style={styles.h1}>Tonight we watch</Text>
      <Text style={styles.winnerTitle}>{winner.movie.title} 🎉</Text>
      <Text style={styles.candidateMeta}>
        {winner.movie.runtime_min} min · {winner.movie.content_rating} · {winner.movie.genres.join(", ")}
      </Text>
      <Text style={styles.body}>{result.explanation}</Text>
      <View style={{ height: 24 }} />
      <HostButton label="Another round ↺" onPress={onRestart} />
    </View>
  );
}

function Center({ text }: { text: string }) {
  return (
    <View style={styles.center}>
      <Text style={styles.centerText}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#12101c", padding: 48 },
  topbar: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 32 },
  logo: { color: "#f2effa", fontSize: 28, fontWeight: "700" },
  row: { flexDirection: "row", alignItems: "center" },
  warn: { color: "#9c93b5", fontSize: 18 },
  roomCode: { color: "#ff9f43", fontSize: 24, fontWeight: "700", fontFamily: "monospace" },
  body: { flex: 1 },
  h1: { color: "#f2effa", fontSize: 40, fontWeight: "700", marginBottom: 16 },
  h2: { color: "#9c93b5", fontSize: 24, marginBottom: 12 },
  qrPlaceholder: {
    backgroundColor: "#1d1a2e", borderRadius: 16, padding: 32,
    alignItems: "center", marginBottom: 24, borderWidth: 2, borderColor: "#ff9f43",
  },
  joinUrl: { color: "#9c93b5", fontSize: 20, marginBottom: 8 },
  roomCodeBig: { color: "#ff9f43", fontSize: 64, fontWeight: "700", fontFamily: "monospace" },
  memberRow: { color: "#f2effa", fontSize: 24, marginVertical: 4 },
  hostButton: {
    backgroundColor: "#ff9f43", borderRadius: 12, padding: 20,
    alignItems: "center", marginTop: 16,
  },
  hostButtonFocus: { borderWidth: 4, borderColor: "#f2effa" },
  hostButtonDisabled: { backgroundColor: "#262138" },
  hostButtonText: { color: "#241a05", fontSize: 26, fontWeight: "700" },
  candidate: { backgroundColor: "#1d1a2e", borderRadius: 12, padding: 20, marginVertical: 8 },
  candidateTitle: { color: "#f2effa", fontSize: 28, fontWeight: "600" },
  candidateMeta: { color: "#9c93b5", fontSize: 20, marginTop: 4 },
  winnerTitle: { color: "#ff9f43", fontSize: 56, fontWeight: "700", marginBottom: 8 },
  body: { color: "#c9c0dd", fontSize: 22, lineHeight: 32 },
  center: { flex: 1, justifyContent: "center", alignItems: "center", padding: 64 },
  centerText: { color: "#9c93b5", fontSize: 28, textAlign: "center" },
});
