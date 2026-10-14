#!/usr/bin/env node
/**
 * cdp-drive.mjs — minimal CDP driver for automating Electron/VS Code
 * workbench surfaces. Zero deps (WebSocket + fetch are native on
 * Node >=22). Used by .devin/skills/vscode-gui-test/.
 *
 *   node tools/cdp-drive.mjs --port 9333 --list
 *   node tools/cdp-drive.mjs --port 9333 --eval 'document.title'
 *   node tools/cdp-drive.mjs --port 9333 --type '@sessions '
 *   node tools/cdp-drive.mjs --port 9333 --key Enter [--mods 3]
 *   node tools/cdp-drive.mjs --port 9333 --click 640,400
 *   node tools/cdp-drive.mjs --port 9333 --shot /tmp/out.png
 *   node tools/cdp-drive.mjs --port 9333 --eval-file /tmp/expr.js
 *
 * Flags: --port N (default 9222), --match <substr> picks a target whose
 * URL contains it (default: vscode-file://), --sleep ms between ops.
 */
import { writeFileSync, readFileSync } from 'node:fs';

const arg = (name, dflt) => {
  const i = process.argv.indexOf(`--${name}`);
  return i === -1 ? dflt : process.argv[i + 1];
};
const has = (name) => process.argv.includes(`--${name}`);
const port = Number(arg('port', 9222));
const match = arg('match', 'vscode-file://');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
if (has('list')) {
  for (const t of targets) console.log(t.type.padEnd(8), t.url.slice(0, 100));
  process.exit(0);
}
const page = targets.find((t) => t.url.includes(match));
if (!page) {
  console.error(`no target matching ${match} — run --list`);
  process.exit(1);
}
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
let id = 0;
const pend = new Map();
ws.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
};
const send = (method, params = {}) =>
  new Promise((res) => { const i = ++id; pend.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });

const gap = Number(arg('sleep', 120));
let out = '';

if (has('eval') || has('eval-file')) {
  const expr = has('eval-file') ? readFileSync(arg('eval-file'), 'utf8') : arg('eval');
  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  out = JSON.stringify(r.result?.result?.value ?? r.result?.exceptionDetails ?? r.result, null, 0);
}
if (has('type')) {
  // char events — trigger Monaco suggest/completion (insertText does not)
  for (const ch of arg('type')) {
    await send('Input.dispatchKeyEvent', { type: 'char', text: ch, key: ch });
    await sleep(gap);
  }
  out = 'typed';
}
if (has('insert')) {
  await send('Input.insertText', { text: arg('insert') });
  out = 'inserted';
}
if (has('key')) {
  const k = arg('key'); const mods = Number(arg('mods', 0));
  const codes = { Enter: ['Enter', 13], Escape: ['Escape', 27], Tab: ['Tab', 9], Backspace: ['Backspace', 8] };
  const [code, vk] = codes[k] ?? [`Key${k.toUpperCase()}`, k.toUpperCase().charCodeAt(0)];
  for (const type of ['rawKeyDown', 'keyUp'])
    await send('Input.dispatchKeyEvent', { type, key: k, code, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk, modifiers: mods });
  out = 'keyed';
}
if (has('click')) {
  const [x, y] = arg('click').split(',').map(Number);
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 });
  out = 'clicked';
}
if (has('shot')) {
  const r = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync(arg('shot'), Buffer.from(r.result.data, 'base64'));
  out = `shot ${arg('shot')}`;
}
console.log(out);
ws.close();
