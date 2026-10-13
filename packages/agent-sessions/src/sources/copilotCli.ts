/**
 * copilot-cli surface parser — spec v3.4.4.
 *
 * Source: <copilot-root>/session-state/<uuid>/{events.jsonl,workspace.yaml},
 * flat session-state/<uuid>.jsonl, legacy <copilot-root>/history-session-state/.
 * Roots scanned in order: $COPILOT_DIR, $COPILOT_HOME, ~/.copilot — all
 * existing roots merge; the same native id in >1 root is `duplicates`
 * (`cross-workspace-duplicate` when the workspace hash differs) and the
 * first readable copy wins.
 *
 * events.jsonl envelope: {id, parentId, timestamp, type, data}. Unknown
 * event types pass through with a counted `partial-parse` warning — they
 * never fail the session. A malformed last line is `truncated-tail`;
 * malformed mid-file lines are `partial-parse`. No message content, cwd or
 * git_root text, or raw exception text is ever emitted — paths only feed
 * workspaceHash().
 */
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import type { Dirent } from 'node:fs';
import { join } from 'node:path';
import { canonicalId, ephemeralKey, workspaceHash } from '../ids.ts';
import { result, warn } from '../model.ts';
import type {
  CollectEnv, CollectMode, ParseWarning, SessionMeta, SourceResult, SurfaceParser,
} from '../model.ts';

const SURFACE = 'copilot-cli' as const;
const STATE_DIRS = ['session-state', 'history-session-state'];
const JSONL_EXT = '.jsonl';

/** Event types observed in real session-state files (spec evidence list
 *  plus the extra types the reference parser knows). Anything else is
 *  pass-through and counted, never fatal. */
const KNOWN_TYPES = new Set([
  'session.start', 'session.shutdown', 'session.usage_checkpoint', 'session.model_change',
  'session.auto_mode_resolved', 'session.compaction_complete', 'session.error',
  'assistant.turn_start', 'assistant.turn_end', 'assistant.message', 'user.message',
  'system.message', 'tool.execution_start', 'tool.execution_complete',
  'permission.requested', 'permission.completed', 'hook.start', 'hook.end',
  'subagent.deselected',
]);

/** Top-level `key: value` scalars of a flat YAML file (nested blocks,
 *  lists and comments ignored — workspace.yaml is flat by contract). */
function readYamlScalars(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of text.split(/\r?\n/)) {
    const m = /^([A-Za-z_][\w-]*):[ \t]*(.*)$/.exec(line);
    if (m?.[1] === undefined) continue;
    let v = (m[2] ?? '').trim();
    if (!v || v === '|' || v === '>' || v === '~' || v === 'null') continue;
    if (v.startsWith('"') && v.endsWith('"') && v.length >= 2) {
      try { v = String(JSON.parse(v)); } catch { v = v.slice(1, -1); }
    } else if (v.startsWith("'") && v.endsWith("'") && v.length >= 2) {
      v = v.slice(1, -1).replace(/''/g, "'");
    } else v = v.replace(/\s+#.*$/, '');
    if (v) out[m[1]] = v;
  }
  return out;
}

/** workspaceHash seed normalization: trimmed, trailing separators stripped. */
function normalizeSeed(p: string): string {
  let s = p.trim();
  while (s.length > 1 && (s.endsWith('/') || s.endsWith('\\'))) s = s.slice(0, -1);
  return s;
}

function timestamp(v: unknown): string | null {
  if (typeof v === 'string' && v) return v;
  if (typeof v === 'number' && Number.isFinite(v)) return new Date(v).toISOString();
  return null;
}

interface Scan {
  status: 'ok' | 'unreadable' | 'unrecognized';
  events: Record<string, unknown>[];
  unknownTypes: number;
  badLines: number;
  truncatedTail: boolean;
}

function scanEventsFile(filePath: string): Scan {
  const scan: Scan = { status: 'ok', events: [], unknownTypes: 0, badLines: 0, truncatedTail: false };
  let text: string;
  try { text = readFileSync(filePath, 'utf8'); } catch { scan.status = 'unreadable'; return scan; }
  const lines = text.split(/\r?\n/);
  let last = lines.length - 1;
  while (last >= 0 && (lines[last] ?? '').trim() === '') last--;
  for (let i = 0; i <= last; i++) {
    const line = (lines[i] ?? '').trim();
    if (!line) continue;
    let obj: unknown;
    try { obj = JSON.parse(line); }
    catch {
      if (i === last) scan.truncatedTail = true; else scan.badLines++;
      continue;
    }
    const ev = obj as Record<string, unknown>;
    if (typeof ev.type !== 'string') { scan.badLines++; continue; } // valid JSON, wrong envelope
    if (!KNOWN_TYPES.has(ev.type)) scan.unknownTypes++;
    scan.events.push(ev);
  }
  // Lines present but zero recognizable events -> not copilot format.
  // An empty file is a session that wrote nothing — still recognizable.
  if (last >= 0 && scan.events.length === 0) scan.status = 'unrecognized';
  return scan;
}

interface Candidate {
  /** Native session id: the <uuid> directory or flat-file name. */
  nativeId: string;
  eventsPath: string;
  yamlPath: string | null;
  root: string;
}

function discover(root: string, candidates: Candidate[], ioErrors: { n: number }): void {
  for (const name of STATE_DIRS) {
    const stateDir = join(root, name);
    if (!existsSync(stateDir)) continue;
    let entries: Dirent[];
    try { entries = readdirSync(stateDir, { withFileTypes: true }); }
    catch { ioErrors.n++; continue; }
    for (const e of entries) {
      if (e.isDirectory()) {
        const eventsPath = join(stateDir, e.name, 'events.jsonl');
        if (!existsSync(eventsPath)) continue; // opened session, nothing typed yet
        const yamlPath = join(stateDir, e.name, 'workspace.yaml');
        candidates.push({ nativeId: e.name, eventsPath, yamlPath: existsSync(yamlPath) ? yamlPath : null, root });
      } else if (e.isFile() && e.name.endsWith(JSONL_EXT)) {
        candidates.push({ nativeId: e.name.slice(0, -JSONL_EXT.length), eventsPath: join(stateDir, e.name), yamlPath: null, root });
      }
    }
  }
}

function wsHashOf(ws: Record<string, string>): string | null {
  const seed = ws.git_root ?? ws.cwd;
  return seed ? workspaceHash(normalizeSeed(seed)) : null;
}

function toMeta(c: Candidate, scan: Scan): SessionMeta {
  const warnings: ParseWarning[] = [];
  const ws: Record<string, string> = {};
  if (c.yamlPath) {
    try { Object.assign(ws, readYamlScalars(readFileSync(c.yamlPath, 'utf8'))); }
    catch { warnings.push(warn('partial-parse', 'workspace metadata file unreadable')); }
  }
  let version: string | null = null;
  let started: string | null = null;
  let ended: string | null = null;
  let sawStart = false;
  for (const ev of scan.events) {
    const t = timestamp(ev.timestamp);
    started ??= t;
    if (ev.type === 'session.start' && !sawStart) {
      sawStart = true;
      started = t ?? started;
      const d = ev.data;
      const v = d && typeof d === 'object' ? (d as Record<string, unknown>).version : undefined;
      if (v !== undefined && v !== null) version = String(v);
    }
    if (ev.type === 'session.shutdown' && t) ended = t;
  }
  if (!sawStart) warnings.push(warn('missing-field', 'no session.start event'));
  else if (version === null) warnings.push(warn('missing-field', 'session.start has no version field'));
  if (started === null) warnings.push(warn('missing-field', 'no start timestamp determinable', version));
  if (ended === null) {
    warnings.push(scan.truncatedTail || scan.badLines > 0
      ? warn('no-end-marker', 'no session.shutdown; end marker may be lost', version)
      : warn('session-open', 'no session.shutdown event', version));
  }
  if (scan.truncatedTail) warnings.push(warn('truncated-tail', 'last line not valid JSON; skipped', version));
  if (scan.badLines > 0) warnings.push(warn('partial-parse', `${scan.badLines} malformed line(s) skipped`, version));
  if (scan.unknownTypes > 0) warnings.push(warn('partial-parse', `${scan.unknownTypes} event(s) had unrecognized type`, version));

  const wsHash = wsHashOf(ws);
  // Title only when the user explicitly renamed the session — never
  // derived from message content or generated summaries.
  const named = (ws.user_named ?? '').toLowerCase();
  const title = ['true', 'yes', '1'].includes(named) ? (ws.name ?? null) : null;
  const id = c.nativeId ? canonicalId(SURFACE, wsHash, 'native', c.nativeId) : null;
  if (id === null && wsHash === null) {
    warnings.push(warn('unknown-workspace', 'no stable session id or workspace identity', version));
  } else if (id === null) {
    warnings.push(warn('missing-field', 'no native session id determinable', version));
  }
  return {
    surface: SURFACE, id, display_key: '', // display_key assigned after final sort
    title, started_at: started, ended_at: ended, source_version: version,
    workspace_hash: wsHash, event_count: scan.events.length, parse_warnings: warnings,
  };
}

function collect(env: CollectEnv, _mode: CollectMode): SourceResult {
  const roots: string[] = [];
  const seenRoots = new Set<string>();
  for (const r of [env.env?.COPILOT_DIR, env.env?.COPILOT_HOME, join(env.home, '.copilot')]) {
    if (typeof r === 'string' && r && !seenRoots.has(r)) { seenRoots.add(r); roots.push(r); }
  }
  const existing = roots.filter((r) => existsSync(r));
  if (existing.length === 0) return result(SURFACE, 'source-not-found', []);

  const candidates: Candidate[] = [];
  const ioErrors = { n: 0 };
  for (const root of existing) discover(root, candidates, ioErrors);
  if (candidates.length === 0) return result(SURFACE, ioErrors.n > 0 ? 'read-error' : 'no-sessions', []);

  const topWarnings: ParseWarning[] = [];
  const sessions: SessionMeta[] = [];
  const seenIds = new Map<string, { root: string; wsHash: string | null }>();
  let unreadable = 0, unrecognized = 0, dupes = 0, crossWs = 0;
  for (const c of candidates) {
    const prior = seenIds.get(c.nativeId);
    if (prior) {
      if (prior.root !== c.root) {
        let h: string | null = null;
        if (c.yamlPath) {
          try { h = wsHashOf(readYamlScalars(readFileSync(c.yamlPath, 'utf8'))); } catch { /* unreadable dup */ }
        }
        if (h !== null && prior.wsHash !== null && h !== prior.wsHash) crossWs++; else dupes++;
      }
      continue; // first readable copy wins; same-root legacy dup is silent
    }
    const scan = scanEventsFile(c.eventsPath);
    if (scan.status === 'unreadable') { unreadable++; continue; }
    if (scan.status === 'unrecognized') { unrecognized++; continue; }
    const meta = toMeta(c, scan);
    seenIds.set(c.nativeId, { root: c.root, wsHash: meta.workspace_hash });
    sessions.push(meta);
  }
  if (dupes) topWarnings.push(warn('duplicates', `${dupes} duplicate session(s) across roots`));
  if (crossWs) topWarnings.push(warn('cross-workspace-duplicate', `${crossWs} session id(s) under a different workspace across roots`));
  if (unreadable + unrecognized > 0) topWarnings.push(warn('partial-parse', `${unreadable + unrecognized} session file(s) skipped`));
  if (sessions.length === 0) {
    return result(SURFACE, unreadable > 0 ? 'read-error' : 'unsupported-format', [], topWarnings);
  }
  sessions.sort((a, b) => (a.id ?? '').localeCompare(b.id ?? ''));
  sessions.forEach((s, i) => { s.display_key = ephemeralKey(SURFACE, i); });
  return result(SURFACE, 'ok', sessions, topWarnings);
}

export const copilotCliParser: SurfaceParser = { surface: SURFACE, collect };
