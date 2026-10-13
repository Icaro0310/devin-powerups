/**
 * codex-cli surface parser — build-fresh (no TS reference).
 * Precedence (provisional, revertible in G1):
 *   1. SQLite `<codexHome>/state_<N>.sqlite`, largest N wins, READ-ONLY
 *      via `node:sqlite`; metadata columns only — never select title/
 *      preview/first_user_message (auto-derived from user content).
 *      Unreadable db → `read-error` alone, else `partial-parse`+rollouts.
 *   2. Rollout JSONL under `sessions/`, `archived_sessions/`,
 *      `$CODEX_SESSIONS_DIR`; known ids → `duplicates`; forks ignored.
 * ended_at: no close marker — <60s activity → `session-open`; else
 * updated_at / last `task_complete`. source_version: `state-<N>`/`rollout`.
 */

import { existsSync, readdirSync, readFileSync, type Dirent } from 'node:fs';
import { createRequire } from 'node:module';
import { join, normalize } from 'node:path';
import type { CollectEnv, CollectMode, ParseWarning, SessionMeta, SourceResult, SurfaceParser } from '../model.ts';
import { result, warn } from '../model.ts';
import { canonicalId, ephemeralKey, workspaceHash } from '../ids.ts';

const SURFACE = 'codex-cli' as const;
const FRESH_MS = 60_000;
const STATE_RE = /^state_(\d+)\.sqlite$/;
const ROLLOUT_RE = /^rollout-.*\.jsonl$/;

/** Minimal `node:sqlite` surface — lazy require so platforms without it still parse rollouts. */
type SqliteCtor = new (path: string, opts: { readOnly: boolean }) => {
  prepare(sql: string): { all(): unknown[] };
  close(): void;
};

function loadSqlite(): SqliteCtor | null {
  try {
    return (createRequire(import.meta.url)('node:sqlite') as { DatabaseSync?: SqliteCtor }).DatabaseSync ?? null;
  } catch { return null; }
}

interface Draft {
  nativeId: string | null; cwd: string | null;
  startedAt: string | null; endedAt: string | null; sourceVersion: string | null;
  eventCount: number | null; warnings: ParseWarning[];
}

const asStr = (v: unknown): string | null => (typeof v === 'string' && v ? v : null);
const asObj = (v: unknown): Record<string, unknown> => (typeof v === 'object' && v !== null ? v as Record<string, unknown> : {});

/** Number → unix s/ms; string → ISO when parseable; else null. */
function toIso(v: unknown): string | null {
  if (typeof v === 'number' && Number.isFinite(v)) return new Date(v < 1e12 ? v * 1000 : v).toISOString();
  const t = typeof v === 'string' ? Date.parse(v) : NaN;
  return Number.isNaN(t) ? null : new Date(t).toISOString();
}

const normCwd = (c: string): string => normalize(c).replace(/[\\/]+$/, '');
const isFresh = (iso: string): boolean => Date.now() - Date.parse(iso) < FRESH_MS;

/** ended_at: explicit close wins; missing activity → `no-end-marker`;
 *  fresh activity → `session-open` (stays null); otherwise infer close
 *  from last activity — silently when `quietInfer`, else with warning. */
function deriveEndedAt(lastTs: string | null, explicitEnd: string | null, quietInfer: boolean, w: ParseWarning[], origin?: string): string | null {
  if (explicitEnd) return explicitEnd;
  if (!lastTs) { w.push(warn('no-end-marker', 'no activity timestamp', origin)); return null; }
  if (isFresh(lastTs)) { w.push(warn('session-open', 'activity in the last 60s; session appears open', origin)); return null; }
  if (!quietInfer) w.push(warn('no-end-marker', 'closed state inferred from last activity', origin));
  return lastTs;
}

function stateVersion(p: string): string | null {
  const m = STATE_RE.exec(p.split(/[\\/]/).pop() ?? '');
  return m?.[1] ? `state-${m[1]}` : null;
}

function newestStateDb(dir: string): string | null {
  let names: string[];
  try {
    names = readdirSync(dir);
  } catch { return null; }
  let best: string | null = null, bestN = -1;
  for (const name of names) {
    const n = Number(STATE_RE.exec(name)?.[1]);
    if (n > bestN) { bestN = n; best = name; }
  }
  return best ? join(dir, best) : null;
}

function walk(dir: string, out: string[], depth: number): void {
  if (depth > 8) return;
  let entries: Dirent[];
  try { entries = readdirSync(dir, { withFileTypes: true }); } catch { return; }
  for (const e of entries) {
    if (e.isDirectory()) walk(join(dir, e.name), out, depth + 1);
    else if (e.isFile() && ROLLOUT_RE.test(e.name)) out.push(join(dir, e.name));
  }
}

type ThreadRow = Record<string, unknown>;

/** Strictly read-only open AND probe — DatabaseSync opens lazily, so a
 *  bad path/WAL-on-ro-fs only fails at first use; `immutable=1` retries it. */
function openReadOnly(Ctor: SqliteCtor, path: string) {
  const uri = 'file:' + path.split('/').map(encodeURIComponent).join('/') + '?mode=ro&immutable=1';
  for (const spec of [path, uri]) {
    try {
      const db = new Ctor(spec, { readOnly: true });
      db.prepare('SELECT 1').all(); // force the lazy open now
      return db;
    } catch { /* try the next spec */ }
  }
  throw new Error('state db unreadable');
}

function readThreads(path: string): Draft[] {
  const Ctor = loadSqlite();
  if (!Ctor) throw new Error('node:sqlite unavailable');
  const db = openReadOnly(Ctor, path);
  try {
    const sv = stateVersion(path);
    const rows = db.prepare(
      'SELECT id, created_at, updated_at, cwd, has_user_event FROM threads',
    ).all() as ThreadRow[];
    return rows.map((row) => {
      const w: ParseWarning[] = [];
      const nativeId = asStr(row.id), cwd = asStr(row.cwd);
      const startedAt = toIso(row.created_at), updated = toIso(row.updated_at);
      if (!nativeId) w.push(warn('missing-field', 'native id missing', sv));
      if (!startedAt) w.push(warn('missing-field', 'start timestamp missing', sv));
      if (!cwd) w.push(warn('unknown-workspace', 'workspace path missing; id carries no workspace segment', sv));
      const hasUser = row.has_user_event === 1 || row.has_user_event === true;
      const endedAt = deriveEndedAt(updated, null, hasUser, w, sv ?? undefined);
      return {
        nativeId, cwd: cwd ? normCwd(cwd) : null, startedAt, endedAt,
        sourceVersion: sv, eventCount: null, warnings: w,
      };
    });
  } finally {
    db.close();
  }
}

function parseRollout(path: string): Draft | null {
  const text = readFileSync(path, 'utf8');
  const endsNl = text.length === 0 || text.endsWith('\n');
  const lines = text.split('\n');
  if (endsNl) lines.pop();
  let nativeId: string | null = null, cwd: string | null = null, startedAt: string | null = null;
  let lastTs: string | null = null, endTs: string | null = null;
  let events = 0, malformed = 0, truncated = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line?.trim()) continue;
    let rec: unknown;
    try {
      rec = JSON.parse(line);
    } catch {
      if (!endsNl && i === lines.length - 1) truncated = true;
      else malformed++;
      continue;
    }
    const obj = asObj(rec);
    if (Object.keys(obj).length === 0) { malformed++; continue; }
    const payload = asObj(obj.payload);
    const ts = toIso(obj.timestamp ?? payload.timestamp);
    if (ts) lastTs = ts;
    if (obj.type === 'session_meta') {
      if (asStr(payload.forked_from_id)) return null;
      nativeId = asStr(payload.id) ?? nativeId;
      if (!startedAt) startedAt = toIso(payload.timestamp) ?? ts;
      const git = asObj(payload.git);
      cwd = asStr(payload.cwd) ?? asStr(git.root) ?? asStr(git.repository_root) ?? cwd;
    } else if (obj.type === 'event_msg' && payload.type === 'task_complete' && ts) {
      endTs = ts;
    }
    events++;
  }
  if (events === 0) return null;
  const w: ParseWarning[] = [];
  if (truncated) w.push(warn('truncated-tail', 'final record truncated', 'rollout'));
  if (malformed > 0) w.push(warn('partial-parse', `${malformed} malformed record(s) skipped`, 'rollout'));
  if (!nativeId) w.push(warn('missing-field', 'native id missing', 'rollout'));
  if (!cwd) w.push(warn('unknown-workspace', 'workspace path missing; id carries no workspace segment', 'rollout'));
  if (!startedAt) startedAt = lastTs;
  if (!startedAt) w.push(warn('missing-field', 'start timestamp missing', 'rollout'));
  const endedAt = deriveEndedAt(lastTs, endTs, false, w, 'rollout');
  return {
    nativeId, cwd: cwd ? normCwd(cwd) : null, startedAt, endedAt,
    sourceVersion: 'rollout', eventCount: events, warnings: w,
  };
}

function toMeta(d: Draft, index: number): SessionMeta {
  const ws = d.cwd ? workspaceHash(d.cwd) : null;
  const id = d.nativeId ? canonicalId(SURFACE, ws, 'native', d.nativeId) : null;
  return {
    surface: SURFACE, id, display_key: id ?? ephemeralKey(SURFACE, index),
    title: null, started_at: d.startedAt, ended_at: d.endedAt,
    source_version: d.sourceVersion, workspace_hash: ws,
    event_count: d.eventCount, parse_warnings: d.warnings,
  };
}

export const codexCliParser: SurfaceParser = {
  surface: SURFACE,
  collect(env: CollectEnv, _mode: CollectMode): SourceResult {
    const codexHome = env.env?.CODEX_HOME?.trim() || join(env.home, '.codex');
    const codexExists = existsSync(codexHome);
    const files: string[] = [];
    if (codexExists) {
      walk(join(codexHome, 'sessions'), files, 0);
      walk(join(codexHome, 'archived_sessions'), files, 0);
    }
    const extra = env.env?.CODEX_SESSIONS_DIR?.trim();
    if (extra) walk(extra, files, 0);
    files.sort();
    if (!codexExists && files.length === 0) return result(SURFACE, 'source-not-found', []);
    const state = codexExists ? newestStateDb(codexHome) : null;
    if (!state && files.length === 0) return result(SURFACE, 'no-sessions', []);

    const warnings: ParseWarning[] = [];
    const drafts: Draft[] = [];
    const seen = new Set<string>();
    let dupes = 0;
    if (state) {
      try {
        for (const d of readThreads(state)) {
          if (d.nativeId) seen.add(d.nativeId);
          drafts.push(d);
        }
      } catch {
        if (files.length === 0) return result(SURFACE, 'read-error', []);
        warnings.push(warn('partial-parse', 'state database unreadable; rollout files used', stateVersion(state)));
      }
    }
    for (const f of files) {
      let d: Draft | null = null;
      try {
        d = parseRollout(f);
      } catch {
        warnings.push(warn('partial-parse', 'one rollout file unreadable', 'rollout'));
      }
      if (!d) continue;
      if (d.nativeId && seen.has(d.nativeId)) { dupes++; continue; }
      if (d.nativeId) seen.add(d.nativeId);
      drafts.push(d);
    }
    if (dupes > 0) warnings.push(warn('duplicates', `${dupes} duplicate session record(s) skipped`));
    if (drafts.length === 0) return result(SURFACE, 'no-sessions', [], warnings);
    drafts.sort((a, b) => (b.startedAt ?? '').localeCompare(a.startedAt ?? ''));
    return result(SURFACE, 'ok', drafts.map(toMeta), warnings);
  },
};
