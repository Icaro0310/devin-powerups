# About these knowledge files

These are **copies** uploaded to the GPT's Knowledge section. The GPT
editor stores the uploaded bytes — not a live link — so they are snapshots
and must be re-synced whenever the source docs change.

| Copy in this directory | Source (repo root) |
|---|---|
| `registry.json` | [`registry.json`](../../registry.json) |
| `README.md` | [`README.md`](../../README.md) |
| `adapter-checklist.md` | [`docs/adapter-checklist.md`](../../docs/adapter-checklist.md) |

Regenerate the copies from the repo root:

```bash
cp registry.json README.md gpt-store-assets/knowledge/
cp docs/adapter-checklist.md gpt-store-assets/knowledge/
```

Then in the GPT editor: Edit → Knowledge → delete the stale file → upload
the fresh copy → Save/Update (full steps in
[`../README.md`](../README.md)).

Upload everything in this directory **except** this `ABOUT.md` — it
describes the package, it is not knowledge content.
