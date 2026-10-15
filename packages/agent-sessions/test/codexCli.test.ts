import { before, test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { CollectEnv } from '../src/model.ts';
import { canonicalId, workspaceHash } from '../src/ids.ts';
import { codexCliParser } from '../src/sources/codexCli.ts';

const ROOT = fileURLToPath(new URL('./fixtures/codex', import.meta.url));

/** Minimal node:sqlite surface for fixture creation (type-free so the
 *  test compiles even where node:sqlite typings are absent). */
interface TestDb {
  exec(sql: string): void;
  prepare(sql: string): { run(...params: unknown[]): void };
  close(): void;
}
const DatabaseSync = (createRequire(import.meta.url)('node:sqlite') as {
  DatabaseSync: new (path: string) => TestDb;
}).DatabaseSync;

const THREADS_DDL = `CREATE TABLE threads (
  id TEXT, rollout_path TEXT, created_at TEXT, updated_at TEXT, title TEXT,
  model TEXT, tokens_used INTEGER, cwd TEXT, cli_version TEXT,
  has_user_event INTEGER, archived INTEGER, git_branch TEXT,
  git_origin_url TEXT, preview TEXT, source TEXT
)`;

interface ThreadFixture {
  id: string;
  created_at: string;
  updated_at: string;
  title?: string | null;
  cwd?: string | null;
  has_user_event?: number;
}

function mkhome(name: string): CollectEnv {
  const home = join(ROOT, name);
  mkdirSync(home, { recursive: true });
  return { home, platform: 'linux', env: {} };
}

function mkStateDb(home: string, n: number, rows: ThreadFixture[]): void {
  const dir = join(home, '.codex');
  mkdirSync(dir, { recursive: true });
  const db = new DatabaseSync(join(dir, `state_${n}.sqlite`));
  db.exec(THREADS_DDL);
  const ins = db.prepare(
    'INSERT INTO threads (id, created_at, updated_at, title, cwd, has_user_event, preview) VALUES (?, ?, ?, ?, ?, ?, ?)',
  );
  for (const r of rows) {
    ins.run(r.id, r.created_at, r.updated_at, r.title ?? null, r.cwd ?? null,
      r.has_user_event ?? 1, 'SENTINEL-CONTENT-MUST-NOT-LEAK');
  }
  db.close();
}

function mkRollout(home: string, rel: string, lines: unknown[], trailingNl = true): void {
  const p = join(home, '.codex', rel);
  mkdirSync(dirname(p), { recursive: true });
  const body = lines.map((l) => (typeof l === 'string' ? l : JSON.stringify(l))).join('\n');
  writeFileSync(p, body + (trailingNl ? '\n' : ''));
}

before(() => {
  rmSync(ROOT, { recursive: true, force: true });
  mkdirSync(ROOT, { recursive: true });
});

test('a) state db threads are listed with canonical ids', () => {
  const env = mkhome('a');
  mkStateDb(env.home, 5, [
    { id: 'thr-1', created_at: '2025-01-01T10:00:00Z', updated_at: '2025-01-01T11:00:00Z', title: 'First', cwd: '/repo/a' },
    { id: 'thr-2', created_at: '2025-01-02T10:00:00Z', updated_at: '2025-01-02T11:00:00Z', title: null, cwd: '/repo/b' },
  ]);
  const res = codexCliParser.collect(env, 'metadata');
  assert.equal(res.state, 'partial'); // inferred closes carry mandatory no-end-marker (spec §5.3)
  assert.equal(res.sessions.length, 2);
  const wsA = workspaceHash('/repo/a');
  const s1 = res.sessions.find((s) => s.id === canonicalId('codex-cli', wsA, 'native', 'thr-1'));
  assert.ok(s1);
  assert.equal(s1.started_at, '2025-01-01T10:00:00.000Z');
  assert.equal(s1.ended_at, '2025-01-01T11:00:00.000Z');
  assert.ok(s1.parse_warnings.some((w) => w.code === 'no-end-marker'));
  assert.equal(s1.source_version, 'state-5');
  assert.equal(s1.title, null); // threads.title (auto-generated) must not leak
  assert.equal(s1.workspace_hash, wsA);
});

test('b) rollout jsonl with task_complete yields ended_at', () => {
  const env = mkhome('b');
  mkRollout(env.home, join('sessions', '2025', '01', '03', 'rollout-2025-01-03T09-00-00_x.jsonl'), [
    { timestamp: '2025-01-03T09:00:00Z', type: 'session_meta', payload: { id: 'roll-1', timestamp: '2025-01-03T09:00:00Z', cwd: '/repo/x', instructions: 'SECRET-INSTRUCTIONS', cli_version: '0.40.0' } },
    { timestamp: '2025-01-03T09:05:00Z', type: 'event_msg', payload: { type: 'task_started' } },
    { timestamp: '2025-01-03T09:30:00Z', type: 'event_msg', payload: { type: 'task_complete' } },
  ]);
  const res = codexCliParser.collect(env, 'metadata');
  assert.equal(res.state, 'ok');
  assert.equal(res.sessions.length, 1);
  const s = res.sessions[0]!;
  assert.equal(s.id, canonicalId('codex-cli', workspaceHash('/repo/x'), 'native', 'roll-1'));
  assert.equal(s.started_at, '2025-01-03T09:00:00.000Z');
  assert.equal(s.ended_at, '2025-01-03T09:30:00.000Z');
  assert.equal(s.source_version, 'rollout');
  assert.equal(s.event_count, 3);
  assert.equal(s.title, null);
});

test('c) rollout duplicating a state thread is deduplicated', () => {
  const env = mkhome('c');
  mkStateDb(env.home, 3, [
    { id: 'thr-dup', created_at: '2025-01-04T10:00:00Z', updated_at: '2025-01-04T11:00:00Z', title: 'Dup', cwd: '/repo/d' },
  ]);
  mkRollout(env.home, join('sessions', '2025', '01', '04', 'rollout-2025-01-04T10-00-00_y.jsonl'), [
    { timestamp: '2025-01-04T10:00:00Z', type: 'session_meta', payload: { id: 'thr-dup', timestamp: '2025-01-04T10:00:00Z', cwd: '/repo/d' } },
    { timestamp: '2025-01-04T11:00:00Z', type: 'event_msg', payload: { type: 'task_complete' } },
  ]);
  const res = codexCliParser.collect(env, 'metadata');
  assert.equal(res.state, 'partial');
  assert.equal(res.sessions.length, 1);
  const s = res.sessions[0]!;
  assert.equal(s.source_version, 'state-3');
  assert.equal(s.id, canonicalId('codex-cli', workspaceHash('/repo/d'), 'native', 'thr-dup'));
  const dup = res.warnings.find((w) => w.code === 'duplicates');
  assert.ok(dup);
  assert.match(dup.message, /1/);
});

test('d) missing .codex dir -> source-not-found', () => {
  const res = codexCliParser.collect(mkhome('d'), 'metadata');
  assert.equal(res.state, 'source-not-found');
  assert.equal(res.sessions.length, 0);
});

test('e) empty .codex dir -> no-sessions', () => {
  const env = mkhome('e');
  mkdirSync(join(env.home, '.codex'), { recursive: true });
  const res = codexCliParser.collect(env, 'metadata');
  assert.equal(res.state, 'no-sessions');
  assert.equal(res.sessions.length, 0);
});

test('f) rollout with truncated final line -> truncated-tail', () => {
  const env = mkhome('f');
  mkRollout(env.home, join('sessions', '2025', '01', '05', 'rollout-t.jsonl'), [
    { timestamp: '2025-01-05T10:00:00Z', type: 'session_meta', payload: { id: 'roll-t', timestamp: '2025-01-05T10:00:00Z', cwd: '/repo/t' } },
    { timestamp: '2025-01-05T10:30:00Z', type: 'event_msg', payload: { type: 'task_complete' } },
    '{"timestamp":"2025-01-05T10:31:00Z","type":"event_ms',
  ], false);
  const res = codexCliParser.collect(env, 'metadata');
  assert.equal(res.state, 'partial');
  assert.equal(res.sessions.length, 1);
  const s = res.sessions[0]!;
  assert.ok(s.parse_warnings.some((w) => w.code === 'truncated-tail'));
  assert.equal(s.ended_at, '2025-01-05T10:30:00.000Z');
});

test('g) rollout without cwd -> null workspace hash in id', () => {
  const env = mkhome('g');
  mkRollout(env.home, join('sessions', '2025', '01', '06', 'rollout-n.jsonl'), [
    { timestamp: '2025-01-06T10:00:00Z', type: 'session_meta', payload: { id: 'roll-nocwd', timestamp: '2025-01-06T10:00:00Z' } },
    { timestamp: '2025-01-06T10:30:00Z', type: 'event_msg', payload: { type: 'task_complete' } },
  ]);
  const res = codexCliParser.collect(env, 'metadata');
  assert.equal(res.sessions.length, 1);
  const s = res.sessions[0]!;
  assert.equal(s.id, null); // no stable workspace identity -> never canonical
  assert.equal(s.workspace_hash, null);
  assert.match(s.display_key, /^codex-cli:ephemeral:/);
  assert.ok(s.parse_warnings.some((w) => w.code === 'unknown-workspace'));
});

test('h) task_started after task_complete -> end no longer determinable', () => {
  const env = mkhome('h');
  mkRollout(env.home, join('sessions', '2025', '01', '07', 'rollout-restart.jsonl'), [
    { timestamp: '2025-01-07T10:00:00Z', type: 'session_meta', payload: { id: 'roll-restart', timestamp: '2025-01-07T10:00:00Z', cwd: '/repo/a' } },
    { timestamp: '2025-01-07T10:05:00Z', type: 'event_msg', payload: { type: 'task_complete' } },
    { timestamp: '2025-01-07T10:10:00Z', type: 'event_msg', payload: { type: 'task_started' } },
  ]);
  const res = codexCliParser.collect(env, 'metadata');
  const s = res.sessions[0]!;
  assert.equal(s.ended_at, null); // second task still running
  assert.ok(s.parse_warnings.some((w) => w.code === 'no-end-marker' || w.code === 'session-open'));
});

test('i) same native id in different workspaces -> both kept, cross-workspace warning', () => {
  const env = mkhome('i');
  for (const [file, cwd] of [['rollout-x1.jsonl', '/repo/a'], ['rollout-x2.jsonl', '/repo/b']] as const) {
    mkRollout(env.home, join('sessions', '2025', '01', '08', file), [
      { timestamp: '2025-01-08T10:00:00Z', type: 'session_meta', payload: { id: 'dup-id', timestamp: '2025-01-08T10:00:00Z', cwd } },
      { timestamp: '2025-01-08T10:30:00Z', type: 'event_msg', payload: { type: 'task_complete' } },
    ]);
  }
  const res = codexCliParser.collect(env, 'metadata');
  assert.equal(res.sessions.length, 2); // distinct workspaces are distinct sessions
  assert.ok(res.warnings.some((w) => w.code === 'cross-workspace-duplicate'));
});
