/**
 * Canonical session-corpus parity test.
 *
 * VENDORED CORPUS — do not edit in place. test/session-corpus/ is a copy of
 *   devin-internals-spec/fixtures/session-corpus/  (repo: devin-internals-spec,
 *   origin/main; contract: docs/SESSION-SURFACES.md §2/§4/§5/§6/§7).
 * To refresh, re-copy the whole directory — manifest.json is the authority
 * for expected canonical SessionMeta fields. Divergence means a spec drift
 * in this package's parsers: fix the code, never the manifest.
 *
 * Each manifest fixture names a surface and a store_path; the matching
 * SurfaceParser is pointed at that store via the same roots/env overrides
 * the unit tests use:
 *   copilot-cli  -> env.env.COPILOT_DIR  (store holds session-state/ + history-session-state/)
 *   codex-cli    -> env.env.CODEX_HOME   (store holds state_<N>.sqlite + sessions/)
 *   vscode-chat  -> env.appdata          (store holds <Variant>/User/...)
 * `home` always points at a nonexistent dir so real user stores are never
 * scanned into a result.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import { copilotCliParser } from '../src/sources/copilotCli.ts';
import { codexCliParser } from '../src/sources/codexCli.ts';
import { vscodeChatParser } from '../src/sources/vscodeChat.ts';
import { enc, workspaceHash } from '../src/ids.ts';
import type { SessionMeta, SourceResult, Surface } from '../src/model.ts';

const CORPUS = join(dirname(fileURLToPath(import.meta.url)), 'session-corpus');
/** Synthetic home guaranteed to contain no real session stores. */
const NO_HOME = join(CORPUS, '__no_such_home__');

interface SessionExpect {
  id_present: boolean;
  state: string;
  warning_codes: string[];
  event_count: number | null;
  started_at: string | null;
  ended_at: string | null;
}
interface ManifestSession {
  native_id: string;
  workspace_seed: string | null;
  expect: SessionExpect;
}
interface ManifestFixture {
  surface: Surface;
  store_path: string;
  source_warnings: string[];
  sessions: ManifestSession[];
}
interface Manifest {
  version: number;
  fixtures: ManifestFixture[];
}

const manifest = JSON.parse(readFileSync(join(CORPUS, 'manifest.json'), 'utf8')) as Manifest;

/** Invoke each surface parser against its vendored store, fully isolated. */
function parseStore(fixture: ManifestFixture): SourceResult {
  const store = join(CORPUS, fixture.store_path);
  switch (fixture.surface) {
    case 'copilot-cli':
      return copilotCliParser.collect(
        { home: NO_HOME, platform: 'linux', env: { COPILOT_DIR: store } }, 'metadata');
    case 'codex-cli':
      return codexCliParser.collect(
        { home: NO_HOME, platform: 'linux', env: { CODEX_HOME: store } }, 'metadata');
    case 'vscode-chat':
      return vscodeChatParser.collect(
        { home: NO_HOME, platform: 'linux', appdata: store }, 'metadata');
    default:
      throw new Error(`no corpus store wiring for surface ${fixture.surface}`);
  }
}

/** workspace_hash the parsers must derive from a manifest workspace_seed:
 *  vscode-chat uses the <wsDir> name verbatim; copilot-cli hashes the
 *  trimmed yaml seed; codex-cli hashes the normalized cwd. */
function expectedWsHash(surface: Surface, seed: string | null): string | null {
  if (seed === null) return null;
  if (surface === 'vscode-chat') return seed;
  const normalized = surface === 'codex-cli' ? normalize(seed) : seed.trim();
  return workspaceHash(normalized.replace(/[\\/]+$/, ''));
}

/** Find the SessionMeta a manifest entry describes. id_present entries are
 *  matched on the canonical id tail (`native:<enc(native_id)>`) + workspace
 *  hash; id-absent entries can only match the null-id / null-hash rows the
 *  store produced (§4: hashless native ids never get canonical ids). */
function findSession(res: SourceResult, fx: ManifestFixture, entry: ManifestSession): SessionMeta | undefined {
  const wsHash = expectedWsHash(fx.surface, entry.workspace_seed);
  return res.sessions.find((s) => {
    if (s.workspace_hash !== wsHash) return false;
    return entry.expect.id_present
      ? s.id !== null && s.id.endsWith(`:native:${enc(entry.native_id)}`)
      : s.id === null;
  });
}

const codes = (res: SourceResult | SessionMeta): Set<string> =>
  new Set(('warnings' in res ? res.warnings : res.parse_warnings).map((w) => w.code));

for (const fx of manifest.fixtures) {
  const res = parseStore(fx);

  test(`${fx.surface}: ${fx.store_path} -> expected source warnings, one meta per manifest entry`, () => {
    // A parsed corpus store may carry warnings; it must never hard-fail.
    assert.ok(['ok', 'partial', 'no-sessions'].includes(res.state), `unexpected state ${res.state}`);
    assert.deepEqual(codes(res), new Set(fx.source_warnings), 'source-level warning codes');
    assert.equal(res.sessions.length, fx.sessions.length, 'session count');
    const nullIdMeta = res.sessions.filter((s) => s.id === null).length;
    const nullIdExpected = fx.sessions.filter((s) => !s.expect.id_present).length;
    assert.equal(nullIdMeta, nullIdExpected, 'id-absent session count');
  });

  for (const entry of fx.sessions) {
    test(`${fx.surface}: session ${entry.native_id} matches canonical manifest`, () => {
      const s = findSession(res, fx, entry);
      assert.ok(s, `no SessionMeta for native_id ${entry.native_id}`);

      // expect.state refers to the session's parse outcome: 'ok' = the
      // session parsed into a complete SessionMeta (warnings allowed —
      // they are per-session metadata, and the result-level state already
      // downgrades to 'partial' on their account).
      assert.equal(entry.expect.state, 'ok');

      assert.deepEqual(codes(s), new Set(entry.expect.warning_codes), 'warning_codes (set)');
      assert.equal(s.event_count, entry.expect.event_count, 'event_count');
      assert.equal(s.started_at, entry.expect.started_at, 'started_at');
      assert.equal(s.ended_at, entry.expect.ended_at, 'ended_at');

      if (entry.expect.id_present) {
        assert.notEqual(s.id, null, 'id must be present');
        assert.ok(s.id!.startsWith(`${fx.surface}:`), 'id carries the surface prefix');
        assert.ok(s.id!.includes(entry.native_id), 'id carries the native id');
      } else {
        assert.equal(s.id, null, 'id must be absent');
        assert.ok(s.display_key.startsWith(`${fx.surface}:ephemeral:`), 'ephemeral display_key');
      }
    });
  }
}
