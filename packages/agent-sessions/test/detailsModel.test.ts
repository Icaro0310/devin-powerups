import { test } from 'node:test';
import assert from 'node:assert/strict';
import type { SessionMeta, SourceResult } from '../src/model.ts';
import { renderSessionDetails } from '../adapters/vscode/detailsModel.ts';

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

const RESULT: SourceResult = { surface: 'copilot-cli', state: 'ok', sessions: [], warnings: [] };

test('H1 is the display_key last-12', () => {
  const out = renderSessionDetails(meta(), RESULT);
  assert.match(out, /^# Session …123456789012\n/m);
});

test('all canonical fields render as table rows', () => {
  const out = renderSessionDetails(meta(), RESULT);
  assert.match(out, /\| field \| value \|/);
  assert.match(out, /\| surface \| copilot-cli \|/);
  assert.match(out, /\| id \| copilot-cli:1a2b3c4d5e6f7890:native:aaaa-bbbb \|/);
  assert.match(out, /\| display_key \| copilot-cli:ephemeral:123456789012 \|/);
  assert.match(out, /\| started_at \| 2026-10-01T14:32:00\.000Z \|/);
  assert.match(out, /\| ended_at \| 2026-10-01T15:00:00\.000Z \|/);
  assert.match(out, /\| source_version \| 1 \|/);
  assert.match(out, /\| workspace_hash \| 1a2b3c4d5e6f7890 \|/);
  assert.match(out, /\| event_count \| 4 \|/);
});

test('null fields render the policy fallbacks', () => {
  const out = renderSessionDetails(
    meta({ id: null, started_at: null, ended_at: null, source_version: null, workspace_hash: null, event_count: null }),
    undefined,
  );
  assert.match(out, /\| id \| \(unstable\) \|/);
  assert.match(out, /\| started_at \| \(unknown\) \|/);
  assert.match(out, /\| ended_at \| open\/unknown \|/);
  assert.match(out, /\| source_version \| \(unknown\) \|/);
  assert.match(out, /\| workspace_hash \| \(unknown\) \|/);
  assert.match(out, /\| event_count \| \(unknown\) \|/);
});

test('parse warnings list session + owning-source warnings, deduped', () => {
  const m = meta({ parse_warnings: [
    { code: 'session-open', message: 'no shutdown marker', source_version: '1' },
    { code: 'duplicates', message: '2 duplicate sessions dropped', source_version: null },
  ] });
  const r: SourceResult = {
    surface: 'copilot-cli', state: 'partial', sessions: [m],
    warnings: [{ code: 'duplicates', message: '2 duplicate sessions dropped', source_version: null }],
  };
  const out = renderSessionDetails(m, r);
  assert.match(out, /## Parse warnings/);
  assert.match(out, /- `session-open` — no shutdown marker/);
  assert.equal(out.match(/`duplicates` — 2 duplicate sessions dropped/g)?.length, 1);
});

test('no warnings -> _none_', () => {
  assert.match(renderSessionDetails(meta(), RESULT), /## Parse warnings\n\n_none_/);
});

test('pipe chars in table cells are escaped', () => {
  const out = renderSessionDetails(meta({ source_version: 'v|2' }), undefined);
  assert.ok(out.includes('| source_version | v\\|2 |'));
});

test('titles are never rendered', () => {
  const out = renderSessionDetails(meta({ title: 'TOP SECRET TITLE' }), RESULT);
  assert.ok(!out.includes('TOP SECRET TITLE'));
  assert.match(out, /titles and message content are never rendered, by policy/);
});
