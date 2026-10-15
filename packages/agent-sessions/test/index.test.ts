import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { collectAll } from '../src/sources/index.ts';

test('collectAll returns one result per surface, no cross-surface coupling', () => {
  const home = mkdtempSync(join(tmpdir(), 'as-empty-'));
  const out = collectAll({ home, platform: 'linux' }, 'metadata');
  assert.equal(out.length, 4);
  const surfaces = out.map(r => r.surface).sort();
  assert.deepEqual(surfaces, ['codex-cli', 'copilot-cli', 'devin-cli', 'vscode-chat']);
  // Empty synthetic home: every surface reports source-not-found, never no-sessions
  for (const r of out) assert.equal(r.state, 'source-not-found', `${r.surface} should be source-not-found`);
});

test('a broken source does not block the others', () => {
  const home = mkdtempSync(join(tmpdir(), 'as-partial-'));
  // .copilot exists (source present) but zero session dirs -> no-sessions
  mkdirSync(join(home, '.copilot'), { recursive: true });
  const out = collectAll({ home, platform: 'linux' }, 'metadata');
  const copilot = out.find(r => r.surface === 'copilot-cli');
  const others = out.filter(r => r.surface !== 'copilot-cli');
  assert.equal(copilot?.state, 'no-sessions');
  for (const r of others) assert.equal(r.state, 'source-not-found');
});

