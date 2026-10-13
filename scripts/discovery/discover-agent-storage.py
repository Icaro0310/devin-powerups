#!/usr/bin/env python3
"""discover-agent-storage.py — read-only diagnostic for local agent storage.

Inventories on-disk state for three agent/chat surfaces and prints a
privacy-redacted JSON report the owner can paste back:

  * Copilot Chat in VS Code (desktop + remote-server): workspaceStorage
    */chatSessions (+ GitHub.copilot-chat/github.copilot-chat variants),
    globalStorage/emptyWindowChatSessions, globalStorage/github.copilot-chat,
    globalStorage/state.vscdb schema, chat.disableAIFeatures in settings.json.
  * Codex CLI: ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl (+ $CODEX_HOME).
  * Copilot CLI: ~/.copilot/session-state/<uuid>/{events.jsonl,workspace.yaml},
    legacy history-session-state, Chronicle session-store.db (+ $COPILOT_HOME).

PRIVACY (hard): only counts, size buckets, day mtimes, entry types and
SQLite table/column names are emitted. Paths pass through logical_path():
home -> '~', username -> '<USER>'. No contents, titles, project names,
UUIDs or rows. Writes only inside tempfile.mkdtemp() during --self-test.

Usage: discover-agent-storage.py [--pretty] [--root DIR] [--self-test|-SelfTest]
Python 3.8+, stdlib only. Windows/macOS/Linux/WSL; devcontainer/SSH flags
are reported under "host".
"""
from __future__ import annotations

import argparse, getpass, json, os, platform, re, shutil, sqlite3, subprocess
import sys, tempfile, urllib.parse
from datetime import datetime, timezone
from pathlib import Path

SIZE_BUCKETS = ("<1KB", "1-64KB", "64KB-1MB", ">1MB")
MAX_ENTRIES, TREE_CAP, PROBE_TIMEOUT = 200000, 600, 10
SAFE_DIRS = {"workspaceStorage", "globalStorage", "chatSessions",  # structural,
             "emptyWindowChatSessions", "transferredChatSessions",
             "github.copilot-chat", "GitHub.copilot-chat",          # never user data
             "session-state", "history-session-state",
             "sessions", "archived_sessions", "User", "data",
             "pkg", "universal", "schemas"}
SAFE_FILES = {"state.vscdb", "settings.json", "events.jsonl",
              "workspace.yaml", "session-store.db"}
OPAQUE_RE = re.compile(r"^[0-9a-fA-F-]{16,}(\.[0-9a-zA-Z]{1,8})?$")
DIGITS_RE = re.compile(r"^\d{1,10}$")
ROLLOUT_RE = re.compile(r"^rollout-[\w.\-]+\.jsonl$")

class Ctx:
    """Shared context: home root, redaction set, error accumulator."""

    def __init__(self, home, root_override=False):
        self.home, self.root_override, self.errors = Path(home), root_override, []
        names = {self.home.name}
        try:
            names.add(getpass.getuser())
        except Exception: pass
        for var in ("USERNAME", "USER", "LOGNAME"):
            if os.environ.get(var): names.add(os.environ[var])
        self.names = {n for n in names if n and n != "~"}

    def logical(self, p):
        """Map home -> '~' and any username occurrence -> '<USER>'."""
        s, h = str(p), str(self.home)
        if s == h:
            s = "~"
        elif s.startswith(h + os.sep) or s.startswith(h + "/"):
            s = "~" + s[len(h):]
        s = s.replace("\\", "/")
        for n in sorted(self.names, key=len, reverse=True):
            s = s.replace(n, "<USER>")
        return s

    def err(self, p, kind):
        self.errors.append({"path": self.logical(p), "kind": kind})

def bucket(n):
    return ("<1KB" if n < 1024 else "1-64KB" if n < 64 * 1024
            else "64KB-1MB" if n < 1024 * 1024 else ">1MB")

def _day_merge(res, ts):
    d = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
    if res["mtime_earliest_day"] is None or d < res["mtime_earliest_day"]:
        res["mtime_earliest_day"] = d
    if res["mtime_latest_day"] is None or d > res["mtime_latest_day"]:
        res["mtime_latest_day"] = d

def _empty_stats(path, ctx):
    return {"path": ctx.logical(path), "exists": Path(path).is_dir() or Path(path).is_file(),
            "state": "not-found", "files": 0, "dirs": 0, "other": 0, "by_ext": {},
            "size_buckets": {b: 0 for b in SIZE_BUCKETS},
            "mtime_earliest_day": None, "mtime_latest_day": None,
            "truncated_tail": {}, "tree": [], "tree_capped": False, "capped": False}


def _tail_truncated(path, ctx):
    """True when a non-empty file's last byte is not a newline."""
    try:
        with open(path, "rb") as fh:
            fh.seek(-1, os.SEEK_END)
            return fh.read(1) != b"\n"
    except PermissionError: ctx.err(path, "access-denied")
    except OSError: ctx.err(path, "read-error")
    return False

def inspect_dir(base, ctx, max_depth=4):
    """Counts/exts/days/size-buckets/tree for a directory. Read-only."""
    res = _empty_stats(base, ctx)
    if not res["exists"]: return res
    res["state"] = "present"
    total = [0]

    def disp(name, is_dir):  # safe/opaque names verbatim, else typed tag
        ok = (name in SAFE_DIRS or OPAQUE_RE.match(name) or DIGITS_RE.match(name)) if is_dir \
            else (name in SAFE_FILES or OPAQUE_RE.match(name) or ROLLOUT_RE.match(name))
        return name if ok else ("<DIR>" if is_dir else "<FILE>")

    def walk(d, rel, depth):
        try:
            with os.scandir(d) as it:
                ents = sorted(it, key=lambda e: e.name)
        except PermissionError: return ctx.err(d, "access-denied")
        except OSError: return ctx.err(d, "read-error")
        counters = {}
        for e in ents:
            if total[0] >= MAX_ENTRIES:
                res["capped"] = True
                return
            total[0] += 1
            try:
                t = ("other" if e.is_symlink() else "dir" if e.is_dir(follow_symlinks=False)
                     else "file" if e.is_file(follow_symlinks=False) else "other")
            except OSError: t = "other"
            name = "<OTHER>" if t == "other" else disp(e.name, t == "dir")
            if name.startswith("<"):
                counters[t] = counters.get(t, 0) + 1
                name = name[:-1] + ":" + str(counters[t]) + ">"
            r = name if not rel else rel + "/" + name
            if len(res["tree"]) < TREE_CAP:
                res["tree"].append({"path": r, "type": t})
            else:
                res["tree_capped"] = True
            if t == "dir":
                res["dirs"] += 1
                if depth < max_depth:
                    walk(Path(e.path), r, depth + 1)
            elif t == "file":
                res["files"] += 1
                ext = Path(e.name).suffix.lower()
                k = ext if (ext and len(ext) <= 10) else ("<NONE>" if not ext else "<OTHER>")
                res["by_ext"][k] = res["by_ext"].get(k, 0) + 1
                try:
                    st = e.stat(follow_symlinks=False)
                    res["size_buckets"][bucket(st.st_size)] += 1
                    _day_merge(res, st.st_mtime)
                    if st.st_size > 0 and _tail_truncated(e.path, ctx):
                        kk = rel or "<root>"
                        res["truncated_tail"][kk] = res["truncated_tail"].get(kk, 0) + 1
                except PermissionError: ctx.err(e.path, "access-denied")
                except OSError: ctx.err(e.path, "read-error")
            else:
                res["other"] += 1

    walk(Path(base), "", 1)
    return res

def merge_inspect(items):
    """Merge inspect_dir results, prefixing tail dirs with parent path."""
    m = {"dirs_scanned": len(items), "dirs_present": 0, "files": 0, "by_ext": {},
         "size_buckets": {b: 0 for b in SIZE_BUCKETS}, "truncated_tail": {},
         "mtime_earliest_day": None, "mtime_latest_day": None}
    for it in items:
        if not it["exists"]:
            continue
        m["dirs_present"] += 1
        m["files"] += it["files"]
        for k, v in it["by_ext"].items():
            m["by_ext"][k] = m["by_ext"].get(k, 0) + v
        for b in SIZE_BUCKETS:
            m["size_buckets"][b] += it["size_buckets"][b]
        for f, pick in (("mtime_earliest_day", min), ("mtime_latest_day", max)):
            if it[f] and (m[f] is None or pick(it[f], m[f]) == it[f]):
                m[f] = it[f]
        for k, v in it["truncated_tail"].items():
            kk = it["path"] + ("/" + k if k != "<root>" else "")
            m["truncated_tail"][kk] = m["truncated_tail"].get(kk, 0) + v
    return m

def sqlite_schema(path, ctx):
    """Table + column names only, read-only URI. Never rows."""
    res = {"path": ctx.logical(path), "exists": Path(path).is_file(),
           "state": "not-found", "tables": {}}
    if not res["exists"]: return res
    res["state"] = "present"
    uri = "file:" + urllib.parse.quote(str(path).replace("\\", "/"), safe="/:") + "?mode=ro"
    try:
        con = sqlite3.connect(uri, uri=True)
        try:
            names = [r[0] for r in con.execute(
                "select name from sqlite_master where type in ('table','view') order by 1")]
            for name in names:
                lit = "'" + name.replace("'", "''") + "'"
                try:
                    res["tables"][name] = [r[1] for r in con.execute("pragma table_info(%s)" % lit)]
                except sqlite3.Error: res["tables"][name] = []
        finally:
            con.close()
    except sqlite3.Error:
        res["state"] = "unreadable"; ctx.err(path, "read-error")
    return res

def settings_disable_ai(user_dir):
    f = Path(user_dir) / "settings.json"
    if not f.is_file(): return {"status": "not-found"}
    try:
        data = json.loads(f.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return {"status": "unreadable"}
    if isinstance(data, dict) and "chat.disableAIFeatures" in data:
        v = data["chat.disableAIFeatures"]
        return {"status": "set", "value": v if isinstance(v, bool) else "<OTHER>"}
    return {"status": "unset"}

def detect_host(home):
    wsl = bool(os.environ.get("WSL_INTEROP") or os.environ.get("WSL_DISTRO_NAME"))
    if not wsl:
        try:
            wsl = "microsoft" in Path("/proc/sys/kernel/osrelease").read_text().lower()
        except OSError: pass
    return {"os": platform.system() or sys.platform, "platform": sys.platform, "wsl": wsl,
            "devcontainer": bool(os.environ.get("REMOTE_CONTAINERS")) or Path("/.dockerenv").exists(),
            "ssh": bool(os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY")),
            "remote_server": (home / ".vscode-server").is_dir() or (home / ".vscode-server-insiders").is_dir()}

def vscode_candidates(ctx):
    h = ctx.home
    app = (h / "AppData" / "Roaming") if (ctx.root_override or not os.environ.get("APPDATA")) \
        else Path(os.environ["APPDATA"])
    out = [("code", "windows-appdata", app / "Code" / "User"),
           ("code-insiders", "windows-appdata", app / "Code - Insiders" / "User"),
           ("code", "linux-config", h / ".config" / "Code" / "User"),
           ("code-insiders", "linux-config", h / ".config" / "Code - Insiders" / "User"),
           ("code", "macos", h / "Library" / "Application Support" / "Code" / "User"),
           ("code-insiders", "macos", h / "Library" / "Application Support" / "Code - Insiders" / "User"),
           ("code", "remote-server", h / ".vscode-server" / "data" / "User"),
           ("code-insiders", "remote-server", h / ".vscode-server-insiders" / "data" / "User")]
    seen, uniq = set(), []
    for inst, flav, p in out:
        if os.path.normcase(str(p)) not in seen:
            seen.add(os.path.normcase(str(p)))
            uniq.append((inst, flav, p))
    return uniq

def scan_vscode_user(user_dir, ctx):
    ws, gs = Path(user_dir) / "workspaceStorage", Path(user_dir) / "globalStorage"
    chat_dirs, n_ws = [], 0
    if ws.is_dir():
        try:
            with os.scandir(ws) as it:
                for e in it:
                    try:
                        ok = e.is_dir(follow_symlinks=False)
                    except OSError: ok = False
                    if not ok:
                        continue
                    n_ws += 1
                    for sub in ("chatSessions", "GitHub.copilot-chat/chatSessions",
                                "github.copilot-chat/chatSessions"):
                        d = Path(e.path) / sub
                        if d.is_dir():
                            chat_dirs.append(d)
        except PermissionError: ctx.err(ws, "access-denied")
        except OSError: ctx.err(ws, "read-error")
    return {"workspace_dirs": n_ws,
            "workspace_storage": inspect_dir(ws, ctx, max_depth=3),
            "chat_session_dirs": len(chat_dirs),
            "chat_sessions": merge_inspect([inspect_dir(d, ctx, max_depth=2) for d in chat_dirs]),
            "empty_window_sessions": inspect_dir(gs / "emptyWindowChatSessions", ctx, max_depth=2),
            "transferred_window_sessions": inspect_dir(gs / "transferredChatSessions", ctx, max_depth=2),
            "copilot_chat_global": inspect_dir(gs / "github.copilot-chat", ctx, max_depth=2),
            "state_db": sqlite_schema(gs / "state.vscdb", ctx),
            "chat_disable_ai": settings_disable_ai(user_dir)}

def _env_bases(ctx, rel_home, env_vars, rel_env):
    bases = [("home", ctx.home / rel_home)]
    for env_var in env_vars:
        if os.environ.get(env_var):
            bases.append(("env:" + env_var, Path(os.environ[env_var]) / rel_env))
    return bases

def scan_codex(ctx):
    def probe(src, d):
        insp = inspect_dir(d, ctx, max_depth=4)
        rollouts = 0
        if d.is_dir():
            try:
                for _ in d.rglob("rollout-*.jsonl"):
                    rollouts += 1
            except PermissionError: ctx.err(d, "access-denied")
            except OSError: ctx.err(d, "read-error")
        insp.update(source=src, rollout_files=rollouts)
        return insp

    sessions = [probe(s, d) for s, d in _env_bases(
        ctx, ".codex/sessions", ("CODEX_HOME",), "sessions")]
    if os.environ.get("CODEX_SESSIONS_DIR"):
        sessions.append(probe("env:CODEX_SESSIONS_DIR",
                              Path(os.environ["CODEX_SESSIONS_DIR"])))
    archived = [probe(s, d) for s, d in _env_bases(
        ctx, ".codex/archived_sessions", ("CODEX_HOME",), "archived_sessions")]
    return {"sessions": {"per_base": sessions},
            "archived_sessions": {"per_base": archived}}

def scan_session_state(base, ctx):
    res = {"path": ctx.logical(base), "exists": Path(base).is_dir(), "state": "not-found",
           "session_dirs": 0, "flat_jsonl_files": 0, "other_entries": 0,
           "file_presence": {"events.jsonl": 0, "workspace.yaml": 0},
           "size_buckets": {b: 0 for b in SIZE_BUCKETS},
           "mtime_earliest_day": None, "mtime_latest_day": None,
           "truncated_tail": {"<session-dir>": 0}}
    if not res["exists"]: return res
    res["state"] = "present"
    try:
        with os.scandir(base) as it:
            ents = list(it)
    except PermissionError:
        ctx.err(base, "access-denied"); return res
    except OSError:
        ctx.err(base, "read-error"); return res
    for e in ents:
        try:
            isd = e.is_dir(follow_symlinks=False)
        except OSError: continue
        if not isd:
            res["other_entries"] += 1
            if e.name.endswith(".jsonl") and OPAQUE_RE.match(e.name[:-6]):
                res["flat_jsonl_files"] += 1  # flat <uuid>.jsonl session layout
            continue
        res["session_dirs"] += 1  # UUID names are never stored or emitted.
        truncated = False
        for fn in ("events.jsonl", "workspace.yaml"):
            f = Path(e.path) / fn
            try:
                if not f.is_file():
                    continue
                st = f.stat()
                res["file_presence"][fn] += 1
                res["size_buckets"][bucket(st.st_size)] += 1
                _day_merge(res, st.st_mtime)
                if st.st_size > 0 and _tail_truncated(f, ctx):
                    truncated = True
            except PermissionError: ctx.err(f, "access-denied")
            except OSError: ctx.err(f, "read-error")
        if truncated:
            res["truncated_tail"]["<session-dir>"] += 1
    return res

def _first_line(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=PROBE_TIMEOUT)
    except subprocess.TimeoutExpired: return "timeout", None
    except OSError: return "exec-failed", None
    for stream in (r.stdout, r.stderr):
        for line in (stream or "").splitlines():
            if line.strip():
                return "ok", line.strip()[:200]
    return "ok", None

def probe_versions(ctx):
    out = {}

    def probe(key, cmd0):
        exe = shutil.which(cmd0)
        ent = {"installed": bool(exe)}
        if exe:
            ent["path"] = ctx.logical(exe)
            ent["probe"], line = _first_line([cmd0, "--version"])
            if line:
                ent["version_first_line"] = line
        out[key] = ent

    for name in ("code", "code-insiders", "copilot", "codex", "node"):
        probe(name, name)
    py = next((n for n in ("python3", "python") if shutil.which(n)), None)
    probe("python", py) if py else out.setdefault("python", {"installed": False})
    if out["code"]["installed"]:
        try:
            r = subprocess.run(["code", "--list-extensions"], capture_output=True,
                               text=True, timeout=PROBE_TIMEOUT)
            out["code"]["copilot_extensions"] = sorted(
                {l.strip() for l in r.stdout.splitlines() if "copilot" in l.lower() and l.strip()})
        except subprocess.TimeoutExpired: out["code"]["copilot_extensions_probe"] = "timeout"
        except OSError: out["code"]["copilot_extensions_probe"] = "exec-failed"
    return out

def _file_probe(path, ctx):
    """Existence + size bucket + mtime day for a single known file."""
    p = Path(path)
    res = {"path": ctx.logical(p), "exists": p.is_file()}
    if res["exists"]:
        try:
            st = p.stat()
            res["size_bucket"] = bucket(st.st_size)
            res["mtime_day"] = datetime.fromtimestamp(
                st.st_mtime, tz=timezone.utc).date().isoformat()
        except PermissionError: ctx.err(p, "access-denied")
        except OSError: ctx.err(p, "read-error")
    return res

def _schema_probe(pkg_dir, ctx):
    """Tree + count of shipped session-events.schema.json files."""
    res = inspect_dir(pkg_dir, ctx, max_depth=3)
    res["session_events_schema_files"] = 0
    if pkg_dir.is_dir():
        try:
            for _ in pkg_dir.rglob("session-events.schema.json"):
                res["session_events_schema_files"] += 1
        except PermissionError: ctx.err(pkg_dir, "access-denied")
        except OSError: ctx.err(pkg_dir, "read-error")
    return res

def _copilot_bases(ctx):
    bases = [("home", ctx.home / ".copilot")]
    for ev in ("COPILOT_DIR", "COPILOT_HOME"):
        if os.environ.get(ev):
            bases.append(("env:" + ev, Path(os.environ[ev])))
    return bases

def build_report(home, root_override=False):
    ctx = Ctx(home, root_override=root_override)
    installs = []
    for inst, flav, ud in vscode_candidates(ctx):
        ent = {"install": inst, "flavor": flav, "user_dir": ctx.logical(ud),
               "present": ud.is_dir(), "state": "present" if ud.is_dir() else "not-found"}
        if ent["present"]:
            ent["storage"] = scan_vscode_user(ud, ctx)
        installs.append(ent)
    copilot_cli = {}
    for key, rel, fn in (
            ("session_state", "session-state", scan_session_state),
            ("legacy", "history-session-state",
             lambda d, c: inspect_dir(d, c, max_depth=1)),
            ("chronicle", "session-store.db", sqlite_schema)):
        copilot_cli[key] = {"per_base": [dict(fn(b / rel, ctx), source=s)
                                         for s, b in _copilot_bases(ctx)]}
    copilot_cli["vscode_metadata_cache"] = {
        "per_base": [dict(_file_probe(b / "vscode.session.metadata.cache.json", ctx),
                          source=s)
                     for s, b in _copilot_bases(ctx)]}
    copilot_cli["shipped_schemas"] = {
        "per_base": [dict(_schema_probe(b / "pkg", ctx), source=s)
                     for s, b in _copilot_bases(ctx)]}
    return {
        "generated_at_utc_day": datetime.now(timezone.utc).date().isoformat(),
        "host": detect_host(ctx.home),
        "versions": probe_versions(ctx),
        "surfaces": {
            "vscode_chat": {"per_install": installs},
            "codex_cli": scan_codex(ctx),
            "copilot_cli": copilot_cli},
        "errors": ctx.errors}

def pretty(rep):
    h, s, L = rep["host"], rep["surfaces"], []
    L.append("host: %s wsl=%s devcontainer=%s ssh=%s remote_server=%s  generated=%s"
             % (h["os"], h["wsl"], h["devcontainer"], h["ssh"], h["remote_server"],
                rep["generated_at_utc_day"]))
    for name, v in rep["versions"].items():
        L.append("  %-14s %s" % (name, (v.get("version_first_line") or v.get("probe"))
                                 if v.get("installed") else "not installed"))
        L.extend("    ext: %s" % e for e in v.get("copilot_extensions", []))
    for i in s["vscode_chat"]["per_install"]:
        L.append("  vscode[%s/%s] %s %s" % (i["install"], i["flavor"], i["state"], i["user_dir"]))
        st = i.get("storage")
        if st:
            cs = st["chat_sessions"]
            L.append("    workspaces=%d chat_dirs=%d chat_files=%d days=%s..%s ai_disabled=%s state_db=%s(%d tables)"
                     % (st["workspace_dirs"], st["chat_session_dirs"], cs["files"],
                        cs["mtime_earliest_day"], cs["mtime_latest_day"],
                        st["chat_disable_ai"]["status"], st["state_db"]["state"],
                        len(st["state_db"].get("tables", {}))))
    cx = s["codex_cli"]
    for sect in ("sessions", "archived_sessions"):
        for b in cx[sect]["per_base"]:
            L.append("  codex-%s[%s] %s %s rollout=%d files=%d days=%s..%s"
                     % (sect, b["source"], b["state"], b["path"], b["rollout_files"],
                        b["files"], b["mtime_earliest_day"], b["mtime_latest_day"]))
    cc = s["copilot_cli"]
    for b in cc["session_state"]["per_base"]:
        L.append("  session-state[%s] %s %s dirs=%d flat=%d events=%d workspace=%d"
                 % (b["source"], b["state"], b["path"], b["session_dirs"],
                    b["flat_jsonl_files"], b["file_presence"]["events.jsonl"],
                    b["file_presence"]["workspace.yaml"]))
    for b in cc["legacy"]["per_base"]:
        L.append("  legacy[%s] %s %s entries=%d"
                 % (b["source"], b["state"], b["path"], b["files"] + b["dirs"]))
    for b in cc["chronicle"]["per_base"]:
        L.append("  chronicle[%s] %s %s tables=%s"
                 % (b["source"], b["state"], b["path"], sorted(b.get("tables", {}))))
    for b in cc["vscode_metadata_cache"]["per_base"]:
        L.append("  vscode-metadata-cache[%s] exists=%s %s"
                 % (b["source"], b.get("exists"), b["path"]))
    for b in cc["shipped_schemas"]["per_base"]:
        L.append("  shipped-schemas[%s] %s %s session-events.schema=%d"
                 % (b["source"], b["state"], b["path"],
                    b.get("session_events_schema_files", 0)))
    L.append("errors: %d" % len(rep["errors"]))
    L.extend("  %s %s" % (e["kind"], e["path"]) for e in rep["errors"][:20])
    return "\n".join(L)

# --- self-test --------------------------------------------------------------

def _write(path, data=b"", newline=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data + (b"\n" if newline else b""))

def _mk_db(path, ddl):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.executescript(ddl)
    con.commit()
    con.close()

def run_self_test():
    results = []

    def check(name, cond, detail=""):
        results.append(bool(cond))
        print("%s %s%s" % ("PASS" if cond else "FAIL", name,
                           "" if cond or not detail else " :: " + detail))

    ctx = Ctx(Path.home())
    try:
        uname = getpass.getuser()
    except Exception: uname = ""
    uname = uname or Path.home().name
    lp = ctx.logical(str(Path("/nonexistent-base") / uname / "proj" / "f.jsonl"))
    check("logical_path redacts username", uname not in lp and "<USER>" in lp, lp)
    lp2 = ctx.logical(Path.home() / "sub" / "f.txt")
    check("logical_path home to ~", lp2.startswith("~/") and str(Path.home()) not in lp2, lp2)

    root = Path(tempfile.mkdtemp(prefix="agent-storage-fixture-"))
    try:
        user = root / ".config" / "Code" / "User"
        wshash = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
        ws = user / "workspaceStorage" / wshash
        chat = ws / "chatSessions"
        sess = root / ".copilot" / "session-state" / "3f8a4e3f-4444-4555-8666-c77788899999"
        _write(chat / "0c7d1b0c-1111-4222-8333-944455556666.jsonl", b'{"k":1}', newline=False)
        _write(chat / "1d8e2c1d-2222-4333-8444-a55566677777.jsonl", b'{"k":2}')
        _write(ws / "GitHub.copilot-chat" / "chatSessions"
               / "2e9f3d2e-3333-4444-8555-b66677788888.jsonl", b"{}")
        _write(user / "globalStorage" / "emptyWindowChatSessions" / "e.json", b"{}")
        _write(user / "globalStorage" / "github.copilot-chat" / "g.json", b"{}")
        _write(user / "settings.json", b'{"chat.disableAIFeatures": true}')
        _mk_db(user / "globalStorage" / "state.vscdb", "create table ItemTable(key TEXT, value BLOB);")
        _write(root / ".vscode-server" / "data" / "User" / "globalStorage" / "x.json", b"{}")
        _write(root / ".codex" / "sessions" / "2025" / "01" / "02"
               / "rollout-2025-01-02T00-00-00-aaaa.jsonl", b'{"r":1}')
        _write(root / ".codex" / "archived_sessions"
               / "rollout-2024-12-31T00-00-00-bbbb.jsonl", b'{"r":2}')
        _write(sess / "events.jsonl", b'{"e":1}')
        _write(sess / "workspace.yaml", b"id: x", newline=False)
        _write(root / ".copilot" / "session-state"
               / "a1b2c3d4-5555-4666-8777-d88899990000.jsonl", b'{"e":2}')
        _write(root / ".copilot" / "history-session-state" / "legacy", b"x")
        _write(user / "globalStorage" / "transferredChatSessions" / "t.json", b"{}")
        _write(root / ".copilot" / "vscode.session.metadata.cache.json", b"{}")
        _write(root / ".copilot" / "pkg" / "universal" / "1.0.48" / "schemas"
               / "session-events.schema.json", b"{}")
        _mk_db(root / ".copilot" / "session-store.db",
               "create table sessions(id TEXT primary key, created_at TEXT);"
               "create table checkpoints(session_id TEXT);")
        ctx2 = Ctx(root, root_override=True)

        insp = inspect_dir(chat, ctx2, max_depth=2)
        check("truncated_tail detects missing newline",
              sum(insp["truncated_tail"].values()) == 1, str(insp["truncated_tail"]))
        sch = sqlite_schema(root / ".copilot" / "session-store.db", ctx2)
        check("sqlite schema tables+columns",
              sch["exists"] and sch["tables"].get("sessions") == ["id", "created_at"]
              and sch["tables"].get("checkpoints") == ["session_id"], str(sch))

        rep = build_report(root, root_override=True)
        vi = [i for i in rep["surfaces"]["vscode_chat"]["per_install"] if i["present"]]
        st0 = vi[0]["storage"] if vi else {}
        codex0 = rep["surfaces"]["codex_cli"]["sessions"]["per_base"][0]
        arc0 = rep["surfaces"]["codex_cli"]["archived_sessions"]["per_base"][0]
        ss0 = rep["surfaces"]["copilot_cli"]["session_state"]["per_base"][0]
        leg0 = rep["surfaces"]["copilot_cli"]["legacy"]["per_base"][0]
        chr0 = rep["surfaces"]["copilot_cli"]["chronicle"]["per_base"][0]
        mc0 = rep["surfaces"]["copilot_cli"]["vscode_metadata_cache"]["per_base"][0]
        sch0 = rep["surfaces"]["copilot_cli"]["shipped_schemas"]["per_base"][0]
        check("vscode surface detected",
              bool(vi) and st0.get("chat_session_dirs") == 2
              and st0["chat_sessions"]["files"] == 3
              and st0["chat_disable_ai"]["status"] == "set"
              and "ItemTable" in st0["state_db"]["tables"])
        check("codex surface detected", codex0["exists"] and codex0["rollout_files"] == 1)
        check("codex archived_sessions detected",
              arc0["exists"] and arc0["rollout_files"] == 1)
        check("copilot-cli session-state detected",
              ss0["session_dirs"] == 1 and ss0["flat_jsonl_files"] == 1 and
              ss0["file_presence"] == {"events.jsonl": 1, "workspace.yaml": 1})
        check("copilot-cli legacy + chronicle detected",
              leg0["files"] + leg0["dirs"] == 1 and chr0["exists"] and "sessions" in chr0["tables"])
        check("metadata cache + shipped schema probed",
              mc0["exists"] and sch0["session_events_schema_files"] == 1)
        check("remote server host flag", rep["host"]["remote_server"] is True)
        check("no username leakage in report", uname not in json.dumps(rep))

        rep2 = build_report(root / "does-not-exist", root_override=True)
        cc2 = rep2["surfaces"]
        ok = (all(not i["present"] for i in cc2["vscode_chat"]["per_install"])
              and cc2["codex_cli"]["sessions"]["per_base"][0]["state"] == "not-found"
              and cc2["copilot_cli"]["session_state"]["per_base"][0]["state"] == "not-found"
              and cc2["copilot_cli"]["chronicle"]["per_base"][0]["state"] == "not-found"
              and isinstance(rep2["errors"], list))
        check("nonexistent root -> not-found states", ok)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print("self-test: %d/%d passed" % (sum(results), len(results)))
    return 0 if all(results) else 1

def main(argv=None):
    p = argparse.ArgumentParser(
        description="Read-only discovery of local agent session storage "
                    "(privacy-redacted JSON report).")
    p.add_argument("--pretty", action="store_true",
                   help="human-readable summary instead of JSON")
    p.add_argument("--root", type=Path, default=None,
                   help="treat DIR as the home/config root (fixture testing)")
    p.add_argument("--self-test", "-SelfTest", dest="self_test", action="store_true",
                   help="run fixture checks; exit 0 iff all pass")
    a = p.parse_args(argv)
    if a.self_test: return run_self_test()
    home = a.root.expanduser() if a.root else Path.home()
    rep = build_report(home, root_override=a.root is not None)
    print(pretty(rep) if a.pretty else json.dumps(rep, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
