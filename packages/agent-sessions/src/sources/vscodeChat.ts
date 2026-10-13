/**
 * vscode-chat surface — VS Code Chat session metadata collector.
 *
 * Layout (variants may coexist; <base> = env.appdata, else AppData/Roaming
 * on win32, Library/Application Support on darwin, .config under env.home):
 *   <base>/<Variant>/User/workspaceStorage/<wsDir>/chatSessions/<id>.{json,jsonl}
 *   <base>/<Variant>/User/globalStorage/{emptyWindow,transferred}ChatSessions/<id>.{json,jsonl}
 *   <env.home>/.vscode-server/data/User/...                       (remote server)
 * The <wsDir> name is already VS Code's stable workspace hash — used
 * verbatim as workspace_hash; global sessions get workspace_hash null.
 *
 * A .json file holds the final session snapshot; a .jsonl file is a
 * mutation log replayed in order — kind 0 replaces the document, kind 1
 * sets the value at path k, kind 2 appends v to the array at k (first
 * truncating it to index i when given), kind 3 deletes k. When both
 * exist for one id the .jsonl wins; unknown kinds are counted and a
 * trailing unparseable line flags truncated-tail. Privacy: only metadata
 * leaves this file — no message text, workspace names or raw errors.
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import { canonicalId, ephemeralKey } from '../ids.ts';
import { result, warn } from '../model.ts';
import type { CollectEnv, CollectMode, ParseWarning, SessionMeta, SourceResult, SurfaceParser } from '../model.ts';

const SURFACE = 'vscode-chat' as const;
const isObject = (v: unknown): v is Record<string, any> => !!v && typeof v === 'object' && !Array.isArray(v);
const isChatFile = (n: string) => n.endsWith('.jsonl') || n.endsWith('.json');
/** Document keys that mark a recognizable VS Code chat session object. */
const KNOWN_KEYS = ['requests', 'customTitle', 'title', 'creationDate', 'lastMessageDate',
  'version', 'requesterUsername', 'responderUsername', 'sessionId', 'initialLocation', 'isImported', 'agent'];
const recognizable = (doc: Record<string, any>) => KNOWN_KEYS.some((k) => k in doc);

// ---------- discovery ----------

function isDir(p: string): boolean {
  try { return fs.statSync(p).isDirectory(); } catch { return false; }
}
function readdirSafe(dir: string): fs.Dirent[] {
  try { return fs.readdirSync(dir, { withFileTypes: true }); } catch { return []; }
}

/** Candidate <...>/User dirs of every VS Code variant. */
function userDirs(env: CollectEnv): string[] {
  const base = env.appdata ?? (
    env.platform === 'win32' ? path.join(env.home, 'AppData', 'Roaming')
      : env.platform === 'darwin' ? path.join(env.home, 'Library', 'Application Support')
        : path.join(env.home, '.config'));
  return [
    ...['Code', 'Code - Insiders'].map((n) => path.join(base, n, 'User')),
    path.join(env.home, '.vscode-server', 'data', 'User'),
  ];
}

interface ChatFile { filePath: string; id: string; wsHash: string | null }

/** Chat logs in one folder; for one id the .jsonl is current, the .json stale. */
function chatLogs(dir: string, wsHash: string | null): ChatFile[] {
  const byId = new Map<string, ChatFile>();
  for (const e of readdirSafe(dir)) {
    if (!e.isFile() || !isChatFile(e.name)) continue;
    const id = e.name.replace(/\.jsonl?$/, '');
    if (id && (!byId.has(id) || e.name.endsWith('.jsonl'))) {
      byId.set(id, { filePath: path.join(dir, e.name), id, wsHash });
    }
  }
  return [...byId.values()];
}

function discover(userDir: string): ChatFile[] {
  const files = ['emptyWindowChatSessions', 'transferredChatSessions']
    .flatMap((n) => chatLogs(path.join(userDir, 'globalStorage', n), null));
  for (const e of readdirSafe(path.join(userDir, 'workspaceStorage'))) {
    if (e.isDirectory()) files.push(...chatLogs(path.join(userDir, 'workspaceStorage', e.name, 'chatSessions'), e.name));
  }
  return files;
}

// ---------- mutation replay (.jsonl) / snapshot (.json) ----------

/** The container at `keys` in `root`, creating objects/arrays along the way. */
const UNSAFE_KEYS = new Set(['__proto__', 'prototype', 'constructor']);

function walk(root: Record<string, any>, keys: (string | number)[]): any {
  let cur: any = root;
  for (let i = 0; i < keys.length; i++) {
    const key = keys[i]!;
    if (cur === null || typeof cur !== 'object') return undefined;
    if (cur[key] === null || typeof cur[key] !== 'object') {
      cur[key] = typeof keys[i + 1] === 'number' ? [] : {};
    }
    cur = cur[key];
  }
  return cur;
}

interface Rebuild { doc: Record<string, any>; unknownKinds: number; badTail: boolean; corrupt: boolean }

/** Rebuilds a session document from a snapshot or a mutation log. */
function rebuild(text: string): Rebuild {
  const trimmed = text.trim();
  if (trimmed.startsWith('{')) {
    try {
      const whole: unknown = JSON.parse(trimmed);
      if (isObject(whole) && typeof whole.kind !== 'number') {
        return { doc: whole, unknownKinds: 0, badTail: false, corrupt: false };
      }
    } catch { /* not a single document — treat as mutation log */ }
  }
  let state: Record<string, any> = {}, unknownKinds = 0, badTail = false, parsedLines = 0;
  const lines = text.split('\n');
  let lastLine = -1;
  for (let i = lines.length - 1; i >= 0; i--) if (lines[i]!.trim()) { lastLine = i; break; }
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]!.trim();
    if (!line) continue;
    let r: any;
    try { r = JSON.parse(line); parsedLines++; } catch {
      if (i === lastLine) badTail = true; // partially written tail; mid-log lines are skipped
      continue;
    }
    if (!isObject(r)) continue;
    const k = Array.isArray(r.k) ? r.k.filter((p: unknown) => typeof p === 'string' || typeof p === 'number') : [];
    if (k.some((p) => typeof p === 'string' && UNSAFE_KEYS.has(p))) { unknownKinds++; continue; }
    const last = k[k.length - 1];
    const parent = () => walk(state, k.slice(0, -1));
    switch (r.kind) {
      case 0: if (isObject(r.v)) state = r.v; break;
      case 1: {
        if (!k.length) { if (isObject(r.v)) state = r.v; break; }
        const p = parent();
        if (p && typeof p === 'object') p[last!] = r.v;
        break;
      }
      case 2: {
        const p = parent();
        if (!p || typeof p !== 'object') break;
        let arr = k.length ? p[last!] : undefined;
        if (!Array.isArray(arr)) {
          if (!k.length) break;
          arr = p[last!] = [];
        }
        const items = Array.isArray(r.v) ? r.v : r.v === undefined ? [] : [r.v];
        if (typeof r.i === 'number' && r.i >= 0 && r.i <= arr.length) arr.splice(r.i, arr.length - r.i, ...items);
        else arr.push(...items);
        break;
      }
      case 3: {
        if (!k.length) break;
        const p = parent();
        if (Array.isArray(p) && typeof last === 'number') { if (last >= 0) p.splice(last, 1); }
        else if (p && typeof p === 'object') delete p[last!];
        break;
      }
      default: unknownKinds++;
    }
  }
  return { doc: state, unknownKinds, badTail, corrupt: !parsedLines && trimmed.length > 0 };
}

// ---------- metadata ----------

function numericTime(v: unknown): number | undefined {
  if (typeof v === 'number' && Number.isFinite(v) && v > 0) return v;
  if (typeof v === 'string') { const t = Date.parse(v); return Number.isNaN(t) ? undefined : t; }
  return undefined;
}

function metaOf(rb: Rebuild, f: ChatFile): SessionMeta {
  const w: ParseWarning[] = [];
  if (rb.unknownKinds) w.push(warn('unsupported-mutation', `${rb.unknownKinds} mutation(s) with unknown kind skipped`));
  if (rb.badTail) w.push(warn('truncated-tail', 'trailing mutation line discarded (unparseable)'));
  const doc = rb.doc, requests = Array.isArray(doc.requests) ? doc.requests : [];
  const times: number[] = [];
  const push = (v: unknown) => { const t = numericTime(v); if (t !== undefined) times.push(t); };
  for (const v of [doc.creationDate, doc.lastMessageDate]) push(v);
  let lastReq: Record<string, any> | undefined;
  for (const r of requests) {
    if (!isObject(r)) continue;
    lastReq = r;
    push(r.timestamp);
    push(r.responseTimestamp);
    push(r.modelState?.completedAt);
    const t = numericTime(r.timestamp);
    const elapsed = numericTime(r.result?.timings?.totalElapsed);
    if (t !== undefined && elapsed !== undefined) times.push(t + elapsed);
  }
  const completed = lastReq && (numericTime(lastReq.responseTimestamp) !== undefined
    || numericTime(lastReq.modelState?.completedAt) !== undefined
    || isObject(lastReq.result) || lastReq.isCanceled === true);
  if (!times.length) w.push(warn('missing-field', 'session document has no timestamps'));
  else if (!lastReq) w.push(warn('no-end-marker', 'no requests recorded; session end not determinable'));
  else if (!completed) w.push(warn('session-open', 'last request has no completion marker; session may be open'));
  const version = typeof doc.version === 'number' || typeof doc.version === 'string' ? String(doc.version) : null;
  if (version === null) w.push(warn('missing-field', 'session document has no version field'));
  if (!f.wsHash) w.push(warn('unknown-workspace', 'no stable workspace identity; session not deduplicated'));
  const ended = completed && times.length ? new Date(Math.max(...times)).toISOString() : null;
  return {
    surface: SURFACE,
    id: f.wsHash ? canonicalId(SURFACE, f.wsHash, 'native', f.id) : null,
    display_key: '',
    title: null, // auto-generated titles embed first-prompt text (verified on real data) — content-derived; customTitle not distinguishable
    started_at: times.length ? new Date(Math.min(...times)).toISOString() : null,
    ended_at: ended,
    source_version: version,
    workspace_hash: f.wsHash,
    event_count: requests.length,
    parse_warnings: w,
  };
}

// ---------- collect ----------

function collect(env: CollectEnv, _mode: CollectMode): SourceResult {
  const roots = userDirs(env).filter(isDir);
  if (!roots.length) return result(SURFACE, 'source-not-found', []);
  const files = roots.flatMap(discover);
  if (!files.length) return result(SURFACE, 'no-sessions', []);

  const seenIds = new Set<string>();
  const parsed: { meta: SessionMeta; dir: string; sid: string }[] = [];
  let unreadable = 0, unrecognized = 0, dropped = 0;
  for (const f of files) {
    let text: string;
    try { text = fs.readFileSync(f.filePath, 'utf8'); } catch { unreadable++; continue; }
    const rb = rebuild(text);
    if (rb.corrupt) { unreadable++; continue; }
    if (!recognizable(rb.doc)) { unrecognized++; continue; }
    const meta = metaOf(rb, f);
    if (meta.id && seenIds.has(meta.id)) { dropped++; continue; }
    if (meta.id) seenIds.add(meta.id);
    parsed.push({ meta, dir: path.dirname(f.filePath), sid: f.id });
  }
  // Same session id in >1 storage dir: keep all entries, flag each.
  const locs = new Map<string, Set<string>>();
  for (const p of parsed) (locs.get(p.sid) ?? locs.set(p.sid, new Set()).get(p.sid)!).add(p.dir);
  for (const p of parsed) {
    const n = locs.get(p.sid)!.size;
    if (n > 1) p.meta.parse_warnings.push(warn('cross-workspace-duplicate', `session id present in ${n} storage locations`));
  }
  const sessions = parsed.map((p) => p.meta)
    .sort((a, b) => (b.ended_at ?? b.started_at ?? '').localeCompare(a.ended_at ?? a.started_at ?? ''));
  sessions.forEach((s, i) => { s.display_key = ephemeralKey(SURFACE, i); });

  const warnings: ParseWarning[] = [];
  if (unreadable) warnings.push(warn('partial-parse', `${unreadable} session file(s) unreadable`));
  if (unrecognized) warnings.push(warn('partial-parse', `${unrecognized} session document(s) have unrecognized structure`));
  if (dropped) warnings.push(warn('duplicates', `${dropped} duplicate session(s) dropped`));
  const state = sessions.length ? 'ok' : unreadable ? 'read-error' : 'unsupported-format';
  return result(SURFACE, state, sessions, warnings);
}

export const vscodeChatParser: SurfaceParser = { surface: SURFACE, collect };
