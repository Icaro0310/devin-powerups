/**
 * Extension entry — agent-sessions (icaro0310.agent-sessions).
 * Wiring only: builds the real CollectEnv from the extension host,
 * runs the canonical collect, and registers the contributed surfaces
 * (TreeView = primary UI, `@sessions` chat participant = secondary,
 * read-only details documents). No parsing logic lives here.
 *
 * Local-first contract: synchronous stdlib reads only — no network,
 * no writes to agent storage, no telemetry.
 */
import * as os from 'node:os';
import * as vscode from 'vscode';
import type { CollectEnv, SourceResult } from '../../src/model.ts';
import { collectAll } from '../../src/sources/index.ts';
import { SessionsTreeProvider } from './tree.ts';
import type { SessionNode } from './treeModel.ts';
import { createSessionsParticipant } from './chat.ts';
import { SessionDetailsProvider, detailsUri } from './details.ts';

/** Real host environment for the parsers. `appdata` is only meaningful
 *  on Windows roaming profiles; elsewhere the parsers derive their own
 *  per-platform config dirs from `home`. */
export function collectEnvForHost(): CollectEnv {
  const env: CollectEnv = {
    home: os.homedir(),
    platform: process.platform,
    env: process.env,
  };
  if (typeof process.env.APPDATA === 'string' && process.env.APPDATA) {
    env.appdata = process.env.APPDATA;
  }
  return env;
}

export function activate(context: vscode.ExtensionContext): void {
  // Last canonical collect; refreshed on demand by the refresh command.
  let results: SourceResult[] = collectAll(collectEnvForHost(), 'metadata');
  const getResults = (): SourceResult[] => results;
  const refresh = (): void => {
    results = collectAll(collectEnvForHost(), 'metadata');
    treeProvider.refresh();
    detailsProvider.refresh(); // re-render open details docs — ephemeral keys are positional
  };

  const treeProvider = new SessionsTreeProvider(getResults);
  const treeView = vscode.window.createTreeView('agentSessions.sessions', {
    treeDataProvider: treeProvider,
    showCollapseAll: true,
  });

  const detailsProvider = new SessionDetailsProvider(getResults);
  const detailsReg = vscode.workspace.registerTextDocumentContentProvider(
    SessionDetailsProvider.scheme,
    detailsProvider,
  );

  const participant = createSessionsParticipant(getResults);

  context.subscriptions.push(
    treeView,
    detailsReg,
    participant,
    vscode.commands.registerCommand('agentSessions.refresh', refresh),
    vscode.commands.registerCommand('agentSessions.openDetails', async (arg?: string | SessionNode) => {
      // Row click passes the display key; the context menu passes the node.
      const displayKey = typeof arg === 'string'
        ? arg
        : arg?.kind === 'session' ? arg.meta.display_key : undefined;
      if (!displayKey) return;
      const doc = await vscode.workspace.openTextDocument(detailsUri(displayKey));
      await vscode.window.showTextDocument(doc, { preview: true, viewColumn: vscode.ViewColumn.Beside });
    }),
  );
}

export function deactivate(): void {
  // nothing held open — parsers are synchronous and stateless
}
