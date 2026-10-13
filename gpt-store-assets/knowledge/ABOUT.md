# About these knowledge files

These are **copies** uploaded to the GPT's Knowledge section. The GPT
editor stores the uploaded bytes — not a live link — so they are snapshots
and must be re-synced whenever the source docs change.

| Copy in this directory | Source |
|---|---|
| `registry.json` | [`registry.json`](../../registry.json) |
| `README.md` | [`README.md`](../../README.md) |
| `adapter-checklist.md` | [`docs/adapter-checklist.md`](../../docs/adapter-checklist.md) |
| `BOOTSTRAP.md` | [`docs/BOOTSTRAP.md`](../../docs/BOOTSTRAP.md) |
| `packages/<pkg>.md` | each package's `README.md` (registry `local_dir` + `package.path`) |

Regenerate the copies from the repo root:

```bash
cp registry.json README.md gpt-store-assets/knowledge/
cp docs/adapter-checklist.md docs/BOOTSTRAP.md gpt-store-assets/knowledge/
python3 - <<'EOF'
import json, os, shutil
reg = json.load(open('registry.json'))
eco = os.path.expanduser('~/devin/devin-ecosystem')
for r in reg['repositories']:
    p = r.get('package') or {}
    if p.get('ecosystem') != 'pypi':
        continue
    base = os.path.join(eco, r.get('local_dir') or r['name'])
    src = os.path.join(base, p['path'], 'README.md') if p.get('path') else os.path.join(base, 'README.md')
    if os.path.isfile(src):
        shutil.copy(src, f"gpt-store-assets/knowledge/packages/{p.get('name', r['name'])}.md")
EOF
```

Then in the GPT editor: Edit → Knowledge → delete the stale file → upload
the fresh copy → Save/Update (full steps in
[`../README.md`](../README.md)).

Upload everything in this directory **except** this `ABOUT.md` — it
describes the package, it is not knowledge content.
