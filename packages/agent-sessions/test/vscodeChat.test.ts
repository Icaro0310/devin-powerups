import { after, test } from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { vscodeChatParser } from '../src/sources/vscodeChat.ts';
import { canonicalId } from '../src/ids.ts';
import type { CollectEnv } from '../src/model.ts';

// Synthetic fixture roots live under test/fixtures/vscode/ and are removed
// after the run; each test gets its own root via mkdtemp.
const ROOT = fileURLToPath(new URL('./fixtures/vscode/', import.meta.url));
after(() => fs.rmSync(ROOT, { recursive: true, force: true }));

function mkRoot(): string {
  fs.mkdirSync(ROOT, { recursive: true });
  return fs.mkdtempSync(path.join(ROOT, 'case-'));
}
/** env where `root` is the roaming app-data dir holding <Variant>/User. */
function envFor(root: string): CollectEnv {
  return { home: path.join(root, 'home'), platform: 'linux', appdata: root };
}
function write(root: string, rel: string, content: string): string {
  const p = path.join(root, rel);
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, content);
  return p;
}
const wsDir = (wsHash: string) =>
  path.join('Code', 'User', 'workspaceStorage', wsHash, 'chatSessions');
const globalDir = (name: string) => path.join('Code', 'User', 'globalStorage', name);

const WS_A = 'a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6'; // wsdir names are opaque md5 hashes
const WS_B = 'f6e5d4c3b2a10987f6e5d4c3b2a10987';
const T0 = 1700000000000;
const iso = (t: number) => new Date(t).toISOString();
const snapshot = (extra: Record<string, unknown> = {}) => JSON.stringify({
  version: 2, creationDate: T0, lastMessageDate: T0 + 5000, customTitle: 'Snap', requests: [], ...extra,
});

test('jsonl mutation log: kinds 0-3 replay in order to the final document', () => {
  const root = mkRoot();
  const id = 'sess-replay-1';
  const lines = [
    { kind: 0, v: { version: 2, creationDate: T0, lastMessageDate: T0 + 1000, customTitle: 'Base', requests: [] } },
    { kind: 1, k: ['customTitle'], v: 'Replayed Title' },
    { kind: 2, k: ['requests'], v: { timestamp: T0 + 2000, responseTimestamp: T0 + 3000, result: { timings: { totalElapsed: 4000 } } } },
    { kind: 2, k: ['requests'], v: { timestamp: T0 + 9000 } }, // appended, then deleted
    { kind: 3, k: ['requests', 1] },
  ].map((l) => JSON.stringify(l)).join('\n') + '\n';
  write(root, path.join(wsDir(WS_A), `${id}.jsonl`), lines);

  const res = vscodeChatParser.collect(envFor(root), 'metadata');
  assert.equal(res.state, 'ok');
  assert.equal(res.sessions.length, 1);
  const s = res.sessions[0]!;
  assert.equal(s.id, canonicalId('vscode-chat', WS_A, 'native', id));
  assert.equal(s.workspace_hash, WS_A);
  assert.equal(s.title, null); // content-derived titles never emitted
  assert.equal(s.event_count, 1); // kind-3 removed the second request
  assert.equal(s.started_at, iso(T0));
  assert.equal(s.ended_at, iso(T0 + 6000)); // timestamp + totalElapsed wins over responseTimestamp
  assert.deepEqual(s.parse_warnings, []);
  assert.equal(s.source_version, '2');
});

test('.jsonl prevails over .json for the same session id', () => {
  const root = mkRoot();
  const id = 'sess-dual-1';
  write(root, path.join(wsDir(WS_A), `${id}.json`), snapshot({ customTitle: 'From JSON' }));
  const log = JSON.stringify({ kind: 0, v: { ...JSON.parse(snapshot()), customTitle: 'From JSONL' } }) + '\n';
  write(root, path.join(wsDir(WS_A), `${id}.jsonl`), log);

  const res = vscodeChatParser.collect(envFor(root), 'metadata');
  assert.equal(res.sessions.length, 1);
  assert.equal(res.sessions[0]!.title, null); // jsonl wins but title stays null
});

test('same session id in two workspace dirs -> cross-workspace-duplicate, both kept', () => {
  const root = mkRoot();
  const id = 'sess-dupe-1';
  write(root, path.join(wsDir(WS_A), `${id}.json`), snapshot({ customTitle: 'A' }));
  write(root, path.join(wsDir(WS_B), `${id}.json`), snapshot({ customTitle: 'B' }));

  const res = vscodeChatParser.collect(envFor(root), 'metadata');
  assert.equal(res.state, 'partial');
  assert.equal(res.sessions.length, 2);
  const ids = res.sessions.map((s) => s.id).sort();
  assert.deepEqual(ids, [
    canonicalId('vscode-chat', WS_A, 'native', id),
    canonicalId('vscode-chat', WS_B, 'native', id),
  ].sort());
  for (const s of res.sessions) {
    const w = s.parse_warnings.filter((x) => x.code === 'cross-workspace-duplicate');
    assert.equal(w.length, 1);
    assert.match(w[0]!.message, /2 storage locations/);
  }
});

test('no User dir of any variant -> source-not-found', () => {
  const res = vscodeChatParser.collect(envFor(mkRoot()), 'metadata');
  assert.equal(res.state, 'source-not-found');
  assert.deepEqual(res.sessions, []);
});

test('User dir exists but no chatSessions -> no-sessions', () => {
  const root = mkRoot();
  fs.mkdirSync(path.join(root, 'Code', 'User', 'workspaceStorage'), { recursive: true });
  fs.mkdirSync(path.join(root, 'Code', 'User', 'globalStorage'), { recursive: true });
  const res = vscodeChatParser.collect(envFor(root), 'metadata');
  assert.equal(res.state, 'no-sessions');
  assert.deepEqual(res.sessions, []);
});

test('unknown mutation kind -> unsupported-mutation warning, session still parsed', () => {
  const root = mkRoot();
  const id = 'sess-mut-1';
  const lines = [
    { kind: 0, v: JSON.parse(snapshot({ customTitle: 'Kept' })) },
    { kind: 9, k: ['requests'], v: {} },
    { kind: 42, v: 1 },
  ].map((l) => JSON.stringify(l)).join('\n');
  write(root, path.join(wsDir(WS_A), `${id}.jsonl`), lines);

  const res = vscodeChatParser.collect(envFor(root), 'metadata');
  assert.equal(res.state, 'partial');
  const s = res.sessions[0]!;
  assert.equal(s.title, null);
  const w = s.parse_warnings.find((x) => x.code === 'unsupported-mutation');
  assert.ok(w);
  assert.match(w.message, /2 mutation\(s\)/);
});

test('emptyWindowChatSessions -> workspace_hash null, canonical id without workspace', () => {
  const root = mkRoot();
  const id = 'sess-empty-1';
  write(root, path.join(globalDir('emptyWindowChatSessions'), `${id}.json`), snapshot());
  const res = vscodeChatParser.collect(envFor(root), 'metadata');
  assert.equal(res.sessions.length, 1);
  const s = res.sessions[0]!;
  assert.equal(s.workspace_hash, null);
  assert.equal(s.id, `vscode-chat:native:${id}`);
  assert.equal(s.id, canonicalId('vscode-chat', null, 'native', id));
});

test('truncated last mutation line -> truncated-tail warning', () => {
  const root = mkRoot();
  const id = 'sess-trunc-1';
  const lines = JSON.stringify({ kind: 0, v: JSON.parse(snapshot()) }) + '\n{"kind":1,"k":["cust';
  write(root, path.join(wsDir(WS_A), `${id}.jsonl`), lines);
  const res = vscodeChatParser.collect(envFor(root), 'metadata');
  const s = res.sessions[0]!;
  assert.equal(s.title, null);
  assert.ok(s.parse_warnings.some((w) => w.code === 'truncated-tail'));
});

test('unrecognizable document structure -> unsupported-format when nothing parses', () => {
  const root = mkRoot();
  write(root, path.join(wsDir(WS_A), 'sess-bad-1.json'), '["not","a","session"]');
  const res = vscodeChatParser.collect(envFor(root), 'metadata');
  assert.equal(res.state, 'unsupported-format');
  assert.deepEqual(res.sessions, []);
  assert.ok(res.warnings.some((w) => w.code === 'partial-parse'));
});

test('fully unparseable file -> read-error when nothing is readable', () => {
  const root = mkRoot();
  write(root, path.join(wsDir(WS_A), 'sess-corrupt-1.json'), 'garbage');
  const res = vscodeChatParser.collect(envFor(root), 'metadata');
  assert.equal(res.state, 'read-error');
  assert.deepEqual(res.sessions, []);
  assert.ok(res.warnings.some((w) => w.code === 'partial-parse'));
});

test('open session without completion marker -> session-open warning', () => {
  const root = mkRoot();
  const id = 'sess-open-1';
  write(root, path.join(wsDir(WS_A), `${id}.json`), snapshot({
    requests: [{ timestamp: T0 + 2000, message: { text: 'redacted' } }],
  }));
  const res = vscodeChatParser.collect(envFor(root), 'metadata');
  const s = res.sessions[0]!;
  assert.equal(s.event_count, 1);
  assert.ok(s.parse_warnings.some((w) => w.code === 'session-open'));
  assert.equal(s.ended_at, iso(T0 + 5000)); // lastMessageDate still bounds the end
});
