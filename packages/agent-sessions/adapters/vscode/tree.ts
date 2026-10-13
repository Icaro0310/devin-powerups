/**
 * VS Code TreeView glue — thin adapter over the pure treeModel layer.
 * Owns the change emitter, collapsible state, ThemeIcons and the click
 * command; all ordering/text/icon decisions live in treeModel.ts.
 */
import * as vscode from 'vscode';
import type { SessionMeta, SourceResult, Surface } from '../../src/model.ts';
import {
  buildSessionTree, contextValue, iconId, sessionDescription, sessionLabel,
  sessionTooltip, surfaceChildren, surfaceDescription, surfaceLabel, surfaceTooltip,
} from './treeModel.ts';
import type { SessionNode } from './treeModel.ts';

type SurfaceNode = Extract<SessionNode, { kind: 'surface' }>;

/** TreeDataProvider for `agentSessions.sessions`. Reads the latest
 *  SourceResult[] via `getResults` on every render — call `refresh()`
 *  after the underlying results are re-collected. */
export class SessionsTreeProvider implements vscode.TreeDataProvider<SessionNode> {
  private readonly emitter = new vscode.EventEmitter<SessionNode | undefined | null | void>();
  readonly onDidChangeTreeData: vscode.Event<SessionNode | undefined | null | void> = this.emitter.event;

  constructor(private readonly getResults: () => SourceResult[]) {}

  /** Signal a full re-render after the results array was replaced. */
  refresh(): void {
    this.emitter.fire(undefined);
  }

  getChildren(element?: SessionNode): SessionNode[] {
    if (element === undefined) return buildSessionTree(this.getResults());
    if (element.kind !== 'surface') return [];
    const result = this.surfaceResult(element.surface);
    return result === undefined ? [] : surfaceChildren(result);
  }

  getTreeItem(element: SessionNode): vscode.TreeItem {
    return element.kind === 'surface' ? this.surfaceItem(element) : this.sessionItem(element.meta);
  }

  private surfaceResult(surface: Surface): SourceResult | undefined {
    return this.getResults().find(r => r.surface === surface);
  }

  private surfaceItem(node: SurfaceNode): vscode.TreeItem {
    const result = this.surfaceResult(node.surface);
    const item = new vscode.TreeItem(
      result ? surfaceLabel(result) : node.surface,
      vscode.TreeItemCollapsibleState.Expanded,
    );
    item.contextValue = contextValue(node);
    item.iconPath = new vscode.ThemeIcon(iconId(node));
    item.description = result ? surfaceDescription(result) : node.state;
    if (result) item.tooltip = surfaceTooltip(result).join('\n');
    return item;
  }

  private sessionItem(meta: SessionMeta): vscode.TreeItem {
    const node: SessionNode = { kind: 'session', meta };
    const item = new vscode.TreeItem(sessionLabel(meta), vscode.TreeItemCollapsibleState.None);
    item.contextValue = contextValue(node);
    item.description = sessionDescription(meta);
    item.tooltip = sessionTooltip(meta).join('\n');
    item.iconPath = new vscode.ThemeIcon(iconId(node));
    item.command = {
      command: 'agentSessions.openDetails',
      title: 'Open Details',
      arguments: [meta.display_key],
    };
    return item;
  }
}
