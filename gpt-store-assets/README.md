# GPT Store assets — publish the devin-* ecosystem GPT in ~3 minutes

Everything the OpenAI GPT editor needs, paste-ready. OpenAI exposes no API
for GPT creation: this is a one-time manual setup plus a resync step when
the knowledge docs change.

## Create (first publish)

1. Open <https://chatgpt.com/gpts/editor> (or "Explore GPTs → Create" in
   ChatGPT). A paid ChatGPT plan is required to build GPTs.
2. **Create** tab: skip the chatbot — open the **Configure** tab directly.
3. Fill the fields:
   - **Name**: `devin-* Ecosystem Guide` (free text — pick your own if
     preferred).
   - **Description**: paste the contents of [`description.txt`](description.txt).
   - **Instructions**: paste the full contents of
     [`instructions.md`](instructions.md) (sized to fit the 8,000-char cap).
   - **Conversation starters** (optional): suggested lines below.
   - **Capabilities**: Web Search can stay on (lets the GPT read repo docs
     live); Code Interpreter and Image Generation are not needed.
   - **Actions**: none — this GPT never calls external APIs.
4. **Knowledge → Upload files**: everything in [`knowledge/`](knowledge/)
   **except** `ABOUT.md` (`registry.json`, `README.md`,
   `adapter-checklist.md`).
5. Privacy policy: the publish dialog asks for a privacy URL when you
   publish publicly (also settable from the editor's settings). Paste the
   URL line from [`privacy-url.txt`](privacy-url.txt) — read the comment in
   that file first, the page must exist and cover this GPT before publish.
6. **Create/Publish** → choose visibility: "Only me", "Anyone with the
   link", or "Everyone" (GPT Store listing).

## Update (when the docs change)

1. <https://chatgpt.com/gpts> → your GPT → **Edit**.
2. Regenerate the knowledge copies — see [`knowledge/ABOUT.md`](knowledge/ABOUT.md)
   for the source paths and copy commands.
3. In the editor: **Knowledge** → delete the stale file, upload the fresh
   copy.
4. Edit the Instructions text if the ecosystem changed.
5. **Save → Update** — the listing picks up changes immediately.

## Suggested conversation starters

- `Which devin-* tool searches across all my sessions?`
- `How do I back up Devin's local stores safely?`
- `What is the difference between devin-assure and devin-explore?`
- `How do I install the ecosystem with devin-devkit?`

## Gotchas

- **Instructions cap**: 8,000 chars. `instructions.md` is sized to fit —
  keep it that way when editing.
- **Knowledge files are snapshots**: the editor stores the uploaded bytes,
  not a live link. Resync on every registry/README change that matters.
- **Builder profile**: publishing to "Everyone" requires a public builder
  profile — set a display name (or verify a domain) under ChatGPT settings
  → Builder profile.
- **No invented surface**: keep `instructions.md` truthful — only commands,
  repos and features documented in `README.md` / `registry.json`. The GPT
  must never offer to run mutating commands for the user; the ecosystem's
  own tools are dry-run-first by design and the GPT only explains them.
- **Unofficial**: the listing description and instructions carry the
  "not affiliated with Cognition AI" disclaimer — keep it.
