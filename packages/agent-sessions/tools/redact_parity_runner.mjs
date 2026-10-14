// Parity runner for tools/check_redact_parity.py — drives the TS port over
// corpus inputs in one node process.
//   node redact_parity_runner.mjs            stdin: JSON array of inputs,
//                                            stdout: JSON array of
//                                            {redact_text: {output, edits}, scan_text: [...]}
//   node redact_parity_runner.mjs --surface  stdout: JSON array of "category:pattern_name"
import { redactText, scanText, patternSurface } from '../src/redact.ts';

if (process.argv.includes('--surface')) {
  process.stdout.write(JSON.stringify([...patternSurface()]) + '\n');
} else {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  const inputs = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  const out = inputs.map((text) => ({
    redact_text: redactText(text),
    scan_text: scanText(text, '<corpus>', 'corpus'),
  }));
  process.stdout.write(JSON.stringify(out) + '\n');
}
