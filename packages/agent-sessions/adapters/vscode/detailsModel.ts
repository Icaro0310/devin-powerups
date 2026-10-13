/**
 * Details documents — pure markdown model behind the read-only
 * `agent-sessions:` virtual documents. Metadata only: titles, paths,
 * workspace names and message text are never rendered. `result` is
 * the owning source (its warnings are listed after the session's).
 */

import type { ParseWarning, SessionMeta, SourceResult } from '../../src/model.ts';
import { tail } from './chatModel.ts';

/** Full markdown for one session's virtual document. */
export function renderSessionDetails(meta: SessionMeta, result: SourceResult | undefined): string {
  const lines: string[] = [
    `# Session ${tail(meta.display_key, 12)}`,
    '',
    '| field | value |',
    '| --- | --- |',
    row('surface', meta.surface),
    row('id', meta.id ?? '(unstable)'),
    row('display_key', meta.display_key),
    row('started_at', meta.started_at ?? '(unknown)'),
    row('ended_at', meta.ended_at ?? 'open/unknown'),
    row('source_version', meta.source_version ?? '(unknown)'),
    row('workspace_hash', meta.workspace_hash ?? '(unknown)'),
    row('event_count', meta.event_count === null ? '(unknown)' : String(meta.event_count)),
    '',
    '## Parse warnings',
    '',
  ];
  const warnings = collectWarnings(meta, result);
  if (warnings.length === 0) {
    lines.push('_none_');
  } else {
    for (const w of warnings) lines.push(`- \`${w.code}\` — ${w.message}`);
  }
  lines.push('', '---', '_Metadata only — session titles and message content are never rendered, by policy._');
  return lines.join('\n') + '\n';
}

/** Session warnings first, then owning-source warnings; deduped. */
export function collectWarnings(meta: SessionMeta, result: SourceResult | undefined): ParseWarning[] {
  const seen = new Set<string>();
  const out: ParseWarning[] = [];
  for (const w of [...meta.parse_warnings, ...(result?.warnings ?? [])]) {
    const k = `${w.code} ${w.message}`;
    if (!seen.has(k)) {
      seen.add(k);
      out.push(w);
    }
  }
  return out;
}

function cell(value: string): string {
  return value.replaceAll('|', '\\|');
}

function row(field: string, value: string): string {
  return `| ${field} | ${cell(value)} |`;
}
