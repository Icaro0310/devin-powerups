/**
 * Canonical model — locked by spec v3.4.4 (Parte 2b).
 *
 * `surface` values are a closed set; a session may never report a surface
 * outside this union. `'devin-cli'` extends the spec'd trio — the set
 * stays closed, the union grows only by deliberate addition
 * (D-2026-10-15, path-A activation). `ended_at`/`source_version` semantics: null means
 * "not determinable" and the reason must surface in `parse_warnings`
 * (`session-open`, `no-end-marker`, `missing-field`, …) — never guessed.
 *
 * `parse_warnings[].message` follows the safe-message rule: controlled
 * templates only. Never raw exception text, full paths, project names,
 * session IDs, source field values, or content fragments. Non-sensitive
 * technical detail = codes and counts only.
 */

export type Surface = 'vscode-chat' | 'copilot-cli' | 'codex-cli' | 'devin-cli';

export type SessionState =
  | 'ok'                  // full parse, no warnings
  | 'partial'             // parsed with warnings
  | 'no-sessions'         // source exists and contains zero sessions
  | 'source-not-found'    // expected location missing or agent not detected
  | 'unsupported-format'  // source exists, format recognized as unknown
  | 'read-error';         // existing source failed to read

export type WarningCode =
  | 'duplicates' | 'cross-workspace-duplicate' | 'unsupported-mutation'
  | 'truncated-tail' | 'missing-field' | 'format-version-mismatch'
  | 'no-end-marker' | 'session-open' | 'partial-parse'
  | 'provisional-id' | 'unknown-workspace';

export interface ParseWarning {
  code: WarningCode;
  message: string;                 // safe template + counts only
  source_version: string | null;
}

/** Build a warning whose message is a controlled template (no secrets). */
export function warn(code: WarningCode, message: string, sourceVersion: string | null = null): ParseWarning {
  return { code, message, source_version: sourceVersion };
}

export interface SessionMeta {
  surface: Surface;
  /** Canonical ID (see ids.ts). null + `unknown-workspace` warning when
   *  the workspace identity is not stable — uniqueness not guaranteed. */
  id: string | null;
  /** Presentation key for id:null rows — ephemeral, never persisted. */
  display_key: string;
  /** DECISION (stricter than spec, intentional): spec allowed titles
   *  behind a flag; we emit `null` unconditionally because real
   *  `customTitle`/`threads.title` values are auto-generated from
   *  message content — a title is content-derived, not metadata.
   *  Not a bug; do not "fix" by surfacing stored titles. */
  title: string | null;
  started_at: string | null;
  ended_at: string | null;
  source_version: string | null;
  workspace_hash: string | null;
  event_count: number | null;
  parse_warnings: ParseWarning[];
}

export interface SourceResult {
  surface: Surface;
  state: SessionState;
  sessions: SessionMeta[];
  warnings: ParseWarning[];
}

/** Inputs every surface parser receives. `home` abstracts the user
 *  profile dir so tests pass a synthetic fixture root. `appdata` is the
 *  roaming profile dir on Windows (defaults to home/AppData/Roaming on
 *  win32-style roots, home/.config elsewhere — parsers pick per their
 *  source layout). */
export interface CollectEnv {
  home: string;
  platform: NodeJS.Platform;
  /** Absolute override for the roaming app-data dir (VS Code storage). */
  appdata?: string;
  env?: NodeJS.ProcessEnv;
}

export type CollectMode = 'metadata' | 'full';

export interface SurfaceParser {
  surface: Surface;
  collect(env: CollectEnv, mode: CollectMode): SourceResult;
}

export function result(surface: Surface, state: SessionState, sessions: SessionMeta[], warnings: ParseWarning[] = []): SourceResult {
  if (state === 'ok' && (warnings.length > 0 || sessions.some(s => s.parse_warnings.length > 0))) state = 'partial';
  return { surface, state, sessions, warnings };
}
