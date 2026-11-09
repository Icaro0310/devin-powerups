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
    // corpus schema v2 (devin-powerups#271): optional blob-name hint —
    // feeds scanText's file label and redactText's file-gated /
    // python-source semantics (devin-redact 0.2.6 `file=` param).
    file?: string;
    redact_text: { output: string; edits: { category: string; line: number; fingerprint: string }[] };
    scan_text: unknown[];
  });

for (const c of cases) {
  test(`redact corpus: ${c.name}`, () => {
    assert.deepEqual(redactText(c.input, c.file), c.redact_text);
    assert.deepEqual(scanText(c.input, c.file ?? '<corpus>', 'corpus'), c.scan_text);
  });
}

test('tag-gap rescan finds KEY= after a non-key suffix', () => {
  // devin-powerups#223 review: the fragment rescan inherits the env
  // pattern's `^` anchor, so 'API_KEY=<tag>suffix OTHER_TOKEN=raw' left
  // the tail raw — the fragment starts with a non-key word. The port
  // scans env fragments de-anchored; upstream converged in
  // devin-state#82 (shipped in devin-redact 0.2.5), so the case now
  // also lives in the parity corpus as env_tag_suffix_head.
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
  assert.equal(findings[0]!.fingerprint, fp);
  assert.equal(findings[0]!.preview, ' OTH...');
});

test('pattern surface matches the Python PATTERNS table', () => {
  assert.deepEqual([...patternSurface()].sort(), [
    'absolute_path:posix_home_path',
    'absolute_path:windows_user_path',
    'api_key:age_secret_key',
    'api_key:aws_access_key_id',
    'api_key:digitalocean_pat',
    'api_key:gitlab_pat',
    'api_key:gitlab_scoped_token',
    'api_key:google_api_key',
    'api_key:google_oauth_token',
    'api_key:huggingface_token',
    'api_key:npm_token',
    'api_key:openai_key',
    'api_key:pypi_token',
    'api_key:sendgrid_key',
    'api_key:shopify_token',
    'api_key:slack_app_token',
    'api_key:slack_token',
    'api_key:square_token',
    'api_key:stripe_live_key',
    'api_key:stripe_restricted_key',
    'api_key:stripe_webhook_secret',
    'bearer_token:basic_auth_header',
    'bearer_token:bearer_header',
    'bearer_token:jwt',
    'connection_uri:uri_userinfo',
    'devin_pairing_code:devin_pairing_code',
    'email:email',
    'env_assignment:env_assignment',
    'env_assignment:env_assignment[100]',
    'env_assignment:env_assignment[101]',
    'env_assignment:env_assignment[102]',
    'env_assignment:env_assignment[103]',
    'env_assignment:env_assignment[104]',
    'env_assignment:env_assignment[105]',
    'env_assignment:env_assignment[106]',
    'env_assignment:env_assignment[107]',
    'env_assignment:env_assignment[108]',
    'env_assignment:env_assignment[109]',
    'env_assignment:env_assignment[10]',
    'env_assignment:env_assignment[110]',
    'env_assignment:env_assignment[111]',
    'env_assignment:env_assignment[112]',
    'env_assignment:env_assignment[113]',
    'env_assignment:env_assignment[114]',
    'env_assignment:env_assignment[115]',
    'env_assignment:env_assignment[116]',
    'env_assignment:env_assignment[117]',
    'env_assignment:env_assignment[118]',
    'env_assignment:env_assignment[119]',
    'env_assignment:env_assignment[11]',
    'env_assignment:env_assignment[120]',
    'env_assignment:env_assignment[121]',
    'env_assignment:env_assignment[122]',
    'env_assignment:env_assignment[123]',
    'env_assignment:env_assignment[124]',
    'env_assignment:env_assignment[125]',
    'env_assignment:env_assignment[126]',
    'env_assignment:env_assignment[127]',
    'env_assignment:env_assignment[128]',
    'env_assignment:env_assignment[129]',
    'env_assignment:env_assignment[12]',
    'env_assignment:env_assignment[130]',
    'env_assignment:env_assignment[131]',
    'env_assignment:env_assignment[132]',
    'env_assignment:env_assignment[133]',
    'env_assignment:env_assignment[13]',
    'env_assignment:env_assignment[14]',
    'env_assignment:env_assignment[15]',
    'env_assignment:env_assignment[16]',
    'env_assignment:env_assignment[17]',
    'env_assignment:env_assignment[18]',
    'env_assignment:env_assignment[19]',
    'env_assignment:env_assignment[20]',
    'env_assignment:env_assignment[21]',
    'env_assignment:env_assignment[22]',
    'env_assignment:env_assignment[23]',
    'env_assignment:env_assignment[24]',
    'env_assignment:env_assignment[25]',
    'env_assignment:env_assignment[26]',
    'env_assignment:env_assignment[27]',
    'env_assignment:env_assignment[28]',
    'env_assignment:env_assignment[29]',
    'env_assignment:env_assignment[2]',
    'env_assignment:env_assignment[30]',
    'env_assignment:env_assignment[31]',
    'env_assignment:env_assignment[32]',
    'env_assignment:env_assignment[33]',
    'env_assignment:env_assignment[34]',
    'env_assignment:env_assignment[35]',
    'env_assignment:env_assignment[36]',
    'env_assignment:env_assignment[37]',
    'env_assignment:env_assignment[38]',
    'env_assignment:env_assignment[39]',
    'env_assignment:env_assignment[3]',
    'env_assignment:env_assignment[40]',
    'env_assignment:env_assignment[41]',
    'env_assignment:env_assignment[42]',
    'env_assignment:env_assignment[43]',
    'env_assignment:env_assignment[44]',
    'env_assignment:env_assignment[45]',
    'env_assignment:env_assignment[46]',
    'env_assignment:env_assignment[47]',
    'env_assignment:env_assignment[48]',
    'env_assignment:env_assignment[49]',
    'env_assignment:env_assignment[4]',
    'env_assignment:env_assignment[50]',
    'env_assignment:env_assignment[51]',
    'env_assignment:env_assignment[52]',
    'env_assignment:env_assignment[53]',
    'env_assignment:env_assignment[54]',
    'env_assignment:env_assignment[55]',
    'env_assignment:env_assignment[56]',
    'env_assignment:env_assignment[57]',
    'env_assignment:env_assignment[58]',
    'env_assignment:env_assignment[59]',
    'env_assignment:env_assignment[5]',
    'env_assignment:env_assignment[60]',
    'env_assignment:env_assignment[61]',
    'env_assignment:env_assignment[62]',
    'env_assignment:env_assignment[63]',
    'env_assignment:env_assignment[64]',
    'env_assignment:env_assignment[65]',
    'env_assignment:env_assignment[66]',
    'env_assignment:env_assignment[67]',
    'env_assignment:env_assignment[68]',
    'env_assignment:env_assignment[69]',
    'env_assignment:env_assignment[6]',
    'env_assignment:env_assignment[70]',
    'env_assignment:env_assignment[71]',
    'env_assignment:env_assignment[72]',
    'env_assignment:env_assignment[73]',
    'env_assignment:env_assignment[74]',
    'env_assignment:env_assignment[75]',
    'env_assignment:env_assignment[76]',
    'env_assignment:env_assignment[77]',
    'env_assignment:env_assignment[78]',
    'env_assignment:env_assignment[79]',
    'env_assignment:env_assignment[7]',
    'env_assignment:env_assignment[80]',
    'env_assignment:env_assignment[81]',
    'env_assignment:env_assignment[82]',
    'env_assignment:env_assignment[83]',
    'env_assignment:env_assignment[84]',
    'env_assignment:env_assignment[85]',
    'env_assignment:env_assignment[86]',
    'env_assignment:env_assignment[87]',
    'env_assignment:env_assignment[88]',
    'env_assignment:env_assignment[89]',
    'env_assignment:env_assignment[8]',
    'env_assignment:env_assignment[90]',
    'env_assignment:env_assignment[91]',
    'env_assignment:env_assignment[92]',
    'env_assignment:env_assignment[93]',
    'env_assignment:env_assignment[94]',
    'env_assignment:env_assignment[95]',
    'env_assignment:env_assignment[96]',
    'env_assignment:env_assignment[97]',
    'env_assignment:env_assignment[98]',
    'env_assignment:env_assignment[99]',
    'env_assignment:env_assignment[9]',
    'env_assignment:env_assignment_json',
    'github_token:github_fine_grained_pat',
    'github_token:github_token',
    'private_key:pem_private_key',
    'private_key:pem_private_key_unterminated',
    'webhook_url:discord_webhook_url',
    'webhook_url:office365_webhook_url',
    'webhook_url:slack_webhook_url'
  ]);
});
