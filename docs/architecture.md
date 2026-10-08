# Architecture

```text
┌─────────────────────────────┐        ┌─────────────────────────────┐
│  TV app (React Native for   │        │  Phone web app (React/Vite) │
│  Vega, Fire TV)             │        │  join via QR / room code    │
│                             │        │                             │
│  · public stage: candidates │        │  · private input: bottom    │
│    voting progress, result  │        │    lines, votes, concession │
│  · host actions: start,     │        │    responses                │
│    restart (D-pad driven)   │        │                             │
└──────────────┬──────────────┘        └──────────────┬──────────────┘
               │            WebSocket (JSON)          │
               └──────────────────┬───────────────────┘
                                  ▼
                 ┌────────────────────────────────────┐
                 │  Server (FastAPI, authoritative)   │
                 │  · room state machine + timers     │
                 │  · hard-constraint filtering       │
                 │  · candidate ranking + reasons     │
                 │  · conflict analysis & minimal     │
                 │    concession proposals            │
                 │  · preference extraction (stub →   │
                 │    LLM later)                      │
                 │  · movie catalog (sample → TMDB)   │
                 └────────────────────────────────────┘
```

## Core principle: AI proposes, code decides

The LLM layer (once wired in) only turns free text into structured
preferences and writes explanations. What is watchable, how candidates rank,
what a fair tie-break is, and whose constraint blocks the group are all
decided by deterministic code in `server/app/matcher.py`. Model output is
validated against this contract and can never silently relax a member's
bottom line - only that member's explicit confirmation can.

## Why the negotiation phase exists

Every competing product stops at "vote on options" or "swipe until match".
When the group has no overlap, they dead-loop. PickNight detects the
deadlock, computes the *smallest* relaxation that unlocks candidates, and
asks exactly that member - privately, with concrete examples, with the right
to refuse. The acceptance is the demo moment.

## Component map

| Folder | What | Runs where |
| --- | --- | --- |
| `server/` | FastAPI app, room state machine, matcher, catalog, stub analyzer + tests | anywhere (Windows OK) |
| `mobile/` | phone web app (join → preferences → negotiate → vote → result) | browser, `npm run dev` |
| `tv/` | Vega OS React Native app (public stage + host actions) | **macOS / Ubuntu only** (Vega SDK) |
| `docs/` | protocol, friction log, architecture | - |

## Development workflow (split machines)

1. Windows side: run `server` + `mobile`, develop all logic and UI.
2. Vega side (teammate): `npm install` inside `tv/`, boot the Vega Virtual
   Device, build & launch. `.env` points at the shared backend.
3. Both talk to the same backend over the LAN; use `VITE_SERVER_BASE` /
   `PICKNIGHT_SERVER` to point at the host machine's IP.

## MVP scope (hackathon)

- 2–4 members per room, one round, text input on phones.
- Sample catalog of 16 movies (TMDB integration is a stretch goal).
- Deterministic stub analyzer (LLM extraction is a stretch goal).
- 30-second voting window; concession auto-declines after 30 seconds.
