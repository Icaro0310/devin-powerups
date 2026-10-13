# Publish checklist — per channel, with the findings that bit us

The release order of operations for any package in the ecosystem.
Per-channel gotchas are findings from real publish runs — each one is a
checklist item because it failed (or silently blocked) at least once.

## Order of operations

1. Version bump PR lands on `main` — `pyproject.toml` `version` and the
   wheel's `__version__` must agree (the wheel gate enforces it).
2. Tag `<pkg>-v<ver>` on `main` → the repo's release workflow runs.
   `release.yml` fails the PyPI leg when a `<pkg>-v<ver>` tag does not
   match the pyproject version — a mistagged release would otherwise
   pass the wheel gate and publish the wrong version.
3. Wheel gate: `verify-wheel-version.yml` builds `dist/`, asserts
   `__version__ == pyproject.version`, uploads the verified `dist`
   artifact. Nothing publishes that did not pass this gate.
4. PyPI upload via the repo's own `pypi-publish.yml` (environment gate
   + OIDC trusted publishing — see below).
5. GHCR image build+push via the repo's `docker-publish.yml` (triggers
   on the publish workflow succeeding; cosign keyless signature).
6. GitHub release creation — stays **manual** (or a separate caller
   step); the GitHub Marketplace checkbox lives on the release form, so
   the release author must tick it *here*. `release.yml` does not
   create the GitHub release.
7. `.vsix` → VS Code Marketplace — CI publishes via Entra workload
   identity when the caller repo sets `AZURE_CLIENT_ID`/`AZURE_TENANT_ID`;
   otherwise the `vsix` artifact stays for a **portal** upload (manual
   fallback).
8. Open VSX — CI publishes via `ovsx` when the caller forwards
   `OVSX_PAT`; Eclipse Marketplace — still pending moderation, see
   below.
9. Smoke-test every channel that shipped (per-channel notes below).

`release.yml` (reusable) collapses legs 3–5 and the CI-visible parts of
7–8 (lint + `.vsix` artifact + Entra publish or notice) into one fan-out
call — leg 6 stays manual. See
[VARIANTS.md](../.github/workflows/VARIANTS.md) for the caller template
and the PyPI cross-repo caveat.

## PyPI

- Auth is **OIDC Trusted Publishing only** — no API tokens
  (`secrets-scan` fails any live `secrets.PYPI_API_TOKEN` reference).
- Trusted Publisher fields must match **exactly**: owner, repo,
  workflow filename, environment. The environment names in use:
  `pypi`, `pypi-devkit`, `pypi-skill-catalog`, `pypi-switch`. A typo on
  any field fails the exchange with `invalid-publisher`.
- **Reusable-workflow callers cannot publish**: PyPI validates
  `job_workflow_ref`, which for a `uses:` call resolves to the reusable
  file's repo — a per-repo TP can never match it
  (pypi/warehouse#11096). Each product repo carries an *inline*
  `pypi-publish.yml`; `release.yml`'s PyPI leg detects the cross-repo
  case and skips with a warning rather than failing.
- The wheel's `__version__` must equal the pyproject `version` — the
  verify gate blocks the release otherwise.
  A `Version lockstep` step in the shared `python-test.yml` catches the
  same drift at PR time; a FAIL on an **archived/absorbed** repo (e.g.
  standalone `devin-metrics`, superseded by the assure monorepo) is
  informative, not blocking — the sensor measures state, not intent;
  the maintainer decides whether the dead repo is worth the sync.

- Re-publishing the same version fails at upload with
  **"file already exists"** — and that failure is *good news*: it
  proves the OIDC exchange worked (an auth failure is a **403** during
  token exchange, before upload). `release.yml` pre-checks the PyPI
  JSON API **per file** so the leg stays green on re-runs and resumes
  partial releases (a published sdist with a missing wheel uploads the
  wheel, not a blanket skip).
- A *pending* publisher is consumed by the first successful upload; if
  anything else creates the project first the pending entry goes stale
  (`invalid-pending-publisher`) — delete it and add an **Active**
  publisher on the project's own Publishing settings.
- Smoke: `pip index versions <pkg>` or `pip install <pkg>==<ver>` in a
  fresh venv, then `python -c "import <mod>; print(<mod>.__version__)"`.
- **Index propagation lag**: after a successful upload, PyPI's CDN can
  serve the old file/version list for ~2-5 minutes. A downstream CI run
  (or `pip install <pkg>==<new>`) started in that window can fail with
  `from versions: <old-only>` — that is a **stale index, not a real
  failure**. Wait ~5 min and re-run; do not "fix" the code. If a
  workflow ever needs to poll for availability, retry 3× with 30-60s
  backoff rather than a single read.
- **Publish only from merged `main`** — this applies to manual publishes
  too (`ovsx publish`, `vsce publish`, portal upload). A publish run
  from an unmerged branch leaves the registry ahead of `main`; the next
  tag then either downgrades (rejected) or ships metadata that does not
  match the code. CI guards this via `verify-wheel-version`'s
  merged-into-main check; manual runs must self-check
  (`git merge-base --is-ancestor HEAD origin/main`) before uploading.
  Seen live: `devin-doctor` 0.1.1 reached Open VSX while `main` was 0.1.0.


## VS Code Marketplace

- `publisher` in `package.json` must equal the Marketplace publisher ID
  **exactly**, and publisher IDs are **lowercase** — a case mismatch
  fails at publish time, not at package time.
- `vsce package` requires `activationEvents` when `main` is set —
  devin-memory missed them and packaging failed outright. `release.yml`
  runs a manifest lint (publisher/name/engines/activationEvents,
  incl. `onMcpServerDefinitionProviders:<id>` hooks) before `vsce`.
- Extension `package.json` `version` ships **in lockstep** with the
  package version — `release.yml` fails the leg on mismatch, so bump
  it in the same PR as the pyproject bump.
- PAT/CLI publishing (`vsce publish`) needs a Personal Access Token from
  an **Azure DevOps org**, which needs an **Azure subscription** —
  not available. The active path is **Entra workload identity**:
  `release.yml`'s `vscode-ext` job runs under `environment: release`,
  `azure/login` mints an OIDC token against the
  `devin-vscode-marketplace` app registration (federated credential
  `gh-<repo>-release`), and `vsce publish --azure-credential` pushes the
  `.vsix`. Requires per-repo vars `AZURE_CLIENT_ID`/`AZURE_TENANT_ID`
  and a federated credential on the app for that repo — setup: Entra →
  App registrations → `devin-vscode-marketplace` → Certificates &
  secrets → Federated credentials → GitHub Actions → entity
  `Environment` = `release`. One-off helper to resolve the marketplace
  member ID: `devin-explore/.github/workflows/marketplace-identity.yml`
  (dispatch, read the `id` field, add it as publisher member →
  Contributor). Portal upload remains the manual fallback:
  <https://marketplace.visualstudio.com/manage/publishers/>.
- After the portal upload the listing shows **"Verifying"** — normal;
  validation is async and can take minutes to hours.
- Smoke: install the `.vsix` locally (`code --install-extension
  <file>.vsix`) *before* uploading; after publish, find the extension
  in Marketplace search and `code --install-extension
  <publisher>.<name>`.

## GitHub Marketplace (Actions)

- Listing is a **checkbox on the release-creation form** ("Publish this
  Action to the GitHub Marketplace") — set at creation only; **editing
  a release afterwards cannot add it**. Miss it and the fix is a new
  release.
- `action.yml` `description` must be **<125 chars** — a silent blocker:
  the checkbox stays disabled with no clear error.
- Branding (`icon` + `color`) is **required** in `action.yml` metadata.
- The listing slug comes from `action.yml` `name:`, **not** the repo
  name.
- Smoke: open the repo's Marketplace listing after release; install the
  action in a scratch workflow with `uses: owner/repo@<tag>`.

## Open VSX

- **Live since 2026-10-12.** All six extensions published (doctor,
  search, qa-pack, devkit, memory, bridge). Creating the `icaro0310`
  namespace granted contributor publish authority — no owner grant
  needed to publish.
- CI: the `release.yml` leg runs `ovsx publish --pat $OVSX_PAT
  --skip-duplicate --packagePath ./*.vsix` when the caller forwards the
  secret (`secrets:` mapping or `inherit`); absent, it warns and the
  vsix stays as the `vsix` artifact.
- Manual: `OVSX_PAT=<token> npx ovsx publish <file.vsix>` — PAT lives
  in the vault ("Open VSX + Eclipse" note), mirrored as the `OVSX_PAT`
  secret in the five extension repos.
- Still pending: **EclipseFdn/open-vsx.org#14088** — the owner grant
  only flips `verified: false`→`true` (removes the "not a verified
  publisher" banner); no republish needed when it lands.
- Smoke: `curl -s https://open-vsx.org/api/icaro0310/<name>/latest`
  (indexing takes a few minutes after publish).

## Eclipse Marketplace

- Listing submitted via the `/node/add/resource` form on
  marketplace.eclipse.org — currently **in moderation**. Nothing to
  automate; check the listing state on the portal.
- Smoke: search the Marketplace client (Eclipse → Help → Marketplace)
  for the listing once approved.

## Docker / GHCR

- Per-repo `docker-publish.yml` builds `ghcr.io/<owner>/<image>`, pushes
  `:latest` + `:<version>`, and signs with **cosign keyless** (OIDC,
  no keys to manage). `release.yml`'s docker leg mirrors that pattern
  for repos with a root `Dockerfile`.
- Image refs are **lowercase-only** — `ghcr.io/Icaro0310/...` is
  rejected by buildx. `release.yml` lowercases owner + image name; a
  hand-rolled workflow must do the same.
- The image tags come from the pyproject `version` — same source of
  truth as the wheel.
- Smoke: `cosign verify ghcr.io/<owner>/<image>:<ver>` (check the
  keyless cert identity is the repo's workflow), then `docker run --rm
  ghcr.io/<owner>/<image>:latest --help`.
