import { test } from 'node:test';
import assert from 'node:assert/strict';
import { canonicalId, enc, ephemeralKey, workspaceHash } from '../src/ids.ts';

test('canonical hierarchy: native / documented-alt / provisional-hash', () => {
  assert.equal(canonicalId('codex-cli', null, 'native', 'abc'), 'codex-cli:native:abc');
  assert.equal(canonicalId('codex-cli', null, 'documented-alt', 'x'), 'codex-cli:documented-alt:x');
  assert.equal(canonicalId('copilot-cli', null, 'provisional-hash', 'h'), 'copilot-cli:provisional-hash:h');
});

test('workspace-hash form inserts hash between source and kind', () => {
  const ws = workspaceHash('/repo/a');
  assert.equal(canonicalId('vscode-chat', ws, 'native', 's1'), `vscode-chat:${ws}:native:s1`);
  assert.match(ws, /^[0-9a-f]{16}$/);
});

test('distinct stable workspaces -> distinct canonical IDs', () => {
  const a = canonicalId('copilot-cli', workspaceHash('/repo/a'), 'native', 'same-id');
  const b = canonicalId('copilot-cli', workspaceHash('/repo/b'), 'native', 'same-id');
  assert.notEqual(a, b);
});

test('component encoding makes separators unambiguous', () => {
  const id = canonicalId('copilot-cli', null, 'native', 'a:b%c');
  assert.equal(id, 'copilot-cli:native:a%3Ab%25c');
  assert.equal(id.split(':').length, 3); // exactly 3 segments
  assert.equal(enc('%'), '%25');
  assert.equal(enc(':'), '%3A');
});

test('derived ids never render as native', () => {
  const id = canonicalId('codex-cli', null, 'provisional-hash', 'deadbeef');
  assert.ok(!id.includes(':native:'));
  assert.ok(id.includes(':provisional-hash:'));
});

test('ephemeral display keys are distinct and non-canonical', () => {
  const k1 = ephemeralKey('vscode-chat', 0);
  const k2 = ephemeralKey('vscode-chat', 1);
  assert.notEqual(k1, k2);
  assert.ok(!k1.includes(':native:'));
});
