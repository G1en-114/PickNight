# PickNight message protocol (v1)

Single source of truth for client-server messages. The server (`server/app`)
implements it; mobile (`mobile/src/types.ts`) and TV (`tv/src/App.tsx`) mirror it.

Transport: one WebSocket per client at `ws(s)://<server>/ws/<ROOM_CODE>`.
JSON text frames. The server is authoritative - clients render snapshots.

## Identity

- `POST /api/rooms` → `{ room_code, host_token }`. The TV holds the host token.
- Phones join with a display name, receive `{ memberId, memberToken }`, and
  should store the token (sessionStorage) to rejoin after disconnects.
- Disconnecting never removes a member; reconnect + `join` with the token
  restores identity and yields a fresh snapshot.

## Idempotency

State-changing member messages carry a `requestId`. Duplicate `requestId`s are
dropped silently by the server.

## Client → Server

| type | who | payload | notes |
| --- | --- | --- | --- |
| `join` | all | `role: "tv" \| "member"`, `name?`, `token?` | TV sends the host token |
| `start_preferences` | TV | - | lobby → preferences; needs ≥ 2 members |
| `restart` | TV | - | back to lobby, keeps members |
| `submit_preferences` | member | `requestId`, `hard{}`, `soft{}`, `freeText` | private; auto-advances when all submitted |
| `concession_response` | member | `requestId`, `concessionId`, `accepted` | only the targeted member may answer |
| `cast_vote` | member | `requestId`, `candidateId` | one vote each, sealed until close |
| `ping` | any | - | server replies `pong` |

### `hard` (bottom lines - enforceable, only relaxed by the owner's confirmed concession)

```
max_runtime_min?: int        # e.g. 120
excluded_genres?: string[]   # e.g. ["Horror"]
excluded_keywords?: string[]
max_content_rating?: "G"|"PG"|"PG-13"|"R"
```

### `soft` (ranking + explanation only)

```
preferred_genres?: string[]
mood?: string                # matched against movie tags
era?: "new"|"classic"
```

## Server → Client

| type | audience | payload |
| --- | --- | --- |
| `joined` | sender | `role`, (`memberId`, `memberToken`), `room` |
| `snapshot` | per-socket | `room` (public state), `you` (role-scoped private state) |
| `phase_changed` | broadcast | `phase` |
| `preferences_progress` | broadcast | `submitted` memberId, `name` |
| `candidates_ready` | broadcast | `candidates[]` (movie + score + reasons) |
| `concession_request` | **targeted member only** | `concessionId`, `askText`, `relaxSummary`, `deadlineMs` |
| `concession_outcome` | broadcast | `memberName`, `accepted` (never the private content) |
| `vote_progress` | broadcast | `cast`, `total`, `deadlineMs` |
| `result` | broadcast | `result{ no_pick, winner, tally, explanation }` |
| `error` | sender | `code`, `message`, `forRequestId?` |

### Phases

`lobby → preferences → matching → (negotiation → matching)* → voting → result`

- **matching** is server-side and instant (stub) or LLM-backed (later).
- **negotiation** triggers only when zero movies survive everyone's hard
  constraints. The server computes minimal single-member relaxations and asks
  that member privately. Accepting re-runs matching; declining moves to the
  next proposal; exhausting proposals ends in a `no_pick` result.
- Tie-break at vote close is deterministic: votes → group soft score →
  shorter runtime → title (A-Z). It never depends on model output.

## Privacy rules

- Preferences and concession requests are private to their member.
- The TV and other members only learn *who* is negotiating and *whether* they
  agreed - never what was asked.
- Individual votes are never revealed; only the tally per candidate.
