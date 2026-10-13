/**
 * treeModel unit tests — pure Node, synthetic SourceResult objects only.
 * Covers: registry-order roots (empty surfaces included), started_at desc
 * with nulls last, zero-content-exposure (title never rendered), the
 * `· open` marker, verbatim warnings, contextValue/icon mapping.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import type { ParseWarning, SessionMeta, SessionState, SourceResult, Surface } from '../src/model.ts';
import {
  buildSessionTree, contextValue, formatLocalDateTime, iconId, sessionDescription,
  sessionLabel, sessionTooltip, shortDisplayKey, surfaceChildren,
  surfaceDescription, surfaceLabel, surfaceTooltip,
} from '../adapters/vscode/treeModel.ts';
import type { SessionNode } from '../adapters/vscode/treeModel.ts';

let seq = 0;
function meta(surface: Surface, over: Partial<SessionMeta> = {}): SessionMeta {
  return {
    surface,
    id: null,
    display_key: `${surface}:ephemeral:${seq++}`,
    title: null,
    started_at: null,
    ended_at: null,
    source_version: null,
    workspace_hash: null,
    event_count: null,
    parse_warnings: [],
    ...over,
  };
}

function result(surface: Surface, over: Partial<SourceResult> = {}): SourceResult {
  return { surface, state: 'ok', sessions: [], warnings: [], ...over };
}

const warning = (code: ParseWarning['code'], message: string): ParseWarning =>
  ({ code, message, source_version: null });

const p2 = (n: number): string => String(n).padStart(2, '0');
const localStamp = (iso: string): string => {
  const d = new Date(iso);
  return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())} ${p2(d.getHours())}:${p2(d.getMinutes())}`;
};

test('root: one node per surface in registry order, empty surfaces included', () => {
  const results = [
    result('vscode-chat', { state: 'source-not-found' }),
    result('copilot-cli', { sessions: [meta('copilot-cli'), meta('copilot-cli')] }),
    result('codex-cli', { state: 'read-error' }),
  ];
  const nodes = buildSessionTree(results);
  assert.deepEqual(nodes.map(n => n.kind === 'surface' ? n.surface : '?'),
    ['copilot-cli', 'codex-cli', 'vscode-chat']);
  assert.deepEqual(nodes[0], {
    kind: 'surface', surface: 'copilot-cli', state: 'ok', sessionCount: 2, warningCount: 0,
  });
  assert.deepEqual(nodes[2], {
    kind: 'surface', surface: 'vscode-chat', state: 'source-not-found', sessionCount: 0, warningCount: 0,
  });
});

test('children: sessions sort by started_at desc, nulls last, stable ties', () => {
  const old = meta('codex-cli', { started_at: '2026-01-01T00:00:00Z' });
  const nullA = meta('codex-cli');
  const recent = meta('codex-cli', { started_at: '2026-03-01T00:00:00Z' });
  const nullB = meta('codex-cli');
  const mid = meta('codex-cli', { started_at: '2026-02-01T00:00:00Z' });
  const children = surfaceChildren(result('codex-cli', { sessions: [old, nullA, recent, nullB, mid] }));
  assert.deepEqual(children.map(n => n.kind === 'session' ? n.meta : null),
    [recent, mid, old, nullA, nullB]);
  for (const n of children) assert.equal(n.kind, 'session');
});

test('session label: local YYYY-MM-DD HH:MM, unknown date, never the title', () => {
  const m = meta('copilot-cli', { started_at: '2026-06-15T14:05:00Z', title: 'TOP SECRET TITLE' });
  const label = sessionLabel(m);
  assert.match(label, /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
  assert.equal(label, localStamp('2026-06-15T14:05:00Z'));
  assert.ok(!label.includes('TOP SECRET TITLE'));
  assert.equal(sessionLabel(meta('copilot-cli', { title: 'still hidden' })), 'unknown date');
  assert.equal(formatLocalDateTime('not-a-date'), 'unknown date');
});

test('session description: ws hash head + truncated key, no title/full key', () => {
  const key = 'copilot-cli:abcdef123456:native:zzzzzzzz';
  const m = meta('copilot-cli', {
    display_key: key,
    workspace_hash: '0123456789abcdef',
    title: 'Do Not Render Me',
  });
  const desc = sessionDescription(m);
  assert.equal(desc, `ws:01234567 · …${key.slice(-12)}`);
  assert.ok(!desc.includes('89abcdef'), 'hash truncated to first 8');
  assert.ok(!desc.includes(key), 'only the key tail is shown');
  assert.ok(!desc.includes('Do Not Render Me'));
});

test('session description: `· open` suffix for session-open warnings only', () => {
  const open = meta('copilot-cli', { parse_warnings: [warning('session-open', 'no shutdown marker')] });
  assert.ok(sessionDescription(open).endsWith(' · open'));
  const other = meta('copilot-cli', { parse_warnings: [warning('no-end-marker', 'x')] });
  assert.ok(!sessionDescription(other).endsWith(' · open'));
  assert.ok(!sessionDescription(meta('copilot-cli')).endsWith(' · open'));
});

test('shortDisplayKey: last 12 chars with ellipsis, short keys verbatim', () => {
  assert.equal(shortDisplayKey('1234567890123'), '…234567890123');
  assert.equal(shortDisplayKey('123456789012'), '123456789012');
  assert.equal(shortDisplayKey('short'), 'short');
});

test('session tooltip: surface, times, events, verbatim warnings, no title', () => {
  const m = meta('vscode-chat', {
    title: 'hidden title',
    started_at: '2026-01-01T10:00:00Z',
    ended_at: '2026-01-01T11:00:00Z',
    event_count: 7,
    parse_warnings: [warning('truncated-tail', 'malformed tail dropped')],
  });
  const tip = sessionTooltip(m);
  assert.ok(tip.includes('surface: vscode-chat'));
  assert.ok(tip.includes(`started: ${localStamp('2026-01-01T10:00:00Z')}`));
  assert.ok(tip.includes(`ended: ${localStamp('2026-01-01T11:00:00Z')}`));
  assert.ok(tip.includes('events: 7'));
  assert.ok(tip.includes('[truncated-tail] malformed tail dropped'));
  assert.ok(!tip.join('\n').includes('hidden title'));
  // null event_count -> no events line at all
  assert.ok(!sessionTooltip(meta('vscode-chat')).some(l => l.startsWith('events:')));
});

test('surface label/description: count or state when empty', () => {
  const r = result('codex-cli', { sessions: [meta('codex-cli'), meta('codex-cli'), meta('codex-cli')] });
  assert.equal(surfaceLabel(r), 'codex-cli');
  assert.equal(surfaceDescription(r), '3 sessions');
  assert.equal(surfaceDescription(result('codex-cli', { state: 'source-not-found' })), 'source-not-found');
  assert.equal(surfaceDescription(result('codex-cli', { state: 'no-sessions' })), 'no-sessions');
  assert.equal(surfaceDescription(result('codex-cli', { state: 'unsupported-format' })), 'unsupported-format');
});

test('surface tooltip: state, count, verbatim result-level warnings', () => {
  const r = result('copilot-cli', {
    state: 'partial',
    sessions: [meta('copilot-cli')],
    warnings: [warning('duplicates', '2 duplicate sessions skipped')],
  });
  const tip = surfaceTooltip(r);
  assert.ok(tip.includes('surface: copilot-cli'));
  assert.ok(tip.includes('state: partial'));
  assert.ok(tip.includes('sessions: 1'));
  assert.ok(tip.includes('[duplicates] 2 duplicate sessions skipped'));
});

test('contextValue maps node kind (session rows get the openDetails menu)', () => {
  const surface = buildSessionTree([result('copilot-cli')])[0]!;
  const session = surfaceChildren(result('copilot-cli', { sessions: [meta('copilot-cli')] }))[0]!;
  assert.equal(contextValue(surface), 'surface');
  assert.equal(contextValue(session), 'session');
});

test('iconId: per-state surface icons, warning icon for flagged sessions', () => {
  const surf = (state: SessionState): SessionNode =>
    ({ kind: 'surface', surface: 'copilot-cli', state, sessionCount: 0, warningCount: 0 });
  assert.equal(iconId(surf('ok')), 'check');
  assert.equal(iconId(surf('partial')), 'info');
  assert.equal(iconId(surf('no-sessions')), 'info');
  assert.equal(iconId(surf('source-not-found')), 'circle-slash');
  assert.equal(iconId(surf('read-error')), 'error');
  assert.equal(iconId(surf('unsupported-format')), 'error');
  assert.equal(iconId({ kind: 'session', meta: meta('copilot-cli') }), 'comment-discussion');
  const flagged = meta('copilot-cli', { parse_warnings: [warning('partial-parse', 'x')] });
  assert.equal(iconId({ kind: 'session', meta: flagged }), 'warning');
});
