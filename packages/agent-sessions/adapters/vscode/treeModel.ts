/**
 * TreeView pure model — node list + label/description/tooltip text for the
 * sessions tree. No `vscode` import: unit-testable in plain Node.
 * Zero content exposure: `title` is suppressed by policy and never read;
 * warning messages are pre-sanitized templates rendered verbatim.
 */
import type {
  ParseWarning, SessionMeta, SessionState, SourceResult, Surface,
} from '../../src/model.ts';

export type SessionNode =
  | { kind: 'surface'; surface: Surface; state: SessionState; sessionCount: number; warningCount: number }
  | { kind: 'session'; meta: SessionMeta };

/** Stable root order — mirrors the parser registry (sources/index.ts). */
export const SURFACE_ORDER: readonly Surface[] = ['copilot-cli', 'codex-cli', 'vscode-chat', 'devin-cli'];

const KEY_TAIL = 12;
const WS_HEAD = 8;
const UNKNOWN_DATE = 'unknown date';

function surfaceRank(surface: Surface): number {
  const i = SURFACE_ORDER.indexOf(surface);
  return i === -1 ? SURFACE_ORDER.length : i;
}

/** Root level: one surface node per SourceResult, in registry order.
 *  Empty/unavailable surfaces are nodes too — their state is shown. */
export function buildSessionTree(results: SourceResult[]): SessionNode[] {
  return [...results]
    .sort((a, b) => surfaceRank(a.surface) - surfaceRank(b.surface))
    .map(r => ({
      kind: 'surface' as const,
      surface: r.surface,
      state: r.state,
      sessionCount: r.sessions.length,
      warningCount: r.warnings.length,
    }));
}

/** Epoch ms for an ISO timestamp; null/unparseable -> null (sorts last). */
function epochMs(iso: string | null): number | null {
  if (iso === null) return null;
  const t = Date.parse(iso);
  return Number.isNaN(t) ? null : t;
}

/** Children of one surface: sessions by `started_at` descending, nulls
 *  last. Sort is stable — equal/absent keys keep parser order. */
export function surfaceChildren(result: SourceResult): SessionNode[] {
  return [...result.sessions]
    .sort((a, b) => {
      const ta = epochMs(a.started_at);
      const tb = epochMs(b.started_at);
      if (ta === null && tb === null) return 0;
      if (ta === null) return 1;
      if (tb === null) return -1;
      return tb - ta;
    })
    .map(meta => ({ kind: 'session' as const, meta }));
}

const pad2 = (n: number): string => String(n).padStart(2, '0');

/** `YYYY-MM-DD HH:MM` in local time; `unknown date` when absent/bad. */
export function formatLocalDateTime(iso: string | null): string {
  const t = epochMs(iso);
  if (t === null) return UNKNOWN_DATE;
  const d = new Date(t);
  const day = `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
  return `${day} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

/** Last KEY_TAIL chars of a display key, `…`-prefixed when truncated. */
export function shortDisplayKey(displayKey: string): string {
  return displayKey.length > KEY_TAIL ? `…${displayKey.slice(-KEY_TAIL)}` : displayKey;
}

/** Pre-sanitized warning as one line: `[code] message` — verbatim. */
function warnLine(w: ParseWarning): string {
  return `[${w.code}] ${w.message}`;
}

const hasCode = (meta: SessionMeta, code: ParseWarning['code']): boolean =>
  meta.parse_warnings.some(w => w.code === code);

/** Session row label: local start time only — `title` never rendered. */
export function sessionLabel(meta: SessionMeta): string {
  return formatLocalDateTime(meta.started_at);
}

/** Short discriminator: `ws:<hash8>` + truncated key + `· open` marker. */
export function sessionDescription(meta: SessionMeta): string {
  const parts: string[] = [];
  if (meta.workspace_hash !== null && meta.workspace_hash !== '') {
    parts.push(`ws:${meta.workspace_hash.slice(0, WS_HEAD)}`);
  }
  parts.push(shortDisplayKey(meta.display_key));
  if (hasCode(meta, 'session-open')) parts.push('open');
  return parts.join(' · ');
}

/** Session tooltip lines: surface, times, event count, warnings. */
export function sessionTooltip(meta: SessionMeta): string[] {
  const lines = [
    `surface: ${meta.surface}`,
    `started: ${formatLocalDateTime(meta.started_at)}`,
    `ended: ${formatLocalDateTime(meta.ended_at)}`,
  ];
  if (meta.event_count !== null) lines.push(`events: ${meta.event_count}`);
  for (const w of meta.parse_warnings) lines.push(warnLine(w));
  return lines;
}

/** Surface row label: the surface name itself. */
export function surfaceLabel(result: SourceResult): string {
  return result.surface;
}

/** `<n> sessions`; the state itself when the surface has none. */
export function surfaceDescription(result: SourceResult): string {
  return result.sessions.length === 0 ? result.state : `${result.sessions.length} sessions`;
}

/** Surface tooltip lines: surface, state, count, result-level warnings. */
export function surfaceTooltip(result: SourceResult): string[] {
  const lines = [
    `surface: ${result.surface}`,
    `state: ${result.state}`,
    `sessions: ${result.sessions.length}`,
  ];
  for (const w of result.warnings) lines.push(warnLine(w));
  return lines;
}

/** TreeItem contextValue — `session` rows carry the openDetails menu. */
export function contextValue(node: SessionNode): 'surface' | 'session' {
  return node.kind;
}

/** ThemeIcon id per node/state (pure so the mapping stays testable). */
export function iconId(node: SessionNode): string {
  if (node.kind === 'session') {
    return node.meta.parse_warnings.length > 0 ? 'warning' : 'comment-discussion';
  }
  switch (node.state) {
    case 'ok': return 'check';
    case 'partial': case 'no-sessions': return 'info';
    case 'source-not-found': return 'circle-slash';
    case 'read-error': case 'unsupported-format': return 'error';
  }
}
