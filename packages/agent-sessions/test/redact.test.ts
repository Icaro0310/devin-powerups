import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { redactText, scanText, patternSurface } from '../src/redact.ts';

const CORPUS = fileURLToPath(new URL('./redact-corpus.jsonl', import.meta.url));
const cases = readFileSync(CORPUS, 'utf8')
  .split('\n')
  .filter((l) => l.trim())
  .map((l) => JSON.parse(l) as {
    name: string;
    input: string;
    redact_text: { output: string; edits: { category: string; line: number; fingerprint: string }[] };
    scan_text: unknown[];
  });

for (const c of cases) {
  test(`redact corpus: ${c.name}`, () => {
    assert.deepEqual(redactText(c.input), c.redact_text);
    assert.deepEqual(scanText(c.input, '<corpus>', 'corpus'), c.scan_text);
  });
}

test('tag-gap rescan finds KEY= after a non-key suffix', () => {
  // devin-powerups#223 review: the fragment rescan inherits the env
  // pattern's `^` anchor, so 'API_KEY=<tag>suffix OTHER_TOKEN=raw' left
  // the tail raw — the fragment starts with a non-key word. The port
  // scans env fragments de-anchored; upstream Python still anchors, so
  // this case stays out of the parity corpus on purpose.
  const input = 'API_KEY=<REDACTED:abc123>suffix OTHER_TOKEN=rawsecret99';
  const fp = createHash('sha256')
    .update(' OTHER_TOKEN=rawsecret99', 'utf8')
    .digest('hex')
    .slice(0, 16);
  assert.deepEqual(redactText(input), {
    output: `API_KEY=<REDACTED:abc123>suffix OTHER_TOKEN=<REDACTED:${fp}>`,
    edits: [{ category: 'env_assignment', line: 1, fingerprint: fp }],
  });
  const findings = scanText(input, '<corpus>', 'corpus');
  assert.equal(findings.length, 1);
  assert.equal(findings[0].fingerprint, fp);
  assert.equal(findings[0].preview, ' OTH...et99');
});

test('pattern surface matches the Python PATTERNS table', () => {
  assert.deepEqual([...patternSurface()].sort(), [
    'absolute_path:posix_home_path',
    'absolute_path:windows_user_path',
    'api_key:aws_access_key_id',
    'api_key:google_api_key',
    'api_key:openai_key',
    'api_key:slack_token',
    'api_key:stripe_live_key',
    'api_key:stripe_restricted_key',
    'bearer_token:bearer_header',
    'bearer_token:jwt',
    'devin_pairing_code:devin_pairing_code',
    'email:email',
    'env_assignment:env_assignment',
    'github_token:github_fine_grained_pat',
    'github_token:github_token',
    'private_key:pem_private_key',
  ]);
});
