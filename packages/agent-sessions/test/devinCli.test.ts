import { before, test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { CollectEnv } from '../src/model.ts';
import { canonicalId, workspaceHash } from '../src/ids.ts';
import { devinCliParser } from '../src/sources/devinCli.ts';

const ROOT = fileURLToPath(new URL('./fixtures/devin', import.meta.url));

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

const SESSIONS_DDL = `CREATE TABLE sessions (
  id TEXT, working_directory TEXT, backend_type TEXT, model TEXT,
  agent_mode TEXT, created_at INTEGER, last_activity_at INTEGER,
  title TEXT, main_chain_id INTEGER, shell_last_seen_index INTEGER,
  cogs_json TEXT, workspace_dirs TEXT, hidden INTEGER, metadata TEXT
)`;
const NODES_DDL = `CREATE TABLE message_nodes (
  row_id INTEGER PRIMARY KEY, session_id TEXT, node_id INTEGER,
  parent_node_id INTEGER, chat_message TEXT, created_at INTEGER, metadata TEXT
)`;
const REFINERY_DDL = `CREATE TABLE refinery_schema_history (version INTEGER)`;

interface SessionFixture {
  id: string;
  created_at: number;
  last_activity_at: number;
  working_directory?: string | null;
  hidden?: number;
}

const SEC = (iso: string) => Math.floor(Date.parse(iso) / 1000);

function mkhome(name: string, platform: NodeJS.Platform = 'linux'): CollectEnv {
  const home = join(ROOT, name);
  mkdirSync(home, { recursive: true });
  return { home, platform, env: {} };
}

/** Fixture db at the linux default: <home>/.local/share/devin/cli/sessions.db */
function mkSessionsDb(home: string, rows: SessionFixture[], nodes: Record<string, number> = {}): void {
  const dir = join(home, '.local', 'share', 'devin', 'cli');
  mkdirSync(dir, { recursive: true });
  const db = new DatabaseSync(join(dir, 'sessions.db'));
  db.exec(SESSIONS_DDL);
  db.exec(NODES_DDL);
  db.exec(REFINERY_DDL);
  db.prepare('INSERT INTO refinery_schema_history (version) VALUES (?)').run(7);
  const ins = db.prepare(
    'INSERT INTO sessions (id, working_directory, backend_type, model, agent_mode, created_at, last_activity_at, title, hidden, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
  );
  for (const r of rows) {
    ins.run(r.id, r.working_directory ?? null, 'windsurf', 'swe-1-6', 'default',
      r.created_at, r.last_activity_at, 'SENTINEL-TITLE-MUST-NOT-LEAK',
      r.hidden ?? 0, 'SENTINEL-METADATA-MUST-NOT-LEAK');
  }
  const insNode = db.prepare(
    'INSERT INTO message_nodes (session_id, node_id, chat_message) VALUES (?, ?, ?)',
  );
  for (const [sid, n] of Object.entries(nodes)) {
    for (let i = 0; i < n; i++) insNode.run(sid, i, 'SENTINEL-CONTENT-MUST-NOT-LEAK');
  }
  db.close();
}

before(() => {
  rmSync(ROOT, { recursive: true, force: true });
  mkdirSync(ROOT, { recursive: true });
});

test('a) source-not-found when no sessions.db exists', () => {
  const res = devinCliParser.collect(mkhome('a'), 'metadata');
  assert.equal(res.state, 'source-not-found');
  assert.equal(res.sessions.length, 0);
});

test('b) sessions listed with canonical ids, sorted desc, content never leaks', () => {
  const env = mkhome('b');
  mkSessionsDb(env.home, [
    { id: 'alpha-fox', created_at: SEC('2025-01-01T10:00:00Z'), last_activity_at: SEC('2025-01-01T11:00:00Z'), working_directory: '/repo/a' },
    { id: 'bravo-cat', created_at: SEC('2025-01-02T10:00:00Z'), last_activity_at: SEC('2025-01-02T11:00:00Z'), working_directory: '/repo/b' },
  ], { 'alpha-fox': 3 });
  const res = devinCliParser.collect(env, 'metadata');
  assert.equal(res.state, 'partial'); // no-end-marker inference warnings
  assert.equal(res.sessions.length, 2);
  const newer = res.sessions[0]!, older = res.sessions[1]!;
  assert.equal(newer.id, canonicalId('devin-cli', workspaceHash('/repo/b'), 'native', 'bravo-cat'));
  assert.equal(older.id, canonicalId('devin-cli', workspaceHash('/repo/a'), 'native', 'alpha-fox'));
  assert.equal(newer.title, null);
  assert.equal(older.event_count, 3);
  assert.equal(newer.event_count, null);
  assert.equal(newer.source_version, 'schema-v7');
  assert.equal(newer.ended_at, '2025-01-02T11:00:00.000Z');
  assert.ok(newer.parse_warnings.some(w => w.code === 'no-end-marker'));
  const blob = JSON.stringify(res);
  assert.ok(!blob.includes('SENTINEL'), 'no title/metadata/message content leaks');
  assert.ok(!blob.includes('/repo/b'), 'workspace path never emitted, only its hash');
});

test('c) hidden sessions are excluded', () => {
  const env = mkhome('c');
  mkSessionsDb(env.home, [
    { id: 'visible', created_at: SEC('2025-01-01T10:00:00Z'), last_activity_at: SEC('2025-01-01T11:00:00Z'), working_directory: '/repo/a' },
    { id: 'concealed', created_at: SEC('2025-01-02T10:00:00Z'), last_activity_at: SEC('2025-01-02T11:00:00Z'), working_directory: '/repo/a', hidden: 1 },
  ]);
  const res = devinCliParser.collect(env, 'metadata');
  assert.equal(res.sessions.length, 1);
  assert.equal(res.sessions[0]!.id, canonicalId('devin-cli', workspaceHash('/repo/a'), 'native', 'visible'));
});

test('d) missing workspace keeps session but id stays null', () => {
  const env = mkhome('d');
  mkSessionsDb(env.home, [
    { id: 'nows', created_at: SEC('2025-01-01T10:00:00Z'), last_activity_at: SEC('2025-01-01T11:00:00Z'), working_directory: null },
  ]);
  const res = devinCliParser.collect(env, 'metadata');
  assert.equal(res.sessions.length, 1);
  const s = res.sessions[0]!;
  assert.equal(s.id, null);
  assert.equal(s.workspace_hash, null);
  assert.ok(s.parse_warnings.some(w => w.code === 'unknown-workspace'));
  assert.ok(s.display_key.startsWith('devin-cli:ephemeral:'));
});

test('e) fresh activity reports session-open, never an inferred close', () => {
  const env = mkhome('e');
  const now = Math.floor(Date.now() / 1000);
  mkSessionsDb(env.home, [
    { id: 'live', created_at: now - 120, last_activity_at: now, working_directory: '/repo/a' },
  ]);
  const res = devinCliParser.collect(env, 'metadata');
  assert.equal(res.sessions.length, 1);
  const s = res.sessions[0]!;
  assert.equal(s.ended_at, null);
  assert.ok(s.parse_warnings.some(w => w.code === 'session-open'));
});

test('f) unreadable db reports read-error', () => {
  const env = mkhome('f');
  const dir = join(env.home, '.local', 'share', 'devin', 'cli');
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, 'sessions.db'), 'not a sqlite database at all');
  const res = devinCliParser.collect(env, 'metadata');
  assert.equal(res.state, 'read-error');
});

test('g) empty db reports no-sessions', () => {
  const env = mkhome('g');
  mkSessionsDb(env.home, []);
  const res = devinCliParser.collect(env, 'metadata');
  assert.equal(res.state, 'no-sessions');
});

test('h) windows appdata root is honored', () => {
  const home = join(ROOT, 'h');
  const appdata = join(home, 'AppData', 'Roaming');
  const dir = join(appdata, 'devin', 'cli');
  mkdirSync(dir, { recursive: true });
  const db = new DatabaseSync(join(dir, 'sessions.db'));
  db.exec(SESSIONS_DDL);
  db.prepare(
    'INSERT INTO sessions (id, working_directory, created_at, last_activity_at, hidden) VALUES (?, ?, ?, ?, ?)',
  ).run('win-sess', 'C:\\repo\\a', SEC('2025-01-01T10:00:00Z'), SEC('2025-01-01T11:00:00Z'), 0);
  db.close();
  const res = devinCliParser.collect({ home, platform: 'win32', appdata, env: {} }, 'metadata');
  assert.equal(res.state, 'partial');
  assert.equal(res.sessions.length, 1);
});
