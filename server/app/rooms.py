"""Room state machine and WebSocket protocol handling.

Design rules (see docs/protocol.md):
- The server owns the authoritative state; clients render snapshots.
- Every room has one host token (the TV). Phones are members with tokens.
- Hard constraints are only relaxed after the owning member's explicit
  confirmation; votes stay sealed until voting closes.
- Duplicated requestIds are ignored (idempotency).
- State-changing broadcasts always follow a private reply when the actor
  needs confirmation (join, concession).
"""

from __future__ import annotations

import asyncio
import json
import secrets
import time
from dataclasses import dataclass, field

from fastapi import WebSocket

from .catalog import CATALOG
from .llm import get_analyzer, merge_preferences
from .matcher import apply_concession, build_candidates, conflict_proposals
from .models import (
    Candidate,
    ConcessionRequest,
    HardConstraints,
    Phase,
    Preferences,
    Result,
    SoftPreferences,
    TallyEntry,
)

MIN_MEMBERS = 2
VOTE_WINDOW_S = 30
CONCESSION_WINDOW_S = 30
ROOM_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L


def _now_ms() -> int:
    return int(time.time() * 1000)


def new_room_code(existing: set[str]) -> str:
    while True:
        code = "".join(secrets.choice(ROOM_CODE_ALPHABET) for _ in range(4))
        if code not in existing:
            return code


@dataclass
class Member:
    id: str
    name: str
    token: str
    preferences: Preferences | None = None
    vote: str | None = None
    voted_for_title: str | None = None
    concession_count: int = 0


@dataclass
class Room:
    code: str
    host_token: str
    phase: Phase = Phase.LOBBY
    members: dict[str, Member] = field(default_factory=dict)
    candidates: list[Candidate] = field(default_factory=list)
    result: Result | None = None
    pending_concession: ConcessionRequest | None = None
    concession_queue: list = field(default_factory=list)  # ConcessionProposal
    _pending_apply: tuple = field(default=(None, None))  # (field, value) for the pending concession
    vote_deadline_ms: int | None = None
    concession_deadline_ms: int | None = None
    # connection bookkeeping
    member_sockets: dict[str, set[WebSocket]] = field(default_factory=dict)
    tv_sockets: set[WebSocket] = field(default_factory=set)
    socket_member: dict[WebSocket, str] = field(default_factory=dict)
    seen_request_ids: set[str] = field(default_factory=set)
    _timers: list[asyncio.Task] = field(default_factory=list)
    _next_member = 1

    # ---------- helpers ----------

    def public_state(self) -> dict:
        return {
            "code": self.code,
            "phase": self.phase.value,
            "members": [
                {"id": m.id, "name": m.name, "submitted": m.preferences is not None}
                for m in self.members.values()
            ],
            "candidates": (
                [c.model_dump() for c in self.candidates]
                if self.phase in (Phase.VOTING, Phase.RESULT)
                else []
            ),
            "voteProgress": {
                "cast": sum(1 for m in self.members.values() if m.vote is not None),
                "total": len(self.members),
            },
            "voteDeadlineMs": self.vote_deadline_ms,
            "negotiation": (
                {"targetName": self.members[self.pending_concession.member_id].name}
                if self.pending_concession
                else None
            ),
            "result": self.result.model_dump() if self.result else None,
        }

    def private_state(self, member: Member) -> dict:
        return {
            "memberId": member.id,
            "role": "member",
            "submitted": member.preferences is not None,
            "voted": member.vote is not None,
            "pendingConcession": (
                self.pending_concession.model_dump()
                if self.pending_concession
                and self.pending_concession.member_id == member.id
                else None
            ),
        }

    # ---------- messaging ----------

    async def send_json(self, ws: WebSocket, payload: dict) -> None:
        try:
            await ws.send_text(json.dumps(payload))
        except Exception:
            pass  # socket died; disconnect handler cleans up

    async def broadcast(self, payload: dict) -> None:
        targets = list(self.tv_sockets)
        for sockets in self.member_sockets.values():
            targets.extend(sockets)
        for ws in targets:
            await self.send_json(ws, payload)

    async def send_to_member(self, member_id: str, payload: dict) -> None:
        for ws in list(self.member_sockets.get(member_id, ())):
            await self.send_json(ws, payload)

    async def broadcast_snapshot(self) -> None:
        public = self.public_state()
        for ws in list(self.tv_sockets):
            await self.send_json(
                ws, {"type": "snapshot", "room": public, "you": {"role": "tv"}}
            )
        for member_id, sockets in self.member_sockets.items():
            member = self.members.get(member_id)
            if not member:
                continue
            for ws in list(sockets):
                await self.send_json(
                    ws,
                    {
                        "type": "snapshot",
                        "room": public,
                        "you": self.private_state(member),
                    },
                )

    # ---------- state machine ----------

    async def set_phase(self, phase: Phase) -> None:
        self.phase = phase
        await self.broadcast({"type": "phase_changed", "phase": phase.value})

    def _cancel_timers(self) -> None:
        for task in self._timers:
            task.cancel()
        self._timers = []

    def _arm_vote_deadline(self) -> None:
        self.vote_deadline_ms = _now_ms() + VOTE_WINDOW_S * 1000

        async def closer() -> None:
            await asyncio.sleep(VOTE_WINDOW_S)
            if self.phase == Phase.VOTING:
                await self.close_voting()

        self._timers.append(asyncio.create_task(closer()))

    def _arm_concession_deadline(self, concession_id: str) -> None:
        self.concession_deadline_ms = _now_ms() + CONCESSION_WINDOW_S * 1000

        async def expirer() -> None:
            await asyncio.sleep(CONCESSION_WINDOW_S)
            if self.pending_concession and self.pending_concession.id == concession_id:
                await self.resolve_concession(concession_id, accepted=False)

        self._timers.append(asyncio.create_task(expirer()))

    async def begin_preferences(self) -> str | None:
        if self.phase != Phase.LOBBY:
            return "Preferences can only start from the lobby."
        if len(self.members) < MIN_MEMBERS:
            return f"Need at least {MIN_MEMBERS} members to start."
        await self.set_phase(Phase.PREFERENCES)
        await self.broadcast_snapshot()
        return None

    async def maybe_finish_collecting(self) -> None:
        if (
            self.phase == Phase.PREFERENCES
            and len(self.members) >= MIN_MEMBERS
            and all(m.preferences is not None for m in self.members.values())
        ):
            await self.run_matching()

    async def run_matching(self) -> None:
        await self.set_phase(Phase.MATCHING)
        prefs = {m.id: m.preferences for m in self.members.values()}
        names = {m.id: m.name for m in self.members.values()}
        candidates = build_candidates(CATALOG, prefs, names)

        if candidates:
            self.candidates = candidates
            self.result = None
            await self.start_voting()
            return

        # Deadlock: hand it to the negotiator.
        self.concession_queue = conflict_proposals(CATALOG, prefs, names)
        if not self.concession_queue:
            self.result = Result(
                no_pick=True,
                explanation=(
                    "No movie can satisfy everyone's bottom lines, and no safe "
                    "concession was possible. Restart and try again."
                ),
            )
            await self.set_phase(Phase.RESULT)
            await self.broadcast_snapshot()
            return
        await self.set_phase(Phase.NEGOTIATION)
        await self._offer_next_concession()

    async def _offer_next_concession(self) -> None:
        if not self.concession_queue:
            self.result = Result(
                no_pick=True,
                explanation=(
                    "Nobody was willing to bend tonight, so there is no common "
                    "pick. Restart and try different preferences."
                ),
            )
            await self.set_phase(Phase.RESULT)
            await self.broadcast_snapshot()
            return

        proposal = self.concession_queue.pop(0)
        concession = ConcessionRequest(
            id=f"c{secrets.token_hex(3)}",
            member_id=proposal.member_id,
            ask_text=proposal.ask_text,
            relax_summary=f"{proposal.current} -> {proposal.suggested}",
        )
        self.pending_concession = concession
        # Remember what to apply on accept.
        self._pending_apply = (proposal.field, proposal.value)
        self._arm_concession_deadline(concession.id)

        await self.send_to_member(
            proposal.member_id,
            {
                "type": "concession_request",
                "concessionId": concession.id,
                "askText": concession.ask_text,
                "relaxSummary": concession.relax_summary,
                "deadlineMs": self.concession_deadline_ms,
            },
        )
        await self.broadcast_snapshot()  # others see "negotiating with <name>"

    async def resolve_concession(self, concession_id: str, *, accepted: bool) -> None:
        if not self.pending_concession or self.pending_concession.id != concession_id:
            return
        concession = self.pending_concession
        member = self.members.get(concession.member_id)
        self.pending_concession = None
        self.concession_deadline_ms = None

        if accepted and member and member.preferences:
            field_name, value = self._pending_apply
            member.preferences = apply_concession(
                member.preferences, field_name, value
            )
            member.concession_count += 1
            await self.send_to_member(
                member.id,
                {
                    "type": "concession_resolved",
                    "concessionId": concession_id,
                    "accepted": True,
                },
            )
            await self.broadcast(
                {
                    "type": "concession_outcome",
                    "memberName": member.name,
                    "accepted": True,
                    "relaxSummary": concession.relax_summary,
                }
            )
            await self.run_matching()  # re-run with relaxed constraint
            return

        # Declined or expired: try the next proposal.
        await self.send_to_member(
            concession.member_id,
            {
                "type": "concession_resolved",
                "concessionId": concession_id,
                "accepted": False,
            },
        )
        if member:
            await self.broadcast(
                {
                    "type": "concession_outcome",
                    "memberName": member.name,
                    "accepted": False,
                    "relaxSummary": None,
                }
            )
        await self._offer_next_concession()

    async def start_voting(self) -> None:
        for m in self.members.values():
            m.vote = None
        self._cancel_timers()
        await self.broadcast(
            {"type": "candidates_ready", "candidates": [c.model_dump() for c in self.candidates]}
        )
        await self.set_phase(Phase.VOTING)
        self._arm_vote_deadline()
        await self.broadcast_snapshot()

    async def close_voting(self) -> None:
        if self.phase != Phase.VOTING:
            return
        self._cancel_timers()
        self.vote_deadline_ms = None

        tally: dict[str, int] = {c.movie.id: 0 for c in self.candidates}
        for m in self.members.values():
            if m.vote in tally:
                tally[m.vote] += 1
        by_id = {c.movie.id: c for c in self.candidates}
        entries = [
            TallyEntry(candidate_id=cid, title=by_id[cid].movie.title, votes=v)
            for cid, v in tally.items()
        ]
        entries.sort(key=lambda e: (-e.votes, -by_id[e.candidate_id].score))

        voted = sum(1 for m in self.members.values() if m.vote is not None)
        if voted == 0:
            self.result = Result(
                no_pick=True,
                explanation="Nobody voted in time. Restart for another round.",
                tally=entries,
            )
        else:
            winner_id = entries[0].candidate_id
            # Deterministic tie-break: group score, then shorter runtime,
            # then title - already the candidate ordering, so entries[0] wins.
            winner = by_id[winner_id]
            reason_bits = []
            for r in winner.reasons:
                who = f"{r.for_member}: " if r.for_member else ""
                reason_bits.append(f"{who}{r.text}")
            concessions = [
                m.name for m in self.members.values() if m.concession_count > 0
            ]
            concession_note = (
                f" A special thanks to {' and '.join(concessions)} for bending a little."
                if concessions
                else ""
            )
            self.result = Result(
                winner=winner,
                tally=entries,
                explanation=(
                    f"{winner.movie.title} ({winner.movie.year}) takes the night with "
                    f"{entries[0].votes} of {voted} vote(s). {reason_bits[0]}{concession_note}"
                ),
            )
        await self.set_phase(Phase.RESULT)
        await self.broadcast(
            {
                "type": "result",
                "result": self.result.model_dump(),
            }
        )
        await self.broadcast_snapshot()

    async def restart(self) -> None:
        self._cancel_timers()
        self.candidates = []
        self.result = None
        self.pending_concession = None
        self.concession_queue = []
        self.vote_deadline_ms = None
        self.concession_deadline_ms = None
        for m in self.members.values():
            m.preferences = None
            m.vote = None
            m.concession_count = 0
        await self.set_phase(Phase.LOBBY)
        await self.broadcast_snapshot()


class RoomManager:
    def __init__(self) -> None:
        self.rooms: dict[str, Room] = {}

    def create_room(self) -> tuple[str, str]:
        code = new_room_code(set(self.rooms))
        host_token = secrets.token_hex(16)
        self.rooms[code] = Room(code=code, host_token=host_token)
        return code, host_token

    def get(self, code: str) -> Room | None:
        return self.rooms.get(code)


MANAGER = RoomManager()
ANALYZER = get_analyzer()
