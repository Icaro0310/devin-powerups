import { test } from 'node:test';
import assert from 'node:assert/strict';
import type { SessionMeta, SourceResult } from '../src/model.ts';
import { answer, formatSessionLine, matchSessions, renderOverview } from '../adapters/vscode/chatModel.ts';

function meta(over: Partial<SessionMeta> = {}): SessionMeta {
  return {
    surface: 'copilot-cli',
    id: 'copilot-cli:1a2b3c4d5e6f7890:native:aaaa-bbbb',
    display_key: 'copilot-cli:ephemeral:123456789012',
    title: null,
    started_at: '2026-10-01T14:32:00.000Z',
    ended_at: '2026-10-01T15:00:00.000Z',
    source_version: '1',
    workspace_hash: '1a2b3c4d5e6f7890',
    event_count: 4,
    parse_warnings: [],
    ...over,
  };
}

function fixture(): SourceResult[] {
  return [
    { surface: 'copilot-cli', state: 'ok', sessions: [meta()], warnings: [] },
    {
      surface: 'codex-cli',
      state: 'partial',
      sessions: [meta({ surface: 'codex-cli', id: null, display_key: 'codex-cli:ephemeral:0', workspace_hash: null })],
      warnings: [{ code: 'session-open', message: '1 session has no shutdown marker', source_version: null }],
    },
    { surface: 'vscode-chat', state: 'source-not-found', sessions: [], warnings: [] },
  ];
}

test('empty prompt renders the per-surface overview', () => {
  const out = answer('', fixture());
  assert.match(out, /\*\*copilot-cli\*\*: ok — 1 session/);
  assert.match(out, /\*\*codex-cli\*\*: partial — 1 session · 1 warning/);
  assert.match(out, /\*\*vscode-chat\*\*: source-not-found — 0 sessions/);
  assert.match(out, /metadata-only view — session titles and message content are suppressed by policy/);
});

test('whitespace-only prompt is the overview too', () => {
  assert.equal(answer('  \n\t ', fixture()), renderOverview(fixture()));
});

test('overview bullets show pre-sanitized warning messages', () => {
  const out = answer('', fixture());
  assert.match(out, / {2}- 1 session has no shutdown marker/);
});

test('session-level warnings count toward the surface total', () => {
  const results: SourceResult[] = [{
    surface: 'copilot-cli',
    state: 'partial',
    sessions: [meta({ parse_warnings: [
      { code: 'session-open', message: 'no shutdown marker', source_version: '1' },
      { code: 'missing-field', message: 'missing version field', source_version: '1' },
    ] })],
    warnings: [],
  }];
  assert.match(answer('', results), /copilot-cli\*\*: partial — 1 session · 2 warnings/);
});

test('filter matches surface, id, display_key and workspace_hash', () => {
  const results = fixture();
  assert.equal(matchSessions('copilot', results).length, 1); // surface
  assert.equal(matchSessions('1a2b3c4d', results).length, 1); // ws-hash prefix
  assert.equal(matchSessions('AAAA-BBBB', results).length, 1); // id substring, case-insensitive
  assert.equal(matchSessions('ephemeral', results).length, 2); // display_key on both
  assert.equal(matchSessions('cli', results).length, 2); // copilot-cli + codex-cli surfaces
});

test('filtered answer is a compact list capped at 20 with a truncation note', () => {
  const sessions = Array.from({ length: 25 }, (_, i) => meta({ display_key: `copilot-cli:ephemeral:${i}` }));
  const out = answer('copilot', [{ surface: 'copilot-cli', state: 'ok', sessions, warnings: [] }]);
  assert.equal(out.split('\n').filter(l => l.startsWith('- ')).length, 20);
  assert.match(out, /…5 more — refine the filter/);
});

test('no matches -> single line', () => {
  const out = answer('zzz-no-such', fixture());
  assert.equal(out.split('\n').length, 1);
  assert.match(out, /no sessions match/);
});

test('session line shape: local date · surface · ws first-8 · key last-12', () => {
  const line = formatSessionLine(meta());
  assert.match(line, /^- \d{4}-\d{2}-\d{2} \d{2}:\d{2} · copilot-cli · ws:1a2b3c4d · …123456789012$/);
});

test('null fields degrade in the session line', () => {
  const line = formatSessionLine(meta({ started_at: null, workspace_hash: null, display_key: 'short' }));
  assert.equal(line, '- unknown-time · copilot-cli · ws:(unknown) · short');
});

test('titles are never emitted or searchable', () => {
  const results: SourceResult[] = [{
    surface: 'copilot-cli', state: 'ok', sessions: [meta({ title: 'SECRET PROJECT NAME' })], warnings: [],
  }];
  assert.ok(!answer('', results).includes('SECRET PROJECT NAME'));
  assert.ok(!answer('copilot', results).includes('SECRET PROJECT NAME'));
  assert.match(answer('SECRET PROJECT', results), /no sessions match/);
});
