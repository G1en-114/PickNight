# PickNight 🌙🍿

**The family movie-night negotiator for Fire TV.** Picking a movie together
takes forever because everyone's bottom lines conflict. PickNight collects
each person's limits privately, finds what genuinely works for the group,
and - when nothing does - negotiates the smallest possible compromise with
exactly the person who can unlock it. Nobody's hard lines are ever relaxed
without their explicit OK.

Built for the [Build, Ship, Shape: Amazon Developer Hackathon 2026]
(https://amazonappdev2026.devpost.com/), Fire TV track.

## How a night works

1. The TV (Fire TV / Vega OS) creates a room; family members scan the QR.
2. Each phone collects **bottom lines** (runtime, content rating, hard vetoes)
   and **moods** - privately, in plain language.
3. PickNight filters the catalog by *everyone's* bottom lines and ranks three
   candidates with per-person reasons ("matches Kid: Animation; feels cozy").
4. Sealed 30-second vote on phones, live progress on the TV.
5. If nothing survives the group's constraints, PickNight identifies the
   minimal concession ("Dad, if you allow up to 140 min, 4 movies open up")
   and asks **only Dad**, privately, with the right to refuse.
6. Result: the winner, why it won, who bent a little, and where to watch it.

## Repository layout

| Folder | What |
| --- | --- |
| [`server/`](server/) | FastAPI backend: room state machine, deterministic matcher & conflict negotiator, sample catalog, stub preference analyzer, tests |
| [`mobile/`](mobile/) | Phone web app (React + Vite): join, preferences, concession response, sealed voting |
| [`tv/`](tv/) | Fire TV app (React Native for Vega OS) - build on macOS/Ubuntu only, see its README |
| [`docs/protocol.md`](docs/protocol.md) | The client-server message contract |
| [`docs/architecture.md`](docs/architecture.md) | Architecture and the "AI proposes, code decides" principle |
| [`docs/friction-log.md`](docs/friction-log.md) | Amazon-tool friction we actually hit |

## Quick start

```bash
# 1) Backend (any OS)
cd server
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 2) Phone web app
cd mobile
npm install
npm run dev            # http://localhost:5173/?room=CODE

# 3) TV app - macOS/Ubuntu with Vega SDK only; see tv/README.md
```

Create a room with `curl -X POST http://localhost:8000/api/rooms`, open the
mobile app with the returned code, and play through a full night. To see the
negotiation moment: one person caps runtime at 90 min while another vetoes
animation, family and comedy.

## Status

Scaffold - backend flow is tested end-to-end (`cd server && pytest`),
mobile renders all phases, TV awaits its first real Vega build.

## Team workflow

Windows machine: server + mobile + all shared logic. macOS/Ubuntu machine
(Vega SDK): `tv/` builds, simulator recordings, D-pad checks.

## License

TBD - will be set to an open-source license before the hackathon submission
deadline, as required by the rules.
