/**
 * Details documents — vscode glue: `agent-sessions:Session/<key>.md`
 * read-only virtual documents. Rendering lives in detailsModel.ts
 * (pure); this file only maps URIs to collected sessions.
 */

import * as vscode from 'vscode';
import type { SessionMeta, SourceResult } from '../../src/model.ts';
import { renderSessionDetails } from './detailsModel.ts';

/** URI scheme for session detail documents. */
export const DETAILS_SCHEME = 'agent-sessions';

/** `agent-sessions:Session/<key>.md` — key is percent-encoded. */
export function detailsUri(displayKey: string): vscode.Uri {
  return vscode.Uri.parse(`${DETAILS_SCHEME}:Session/${encodeURIComponent(displayKey)}.md`);
}

interface Found {
  meta: SessionMeta;
  result: SourceResult;
}

export class SessionDetailsProvider implements vscode.TextDocumentContentProvider {
  /** Registration scheme — read by extension.ts. */
  static readonly scheme: string = DETAILS_SCHEME;

  constructor(private readonly getResults: () => SourceResult[]) {}

  provideTextDocumentContent(uri: vscode.Uri): string {
    const found = this.find(keyCandidates(uri));
    if (found === undefined) {
      return '# Session not found\n\nNo collected session matches this document — the session set may have changed. Run **Agent Sessions: Refresh** and reopen.\n';
    }
    return renderSessionDetails(found.meta, found.result);
  }

  /** Match on display_key across all results first, then canonical id. */
  private find(keys: readonly string[]): Found | undefined {
    const results = this.getResults();
    for (const result of results) {
      for (const s of result.sessions) {
        if (keys.includes(s.display_key)) return { meta: s, result };
      }
    }
    for (const result of results) {
      for (const s of result.sessions) {
        if (s.id !== null && keys.includes(s.id)) return { meta: s, result };
      }
    }
    return undefined;
  }
}

/** `uri.path` arrives percent-decoded; decoding the basename again
 *  covers undecoded callers — we match on both so ids containing a
 *  literal `%` still resolve. */
function keyCandidates(uri: vscode.Uri): string[] {
  const seg = uri.path.slice(uri.path.lastIndexOf('/') + 1);
  const base = seg.endsWith('.md') ? seg.slice(0, -3) : seg;
  let decoded = base;
  try {
    decoded = decodeURIComponent(base);
  } catch {
    // malformed escape — keep the raw basename
  }
  return decoded === base ? [base] : [decoded, base];
}
