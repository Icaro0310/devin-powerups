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

  private readonly emitter = new vscode.EventEmitter<vscode.Uri>();
  readonly onDidChange: vscode.Event<vscode.Uri> = this.emitter.event;
  private readonly opened = new Set<string>();

  constructor(private readonly getResults: () => SourceResult[]) {}

  provideTextDocumentContent(uri: vscode.Uri): string {
    this.opened.add(uri.toString());
    const found = this.find(keyCandidates(uri));
    if (found === undefined) {
      return '# Session not found\n\nNo collected session matches this document — the session set may have changed. Run **Agent Sessions: Refresh** and reopen.\n';
    }
    return renderSessionDetails(found.meta, found.result);
  }

  /** Re-request content for every opened details document — ephemeral
   *  keys are positional, so a refresh can rebind a URI to another
   *  session; without onDidChange VS Code serves the cached text. */
  refresh(): void {
    for (const raw of this.opened) this.emitter.fire(vscode.Uri.parse(raw));
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

/** `uri.path` arrives already percent-decoded by VS Code — the basename
 *  IS the display key. Decoding it again can collide with a different
 *  canonical key (a `:` vs a literal `%3A` native id), so never re-decode. */
function keyCandidates(uri: vscode.Uri): string[] {
  const seg = uri.path.slice(uri.path.lastIndexOf('/') + 1);
  const base = seg.endsWith('.md') ? seg.slice(0, -3) : seg;
  return [base];
}
