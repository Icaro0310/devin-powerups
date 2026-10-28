# Incident log

Operational incidents and audit surprises across the ecosystem, newest
first. Each entry records what happened, the blast radius, and the lesson
that outlives the fix.

## 2026-10-28 — Open VSX audit confusion

- **What happened:** a publication audit checked only the VS Code
  Marketplace and reported "zero published" for the ecosystem's VS Code
  extensions. In reality all 7 extensions were already published on
  **Open VSX** (`open-vsx.org/icaro0310/*`) — a separate registry the
  audit never queried.
- **Blast radius:** misleading audit output only; the extensions were
  correctly published the whole time.
- **Lesson:** "is it published?" audits must enumerate **every** channel
  the ecosystem ships through — PyPI, npm, Open VSX, VS Code Marketplace,
  GitHub releases/tags, and the product site. A single-channel answer is
  a false negative by construction.
- **Follow-up:** `tools/ecosystem_sync.py` now covers all channels
  (Marketplace reported as `unavailable` until the Entra credential
  lands, instead of silently skipping).
