/**
 * Parser registry + orchestration. One SourceResult per surface; a
 * parser throwing is converted into a `read-error` result — one broken
 * surface never blocks the others.
 */

import type { CollectEnv, CollectMode, SourceResult, SurfaceParser } from '../model.ts';
import { warn } from '../model.ts';
import { copilotCliParser } from './copilotCli.ts';
import { codexCliParser } from './codexCli.ts';
import { vscodeChatParser } from './vscodeChat.ts';

export const parsers: SurfaceParser[] = [copilotCliParser, codexCliParser, vscodeChatParser];

export function collectAll(env: CollectEnv, mode: CollectMode = 'metadata'): SourceResult[] {
  return parsers.map(p => {
    try {
      return p.collect(env, mode);
    } catch {
      return {
        surface: p.surface,
        state: 'read-error',
        sessions: [],
        warnings: [warn('partial-parse', 'parser failed; 0 sessions collected')],
      };
    }
  });
}
