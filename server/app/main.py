"""PickNight API: room creation + WebSocket message loop.

Run:  uvicorn app.main:app --reload --port 8000   (from server/)
"""

from __future__ import annotations

import json
import secrets

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .llm import merge_preferences
from .models import HardConstraints, Phase, Preferences, SoftPreferences
from .rooms import MANAGER, Member, Room, _now_ms
from .rooms import ANALYZER

app = FastAPI(title="PickNight server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateRoomResponse(BaseModel):
    room_code: str
    host_token: str


@app.post("/api/rooms", response_model=CreateRoomResponse)
def create_room() -> CreateRoomResponse:
    code, host_token = MANAGER.create_room()
    return CreateRoomResponse(room_code=code, host_token=host_token)


@app.get("/api/rooms/{code}")
def room_info(code: str) -> dict:
    room = MANAGER.get(code)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return {
        "exists": True,
        "phase": room.phase.value,
        "memberCount": len(room.members),
    }


def _err(ws: WebSocket, code: str, message: str, for_request_id: str | None = None) -> dict:
    return {"type": "error", "code": code, "message": message, "forRequestId": for_request_id}


async def _handle(room: Room, ws: WebSocket, msg: dict) -> None:
    """Handle one client message. Member identity is derived from the socket
    (set at join time), so reconnects and duplicate frames stay consistent."""
    mtype = msg.get("type")
    request_id = msg.get("requestId")
    member = room.members.get(room.socket_member.get(ws, "")) if ws in room.socket_member else None

    if mtype == "ping":
        await ws.send_text(json.dumps({"type": "pong", "t": _now_ms()}))
        return

    if mtype == "join":
        role = msg.get("role", "member")
        if role == "tv":
            if msg.get("token") != room.host_token:
                await ws.send_text(json.dumps(_err(ws, "bad_host_token", "Invalid host token.")))
                return
            room.tv_sockets.add(ws)
            await ws.send_text(
                json.dumps(
                    {
                        "type": "joined",
                        "role": "tv",
                        "room": room.public_state(),
                    }
                )
            )
            await room.broadcast_snapshot()
            return

        name = (msg.get("name") or "").strip()[:20] or "Guest"
        # Rejoin with an existing member token restores identity.
        token = msg.get("token")
        existing = next((m for m in room.members.values() if m.token == token), None) if token else None
        if existing:
            member = existing
        else:
            if room.phase != Phase.LOBBY and room.phase != Phase.PREFERENCES:
                await ws.send_text(
                    json.dumps(_err(ws, "room_started", "The night already started."))
                )
                return
            member = Member(
                id=f"m{room._next_member}",
                name=name,
                token=secrets.token_hex(12),
            )
            room._next_member += 1
            room.members[member.id] = member
        room.member_sockets.setdefault(member.id, set()).add(ws)
        room.socket_member[ws] = member.id
        await ws.send_text(
            json.dumps(
                {
                    "type": "joined",
                    "role": "member",
                    "memberId": member.id,
                    "memberToken": member.token,
                    "room": room.public_state(),
                }
            )
        )
        await room.broadcast_snapshot()
        return

    if mtype in ("start_preferences", "restart"):
        if ws not in room.tv_sockets:
            await ws.send_text(json.dumps(_err(ws, "host_only", "Only the TV can do that.")))
            return
        if mtype == "start_preferences":
            error = await room.begin_preferences()
            if error:
                await ws.send_text(json.dumps(_err(ws, "cannot_start", error)))
        else:
            await room.restart()
        return

    # Everything below needs a member identity.
    if member is None:
        await ws.send_text(json.dumps(_err(ws, "not_joined", "Join the room first.")))
        return

    # Idempotency for state-changing member actions.
    if request_id:
        if request_id in room.seen_request_ids:
            return  # duplicate delivery; the effect already happened
        room.seen_request_ids.add(request_id)

    if mtype == "submit_preferences":
        if room.phase != Phase.PREFERENCES:
            await ws.send_text(
                json.dumps(_err(ws, "wrong_phase", "Not collecting preferences now.", request_id))
            )
            return
        structured = Preferences(
            hard=HardConstraints(**(msg.get("hard") or {})),
            soft=SoftPreferences(**(msg.get("soft") or {})),
            free_text=(msg.get("freeText") or "")[:500],
        )
        if structured.free_text:
            ft_hard, ft_soft = await ANALYZER.extract(structured.free_text)
            structured = merge_preferences(structured, ft_hard, ft_soft)
        member.preferences = structured
        await ws.send_text(json.dumps({"type": "preferences_ack", "forRequestId": request_id}))
        await room.broadcast(
            {"type": "preferences_progress", "submitted": member.id, "name": member.name}
        )
        await room.maybe_finish_collecting()
        await room.broadcast_snapshot()
        return

    if mtype == "concession_response":
        if room.phase != Phase.NEGOTIATION:
            await ws.send_text(json.dumps(_err(ws, "wrong_phase", "No negotiation in progress.", request_id)))
            return
        concession = room.pending_concession
        if not concession or concession.member_id != member.id:
            await ws.send_text(json.dumps(_err(ws, "not_yours", "This concession isn't addressed to you.", request_id)))
            return
        await room.resolve_concession(msg.get("concessionId"), accepted=bool(msg.get("accepted")))
        return

    if mtype == "cast_vote":
        if room.phase != Phase.VOTING:
            await ws.send_text(json.dumps(_err(ws, "wrong_phase", "Voting is closed.", request_id)))
            return
        if member.vote is not None:
            await ws.send_text(json.dumps(_err(ws, "already_voted", "One vote each.", request_id)))
            return
        candidate_ids = [c.movie.id for c in room.candidates]
        if msg.get("candidateId") not in candidate_ids:
            await ws.send_text(json.dumps(_err(ws, "bad_candidate", "Unknown candidate.", request_id)))
            return
        member.vote = msg.get("candidateId")
        await ws.send_text(json.dumps({"type": "vote_ack", "forRequestId": request_id}))
        await room.broadcast(
            {
                "type": "vote_progress",
                "cast": sum(1 for m in room.members.values() if m.vote is not None),
                "total": len(room.members),
                "deadlineMs": room.vote_deadline_ms,
            }
        )
        if all(m.vote is not None for m in room.members.values()):
            await room.close_voting()
        else:
            await room.broadcast_snapshot()
        return

    await ws.send_text(json.dumps(_err(ws, "unknown_type", f"Unknown message type {mtype!r}")))


@app.websocket("/ws/{code}")
async def ws_endpoint(ws: WebSocket, code: str) -> None:
    room = MANAGER.get(code)
    if not room:
        await ws.close(code=4404)
        return
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_text(json.dumps(_err(ws, "bad_json", "Malformed message.")))
                continue
            await _handle(room, ws, msg)
    except WebSocketDisconnect:
        pass
    finally:
        room.tv_sockets.discard(ws)
        room.socket_member.pop(ws, None)
        for mid, sockets in list(room.member_sockets.items()):
            sockets.discard(ws)
            if not sockets:
                room.member_sockets.pop(mid, None)
