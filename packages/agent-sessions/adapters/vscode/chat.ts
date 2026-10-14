/**
 * `@sessions` chat participant — vscode glue only. Rendering lives
 * in chatModel.ts (pure). Errors never leak: a broken answer
 * degrades to a fixed safe message.
 */

import * as vscode from 'vscode';
import type { SourceResult } from '../../src/model.ts';
import { answer } from './chatModel.ts';

/** Must match `contributes.chatParticipants[].id` in package.json. */
const PARTICIPANT_ID = 'agent-sessions.sessions';
const FALLBACK = 'session data unavailable — run the Refresh command or check the Agent Sessions view';

export function createSessionsParticipant(getResults: () => SourceResult[]): vscode.ChatParticipant {
  const handler: vscode.ChatRequestHandler = (request, _context, stream, _token) => {
    try {
      stream.markdown(answer(request.prompt, getResults()));
    } catch {
      stream.markdown(FALLBACK);
    }
    return {};
  };
  return vscode.chat.createChatParticipant(PARTICIPANT_ID, handler);
}
