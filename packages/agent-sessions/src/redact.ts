/**
 * Vendored TS port of the TEXT surface of the Python `devin-redact` engine
 * (devin-state/packages/redact: patterns.py + engine.py `scan_text` /
 * `redact_text`). Byte-parity contract: test/redact-corpus.jsonl,
 * enforced bidirectionally by tools/check_redact_parity.py.
 *
 * Porting traps:
 *  - Python `\b` is Unicode-aware (é is a word char); JS `\b` is ASCII-only.
 *    All boundaries are spelled as \p lookarounds (WB).
 *  - `ast.literal_eval` is a hand-rolled recognizer for exactly the grammar
 *    that yields a str/bytes (or 1-tuple thereof): parens, quoted literals
 *    with r/b/u/rb/br prefixes, implicit concatenation, `#` comments.
 *  - `_fingerprint` encodes utf-8 with surrogatepass — a manual encoder keeps
 *    lone surrogates identical to Python.
 */

import { createHash } from 'node:crypto';

// Python \w on str = letters + numbers + underscore (Unicode).
const W = '[\\p{L}\\p{N}_]';
// Python \b = transition between word and non-word (or string edge).
const WB = `(?:(?<!${W})(?=${W})|(?<=${W})(?!${W}))`;
const rx = (src: string, flags = ''): RegExp => new RegExp(src, `gud${flags}`);

// Order matters — mirrors PATTERNS dict insertion order.
const PATTERNS: [string, RegExp[]][] = [
  ['api_key', [
    rx(String.raw`${WB}sk-(?:proj-)?[A-Za-z0-9_-]{16,}${WB}`),
    rx(String.raw`${WB}sk_live_[A-Za-z0-9]{16,}${WB}`),
    rx(String.raw`${WB}rk_live_[A-Za-z0-9]{16,}${WB}`),
    rx(String.raw`${WB}(?:AKIA|ASIA)[0-9A-Z]{16}${WB}`),
    rx(String.raw`${WB}AIza[0-9A-Za-z_-]{35}${WB}`),
    rx(String.raw`${WB}xox[baprs]-[0-9A-Za-z-]{10,}${WB}`),
  ]],
  ['bearer_token', [
    rx(String.raw`[Bb]earer\s+([A-Za-z0-9._~+/=-]{16,})`),
    rx(String.raw`${WB}(eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})${WB}`),
  ]],
  ['github_token', [
    rx(String.raw`${WB}gh[pousr]_[A-Za-z0-9]{20,}${WB}`),
    rx(String.raw`${WB}github_pat_[A-Za-z0-9_]{22,}${WB}`),
  ]],
  ['private_key', [
    rx(String.raw`-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----`, 's'),
  ]],
  ['env_assignment', [
    rx(String.raw`^\s*(?:export\s+)?[A-Za-z_][A-Za-z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*\s*=\s*\S[^\n]*`, 'm'),
  ]],
  ['devin_pairing_code', [
    rx(String.raw`(?:pairing|pair)[ -]?code\s*[:=]?\s*([A-Z0-9]{4}(?:-[A-Z0-9]{4}){1,3})`, 'i'),
  ]],
  ['email', [
    rx(String.raw`${WB}[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}${WB}`),
  ]],
  ['absolute_path', [
    rx(String.raw`${WB}[A-Za-z]:\\Users\\[^\s"'<>|]+`),
    rx(String.raw`(?<![\p{L}\p{N}_/.-])/(?:home|Users)/[^\s"'<>|]+`),
  ]],
];

const PATTERN_NAMES: Record<string, string[]> = {
  api_key: ['openai_key', 'stripe_live_key', 'stripe_restricted_key', 'aws_access_key_id', 'google_api_key', 'slack_token'],
  bearer_token: ['bearer_header', 'jwt'],
  github_token: ['github_token', 'github_fine_grained_pat'],
  private_key: ['pem_private_key'],
  env_assignment: ['env_assignment'],
  devin_pairing_code: ['devin_pairing_code'],
  email: ['email'],
  absolute_path: ['windows_user_path', 'posix_home_path'],
};

function patternName(category: string, index: number): string {
  const names = PATTERN_NAMES[category] ?? [];
  return names[index] ?? `${category}[${index}]`;
}

const REDACTED_TAG = '<REDACTED:';

// --- _fingerprint -----------------------------------------------------------
// sha256(value.encode('utf-8', 'surrogatepass'))[:16]. The manual encoder keeps
// lone surrogates identical to Python (JS 'utf8' would emit U+FFFD instead).
function utf8SurrogatePass(value: string): Buffer {
  const bytes: number[] = [];
  for (const ch of value) {
    const cp = ch.codePointAt(0)!;
    if (cp < 0x80) bytes.push(cp);
    else if (cp < 0x800) bytes.push(0xc0 | (cp >> 6), 0x80 | (cp & 0x3f));
    else if (cp < 0x10000) bytes.push(0xe0 | (cp >> 12), 0x80 | ((cp >> 6) & 0x3f), 0x80 | (cp & 0x3f));
    else bytes.push(0xf0 | (cp >> 18), 0x80 | ((cp >> 12) & 0x3f), 0x80 | ((cp >> 6) & 0x3f), 0x80 | (cp & 0x3f));
  }
  return Buffer.from(bytes);
}

function fingerprint(value: string): string {
  return createHash('sha256').update(utf8SurrogatePass(value)).digest('hex').slice(0, 16);
}

const tag = (value: string): string => `<REDACTED:${fingerprint(value)}>`;

// --- _mask / _line_of -------------------------------------------------------
// Python str.splitlines() boundaries: \n \r \r\n \v \f \x1c-\x1e \x85 \u2028 \u2029.
const LINE_BREAKS = new Set(['\n', '\r', '\v', '\f', '\x1c', '\x1d', '\x1e', '\x85', '\u2028', '\u2029']);

function mask(value: string): string {
  if (value.includes('\n')) {
    let cut = value.length;
    for (let i = 0; i < value.length; i++) {
      if (LINE_BREAKS.has(value.charAt(i))) { cut = i; break; }
    }
    value = value.slice(0, cut);
  }
  const cps = Array.from(value); // Python len()/slicing count code points
  if (cps.length <= 6) return '*'.repeat(cps.length);
  return `${cps.slice(0, 4).join('')}...${cps.slice(-4).join('')}`;
}

function lineOf(text: string, offset: number): number {
  let line = 1;
  for (let i = 0; i < offset; i++) if (text[i] === '\n') line++;
  return line;
}

// --- _literal_string_value --------------------------------------------------
// str.strip() whitespace = Unicode isspace() — note: NOT \ufeff (JS trim would).
const PY_WS = '\\x09-\\x0d\\x1c-\\x1f\\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000';
const STRIP_RE = new RegExp(`^[${PY_WS}]+|[${PY_WS}]+$`, 'g');
const CODE_VALUE_RE = /^\s*(?:[(\[{]|[A-Za-z_][\p{L}\p{N}_.]*\s*\()/u;

type LitKind = 'str' | 'bytes' | 'tuple1' | 'other';
interface P { s: string; i: number }

// Whitespace between tokens: space/tab/formfeed always, \n \r and comments
// only inside parens (CPython tokenizer rules).
function skipTrivia(p: P, inner: boolean): void {
  const s = p.s;
  for (;;) {
    const c = s[p.i];
    if (c === ' ' || c === '\t' || c === '\f') { p.i++; continue; }
    if (inner && (c === '\n' || c === '\r')) { p.i++; continue; }
    if (c === '#') {
      while (p.i < s.length && s[p.i] !== '\n' && s[p.i] !== '\r') p.i++;
      continue;
    }
    break;
  }
}

// Top-level tail: only whitespace, newlines and comments may follow the value.
function skipTail(p: P): void {
  const s = p.s;
  for (;;) {
    const c = s[p.i];
    if (c === ' ' || c === '\t' || c === '\f' || c === '\n' || c === '\r') { p.i++; continue; }
    if (c === '#') {
      while (p.i < s.length && s[p.i] !== '\n' && s[p.i] !== '\r') p.i++;
      continue;
    }
    break;
  }
}

const isHex = (s: string): boolean => /^[0-9A-Fa-f]+$/.test(s);

// Scan one string literal at p.i. Returns 'str'|'bytes' and advances past it,
// or null (leaves p.i at the literal start) when the token isn't one literal
// Python would accept: bad prefix, unterminated, EOL in single-quoted,
// non-ASCII in a bytes literal, or a truncated \x / \u / \U / \N{} escape.
function scanLiteral(p: P): LitKind | null {
  const s = p.s;
  let j = p.i;
  let prefix = '';
  while (j < s.length && /[A-Za-z]/.test(s.charAt(j))) prefix += s.charAt(j++);
  const q = s[j];
  if (q !== "'" && q !== '"') return null;
  const low = prefix.toLowerCase();
  let kind: 'str' | 'bytes';
  if (low === '' || low === 'r' || low === 'u') kind = 'str';
  else if (low === 'b' || low === 'rb' || low === 'br') kind = 'bytes';
  else return null; // f*/t*/ur*/name — literal_eval rejects (or not a string)
  const raw = low.includes('r');
  const triple = s[j + 1] === q && s[j + 2] === q;
  j += triple ? 3 : 1;
  const start = j;
  let end = -1;
  while (j < s.length) {
    const c = s[j];
    if (c === '\\') {
      const e = s[j + 1];
      if (e === undefined) return null;
      if (!raw) {
        const hex = e === 'x' ? 2 : kind === 'str' && e === 'u' ? 4 : kind === 'str' && e === 'U' ? 8 : 0;
        if (hex && (j + 2 + hex > s.length || !isHex(s.slice(j + 2, j + 2 + hex)))) return null;
        if (kind === 'str' && e === 'N') {
          if (s[j + 2] !== '{') return null;
          const close = s.indexOf('}', j + 3);
          if (close <= j + 3) return null;
        }
      }
      j += 2;
      continue;
    }
    if (!triple && (c === '\n' || c === '\r')) return null;
    if (c === q) {
      if (triple) {
        if (s[j + 1] === q && s[j + 2] === q) { end = j + 3; break; }
        j++;
        continue;
      }
      end = j + 1;
      break;
    }
    j++;
  }
  if (end === -1) return null;
  if (kind === 'bytes' && /[^\x00-\x7f]/.test(s.slice(start, triple ? end - 3 : end - 1))) return null;
  p.i = end;
  return kind;
}

// One literal_eval-able value: string literal(s) — implicitly concatenated —
// or a parenthesized expression (grouping or one-element tuple). Anything else
// fails the same way literal_eval fails / returns a non-str value: null.
function parseExpr(p: P, inner: boolean): LitKind | null {
  skipTrivia(p, inner);
  const s = p.s;
  if (s[p.i] === '(') {
    p.i++;
    const k = parseExpr(p, true);
    if (k === null) return null;
    skipTrivia(p, true);
    if (s[p.i] === ',') {
      p.i++;
      skipTrivia(p, true);
      if (s[p.i] !== ')') return null;
      p.i++;
      return k === 'str' || k === 'bytes' ? 'tuple1' : 'other';
    }
    if (s[p.i] !== ')') return null;
    p.i++;
    return k;
  }
  let kind: LitKind | null = null;
  for (;;) {
    const lit = scanLiteral(p);
    if (lit === null) break;
    if (kind !== null && kind !== lit) return null; // mixed str+bytes concat
    kind = lit;
    skipTrivia(p, inner);
  }
  return kind;
}

// _literal_string_value: rhs parses to a str/bytes literal or a 1-tuple of one.
function literalStringValue(rhs: string): boolean {
  const s = rhs.replace(STRIP_RE, '');
  const p: P = { s, i: 0 };
  let kind: LitKind | null;
  try {
    kind = parseExpr(p, false);
  } catch {
    return false; // RecursionError parity on absurd nesting depth
  }
  if (kind === null) return false;
  skipTail(p);
  return p.i === s.length && kind !== 'other';
}

// _looks_like_code_assignment: suppress env_assignment hits whose RHS is a
// container literal or a call — unless it still parses as a plain literal.
function looksLikeCodeAssignment(whole: string): boolean {
  const eq = whole.indexOf('=');
  if (eq === -1) return false;
  const rhs = whole.slice(eq + 1);
  if (!CODE_VALUE_RE.test(rhs)) return false;
  return !literalStringValue(rhs);
}

// --- _iter_matches ----------------------------------------------------------
interface RawMatch {
  category: string;
  name: string;
  m: RegExpExecArray;
}

// A closed <REDACTED:…> tag — prior redaction output. Only this span is
// off-limits to re-processing; text around it is not.
const TAG_RUN = /<REDACTED:[^>\n]*>/gud;

// env_assignment without the ^ anchor — used ONLY by the tag-gap fragment
// rescan. The anchored pattern misses a KEY= candidate that does not lead
// the fragment: after a closed tag, non-key text may come first
// ('API_KEY=<tag>suffix OTHER_TOKEN=raw' left the tail raw). \s* plus a
// word-boundary lookbehind on the name reproduces the anchored match
// exactly at a key-led fragment start — leading whitespace stays inside
// the match — and still finds each KEY= later in the fragment.
const ENV_FRAGMENT_RE = rx(
  String.raw`\s*(?<!${W})(?:export\s+)?[A-Za-z_][A-Za-z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*\s*=\s*\S[^\n]*`,
);

// _ShiftedMatch: a fragment match re-rooted in the parent text's
// coordinates. A RegExpExecArray is a plain Array plus index/input/indices,
// so a copy with the offsets shifted carries everything consumers read
// (m[0], m[1], m.index, m.indices).
function shiftedMatch(m: RegExpExecArray, delta: number): RegExpExecArray {
  const copy = Array.from(m) as RegExpExecArray & { indices?: [number, number][] };
  copy.index = m.index + delta;
  copy.input = m.input;
  const idx = (m as RegExpExecArray & { indices?: [number, number][] }).indices;
  if (idx !== undefined) {
    copy.indices = idx.map((span) =>
      span === undefined ? span : ([span[0] + delta, span[1] + delta] as [number, number]),
    ) as [number, number][];
  }
  return copy;
}

// _comment_start: index of the first '#' outside quotes — where comment
// text begins — or s.length when the line has no comment.
function commentStart(s: string): number {
  let single = false;
  let double = false;
  let i = 0;
  while (i < s.length) {
    const ch = s.charAt(i);
    if (single) {
      if (ch === '\\') i += 1;
      else if (ch === "'") single = false;
    } else if (double) {
      if (ch === '\\') i += 1;
      else if (ch === '"') double = false;
    } else if (ch === "'") single = true;
    else if (ch === '"') double = true;
    else if (ch === '#') return i;
    i += 1;
  }
  return s.length;
}

// _enclosures_closed: true when s leaves no open enclosure — brackets
// balanced, no dangling quote, no comment. Tells whether a fragment
// boundary sits inside a literal, container or comment, where a redaction
// replacement could eat the enclosure's delimiters and corrupt valid
// source. A tiny state machine, not a parser: quotes inside the other
// quote kind and backslash escapes are handled; a '#' outside quotes
// makes the rest of the line a comment, so the candidate is dropped (an
// over-cautious answer only keeps the old skip, which is safe).
function enclosuresClosed(s: string): boolean {
  let depth = 0;
  let single = false;
  let double = false;
  let i = 0;
  while (i < s.length) {
    const ch = s.charAt(i);
    if (single) {
      if (ch === '\\') i += 1; // escaped char — can't close the quote
      else if (ch === "'") single = false;
    } else if (double) {
      if (ch === '\\') i += 1;
      else if (ch === '"') double = false;
    } else if (ch === "'") single = true;
    else if (ch === '"') double = true;
    else if (ch === '#') return false;
    else if (ch === '(' || ch === '[' || ch === '{') depth += 1;
    else if (ch === ')' || ch === ']' || ch === '}') depth -= 1;
    i += 1;
  }
  return depth === 0 && !single && !double;
}

// _iter_fragment_matches: re matches inside text[lo:hi] shifted by lo.
// env candidates get the code-assignment guard plus the enclosure check:
// the value text from valueStart must reach each side of the candidate
// with every bracket closed and quote paired — a candidate inside '…',
// "…" or […/(…/{… is dropped rather than let its replacement eat
// delimiters.
function* iterFragmentMatches(
  re: RegExp,
  text: string,
  lo: number,
  hi: number,
  env: boolean,
  valueStart: number,
): Generator<RegExpExecArray> {
  if (env) {
    // An unquoted '#' starts a comment: the tail is comment text, not
    // rescan candidates — but the secret *before* it must still redact,
    // so the fragment is trimmed there (plus the whitespace between
    // value and marker, which belongs to the comment).
    hi = lo + commentStart(text.slice(lo, hi));
    while (hi > lo && (text.charAt(hi - 1) === ' ' || text.charAt(hi - 1) === '\t')) hi -= 1;
  }
  if (lo >= hi) return;
  for (const m of text.slice(lo, hi).matchAll(re)) {
    const whole = m[0];
    if (whole.includes(REDACTED_TAG)) {
      // A malformed (unclosed) tag inside the fragment — still never
      // re-processed, same as the whole-match rule.
      continue;
    }
    if (env) {
      if (looksLikeCodeAssignment(whole)) continue;
      const start = lo + m.index;
      const end = start + whole.length;
      if (!(enclosuresClosed(text.slice(valueStart, start)) && enclosuresClosed(text.slice(valueStart, end)))) {
        continue;
      }
    }
    yield shiftedMatch(m, lo);
  }
}

// _iter_tag_gap: re matches inside the tag-free fragments of m.
//
// A match containing <REDACTED:…> is prior redaction output — but only
// the tag's own span is off-limits. Greedy patterns reach past the tag:
// env_assignment swallows the rest of the line, so a second secret inside
// the same match — the OTHER= in 'KEY=<REDACTED:x> OTHER=raw' — would
// stay raw if the whole match were dropped, and it can never match
// separately (the pattern is ^-anchored). Each tag-free fragment is
// therefore re-scanned with the same pattern (devin-state#66). A
// '<REDACTED:' prefix with no closing '>' is malformed, not a real tag —
// the old whole-match skip still applies there.
function* iterTagGap(
  re: RegExp,
  text: string,
  m: RegExpExecArray,
  env: boolean,
): Generator<RegExpExecArray> {
  const whole = m[0];
  const end = m.index + whole.length;
  const tags = [...text.slice(m.index, end).matchAll(TAG_RUN)];
  if (tags.length === 0) return;
  // env fragments re-scan with the de-anchored variant — re is ^-anchored
  // and would miss a KEY= that does not lead the fragment.
  const scanRe = env ? ENV_FRAGMENT_RE : re;
  // For env_assignment the enclosure state is measured from the value's
  // first char — the position after '='.
  const valueStart = env ? m.index + whole.indexOf('=') + 1 : m.index;
  let pos = m.index;
  for (const t of tags) {
    yield* iterFragmentMatches(scanRe, text, pos, m.index + t.index, env, valueStart);
    pos = m.index + t.index + t[0].length;
  }
  yield* iterFragmentMatches(scanRe, text, pos, end, env, valueStart);
}

function* iterMatches(text: string): Generator<RawMatch> {
  for (const [category, regexes] of PATTERNS) {
    const env = category === 'env_assignment';
    for (let i = 0; i < regexes.length; i++) {
      const re = regexes[i];
      if (re === undefined) continue;
      for (const m of text.matchAll(re)) {
        if (m[0].includes(REDACTED_TAG)) {
          // Prior redaction output — re-scan only the tag-free fragments;
          // the env code guard and the enclosure check apply per fragment.
          for (const fm of iterTagGap(re, text, m, env)) {
            yield { category, name: patternName(category, i), m: fm };
          }
          continue;
        }
        if (env && looksLikeCodeAssignment(m[0])) continue;
        yield { category, name: patternName(category, i), m };
      }
    }
  }
}

// sensitive_match: group 1 when the pattern has one, else the whole match.
// m[1] !== undefined is Python's truthy match.lastindex for these patterns
// (each has at most one group, mandatory when present).
function sensitive(m: RegExpExecArray): { value: string; start: number; end: number } {
  const idx = (m as RegExpExecArray & { indices?: [number, number][] }).indices;
  if (m[1] !== undefined && idx?.[1] !== undefined) {
    return { value: m[1], start: idx[1][0], end: idx[1][1] };
  }
  return { value: m[0], start: m.index, end: m.index + m[0].length };
}

// --- scan_text --------------------------------------------------------------
export interface Finding {
  file: string;
  category: string;
  pattern: string;
  kind: 'pattern';
  location: string;
  fingerprint: string;
  preview: string;
}

export function scanText(text: string, file: string, location: string): Finding[] {
  const findings: Finding[] = [];
  const seen = new Set<string>();
  for (const { category, name, m } of iterMatches(text)) {
    const { value, start } = sensitive(m);
    const key = `${category}${name}${start}`;
    if (seen.has(key)) continue;
    seen.add(key);
    findings.push({
      file,
      category,
      pattern: name,
      kind: 'pattern',
      location: `${location}:line ${lineOf(text, m.index)}`,
      fingerprint: fingerprint(value),
      preview: mask(value),
    });
  }
  return findings;
}

// --- redact_text ------------------------------------------------------------
export function redactText(text: string): {
  output: string;
  edits: { category: string; line: number; fingerprint: string }[];
} {
  const candidates: { start: number; end: number; replacement: string; category: string; fp: string }[] = [];
  for (const { category, m } of iterMatches(text)) {
    const { value, start, end } = sensitive(m);
    const fp = fingerprint(value);
    if (category === 'env_assignment') {
      const whole = m[0];
      const eq = whole.indexOf('='); // keep the KEY= prefix
      candidates.push({
        start: m.index,
        end: m.index + whole.length,
        replacement: `${whole.slice(0, eq + 1)}${tag(value)}`,
        category,
        fp,
      });
    } else {
      candidates.push({ start, end, replacement: tag(value), category, fp });
    }
  }
  // leftmost, then longest — JS sort is stable like Python's.
  candidates.sort((a, b) => (a.start - b.start) || ((b.end - b.start) - (a.end - a.start)));
  const accepted: typeof candidates = [];
  let lastEnd = -1;
  for (const cand of candidates) {
    if (cand.start >= lastEnd) {
      accepted.push(cand);
      lastEnd = cand.end;
    }
  }
  let output = text;
  const edits: { category: string; line: number; fingerprint: string }[] = [];
  for (let i = accepted.length - 1; i >= 0; i--) {
    const c = accepted[i]!; // i < length guaranteed by the loop bound
    output = output.slice(0, c.start) + c.replacement + output.slice(c.end);
    edits.push({ category: c.category, line: lineOf(text, c.start), fingerprint: c.fp });
  }
  edits.reverse();
  return { output, edits };
}

// --- pattern surface (parity check) -----------------------------------------
export function patternSurface(): Set<string> {
  const out = new Set<string>();
  for (const [category, regexes] of PATTERNS) {
    for (let i = 0; i < regexes.length; i++) out.add(`${category}:${patternName(category, i)}`);
  }
  return out;
}
