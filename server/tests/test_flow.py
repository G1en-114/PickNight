"""End-to-end flow tests over real WebSockets (Starlette TestClient).

Covers: create room -> TV joins -> members join -> collect preferences ->
auto matching -> candidates -> voting -> result; plus the conflict path with
a confirmed concession; plus idempotent duplicate votes.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from app.rooms import MANAGER

client = TestClient(app)


def recv_until(ws, want_type: str, max_messages: int = 50):
    """Pull messages until one of `want_type` arrives; return it."""
    for _ in range(max_messages):
        data = json.loads(ws.receive_text())
        if data.get("type") == want_type:
            return data
    raise AssertionError(f"never received {want_type}")


def _setup_room():
    resp = client.post("/api/rooms")
    assert resp.status_code == 200
    body = resp.json()
    return body["room_code"], body["host_token"]


def _join_member(ws, name: str):
    ws.send_text(json.dumps({"type": "join", "role": "member", "name": name}))
    return json.loads(ws.receive_text())


def _submit(ws, hard: dict, soft: dict | None = None, free_text: str = ""):
    ws.send_text(
        json.dumps(
            {
                "type": "submit_preferences",
                "requestId": f"req-{secrets_counter()}",
                "hard": hard,
                "soft": soft or {},
                "freeText": free_text,
            }
        )
    )


_secrets = iter(range(10000))


def secrets_counter() -> int:
    return next(_secrets)


def test_full_happy_path():
    code, host_token = _setup_room()
    with client.websocket_connect(f"/ws/{code}") as tv, \
         client.websocket_connect(f"/ws/{code}") as p1, \
         client.websocket_connect(f"/ws/{code}") as p2:
        tv.send_text(json.dumps({"type": "join", "role": "tv", "token": host_token}))
        assert json.loads(tv.receive_text())["role"] == "tv"

        j1 = _join_member(p1, "Dad")
        j2 = _join_member(p2, "Kid")
        assert j1["memberId"] != j2["memberId"]

        tv.send_text(json.dumps({"type": "start_preferences"}))
        recv_until(p1, "phase_changed")

        _submit(p1, {"max_runtime_min": 120}, {"preferred_genres": ["Animation"]})
        recv_until(p1, "preferences_ack")
        # Second submit triggers auto matching -> candidates -> voting.
        _submit(p2, {"excluded_genres": ["Horror", "Thriller"]}, {"preferred_genres": ["Family"]})
        candidates = recv_until(p2, "candidates_ready")
        assert 1 <= len(candidates["candidates"]) <= 3

        voting = recv_until(p2, "phase_changed")
        assert voting["phase"] == "voting"

        winner_id = candidates["candidates"][0]["movie"]["id"]
        p1.send_text(json.dumps({"type": "cast_vote", "requestId": "v1", "candidateId": winner_id}))
        recv_until(p1, "vote_ack")
        p2.send_text(json.dumps({"type": "cast_vote", "requestId": "v2", "candidateId": winner_id}))

        result = recv_until(p1, "result")["result"]
        assert result["no_pick"] is False
        assert result["winner"]["movie"]["id"] == winner_id
        assert result["explanation"]
        # TV sees the same result.
        tv_result = recv_until(tv, "result")
        assert tv_result["result"]["winner"]["movie"]["id"] == winner_id


def test_duplicate_vote_is_idempotent():
    code, host_token = _setup_room()
    with client.websocket_connect(f"/ws/{code}") as tv, \
         client.websocket_connect(f"/ws/{code}") as p1, \
         client.websocket_connect(f"/ws/{code}") as p2:
        tv.send_text(json.dumps({"type": "join", "role": "tv", "token": host_token}))
        json.loads(tv.receive_text())
        _join_member(p1, "A")
        _join_member(p2, "B")
        tv.send_text(json.dumps({"type": "start_preferences"}))
        recv_until(p1, "phase_changed")
        _submit(p1, {})
        recv_until(p1, "preferences_ack")
        _submit(p2, {})
        candidates = recv_until(p1, "candidates_ready")
        cid = candidates["candidates"][0]["movie"]["id"]

        # Same requestId delivered twice must only count once.
        p1.send_text(json.dumps({"type": "cast_vote", "requestId": "dup", "candidateId": cid}))
        recv_until(p1, "vote_ack")
        p1.send_text(json.dumps({"type": "cast_vote", "requestId": "dup", "candidateId": cid}))

        p2.send_text(json.dumps({"type": "cast_vote", "requestId": "b1", "candidateId": cid}))
        result = recv_until(p2, "result")["result"]
        votes = sum(e["votes"] for e in result["tally"])
        assert votes == 2, f"expected exactly 2 votes, tally was {result['tally']}"


def test_conflict_leads_to_concession_and_recovery():
    code, host_token = _setup_room()
    with client.websocket_connect(f"/ws/{code}") as tv, \
         client.websocket_connect(f"/ws/{code}") as p1, \
         client.websocket_connect(f"/ws/{code}") as p2:
        tv.send_text(json.dumps({"type": "join", "role": "tv", "token": host_token}))
        json.loads(tv.receive_text())
        _join_member(p1, "Short-tempered Sam")   # wants <= 90 min
        _join_member(p2, "Picky Pam")            # bans animation/family/comedy
        tv.send_text(json.dumps({"type": "start_preferences"}))
        recv_until(p1, "phase_changed")

        _submit(p1, {"max_runtime_min": 90})
        recv_until(p1, "preferences_ack")
        _submit(p2, {"excluded_genres": ["Animation", "Family", "Comedy"]})

        # Greedy conflict analysis relaxes Sam's runtime cap first (it unlocks
        # the most movies), so the targeted request lands on p1 only.
        concession = recv_until(p1, "concession_request")
        assert "e.g." in concession["askText"]

        p1.send_text(
            json.dumps(
                {
                    "type": "concession_response",
                    "requestId": "cr1",
                    "concessionId": concession["concessionId"],
                    "accepted": True,
                }
            )
        )
        candidates = recv_until(p1, "candidates_ready")
        assert candidates["candidates"], "concession must unlock candidates"


def test_cannot_start_with_one_member():
    code, host_token = _setup_room()
    with client.websocket_connect(f"/ws/{code}") as tv, \
         client.websocket_connect(f"/ws/{code}") as p1:
        tv.send_text(json.dumps({"type": "join", "role": "tv", "token": host_token}))
        json.loads(tv.receive_text())
        _join_member(p1, "Lonely")
        tv.send_text(json.dumps({"type": "start_preferences"}))
        err = recv_until(tv, "error")
        assert err["code"] == "cannot_start"
