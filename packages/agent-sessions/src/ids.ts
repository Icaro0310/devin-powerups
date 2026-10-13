/**
 * Canonical ID contract — spec v3.4.4 (closed hierarchy).
 *
 *   <source>:native:<id>                 native identifier
 *   <source>:documented-alt:<id>         documented alternate identifier
 *   <source>:provisional-hash:<hash>     stable-field hash (flagged)
 *   <source>:<workspace-hash>:<kind>:<value>   with stable workspace hash
 *
 * Components are encoded so `:` can never appear inside a value — the
 * `:` separators stay unambiguous and the string round-trips. A derived
 * identifier is never rendered as `native`.
 *
 * Dedup scope: same `source` + same stable `workspace-hash` only.
 * Sessions with `id: null` (no stable workspace identity) are never
 * deduplicated and never claim canonical uniqueness.
 */

import { createHash } from 'node:crypto';
import type { Surface } from './model.ts';

export type IdKind = 'native' | 'documented-alt' | 'provisional-hash';

/** Encode one component: `%` first, then `:` — order matters. */
export function enc(component: string): string {
  return component.replace(/%/g, '%25').replace(/:/g, '%3A');
}

/** Stable workspace hash: sha256 of a normalized identity seed
 *  (git root, workspace folder URI, rollout cwd — caller normalizes:
 *  absolute, resolved, trailing separators stripped, case per platform).
 *  16 lowercase hex chars; not reversible, never contains the path. */
export function workspaceHash(seed: string): string {
  return createHash('sha256').update(seed, 'utf8').digest('hex').slice(0, 16);
}

export function canonicalId(surface: Surface, wsHash: string | null, kind: IdKind, value: string): string {
  const tail = `${kind}:${enc(value)}`;
  return wsHash ? `${surface}:${wsHash}:${tail}` : `${surface}:${tail}`;
}

/** Ephemeral presentation key for `id: null` sessions — position-based,
 *  in-memory only, never persisted, never presented as canonical. */
export function ephemeralKey(surface: Surface, index: number): string {
  return `${surface}:ephemeral:${index}`;
}
