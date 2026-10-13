# Manual Fallback Diagnostics

Use this file **only when `discover-agent-storage.ps1` cannot run at all** —
for example when Constrained Language Mode, AppLocker or WDAC block `.ps1`
execution entirely. Every command below is a single line you paste into an
interactive `powershell.exe` window (Windows PowerShell 5.1, no admin, no
script file). All commands are read-only and use only built-in cmdlets
(`Test-Path`, `Get-ChildItem`, `Get-Command`, `$env:` vars).

**Privacy:** each command prints only `yes`/`no`, a count, a version line or a
path. Before pasting output back, make sure your real username does not
appear — run the path-redaction helper (last command) or eyeball the output.
If a path printed by your own variation contains the username, replace it
with `~` before sharing.

## Commands

### 1. Copilot CLI session-state dirs (exists + counts, all bases)

```powershell
@(@('home', "$env:USERPROFILE\.copilot\session-state"), @('COPILOT_DIR', $(if ($env:COPILOT_DIR) { "$env:COPILOT_DIR\session-state" })), @('COPILOT_HOME', $(if ($env:COPILOT_HOME) { "$env:COPILOT_HOME\session-state" }))) | ForEach-Object { if (-not $_[1]) { "$($_[0]): env-unset" } elseif (Test-Path $_[1]) { "$($_[0]): dirs=" + @(Get-ChildItem $_[1] -Directory -ErrorAction SilentlyContinue).Count + ' flat=' + @(Get-ChildItem $_[1] -File -Filter '*.jsonl' -ErrorAction SilentlyContinue).Count } else { "$($_[0]): no" } }
```

Reports per base (`home`, `COPILOT_DIR`, `COPILOT_HOME`): `dirs=N` session
subdirectories and `flat=N` loose `*.jsonl` session files, `no` (missing)
or `env-unset`.

### 2. Chronicle session-store.db existence

```powershell
if (Test-Path "$env:USERPROFILE\.copilot\session-store.db") { 'yes' } else { 'no' }
```

Reports `yes` if the Copilot CLI Chronicle database exists.

### 3. Codex CLI rollout sessions + archived (exists + file counts)

```powershell
@(@('home-sessions', "$env:USERPROFILE\.codex\sessions"), @('home-archived', "$env:USERPROFILE\.codex\archived_sessions"), @('CODEX_HOME', $(if ($env:CODEX_HOME) { "$env:CODEX_HOME\sessions" })), @('CODEX_SESSIONS_DIR', $env:CODEX_SESSIONS_DIR)) | ForEach-Object { if (-not $_[1]) { "$($_[0]): env-unset" } elseif (Test-Path $_[1]) { "$($_[0]): rollouts=" + @(Get-ChildItem $_[1] -Recurse -Filter 'rollout-*.jsonl' -File -ErrorAction SilentlyContinue).Count } else { "$($_[0]): no" } }
```

Reports `rollouts=N` per base (`home-sessions`, `home-archived`,
`CODEX_HOME`, `CODEX_SESSIONS_DIR`), `no` or `env-unset`.

### 4. VS Code workspaceStorage chatSessions dirs (exists + count)

```powershell
if (Test-Path "$env:APPDATA\Code\User\workspaceStorage") { 'yes ' + @(Get-ChildItem "$env:APPDATA\Code\User\workspaceStorage" -Directory -ErrorAction SilentlyContinue | ForEach-Object { Join-Path $_.FullName 'chatSessions' } | Where-Object { Test-Path $_ }).Count } else { 'no' }
```

Reports `yes N` where N = workspace hash dirs containing a `chatSessions` folder, or `no`. For Insiders, replace `Code` with `Code - Insiders` in the path.

### 5. copilot / codex / code binary presence

```powershell
'copilot: ' + $(if (Get-Command copilot -ErrorAction SilentlyContinue) { 'yes' } else { 'no' }) + '  codex: ' + $(if (Get-Command codex -ErrorAction SilentlyContinue) { 'yes' } else { 'no' }) + '  code: ' + $(if (Get-Command code -ErrorAction SilentlyContinue) { 'yes' } else { 'no' })
```

Reports `yes`/`no` per binary found on PATH. Add `--version` probes manually if needed (`copilot --version`, `codex --version`).

### 6. Copilot extensions installed in VS Code

```powershell
code --list-extensions | Select-String -Pattern 'copilot'
```

Prints only extension IDs containing `copilot` (case-insensitive), e.g. `github.copilot-chat`. Empty output = none found (or `code` not on PATH).

### 7. VS Code globalStorage state.vscdb existence

```powershell
if (Test-Path "$env:APPDATA\Code\User\globalStorage\state.vscdb") { 'yes' } else { 'no' }
```

Reports `yes` if the VS Code state database exists (its schema is NOT inspected here — see note below).

### 8. Print a redacted (logical) path for sharing

```powershell
"$env:USERPROFILE\.copilot\session-store.db" -replace ($env:USERPROFILE -replace '\\', '\\'), '~'
```

Prints the path with your profile replaced by `~` (e.g. `~\.copilot\session-store.db`). Reuse the same `-replace` pattern to redact any other path before pasting it anywhere.

## SQLite schema — not possible as a CLM one-liner

There is **no safe one-line way** to dump `state.vscdb` / `session-store.db`
table and column names under Constrained Language Mode (no `Add-Type`, no
.NET `sqlite` assemblies, and `.exe` helpers may also be blocked). Options:

- If `sqlite3.exe` is allowed to run:
  `sqlite3 -readonly "$env:APPDATA\Code\User\globalStorage\state.vscdb" ".tables"`
  then `PRAGMA table_info(<name>);` per table — share names only, never rows.
- Otherwise run `discover-agent-storage.py` (Python sibling of the .ps1) or
  any standalone SQLite browser on a **copy** of the DB, and report table /
  column names only.
