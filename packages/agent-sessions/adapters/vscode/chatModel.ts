/**
 * `@sessions` chat answers — pure markdown model, no vscode imports.
 * Metadata-only contract: surfaces, states, counts, workspace hashes
 * and session keys. Titles, paths, workspace names and message text
 * are never emitted (`title` is ignored even when a fixture sets it).
 * Warning messages are pre-sanitized templates — safe to render.
 */

import type { ParseWarning, SessionMeta, SourceResult } from '../../src/model.ts';

/** Max sessions rendered for a filtered query. */
const LIST_CAP = 20;
/** Max warning bullets per surface in the overview. */
const WARNING_CAP = 3;

/** Answer one chat prompt with metadata-only markdown. */
export function answer(prompt: string, results: SourceResult[]): string {
  const query = prompt.trim().toLowerCase();
  if (query === '') return renderOverview(results);
  const matches = matchSessions(query, results);
  if (matches.length === 0) {
    return 'no sessions match — try a surface name, workspace hash or session key';
  }
  const lines = matches.slice(0, LIST_CAP).map(formatSessionLine);
  const hidden = matches.length - LIST_CAP;
  if (hidden > 0) lines.push(`_…${hidden} more — refine the filter_`);
  return lines.join('\n');
}

/** Empty-prompt overview: one line per surface, warnings bulleted. */
export function renderOverview(results: SourceResult[]): string {
  const lines: string[] = [];
  for (const r of results) {
    const warnings = allWarnings(r);
    const total = r.warnings.length + r.sessions.reduce((sum, s) => sum + s.parse_warnings.length, 0);
    const n = r.sessions.length;
    let line = `- **${r.surface}**: ${r.state} — ${n} session${n === 1 ? '' : 's'}`;
    if (total > 0) line += ` · ${total} warning${total === 1 ? '' : 's'}`;
    lines.push(line);
    for (const { w, count } of warnings.slice(0, WARNING_CAP)) {
      lines.push(`  - ${w.message}${count > 1 ? ` (×${count})` : ''}`);
    }
    const extra = warnings.length - WARNING_CAP;
    if (extra > 0) lines.push(`  - _…${extra} more kinds_`);
  }
  lines.push('_metadata-only view — session titles and message content are suppressed by policy_');
  return lines.join('\n');
}

/** Sessions whose surface, display_key, canonical id or workspace
 *  hash contains the query (case-insensitive). Newest first — same
 *  ordering as the tree, so a capped answer keeps the recent rows. */
export function matchSessions(query: string, results: SourceResult[]): SessionMeta[] {
  const q = query.toLowerCase();
  const out: SessionMeta[] = [];
  for (const r of results) {
    for (const s of r.sessions) {
      const hit =
        s.surface.includes(q) ||
        s.display_key.toLowerCase().includes(q) ||
        (s.id !== null && s.id.toLowerCase().includes(q)) ||
        (s.workspace_hash !== null && s.workspace_hash.toLowerCase().includes(q));
      if (hit) out.push(s);
    }
  }
  out.sort((a, b) => (b.started_at ?? '').localeCompare(a.started_at ?? ''));
  return out;
}

/** One compact row: `- 2026-10-01 14:32 · copilot-cli · ws:1a2b3c4d · …99ab12`. */
export function formatSessionLine(s: SessionMeta): string {
  const ws = s.workspace_hash === null ? 'ws:(unknown)' : `ws:${s.workspace_hash.slice(0, 8)}`;
  return `- ${formatLocal(s.started_at)} · ${s.surface} · ${ws} · ${tail(s.display_key, 12)}`;
}

/** Local `YYYY-MM-DD HH:MM`; `unknown-time` when not determinable. */
export function formatLocal(iso: string | null): string {
  const d = iso === null ? null : new Date(iso);
  if (d === null || Number.isNaN(d.getTime())) return 'unknown-time';
  const p = (n: number): string => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

/** Last `n` chars, prefixed with `…` when truncated. */
export function tail(value: string, n: number): string {
  return value.length > n ? `…${value.slice(-n)}` : value;
}

/** Source-level + session-level warnings, deduped by code+message,
 *  with each distinct kind carrying its occurrence count. */
function allWarnings(r: SourceResult): { w: ParseWarning; count: number }[] {
  const seen = new Map<string, { w: ParseWarning; count: number }>();
  for (const w of [...r.warnings, ...r.sessions.flatMap(s => s.parse_warnings)]) {
    const k = `${w.code} ${w.message}`;
    const e = seen.get(k);
    if (e) e.count++; else seen.set(k, { w, count: 1 });
  }
  return [...seen.values()];
}
