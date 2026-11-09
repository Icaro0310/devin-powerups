// Parity runner for tools/check_redact_parity.py — drives the TS port over
// corpus cases in one node process.
//   node redact_parity_runner.mjs            stdin: JSON array of
//                                            {input, file?} cases,
//                                            stdout: JSON array of
//                                            {redact_text: {output, edits}, scan_text: [...]}
//   node redact_parity_runner.mjs --surface  stdout: JSON array of "category:pattern_name"
import { redactText, scanText, patternSurface } from '../src/redact.ts';

if (process.argv.includes('--surface')) {
  process.stdout.write(JSON.stringify([...patternSurface()]) + '\n');
} else {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  const cases = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  const out = cases.map(({ input, file }) => ({
    redact_text: redactText(input),
    // `file` is the corpus schema-v2 blob hint: it feeds scanText's
    // finding label today and the file-gated / python-source hints once
    // the devin-redact 0.2.6 port lands (redactText gains its file
    // param there — PR2).
    scan_text: scanText(input, file ?? '<corpus>', 'corpus'),
  }));
  process.stdout.write(JSON.stringify(out) + '\n');
}
