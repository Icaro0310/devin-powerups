// Minimal 'vscode' runtime stub — activation smoke tests only (test/, never shipped).
// Records every registration; exercises providers once so wiring bugs surface.

export const registered = { views: [], commands: [], providers: [], participants: [], docs: [] };

export class EventEmitter {
  constructor() { this.listeners = []; }
  get event() { return (l) => { this.listeners.push(l); return { dispose() {} }; }; }
  fire(e) { for (const l of this.listeners) l(e); }
  dispose() {}
}
export class TreeItem {
  constructor(label, collapsibleState) { this.label = label; this.collapsibleState = collapsibleState; }
}
export class ThemeIcon {
  constructor(id) { this.id = id; }
}
export class MarkdownString {
  constructor(v) { this.value = v; }
}
export const TreeItemCollapsibleState = { None: 0, Collapsed: 1, Expanded: 2 };
export const ViewColumn = { Beside: 2 };

export const Uri = {
  parse(s) {
    const i = s.indexOf(':');
    const rawPath = s.slice(i + 1);
    let path = rawPath;
    try { path = decodeURIComponent(rawPath); } catch { /* keep raw */ }
    return { scheme: s.slice(0, i), path, toString: () => s };
  },
};

export const window = {
  createTreeView(viewId, opts) {
    registered.views.push({ viewId, provider: opts.treeDataProvider });
    return { dispose() {} };
  },
  async showTextDocument(doc, _opts) { registered.docs?.push?.(doc.uri.toString()); return { document: doc }; },
};

export const workspace = {
  registerTextDocumentContentProvider(scheme, provider) {
    registered.providers.push({ scheme, provider });
    return { dispose() {} };
  },
  async openTextDocument(uri) {
    const p = registered.providers.find((p) => p.scheme === uri.scheme);
    return { uri, getText: () => (p ? p.provider.provideTextDocumentContent(uri) : '') };
  },
};

export const commands = {
  registerCommand(id, fn) { registered.commands.push({ id, fn }); return { dispose() {} }; },
  async executeCommand(id, ...args) {
    const c = registered.commands.find((c) => c.id === id);
    return c ? c.fn(...args) : undefined;
  },
};

export const chat = {
  createChatParticipant(id, handler) {
    registered.participants.push({ id, handler });
    return { id, requestHandler: handler, dispose() {} };
  },
};
