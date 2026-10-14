// Activation smoke test — runs the COMPILED extension entry against the
// vscode stub and exercises every registered surface once.
// Prereq: npm run build. Usage: node --import ./test/vscode-loader-import.mjs test/smoke-activate.mjs
import assert from 'node:assert/strict';
const vscode = await import('vscode');
const ext = await import('../out/adapters/vscode/extension.js');

const subscriptions = [];
ext.activate({ subscriptions });

const r = vscode.registered;
assert.deepEqual(r.views.map((v) => v.viewId), ['agentSessions.sessions'], 'tree view registered');
assert.deepEqual(r.participants.map((p) => p.id), ['agent-sessions.sessions'], 'participant id matches manifest');
assert.deepEqual(r.providers.map((p) => p.scheme), ['agent-sessions'], 'details scheme registered');
assert.ok(
  ['agentSessions.refresh', 'agentSessions.openDetails'].every((c) => r.commands.some((x) => x.id === c)),
  'commands registered',
);
assert.equal(subscriptions.length, 6, 'six disposables pushed');

// Tree provider: 3 surface nodes always, expanded, correct contextValue
const tree = r.views[0].provider;
const roots = tree.getChildren();
assert.equal(roots.length, 3, 'one node per surface');
for (const n of roots) {
  const item = tree.getTreeItem(n);
  assert.equal(item.contextValue, 'surface');
  for (const child of tree.getChildren(n)) assert.equal(tree.getTreeItem(child).contextValue, 'session');
}

// Participant: empty prompt → overview mentioning all three surfaces
const chunks = [];
const stream = { markdown(m) { chunks.push(typeof m === 'string' ? m : m.value); } };
await r.participants[0].handler({ prompt: '' }, {}, stream, {});
const md = chunks.join('');
for (const s of ['copilot-cli', 'codex-cli', 'vscode-chat']) assert.ok(md.includes(s), `overview mentions ${s}`);

// Details provider: unknown key → graceful not-found doc
const doc = r.providers[0].provider.provideTextDocumentContent(
  vscode.Uri.parse('agent-sessions:Session/nope.md'),
);
assert.match(doc, /Session not found/);

console.log('smoke-activate: OK — views, participant, details provider, commands wired');

// openDetails accepts both invocation shapes: row click passes the display
// key string; the context menu passes the SessionNode. Both must open a doc.
const openDetails = r.commands.find((c) => c.id === 'agentSessions.openDetails');
await openDetails.fn('copilot-cli:ephemeral:0');
await openDetails.fn({ kind: 'session', meta: { display_key: 'copilot-cli:ephemeral:0' } });
assert.ok(vscode.registered.docs.length >= 2, 'openDetails opened docs for both arg shapes');

// details provider untracks closed documents — refresh must not fire for them
const provider = r.providers[0].provider;
const uri = vscode.Uri.parse('agent-sessions:Session/nope.md');
provider.provideTextDocumentContent(uri); // tracked now
for (const fn of vscode.registered.closeListeners ?? []) fn({ uri });
let fired = false;
provider.onDidChange(() => { fired = true; });
provider.refresh();
assert.equal(fired, false, 'closed details doc no longer receives change events');
