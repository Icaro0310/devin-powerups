<div align="center">

<a href="https://github.com/Icaro0310/devin-devkit/actions/workflows/test-skill-catalog.yml"><img src="https://github.com/Icaro0310/devin-devkit/actions/workflows/test-skill-catalog.yml/badge.svg" alt="ci"/></a>

<a href="https://scorecard.dev/viewer/?uri=github.com/Icaro0310/devin-devkit"><img src="https://api.scorecard.dev/projects/github.com/Icaro0310/devin-devkit/badge" alt="OpenSSF Scorecard"/></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT"/></a>
<a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+"/></a>
<a href="https://github.com/Icaro0310/devin-devkit"><img src="https://img.shields.io/github/stars/Icaro0310/devin-devkit" alt="GitHub stars"/></a>
<a href="https://github.com/Icaro0310/devin-devkit/commits/main"><img src="https://img.shields.io/github/last-commit/Icaro0310/devin-devkit" alt="Last commit"/></a>
<a href="https://github.com/Icaro0310/awesome-devin"><img src="https://img.shields.io/badge/part%20of-devin--*-ecosystem-7c3aed" alt="devin-* ecosystem"/></a>
<a href="https://github.com/Icaro0310/devin-devkit/issues"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen" alt="PRs welcome"/></a>
</div>

<!-- DEVIN-ECO:BEGIN -->
> **Part of the [DEVIN ecosystem](https://github.com/Icaro0310/awesome-devin)**  
> Track: Build · Nature: product  
> For: Maintainers, AI engineers, Developers  
> Interface: CLI / Registry  
> Path: Developers · step 2/4 — after `devin-devkit`, before `devin-internals-spec`
<!-- DEVIN-ECO:END -->


# devin-skill-catalog

> **Unofficial community project.** Not affiliated with, endorsed by, or
> sponsored by Cognition AI. "Devin" is a trademark of Cognition AI.

**[Linux](README.linux.md)** · **[Personal Windows](README.windows.md)** · **[Corporate Windows](README.corporate-windows.md)**

Part of the [awesome-devin](https://github.com/Icaro0310/awesome-devin) ecosystem: the curated hub for the devin-* tools.

`devin-skill-catalog` inventories, lints, quarantines and promotes the
`SKILL.md` skills and `rules/*.md` rules that live under `.devin/` dirs —
workspace-level and user-level. It adds a lifecycle registry, a
per-workspace inventory diff, two offline evidence gates, and a portable
bundle format so approved items can move between machines **through**
quarantine instead of around it.

## The problem

`.devin/skills/` and `.devin/rules/` accumulate content from everywhere —
hand-written, copied from other repos, pasted from a chat. Nothing
answers the basic questions: *what is installed where? did this skill
change between my workspaces? does this rule contain injection phrasing
or a pasted API key? and which of these have I actually reviewed?*

`devin-skill-catalog` is the inventory + supply-chain gate for that
content.

## What it does

- **Inventory** — scans `.devin/skills/<name>/SKILL.md` and
  `.devin/rules/*.md`, hashes each item (sha256), annotates it with its
  registry state.
- **Lint** — structural checks: frontmatter presence, `name` matching
  the directory, a real `description`, `# ` titles on rules.
- **Gates** — two offline evidence gates (G1/G2, below) plus a G3
  promotion gate driven by `g3-report` verdicts. G1/G2 are heuristics,
  **not proof**.
- **Lifecycle** — a registry at
  `<config-dir>/.devin-ecosystem/skill-catalog.json` tracks every item
  through `proposed → quarantined → approved → active → retired`.
- **Diff** — content-hash comparison of the inventories of two dirs.
- **Bundles** — export `approved` items to a directory or `.tar[.gz]`
  with a `manifest.json` (items, per-file sha256, source profile);
  import verifies checksums and lands items **quarantined — never
  directly active**.

## Install

Requires Python ≥ 3.10 and `pipx` or `uv`. Stdlib only — no dependencies.

```bash
uv tool install devin-skill-catalog   # or: pipx install devin-skill-catalog
```

Published on PyPI as `devin-skill-catalog`. The bundled DevKit manifest
still installs it from the GitHub source archive; profile installs and the
PyPI install produce the same CLI.

## Commands

```bash
devin-skill-catalog scan [PATH ...]              # inventory (read-only)
devin-skill-catalog lint [PATH ...]              # structural findings
devin-skill-catalog diff A B                     # inventory diff by sha256
devin-skill-catalog gate g1 PATH                 # static hygiene gate
devin-skill-catalog gate g2 PATH [--packs-dir D] # grounding gate
devin-skill-catalog quarantine ITEM [PATH ...]   # snapshot → quarantined
devin-skill-catalog promote ITEM [--force]       # quarantined → approved (G1 + G3 policy)
              [--g3-report PATH]
              [--g3-inconclusive-reason "…"]
devin-skill-catalog activate ITEM                # approved → active
devin-skill-catalog retire ITEM                  # any state → retired
devin-skill-catalog export-bundle --out DIR      # pack approved items
devin-skill-catalog import-bundle PATH           # land items quarantined
```

`ITEM` is `kind:name` (`skill:foo`, `rule:bar`) or a bare name when it
resolves unambiguously. `PATH` accepts a workspace root, a `.devin` dir,
a skill dir or a single file.

**Plan-first mutations.** `quarantine`, `promote`, `activate`, `retire`
and `import-bundle` print a plan and write nothing unless `--apply` is
passed:

```
$ devin-skill-catalog quarantine skill:demo ./ws
plan:
  quarantine skill:demo (currently proposed)
  copy 1 file(s)  ./ws/.devin/skills/demo
               → ~/.config/devin/.devin-ecosystem/skill-catalog/quarantine/skill/demo
  registry: proposed → quarantined
  note: the original files in .devin/ stay untouched — remove them
        manually if the item must stop loading

nothing written — re-run with --apply to execute
```

**Read-only scanned dirs.** The tool *never* writes to a `.devin/` dir.
The only write targets are the registry file and quarantine store under
the Devin config dir, plus whatever you point `--out` at. Quarantine
snapshots the item; removing the original from `.devin/` is your call.

## Lifecycle

```
proposed → quarantined → approved → active → retired
               ↑____________________|          ↓
               (approve can be rolled back;    retired → proposed
                retire works from any state)    (re-propose)
```

- `quarantine` — copies the item into the quarantine store (outside
  `.devin/`, so Devin never loads it) and marks it `quarantined`.
- `promote` — runs **G1 on the stored copy** and enforces the **G3
  promotion policy** (below); a G1 FAIL refuses the promotion
  (`--force` overrides — but never a `regresses` verdict).
  `quarantined → approved`.
- `activate` — marks the item `active` in the catalog. Installing files
  into `.devin/` remains a manual step — this tool never writes there.
- `retire` — parks an item; `retired → proposed` is the only way back.

Unregistered items found on disk report as unregistered — the catalog
does not pretend to have reviewed what it has never seen.

## Gates

### G1 — static hygiene

The lint checks **plus** heuristic scans over every text file of the
item:

- prompt-injection phrasing (`ignore previous instructions`,
  `disregard previous`, jailbreak openers, `do not tell the user`)
- system-prompt exfiltration phrasing
- download-and-execute patterns (`curl … | sh`)
- destructive shell patterns (`rm -rf /`, fork bombs)
- secret-shaped strings — GitHub/Slack token prefixes, `sk-…` keys,
  `AKIA…`, private-key markers, high-entropy runs, large base64 blobs

Secret findings print *"possible secret at line N — value suppressed"*:
**the matched value is never printed**, in text or JSON output.

`promote --apply` runs G1 on the quarantined copy and refuses on FAIL.
`gate g1|g2 PATH --apply` records per-item gate results in the registry.

### G2 — offline evidence (grounding)

Does what the item *claims* line up with what *exists*?

- frontmatter-declared `files`/`scripts` must exist next to the item
  (missing → FAIL)
- inline code-span path references are resolved relative to the item
  (missing → WARN — the skill may create them)
- declared `commands`/`tools` are checked on `PATH` (missing → WARN)
- `--packs-dir DIR` verifies devin-evals rubric packs are loadable —
  noted, **not executed** (eval runs are devin-evals' job)

### G3 — measured effect (promotion policy)

G3 is not a heuristic this tool runs — it is a **promotion policy**
consuming a `g3-report/0.1` JSON produced elsewhere (an A/B eval run,
e.g. devin-evals). Pass it with `promote --g3-report PATH`:

| item | no report | `improves` / `no-detectable-effect` | `inconclusive` | `regresses` |
|------|-----------|-------------------------------------|----------------|-------------|
| always-on rule (`.devin/rules`) | **refused** | promoted | refused | **refused** |
| skill (`.devin/skills`) | promoted; registry records `g3: "not-measured"` | promoted; records `g3: "<verdict>"` + report path | promoted only with `--g3-inconclusive-reason "…"` (recorded) | **refused** |

- `regresses` is a **hard block for every kind** — a regressed
  artifact must not be promoted, and `--force` does **not** override
  it (`--force` only lifts a G1 FAIL).
- Promotion stays an explicit human decision: `--apply` is still
  required; without it the plan prints what the verdict would do and
  writes nothing.
- If the report's `candidate.sha256` does not match the stored copy,
  promote prints a warning but proceeds — the report may legitimately
  describe a pre-fix artifact.

## Adopting external skills

Adopting a third-party skill means a governed catalog entry pinned by
SHA-256, not a code fork and not a bare pointer. Upstream URLs are
provenance; the catalog governs a frozen local copy.

1. **Vendor into a staging `.devin` dir that nothing loads** — never
   straight into a live workspace or the user skills dir; files there
   load immediately, bypassing the gates. Any folder shaped like
   `.devin/skills/` works:

   ```
   <staging>/.devin/skills/<name>/   ← copy of the upstream skill dir
   ```

2. **Govern through the normal lifecycle:**

   ```
   devin-skill-catalog scan <staging>/.devin --no-user
   devin-skill-catalog quarantine skill:<name> <staging>/.devin --apply \
       --note "vendor adopt: <upstream-url> @ <commit>"
   devin-skill-catalog gate g1 <staging>/.devin/skills/<name>
   devin-skill-catalog promote skill:<name> --apply --note "G1 pass"
   devin-skill-catalog activate skill:<name> --apply
   ```

3. **Install only what you want live, manually** — copy the item dir
   into a live `skills/` dir (create it first so the copy lands at
   `skills/<name>/SKILL.md`). Per-OS skills dir paths are in the
   platform guides (`README.linux.md`, `README.windows.md`,
   `README.corporate-windows.md`).

Rules of the road:

- Keep a `VENDORS.md` next to the staging dir: upstream URL, license,
  commit SHA, date. Keep the license file for MIT/CC-BY content.
- A G1 FAIL on third-party content deserves a human read before
  `--force`: skills that *teach* injection hygiene legitimately quote
  attack strings — that is a recorded false-positive, not a verdict.
- Active-in-catalog ≠ loaded. Install into a live skills dir only what
  you actually want in sessions.
- `export-bundle` packs **approved** items only — bundle a reviewed set
  before activating it, or keep shipping copies via `import-bundle`
  quarantine on the receiving side.
- On upstream changes, re-vendor by **replacing** the staged item dir
  (delete it, then copy) and re-quarantining from scratch — copying over
  the old tree leaves files upstream deleted, and the quarantine store
  merges rather than replaces, so stale files would survive the
  re-review.

Worked example: 25 skills from `addyosmani/agent-skills` (MIT), 6 from
`DietrichGebert/ponytail` (MIT) and a local `graphify` install were
governed this way on 2026-10-13 — 30 clean G1 passes and 2 documented
false-positives (quoted injection strings inside anti-injection
guidance), all promoted and activated.

## Honest limitations

- **Heuristic gates are not proof.** G1 catches known-bad phrasing and
  token *shapes*; a cleverly worded injection or an unusual secret
  format will sail through, and benign text can false-positive. A clean
  G1/G2 run means *"no red flags found"*, not *"safe"*.
- **`.devin/` is never written.** Quarantine marks + snapshots; it does
  not remove the original. Activation records intent; installing is
  manual.
- **Frontmatter is not YAML.** The parser handles the common subset
  (scalars, lists, block scalars) and degrades gracefully on the rest.
- **Registry ≠ audit log.** It records transitions and gate outcomes
  for your own workflow; it is not tamper-evident.
- Bundle imports trust the manifest format, not the manifest's claims:
  checksums are verified, but items still land quarantined and must pass
  the gates to promote.

## Development

```bash
pip install -e ".[dev]"
python -m pytest
```

Tests run entirely on synthetic `.devin/` fixture trees — nothing real
is scanned.

## When to use this

- You want to know which skills/rules exist across workspaces and user
  dirs, and whether they drifted (`diff`).
- You are about to adopt a skill from somewhere else and want a
  quarantine → gate → approve path instead of dropping it into `.devin/`.
- You want to move *reviewed* items between machines with checksum
  verification (`export-bundle` / `import-bundle`).

## When NOT to use this

- You want a security scanner with guarantees — the gates are
  heuristics, not proof (see *Honest limitations*).
- You want the tool to modify `.devin/` — it is deliberately read-only
  there; only the registry dir is writable.
- You want rubric evals executed — that is
  [devin-evals](https://github.com/Icaro0310/devin-assure/tree/main/packages/evals)' job; G2 only
  verifies packs are loadable.

## License

MIT — see [LICENSE](LICENSE).
