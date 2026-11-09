// Redaction engine — vendored TypeScript port of devin-redact 0.2.6
// (packages/redact/src/devin_redact/{engine,patterns}.py).
//
// Fidelity contract: reproduces the Python engine's observable behavior for
// the text surface (scan_text / redact_text / pattern surface). File walking
// and SQLite storage from engine.py are intentionally out of scope. All 168
// upstream pattern definitions live in redact-patterns.ts, produced by the
// py2js translator documented there.
//
// Python `str` semantics are emulated where observable: Unicode \w/\b/\s via
// the translator, code-point counting for previews, str.splitlines() line
// breaks, str.strip() whitespace, ast.literal_eval literal shapes, and a
// CPython-compatible tokenizer for Python-source string spans (with the
// engine's delimiter fallback).

import { createHash } from 'node:crypto';
import {
  COMPILED,
  FILE_GATED_MAP,
  GUARD_EXEMPT_KEYS,
  HELPERS_RX,
  LOWER_DOTTED_TYPES,
  PY_SOURCE_NAMES,
  PY_SOURCE_SUFFIXES,
  SECRET_CATEGORIES,
  translatePy,
  TYPE_NAMES,
  type CompiledEntry,
} from './redact-patterns.ts';

// ---------------------------------------------------------------------------
// Python str helpers
// ---------------------------------------------------------------------------

const LINE_BREAKS = new Set([
  0x0a, 0x0d, 0x0b, 0x0c, 0x1c, 0x1d, 0x1e, 0x85, 0x2028, 0x2029,
]);

// Python str.isspace() set (same alphabet as the translator's \s).
const PY_WS = new Set([
  0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x1c, 0x1d, 0x1e, 0x1f, 0x20, 0x85,
  0xa0, 0x1680, 0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006,
  0x2007, 0x2008, 0x2009, 0x200a, 0x2028, 0x2029, 0x202f, 0x205f, 0x3000,
]);

function isPyWs(cp: number): boolean {
  return PY_WS.has(cp);
}

function cpLen(cp: number): number {
  return cp > 0xffff ? 2 : 1;
}

function pyStrip(s: string): string {
  return pyStripRight(pyStripLeft(s));
}

function pyStripLeft(s: string): string {
  let i = 0;
  while (i < s.length) {
    const c = s.codePointAt(i);
    if (c === undefined || !isPyWs(c)) break;
    i += cpLen(c);
  }
  return s.slice(i);
}

function cpBefore(s: string, b: number): number | undefined {
  if (b <= 0) return undefined;
  const lo = s.charCodeAt(b - 1);
  if (lo >= 0xdc00 && lo <= 0xdfff && b >= 2) {
    const hi = s.charCodeAt(b - 2);
    if (hi >= 0xd800 && hi <= 0xdbff) return s.codePointAt(b - 2);
  }
  return lo;
}

function pyStripRight(s: string): string {
  let b = s.length;
  while (b > 0) {
    const c = cpBefore(s, b);
    if (c === undefined || !isPyWs(c)) break;
    b -= cpLen(c);
  }
  return s.slice(0, b);
}

function pyLstrip(s: string): string {
  return pyStripLeft(s);
}

function pyRstrip(s: string): string {
  return pyStripRight(s);
}

/** Number of leading whitespace code points (Python len() counts cps). */
function pyLstripCount(s: string): number {
  let i = 0;
  let n = 0;
  while (i < s.length) {
    const c = s.codePointAt(i);
    if (c === undefined || !isPyWs(c)) break;
    i += cpLen(c);
    n++;
  }
  return n;
}

/** str.splitlines() equivalent (boundaries per Python docs). */
function splitLines(s: string): string[] {
  const out: string[] = [];
  let start = 0;
  let i = 0;
  while (i < s.length) {
    const c = s.codePointAt(i)!;
    const w = cpLen(c);
    if (LINE_BREAKS.has(c)) {
      out.push(s.slice(start, i));
      if (c === 0x0d && s.codePointAt(i + w) === 0x0a) {
        i += w + 1;
      } else {
        i += w;
      }
      start = i;
      continue;
    }
    i += w;
  }
  out.push(s.slice(start));
  return out;
}

// ---------------------------------------------------------------------------
// Fingerprint / preview / location (engine.py)
// ---------------------------------------------------------------------------

function fingerprint(value: string): string {
  // sha256 utf-8 surrogatepass == TextEncoder for valid input; lone
  // surrogates encode as U+FFFD (Python emits raw 3-byte form) — accepted
  // divergence on malformed input only.
  return createHash('sha256').update(value, 'utf8').digest('hex').slice(0, 16);
}

function tag(value: string): string {
  return `<REDACTED:${fingerprint(value)}>`;
}

function mask(value: string): string {
  // _mask: head-only preview.
  let v = value;
  if (v.includes('\n')) v = splitLines(v)[0]!;
  const chars = Array.from(v);
  if (chars.length <= 6) return '*'.repeat(chars.length);
  return chars.slice(0, 4).join('') + '...';
}

function lineOf(text: string, offset: number): number {
  let line = 1;
  const end = Math.min(offset, text.length);
  for (let i = 0; i < end; i++) {
    if (text.charCodeAt(i) === 0x0a) line++;
  }
  return line;
}

// ---------------------------------------------------------------------------
// File classification (engine.py _python_source_file)
// ---------------------------------------------------------------------------

const PY_NAMES = new Set(PY_SOURCE_NAMES);
const PY_SUFFIXES = PY_SOURCE_SUFFIXES.map((s) => s.toLowerCase());

function isPySourceFile(file: string): boolean {
  const i = file.lastIndexOf('/');
  const base = i < 0 ? file : file.slice(i + 1);
  if (PY_NAMES.has(base)) return true;
  const lower = base.toLowerCase();
  return PY_SUFFIXES.some((s) => lower.endsWith(s));
}

// ---------------------------------------------------------------------------
// Match facade — minimal re.Match stand-in (indices via 'd' flag)
// ---------------------------------------------------------------------------

interface PyMatch {
  0: string;
  1?: string;
  /** all capture groups: groups[0] == group(1), groups[1] == group(2), … */
  groups: (string | undefined)[];
  index: number;
  indices: ([number, number] | undefined)[];
  input: string;
}

function toPyMatch(m: RegExpExecArray, input: string): PyMatch {
  const idx = (m as unknown as { indices?: ([number, number] | undefined)[] }).indices;
  const groups: (string | undefined)[] = [];
  for (let gi = 1; gi < m.length; gi++) groups.push(m[gi]);
  const out: PyMatch = {
    0: m[0],
    groups,
    index: m.index,
    indices: idx ?? [[m.index, m.index + m[0].length]],
    input,
  };
  if (m[1] !== undefined) out[1] = m[1];
  return out;
}

/** re.Pattern.search(string, pos) equivalent — first match at/after pos. */
function searchFrom(re: RegExp, s: string, pos = 0): PyMatch | null {
  re.lastIndex = pos;
  const m = re.exec(s);
  return m === null ? null : toPyMatch(m, s);
}

/** re.match — match must start at index 0. */
function matchAt0(re: RegExp, s: string): PyMatch | null {
  re.lastIndex = 0;
  const m = re.exec(s);
  if (m === null || m.index !== 0) return null;
  return toPyMatch(m, s);
}

/** re.fullmatch — match must cover the entire string. */
function fullmatch(re: RegExp, s: string): PyMatch | null {
  re.lastIndex = 0;
  const m = re.exec(s);
  if (m === null || m.index !== 0 || m[0].length !== s.length) return null;
  return toPyMatch(m, s);
}

function* findAll(re: RegExp, s: string): Generator<PyMatch> {
  re.lastIndex = 0;
  for (const m of s.matchAll(re)) {
    yield toPyMatch(m, s);
  }
}

function mStart0(m: PyMatch): number {
  return m.indices[0]![0];
}
function mEnd0(m: PyMatch): number {
  return m.indices[0]![1];
}
function g1Span(m: PyMatch): [number, number] | null {
  if (m[1] === undefined) return null;
  const g = m.indices[1];
  return g === undefined ? null : [g[0], g[1]];
}

// ---------------------------------------------------------------------------
// ast.literal_eval port — only the str/bytes (or 1-tuple thereof) shape the
// engine cares about: _literal_string_value returns True iff literal_eval
// succeeds AND the value is str/bytes or a 1-tuple containing str/bytes.
// ---------------------------------------------------------------------------

type LitKind = 'str' | 'bytes' | 'other' | 'fail';

interface LitResult {
  kind: LitKind;
  /** for containers: element kinds (dict flattened k,v,k,v) */
  items?: LitKind[];
  tupleLen?: number;
  tupleSingleStrBytes?: boolean;
}

class LiteralParser {
  private i = 0;
  failed = false;
  private readonly s: string;
  constructor(s: string) {
    this.s = s;
  }

  private ws(): void {
    while (this.i < this.s.length) {
      const c = this.s[this.i]!;
      if (c === ' ' || c === '\t' || c === '\n' || c === '\r' || c === '\f' || c === '\v') this.i++;
      else break;
    }
  }
  private peek(off = 0): string {
    return this.s[this.i + off] ?? '';
  }
  private eat(ch: string): boolean {
    if (this.peek() === ch) {
      this.i++;
      return true;
    }
    return false;
  }
  private fail(): LitResult {
    this.failed = true;
    return { kind: 'fail' };
  }

  parse(): LitResult {
    this.ws();
    const v = this.atom();
    this.ws();
    // implicit string concatenation is part of the atom for strings
    if (this.i !== this.s.length) return this.fail();
    return v;
  }

  private atom(): LitResult {
    this.ws();
    const c = this.peek();
    if (c === '(') return this.paren();
    if (c === '[') return this.bracket('list');
    if (c === '{') return this.brace();
    if (c === '+' || c === '-') {
      this.i++;
      this.ws();
      const v = this.atom();
      // unary +/- only valid on numbers in literal_eval
      if (v.kind !== 'other' || this.numFlag) return this.fail();
      return v;
    }
    if (c === "'" || c === '"' || this.strPrefixAhead()) {
      return this.stringSeq();
    }
    if (/[0-9]/.test(c) || (c === '.' && /[0-9]/.test(this.peek(1)))) {
      return this.number();
    }
    if (this.s.startsWith('...', this.i)) {
      this.i += 3;
      return { kind: 'other' };
    }
    const m = /^[A-Za-z_][A-Za-z0-9_]*/.exec(this.s.slice(this.i));
    if (m !== null) {
      const w = m[0];
      if (w === 'True' || w === 'False' || w === 'None') {
        this.i += w.length;
        return { kind: 'other' };
      }
    }
    return this.fail();
  }

  private numFlag = false;

  private strPrefixAhead(): boolean {
    // [rRbBuUfF]+ immediately followed by a quote
    let j = this.i;
    while (j < this.s.length && /[rRbBuUfF]/.test(this.s[j]!)) j++;
    return j > this.i && (this.s[j] === "'" || this.s[j] === '"');
  }

  /** One or more adjacent string literals (implicit concat). */
  private stringSeq(): LitResult {
    let kind: 'str' | 'bytes' | null = null;
    for (;;) {
      const one = this.stringOne();
      if (one === null) return this.fail();
      if (kind === null) kind = one;
      else if (kind !== one) return this.fail(); // can't mix str+bytes
      this.ws();
      // another string literal adjacent?
      const c = this.peek();
      const nextIsStr =
        c === "'" ||
        c === '"' ||
        ((c !== '' && /[rRbBuUfF]/.test(c)) && this.strPrefixAhead());
      if (!nextIsStr) break;
    }
    return { kind: kind === 'bytes' ? 'bytes' : 'str' };
  }

  /** Single string literal → 'str' | 'bytes' | null(fail). */
  private stringOne(): 'str' | 'bytes' | null {
    let j = this.i;
    while (j < this.s.length && /[rRbBuUfF]/.test(this.s[j]!)) j++;
    const prefix = this.s.slice(this.i, j).toLowerCase();
    if (prefix.includes('f')) {
      this.failed = true;
      return null;
    }
    this.i = j;
    const q = this.peek();
    if (q !== "'" && q !== '"') return null;
    const triple = this.s.startsWith(q + q + q, this.i);
    let k = this.i + (triple ? 3 : 1);
    const n = this.s.length;
    while (k < n) {
      const c = this.s[k]!;
      if (c === '\\') {
        const nx = this.s[k + 1];
        if (nx === undefined) return null;
        k += nx === '\r' && this.s[k + 2] === '\n' ? 3 : 2;
        continue;
      }
      if (triple) {
        if (this.s.startsWith(q + q + q, k)) {
          this.i = k + 3;
          return prefix.includes('b') ? 'bytes' : 'str';
        }
        k++;
        continue;
      }
      if (c === q) {
        this.i = k + 1;
        return prefix.includes('b') ? 'bytes' : 'str';
      }
      if (c === '\n' || c === '\r') return null;
      k++;
    }
    return null;
  }

  private number(): LitResult {
    this.numFlag = true;
    // int/float/complex — all 'other' for our purposes; just validate shape.
    const start = this.i;
    const two = this.s.slice(this.i, this.i + 2).toLowerCase();
    if (two === '0x' || two === '0o' || two === '0b') {
      const base = two === '0x' ? 16 : two === '0o' ? 8 : 2;
      let j = this.i + 2;
      let digits = 0;
      while (j < this.s.length) {
        const c = this.s[j]!;
        const ok =
          (base === 16 && /[0-9a-fA-F_]/.test(c)) ||
          (base === 8 && /[0-7_]/.test(c)) ||
          (base === 2 && /[01_]/.test(c));
        if (!ok) break;
        if (c !== '_') digits++;
        j++;
      }
      if (digits === 0) return this.fail();
      const nx = this.s[j];
      if (nx !== undefined && /[A-Za-z0-9_.]/.test(nx)) {
        const cont =
          (base === 16 && /[0-9a-fA-F_]/.test(nx)) ||
          (base === 8 && /[0-7_]/.test(nx)) ||
          (base === 2 && /[01_]/.test(nx));
        if (!cont) return this.fail();
      }
      this.i = j;
      return { kind: 'other' };
    }
    let j = this.i;
    while (j < this.s.length && /[0-9_]/.test(this.s[j]!)) j++;
    const intPart = this.s.slice(this.i, j);
    if (intPart.includes('_') && (intPart.startsWith('_') || intPart.endsWith('_') || intPart.includes('__'))) {
      return this.fail();
    }
    if (this.s[j] === '.' && /[0-9]/.test(this.s[j + 1] ?? '')) {
      j++;
      while (j < this.s.length && /[0-9_]/.test(this.s[j]!)) j++;
    }
    if (this.s[j] === 'e' || this.s[j] === 'E') {
      let k = j + 1;
      if (this.s[k] === '+' || this.s[k] === '-') k++;
      if (k < this.s.length && /[0-9]/.test(this.s[k]!)) {
        j = k;
        while (j < this.s.length && /[0-9_]/.test(this.s[j]!)) j++;
      }
    }
    if (this.s[j] === 'j' || this.s[j] === 'J') j++;
    const full = this.s.slice(this.i, j);
    if (full.includes('_') && /(__|_$)/.test(full)) return this.fail();
    this.i = j;
    return { kind: 'other' };
  }

  /** Parenthesized: (x) groups, (x,) 1-tuple, () empty tuple. */
  private paren(): LitResult {
    this.i++;
    this.ws();
    if (this.eat(')')) return { kind: 'other', tupleLen: 0 };
    const items: LitKind[] = [];
    let trailingComma = false;
    for (;;) {
      this.ws();
      if (this.peek() === ')') {
        this.i++;
        break;
      }
      if (this.i >= this.s.length) return this.fail();
      const v = this.atom();
      if (v.kind === 'fail') return this.fail();
      items.push(v.kind);
      this.ws();
      if (this.eat(',')) {
        trailingComma = true;
        continue;
      }
      if (this.eat(')')) break;
      return this.fail();
    }
    if (items.length === 1 && !trailingComma) {
      // (x) is just x — propagate inner kind
      // re-parse not needed: we only stored kind; strings propagate via kind
      return { kind: items[0]!, tupleLen: 1, tupleSingleStrBytes: items[0] === 'str' || items[0] === 'bytes' };
    }
    return { kind: 'other', tupleLen: items.length, tupleSingleStrBytes: items.length === 1 && (items[0] === 'str' || items[0] === 'bytes') };
  }

  private bracket(kind: 'list'): LitResult {
    this.i++;
    const items: LitKind[] = [];
    this.ws();
    if (this.eat(']')) return { kind: 'other', tupleLen: 0 };
    for (;;) {
      this.ws();
      if (this.peek() === ']') {
        this.i++;
        break;
      }
      if (this.i >= this.s.length) return this.fail();
      const v = this.atom();
      if (v.kind === 'fail') return this.fail();
      items.push(v.kind);
      this.ws();
      if (this.eat(',')) {
        this.ws();
        if (this.peek() === ']') {
          this.i++;
          break;
        }
        continue;
      }
      if (this.eat(']')) break;
      return this.fail();
    }
    return { kind: 'other', tupleLen: items.length };
  }

  private brace(): LitResult {
    this.i++;
    this.ws();
    if (this.eat('}')) return { kind: 'other', tupleLen: 0 };
    let isDict = false;
    for (;;) {
      this.ws();
      const k = this.atom();
      if (k.kind === 'fail') return this.fail();
      this.ws();
      if (this.eat(':')) {
        isDict = true;
        const v = this.atom();
        if (v.kind === 'fail') return this.fail();
      }
      this.ws();
      if (this.eat(',')) {
        this.ws();
        if (this.peek() === '}') {
          this.i++;
          break;
        }
        continue;
      }
      if (this.eat('}')) break;
      return this.fail();
    }
    return { kind: 'other', tupleLen: isDict ? -1 : 0 };
  }
}

/**
 * _literal_string_value(rhs): True iff ast.literal_eval(rhs.strip()) yields
 * str/bytes, or a 1-tuple whose single element is str/bytes.
 */
function literalStringValue(rhs: string): boolean {
  const p = new LiteralParser(pyStrip(rhs));
  const v = p.parse();
  if (p.failed || v.kind === 'fail') return false;
  if (v.kind === 'str' || v.kind === 'bytes') return true;
  // 1-tuple containing str/bytes — including parenthesized ("x") which our
  // paren() propagates as kind 'str' already; the tuple case arrives as
  // kind 'other' with tupleLen===1 && tupleSingleStrBytes.
  return v.tupleLen === 1 && v.tupleSingleStrBytes === true;
}

// ---------------------------------------------------------------------------
// Type-annotation / code-assignment guards (engine.py)
// ---------------------------------------------------------------------------

const RX = {
  sep: HELPERS_RX.sep,
  typeExpr: HELPERS_RX.typeExpr,
  rewriteType: HELPERS_RX.rewriteType,
  dottedPath: HELPERS_RX.dottedPath,
  codeValue: HELPERS_RX.codeValue,
  imp: HELPERS_RX.imp,
  fromImp: HELPERS_RX.fromImp,
  fromImpParen: HELPERS_RX.fromImpParen,
  comment: HELPERS_RX.comment,
  assignName: HELPERS_RX.assignName,
  name: HELPERS_RX.name,
  tagRun: HELPERS_RX.tagRun,
  envFragment: HELPERS_RX.envFragment,
  tripleQuote: HELPERS_RX.tripleQuote,
};

// Small ad-hoc Python `re` patterns for redact_text's env rewrite.
const RE_FIRST_COLON_EQ = translatePy('[:=]', 'u'); // re.search(r"[:=]", s)
const RE_COMMA_SEP = translatePy(',\\s*', 'u'); // re.search(r",\s*", whole)
const RE_ENV_PREFIX = translatePy(
  '(?:env|arg|set|setenv|setx|launchctl[ \\t]+setenv)(?:[ \\t]+[-/][a-zA-Z]+)*[ \\t]+\\S+[ \\t]+',
  'iu',
);
const RE_QM = translatePy('\\s*([rRbBuUfF]{0,2})(\\\\?[\\"\'`])', 'u');
const RE_PM = translatePy('([rRbBuUfF]*)(\\"\\"\\"|\'\'\'|[\\"\'])', 'u');
const RE_MT = translatePy('\\(\\s*(.+?)\\s*,\\s*\\)', 'u');
const RE_GQ = translatePy('[rRbBuUfF]*([\\"\'])', 'u'); // re.match on gtext

interface AliasInfo {
  aliases: Map<string, string>;
  stars: string[];
}

function importAliases(text: string, strings: Span[]): AliasInfo {
  const aliases = new Map<string, string>();
  const stars: string[] = [];
  const inside = (pos: number): boolean => insideSpans(strings, pos);

  const bind = (mod: string, names: string): void => {
    for (const rawPart of names.split(',')) {
      // part.strip().strip("()")
      let part = pyStrip(rawPart);
      part = part.replace(/^[()]+/, '').replace(/[()]+$/, '');
      if (part === '') continue;
      if (part === '*') {
        stars.push(mod);
        continue;
      }
      const sepIdx = part.indexOf(' as ');
      let name: string;
      let bound: string;
      if (sepIdx >= 0) {
        name = pyStrip(part.slice(0, sepIdx));
        bound = pyStrip(part.slice(sepIdx + 4));
      } else {
        name = pyStrip(part);
        bound = name;
      }
      if (fullmatch(RX.name, name) !== null && fullmatch(RX.name, bound) !== null) {
        aliases.set(bound, `${mod}.${name}`);
      }
    }
  };

  for (const m of findAll(RX.imp, text)) {
    const g1 = m.indices[1];
    if (g1 === undefined) continue;
    if (strings.length > 0 && inside(mStart0(m))) continue;
    const body = text.slice(g1[0], g1[1]);
    for (const part of body.split(',')) {
      const sepIdx = part.indexOf(' as ');
      if (sepIdx < 0) continue;
      const nameRaw = part.slice(0, sepIdx);
      const aliasRaw = part.slice(sepIdx + 4);
      const nameStripped = pyStrip(nameRaw);
      const aliasStripped = pyStrip(aliasRaw);
      const firstSeg = nameStripped.split('.')[0]!;
      if (
        aliasStripped !== '' &&
        fullmatch(RX.name, aliasStripped) !== null &&
        fullmatch(RX.name, firstSeg) !== null
      ) {
        aliases.set(aliasStripped, nameStripped);
      }
    }
  }

  for (const m of findAll(RX.fromImp, text)) {
    const g1 = m.indices[1];
    const g2 = m.indices[2];
    if (g1 === undefined || g2 === undefined) continue;
    if (strings.length > 0 && inside(mStart0(m))) continue;
    const mod = text.slice(g1[0], g1[1]).replace(/^\.+/, '');
    bind(mod, text.slice(g2[0], g2[1]));
  }

  for (const m of findAll(RX.fromImpParen, text)) {
    const g1 = m.indices[1];
    const g2 = m.indices[2];
    if (g1 === undefined || g2 === undefined) continue;
    if (strings.length > 0 && inside(mStart0(m))) continue;
    const mod = text.slice(g1[0], g1[1]).replace(/^\.+/, '');
    RX.comment.lastIndex = 0;
    const names = text.slice(g2[0], g2[1]).replace(RX.comment, '');
    bind(mod, names);
  }

  // Rebinding invalidates aliases (fail-closed).
  const rebound = new Set<string>();
  for (const m of findAll(RX.assignName, text)) {
    if (strings.length > 0 && inside(mStart0(m))) continue;
    for (let gi = 1; gi < m.indices.length; gi++) {
      const g = m.indices[gi];
      if (g !== undefined) rebound.add(text.slice(g[0], g[1]));
    }
  }
  for (const name of rebound) aliases.delete(name);

  return { aliases, stars };
}

function dottedTerminalIsType(path: string, bindings: AliasInfo | null): boolean {
  const dot = path.lastIndexOf('.');
  const head = path.slice(0, dot);
  const last = path.slice(dot + 1);
  if (TYPE_NAMES.has(last)) return true;
  const firstCh = [...last][0] ?? '';
  if (firstCh !== '' && /\p{Lu}/u.test(firstCh)) return true;
  const first0 = head.split('.')[0]!;
  let first = first0;
  if (bindings !== null && bindings.aliases.size + bindings.stars.length > 0) {
    first = (bindings.aliases.get(first0) ?? first0).split('.')[0]!;
  }
  const allowed = LOWER_DOTTED_TYPES[first];
  return allowed !== undefined && allowed.has(last);
}

function looksLikeTypeAnnotation(rhs: string, bindings: AliasInfo | null): boolean {
  // _looks_like_type_annotation — exact port.
  let v = pyStrip(rhs);
  if (v === '') return false;
  const hashIdx = v.indexOf(' #');
  if (hashIdx >= 0) v = v.slice(0, hashIdx);
  v = pyRstrip(v);
  const eqIdx = v.indexOf('=');
  if (eqIdx >= 0) {
    const tail = v.slice(eqIdx + 1);
    if (literalStringValue(tail)) return false;
    v = pyRstrip(v.slice(0, eqIdx));
  }
  if (v === '' || fullmatch(RX.typeExpr, v) === null) return false;
  if (v.includes('[') || v.includes('|')) {
    // every dotted path in the expression must terminate in a type name
    for (const dm of findAll(RX.dottedPath, v)) {
      if (!dottedTerminalIsType(dm[0], bindings)) return false;
    }
    return true;
  }
  if (v.includes('.')) {
    return (
      fullmatch(RX.dottedPath, v) !== null && dottedTerminalIsType(v, bindings)
    );
  }
  if (bindings !== null) {
    const resolved = bindings.aliases.get(v);
    if (resolved !== undefined) return dottedTerminalIsType(resolved, bindings);
    for (const mod of bindings.stars) {
      if (dottedTerminalIsType(`${mod}.${v}`, bindings)) return true;
    }
  }
  return TYPE_NAMES.has(v);
}

function looksLikeCodeAssignment(whole: string, bindings: AliasInfo | null): boolean {
  const sepM = searchFrom(RE_FIRST_COLON_EQ, whole);
  if (sepM === null) return false;
  const rhs = whole.slice(mEnd0(sepM));
  if (looksLikeTypeAnnotation(rhs, bindings)) return true;
  RX.codeValue.lastIndex = 0;
  if (!RX.codeValue.test(rhs)) return false;
  return !literalStringValue(rhs);
}

// ---------------------------------------------------------------------------
// CPython-compatible tokenizer → string spans (engine.py _string_spans /
// _tagged_string_spans with _delimiter_string_spans fallback)
// ---------------------------------------------------------------------------

interface Span {
  start: number;
  end: number;
}

interface StringInfo {
  /** multiline STRING-token spans (tok.end row > tok.start row) */
  strings: Span[];
  /** ALL STRING-token spans whose raw text contains '<REDACTED:' */
  tagged: Span[];
}

class TokError extends Error {}

const PREFIX_SET = new Set('rRbBuUfFtT'.split(''));

function isIdentStart(c: string): boolean {
  const cp = c.codePointAt(0) ?? 0;
  return /[A-Za-z_]/.test(c) || cp > 0x7f;
}
function isIdentPart(c: string): boolean {
  const cp = c.codePointAt(0) ?? 0;
  return /[A-Za-z0-9_]/.test(c) || cp > 0x7f;
}

function pyStringTokens(text: string): StringInfo {
  const strings: Span[] = [];
  const tagged: Span[] = [];
  const n = text.length;
  let i = 0;
  let paren = 0;
  const indents: { col: number; ws: string }[] = [{ col: 0, ws: '' }];
  let indentPending = true;
  let wsBuf = '';
  let logicalHasCode = false;

  const newlineLen = (p: number): number => {
    const c = text[p];
    if (c === '\n') return 1;
    if (c === '\r') return text[p + 1] === '\n' ? 2 : 1;
    return 0;
  };
  const indentCol = (ws: string): number => {
    let col = 0;
    for (const ch of ws) {
      if (ch === ' ') col += 1;
      else if (ch === '\t') col = (Math.floor(col / 8) + 1) * 8;
      else if (ch === '\f') col = 0;
    }
    return col;
  };
  const cmpWs = (ws: string): string => ws.split('\f').join('');

  const measureIndent = (): void => {
    const col = indentCol(wsBuf);
    const ws = cmpWs(wsBuf);
    const top = indents[indents.length - 1]!;
    if (col > top.col) {
      let ok = true;
      if (ws.includes('\t')) {
        if (!ws.startsWith(top.ws)) {
          const lt = ws.lastIndexOf('\t');
          ok = ws.length - lt - 1 >= top.col;
        }
      }
      if (!ok) throw new TokError('TabError');
      indents.push({ col, ws });
    } else if (col === top.col) {
      if (ws !== top.ws) throw new TokError('TabError');
    } else {
      while (indents.length > 1 && indents[indents.length - 1]!.col > col) indents.pop();
      const t2 = indents[indents.length - 1]!;
      if (t2.col !== col) throw new TokError('IndentationError');
      if (ws !== t2.ws) throw new TokError('TabError');
    }
  };

  const recordString = (start: number, end: number): void => {
    const raw = text.slice(start, end);
    const multi = raw.includes('\n') || raw.includes('\r');
    if (multi) strings.push({ start, end });
    if (raw.includes('<REDACTED:')) tagged.push({ start, end });
  };

  // ---- simple (non-f/t) string: pos = quote index, triple precomputed ----
  const scanSimple = (pos: number, triple: boolean): number => {
    const q = text[pos]!;
    let j = pos + (triple ? 3 : 1);
    while (j < n) {
      const c = text[j]!;
      if (c === '\\') {
        const nx = text[j + 1];
        if (nx === undefined) throw new TokError('unterminated string');
        if (nx === '\n' || nx === '\r') {
          j += nx === '\r' && text[j + 2] === '\n' ? 3 : 2;
          continue;
        }
        j += 2;
        continue;
      }
      if (triple) {
        if (text.startsWith(q + q + q, j)) return j + 3;
        j++;
        continue;
      }
      if (c === q) return j + 1;
      if (c === '\n' || c === '\r') throw new TokError('unterminated string');
      j++;
    }
    throw new TokError('unterminated string');
  };

  // forward decl for mutual recursion
  const scanDelimited = (tokStart: number, quotePos: number): number => {
    const q = text[quotePos]!;
    const triple = text.startsWith(q + q + q, quotePos);
    const end = scanSimple(quotePos, triple);
    recordString(tokStart, end);
    return end;
  };

  // ---- f/t-string: pos = index AFTER opening quote(s) ----
  const scanFString = (pos: number, q: string, triple: boolean): number => {
    interface Mode {
      mode: 'expr' | 'spec';
      fd: number;
    }
    const stack: Mode[] = [];
    let j = pos;
    const skipEsc = (p: number): number => {
      const nx = text[p + 1];
      if (nx === undefined) throw new TokError('unterminated f-string');
      if (nx === '\n' || nx === '\r') return p + (nx === '\r' && text[p + 2] === '\n' ? 3 : 2);
      return p + 2;
    };
    while (j < n) {
      const mode = stack[stack.length - 1];
      const c = text[j]!;
      if (mode === undefined) {
        // middle
        if (c === '{') {
          if (text[j + 1] === '{') {
            j += 2;
            continue;
          }
          stack.push({ mode: 'expr', fd: 1 });
          j++;
          continue;
        }
        if (c === '}') {
          if (text[j + 1] === '}') {
            j += 2;
            continue;
          }
          throw new TokError("f-string: single '}' is not allowed");
        }
        if (c === '\\') {
          j = skipEsc(j);
          continue;
        }
        if (!triple && (c === '\n' || c === '\r')) throw new TokError('unterminated f-string');
        if (triple ? text.startsWith(q + q + q, j) : c === q) return triple ? j + 3 : j + 1;
        j++;
        continue;
      }
      if (mode.mode === 'spec') {
        if (c === '{') {
          if (text[j + 1] === '{') {
            j += 2;
            continue;
          }
          stack.push({ mode: 'expr', fd: 1 });
          j++;
          continue;
        }
        if (c === '}') {
          if (text[j + 1] === '}') {
            j += 2;
            continue;
          }
          stack.pop(); // spec
          stack.pop(); // enclosing expr field
          j++;
          continue;
        }
        if (c === '\\') {
          j = skipEsc(j);
          continue;
        }
        if (!triple && (c === '\n' || c === '\r')) throw new TokError('unterminated f-string');
        if (triple ? text.startsWith(q + q + q, j) : c === q) return triple ? j + 3 : j + 1;
        j++;
        continue;
      }
      // expr
      if (c === '}') {
        mode.fd--;
        if (mode.fd === 0) stack.pop();
        j++;
        continue;
      }
      if (c === '{') {
        mode.fd++;
        j++;
        continue;
      }
      if (c === '#') {
        while (j < n && text[j] !== '\n' && text[j] !== '\r') j++;
        continue;
      }
      if (c === '\\') {
        j = skipEsc(j);
        continue;
      }
      if (c === ':' && mode.fd === 1) {
        stack.push({ mode: 'spec', fd: 0 });
        j++;
        continue;
      }
      if (c === "'" || c === '"') {
        j = scanDelimited(j, j);
        continue;
      }
      if (isIdentStart(c)) {
        let k = j;
        while (k < n && isIdentPart(text[k]!)) k++;
        const word = text.slice(j, k);
        const nx = text[k];
        if (
          (nx === "'" || nx === '"') &&
          word.length > 0 &&
          [...word].every((ch) => PREFIX_SET.has(ch))
        ) {
          const cls = classifyPrefix(word);
          if (cls === 'error') throw new TokError('incompatible string prefix');
          if (cls === 'dup') {
            j = k;
            continue;
          }
          const q2 = text[k]!;
          const trip = text.startsWith(q2 + q2 + q2, k);
          if (cls === 'f' || cls === 't') {
            j = scanFString(k + (trip ? 3 : 1), q2, trip);
            continue;
          }
          j = scanDelimited(j, k);
          continue;
        }
        j = k;
        continue;
      }
      j++;
    }
    throw new TokError('unterminated f-string');
  };

  const classifyPrefix = (word: string): 'plain' | 'f' | 't' | 'error' | 'dup' => {
    const lower = word.toLowerCase();
    const has = (ch: string): boolean => lower.includes(ch);
    const bad =
      (has('u') && (has('b') || has('r') || has('f') || has('t'))) ||
      (has('b') && (has('f') || has('t'))) ||
      (has('f') && has('t'));
    if (bad) return 'error';
    const seen = new Set<string>();
    for (const ch of lower) {
      if (seen.has(ch)) return 'dup';
      seen.add(ch);
    }
    if (has('f')) return 'f';
    if (has('t')) return 't';
    return 'plain';
  };

  // number scanner — throws TokError on invalid literals (→ fallback)
  const scanNumber = (start: number): number => {
    let j = start;
    const two = text.slice(j, j + 2).toLowerCase();
    if (two === '0x' || two === '0o' || two === '0b') {
      const base = two === '0x' ? 16 : two === '0o' ? 8 : 2;
      j += 2;
      let digits = 0;
      while (j < n) {
        const ch = text[j]!;
        const okd =
          (base === 16 && /[0-9a-fA-F_]/.test(ch)) ||
          (base === 8 && /[0-7_]/.test(ch)) ||
          (base === 2 && /[01_]/.test(ch));
        if (!okd) break;
        if (ch !== '_') digits++;
        j++;
      }
      if (digits === 0) throw new TokError('invalid literal');
      const nx = text[j];
      if (nx !== undefined && /[A-Za-z0-9_.]/.test(nx)) {
        const cont =
          (base === 16 && /[0-9a-fA-F_]/.test(nx)) ||
          (base === 8 && /[0-7_]/.test(nx)) ||
          (base === 2 && /[01_]/.test(nx));
        if (!cont) throw new TokError('invalid literal');
      }
      return j;
    }
    while (j < n && /[0-9_]/.test(text[j]!)) j++;
    const intText = text.slice(start, j);
    if (
      intText.includes('_') &&
      (intText.startsWith('_') || intText.endsWith('_') || intText.includes('__'))
    ) {
      throw new TokError('invalid decimal literal');
    }
    if (text[j] === '.' && /[0-9]/.test(text[j + 1] ?? '')) {
      j++;
      while (j < n && /[0-9_]/.test(text[j]!)) j++;
    }
    if (text[j] === 'e' || text[j] === 'E') {
      let k = j + 1;
      if (text[k] === '+' || text[k] === '-') k++;
      if (k < n && /[0-9]/.test(text[k]!)) {
        j = k;
        while (j < n && /[0-9_]/.test(text[j]!)) j++;
      }
    }
    if (text[j] === 'j' || text[j] === 'J') j++;
    const full = text.slice(start, j);
    if (full.includes('_') && /(__|_$)/.test(full)) throw new TokError('invalid decimal literal');
    return j;
  };

  // ---- main loop ----
  while (i < n) {
    const c = text[i]!;

    if (indentPending && (c === ' ' || c === '\t' || c === '\f')) {
      wsBuf += c;
      i++;
      continue;
    }
    if (c === '#') {
      while (i < n && text[i] !== '\n' && text[i] !== '\r') i++;
      if (indentPending) wsBuf = '';
      continue;
    }
    const nl = newlineLen(i);
    if (nl > 0) {
      if (paren === 0 && logicalHasCode) {
        indentPending = true;
        wsBuf = '';
        logicalHasCode = false;
      }
      i += nl;
      continue;
    }
    if (c === '\\') {
      const nx = text[i + 1];
      if (nx === '\n' || nx === '\r') {
        i += nx === '\r' && text[i + 2] === '\n' ? 3 : 2;
        continue;
      }
      i++;
      logicalHasCode = true;
      continue;
    }
    if (c === ' ' || c === '\t' || c === '\f') {
      i++;
      continue;
    }

    if (indentPending) {
      measureIndent();
      indentPending = false;
    }
    logicalHasCode = true;

    // quote → plain string
    if (c === "'" || c === '"') {
      const q = c;
      const triple = text.startsWith(q + q + q, i);
      const end = scanSimple(i, triple);
      recordString(i, end);
      i = end;
      continue;
    }
    // identifier → maybe prefixed string, else NAME
    if (isIdentStart(c)) {
      let k = i;
      while (k < n && isIdentPart(text[k]!)) k++;
      const word = text.slice(i, k);
      const nx = text[k];
      if (
        (nx === "'" || nx === '"') &&
        word.length > 0 &&
        [...word].every((ch) => PREFIX_SET.has(ch))
      ) {
        const cls = classifyPrefix(word);
        if (cls === 'error') throw new TokError('incompatible string prefix');
        if (cls === 'dup') {
          i = k; // NAME then plain string next iteration
          continue;
        }
        const q = text[k]!;
        const trip = text.startsWith(q + q + q, k);
        if (cls === 'f' || cls === 't') {
          i = scanFString(k + (trip ? 3 : 1), q, trip);
          continue;
        }
        const end = scanSimple(k, trip);
        recordString(i, end); // token span includes the prefix
        i = end;
        continue;
      }
      i = k;
      continue;
    }
    // number
    if (/[0-9]/.test(c) || (c === '.' && /[0-9]/.test(text[i + 1] ?? ''))) {
      i = scanNumber(i);
      continue;
    }
    // brackets
    if (c === '(' || c === '[' || c === '{') {
      paren++;
      i++;
      continue;
    }
    if (c === ')' || c === ']' || c === '}') {
      if (paren > 0) paren--;
      i++;
      continue;
    }
    i++;
  }

  if (paren > 0) throw new TokError('EOF in multi-line statement');
  return { strings, tagged };
}

/** _delimiter_string_spans fallback (engine.py). */
function delimiterStringSpans(text: string): Span[] {
  const spans: Span[] = [];
  let open: { start: number; delim: string } | null = null;
  for (const m of findAll(RX.tripleQuote, text)) {
    const idx = mStart0(m);
    const whole = m[0];
    let bs = 0;
    let p = idx - 1;
    while (p >= 0 && text[p] === '\\') {
      bs++;
      p--;
    }
    if (bs % 2 === 1) continue;
    if (open === null) {
      open = { start: idx, delim: whole };
    } else if (open.delim === whole) {
      spans.push({ start: open.start, end: idx + whole.length });
      open = null;
    }
  }
  if (open !== null) spans.push({ start: open.start, end: text.length });
  return spans;
}

function stringInfo(text: string): StringInfo {
  if (text.includes('\x00')) return fallbackInfo(text);
  try {
    return pyStringTokens(text);
  } catch {
    return fallbackInfo(text);
  }
}

function fallbackInfo(text: string): StringInfo {
  // _string_spans fallback returns ALL delimiter spans unfiltered (they are
  // inherently multiline-ish); _tagged_string_spans filters by tag presence.
  const spans = delimiterStringSpans(text);
  const tagged = spans.filter((sp) => {
    const seg = text.slice(sp.start, sp.end);
    RX.tagRun.lastIndex = 0;
    return RX.tagRun.test(seg);
  });
  return { strings: spans, tagged };
}

// ---------------------------------------------------------------------------
// Span membership (engine.py _inside_spans — sorted disjoint bisect)
// ---------------------------------------------------------------------------

function insideSpans(spans: Span[], pos: number): boolean {
  let lo = 0;
  let hi = spans.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    const sp = spans[mid]!;
    if (pos < sp.start) hi = mid;
    else if (pos >= sp.end) lo = mid + 1;
    else return true;
  }
  return false;
}

// ---------------------------------------------------------------------------
// Tag-gap rescanning helpers (engine.py _comment_start / _enclosures_closed)
// ---------------------------------------------------------------------------

/** _comment_start: index of first '#' outside '…'/"…" quotes, or len(s). */
function commentStart(s: string): number {
  let single = false;
  let dbl = false;
  let i = 0;
  while (i < s.length) {
    const ch = s[i]!;
    if (single) {
      if (ch === '\\') i += 1;
      else if (ch === "'") single = false;
    } else if (dbl) {
      if (ch === '\\') i += 1;
      else if (ch === '"') dbl = false;
    } else if (ch === "'") single = true;
    else if (ch === '"') dbl = true;
    else if (ch === '#') return i;
    i += 1;
  }
  return s.length;
}

/** _enclosures_closed: brackets balanced (any closer decrements), no
 *  dangling quote, no '#' outside quotes. */
function enclosuresClosed(s: string): boolean {
  let depth = 0;
  let single = false;
  let dbl = false;
  let i = 0;
  while (i < s.length) {
    const ch = s[i]!;
    if (single) {
      if (ch === '\\') i += 1;
      else if (ch === "'") single = false;
    } else if (dbl) {
      if (ch === '\\') i += 1;
      else if (ch === '"') dbl = false;
    } else if (ch === "'") single = true;
    else if (ch === '"') dbl = true;
    else if (ch === '#') return false;
    else if (ch === '(' || ch === '[' || ch === '{') depth += 1;
    else if (ch === ')' || ch === ']' || ch === '}') depth -= 1;
    i += 1;
  }
  return depth === 0 && !single && !dbl;
}

// ---------------------------------------------------------------------------
// Match iteration (engine.py _iter_matches / _iter_tag_gap /
// _iter_fragment_matches)
// ---------------------------------------------------------------------------

interface MatchHit {
  entry: CompiledEntry;
  m: PyMatch;
  viaTagGap: boolean;
}

function* iterFragmentMatches(
  scanRe: RegExp,
  text: string,
  lo: number,
  hi: number,
  env: boolean,
  valueStart: number,
  bindings: AliasInfo | null,
  strings: Span[],
  guardExempt: boolean,
): Generator<PyMatch> {
  let end = hi;
  if (env) {
    end = lo + commentStart(text.slice(lo, end));
    while (end > lo && (text[end - 1] === ' ' || text[end - 1] === '\t')) end--;
  }
  if (lo >= end) return;
  const seg = text.slice(lo, end);
  for (const fm of findAll(scanRe, seg)) {
    const whole = fm[0];
    if (whole.includes('<REDACTED:')) continue;
    const mStart = lo + fm.index;
    const mEnd = mStart + whole.length;
    if (env) {
      if (strings.length > 0 && insideSpans(strings, mStart)) {
        // inside a string literal: no annotation position — still yield
      } else if (!guardExempt && looksLikeCodeAssignment(whole, bindings)) {
        continue;
      }
      if (
        !(
          enclosuresClosed(text.slice(valueStart, mStart)) &&
          enclosuresClosed(text.slice(valueStart, mEnd))
        )
      ) {
        continue;
      }
    }
    // shift into text coordinates
    const shifted: PyMatch = {
      0: whole,
      groups: fm.groups,
      index: mStart,
      indices: fm.indices.map((g) =>
        g === undefined ? undefined : ([g[0] + lo, g[1] + lo] as [number, number]),
      ),
      input: text,
    };
    if (fm[1] !== undefined) shifted[1] = fm[1];
    yield shifted;
  }
}

function* iterTagGap(
  entry: CompiledEntry,
  text: string,
  m: PyMatch,
  env: boolean,
  bindings: AliasInfo | null,
  strings: Span[],
): Generator<PyMatch> {
  const mStart = mStart0(m);
  const mEnd = mEnd0(m);
  const tags: Span[] = [];
  RX.tagRun.lastIndex = 0;
  for (const tm of text.slice(mStart, mEnd).matchAll(RX.tagRun)) {
    tags.push({ start: mStart + tm.index, end: mStart + tm.index + tm[0].length });
  }
  if (tags.length === 0) return;

  const scanRe =
    entry.sub ?? (env && entry.index === 0 ? RX.envFragment : entry.re);
  const guardExempt = GUARD_EXEMPT_KEYS.has(entry.key);

  let valueStart = mStart;
  if (env) {
    // value_start = m.start() + (sep.start() + 1 if sep else 0) — sep is the
    // first ':'/'=' inside group(0); +1 lands after the separator char.
    const sepM = searchFrom(RE_FIRST_COLON_EQ, m[0]);
    if (sepM !== null) valueStart = mStart + mStart0(sepM) + 1;
  }

  let pos = mStart;
  for (const tagSpan of tags) {
    yield* iterFragmentMatches(scanRe, text, pos, tagSpan.start, env, valueStart, bindings, strings, guardExempt);
    pos = tagSpan.end;
  }
  yield* iterFragmentMatches(scanRe, text, pos, mEnd, env, valueStart, bindings, strings, guardExempt);
}

function* iterMatches(
  text: string,
  pyMode: boolean | null,
  file: string | undefined,
): Generator<MatchHit> {
  const computeStrings = pyMode !== false;
  // engine.py tokenizes unconditionally: _tagged_string_spans (single-line
  // literals carrying a tag) applies even when python_source is False, so
  // the tokenizer runs for every input; only `strings`/`bindings` are gated.
  const info = stringInfo(text);
  const strings = computeStrings ? info.strings : [];
  const taggedStrings = info.tagged;
  const bindings = computeStrings ? importAliases(text, strings) : null;

  for (const entry of COMPILED) {
    const gate = FILE_GATED_MAP.get(entry.key);
    if (gate !== undefined) {
      const fl = (file ?? '').toLowerCase();
      if (!gate.some((suf) => fl.endsWith(suf))) continue;
    }
    const env = entry.category === 'env_assignment';
    const exempt = GUARD_EXEMPT_KEYS.has(entry.key);
    for (const m of findAll(entry.re, text)) {
      const whole = m[0];
      if (whole.includes('<REDACTED:')) {
        for (const fm of iterTagGap(entry, text, m, env, bindings, strings)) {
          yield { entry, m: fm, viaTagGap: true };
        }
        continue;
      }
      if (env && taggedStrings.length > 0 && insideSpans(taggedStrings, mStart0(m))) continue;
      if (
        env &&
        !exempt &&
        !(strings.length > 0 && insideSpans(strings, mStart0(m))) &&
        looksLikeCodeAssignment(whole, bindings)
      ) {
        continue;
      }
      yield { entry, m, viaTagGap: false };
    }
  }
}

// ---------------------------------------------------------------------------
// sensitive value / span (engine.py sensitive_match + call-site span picks)
// ---------------------------------------------------------------------------

const BOM_RE = /^﻿+/;

function sensitiveValue(m: PyMatch): string {
  const raw = m[1] !== undefined ? m[1] : m[0];
  return raw.replace(BOM_RE, '');
}

// ---------------------------------------------------------------------------
// scan_text (engine.py)
// ---------------------------------------------------------------------------

export interface Finding {
  file: string;
  category: string;
  pattern: string;
  kind: 'pattern';
  location: string;
  fingerprint: string;
  preview: string;
}

export function scanText(text: string, file: string, location = 'blob'): Finding[] {
  const pyMode = isPySourceFile(file);
  interface Raw {
    category: string;
    name: string;
    m: PyMatch;
  }
  const raw: Raw[] = [];
  for (const hit of iterMatches(text, pyMode, file)) {
    raw.push({ category: hit.entry.category, name: hit.entry.name, m: hit.m });
  }
  raw.sort((a, b) => {
    if (a.category !== b.category) return a.category < b.category ? -1 : 1;
    const sa = mStart0(a.m);
    const sb = mStart0(b.m);
    if (sa !== sb) return sa - sb;
    return mEnd0(b.m) - mEnd0(a.m); // -end: longest first on shared start
  });
  const findings: Finding[] = [];
  const seen = new Set<string>();
  const accStarts = new Map<string, number[]>();
  const accEnds = new Map<string, number[]>();

  for (const t of raw) {
    const value = sensitiveValue(t.m);
    const sensStart = t.m[1] !== undefined ? g1Span(t.m)![0] : mStart0(t.m);
    const dkey = `${t.category}${t.name}${sensStart}`;
    if (seen.has(dkey)) continue;
    seen.add(dkey);
    const span: [number, number] = [mStart0(t.m), mEnd0(t.m)];
    const starts = accStarts.get(t.category) ?? [];
    const ends = accEnds.get(t.category) ?? [];
    // bisect_right(starts, span[0]) - 1 → last accepted start <= span[0]
    let lo = 0;
    let hi = starts.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (starts[mid]! <= span[0]) lo = mid + 1;
      else hi = mid;
    }
    const idx = lo - 1;
    if (idx >= 0 && ends[idx]! >= span[1]) continue;
    starts.splice(idx + 1, 0, span[0]);
    ends.splice(idx + 1, 0, span[1]);
    accStarts.set(t.category, starts);
    accEnds.set(t.category, ends);
    findings.push({
      file,
      category: t.category,
      pattern: t.name,
      kind: 'pattern',
      location: `${location}:line ${lineOf(text, mStart0(t.m))}`,
      fingerprint: fingerprint(value),
      preview: mask(value),
    });
  }
  return findings;
}

// ---------------------------------------------------------------------------
// redact_text (engine.py)
// ---------------------------------------------------------------------------

export interface Edit {
  category: string;
  line: number;
  fingerprint: string;
}

export interface RedactResult {
  output: string;
  edits: Edit[];
}

interface Candidate {
  start: number;
  end: number;
  replacement: string;
  category: string;
  fp: string;
}

export function redactText(text: string, file?: string | null): RedactResult {
  const fileHint = file ?? undefined;
  const pyMode: boolean | null = fileHint === undefined ? null : isPySourceFile(fileHint);
  const candidates: Candidate[] = [];

  for (const hit of iterMatches(text, pyMode, fileHint)) {
    const { entry, m, viaTagGap } = hit;
    const value = sensitiveValue(m);
    const fp = fingerprint(value);
    const t = tag(value);
    const g1 = g1Span(m);

    if (entry.category === 'env_assignment') {
      const whole = m[0];
      const mStart = mStart0(m);
      const mEnd = mEnd0(m);
      if (g1 !== null) {
        if (!viaTagGap && entry.sub !== undefined) {
          // run-capture arm: group 1 spans the whole argument run; only the
          // secret-bearing tokens inside it mask (sub-regex finditer).
          const sub = entry.sub;
          const gStart = g1[0];
          const gEnd = g1[1];
          for (const sm of findAll(sub, text.slice(gStart, gEnd))) {
            const sv = sm[1] !== undefined ? sm[1] : sm[0];
            const svFp = fingerprint(sv);
            candidates.push({
              start: gStart + sm.index,
              end: gStart + sm.index + sm[0].length,
              replacement: tag(sv),
              category: entry.category,
              fp: svFp,
            });
          }
          continue;
        }
        // group-1 env arm: mask only the captured token span.
        const gStart = g1[0];
        const gEnd = g1[1];
        const gtext = text.slice(gStart, gEnd);
        const qm = matchAt0(RE_GQ, gtext);
        if (
          qm !== null &&
          gtext.length > mEnd0(qm) &&
          gtext.endsWith(qm.groups[0]!)
        ) {
          candidates.push({
            start: gStart + mEnd0(qm),
            end: gEnd - 1,
            replacement: t,
            category: entry.category,
            fp,
          });
          continue;
        }
        let tag2 = t;
        if (fileHint !== undefined && isPySourceFile(fileHint)) tag2 = `"${t}"`;
        candidates.push({ start: gStart, end: gEnd, replacement: tag2, category: entry.category, fp });
        continue;
      }
      // whole-match env arm — the big rewrite block
      let eq: number | null = null;
      let sepEnd: number | null = null;
      const sepM = searchFrom(RX.sep, whole);
      if (sepM !== null) {
        eq = mStart0(sepM);
        sepEnd = mEnd0(sepM);
      }
      if (eq === 0 && '?&;#:'.includes(whole[0]!)) {
        // URL/npmrc arm — retry after the leading separator char
        const sepM2 = searchFrom(RX.sep, whole.slice(1));
        if (sepM2 !== null) {
          eq = mStart0(sepM2) + 1;
          sepEnd = mEnd0(sepM2) + 1;
        } else {
          eq = null;
          sepEnd = null;
        }
      }
      if (eq === null || sepEnd === null) {
        const commaM = searchFrom(RE_COMMA_SEP, whole);
        let replacement: string;
        if (commaM !== null) {
          const cEnd = mEnd0(commaM);
          replacement = whole.slice(0, cEnd) + '"' + t + '"';
        } else {
          const envM = matchAt0(RE_ENV_PREFIX, whole);
          replacement = envM !== null ? envM[0] + t : t;
        }
        candidates.push({ start: mStart, end: mEnd, replacement, category: entry.category, fp });
        continue;
      }
      const rhs = whole.slice(sepEnd);
      // annotated-assignment rewrite: name: T = "lit"
      const eqIdx = rhs.indexOf('=');
      let replacement: string | null = null;
      if (eqIdx >= 0) {
        const annHead = rhs.slice(0, eqIdx);
        const annTail = rhs.slice(eqIdx + 1);
        if (fullmatch(RX.rewriteType, pyStrip(annHead)) !== null) {
          const hashPos = annTail.indexOf(' #');
          const lit = hashPos >= 0 ? annTail.slice(0, hashPos) : annTail;
          if (literalStringValue(lit)) {
            const lead = pyLstripCount(annTail);
            const tok = pyStrip(lit);
            const mtM = fullmatch(RE_MT, tok);
            const inner = mtM !== null && mtM.groups[0] !== undefined ? mtM.groups[0]! : tok;
            const pm = matchAt0(RE_PM, inner);
            let body: string;
            if (pm !== null) {
              body = `${pm.groups[0] ?? ''}${pm.groups[1]}${t}${pm.groups[1]}`;
            } else {
              const q = tok.includes('"') ? "'" : '"';
              body = `${q}${t}${q}`;
            }
            if (mtM !== null) body = `(${body},)`;
            replacement = whole.slice(0, sepEnd) + annHead + '=' + annTail.slice(0, lead) + body;
          }
        }
      }
      if (replacement === null) {
        const qm = matchAt0(RE_QM, rhs);
        if (qm !== null) {
          replacement = whole.slice(0, sepEnd) + qm[0] + t + qm.groups[1]!;
        } else if (pyMode === true || (pyMode === null && whole[eq] === ':')) {
          replacement = `${whole.slice(0, sepEnd)} "${t}"`;
        } else {
          const lead = whole[eq] === ':' ? pyLstripCount(rhs) : 0;
          replacement = whole.slice(0, sepEnd) + rhs.slice(0, lead) + t;
        }
      }
      candidates.push({ start: mStart, end: mEnd, replacement, category: entry.category, fp });
      continue;
    }

    // non-env categories
    const span = g1 !== null ? g1 : ([mStart0(m), mEnd0(m)] as [number, number]);
    candidates.push({ start: span[0], end: span[1], replacement: t, category: entry.category, fp });
  }

  candidates.sort((a, b) => {
    if (a.start !== b.start) return a.start - b.start;
    return b.end - b.start - (a.end - a.start);
  });
  const accepted: Candidate[] = [];
  let lastEnd = -1;
  for (const c of candidates) {
    if (c.start >= lastEnd) {
      accepted.push(c);
      lastEnd = c.end;
    }
  }
  let out = text;
  const edits: Edit[] = [];
  for (let i = accepted.length - 1; i >= 0; i--) {
    const c = accepted[i]!;
    out = out.slice(0, c.start) + c.replacement + out.slice(c.end);
    edits.unshift({ category: c.category, line: lineOf(text, c.start), fingerprint: c.fp });
  }
  return { output: out, edits };
}

// ---------------------------------------------------------------------------
// pattern surface
// ---------------------------------------------------------------------------

let surfaceCache: Set<string> | null = null;
export function patternSurface(): Set<string> {
  if (surfaceCache === null) {
    surfaceCache = new Set(COMPILED.map((e) => `${e.category}:${e.name}`));
  }
  return surfaceCache;
}

export { SECRET_CATEGORIES };
