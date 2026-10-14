#!/usr/bin/env python3
"""Generate the golden parity corpus for the devin-redact TS port.

Each line of the emitted JSONL is one case:
    {"name": ..., "input": ..., "redact_text": {"output": ..., "edits": [...]},
     "scan_text": [...]}

The TS port must reproduce every field byte-identically
(tools/check_redact_parity.py runs the same corpus through both engines —
bidirectional: any pattern/category present on only one side is drift).

Usage:
    PYTHONPATH=<devin-state>/packages/redact/src python3 tools/redact_corpus.py \
        > packages/agent-sessions/test/redact-corpus.jsonl
"""

import json
import sys

from devin_redact.engine import redact_text, scan_text  # noqa: E402

# fmt: off
CASES = [
    # --- every secret category -----------------------------------------
    ("openai_key",         "token sk-proj-Ab12Cd34Ef56Gh78Ij90Kl12 here"),
    ("openai_plain",       "sk-A1b2C3d4E5f6G7h8I9j0K1l2"),
    ("stripe_live",        "pay with sk_live_4eC39HqLyjWDarjtT1zdp7dc"),
    ("stripe_restricted",  "rk_live_4eC39HqLyjWDarjtT1zdp7dc ok"),
    ("aws_access",         "aws key AKIAIOSFODNN7EXAMPLE in text"),
    ("google_api",         "key AIzaSyD4iE2x8VvY3bK9mN0pQ1rS2tU3vW4xY5zA ok"),
    ("slack_token",        "xoxb-1234567890-abcdefghijkl leak"),
    ("bearer_header",      "Authorization: Bearer abcdef0123456789ABCDEFG"),
    ("bearer_lower",       "bearer zz-99_token.value+/=AAAA"),
    ("jwt",                "jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U end"),
    ("github_classic",     "ghp_A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6 live"),
    ("github_fine",        "github_pat_11ABCDEFG0hijklmnopqrstuvwxyz_0123456789abcdefghijklmnopqrstuvwxyz ok"),
    ("pem_block",          "cert -----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBg\n-----END PRIVATE KEY----- end"),
    ("env_plain",          "API_KEY=hunter2secret\nnext line"),
    ("env_export",         "export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG"),
    ("env_quoted",         "DB_PASSWORD=\"sup3rs3cret\" trailing"),
    ("pairing_code",       "your pairing code: AB12-CD34-EF56 ok"),
    ("pairing_word",       "the pair-code = W9X8-Y7Z6 here"),
    # --- PII ------------------------------------------------------------
    ("email",              "contact dev@example.com for info"),
    ("windows_path",       "see C:\\Users\\jdoe\\secrets.txt ok"),
    ("posix_home",         "log at /home/ikaros/.config/key.toml;"),
    ("macos_users",        "file /Users/jdoe/Library/key.pem end"),
    # --- env_assignment code-literal guard (ast.literal_eval path) -----
    ("env_code_frozenset", "_STRUCTURAL_KEYS = frozenset({\"type\", \"kind\"})"),
    ("env_code_regex",     "MY_TOKEN = re.compile(r\"x+\")"),
    ("env_code_list",      "MY_SECRET_PATTERNS = [\"a\", \"b\"]"),
    ("env_code_call",      "MY_API_TOKEN = get_secret()"),
    ("env_literal_paren",  "DB_PASSWORD = (\"hunter2secret\")"),
    ("env_literal_tuple",  "MY_API_KEY = (\"hunter2secret\",)"),
    ("env_literal_concat", "MY_API_KEY = \"hunter\" \"2secret\""),
    ("env_literal_raw",    "MY_API_KEY = r\"hunter2secret\""),
    ("env_literal_bytes",  "MY_API_KEY = b\"hunter2secret\""),
    ("env_literal_triple", "MY_API_KEY = \"\"\"hunter2secret\"\"\""),
    ("env_name_call",      "MY_SECRET = obj.method()"),
    ("env_name_pure_no_match", "PASSWORD = hunter2secret  # bare name, no prefix"),
    # --- overlaps / ordering -------------------------------------------
    ("overlap_bearer_jwt", "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"),
    ("overlap_two_keys",   "sk-A1b2C3d4E5f6G7h8I9j0K1l2 and sk-Z9y8X7w6V5u4T3s2R1q0P9o8"),
    ("adjacent",           "ghp_A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6,ghp_Z9y8X7w6V5u4T3s2R1q0P9o8N7m6L5k4"),
    ("already_redacted",   "token <REDACTED:0123456789abcdef> stays"),
    ("multiline_mixed",    "l1 sk-A1b2C3d4E5f6G7h8I9j0K1l2\nl2 plain\nl3 xoxb-1234567890-abcdefghijkl"),
    # --- negatives / boundaries ----------------------------------------
    ("empty",              ""),
    ("no_match",           "plain text, nothing sensitive here 12345"),
    ("short_sk",           "sk-short no"),
    ("sk_boundary",        "mask-proj-Ab12Cd34Ef56Gh78Ij90Kl12 not a key (no boundary)"),
    ("unicode_adjacent",   "café sk-A1b2C3d4E5f6G7h8I9j0K1l2 fim"),
    ("unicode_boundary",   "cafésk-A1b2C3d4E5f6G7h8I9j0K1l2 glued"),
    ("aws_in_word",        "FAKIAIOSFODNN7EXAMPLE embedded no"),
    ("bearer_short",       "Bearer abc123 too short"),
    ("email_boundary",     "x@y.co is short; real@example.org ok"),
    ("path_quoted",        '"/home/user/file.txt" quoted'),
    ("path_no_space",      "path=/var/log/x not home"),
    # --- mask preview edge cases ----------------------------------------
    ("tiny_secret",        "Bearer abcdefghijklmnop"),          # exactly 16
    ("newline_secret",     "xoxb-1234567890-abcd\nsecond line"),
]
# fmt: on


def main() -> None:
    out = sys.stdout
    for name, text in CASES:
        redacted, edits = redact_text(text)
        findings = scan_text(text, file="<corpus>", location="corpus")
        record = {
            "name": name,
            "input": text,
            "redact_text": {"output": redacted, "edits": edits},
            "scan_text": findings,
        }
        out.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
