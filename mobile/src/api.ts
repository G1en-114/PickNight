// Minimal WebSocket client with rejoin + reconnect backoff.
// The server is authoritative; we only render snapshots.

import type { ClientSend, ServerMessage } from "./types";

export interface ClientHandlers {
  onMessage: (msg: ServerMessage) => void;
  onStatus: (status: "connecting" | "open" | "closed") => void;
}

const MEMBER_TOKEN_KEY = "picknight.memberToken";

export class PickNightClient {
  private ws: WebSocket | null = null;
  private url: string;
  private handlers: ClientHandlers;
  private memberToken: string | null = null;
  private memberName = "";
  private retry = 0;
  private closedByUs = false;

  constructor(roomCode: string, serverBase: string, handlers: ClientHandlers) {
    const wsBase = serverBase.replace(/^http/, "ws");
    this.url = `${wsBase}/ws/${roomCode}`;
    this.handlers = handlers;
    this.memberToken = sessionStorage.getItem(MEMBER_TOKEN_KEY);
  }

  connect(name: string) {
    this.memberName = name;
    this.closedByUs = false;
    this.open();
  }

  private open() {
    this.handlers.onStatus("connecting");
    const ws = new WebSocket(this.url);
    this.ws = ws;

    ws.onopen = () => {
      this.retry = 0;
      this.handlers.onStatus("open");
      this.send({
        type: "join",
        role: "member",
        name: this.memberName,
        token: this.memberToken ?? undefined,
      });
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as ServerMessage;
        if (msg.type === "joined" && msg.memberToken) {
          this.memberToken = msg.memberToken;
          sessionStorage.setItem(MEMBER_TOKEN_KEY, msg.memberToken);
        }
        this.handlers.onMessage(msg);
      } catch {
        // ignore malformed frames
      }
    };

    ws.onclose = () => {
      this.handlers.onStatus("closed");
      if (this.closedByUs) return;
      const delay = Math.min(8000, 500 * 2 ** this.retry++);
      setTimeout(() => this.open(), delay);
    };
  }

  send(msg: ClientSend) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  close() {
    this.closedByUs = true;
    this.ws?.close();
  }
}

export function newRequestId(): string {
  return `r${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
}
