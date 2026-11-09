#!/usr/bin/env python3
"""Generate the golden parity corpus for the devin-redact TS port.

NOTE: this is a parity spec, not a security spec — cases codify the
current Python behaviour. A case passing means "same as Python", not
"safe". Regenerate this corpus in the same change whenever the Python
engine's semantics move — a corpus generated from buggy code freezes
the bug as expected output (env_tag_tail encoded devin-state#66).

Each line of the emitted JSONL is one case:
    {"name": ..., "input": ..., "file": <optional str>,
     "redact_text": {"output": ..., "edits": [...]},
     "scan_text": [...]}

`file` is the optional blob-name hint (corpus schema v2,
devin-powerups#271): absent -> scan_text sees file="<corpus>" and
redact_text sees file=None, exactly the pre-v2 asymmetry. Present ->
the same value feeds both calls (scan label + the file-gated /
python-source hints devin-redact >= 0.2.6 honours).

The TS port must reproduce every field byte-identically
(tools/check_redact_parity.py runs the same corpus through both engines —
bidirectional: any pattern/category present on only one side is drift).

Usage:
    PYTHONPATH=<devin-state>/packages/redact/src python3 tools/redact_corpus.py \
        > packages/agent-sessions/test/redact-corpus.jsonl
"""

import inspect
import json
import sys

from devin_redact.engine import redact_text, scan_text  # noqa: E402

# devin-redact 0.2.6 added `file=` to redact_text; the pinned 0.2.5
# signature is redact_text(text) only. Forward the case's file hint
# only when the resolved engine accepts it, so the same corpus drives
# both pins.
_REDACT_HAS_FILE = "file" in inspect.signature(redact_text).parameters

# fmt: off
# Entries are (name, input) or (name, input, file) — `file` is the
# optional blob-name hint described in the module docstring.
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
    # Trailing `#` comments are invisible to ast.literal_eval (the
    # tokenizer strips them), so a parenthesized literal with a comment
    # tail is still a hardcoded value — Devin Review finding on #276.
    ("env_literal_paren_comment",      'API_KEY = ("hunter2secret99") # nota'),
    ("env_literal_paren_comment_nospace", 'API_KEY = ("hunter2secret99")#nota'),
    ("env_literal_quoted_comment",     'API_KEY = "hunter2secret99" # nota'),
    ("env_name_call",      "MY_SECRET = obj.method()"),
    ("env_name_pure_no_match", "PASSWORD = hunter2secret  # bare name, no prefix"),
    # --- overlaps / ordering -------------------------------------------
    ("overlap_bearer_jwt", "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"),
    ("overlap_two_keys",   "sk-A1b2C3d4E5f6G7h8I9j0K1l2 and sk-Z9y8X7w6V5u4T3s2R1q0P9o8"),
    ("adjacent",           "ghp_A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6,ghp_Z9y8X7w6V5u4T3s2R1q0P9o8N7m6L5k4"),
    ("already_redacted",   "token <REDACTED:0123456789abcdef> stays"),
    # Tag-gap rescan (devin-state#66, fixed in devin-state#79): a match
    # containing a closed <REDACTED:…> tag re-scans each tag-free fragment —
    # only the tag's own span is off-limits.
    ("env_tag_tail",       "API_KEY=<REDACTED:abc123> OTHER_TOKEN=rawsecret99"),
    # Non-key fragment head (devin-powerups#223, upstream devin-state#82):
    # a fragment starting with a non-key word must still find each KEY=
    # later in the fragment — the rescan uses a de-anchored variant.
    ("env_tag_suffix_head", "API_KEY=<REDACTED:abc123>suffix OTHER_TOKEN=rawsecret99"),
    ("env_tag_nested",     "OUTER_KEY=<REDACTED:x1> INNER_KEY=<REDACTED:y2> DEEP_SECRET=z9"),
    ("env_tag_mid_value",  "FIRST_KEY=firstval1<REDACTED:mid99> SECOND_KEY=secondval2"),
    ("env_tag_code_head",  "FIRST_KEY = frozenset({'x'}) <REDACTED:t0> REAL_TOKEN=tv9x"),
    ("env_tag_between",    "A_KEY=<REDACTED:one> B_KEY=<REDACTED:two> C_TOKEN=tailsecret9"),
    # Enclosure guard: fragments inside a container/quoted literal are
    # dropped — re-matching there would eat the closing delimiters.
    ("env_tag_container",  'TOKEN_KEY = ["<REDACTED:abc> API_KEY=innocent"]\n'),
    ("env_tag_quoted",     "MY_API_KEY = 'abc<REDACTED:x9>def'\n"),
    ("env_tag_esc_quote",  'TOKEN_KEY = "abc\\"<REDACTED:x1>tail"\n'),
    # Comment trim: an unquoted `#` ends the rescan fragment — the value
    # before the marker still redacts, comment content survives.
    ("env_tag_in_comment", 'TOKEN_KEY = ("abc") # <REDACTED:x1>\n'),
    ("env_tag_before_comment", "TOKEN_KEY=rawsecret99 # <REDACTED:x1>\n"),
    # The code-assignment guard applies to fragment tails too.
    ("env_tag_code_rhs",   "FIRST_KEY=<REDACTED:a> SECOND_SECRET = frozenset({'x'})\n"),
    # An unclosed `<REDACTED:` is malformed, not a real tag — whole-match
    # skip still applies, the tail stays raw.
    ("env_tag_malformed",  "API_KEY=<REDACTED:abc OTHER_TOKEN=rawsecret99"),
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
    # --- devin-redact 0.2.6 adversarial surface -------------------------
    # Cases distilled from upstream tests/test_evasion.py (devin-state
    # audit corpus): every token family, env/webhook shapes, file-gated
    # and python-source semantics. `file` carries the blob-name hint the
    # upstream test used (schema v2).
    ("tok_gitlab_pat", 'glpat-xxxxxxxxxxxxxxxxxxxx'),
    ("tok_gitlab_deploy", 'gldt-xxxxxxxxxxxxxxxxxxxx'),
    ("tok_gitlab_runner", 'glrt-xxxxxxxxxxxxxxxxxxxx'),
    ("tok_slack_app", 'xapp-1-A0BCDEFGH-abcdefghijkl'),
    ("tok_stripe_whsec", 'whsec_aaaaaaaaaaaaaaaaaaaaaaaa'),
    ("tok_google_oauth", 'ya29.a0Afbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'),
    ("tok_npm", 'npm_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'),
    ("tok_pypi", 'pypi-AgEIcHlwaS5vcmcaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'),
    ("tok_digitalocean", 'dop_v1_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'),
    ("tok_sendgrid", 'SG.aaaaaaaaaaaaaaaaaaaaaa.bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'),
    ("tok_square_atp", 'sq0atp-aaaaaaaaaaaaaaaaaaaaaa'),
    ("tok_square_csp", 'sq0csp-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'),
    ("tok_shopify_at", 'shpat_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'),
    ("tok_shopify_ca", 'shpca_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'),
    ("tok_huggingface", 'hf_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'),
    ("tok_age_key", 'AGE-SECRET-KEY-1QQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQ'),
    ("envc_yaml_colon", 'api_key: hunter2fake\n'),
    ("envc_json_pair", '"api_key": "hunter2fake"\n'),
    ("envc_dict_pair", "cfg = {'secret_key': 'hunter2fake'}\n"),
    ("envc_escaped_json", '{\\"token\\": \\"hunter2fake\\"}\n'),
    ("envc_camel_key", 'apiKey = "hunter2fake"\n'),
    ("envc_camel_token", 'authToken = hunter2fake\n'),
    ("envc_lower_key", 'api_key = "hunter2fake"\n'),
    ("envc_lower_password", 'db_password = hunter2fake\n'),
    ("envc_lower_apikey", 'apikey = hunter2fake\n'),
    ("envc_bare_key", 'key = "hunter2fake"\n'),
    ("envc_inline_json", 'note {"token": "hunter2fake"} tail\n'),
    ("envc_js_literal", "cfg = {apiKey: 'hunter2fake'}\n"),
    ("wh_slack", 'https://hooks.slack.com/services/T00000000/B00000000/XXXXX'),
    ("wh_discord", 'https://discord.com/api/webhooks/1234567890/abcDEF_-0123'),
    ("wh_discordapp", 'https://canary.discordapp.com/api/webhooks/123/abcDEF_-0123'),
    ("wh_office365", 'https://outlook.office.com/webhookb2/aaaa-bbbb@cccc/dddd'),
    ("ev_const_bearertokenname_so_6363", 'const BearerTokenName = somethingLongEnough16', 'x'),
    ("ev_authorization_basic_auth_aa45", 'Authorization: basic authentication is required here', 'x'),
    ("ev_api_key_hunter2fake_011f", '"api_key": "hunter2fake"\n'),
    ("ev_hotkey_ctrl_x_8c52", 'hotkey = "ctrl-x"\n', 'x'),
    ("ev_ssh_deploy_host_example__b018", 'ssh://deploy@host.example/repo', 'x'),
    ("ev_api_key_hunter2_enable_3586", '{"api_key":"hunter2","enabled":true}'),
    ("ev_api_key_hunter2_enabled_ac97", '"api_key":"hunter2","enabled":true\n'),
    ("ev_cfg_secret_key_hunter_ff0a", "cfg = {'secret_key': 'hunter2fake'}\n"),
    ("ev_token_abc_defsecret_4169", '{"token": "abc\\"defsecret"}'),
    ("ev_token_it_s_a_secret_d62b", '{"token": "it\'s a secret"}'),
    ("ev_api_key_hello_fetch_f8a9", '"api_key": "hello=fetch()"\n', 'x'),
    ("ev_api_key_hello_fetch_dd4e", '"api_key": "hello=fetch()"\n'),
    ("ev_api_key_list_abc_def_a0c8", 'api_key: list[abc.def]\n', 'x'),
    ("ev_check_api_key_hunter2_8fa9", 'check(api_key=="hunter2")\n', 'm.py'),
    ("ev_api_key_n_ndarray_2192", 'api_key: n.ndarray\n', 'config.yaml'),
    ("ev_key_hunter2val_0869", 'KEY=hunter2val\n', '.env'),
    ("ev_api_key_np_ndarray_9b9e", 'api_key: np.ndarray\n', 'm.py'),
    ("ev_import_numpy_as_np_api_k_611d", 'import numpy as np\napi_key: np.ndarray\n', 'm.py'),
    ("ev_api_key_n_ndarray_5478", 'api_key: n.ndarray\n', 'x'),
    ("ev_password_n_proxy_0e1b", 'password: n.proxy\n', 'creds.env'),
    ("ev_api_key_hunter2_764d", 'api_key: hunter2\n'),
    ("ev_api_key_hunter2_379d", 'API_KEY=hunter2\n', 'creds.env'),
    ("ev_api_key_hunter2_ed3c", 'api_key hunter2', 'notes.txt'),
    ("ev_password_must_be_rotated_d506", 'PASSWORD must be rotated quarterly', 'notes.md'),
    ("ev_mysql_u_root_p3306_db_f5f5", 'mysql -u root -P3306 db', 'x.txt'),
    ("ev_mysql_u_root_p_db_bbba", 'mysql -u root -p db', 'x.txt'),
    ("ev_cookie_api_key_hunter2_o_a53c", 'Cookie: api_key=hunter2; other=1', 'hdrs.txt'),
    ("ev_if_api_key_x_or_token_5_a583", 'if api_key=="x" or token>=5: pass', 'a.py'),
    ("ev_smbclient_s_u_admin_hunt_888f", 'smbclient //s -U admin%hunter2', 'c.txt'),
    ("ev_openssl_passwd_stdin_bb49", 'openssl passwd -stdin', 'c.txt'),
    ("ev_config_set_sec_api_key_68c6", 'config.set("sec", "api_key", "hunter2")', 'a.py'),
    ("ev_x_get_key_default_val_pr_1e0a", 'x.get("key", default_val)\nprint("hello")', 'a.py'),
    ("ev_set_e_u_o_pipefail_7d49", 'set -e -u -o pipefail', 'rc.txt'),
    ("ev_key_api_secret_key_data__b337", '<key>api_secret</key><data>aHVudGVyMg==</data>', 'p.plist'),
    ("ev_authorization_basic_hunt_7c1b", 'authorization: basic hunter2', 'c.txt'),
    ("ev_env_api_key_hunter2_4582", 'env: {API_KEY: hunter2}', 'd.yml'),
    ("ev_secure_a7v1k2x9zqbn4rt8y_aa3e", 'secure: A7V1k2x9zQbN4rT8yU3iO6pL0sD5fG7hJ2kM', 'd.yml'),
    ("ev_secure_true_427d", 'secure: true', 'd.yml'),
    ("ev_sshpass_hunter2_sshpass__6365", 'SSHPASS=hunter2 sshpass -e ssh h', 's.sh'),
    ("ev_a_b_c_d_e_a3cf", 'a:b:c:d:e', '.pgpass'),
    ("ev_setx_api_key_hunter2_fe9e", 'setx API_KEY hunter2', 's.bat'),
    ("ev_setx_m_api_key_hunter2_78e5", 'setx /M API_KEY hunter2', 's.bat'),
    ("ev_security_find_generic_pa_6e70", 'security find-generic-password -s svc -w | pbcopy', 's.sh'),
    ("ev_rclone_config_create_r_s_fded", 'rclone config create r s3 secret_access_key hunter2 token abc123 region us secret_key b3trayal', 's.sh'),
    ("ev_sqlplus_nolog_ece1", 'sqlplus /nolog', 's.sh'),
    ("ev_radtest_admin_hunter2_lo_4460", 'radtest admin hunter2 localhost 0 sharedsecret', 's.sh'),
    ("ev_rclone_config_create_r_s_3bd7", 'rclone config create r s3 token abc123 region us secret_access_key hunter2', 's.sh'),
    ("ev_rclone_config_create_r_s_ee52", 'rclone config create r s3 secret_access_key hunter2 token "abc 123"', 's.sh'),
    ("ev_gh_secret_set_api_key_en_5776", 'gh secret set API_KEY --env "prod;dev" --body hunter2', 's.sh'),
    ("ev_gh_secret_set_api_key_en_f871", 'gh secret set API_KEY --env "prod|dev" --body hunter2', 's.sh'),
    ("ev_kadmin_w_hunter2_q_addpr_6417", 'kadmin -w hunter2 -q "addprinc -pw secret123 admin"', 's.sh'),
    ("ev_radtest_user_name_hun_te_11fa", 'radtest "user name" "hun ter2" host 0 "shared secret"', 's.sh'),
    ("ev_password_hun_ter2_cbf4", 'password "hun\\"ter2"', '.msmtprc'),
    ("ev_pulumi_config_set_secret_d2fd", 'pulumi config set --secret service:password hunter2', 's.sh'),
    ("ev_mc_admin_user_add_mymini_6cd8", 'mc admin user add myminio admin "hun ter2"', 's.sh'),
    ("ev_redis_cli_set_password_h_8b39", 'redis-cli set password hunter2', 's.sh'),
    ("ev_gh_secret_set_api_key_bo_7a09", 'gh secret set API_KEY --body hunter2 | wc', 's.sh'),
    ("ev_security_add_generic_pas_b733", 'security add-generic-password -s x -w hunter2; rm -rf ~', 's.sh'),
    ("ev_conjur_variable_set_i_x__be6d", 'conjur variable set -i x -v hunter2; rm -rf ~', 's.sh'),
    ("ev_rclone_config_create_r_s_243c", 'rclone config create r s3 secret_access_key hunter2 --interactive', 's.sh'),
    ("ev_redis_cli_get_password_f89e", 'redis-cli get password', 's.sh'),
    ("ev_ldapadd_w_d_cn_admin_w_h_2f55", 'ldapadd -w -D cn=admin -w hunter2', 's.sh'),
    ("ev_http_get_x_auth_type_bas_aac2", 'http GET x --auth-type=basic --auth admin:hunter2', 's.sh'),
    ("ev_expect_password_send_c53f", 'expect "Password:" ; send -- "hunter2\\r"', 's.exp'),
    ("ev_grep_pw_foo_file_txt_597e", 'grep -pw foo file.txt', 's.sh'),
    ("ev_git_grep_pw_foo_file_txt_1f39", 'git grep -Pw foo file.txt', 's.sh'),
    ("ev_kadmin_q_addprinc_pw_sec_62da", 'kadmin -q "addprinc -pw secret123 admin" -w hunter2', 's.sh'),
    ("ev_kadmin_w_hunter2_q_addpr_e6c4", 'kadmin -w hunter2 -q "addprinc -pw pass2 admin"', 's.sh'),
    ("ev_sqlplus_scott_hunter2_ec_9f1a", 'sqlplus scott/hunter2; echo hi', 's.sh'),
    ("ev_requirepass_hunter_2_fd4f", 'requirepass hunter;2', 'redis.conf'),
    ("ev_requirepass_hunter_2_not_294e", 'requirepass hunter;2 # note', 'redis.conf'),
    ("ev_olcrootpw_ssha_a_2_b03b", 'olcRootPW={SSHA}a;2', 'x.ldif'),
    ("ev_password_hunter_2_3b87", 'password hunter;2', '.msmtprc'),
    ("ev_kubectl_create_secret_ge_4438", 'kubectl create secret generic s --from-literal=k=hunter2', 's.sh'),
    ("ev_kubectl_create_secret_ge_6c2c", 'kubectl create secret generic s --from-literal=a=x --from-literal=k=hunter2', 's.sh'),
    ("ev_rabbitmqctl_add_user_adm_dd76", 'rabbitmqctl add_user admin hunter2', 's.sh'),
    ("ev_printf_api_key_s_hunter2_0c9c", 'printf "API_KEY=%s" hunter2 >> .env', 's.sh'),
    ("ev_net_use_s_x_hunter2_use_87f8", 'net use * \\\\s\\x hunter2 /user:u', 'x.bat'),
    ("ev_requirepass_hunter_secre_939e", 'requirepass hunter\\ secret', 'redis.conf'),
    ("ev_sqlplus_scott_hunter_2_d_dc47", 'sqlplus "scott/hunter;2"@db', 's.sh'),
    ("ev_olcrootpw_ssha_a_b_2_712e", 'olcRootPW={SSHA}a\\ b;2', 'x.ldif'),
    ("ev_kubectl_create_configmap_2399", 'kubectl create configmap cm --from-literal=REGION=us-east-1', 's.sh'),
    ("ev_kubectl_create_secret_s__bfbf", 'kubectl create secret s --from-literal=k="hunter2"', 's.sh'),
    ("ev_printf_api_key_s_n_hunte_30da", "printf 'API_KEY=%s\\n' hunter2", 's.sh'),
    ("ev_rabbitmqctl_add_user_fir_4f1f", 'rabbitmqctl add_user "first last" hunter2', 's.sh'),
    ("ev_get_thing_credential_hun_f9a7", 'Get-Thing -Credential hunter2', 's.ps1'),
    ("ev_snmpwalk_v3_u_admin_a_hu_1d9b", 'snmpwalk -v3 -u admin -A hunter2 -X s3cr3t host', 's.sh'),
    ("ev_snmpwalk_v3_u_u_a_sha_x_6a20", 'snmpwalk -v3 -u u -a SHA -x AES h', 's.sh'),
    ("ev_mongosh_mongodb_h_u_u_7c69", 'mongosh "mongodb://h" -u u -p hunter2', 's.sh'),
    ("ev_mosquitto_pub_h_h_u_u_p__8c45", 'mosquitto_pub -h h -u u -P hunter2 -t t -m m', 's.sh'),
    ("ev_mosquitto_pub_h_h_p_8883_fb91", 'mosquitto_pub -h h -p 8883 -t t -m m', 's.sh'),
    ("ev_openssl_enc_aes_256_cbc__812c", 'openssl enc -aes-256-cbc -k hunter2 -in f', 's.sh'),
    ("ev_influx_write_t_hunter2_b_0f55", 'influx write -t hunter2 -b b -o o', 's.sh'),
    ("ev_etcdctl_user_add_u_hunte_0228", 'etcdctl user add u:hunter2', 's.sh'),
    ("ev_arangosh_server_password_9bf0", 'arangosh --server.password hunter2', 's.sh'),
    ("ev_conan_remote_login_r_u_p_88cf", 'conan remote login r u -p hunter2', 's.sh'),
    ("ev_conan_install_pr_default_49d4", 'conan install . -pr default', 's.sh'),
    ("ev_vault_write_secret_x_a_1_b9ba", 'vault write secret/x a=1 k=hunter2 z=9', 's.sh'),
    ("ev_bao_write_secret_x_k_hun_a615", 'bao write secret/x k=hunter2', 's.sh'),
    ("ev_vault_write_transit_keys_5a44", 'vault write transit/keys/k', 's.sh'),
    ("ev_kubectl_create_secret_ge_e0e2", 'kubectl create secret generic s; kubectl create configmap cm --from-literal=REGION=us-east-1', 's.sh'),
    ("ev_kubectl_create_secret_s__3534", 'kubectl create secret s --from-literal=a=x --type=Opaque --from-literal=k=hunter2', 's.sh'),
    ("ev_kubectl_context_prod_n_n_7afd", 'kubectl --context=prod -n ns create secret s --from-literal=k=hunter2', 's.sh'),
    ("ev_printf_api_key_s_token_s_bad4", "printf 'API_KEY=%s TOKEN=%s' hunter2 s3cr3t", 's.sh'),
    ("ev_printf_x_s_api_key_s_aa_45ec", "printf 'x %s API_KEY=%s' aa hunter2", 's.sh'),
    ("ev_rabbitmqctl_add_user_fi__4e5b", 'rabbitmqctl add_user "fi\\"rst last" hunter2', 's.sh'),
    ("ev_openssl_enc_k_hunter2_iv_8f46", 'openssl enc -K hunter2 -iv s3cr3t -in f -out g', 's.sh'),
    ("ev_openssl_req_new_key_priv_a112", 'openssl req -new -key private.pem', 's.sh'),
    ("ev_etcdctl_user_add_alice_h_89d1", 'etcdctl user add "alice:hunter2"', 's.sh'),
    ("ev_conan_install_ssh_p_22_8785", 'conan install . && ssh -p 2222 host', 's.sh'),
    ("ev_vault_write_format_json__920f", 'vault write -format=json secret/x k=hunter2', 's.sh'),
    ("ev_vault_write_secret_x_bla_0a13", 'vault write secret/x blank= k=hunter2', 's.sh'),
    ("ev_ansible_vault_encrypt_st_c6c1", 'ansible-vault encrypt_string hunter2 --name key', 's.sh'),
    ("ev_ansible_vault_encrypt_st_9ee6", 'ansible-vault encrypt_string --stdin-name keyname', 's.sh'),
    ("ev_vault_login_hunter2_7aff", 'vault login hunter2', 's.sh'),
    ("ev_bao_login_method_token_h_3405", 'bao login -method=token hunter2', 's.sh'),
    ("ev_ssh_keygen_p_p_oldhunter_0d4a", 'ssh-keygen -p -P oldhunter -N newhunter -f k', 's.sh'),
    ("ev_smbclient_h_s_hunter2_u__6ec2", 'smbclient //h/s hunter2 -U u', 's.sh'),
    ("ev_smbclient_h_s_u_u_5e97", 'smbclient //h/s -U u', 's.sh'),
    ("ev_kubectl_create_secret_s__021c", 'kubectl create secret s --from-literal=a=x --dry-run=client --from-literal=b=hunter2', 's.sh'),
    ("ev_kubectl_create_secret_s__92f6", 'kubectl create secret s --from-literal=k="hu nter"', 's.sh'),
    ("ev_printf_api_key_s_hunter2_edf7", "printf 'API_KEY=%s' hunter2 >> .env", 's.sh'),
    ("ev_printf_api_key_s_hunter2_e150", "printf 'API_KEY=%s' hunter2 2>log", 's.sh'),
    ("ev_printf_api_key_s_hunter2_58af", "printf 'API_KEY=%s' hunter2 # note", 's.sh'),
    ("ev_printf_api_key_s_token_s_0d1c", "printf 'API_KEY=%s TOKEN=%s' hunter2 s3cr3t >> .env", 's.sh'),
    ("ev_ansible_vault_encrypt_st_870d", 'ansible-vault encrypt_string --name "two words" hunter2', 's.sh'),
    ("ev_vault_login_path_a_b_hun_f32e", 'vault login -path "a b" hunter2', 's.sh'),
    ("ev_vault_login_format_json__7465", 'vault login -format=json hunter2', 's.sh'),
    ("ev_conan_remote_login_r_u_a_9d16", 'conan remote login r u "a&b" -p hunter2', 's.sh'),
    ("ev_smbclient_h_s_hunter2_4309", 'smbclient "//h/s" hunter2', 's.sh'),
    ("ev_smbclient_u_alice_h_s_hu_7500", 'smbclient -U alice //h/s hunter2', 's.sh'),
    ("ev_smbclient_n_h_s_hunter2_1422", 'smbclient -N //h/s hunter2', 's.sh'),
    ("ev_ngrok_authtoken_log_leve_16b4", 'ngrok authtoken --log-level debug hunter2', 's.sh'),
    ("ev_airflow_users_create_u_a_dabf", 'airflow users create -u alice -p hunter2 -r Admin', 's.sh'),
    ("ev_atlas_privatekey_hunter2_dd7e", 'atlas --privateKey hunter2 --publicKey u', 's.sh'),
    ("ev_confluent_api_key_store__51e1", 'confluent api-key store ABCDEF hunter2', 's.sh'),
    ("ev_emqx_ctl_admins_passwd_a_1d12", 'emqx ctl admins passwd admin hunter2', 's.sh'),
    ("ev_hardhat_vars_set_api_key_6042", 'hardhat vars set API_KEY hunter2', 's.sh'),
    ("ev_sst_secrets_set_api_key__1cb2", 'sst secrets set API_KEY hunter2', 's.sh'),
    ("ev_nomad_var_put_secret_x_k_dec1", 'nomad var put secret/x k=hunter2', 's.sh'),
    ("ev_nomad_var_put_secret_x_a_9932", 'nomad var put secret/x a=b k=hunter2', 's.sh'),
    ("ev_kubectl_create_secret_s__a40d", 'kubectl create secret s --from-literal=k=x --note="--from-literal=z=bar"', 's.sh'),
    ("ev_kubectl_create_secret_s__6853", 'kubectl create secret s --from-literal=k=x # eg --from-literal=z=plain', 's.sh'),
    ("ev_kubectl_create_secret_s__32dd", 'kubectl create secret s --from-literal=a=<REDACTED:0123> --from-literal=b=hunter2', 's.sh'),
    ("ev_kubectl_create_secret_s_1cbd", 'kubectl create secret s \\\n  --from-literal=b=hunter2', 's.sh'),
    ("ev_imapsync_password1_hunte_2567", 'imapsync --password1 hunter2 --password2 other', 's.sh'),
    ("ev_cypress_run_env_a_b_ke_2d01", 'cypress run --env "a;b" --key hunter2 --spec s.js', 's.sh'),
    ("ev_sqlplus_admin_hunter2_db_b7cf", 'sqlplus admin/hunter2@dbhost:1521/svc', 's.sh'),
    ("ev_sqlplus_admin_hunter2_db_0b7b", 'sqlplus "admin/hunter2"@db', 's.sh'),
    ("ev_snyk_test_severity_thres_3414", 'snyk test --severity-threshold high', 's.sh'),
    ("ev_ngrok_http_8080_766c", 'ngrok http 8080', 's.sh'),
    ("ev_az_login_p_u_alice_8612", 'az login -p -u alice', 's.sh'),
    ("ev_airflow_users_list_p_808_b5d6", 'airflow users list -p 8080', 's.sh'),
    ("ev_kubectl_create_secret_s__d332", 'kubectl create secret s # c --from-literal=z=plain', 's.sh'),
    ("ev_dotenv_set_foo_hunter2_4fcb", 'dotenv set foo hunter2', 's.sh'),
    ("ev_fly_secrets_list_4a02", 'fly secrets list', 's.sh'),
    ("ev_fab_h_h_p_f_x_task_a7b8", 'fab -H h -p -f x task', 's.sh'),
    ("ev_from_os_import_api_key_e_c26a", 'from os import *\napi_key: environ\n', 'm.py'),
    ("ev_import_numpy_as_n_api_ke_339b", 'import numpy as n\napi_key: n.ndarray\n', 'm.py'),
]
# fmt: on


def main() -> None:
    out = sys.stdout
    for entry in CASES:
        name, text = entry[0], entry[1]
        file = entry[2] if len(entry) > 2 else None
        if _REDACT_HAS_FILE:
            redacted, edits = redact_text(text, file=file)
        else:
            redacted, edits = redact_text(text)
        findings = scan_text(
            text,
            file=file if file is not None else "<corpus>",
            location="corpus",
        )
        record = {
            "name": name,
            "input": text,
            "redact_text": {"output": redacted, "edits": edits},
            "scan_text": findings,
        }
        if file is not None:
            record["file"] = file
        out.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
