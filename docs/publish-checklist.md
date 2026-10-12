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
7. `.vsix` → VS Code Marketplace **portal** upload (manual step today).
8. Open VSX and Eclipse Marketplace — pending, see below.
9. Smoke-test every channel that shipped (per-channel notes below).

`release.yml` (reusable) collapses legs 3–5 and the CI-visible parts of
7–8 (lint + `.vsix` artifact + notices) into one fan-out call — legs 6
and the portal uploads stay manual. See
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
  blocked. The current path is the **portal upload**:
  <https://marketplace.visualstudio.com/manage/publishers/>, upload the
  `.vsix` produced by `vsce package` (the `vsix` workflow artifact).
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

- Namespace claim pending: **EclipseFdn/open-vsx.org#14088** for
  `icaro0310`. Until approved, publishing is impossible — the step in
  `release.yml` is commented out with the activation recipe.
- Once approved: create an Open VSX PAT and `npx ovsx publish --pat
  $OVSX_PAT` (or uncomment the step and forward `OVSX_PAT` via
  `secrets:`).
- Smoke: `ovsx get <publisher>.<name>` / the extension appears on
  open-vsx.org and in VSCodium's default registry.

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
