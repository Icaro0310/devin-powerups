<#
.SYNOPSIS
    Read-only discovery of where Copilot VS Code Chat, Codex CLI and Copilot CLI
    store session data on this machine. Emits a privacy-safe JSON inventory to
    STDOUT that the owner can paste back.

.DESCRIPTION
    Owner-run diagnostic (NOT product code). Windows PowerShell 5.1 compatible,
    no admin rights required. Surfaces inspected:

      * VS Code Copilot Chat: <AppData>\Code\User\workspaceStorage\<hash>\
        chatSessions (+ GitHub.copilot-chat / github.copilot-chat variants),
        globalStorage\emptyWindowChatSessions, globalStorage\github.copilot-chat,
        globalStorage\state.vscdb (SQLite schema only). Same paths under
        "Code - Insiders". WSL presence is flagged, never entered.
      * Codex CLI: ~\.codex\sessions\YYYY\MM\DD\rollout-*.jsonl and
        ~\.codex\archived_sessions (+ $CODEX_HOME, $CODEX_SESSIONS_DIR).
      * Copilot CLI: ~\.copilot\session-state\<id>\{events.jsonl,workspace.yaml}
        and flat <id>.jsonl, legacy ~\.copilot\history-session-state,
        Chronicle session-store.db, vscode.session.metadata.cache.json and
        shipped session-events schemas under ~\.copilot\pkg
        (+ $COPILOT_DIR, $COPILOT_HOME). SQLite: table and column NAMES only,
        never rows.

    PRIVACY (hard rules): all emitted paths are logical (~, <USER>,
    <VSCODE_USER>, <VSCODE_INSIDERS_USER>); no file contents, session titles,
    project names, workspace.yaml/json contents or DB row data are read or
    emitted. Counts only: files by extension, size buckets, day-granularity
    mtimes, truncated-tail counts, table/column names.

    READ-ONLY: nothing on disk is created or modified, except (a) a temporary
    SQLite copy under %TEMP% when the live DB cannot be opened - deleted
    immediately, and (b) -OutFile when explicitly requested. -SelfTest writes
    fixture files under %TEMP% only and removes them.

.PARAMETER OutFile
    Optional. Write the emitted report (header + JSON) to this path as UTF-8.

.PARAMETER Detailed
    Increase nested enumeration depth from 4 to 8 levels.

.PARAMETER Root
    Test hook: treat <Root>\.copilot, <Root>\.codex, <Root>\vscode-user and
    <Root>\vscode-insiders-user as the per-user roots. Used by -SelfTest.

.PARAMETER SelfTest
    Run internal self-tests instead of real discovery; exit code 0 iff all pass.

.EXAMPLE
    powershell -NoProfile -File discover-agent-storage.ps1

.EXAMPLE
    powershell -NoProfile -File discover-agent-storage.ps1 -OutFile "$env:TEMP\agent-inventory.json"
#>
#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$SelfTest,
    [switch]$Detailed,
    [string]$OutFile,
    [string]$Root
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Continue'
# Pre-create so reads of $LASTEXITCODE are safe under StrictMode before the
# first native command ever runs in this session.
$global:LASTEXITCODE = 0
$script:DiscoveryErrors = New-Object System.Collections.ArrayList

# ---------------------------------------------------------------- helpers ---

function ConvertTo-LogicalPath {
    param([string]$Path)
    if ([string]::IsNullOrEmpty($Path)) { return $Path }
    $p = $Path
    if (-not [string]::IsNullOrEmpty($env:APPDATA)) {
        $p = $p -replace [regex]::Escape((Join-Path $env:APPDATA 'Code - Insiders\User')), '<VSCODE_INSIDERS_USER>'
        $p = $p -replace [regex]::Escape((Join-Path $env:APPDATA 'Code\User')),           '<VSCODE_USER>'
    }
    if (-not [string]::IsNullOrEmpty($env:USERPROFILE)) { $p = $p -replace [regex]::Escape($env:USERPROFILE), '~' }
    if (-not [string]::IsNullOrEmpty($env:HOME))        { $p = $p -replace [regex]::Escape($env:HOME), '~' }
    if (-not [string]::IsNullOrEmpty($env:USERNAME))    { $p = $p -replace [regex]::Escape($env:USERNAME), '<USER>' }
    $p = $p -replace '\\', '/'
    return $p
}

function Add-DiscoveryError {
    param([string]$Path, [string]$Kind)
    [void]$script:DiscoveryErrors.Add(([ordered]@{ path = (ConvertTo-LogicalPath $Path); kind = $Kind }))
}

function Get-EnumErrorKind {
    param($ErrRecord)
    if ($null -eq $ErrRecord) { return 'enum-error' }
    $id = ''
    if ($ErrRecord.FullyQualifiedErrorId) { $id = [string]$ErrRecord.FullyQualifiedErrorId }
    if ($id -match 'Unauthorized|AccessDenied|Permission') { return 'access-denied' }
    if ($ErrRecord.Exception -is [System.UnauthorizedAccessException]) { return 'access-denied' }
    return 'enum-error'
}

function Get-SizeBucket {
    param([long]$Length)
    if ($Length -lt 1KB)  { return '<1KB' }
    if ($Length -lt 64KB) { return '1-64KB' }
    if ($Length -lt 1MB)  { return '64KB-1MB' }
    if ($Length -gt 1MB)  { return '>1MB' }
    return '<OTHER>'
}

function New-SizeBuckets {
    return [ordered]@{ '<1KB' = 0; '1-64KB' = 0; '64KB-1MB' = 0; '>1MB' = 0; '<OTHER>' = 0 }
}

function Test-TruncatedTail {
    # $true when a non-empty file's last byte is not a newline. Never reads
    # content beyond the final byte; opens with ReadWrite share (read-only role).
    param([string]$FilePath)
    $fs = $null
    try {
        $fs = New-Object System.IO.FileStream($FilePath, [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        if ($fs.Length -le 0) { return $false }
        [void]$fs.Seek(-1, [System.IO.SeekOrigin]::End)
        return ($fs.ReadByte() -ne 10)
    } catch [System.UnauthorizedAccessException] {
        Add-DiscoveryError -Path $FilePath -Kind 'access-denied'
        return $false
    } catch {
        return $false
    } finally {
        if ($null -ne $fs) { $fs.Close() }
    }
}

function Get-DirInventory {
    # Counts-only inventory of a directory tree, depth-limited. Emits nothing
    # per-file; aggregates ext counts, size buckets, day-granularity mtimes and
    # per-directory truncated-tail counts (dirs keyed by logical path).
    param([string]$Path, [int]$MaxDepth, [string]$Filter)
    $inv = [ordered]@{
        path               = ConvertTo-LogicalPath $Path
        exists             = $false
        state              = 'not-found'
        files              = 0
        dirs               = 0
        other              = 0
        by_ext             = [ordered]@{}
        size_buckets       = New-SizeBuckets
        mtime_earliest_day = ''
        mtime_latest_day   = ''
        truncated_tail     = [ordered]@{}
    }
    if ([string]::IsNullOrEmpty($Path) -or -not (Test-Path -LiteralPath $Path)) { return $inv }
    $inv.exists = $true
    $inv.state  = 'present'
    $queue = New-Object System.Collections.Queue
    $queue.Enqueue(@($Path, 0))
    while ($queue.Count -gt 0) {
        $pair = $queue.Dequeue()
        $dir  = [string]$pair[0]
        $lvl  = [int]$pair[1]
        $ev   = $null
        $items = @(Get-ChildItem -LiteralPath $dir -Force -ErrorAction SilentlyContinue -ErrorVariable ev)
        if ($ev) { foreach ($e in $ev) { Add-DiscoveryError -Path $dir -Kind (Get-EnumErrorKind $e) } }
        foreach ($it in $items) {
            if ($it.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
                $inv.other = $inv.other + 1   # symlink/junction: count, never follow
                continue
            }
            if ($it.PSIsContainer) {
                $inv.dirs = $inv.dirs + 1
                if ($lvl -lt $MaxDepth) { $queue.Enqueue(@($it.FullName, ($lvl + 1))) }
                continue
            }
            if (-not [string]::IsNullOrEmpty($Filter) -and $it.Name -notlike $Filter) { continue }
            $inv.files = $inv.files + 1
            $ext = $it.Extension
            if ([string]::IsNullOrEmpty($ext)) { $ext = '<NOEXT>' } else { $ext = $ext.ToLowerInvariant() }
            if ($inv.by_ext.Contains($ext)) { $inv.by_ext[$ext] = $inv.by_ext[$ext] + 1 } else { $inv.by_ext[$ext] = 1 }
            $b = Get-SizeBucket $it.Length
            $inv.size_buckets[$b] = $inv.size_buckets[$b] + 1
            $day = $it.LastWriteTimeUtc.ToString('yyyy-MM-dd')
            if ($inv.mtime_earliest_day -eq '' -or $day -lt $inv.mtime_earliest_day) { $inv.mtime_earliest_day = $day }
            if ($inv.mtime_latest_day   -eq '' -or $day -gt $inv.mtime_latest_day)   { $inv.mtime_latest_day   = $day }
            if ($it.Length -gt 0 -and (Test-TruncatedTail $it.FullName)) {
                $ld = ConvertTo-LogicalPath $it.DirectoryName
                if ($inv.truncated_tail.Contains($ld)) { $inv.truncated_tail[$ld] = $inv.truncated_tail[$ld] + 1 } else { $inv.truncated_tail[$ld] = 1 }
            }
        }
    }
    return $inv
}

function Merge-Inventories {
    # Merge several Get-DirInventory results into one aggregate (dirs_scanned,
    # dirs_present, files, by_ext, size_buckets, day range, truncated tails).
    param([object[]]$Items)
    $m = [ordered]@{
        dirs_scanned       = $Items.Count
        dirs_present       = 0
        files              = 0
        by_ext             = [ordered]@{}
        size_buckets       = New-SizeBuckets
        mtime_earliest_day = ''
        mtime_latest_day   = ''
        truncated_tail     = [ordered]@{}
    }
    foreach ($it in $Items) {
        if ($null -eq $it -or -not $it.exists) { continue }
        $m.dirs_present = $m.dirs_present + 1
        $m.files = $m.files + $it.files
        foreach ($k in $it.by_ext.Keys) {
            if ($m.by_ext.Contains($k)) { $m.by_ext[$k] = $m.by_ext[$k] + $it.by_ext[$k] } else { $m.by_ext[$k] = $it.by_ext[$k] }
        }
        foreach ($k in $it.size_buckets.Keys) {
            $m.size_buckets[$k] = $m.size_buckets[$k] + $it.size_buckets[$k]
        }
        if ($it.mtime_earliest_day -ne '' -and ($m.mtime_earliest_day -eq '' -or $it.mtime_earliest_day -lt $m.mtime_earliest_day)) { $m.mtime_earliest_day = $it.mtime_earliest_day }
        if ($it.mtime_latest_day   -ne '' -and ($m.mtime_latest_day   -eq '' -or $it.mtime_latest_day   -gt $m.mtime_latest_day))   { $m.mtime_latest_day   = $it.mtime_latest_day }
        foreach ($k in $it.truncated_tail.Keys) {
            if ($m.truncated_tail.Contains($k)) { $m.truncated_tail[$k] = $m.truncated_tail[$k] + $it.truncated_tail[$k] } else { $m.truncated_tail[$k] = $it.truncated_tail[$k] }
        }
    }
    return $m
}

# --------------------------------------------------------------- sqlite -----

function Get-SqliteExe {
    foreach ($n in @('sqlite3.exe', 'sqlite3')) {
        if (Get-Command $n -ErrorAction SilentlyContinue) { return $n }
    }
    return $null
}

function Get-SqliteSchema {
    # Returns @{status; tables=@{name='col1,col2'}} - names only, never values.
    # Prefers `sqlite3 -readonly`; on failure copies the DB to %TEMP%, reads the
    # copy and deletes it (the original is never written to). Without any engine
    # reports 'sqlite-unavailable'.
    param([string]$DbPath)
    $res = [ordered]@{ status = 'sqlite-unavailable'; tables = [ordered]@{} }
    $qTables = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
    $exe = Get-SqliteExe
    if ($null -ne $exe) {
        $src = $DbPath
        $tmp = $null
        $names = @()
        $ok = $false
        try {
            $names = @(& $exe '-readonly' $src $qTables 2>$null)
            if ($LASTEXITCODE -eq 0) { $ok = $true }
        } catch { $ok = $false }
        if (-not $ok) {
            try {
                $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ('dast-' + [guid]::NewGuid().ToString('N') + '.db')
                Copy-Item -LiteralPath $DbPath -Destination $tmp -Force -ErrorAction Stop
                $src = $tmp
                $names = @(& $exe '-readonly' $src $qTables 2>$null)
                if ($LASTEXITCODE -eq 0) { $ok = $true }
            } catch { $ok = $false }
        }
        if ($ok) {
            $res.status = 'ok'
            foreach ($t in $names) {
                if ([string]::IsNullOrWhiteSpace([string]$t)) { continue }
                $tn = ([string]$t).Trim()
                $cols = @(& $exe '-readonly' $src ('PRAGMA table_info("' + $tn.Replace('"', '""') + '");') 2>$null)
                $colNames = @()
                foreach ($cl in $cols) {
                    $parts = ([string]$cl) -split '\|'
                    if ($parts.Count -ge 2) { $colNames += $parts[1] }
                }
                $res.tables[$tn] = ($colNames -join ',')
            }
        } else {
            $res.status = 'error'
            Add-DiscoveryError -Path $DbPath -Kind 'sqlite-read-failed'
        }
        if ($null -ne $tmp) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
        return $res
    }
    # Fallback: System.Data.SQLite from the GAC (rare). Read via temp copy so
    # the live DB is never opened for write; copy deleted in finally.
    $loaded = $false
    try { Add-Type -AssemblyName 'System.Data.SQLite' -ErrorAction Stop; $loaded = $true } catch { $loaded = $false }
    if (-not $loaded) { return $res }
    $tmp2 = Join-Path ([System.IO.Path]::GetTempPath()) ('dast-' + [guid]::NewGuid().ToString('N') + '.db')
    try {
        Copy-Item -LiteralPath $DbPath -Destination $tmp2 -Force -ErrorAction Stop
        $conn = New-Object 'System.Data.SQLite.SQLiteConnection' -ArgumentList ('Data Source=' + $tmp2 + ';Read Only=True;')
        $conn.Open()
        try {
            $tnames = @()
            $cmd = $conn.CreateCommand()
            $cmd.CommandText = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            $rd = $cmd.ExecuteReader()
            while ($rd.Read()) { $tnames += $rd.GetString(0) }
            $rd.Close(); $cmd.Dispose()
            foreach ($t in $tnames) {
                $c2 = $conn.CreateCommand()
                $c2.CommandText = 'PRAGMA table_info("' + $t.Replace('"', '""') + '")'
                $r2 = $c2.ExecuteReader()
                $cn = @()
                while ($r2.Read()) { $cn += $r2.GetString(1) }
                $r2.Close(); $c2.Dispose()
                $res.tables[$t] = ($cn -join ',')
            }
            $res.status = 'ok'
        } finally { $conn.Close(); $conn.Dispose() }
    } catch {
        $res.status = 'error'
        Add-DiscoveryError -Path $DbPath -Kind 'sqlite-read-failed'
    } finally {
        Remove-Item -LiteralPath $tmp2 -Force -ErrorAction SilentlyContinue
    }
    return $res
}

function Get-DbReport {
    param([string]$Path, [string]$Source)
    $r = [ordered]@{
        path          = ConvertTo-LogicalPath $Path
        source        = $Source
        exists        = $false
        state         = 'not-found'
        size_bucket   = ''
        sqlite_status = 'not-attempted'
        tables        = [ordered]@{}
    }
    if ([string]::IsNullOrEmpty($Path) -or -not (Test-Path -LiteralPath $Path)) { return $r }
    $r.exists = $true
    $r.state  = 'present'
    $ev = $null
    $fi = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue -ErrorVariable ev
    if ($ev) { foreach ($e in $ev) { Add-DiscoveryError -Path $Path -Kind (Get-EnumErrorKind $e) } }
    if ($fi) { $r.size_bucket = Get-SizeBucket $fi.Length }
    $sc = Get-SqliteSchema -DbPath $Path
    $r.sqlite_status = $sc.status
    $r.tables = $sc.tables
    return $r
}

# -------------------------------------------------------------- surfaces ----

function Get-VSCodeInstallReport {
    param([string]$Install, [string]$UserDir, [int]$MaxDepth)
    $r = [ordered]@{
        install       = $Install
        flavor        = 'windows-appdata'
        user_dir      = ConvertTo-LogicalPath $UserDir
        present       = $false
        state         = 'not-found'
        workspace_dirs = 0
        workspace_storage_overview = $null
        chat_session_dirs = 0
        chat_sessions = $null
        empty_window_sessions = $null
        transferred_window_sessions = $null
        copilot_chat_global = $null
        state_db      = $null
    }
    if ([string]::IsNullOrEmpty($UserDir) -or -not (Test-Path -LiteralPath $UserDir)) { return $r }
    $r.present = $true
    $r.state = 'present'
    $ws = Join-Path $UserDir 'workspaceStorage'
    $r.workspace_storage_overview = Get-DirInventory -Path $ws -MaxDepth 2 -Filter ''
    $chatDirs = @()
    if (Test-Path -LiteralPath $ws) {
        $ev = $null
        $hashDirs = @(Get-ChildItem -LiteralPath $ws -Directory -Force -ErrorAction SilentlyContinue -ErrorVariable ev)
        if ($ev) { foreach ($e in $ev) { Add-DiscoveryError -Path $ws -Kind (Get-EnumErrorKind $e) } }
        $r.workspace_dirs = $hashDirs.Count
        foreach ($hd in $hashDirs) {
            foreach ($sub in @(@('chatSessions'), @('GitHub.copilot-chat', 'chatSessions'), @('github.copilot-chat', 'chatSessions'))) {
                $p = $hd.FullName
                foreach ($seg in $sub) { $p = Join-Path $p $seg }
                if (Test-Path -LiteralPath $p) { $chatDirs += $p }
            }
        }
    }
    $r.chat_session_dirs = $chatDirs.Count
    $invs = @()
    foreach ($cd in $chatDirs) { $invs += Get-DirInventory -Path $cd -MaxDepth $MaxDepth -Filter '' }
    $r.chat_sessions = Merge-Inventories -Items $invs
    $gs = Join-Path $UserDir 'globalStorage'
    $r.empty_window_sessions = Get-DirInventory -Path (Join-Path $gs 'emptyWindowChatSessions') -MaxDepth $MaxDepth -Filter ''
    $r.transferred_window_sessions = Get-DirInventory -Path (Join-Path $gs 'transferredChatSessions') -MaxDepth $MaxDepth -Filter ''
    $r.copilot_chat_global   = Get-DirInventory -Path (Join-Path $gs 'github.copilot-chat')        -MaxDepth $MaxDepth -Filter ''
    $r.state_db              = Get-DbReport -Path (Join-Path $gs 'state.vscdb') -Source 'local'
    return $r
}

function Get-CopilotSessionStateReport {
    # Per-dir presence counts only; session dir names (UUIDs) never emitted.
    param([string]$Path, [string]$Source)
    $r = [ordered]@{
        path           = ConvertTo-LogicalPath $Path
        source         = $Source
        exists         = $false
        state          = 'not-found'
        session_dirs   = 0
        flat_jsonl_files = 0
        other_entries  = 0
        file_presence  = [ordered]@{ 'events.jsonl' = 0; 'workspace.yaml' = 0 }
        size_buckets   = New-SizeBuckets
        mtime_earliest_day = ''
        mtime_latest_day   = ''
        truncated_tail = [ordered]@{ '<session-dir>' = 0 }
    }
    if ([string]::IsNullOrEmpty($Path) -or -not (Test-Path -LiteralPath $Path)) { return $r }
    $r.exists = $true
    $r.state  = 'present'
    $ev = $null
    $ents = @(Get-ChildItem -LiteralPath $Path -Force -ErrorAction SilentlyContinue -ErrorVariable ev)
    if ($ev) { foreach ($e in $ev) { Add-DiscoveryError -Path $Path -Kind (Get-EnumErrorKind $e) } }
    foreach ($e in $ents) {
        if (-not $e.PSIsContainer -or ($e.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
            $r.other_entries = $r.other_entries + 1
            if (-not $e.PSIsContainer -and $e.Name -match '^[0-9a-fA-F-]{16,}\.jsonl$') {
                $r.flat_jsonl_files = $r.flat_jsonl_files + 1  # flat <uuid>.jsonl session layout
            }
            continue
        }
        $r.session_dirs = $r.session_dirs + 1
        $trunc = $false
        foreach ($fn in @('events.jsonl', 'workspace.yaml')) {
            $fp = Join-Path $e.FullName $fn
            if (-not (Test-Path -LiteralPath $fp)) { continue }
            $r.file_presence[$fn] = $r.file_presence[$fn] + 1
            $ev2 = $null
            $fi = Get-Item -LiteralPath $fp -Force -ErrorAction SilentlyContinue -ErrorVariable ev2
            if ($ev2) { foreach ($x in $ev2) { Add-DiscoveryError -Path $fp -Kind (Get-EnumErrorKind $x) } }
            if ($null -eq $fi) { continue }
            $r.size_buckets[(Get-SizeBucket $fi.Length)] = $r.size_buckets[(Get-SizeBucket $fi.Length)] + 1
            $day = $fi.LastWriteTimeUtc.ToString('yyyy-MM-dd')
            if ($r.mtime_earliest_day -eq '' -or $day -lt $r.mtime_earliest_day) { $r.mtime_earliest_day = $day }
            if ($r.mtime_latest_day   -eq '' -or $day -gt $r.mtime_latest_day)   { $r.mtime_latest_day   = $day }
            if ($fi.Length -gt 0 -and (Test-TruncatedTail $fp)) { $trunc = $true }
        }
        if ($trunc) { $r.truncated_tail['<session-dir>'] = $r.truncated_tail['<session-dir>'] + 1 }
    }
    return $r
}

function Get-LegacyDirReport {
    param([string]$Path, [string]$Source)
    $r = [ordered]@{
        path = ConvertTo-LogicalPath $Path; source = $Source
        exists = $false; state = 'not-found'; dir_count = 0; other_entries = 0
    }
    if ([string]::IsNullOrEmpty($Path) -or -not (Test-Path -LiteralPath $Path)) { return $r }
    $r.exists = $true
    $r.state  = 'present'
    $ev = $null
    $ents = @(Get-ChildItem -LiteralPath $Path -Force -ErrorAction SilentlyContinue -ErrorVariable ev)
    if ($ev) { foreach ($e in $ev) { Add-DiscoveryError -Path $Path -Kind (Get-EnumErrorKind $e) } }
    foreach ($e in $ents) {
        if ($e.PSIsContainer) { $r.dir_count = $r.dir_count + 1 } else { $r.other_entries = $r.other_entries + 1 }
    }
    return $r
}

function Get-FileProbe {
    # Existence + size bucket + mtime day for one known file. Never content.
    param([string]$Path, [string]$Source)
    $r = [ordered]@{ path = ConvertTo-LogicalPath $Path; source = $Source; exists = $false }
    if ([string]::IsNullOrEmpty($Path) -or -not (Test-Path -LiteralPath $Path)) { return $r }
    $r.exists = $true
    $ev = $null
    $fi = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue -ErrorVariable ev
    if ($ev) { foreach ($x in $ev) { Add-DiscoveryError -Path $Path -Kind (Get-EnumErrorKind $x) } }
    if ($null -ne $fi) {
        $r.size_bucket = Get-SizeBucket $fi.Length
        $r.mtime_day   = $fi.LastWriteTimeUtc.ToString('yyyy-MM-dd')
    }
    return $r
}

function Get-SchemaProbe {
    # Directory inventory + count of shipped session-events.schema.json files.
    param([string]$Path, [string]$Source, [int]$MaxDepth)
    $r = Get-DirInventory -Path $Path -MaxDepth $MaxDepth -Filter ''
    $r.source = $Source
    $r.session_events_schema_files = 0
    if (-not [string]::IsNullOrEmpty($Path) -and (Test-Path -LiteralPath $Path)) {
        $ev = $null
        $hits = @(Get-ChildItem -LiteralPath $Path -Recurse -Filter 'session-events.schema.json' -File -Force -ErrorAction SilentlyContinue -ErrorVariable ev)
        if ($ev) { foreach ($x in $ev) { Add-DiscoveryError -Path $Path -Kind (Get-EnumErrorKind $x) } }
        $r.session_events_schema_files = $hits.Count
    }
    return $r
}

# ---------------------------------------------------------------- probes ----

function Get-ToolVersion {
    param([string]$Name)
    $c = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $c) { return 'not-found' }
    $line = ''
    try { $line = & $Name '--version' 2>$null | Select-Object -First 1 } catch { $line = '' }
    if ([string]::IsNullOrWhiteSpace([string]$line)) { return 'found (no version output)' }
    return ([string]$line).Trim()
}

function Get-CopilotExtensions {
    if (-not (Get-Command code -ErrorAction SilentlyContinue)) { return 'code-not-found' }
    $lines = @()
    try { $lines = @(& code '--list-extensions' 2>$null | Where-Object { $_ -match 'copilot' }) } catch { $lines = @('error') }
    return $lines
}

function Get-DisableAISetting {
    param([string]$SettingsPath)
    if ([string]::IsNullOrEmpty($SettingsPath) -or -not (Test-Path -LiteralPath $SettingsPath)) { return 'settings-file-not-found' }
    $obj = $null
    try { $obj = (Get-Content -LiteralPath $SettingsPath -Raw -ErrorAction Stop) | ConvertFrom-Json -ErrorAction Stop }
    catch { return 'unparseable' }
    $p = $obj.PSObject.Properties['chat.disableAIFeatures']
    if ($null -eq $p) { return 'unset' }
    return $p.Value
}

function Get-ScanRoots {
    param([string]$Root)
    $r = [ordered]@{}
    if (-not [string]::IsNullOrEmpty($Root)) {
        $r.copilot_home         = Join-Path $Root '.copilot'
        $r.codex_home           = Join-Path $Root '.codex'
        $r.vscode_user          = Join-Path $Root 'vscode-user'
        $r.vscode_insiders_user = Join-Path $Root 'vscode-insiders-user'
    } else {
        $up = $env:USERPROFILE
        if ([string]::IsNullOrEmpty($up)) { $up = $env:HOME }
        if ([string]::IsNullOrEmpty($up)) { $up = '~unknown' }
        $r.copilot_home = Join-Path $up '.copilot'
        $r.codex_home   = Join-Path $up '.codex'
        $ad = $env:APPDATA
        if ([string]::IsNullOrEmpty($ad)) { $ad = Join-Path $up 'AppData\Roaming' }
        $r.vscode_user          = Join-Path (Join-Path $ad 'Code') 'User'
        $r.vscode_insiders_user = Join-Path (Join-Path $ad 'Code - Insiders') 'User'
    }
    $r.codex_home_env     = $env:CODEX_HOME
    $r.codex_sessions_env = $env:CODEX_SESSIONS_DIR
    $r.copilot_home_env   = $env:COPILOT_HOME
    $r.copilot_dir_env    = $env:COPILOT_DIR
    return $r
}

function New-EnvNotSetEntry {
    param([string]$EnvName)
    return [ordered]@{ path = '(unset)'; source = ('env:' + $EnvName); exists = $false; state = 'env-not-set' }
}

# -------------------------------------------------------------- discovery ---

function Invoke-Discovery {
    param([string]$Root, [int]$MaxDepth, [switch]$SkipProbes)
    $roots = Get-ScanRoots -Root $Root
    $report = [ordered]@{
        tool                 = 'discover-agent-storage.ps1'
        generated_at_utc_day = (Get-Date).ToUniversalTime().ToString('yyyy-MM-dd')
        host = [ordered]@{
            os             = [System.Environment]::OSVersion.VersionString
            ps_version     = $PSVersionTable.PSVersion.ToString()
            windows_native = 'no'
            in_wsl         = 'no'
            wsl_present    = 'no'
        }
        scan = [ordered]@{
            depth = $MaxDepth
            roots = [ordered]@{
                copilot_home         = ConvertTo-LogicalPath $roots.copilot_home
                codex_home           = ConvertTo-LogicalPath $roots.codex_home
                vscode_user          = ConvertTo-LogicalPath $roots.vscode_user
                vscode_insiders_user = ConvertTo-LogicalPath $roots.vscode_insiders_user
            }
        }
        versions = [ordered]@{}
        surfaces = [ordered]@{}
        errors   = @()
    }
    if ([System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT) { $report.host.windows_native = 'yes' }
    if ($env:WSL_DISTRO_NAME -or $env:WSL_INTEROP) { $report.host.in_wsl = 'yes' }
    if (-not $SkipProbes) {
        $wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
        if ($wsl) {
            try { & wsl.exe '-l' '-q' 2>$null | Out-Null; if ($LASTEXITCODE -eq 0) { $report.host.wsl_present = 'yes' } } catch { }
        }
        $report.versions.code          = Get-ToolVersion 'code'
        $report.versions.code_insiders = Get-ToolVersion 'code-insiders'
        $report.versions.copilot_cli   = Get-ToolVersion 'copilot'
        $report.versions.codex         = Get-ToolVersion 'codex'
        $report.versions.node          = Get-ToolVersion 'node'
        $report.versions.python        = Get-ToolVersion 'python'
        $report.versions.py            = Get-ToolVersion 'py'
        $report.versions.copilot_extensions = @(Get-CopilotExtensions)
    } else {
        foreach ($k in @('code', 'code_insiders', 'copilot_cli', 'codex', 'node', 'python', 'py', 'copilot_extensions')) {
            $report.versions[$k] = 'skipped'
        }
    }
    $report.versions['chat.disableAIFeatures']          = Get-DisableAISetting -SettingsPath (Join-Path $roots.vscode_user 'settings.json')
    $report.versions['chat.disableAIFeatures_insiders'] = Get-DisableAISetting -SettingsPath (Join-Path $roots.vscode_insiders_user 'settings.json')

    # --- surface: VS Code Copilot Chat -------------------------------------
    $report.surfaces.vscode_chat = [ordered]@{
        stable   = Get-VSCodeInstallReport -Install 'code'          -UserDir $roots.vscode_user          -MaxDepth $MaxDepth
        insiders = Get-VSCodeInstallReport -Install 'code-insiders' -UserDir $roots.vscode_insiders_user -MaxDepth $MaxDepth
    }

    # --- surface: Codex CLI -------------------------------------------------
    $cdxSessions = [ordered]@{
        home = Get-DirInventory -Path (Join-Path $roots.codex_home 'sessions') -MaxDepth $MaxDepth -Filter 'rollout-*.jsonl'
    }
    $cdxSessions.home.source = 'home'
    $cdxSessions.home.rollout_files = $cdxSessions.home.files
    if (-not [string]::IsNullOrEmpty($roots.codex_home_env)) {
        $e = Get-DirInventory -Path (Join-Path $roots.codex_home_env 'sessions') -MaxDepth $MaxDepth -Filter 'rollout-*.jsonl'
        $e.source = 'env:CODEX_HOME'
        $e.rollout_files = $e.files
        $cdxSessions.env_CODEX_HOME = $e
    } else {
        $cdxSessions.env_CODEX_HOME = New-EnvNotSetEntry 'CODEX_HOME'
    }
    if (-not [string]::IsNullOrEmpty($roots.codex_sessions_env)) {
        $e = Get-DirInventory -Path $roots.codex_sessions_env -MaxDepth $MaxDepth -Filter 'rollout-*.jsonl'
        $e.source = 'env:CODEX_SESSIONS_DIR'
        $e.rollout_files = $e.files
        $cdxSessions.env_CODEX_SESSIONS_DIR = $e
    } else {
        $cdxSessions.env_CODEX_SESSIONS_DIR = New-EnvNotSetEntry 'CODEX_SESSIONS_DIR'
    }
    $cdxArchived = [ordered]@{
        home = Get-DirInventory -Path (Join-Path $roots.codex_home 'archived_sessions') -MaxDepth $MaxDepth -Filter 'rollout-*.jsonl'
    }
    $cdxArchived.home.source = 'home'
    $cdxArchived.home.rollout_files = $cdxArchived.home.files
    if (-not [string]::IsNullOrEmpty($roots.codex_home_env)) {
        $e = Get-DirInventory -Path (Join-Path $roots.codex_home_env 'archived_sessions') -MaxDepth $MaxDepth -Filter 'rollout-*.jsonl'
        $e.source = 'env:CODEX_HOME'
        $e.rollout_files = $e.files
        $cdxArchived.env_CODEX_HOME = $e
    } else {
        $cdxArchived.env_CODEX_HOME = New-EnvNotSetEntry 'CODEX_HOME'
    }
    $report.surfaces.codex_cli = [ordered]@{
        sessions          = $cdxSessions
        archived_sessions = $cdxArchived
    }

    # --- surface: Copilot CLI ------------------------------------------------
    # Bases: home + each set env var (COPILOT_DIR and COPILOT_HOME both probed;
    # candidates disagree on which the CLI honors).
    $ss = [ordered]@{ home = Get-CopilotSessionStateReport -Path (Join-Path $roots.copilot_home 'session-state') -Source 'home' }
    $chr = [ordered]@{ home = Get-DbReport -Path (Join-Path $roots.copilot_home 'session-store.db') -Source 'home' }
    $leg = [ordered]@{ home = Get-LegacyDirReport -Path (Join-Path $roots.copilot_home 'history-session-state') -Source 'home' }
    $mcc = [ordered]@{ home = Get-FileProbe -Path (Join-Path $roots.copilot_home 'vscode.session.metadata.cache.json') -Source 'home' }
    $sch = [ordered]@{ home = Get-SchemaProbe -Path (Join-Path $roots.copilot_home 'pkg') -Source 'home' -MaxDepth 3 }
    foreach ($pair in @(@('COPILOT_DIR', $roots.copilot_dir_env), @('COPILOT_HOME', $roots.copilot_home_env))) {
        $key = 'env_' + $pair[0]
        if (-not [string]::IsNullOrEmpty($pair[1])) {
            $ss[$key]  = Get-CopilotSessionStateReport -Path (Join-Path $pair[1] 'session-state') -Source ('env:' + $pair[0])
            $chr[$key] = Get-DbReport -Path (Join-Path $pair[1] 'session-store.db') -Source ('env:' + $pair[0])
            $leg[$key] = Get-LegacyDirReport -Path (Join-Path $pair[1] 'history-session-state') -Source ('env:' + $pair[0])
            $mcc[$key] = Get-FileProbe -Path (Join-Path $pair[1] 'vscode.session.metadata.cache.json') -Source ('env:' + $pair[0])
            $sch[$key] = Get-SchemaProbe -Path (Join-Path $pair[1] 'pkg') -Source ('env:' + $pair[0]) -MaxDepth 3
        } else {
            $ss[$key]  = New-EnvNotSetEntry $pair[0]
            $chr[$key] = New-EnvNotSetEntry $pair[0]
            $leg[$key] = New-EnvNotSetEntry $pair[0]
            $mcc[$key] = New-EnvNotSetEntry $pair[0]
            $sch[$key] = New-EnvNotSetEntry $pair[0]
        }
    }
    $report.surfaces.copilot_cli = [ordered]@{
        session_state         = $ss
        legacy_history_state  = $leg
        chronicle             = $chr
        vscode_metadata_cache = $mcc
        shipped_schemas       = $sch
    }

    $report.errors = @($script:DiscoveryErrors)
    return $report
}

# --------------------------------------------------------------- selftest ---

function Write-STResult {
    # Write-Host deliberately: self-test lines must not enter the pipeline and
    # contaminate Invoke-SelfTest's integer return value.
    param([string]$Name, [bool]$Ok, [string]$Note)
    $tag = 'FAIL'; if ($Ok) { $tag = 'PASS' }
    $suffix = ''
    if (-not [string]::IsNullOrEmpty($Note)) { $suffix = '  (' + $Note + ')' }
    Write-Host ($tag + '  ' + $Name + $suffix)
}

function Invoke-SelfTest {
    $fails = 0
    $tmp = [System.IO.Path]::GetTempPath()

    # 1. path redaction: fabricated path containing the real username -> ~ / <USER>
    $u = $env:USERNAME
    if ([string]::IsNullOrEmpty($u)) {
        Write-STResult 'path-redaction' $true 'skipped: no USERNAME env'
    } else {
        $base = $env:USERPROFILE
        if ([string]::IsNullOrEmpty($base)) { $base = $env:HOME }
        if ([string]::IsNullOrEmpty($base)) { $base = $tmp }
        $fake = Join-Path $base ('dir_' + $u + '_end')
        $lg = ConvertTo-LogicalPath $fake
        $ok = ($lg -notmatch [regex]::Escape($u)) -and ($lg -match '<USER>|~')
        if (-not $ok) { $fails++ }
        Write-STResult 'path-redaction' $ok $lg
    }

    # 2. truncated-tail detection on a temp file without trailing newline
    $tf = Join-Path $tmp ('dast-st-' + [guid]::NewGuid().ToString('N') + '.tmp')
    $ok = $false
    try {
        [System.IO.File]::WriteAllText($tf, 'tail-without-newline')
        $tTrunc = Test-TruncatedTail $tf
        [System.IO.File]::WriteAllText($tf, "with-newline`n")
        $tNormal = Test-TruncatedTail $tf
        $ok = ($tTrunc -eq $true) -and ($tNormal -eq $false)
    } catch { $ok = $false }
    finally { Remove-Item -LiteralPath $tf -Force -ErrorAction SilentlyContinue }
    if (-not $ok) { $fails++ }
    Write-STResult 'truncated-tail-detect' $ok

    # 3. sqlite schema read returns table+column names only
    $exe = Get-SqliteExe
    if ($null -ne $exe) {
        $db = Join-Path $tmp ('dast-st-' + [guid]::NewGuid().ToString('N') + '.db')
        $ok = $false
        $sc = $null
        try {
            & $exe $db 'CREATE TABLE st_one(a INTEGER, b TEXT); CREATE TABLE st_two(c);' | Out-Null
            $sc = Get-SqliteSchema -DbPath $db
            $ok = ($sc.status -eq 'ok') -and $sc.tables.Contains('st_one') -and ($sc.tables['st_one'] -eq 'a,b') -and $sc.tables.Contains('st_two')
        } catch { $ok = $false }
        finally { Remove-Item -LiteralPath $db -Force -ErrorAction SilentlyContinue }
        if (-not $ok) { $fails++ }
        $note = ''
        if ($null -ne $sc -and $sc.Contains('status')) { $note = 'status=' + [string]$sc.status }
        Write-STResult 'sqlite-schema-read' $ok $note
    } else {
        $sc = Get-SqliteSchema -DbPath (Join-Path $tmp 'nonexistent-dast.db')
        Write-STResult 'sqlite-schema-read' $true ('skipped: no sqlite engine (status=' + [string]$sc.status + ')')
    }

    # 4. all three surfaces + Chronicle present when pointed at fabricated dirs
    $fr = Join-Path $tmp ('dast-root-' + [guid]::NewGuid().ToString('N'))
    $ok = $false
    $stErr = ''
    try {
        $ssd = Join-Path (Join-Path $fr '.copilot') 'session-state'
        $sd = Join-Path $ssd 'sess-0001'
        [void](New-Item -ItemType Directory -Path $sd -Force)
        [System.IO.File]::WriteAllText((Join-Path $sd 'events.jsonl'), "{}`n")
        [System.IO.File]::WriteAllText((Join-Path $sd 'workspace.yaml'), 'k: 1')
        [System.IO.File]::WriteAllText((Join-Path $ssd 'a1b2c3d4-5555-4666-8777-d88899990000.jsonl'), "{}`n")
        [void](New-Item -ItemType Directory -Path (Join-Path (Join-Path $fr '.copilot') 'history-session-state\old-1') -Force)
        [System.IO.File]::WriteAllText((Join-Path $fr '.copilot\session-store.db'), '')
        [System.IO.File]::WriteAllText((Join-Path $fr '.copilot\vscode.session.metadata.cache.json'), '{}')
        $pkgd = Join-Path (Join-Path (Join-Path $fr '.copilot') 'pkg') 'universal\1.0.48\schemas'
        [void](New-Item -ItemType Directory -Path $pkgd -Force)
        [System.IO.File]::WriteAllText((Join-Path $pkgd 'session-events.schema.json'), '{}')
        $rd = Join-Path (Join-Path $fr '.codex') 'sessions\2024\05\06'
        [void](New-Item -ItemType Directory -Path $rd -Force)
        [System.IO.File]::WriteAllText((Join-Path $rd 'rollout-aaa.jsonl'), "{}`n")
        $ard = Join-Path (Join-Path $fr '.codex') 'archived_sessions'
        [void](New-Item -ItemType Directory -Path $ard -Force)
        [System.IO.File]::WriteAllText((Join-Path $ard 'rollout-bbb.jsonl'), "{}`n")
        $vd = Join-Path $fr 'vscode-user'
        $cd = Join-Path (Join-Path (Join-Path $vd 'workspaceStorage') 'a1b2c3d4e5f6') 'chatSessions'
        [void](New-Item -ItemType Directory -Path $cd -Force)
        [System.IO.File]::WriteAllText((Join-Path $cd 's1.json'), '{}')
        [void](New-Item -ItemType Directory -Path (Join-Path (Join-Path $vd 'globalStorage') 'emptyWindowChatSessions') -Force)
        [void](New-Item -ItemType Directory -Path (Join-Path (Join-Path $vd 'globalStorage') 'transferredChatSessions') -Force)
        [void](New-Item -ItemType Directory -Path (Join-Path (Join-Path $vd 'globalStorage') 'github.copilot-chat') -Force)
        [System.IO.File]::WriteAllText((Join-Path (Join-Path $vd 'globalStorage') 'state.vscdb'), '')
        [System.IO.File]::WriteAllText((Join-Path $vd 'settings.json'), '{"chat.disableAIFeatures": true}')
        $rep = Invoke-Discovery -Root $fr -MaxDepth 4 -SkipProbes
        $ok = $true
        $ok = $ok -and $rep.surfaces.Contains('vscode_chat') -and $rep.surfaces.Contains('codex_cli') -and $rep.surfaces.Contains('copilot_cli')
        $ok = $ok -and $rep.surfaces.vscode_chat.stable.present
        $ok = $ok -and ($rep.surfaces.vscode_chat.stable.chat_session_dirs -ge 1)
        $ok = $ok -and ($rep.surfaces.codex_cli.sessions.home.files -ge 1)
        $ok = $ok -and ($rep.surfaces.codex_cli.archived_sessions.home.files -ge 1)
        $ok = $ok -and ($rep.surfaces.copilot_cli.session_state.home.session_dirs -eq 1)
        $ok = $ok -and ($rep.surfaces.copilot_cli.session_state.home.flat_jsonl_files -eq 1)
        $ok = $ok -and ($rep.surfaces.copilot_cli.session_state.home.file_presence['events.jsonl'] -eq 1)
        $ok = $ok -and ($rep.surfaces.copilot_cli.legacy_history_state.home.dir_count -eq 1)
        $ok = $ok -and $rep.surfaces.copilot_cli.chronicle.home.exists
        $ok = $ok -and $rep.surfaces.copilot_cli.chronicle.Contains('env_COPILOT_HOME')
        $ok = $ok -and $rep.surfaces.copilot_cli.chronicle.Contains('env_COPILOT_DIR')
        $ok = $ok -and $rep.surfaces.copilot_cli.vscode_metadata_cache.home.exists
        $ok = $ok -and ($rep.surfaces.copilot_cli.shipped_schemas.home.session_events_schema_files -eq 1)
        $ok = $ok -and $rep.surfaces.vscode_chat.stable.transferred_window_sessions.exists
        $ok = $ok -and ($rep.versions['chat.disableAIFeatures'] -eq $true)
    } catch { $ok = $false; $stErr = [string]$_.Exception.Message }
    finally { Remove-Item -LiteralPath $fr -Recurse -Force -ErrorAction SilentlyContinue }
    if (-not $ok) { $fails++ }
    Write-STResult 'surfaces-fabricated-roots' $ok $stErr

    # 5. nonexistent path does not abort
    $ok = $false
    try {
        $gi = Get-DirInventory -Path (Join-Path $tmp ('dast-nope-' + [guid]::NewGuid().ToString('N'))) -MaxDepth 4 -Filter ''
        $ok = ($gi.exists -eq $false) -and ($gi.files -eq 0) -and ($gi.state -eq 'not-found')
    } catch { $ok = $false }
    if (-not $ok) { $fails++ }
    Write-STResult 'nonexistent-path-safe' $ok

    return $fails
}

# -------------------------------------------------------------------- main ---

if ($SelfTest) {
    Write-Output 'discover-agent-storage self-test'
    $f = Invoke-SelfTest
    Write-Output ('self-test failures: ' + $f)
    if ($f -eq 0) { exit 0 } else { exit 1 }
}

$depth = 4
if ($Detailed) { $depth = 8 }
$rep = Invoke-Discovery -Root $Root -MaxDepth $depth
$json = $rep | ConvertTo-Json -Depth 6
$header = @(
    '# discover-agent-storage.ps1 - read-only diagnostic'
    ('# generated_at_utc_day: ' + $rep.generated_at_utc_day)
    '# privacy: logical paths only (~, <USER>, <VSCODE_USER>); counts/buckets/day-dates; no contents, rows or titles'
    ('# scan roots: ' + $rep.scan.roots.copilot_home + ', ' + $rep.scan.roots.codex_home + ', ' + $rep.scan.roots.vscode_user)
)
$text = ($header -join [System.Environment]::NewLine) + [System.Environment]::NewLine + $json
Write-Output $text
if (-not [string]::IsNullOrEmpty($OutFile)) {
    try {
        $text | Out-File -LiteralPath $OutFile -Encoding utf8 -ErrorAction Stop
        Write-Output ('# written: ' + (ConvertTo-LogicalPath $OutFile))
    } catch {
        Write-Output ('# outfile-failed: ' + (ConvertTo-LogicalPath $OutFile))
    }
}
