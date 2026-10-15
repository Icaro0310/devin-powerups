import { before, test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { copilotCliParser } from '../src/sources/copilotCli.ts';
import { canonicalId, workspaceHash } from '../src/ids.ts';
import type { CollectEnv } from '../src/model.ts';

const FIX = join(dirname(fileURLToPath(import.meta.url)), 'fixtures', 'copilot');
const UUID = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';
const GIT = '/repo/proj';

function ev(id: number, type: string, data: unknown = {}, ts?: string): string {
  return JSON.stringify({
    id: `e${id}`,
    parentId: id === 0 ? null : `e${id - 1}`,
    timestamp: ts ?? `2026-01-01T10:0${id}:00.000Z`,
    type,
    data,
  });
}

const YAML_NAMED = [
  `id: ${UUID}`, 'name: My Session', 'user_named: true', 'summary_count: 0',
  'created_at: 2026-01-01T10:00:00Z', 'updated_at: 2026-01-01T10:05:00Z',
  'client_name: cli', 'host_type: local', `cwd: ${GIT}`, `git_root: ${GIT}`,
  'repository: org/proj', 'branch: main', '',
].join('\n');

const YAML_UNNAMED = YAML_NAMED.replace('user_named: true', 'user_named: false');

function writeSession(home: string, uuid: string, lines: string[], yaml?: string): void {
  const dir = join(home, '.copilot', 'session-state', uuid);
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, 'events.jsonl'), lines.join('\n') + '\n');
  if (yaml !== undefined) writeFileSync(join(dir, 'workspace.yaml'), yaml);
}

function envFor(home: string, extra?: NodeJS.ProcessEnv): CollectEnv {
  return { home, platform: 'linux', env: extra ?? {} };
}

before(() => {
  rmSync(FIX, { recursive: true, force: true });
  mkdirSync(FIX, { recursive: true });
});

test('ok: session.start v1 + shutdown -> ended_at, canonical native id', () => {
  const home = join(FIX, 'a');
  writeSession(home, UUID, [
    ev(0, 'session.start', { version: 1, copilotVersion: '1.2.3' }),
    ev(1, 'user.message', { content: 'hello' }),
    ev(2, 'assistant.message', { content: 'hi there' }),
    ev(3, 'session.shutdown', {}, '2026-01-01T10:09:00.000Z'),
  ], YAML_NAMED);
  const r = copilotCliParser.collect(envFor(home), 'metadata');
  assert.equal(r.state, 'ok');
  assert.equal(r.sessions.length, 1);
  const s = r.sessions[0]!;
  assert.equal(s.surface, 'copilot-cli');
  assert.equal(s.id, canonicalId('copilot-cli', workspaceHash(GIT), 'native', UUID));
  assert.equal(s.workspace_hash, workspaceHash(GIT));
  assert.equal(s.title, 'My Session');
  assert.equal(s.started_at, '2026-01-01T10:00:00.000Z');
  assert.equal(s.ended_at, '2026-01-01T10:09:00.000Z');
  assert.equal(s.source_version, '1');
  assert.equal(s.event_count, 4);
  assert.deepEqual(s.parse_warnings, []);
  assert.ok(s.display_key.startsWith('copilot-cli:ephemeral:'));
});

test('no shutdown + fresh last activity -> session-open, ended_at null', () => {
  const home = join(FIX, 'b');
  const now = new Date().toISOString(); // spec §5.2: session-open only within 60s of read time
  writeSession(home, UUID, [
    ev(0, 'session.start', { version: 1 }, now),
    ev(1, 'user.message', { content: 'still typing' }, now),
  ], YAML_UNNAMED);
  const r = copilotCliParser.collect(envFor(home), 'metadata');
  assert.equal(r.state, 'partial');
  const s = r.sessions[0]!;
  assert.equal(s.ended_at, null);
  assert.equal(s.title, null); // user_named false -> never a title
  assert.ok(s.parse_warnings.some((w) => w.code === 'session-open'));
});

test('no shutdown + stale last activity -> inferred close, no-end-marker', () => {
  const home = join(FIX, 'b2');
  writeSession(home, UUID, [
    ev(0, 'session.start', { version: 1 }),
    ev(1, 'user.message', { content: 'left open' }),
  ], YAML_UNNAMED);
  const r = copilotCliParser.collect(envFor(home), 'metadata');
  assert.equal(r.state, 'partial');
  const s = r.sessions[0]!;
  assert.equal(s.ended_at, '2026-01-01T10:01:00.000Z'); // spec §5.3: inferred from last activity
  assert.equal(s.parse_warnings.filter((w) => w.code === 'no-end-marker').length, 1);
  assert.ok(!s.parse_warnings.some((w) => w.code === 'session-open'));
});

test('truncated last line -> truncated-tail + no-end-marker, rest parsed', () => {
  const home = join(FIX, 'c');
  writeSession(home, UUID, [
    ev(0, 'session.start', { version: 1 }),
    ev(1, 'user.message', { content: 'half a thought' }),
    '{"id":"e2","parentId":"e1","timestamp":"2026-01-01T10:0',
  ], YAML_NAMED);
  const r = copilotCliParser.collect(envFor(home), 'metadata');
  assert.equal(r.state, 'partial');
  const s = r.sessions[0]!;
  assert.equal(s.event_count, 2);
  assert.equal(s.ended_at, '2026-01-01T10:01:00.000Z'); // inferred from last readable activity
  assert.ok(s.parse_warnings.some((w) => w.code === 'truncated-tail'));
  assert.ok(s.parse_warnings.some((w) => w.code === 'no-end-marker'));
});

test('missing copilot root -> source-not-found', () => {
  const r = copilotCliParser.collect(envFor(join(FIX, 'nonexistent')), 'metadata');
  assert.equal(r.state, 'source-not-found');
  assert.equal(r.sessions.length, 0);
});

test('empty session-state -> no-sessions', () => {
  const home = join(FIX, 'e');
  mkdirSync(join(home, '.copilot', 'session-state'), { recursive: true });
  const r = copilotCliParser.collect(envFor(home), 'metadata');
  assert.equal(r.state, 'no-sessions');
  assert.equal(r.sessions.length, 0);
});

test('unknown event types -> counted warning, session still parsed', () => {
  const home = join(FIX, 'f');
  writeSession(home, UUID, [
    ev(0, 'session.start', { version: 1 }),
    ev(1, 'future.new_type', { foo: 1 }),
    ev(2, 'another.weird'),
    ev(3, 'session.shutdown'),
  ], YAML_NAMED);
  const r = copilotCliParser.collect(envFor(home), 'metadata');
  assert.equal(r.state, 'partial');
  const s = r.sessions[0]!;
  assert.equal(s.event_count, 4);
  assert.equal(s.ended_at, '2026-01-01T10:03:00.000Z');
  const w = s.parse_warnings.find((w) => w.code === 'partial-parse');
  assert.ok(w && /2/.test(w.message));
});

test('flat session-state/<uuid>.jsonl variant -> native id, null ws hash', () => {
  const home = join(FIX, 'g');
  const dir = join(home, '.copilot', 'session-state');
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, `${UUID}.jsonl`), [
    ev(0, 'session.start', { version: 1 }),
    ev(1, 'session.shutdown'),
  ].join('\n') + '\n');
  const r = copilotCliParser.collect(envFor(home), 'metadata');
  assert.equal(r.state, 'partial'); // unknown-workspace warning
  const s = r.sessions[0]!;
  assert.equal(s.id, null); // no stable workspace identity -> never canonical
  assert.equal(s.workspace_hash, null);
  assert.ok(s.parse_warnings.some((w) => w.code === 'unknown-workspace'));
  assert.equal(s.title, null);
});

test('env COPILOT_DIR root merges; same id in two roots -> duplicates', () => {
  const home = join(FIX, 'h');
  const envRoot = join(FIX, 'h-env');
  const lines = [ev(0, 'session.start', { version: 1 }), ev(1, 'session.shutdown')];
  writeSession(home, UUID, lines, YAML_NAMED);
  // same session id under $COPILOT_DIR (its own .copilot-style root layout)
  const dir = join(envRoot, 'session-state', UUID);
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, 'events.jsonl'), lines.join('\n') + '\n');
  writeFileSync(join(dir, 'workspace.yaml'), YAML_NAMED);
  const r = copilotCliParser.collect(envFor(home, { COPILOT_DIR: envRoot }), 'metadata');
  assert.equal(r.state, 'partial');
  assert.equal(r.sessions.length, 1); // merged, deduped
  assert.ok(r.warnings.some((w) => w.code === 'duplicates'));
});

test('null JSON line in events file -> bad line skipped, session still parsed', () => {
  const home = join(FIX, 'nullline');
  writeSession(home, UUID, [
    'null',
    ev(0, 'session.start', { version: 1 }),
    ev(1, 'session.shutdown'),
  ], YAML_NAMED);
  const r = copilotCliParser.collect(envFor(home), 'metadata');
  assert.notEqual(r.state, 'read-error');
  assert.equal(r.sessions.length, 1);
  assert.ok(r.sessions[0]!.parse_warnings.some((w) => w.code === 'partial-parse'));
});

test('non-version-shaped version field -> dropped, missing-field warning', () => {
  const home = join(FIX, 'badver');
  writeSession(home, UUID, [
    ev(0, 'session.start', { version: 'run this --dangerous flag' }),
    ev(1, 'session.shutdown'),
  ], YAML_NAMED);
  const r = copilotCliParser.collect(envFor(home), 'metadata');
  const s = r.sessions[0]!;
  assert.equal(s.source_version, null);
  assert.ok(s.parse_warnings.some((w) => w.code === 'missing-field' && /version/.test(w.message)));
});

test('same id different workspace across roots -> both kept, cross-workspace warning', () => {
  const home = join(FIX, 'xws');
  const envRoot = join(FIX, 'xws-env');
  const lines = [ev(0, 'session.start', { version: 1 }), ev(1, 'session.shutdown')];
  writeSession(home, UUID, lines, YAML_NAMED);
  const dir = join(envRoot, 'session-state', UUID);
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, 'events.jsonl'), lines.join('\n') + '\n');
  writeFileSync(join(dir, 'workspace.yaml'), YAML_NAMED.replaceAll(GIT, '/repo/other'));
  const r = copilotCliParser.collect(envFor(home, { COPILOT_DIR: envRoot }), 'metadata');
  assert.equal(r.sessions.length, 2); // distinct workspaces are distinct sessions
  assert.ok(r.warnings.some((w) => w.code === 'cross-workspace-duplicate'));
});

test('same id in three roots A,B,A -> third A deduped against first, not lost', () => {
  const home = join(FIX, 'aba');
  const dirRoot = join(FIX, 'aba-dir');
  const homeRoot = join(FIX, 'aba-home');
  const lines = [ev(0, 'session.start', { version: 1 }), ev(1, 'session.shutdown')];
  const yaml = (cwd: string) => YAML_NAMED.replaceAll(GIT, cwd);
  const write = (root: string, yamlText: string) => {
    const dir = join(root, 'session-state', UUID);
    mkdirSync(dir, { recursive: true });
    writeFileSync(join(dir, 'events.jsonl'), lines.join('\n') + '\n');
    writeFileSync(join(dir, 'workspace.yaml'), yamlText);
  };
  write(join(home, '.copilot'), yaml('/repo/a'));
  write(dirRoot, yaml('/repo/b'));
  write(homeRoot, yaml('/repo/a')); // same ws as first — must dedup, not re-emit id
  const r = copilotCliParser.collect(envFor(home, { COPILOT_DIR: dirRoot, COPILOT_HOME: homeRoot }), 'metadata');
  assert.equal(r.sessions.length, 2);
  assert.equal(new Set(r.sessions.map((s) => s.id)).size, 2); // no duplicate canonical ids
  assert.ok(r.warnings.some((w) => w.code === 'cross-workspace-duplicate'));
  assert.ok(r.warnings.some((w) => w.code === 'duplicates'));
});
