/**
 * devin-cli surface parser — Devin CLI `sessions.db`.
 * Source: `<dataRoot>/devin/cli/sessions.db`, first existing candidate:
 *   win32:  env.appdata ?? <home>/AppData/Roaming
 *   darwin: <home>/Library/Application Support
 *   linux:  $XDG_DATA_HOME ?? <home>/.local/share, then $XDG_CONFIG_HOME
 *           ?? <home>/.config, then <home>  (same roots as devin-search)
 * READ-ONLY via `node:sqlite`; metadata columns only — never select
 * `title`, `metadata` or any message text (all content-derived).
 * `hidden=1` rows are skipped: user-hidden in the CLI UI, same
 * convention as the history export.
 * ended_at: no close marker — <60s activity → `session-open`; else
 * `last_activity_at` with `no-end-marker` inference warning.
 * source_version: `schema-v<N>` from refinery_schema_history, else
 * `sessions.db`.
 */

import { existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join, normalize } from 'node:path';
import type { CollectEnv, CollectMode, ParseWarning, SessionMeta, SourceResult, SurfaceParser } from '../model.ts';
import { result, warn } from '../model.ts';
import { canonicalId, ephemeralKey, workspaceHash } from '../ids.ts';

const SURFACE = 'devin-cli' as const;
const FRESH_MS = 60_000;
const DB_RELPATH = ['devin', 'cli', 'sessions.db'];

/** Minimal `node:sqlite` surface — lazy require so platforms without it
 *  still report `source-not-found` for other surfaces. */
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
const asNum = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const toIso = (v: unknown): string | null => {
  const n = asNum(v);
  return n === null ? null : new Date(n < 1e12 ? n * 1000 : n).toISOString();
};
const normCwd = (c: string): string => normalize(c).replace(/[\\/]+$/, '');
const isFresh = (iso: string): boolean => Date.now() - Date.parse(iso) < FRESH_MS;

/** ended_at: fresh activity → `session-open` (stays null); otherwise
 *  infer close from last_activity_at with a `no-end-marker` warning. */
function deriveEndedAt(lastTs: string | null, w: ParseWarning[], origin: string | null): string | null {
  if (!lastTs) { w.push(warn('no-end-marker', 'no activity timestamp', origin)); return null; }
  if (isFresh(lastTs)) { w.push(warn('session-open', 'activity in the last 60s; session appears open', origin)); return null; }
  w.push(warn('no-end-marker', 'closed state inferred from last activity', origin));
  return lastTs;
}

function dbCandidates(env: CollectEnv): string[] {
  const roots: string[] = [];
  if (env.platform === 'win32') {
    roots.push(env.appdata ?? join(env.home, 'AppData', 'Roaming'));
  } else if (env.platform === 'darwin') {
    roots.push(join(env.home, 'Library', 'Application Support'));
  } else {
    roots.push(env.env?.XDG_DATA_HOME?.trim() || join(env.home, '.local', 'share'));
    roots.push(env.env?.XDG_CONFIG_HOME?.trim() || join(env.home, '.config'));
    roots.push(env.home);
  }
  const seen = new Set<string>();
  return roots
    .map(r => join(r, ...DB_RELPATH))
    .filter(p => (seen.has(p) ? false : (seen.add(p), true)));
}

/** Strictly read-only open AND probe — DatabaseSync opens lazily, so a
 *  bad path/WAL-on-ro-fs only fails at first use; `immutable=1` retries it. */
function openReadOnly(Ctor: SqliteCtor, path: string) {
  const uri = 'file:' + path.split('/').map(encodeURIComponent).join('/') + '?mode=ro&immutable=1';
  for (const spec of [path, uri]) {
    let db: { prepare(sql: string): { all(): unknown[] }; close(): void } | null = null;
    try {
      db = new Ctor(spec, { readOnly: true });
      db.prepare('SELECT 1').all(); // force the lazy open now
      return db;
    } catch {
      try { db?.close(); } catch { /* best-effort */ }
    }
  }
  throw new Error('sessions.db unreadable');
}

function schemaVersion(db: { prepare(sql: string): { all(): unknown[] } }): string {
  try {
    const rows = db.prepare(
      "SELECT name FROM sqlite_master WHERE type='table' AND name='refinery_schema_history'",
    ).all() as { name?: string }[];
    if (rows.length === 0) return 'sessions.db';
    const v = db.prepare('SELECT MAX(version) AS v FROM refinery_schema_history').all() as { v?: unknown }[];
    const n = asNum(v[0]?.v);
    return n === null ? 'sessions.db' : `schema-v${n}`;
  } catch { return 'sessions.db'; }
}

function readSessions(path: string): { drafts: Draft[]; sourceVersion: string } {
  const Ctor = loadSqlite();
  if (!Ctor) throw new Error('node:sqlite unavailable');
  const db = openReadOnly(Ctor, path);
  try {
    const sv = schemaVersion(db);
    const counts = new Map<string, number>();
    try {
      for (const row of db.prepare('SELECT session_id, COUNT(*) AS n FROM message_nodes GROUP BY session_id').all() as Record<string, unknown>[]) {
        const sid = asStr(row.session_id), n = asNum(row.n);
        if (sid && n !== null) counts.set(sid, n);
      }
    } catch { /* message_nodes absent in older schemas — counts stay null */ }
    const rows = db.prepare(
      'SELECT id, working_directory, created_at, last_activity_at, hidden FROM sessions',
    ).all() as Record<string, unknown>[];
    const drafts = rows
      .filter(row => row.hidden !== 1 && row.hidden !== true)
      .map((row): Draft => {
        const w: ParseWarning[] = [];
        const nativeId = asStr(row.id), cwd = asStr(row.working_directory);
        const startedAt = toIso(row.created_at), lastTs = toIso(row.last_activity_at);
        if (!nativeId) w.push(warn('missing-field', 'native id missing', sv));
        if (!startedAt) w.push(warn('missing-field', 'start timestamp missing', sv));
        if (!cwd) w.push(warn('unknown-workspace', 'workspace path missing; session id stays null, not deduplicated', sv));
        const endedAt = deriveEndedAt(lastTs, w, sv);
        return {
          nativeId, cwd: cwd ? normCwd(cwd) : null, startedAt, endedAt,
          sourceVersion: sv, eventCount: nativeId ? counts.get(nativeId) ?? null : null, warnings: w,
        };
      });
    return { drafts, sourceVersion: sv };
  } finally {
    db.close();
  }
}

function toMeta(d: Draft, index: number): SessionMeta {
  const ws = d.cwd ? workspaceHash(d.cwd) : null;
  const id = d.nativeId && ws ? canonicalId(SURFACE, ws, 'native', d.nativeId) : null;
  return {
    surface: SURFACE, id, display_key: id ?? ephemeralKey(SURFACE, index),
    title: null, started_at: d.startedAt, ended_at: d.endedAt,
    source_version: d.sourceVersion, workspace_hash: ws,
    event_count: d.eventCount, parse_warnings: d.warnings,
  };
}

export const devinCliParser: SurfaceParser = {
  surface: SURFACE,
  collect(env: CollectEnv, _mode: CollectMode): SourceResult {
    const dbPath = dbCandidates(env).find(existsSync) ?? null;
    if (!dbPath) return result(SURFACE, 'source-not-found', []);
    let drafts: Draft[];
    try {
      ({ drafts } = readSessions(dbPath));
    } catch {
      return result(SURFACE, 'read-error', []);
    }
    if (drafts.length === 0) return result(SURFACE, 'no-sessions', []);
    drafts.sort((a, b) => (b.startedAt ?? '').localeCompare(a.startedAt ?? ''));
    return result(SURFACE, 'ok', drafts.map(toMeta));
  },
};
