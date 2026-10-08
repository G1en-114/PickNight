# Friction log

Real friction we hit while using Amazon's developer tools for this project.
Recorded as we go (hackathon submission may credit genuine friction logs).

Format: date · tool · task · expected / actual · severity · workaround · suggestion.

---

## 2026-10-08 · Vega SDK (install docs) · Set up the TV app dev environment

- **Task:** Install the Vega SDK on the team's Windows 11 machine to develop
  the Fire TV app.
- **Expected:** An installer or documented Windows/WSL path, like most
  modern mobile SDKs.
- **Actual:** Official install requirements list native macOS and Ubuntu
  only; Windows and WSL are explicitly unsupported. The team had to split
  development: all server/mobile work stays on Windows, TV-app builds move
  to a teammate's Mac/Linux machine, which slows the feedback loop for
  remote-control and focus testing.
- **Severity:** High for Windows-based teams.
- **Workaround:** Develop TV screens as late-bound as possible; keep the
  protocol snapshot-driven so the TV UI is thin; nightly builds on the
  teammate machine.
- **Suggestion:** Officially support WSL2 for the Vega toolchain, or publish
  a remote container/devcontainer image.

## (template for future entries)

- **Date / tool / task:**
- **Expected:**
- **Actual:**
- **Severity:** low / medium / high
- **Workaround:**
- **Suggestion:**
