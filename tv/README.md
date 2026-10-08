# PickNight TV (Vega OS / React Native)

The Fire TV app. **This can only be built on native macOS or Ubuntu** - the
Vega SDK does not support Windows/WSL (see `docs/friction-log.md`). The
Windows-side teammate develops the mobile web app and the server; this folder
is finalized on the Vega machine.

## Setup (Mac / Ubuntu owner)

1. Install the Vega SDK following the official guide:
   https://developer.amazon.com/docs/vega/0.24/install-vega-sdk
2. From this folder, install deps and verify the toolchain:
   ```bash
   npm install
   npm run start:simulator   # boots the Vega Virtual Device
   ```
3. Build / install / launch on the simulator:
   ```bash
   npm run app:build:debug
   ```
4. Point the app at the backend by copying `.env.example` to `.env`.

## What to build here

Screens (see `src/App.tsx` for the state-driven skeleton):

| Phase | TV shows | Remote does |
| --- | --- | --- |
| lobby | room code + join QR + member list | Start (needs ≥ 2 members) |
| preferences | who has submitted | nudge |
| matching | animated "matching" state | - |
| negotiation | "negotiating with &lt;name&gt;" (never the content) | - |
| voting | 3 candidate cards + sealed progress + countdown | highlight only |
| result | winner + reasons + tally | Restart |

Rules of thumb: 10-foot UI (big type, high contrast), D-pad focus must be
visible at distance, and the TV never renders private member input.

## Status

- [ ] Scaffold verified on a real Vega environment
- [ ] QR code rendering (candidate lib: pure-JS QR generator)
- [ ] D-pad navigation on all screens
- [ ] Deploy config against the FastAPI backend
