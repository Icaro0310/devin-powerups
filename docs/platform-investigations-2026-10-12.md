# Platform investigations — Antigravity, Zed, JetBrains (Wave 9)

Date: 2026-10-12
Method: public documentation + ecosystem code inspection. No local installs —
neither Antigravity nor Zed is installed on the audit machine, so installation
claims rely on vendor documentation and third-party install reports, flagged
below as `[docs]` vs `[verified]`.

## TL;DR

All three platforms are reachable today **without new product code**:

| Platform | Channel | Verdict |
|---|---|---|
| Antigravity IDE | `.vsix` / Open VSX | Covered by Wave 3 — publish to Open VSX and Antigravity gets it free |
| Antigravity MCP | `mcp_config.json` | Works today; curated Store submission is external (forum review) |
| Antigravity Skills | `.agents/skills/` | Works today — Wave 1 skills are already in the right layout |
| Zed | ACP custom agent | `devin acp` direct — config only |
| Zed | MCP servers | `context_servers` / Agent Settings — config only |
| JetBrains | `~/.jetbrains/acp.json` | `devin acp` direct — config only (ACP beta in 25.3) |
| JetBrains | AI Assistant MCP | `mcpServers` JSON config — our MCP servers work today |

The only real gaps: a bridge-as-ACP-server mode if we want the policy gate in
front of Zed/JetBrains agents (new spec, Rule-1 sensitive), and the Antigravity
MCP Store listing (external curated process).

---

## 9.1 Google Antigravity

### `.vsix` / Open VSX — `[docs]` verified

Antigravity IDE is a VS Code fork and accepts third-party extensions:

- In-IDE: `Ctrl+Shift+P` → "Extensions: Install from VSIX…"
- CLI: `antigravity-ide --install-extension <pkg>-<ver>.vsix`
- Its default extension registry is **Open VSX** (confirmed by multiple
  third-party extensions publishing install instructions for Antigravity via
  Open VSX: e.g. JetBrains ReSharper, nextcortex extensions).

**Consequence:** Wave 3's dual publish (`vsce` + `ovsx`) covers Antigravity
for free. No separate artifact needed.

### MCP Store — curated, external

- The built-in MCP Store is a **curated** catalog.
- Submission process [docs]: post on the Google AI Developers Forum
  (`discuss.ai.google.dev`) tagged `[MCP Store]` — the tag kicks off official
  review. There is no self-service publish flow found in public docs.
- Register as **🔴 external** in the backlog: we can post the request when
  ready, but approval timing is Google's.

**Works today without the store:** custom servers via
`~/.gemini/config/mcp_config.json` or workspace `.agents/mcp_config.json`:

```json
{
  "mcpServers": {
    "devin-memory": { "command": "devin-memory-mcp" }
  }
}
```

Every MCP server the ecosystem publishes is installable in Antigravity right
now through this path. Documented for users in each package README (Wave 1
MCP "Add Your Own" section covers it — same stanza, different file path).

### Skills — `[docs]` verified

`npx skills add` supports Antigravity natively:

- Workspace scope: `.agents/skills/` — **the same layout our Wave 1 skills
  already use**, so a checkout of any ecosystem repo already exposes its
  skills to Antigravity.
- Global scope: `~/.gemini/antigravity/skills/`.

⚠️ Known upstream bug (vercel-labs/skills#633): Antigravity IDE does **not**
discover symlinked skills in the global dir — only real directories. Advise
`npx skills add <repo> --agent antigravity --copy` (or plain `cp -r`) for
global installs until fixed.

## 9.2 Zed

### ACP — architectural finding

Zed is an ACP **client**. Our `devin-bridge` is also an ACP **client**
(`packages/bridge/src/acp-client.js`; bin commands: `new`, `resume`,
`prompt`, `sessions`, `policy` — no `serve` mode). Pointing the bridge *at*
Zed is architecturally inverted: Zed exposes no ACP server socket for the
bridge to connect to.

What actually works today:

```jsonc
// ~/.config/zed/settings.json
{
  "agent_servers": {
    "Devin": {
      "type": "custom",
      "command": "devin",
      "args": ["acp"]
    }
  }
}
```

Zed then spawns and drives `devin acp` directly — no ecosystem code required.
(Requires the Devin CLI installed and signed in on the machine.)

**If we want the bridge's policy gate in front** of Zed→`devin acp`, the
bridge would need an ACP-*server* mode that proxies and enforces
`policy.json`. That is a new feature, Rule-1 sensitive (it sits in the
spawn/prompt path), and needs its own spec — registered in BACKLOG as
needs-spec, not built in this wave.

### MCP / Skills

- MCP servers: Agent Settings → MCP Servers → Add Local Server, or
  `context_servers` in `settings.json`. Our stdio MCP servers
  (`devin-memory-mcp`, `poordjaevin-mcp`, …) work via this path today.
- Skills: Zed reads AGENTS.md-style context; no dedicated skill dir. Codex
  `AGENTS.md` (Wave 1) covers instructions; skills are loadable through MCP
  prompts where the server advertises them.

## 9.3 JetBrains

### `~/.jetbrains/acp.json` — `[docs]` verified

ACP support is in the 25.3 release-candidate IDEs (JetBrains blog,
Dec 2025). Format confirmed by the official AI Assistant docs:

```jsonc
// ~/.jetbrains/acp.json — created by AI Chat → Add Custom Agent
{
  "default_mcp_settings": {
    "use_custom_mcp": true,
    "use_idea_mcp": false
  },
  "agent_servers": {
    "Devin": {
      "command": "devin",
      "args": ["acp"],
      "env": {}
    }
  }
}
```

Config only — zero code. Same caveat as Zed: this points JetBrains directly
at `devin acp`; the bridge policy layer would need the ACP-server mode above.

### MCP servers — `[docs]` verified

Settings → Tools → AI Assistant → Model Context Protocol → Add, JSON:

```json
{
  "mcpServers": {
    "devin-memory": { "command": "devin-memory-mcp" },
    "poordjaevin":  { "command": "poordjaevin-mcp" }
  }
}
```

Claude Desktop configs can also be imported directly ("Import from Claude"),
so the same stanza serves both.

## Evidence log

- Antigravity MCP docs: `antigravity.google/docs/mcp/` — custom servers via
  `mcp_config.json`; Store = built-in curated catalog.
- Antigravity store submission: `discuss.ai.google.dev` — `[MCP Store]` tag
  triggers official review (Sitelemetry thread, Supabase thread).
- Antigravity vsix: multiple third-party extension pages document
  "Install from VSIX" + `antigravity-ide --install-extension`; JetBrains'
  own ReSharper docs instruct Open VSX install inside Antigravity IDE.
- Antigravity skills: vercel-labs/skills README agent table
  (`antigravity` → `.agents/skills/`, global `~/.gemini/antigravity/skills/`);
  symlink bug: vercel-labs/skills issue #633.
- Zed external agents: `zed.dev/docs/ai/agent-settings` — `agent_servers`,
  `"type": "custom"`. ACP extensions deprecated → migrated to ACP registry
  (zed-industries/zed@c84c22d).
- JetBrains ACP: `jetbrains.com/help/ai-assistant/acp.html` — acp.json
  location and schema; blog post Dec 2025 (beta in 25.3 RC).
- JetBrains MCP: `jetbrains.com/help/ai-assistant/mcp.html` — JSON
  `mcpServers` config, Claude import.
- Bridge is client-only: `packages/bridge/bin/devin-bridge.js` command list —
  `new`, `resume`, `prompt`, `sessions`, `policy`; no `serve`/`acp-server`.

## Follow-ups registered in BACKLOG

- Antigravity MCP Store listing request (🔴 external — forum review).
- `devin-bridge` ACP-server mode spec (enables policy-gated Zed/JetBrains —
  needs-spec, Rule 1).
- Per-package README snippets for Antigravity `mcp_config.json` and Zed/JB
  `agent_servers` — fold into Wave 1 MCP "Add Your Own" sections.
