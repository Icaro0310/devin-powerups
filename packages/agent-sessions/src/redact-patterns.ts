/**
 * Pattern table + helpers for the devin-redact 0.2.6 TS port.
 *
 * GENERATED DATA — do not hand-edit the pattern sources: they are the
 * verbatim `re` pattern strings from devin-redact 0.2.6
 * (devin-state/packages/redact/src/devin_redact/patterns.py + engine.py).
 * `translatePy` below converts each Python `re` source to an equivalent
 * JS RegExp at module load; the parity gate
 * (tools/check_redact_parity.py) verifies the surface bidirectionally.
 */

export interface PyPattern {
  /** devin-redact pattern name (index fallback `category[i]`). */
  name: string;
  /** Verbatim Python `re` source (fully expanded). */
  src: string;
  /** Python re flag letters in effect (i/m/s/u/a/x). */
  flags: string;
}

export interface PyCategory {
  category: string;
  patterns: PyPattern[];
}

// Insertion order mirrors PATTERNS in patterns.py — it drives
// _iter_matches order, which decides which identical-span pattern keeps
// its name under the dedup/containment filter.
export const PATTERN_DATA: PyCategory[] = [
  {
    category: "api_key",
    patterns: [
      {
        name: "openai_key",
        src: "\\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\\b",
        flags: "u",
      },
      {
        name: "stripe_live_key",
        src: "\\bsk_live_[A-Za-z0-9]{16,}\\b",
        flags: "u",
      },
      {
        name: "stripe_restricted_key",
        src: "\\brk_live_[A-Za-z0-9]{16,}\\b",
        flags: "u",
      },
      {
        name: "aws_access_key_id",
        src: "(?:AKIA|ASIA)[0-9A-Z]{16}\\b",
        flags: "u",
      },
      {
        name: "google_api_key",
        src: "AIza[0-9A-Za-z_-]{35}\\b",
        flags: "u",
      },
      {
        name: "slack_token",
        src: "xox[baprs]-[0-9A-Za-z-]{10,}\\b",
        flags: "u",
      },
      {
        name: "slack_app_token",
        src: "xapp-[0-9A-Za-z-]{10,}\\b",
        flags: "u",
      },
      {
        name: "gitlab_pat",
        src: "glpat-[0-9A-Za-z_-]{16,}\\b",
        flags: "u",
      },
      {
        name: "gitlab_scoped_token",
        src: "gl(?:dt|rt|cbt|agent)-[0-9A-Za-z_-]{16,}\\b",
        flags: "u",
      },
      {
        name: "npm_token",
        src: "npm_[0-9A-Za-z]{30,}\\b",
        flags: "u",
      },
      {
        name: "pypi_token",
        src: "pypi-[0-9A-Za-z_-]{16,}\\b",
        flags: "u",
      },
      {
        name: "digitalocean_pat",
        src: "dop_v1_[0-9A-Za-z]{20,}\\b",
        flags: "u",
      },
      {
        name: "sendgrid_key",
        src: "\\bSG\\.[0-9A-Za-z_-]{16,}\\.[0-9A-Za-z_-]{16,}\\b",
        flags: "u",
      },
      {
        name: "square_token",
        src: "sq0[a-z]{3}-[0-9A-Za-z_-]{20,}\\b",
        flags: "u",
      },
      {
        name: "shopify_token",
        src: "shp(?:at|ca|pa|ss)_[0-9a-fA-F]{32,}\\b",
        flags: "u",
      },
      {
        name: "google_oauth_token",
        src: "ya29\\.[0-9A-Za-z_-]{10,}\\b",
        flags: "u",
      },
      {
        name: "huggingface_token",
        src: "hf_[0-9A-Za-z]{30,}\\b",
        flags: "u",
      },
      {
        name: "stripe_webhook_secret",
        src: "whsec_[0-9A-Za-z]{16,}\\b",
        flags: "u",
      },
      {
        name: "age_secret_key",
        src: "AGE-SECRET-KEY-[0-9A-Z]{20,}\\b",
        flags: "u",
      },
    ],
  },
  {
    category: "bearer_token",
    patterns: [
      {
        name: "bearer_header",
        src: "(?i)bearer[\\s:=]+([A-Za-z0-9._~+/=-]{16,})",
        flags: "iu",
      },
      {
        name: "basic_auth_header",
        src: "(?i)authorization[\\s]*:[\\s]*basic[\\s]+((?!(?-i:[a-z]+\\b))[A-Za-z0-9+/=]{8,})",
        flags: "iu",
      },
      {
        name: "jwt",
        src: "(eyJ[A-Za-z0-9_-]{1,}\\.[A-Za-z0-9_-]{2,}\\.[A-Za-z0-9_-]*)",
        flags: "u",
      },
    ],
  },
  {
    category: "github_token",
    patterns: [
      {
        name: "github_token",
        src: "gh[pousr]_[A-Za-z0-9]{20,}\\b",
        flags: "u",
      },
      {
        name: "github_fine_grained_pat",
        src: "github_pat_[A-Za-z0-9_]{22,}\\b",
        flags: "u",
      },
    ],
  },
  {
    category: "private_key",
    patterns: [
      {
        name: "pem_private_key",
        src: "-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----.*?-----END [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----",
        flags: "su",
      },
      {
        name: "pem_private_key_unterminated",
        src: "-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----[ \\t]*\\r?\\n(?:[A-Za-z0-9+/=]+[ \\t]*\\r?\\n?)+",
        flags: "u",
      },
    ],
  },
  {
    category: "env_assignment",
    patterns: [
      {
        name: "env_assignment",
        src: "(?m)^[\\s\\ufeff]*(?:(?i:export|local|readonly|typeset|env|declare|arg|set|const|let|var|val|static|final|public|private|protected|internal|dim|my|our|mut|volatile|unsigned|signed|long|short|char|int|float|double|bool|string|auto|def|fun|function|struct|enum|class|interface|type|typename|ref|String|str)\\s+|(?:-\\w+\\s+)|(?:[*+-]|#+|//+|<!--|;)\\s*)*(?:\\$?[A-Za-z_]\\w*(?:\\.[A-Za-z_]\\w*)*\\s*[\\[{]\\s*[\\\"']?(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)[\\\"']?\\s*[\\]}]|(?:[A-Za-z_]\\w*\\.)*\\s*[\\\"']?(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)[\\\"']?)\\s*(?:::|[:+?])?[ \\t]*[:=][ \\t]*(?:\\\\\\r?\\n[ \\t]*)*\\s*(?:(?:(?:&[ \\t]*(?:'[A-Za-z_]\\w*)?[ \\t]*(?:mut[ \\t]+)?)+)?[A-Za-z_]\\w*(?:\\.[A-Za-z_]\\w*)*(?:\\s*\\|\\s*[A-Za-z_]\\w*(?:\\.[A-Za-z_]\\w*)*)*\\s*=\\s*)?(?:\\(\\s*(?:\\\"\\\"\\\"(?:\\\\.|[^\\\"\\\\])*?\\\"\\\"\\\"|'''(?:\\\\.|[^'\\\\])*?'''|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*?\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*?'|`(?:\\\\.|[^`\\\\\\r\\n])*?`)(?:(?:\\s|\\\\[ \\t]*\\r?\\n[ \\t]*)*(?:\\\"\\\"\\\"(?:\\\\.|[^\\\"\\\\])*?\\\"\\\"\\\"|'''(?:\\\\.|[^'\\\\])*?'''|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*?\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*?'|`(?:\\\\.|[^`\\\\\\r\\n])*?`))*\\s*\\)(?=[ \\t]*[,}\\]]|[ \\t]*$)|(?:\\\"\\\"\\\"(?:\\\\.|[^\\\"\\\\])*?\\\"\\\"\\\"|'''(?:\\\\.|[^'\\\\])*?'''|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*?\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*?'|`(?:\\\\.|[^`\\\\\\r\\n])*?`)(?:[ \\t]*\\\\\\r?\\n[ \\t]*(?:\\\"\\\"\\\"(?:\\\\.|[^\\\"\\\\])*?\\\"\\\"\\\"|'''(?:\\\\.|[^'\\\\])*?'''|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*?\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*?'|`(?:\\\\.|[^`\\\\\\r\\n])*?`))*(?=[ \\t]*[,}\\]]|[ \\t]*$)|(?:!\\S+[ \\t]+)?[|>][-+]?[ \\t]*(?:\\r?\\n[ \\t]+\\S[^\\n]*)+|\\S(?:[^\\n\\\\]|\\\\\\r?\\n)*)",
        flags: "mu",
      },
      {
        name: "env_assignment_json",
        src: "(?mi)^[\\s\\ufeff]*(?:(?i:env|arg|set|setenv|setx|launchctl[ \\t]+setenv))(?:[ \\t]+[-/][a-zA-Z]+)*[ \\t]+(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)(?:[ \\t]*=[ \\t]*|[ \\t]+)(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*?\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*?'|`(?:\\\\.|[^`\\\\\\r\\n])*?`|\\S(?:[^\\n\\\\]|\\\\\\r?\\n)*)",
        flags: "imu",
      },
      {
        name: "env_assignment[2]",
        src: "(?<![\\w'\\\"])(?:\\\\?\\\"(?:(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?))\\\\?\\\"|\\\\?'(?:(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?))\\\\?'|(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?))\\s*:[ \\t]*=?\\s*(?:\\\"\\\"\\\"(?:\\\\.|[^\\\"\\\\])*?\\\"\\\"\\\"|'''(?:\\\\.|[^'\\\\])*?'''|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*?\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*?'|`(?:\\\\.|[^`\\\\\\r\\n])*?`|\\\\\\\"(?:\\\\.|[^\\\"\\\\\\r\\n\\\\])*?\\\\\\\"|\\\\'(?:\\\\.|[^'\\\\\\r\\n\\\\])*?\\\\')",
        flags: "u",
      },
      {
        name: "env_assignment[3]",
        src: "(?<![\\w'\\\"])(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)\\s*=(?!=)\\s*(?:\\(\\s*(?:\\\"\\\"\\\"(?:\\\\.|[^\\\"\\\\])*?\\\"\\\"\\\"|'''(?:\\\\.|[^'\\\\])*?'''|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*?\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*?'|`(?:\\\\.|[^`\\\\\\r\\n])*?`)\\s*\\)(?=[ \\t]*[,}\\])]|[ \\t]*$)|\\\"\\\"\\\"(?:\\\\.|[^\\\"\\\\])*?\\\"\\\"\\\"|'''(?:\\\\.|[^'\\\\])*?'''|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*?\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*?'|`(?:\\\\.|[^`\\\\\\r\\n])*?`|\\\\\\\"(?:\\\\.|[^\\\"\\\\\\r\\n\\\\])*?\\\\\\\"|\\\\'(?:\\\\.|[^'\\\\\\r\\n\\\\])*?\\\\')",
        flags: "u",
      },
      {
        name: "env_assignment[4]",
        src: "(?<!\\w)(?:setdefault|get|pop|putenv|setenv|getenv|define)\\(\\s*\\\\?[\\\"'](?:(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)|(?:[A-Za-z_][\\w.-]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[\\w.-]*|(?:[A-Za-z_][\\w.-]*?[._-])?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:[._-][A-Za-z0-9]+)*|[A-Za-z_][\\w.-]*?(?i:key|secret|token|password|passwd|credential|auth)s?|[A-Za-z_][\\w.-]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[\\w.-]*|(?:[A-Za-z_][\\w.-]*?[._-])?(?i:pass|pwd|passphrase|passcode|userpass)[0-9]*s?))\\\\?[\\\"']\\s*,\\s*(?:\\\"\\\"\\\"(?:\\\\.|[^\\\"\\\\])*?\\\"\\\"\\\"|'''(?:\\\\.|[^'\\\\])*?'''|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*?\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*?'|`(?:\\\\.|[^`\\\\\\r\\n])*?`)",
        flags: "u",
      },
      {
        name: "env_assignment[5]",
        src: "[(,]\\s*[\\\"'](?:(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)|(?:[A-Za-z_][\\w.-]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[\\w.-]*|(?:[A-Za-z_][\\w.-]*?[._-])?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:[._-][A-Za-z0-9]+)*|[A-Za-z_][\\w.-]*?(?i:key|secret|token|password|passwd|credential|auth)s?|[A-Za-z_][\\w.-]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[\\w.-]*|(?:[A-Za-z_][\\w.-]*?[._-])?(?i:pass|pwd|passphrase|passcode|userpass)[0-9]*s?))[\\\"']\\s*,\\s*(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*?\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*?'|`(?:\\\\.|[^`\\\\\\r\\n])*?`)",
        flags: "u",
      },
      {
        name: "env_assignment[6]",
        src: "(?i)\\.(?:set|with|use|add)[\\w_]*(?:key|token|secret|password|passwd|credential|auth)[\\w_]*\\(\\s*(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])+\\\"|'(?:\\\\.|[^'\\\\\\r\\n])+')",
        flags: "iu",
      },
      {
        name: "env_assignment[7]",
        src: "(?im)^[ \\t]*#[ \\t]*define[ \\t]+(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)[ \\t]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*')",
        flags: "imu",
      },
      {
        name: "env_assignment[8]",
        src: "(?i)\\((?:setq|defvar|defconst|defcustom|setopt)[ \\t]+[\\w*-]*(?:key|token|secret|password|passwd|credential|auth)[\\w*-]*[ \\t]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*')",
        flags: "iu",
      },
      {
        name: "env_assignment[9]",
        src: "(?i)<key>[ \\t]*(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)[ \\t]*</key>[ \\t]*<(?:string|data)>([^<]+)</(?:string|data)>",
        flags: "iu",
      },
      {
        name: "env_assignment[10]",
        src: "[?&;#:](?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)=[^\\s&#]+",
        flags: "u",
      },
      {
        name: "env_assignment[11]",
        src: "(?i)variable[ \\t]+\\\\?[\\\"'](?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)\\\\?[\\\"'][ \\t]*\\{[^}]*?default[ \\t]*=[ \\t]*(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*?\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*?')",
        flags: "iu",
      },
      {
        name: "env_assignment[12]",
        src: "(?im)^[ \\t]*(?:machine\\s+\\S+|default)\\s+login\\s+\\S+\\s+(?:password|account)\\s+((?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "imu",
      },
      {
        name: "env_assignment[13]",
        src: "(?<!\\w)(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)[ \\t]*(?:\\\\u003[daDA]|\\\\[:=])[ \\t]*(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "u",
      },
      {
        name: "env_assignment[14]",
        src: "(?i)\\bsshpass\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[15]",
        src: "(?i)\\b(?:curl|wget|httpie?|fetch)\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[16]",
        src: "(?i)\\bredis-cli\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[17]",
        src: "(?i)\\bldap\\w+\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[18]",
        src: "(?i)\\bhttps?[ \\t]+(?:GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[19]",
        src: "\\b(?:mysql|mysqldump|mariadb|mysqladmin|mysqlcheck)\\w*\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "u",
      },
      {
        name: "env_assignment[20]",
        src: "(?i)\\b(?:htpasswd|mosquitto_passwd)[ \\t]+-\\w*b\\w*(?:[ \\t]+\\S+){1,3}[ \\t]+((?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[21]",
        src: "(?i)--[\\w.-]*(?:password|passwd|passphrase|pass|secret|token|api[-_]?key|access[-_]?key|client[-_]?secret|auth[-_]?token|bearer)[ \\t=]+(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[22]",
        src: "(?i)[ \\t]-(?:password|passwd|pwd|passphrase|secret|token|api[-_]?key|access[-_]?key|client[-_]?secret|auth[-_]?token|bearer|pass|credential)(?![\\w-])[ \\t=]+(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[23]",
        src: "(?i)\\b(?:(?:docker|podman|skopeo|buildah|oras|podman-remote)[ \\t]+login|crane[ \\t]+(?:auth[ \\t]+)?login|helm[ \\t]+registry[ \\t]+login)\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[24]",
        src: "\\b(?:zip|unzip)\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "u",
      },
      {
        name: "env_assignment[25]",
        src: "\\b7z[ \\t]+\\S+[ \\t]+-p((?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "u",
      },
      {
        name: "env_assignment[26]",
        src: "(?i)\\baws[ \\t]+configure[ \\t]+set[ \\t]+\\S*(?:key|secret|token)\\S*[ \\t]+((?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[27]",
        src: "(?i)\\b(?:poetry|pip|npm|gem|bundle|git)[ \\t]+config(?:[ \\t]+set|(?:[ \\t]+--?\\w+)*)?[ \\t]+\\S*(?:key|secret|token|pass\\w*|auth)\\S*[ \\t]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[28]",
        src: "(?i)\\bnpm[ \\t]+set[ \\t]+\\S*(?:key|secret|token|pass\\w*|auth)\\S*[ \\t]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[29]",
        src: "(?i)\\bkubectl\\b(?:[ \\t]+(?!#)(?:\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|[^\\s|&;\\\"'\\\\])+)*?[ \\t]+create[ \\t]+secret\\b(?=(?:(?:[ \\t]|\\\\\\r?\\n)+(?!#)(?:\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|[^\\s|&;\\\"'\\\\])+)*(?:[ \\t]|\\\\\\r?\\n)+--from-literal=)((?:(?:[ \\t]|\\\\\\r?\\n)+(?!#)(?:\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|[^\\s|&;\\\"'\\\\])+)+)",
        flags: "iu",
      },
      {
        name: "env_assignment[30]",
        src: "(?i)\\bnet(?:\\.exe)?[ \\t]+user[ \\t]+\\S+[ \\t]+(?!/)((?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[31]",
        src: "\\brabbitmqctl[ \\t]+add_user[ \\t]+(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|\\S+)[ \\t]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "u",
      },
      {
        name: "env_assignment[32]",
        src: "\\bprintf[ \\t]+[\\\"'][^\\\"'\\n]*(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)[ \\t]*=[ \\t]*%[a-z][^\\\"'\\n]*[\\\"'][ \\t]+((?![<>#]|\\d+>)(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;<>])+)(?:[ \\t]+(?![<>#]|\\d+>)(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;<>])+))*)",
        flags: "u",
      },
      {
        name: "env_assignment[33]",
        src: "\\bsnmp\\w+\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "u",
      },
      {
        name: "env_assignment[34]",
        src: "\\b(?:mongo|mongosh|beeline|snowsql|cqlsh|cypher-shell|rdesktop)\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "u",
      },
      {
        name: "env_assignment[35]",
        src: "\\bmosquitto_\\w+\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "u",
      },
      {
        name: "env_assignment[36]",
        src: "\\bopenssl[ \\t]+enc\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "u",
      },
      {
        name: "env_assignment[37]",
        src: "\\binflux\\w*\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "u",
      },
      {
        name: "env_assignment[38]",
        src: "\\betcdctl[ \\t]+user[ \\t]+add[ \\t]+\\\"[^\\\"\\r\\n]*?:([^\\\"\\r\\n]*?)(?=\\\")",
        flags: "u",
      },
      {
        name: "env_assignment[39]",
        src: "\\betcdctl[ \\t]+user[ \\t]+add[ \\t]+'[^'\\r\\n]*?:([^'\\r\\n]*?)(?=')",
        flags: "u",
      },
      {
        name: "env_assignment[40]",
        src: "\\betcdctl[ \\t]+user[ \\t]+add[ \\t]+\\S+?:((?:\\\\.|[^\\s\\\\|&;\\\"'])+)",
        flags: "u",
      },
      {
        name: "env_assignment[41]",
        src: "\\bansible-vault[ \\t]+encrypt_string\\b(?:[ \\t]+(?:(?:-(?:n|p)|--(?:name|stdin-name|vault-id|encrypt-vault-id|new-vault-id|vault-password-file|vault-ca-cert|vault-ca-path|vault-client-cert|vault-client-key|vault-namespace|vault-tls-server-name|vault-wrap-ttl))\\b[ \\t=]+(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!-)[^\\s|&;]+)|-{1,2}(?!-?(?:n|p|name|stdin-name|vault-id|encrypt-vault-id|new-vault-id|vault-password-file|vault-ca-cert|vault-ca-path|vault-client-cert|vault-client-key|vault-namespace|vault-tls-server-name|vault-wrap-ttl)\\b)[\\w-]+(?:=[^\\s|&;]*)?))*[ \\t]+(?!-)(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "u",
      },
      {
        name: "env_assignment[42]",
        src: "\\b(?:vault|bao|openbao)[ \\t]+login\\b(?:[ \\t]+(?:(?:--?(?:method|path))\\b[ \\t=]+(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!-)[^\\s|&;]+)|-{1,2}(?!-?(?:method|path)\\b)[\\w-]+(?:=[^\\s|&;]*)?))*[ \\t]+(?!-)(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "u",
      },
      {
        name: "env_assignment[43]",
        src: "(?i)\\b(?:snyk[ \\t]+auth|wandb[ \\t]+login|ngrok[ \\t]+(?:config[ \\t]+add-)?authtoken|cloudflared[ \\t]+service[ \\t]+install)\\b(?:[ \\t]+(?:(?:--?(?:host|base-url|url|config|log|log-format|log-level|region|metadata))\\b[ \\t=]+(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!-)[^\\s|&;]+)|-{1,2}(?!-?(?:host|base-url|url|config|log|log-format|log-level|region|metadata)\\b)[\\w-]+(?:=[^\\s|&;]*)?))*[ \\t]+(?!-)(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[44]",
        src: "(?i)\\bzrok[ \\t]+enable\\b(?:[ \\t]+(?:(?:--?(?:description|frontends|d|i))\\b[ \\t=]+(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!-)[^\\s|&;]+)|-{1,2}(?!-?(?:description|frontends|d|i)\\b)[\\w-]+(?:=[^\\s|&;]*)?))*[ \\t]+(?!-)(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[45]",
        src: "\\bssh-keygen\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "u",
      },
      {
        name: "env_assignment[46]",
        src: "\\bsmbclient\\b(?:[ \\t]+-{1,2}[^\\s|&;]+(?:[ \\t=]+(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!-|//)[^\\s|&;]+))?)*[ \\t]+(?:\\\"//(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'//(?:\\\\.|[^'\\\\\\r\\n])*'|//[^\\s|&;]+)[ \\t]+(?!-)(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "u",
      },
      {
        name: "env_assignment[47]",
        src: "\\bconan\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "u",
      },
      {
        name: "env_assignment[48]",
        src: "\\b(?:vault|bao|openbao)[ \\t]+write\\b(?:[ \\t]+-[^\\s|&;]+(?:[ \\t=]+(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!-)[^\\s|&;]+))?)*[ \\t]+(?!-)\\S+[ \\t]+(\\S+?=(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])*)(?:[ \\t]+\\S+?=(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])*))*)",
        flags: "u",
      },
      {
        name: "env_assignment[49]",
        src: "(?i)\\bnomad[ \\t]+var[ \\t]+put\\b(?:[ \\t]+-[^\\s|&;]+(?:[ \\t=]+(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!-)[^\\s|&;]+))?)*[ \\t]+(?!-)\\S+[ \\t]+(\\S+?=(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])*)(?:[ \\t]+\\S+?=(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])*))*)",
        flags: "iu",
      },
      {
        name: "env_assignment[50]",
        src: "(?i)\\{\\s*(?:\\w*(?:secret|token|password|passwd|credential|auth)\\w*|api[_-]?key)\\s*,\\s*(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*')",
        flags: "iu",
      },
      {
        name: "env_assignment[51]",
        src: "\\b(?:putty|plink|pscp|psftp|pageant)\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "u",
      },
      {
        name: "env_assignment[52]",
        src: "\\b(?:sqlcmd|bcp|sqlservr|isql|tsql|osql|knife)\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "u",
      },
      {
        name: "env_assignment[53]",
        src: "\\b(?:twine|flit|fab|fabric)\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "u",
      },
      {
        name: "env_assignment[54]",
        src: "(?i)-(?:src|dest)?(?:store|key)pass(?:word)?[ \\t=]+(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[55]",
        src: "(?i)/(?:pass|password|pwd)[ \\t]*:[ \\t]*(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[56]",
        src: "(?i)\\bxfreerdp\\w*\\b[^\\n]*?/p:(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[57]",
        src: "(?i)\\b(?:x11vnc|vncserver|vncpasswd|tightvnc|tigervnc)\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[58]",
        src: "(?i)\\bmysqladmin\\b[^\\n]*?\\bpassword[ \\t]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[59]",
        src: "(?i)\\brabbitmqctl[ \\t]+change_password[ \\t]+\\S+[ \\t]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[60]",
        src: "\\bipmitool\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "u",
      },
      {
        name: "env_assignment[61]",
        src: "\\b(?:useradd|usermod)\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "u",
      },
      {
        name: "env_assignment[62]",
        src: "\\bdoctl[ \\t]+auth[ \\t]+init\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "u",
      },
      {
        name: "env_assignment[63]",
        src: "(?i)\\bnet[ \\t]+use[ \\t]+(?:[\\w*]:?[ \\t]+)?\\\\\\\\\\S+[ \\t]+(?:/u(?:ser)?:[^\\s]+[ \\t]+)?(?!/)(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[64]",
        src: "(?im)^[ \\t]*secure[ \\t]*:[ \\t]*([A-Za-z0-9+/=._~-]{16,})",
        flags: "imu",
      },
      {
        name: "env_assignment[65]",
        src: "(?i)\\b(?:smbclient|smbget|smbpasswd|rpcclient|winexe)\\b[^\\n]*?[ \\t]-U[ \\t]*\\S+%((?:\\\\.|[^\\s\\\\|&;\\\"'])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[66]",
        src: "(?i)\\blftp\\b[^\\n]*?[ \\t]-u[ \\t]*[\\\"']?\\S+,([^\\\"',\\s]+)",
        flags: "iu",
      },
      {
        name: "env_assignment[67]",
        src: "(?i)\\b(?:sqlplus|sqlldr|sqlcl|exp|expdp|imp|impdp|rman|tnsping|orapki)\\b(?:[ \\t]+\\S+)*?[ \\t]+\\S+?/((?:\\\\.|[^\\s\\\\|&;/@\\\"'])+)(?=[@\\s\\\"'|&;]|$)",
        flags: "iu",
      },
      {
        name: "env_assignment[68]",
        src: "(?i)\\b(?:sqlplus|sqlldr|sqlcl|exp|expdp|imp|impdp|rman|tnsping|orapki)\\b(?:[ \\t]+\\S+)*?[ \\t]+\\\"[^\\s@/\\\"]*?/((?:\\\\.|[^\\s\\\\@\\\"])+)(?=\\\")",
        flags: "iu",
      },
      {
        name: "env_assignment[69]",
        src: "\\bopenssl[ \\t]+passwd(?:[ \\t]+-\\w+)*[ \\t]+((?!-)(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "u",
      },
      {
        name: "env_assignment[70]",
        src: "(?i)[\\\"'][\\w-]*(?:key|token|secret|auth|password|passwd)[\\w-]*[ \\t]*:[ \\t]*([^\\\"'\\s][^\\\"'\\r\\n]*?)[\\\"']",
        flags: "iu",
      },
      {
        name: "env_assignment[71]",
        src: "(?i)-pass(?:in|out)?[ \\t=]+pass:((?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[72]",
        src: "(?i)convertto-securestring[ \\t]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])+\\\"|'(?:\\\\.|[^'\\\\\\r\\n])+')",
        flags: "iu",
      },
      {
        name: "env_assignment[73]",
        src: "(?i)\\b(?:key|name)[ \\t]*=[ \\t]*[\\\"'](?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)[\\\"'][ \\t]+value[ \\t]*=[ \\t]*(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*')",
        flags: "iu",
      },
      {
        name: "env_assignment[74]",
        src: "(?im)^[ \\t]*(?:requirepass|masterauth)[ \\t]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\])+)",
        flags: "imu",
      },
      {
        name: "env_assignment[75]",
        src: "(?im)^[ \\t]*(?:olcRootPW|rootpw)[ \\t:=]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\])+)",
        flags: "imu",
      },
      {
        name: "env_assignment[76]",
        src: "(?i)<(?!key>)[\\w.-]*(?:key|secret|token|password|passwd|credential|auth|pw)[\\w.-]*>[ \\t]*([^<\\s][^<\\r\\n]*?)[ \\t]*</",
        flags: "iu",
      },
      {
        name: "env_assignment[77]",
        src: "(?i)(?:identified[ \\t]+(?:with[ \\t]+\\S+[ \\t]+)?by|with[ \\t]+password)[ \\t]+(?:password[ \\t]+)?(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*')",
        flags: "iu",
      },
      {
        name: "env_assignment[78]",
        src: "(?<![\\w])(?:#+|//+|<!--|;)[ \\t]*(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)[ \\t]*[:=][ \\t]*(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*?\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*?'|`(?:\\\\.|[^`\\\\\\r\\n])*?`|\\S(?:[^\\n\\\\]|\\\\\\r?\\n)*)",
        flags: "u",
      },
      {
        name: "env_assignment[79]",
        src: "(?<!\\w)(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)[ \\t]*=(?!=)[ \\t]*([rRbBuUfF]{0,3}(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*?\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*?')|[^\\s'\\\"&;,)\\]}#]+)",
        flags: "u",
      },
      {
        name: "env_assignment[80]",
        src: "(?<![\\w])(?:[A-Za-z_]\\w*\\.)*\\s*(?i:auth|authn|creds?|credentials|userpass)[ \\t]*=[ \\t]*\\(\\s*(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*?\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*?')\\s*,\\s*(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*?\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*?')",
        flags: "u",
      },
      {
        name: "env_assignment[81]",
        src: "(?i)\\b(?:HTTPBasicAuth|HTTPDigestAuth|HTTPProxyAuth|BasicAuth)\\(\\s*(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*?\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*?')\\s*,\\s*(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*?\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*?')",
        flags: "iu",
      },
      {
        name: "env_assignment[82]",
        src: "\\{\\s*\\\\?[\\\"']?(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)[\\\"']?\\s*:\\s*[^\\s'\\\"`,}\\]]+",
        flags: "u",
      },
      {
        name: "env_assignment[83]",
        src: "(?i)\\b(?:proxy_set_header|add_header|set_header|more_set_headers|more_set_input_headers)[ \\t]+[\\w-]*(?:key|token|secret|auth|password|passwd)[\\w-]*[ \\t]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*?\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*?')",
        flags: "iu",
      },
      {
        name: "env_assignment[84]",
        src: "(?im)^[ \\t]*stats[ \\t]+(?:auth|admin)[ \\t]+\\S+:([^\\s,;\\\"']+)",
        flags: "imu",
      },
      {
        name: "env_assignment[85]",
        src: "(?i)\\b(?:wp[ \\t]+config[ \\t]+set|wp[ \\t]+option[ \\t]+(?:add|update)|drush[ \\t]+(?:config:set|config-set|cset|state:set))[ \\t]+(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)[ \\t]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|[^\\s,;]+)",
        flags: "iu",
      },
      {
        name: "env_assignment[86]",
        src: "(?i)\\b(?:kv[ \\t]+put|etcdctl[ \\t]+put)[ \\t]+\\S*(?:key|secret|token|password|passwd|pw|credential|auth)\\S*[ \\t]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|[^\\s,;]+)",
        flags: "iu",
      },
      {
        name: "env_assignment[87]",
        src: "(\\$(?:apr1|1|2a|2b|2x|2y|5|6)\\$[A-Za-z0-9./$=,]+|\\{(?i:sha|ssha|md5|smd5|crypt|blf-crypt|argon2|pbkdf2|scram|ssha256|ssha512|sha256|sha512)\\}[^\\s\\\"'<>\\],};)]+)",
        flags: "u",
      },
      {
        name: "env_assignment[88]",
        src: "(?im)^[ \\t]*(?:\\w+[ \\t]+)?AUTH(?:ENTICATE)?[ \\t]+PLAIN[ \\t]+([A-Za-z0-9+/=]{10,})[ \\t]*$",
        flags: "imu",
      },
      {
        name: "env_assignment[89]",
        src: "\\b(?i:hydra|medusa|crackmapexec|cme|nxc|netexec|evil-winrm|smbmap|enum4linux(?:-ng)?|psexec|racadm|idracadm?)\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "u",
      },
      {
        name: "env_assignment[90]",
        src: "\\bradtest[ \\t]+(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)[ \\t]+((?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+))",
        flags: "u",
      },
      {
        name: "env_assignment[91]",
        src: "\\bradtest(?:[ \\t]+(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)){4}[ \\t]+((?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+))",
        flags: "u",
      },
      {
        name: "env_assignment[92]",
        src: "(?i)\\bkadmin(?:\\.local)?\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[93]",
        src: "[\\\"'][^\\\"'\\n]*?[ \\t]-pw[ \\t=]+(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;'\\\"])+)",
        flags: "u",
      },
      {
        name: "env_assignment[94]",
        src: "(?i)\\b(?:az[ \\t]+login|surreal(?:db)?[ \\t]+(?:sql|start|import|export|backup)|airflow[ \\t]+users[ \\t]+create)\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[95]",
        src: "\\bswift\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "u",
      },
      {
        name: "env_assignment[96]",
        src: "(?i)\\b(?:codecov|codecov-cli|codacy-coverage-reporter)\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[97]",
        src: "(?i)\\b(?:cypress|browserstack(?:-local)?|testingbot)\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[98]",
        src: "(?i)\\b(?:pulsar-admin|pulsar-client|pulsar-perf|pulsar)\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[99]",
        src: "(?i)\\b(?:atlas|mongocli)\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[100]",
        src: "(?i)\\b(?:confluent[ \\t]+api-key[ \\t]+store|(?:emqx[ \\t]+ctl|emqx_ctl)[ \\t]+admins[ \\t]+passwd)[ \\t]+(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)[ \\t]+((?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+))",
        flags: "iu",
      },
      {
        name: "env_assignment[101]",
        src: "(?i)\\bimapsync\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[102]",
        src: "\\bDBI->connect\\(\\s*(?:q[qwx]?\\{[^}]*\\}|\\\"(?:\\\\.|[^\\\"\\\\])*\\\"|'(?:\\\\.|[^'\\\\])*'|[^,\\s()]+)\\s*,\\s*(?:q[qwx]?\\{[^}]*\\}|\\\"(?:\\\\.|[^\\\"\\\\])*\\\"|'(?:\\\\.|[^'\\\\])*'|[^,\\s()]+)\\s*,\\s*(q[qwx]?\\{[^}]*\\}|\\\"(?:\\\\.|[^\\\"\\\\])*\\\"|'(?:\\\\.|[^'\\\\])*'|[^,\\s()]+)",
        flags: "u",
      },
      {
        name: "env_assignment[103]",
        src: "(?i)\\bpulumi[ \\t]+config[ \\t]+set[ \\t]+(?:--\\w+(?:[ \\t=]+\\S+)?[ \\t]+)*(?:[\\w.-]+:)*(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)[ \\t]+((?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+))",
        flags: "iu",
      },
      {
        name: "env_assignment[104]",
        src: "(?i)\\b(?:cf[ \\t]+set-env[ \\t]+\\S+|netlify[ \\t]+env:set|render[ \\t]+env:set|hardhat[ \\t]+vars[ \\t]+set|dotenv[ \\t]+set|railway[ \\t]+variables?[ \\t]+set|arc[ \\t]+env[ \\t]+-e[ \\t]+\\S+)[ \\t]+(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)[ \\t]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[105]",
        src: "(?i)\\b(?:fly(?:ctl)?[ \\t]+secrets?[ \\t]+set|sst[ \\t]+secrets?[ \\t]+set|infisical[ \\t]+secrets?[ \\t]+set|keybase[ \\t]+secret[ \\t]+set)[ \\t]+(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|\\S+)[ \\t]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[106]",
        src: "(?i)\\bgh[ \\t]+(?:secret[ \\t]+set[ \\t]+\\S+|variable[ \\t]+set[ \\t]+(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?))(?:[^|&;\\n\\\"']|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*')*?[ \\t](?:-b|--body)[ \\t=]*(?!-[-\\w])((?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+))",
        flags: "iu",
      },
      {
        name: "env_assignment[107]",
        src: "(?i)\\bsecurity[ \\t]+add-\\w+-password\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[108]",
        src: "(?i)\\beyaml[ \\t]+encrypt\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[109]",
        src: "(?i)\\bschtasks\\b[^\\n]*?/rp[ \\t:]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|(?:\\\\.|[^/\\s\\\\|&;])(?:\\\\.|[^\\s\\\\|&;])*)",
        flags: "iu",
      },
      {
        name: "env_assignment[110]",
        src: "(?i)\\brclone[ \\t]+config[ \\t]+(?:create|update)[ \\t]+(?:\\S+[ \\t]+){1,2}(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)[ \\t]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+(?:[ \\t]+\\S+[ \\t]+(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+))*)",
        flags: "iu",
      },
      {
        name: "env_assignment[111]",
        src: "(?im)^[ \\t]*(?:\\\\.|[^:\\\\\\r\\n])*(?::(?:\\\\.|[^:\\\\\\r\\n])*){3}:((?:\\\\.|[^\\s:\\\\])+)",
        flags: "imu",
      },
      {
        name: "env_assignment[112]",
        src: "(?i)\\bcomposer[ \\t]+config[ \\t]+http-basic\\S*[ \\t]+(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)[ \\t]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[113]",
        src: "(?i)\\bjenkins-cli\\b[^\\n]*?[ \\t]-auth(?:entication)?[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])+\\\"|'(?:\\\\.|[^'\\\\\\r\\n])+'|(?:\\\\.|[^\\s\\\\|&;])+:(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[114]",
        src: "(?i)\\b(?:cargo[ \\t]+login|nuget[ \\t]+setApiKey)[ \\t]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[115]",
        src: "(?i)\\b(?:keyvault[ \\t]+secret[ \\t]+set|ssm[ \\t]+put-parameter|secretsmanager[ \\t]+(?:put-secret-value|update-secret|create-secret))\\b[^\\n]*?[ \\t]--(?:value|secret-string)[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[116]",
        src: "(?i)\\bdoppler[ \\t]+secrets[ \\t]+set[ \\t]+(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)[ \\t]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[117]",
        src: "(?i)\\bcredstash[ \\t]+(?:put|putsecret)[ \\t]+(?:-\\w+[ \\t=]+\\S+[ \\t]+)*(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)[ \\t]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[118]",
        src: "(?i)\\bchamber[ \\t]+write[ \\t]+\\S+[ \\t]+(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)[ \\t]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[119]",
        src: "(?i)\\bredis-cli\\b[^\\n]*?[ \\t]SET[ \\t]+(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)[ \\t]+((?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+))",
        flags: "iu",
      },
      {
        name: "env_assignment[120]",
        src: "(?i)\\bconjur[ \\t]+variable\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[121]",
        src: "(?i)\\bmc[ \\t]+admin[ \\t]+user[ \\t]+add[ \\t]+(?:(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)[ \\t]+){2}((?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+))",
        flags: "iu",
      },
      {
        name: "env_assignment[122]",
        src: "(?i)\\binflux\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[123]",
        src: "(?i)\\bsendemail\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[124]",
        src: "(?i)\\bsigntool\\b[^\\n]*?/p[ \\t]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[125]",
        src: "(?i)\\bnuget\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[126]",
        src: "\\b(?:rar|unrar)\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "u",
      },
      {
        name: "env_assignment[127]",
        src: "(?i)\\bveracrypt\\b((?:\\\\\\r?\\n|\\\\.|\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?!#)(?:\\\\.|[^\\s\\\\|&;\\\"'])+|[ \\t])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[128]",
        src: "[\\\"']?([\\w.-]+:[^\\s\\\"'|]+)[\\\"']?[ \\t]*\\|[ \\t]*(?:sudo[ \\t]+)?(?:chpasswd|newusers)\\b",
        flags: "u",
      },
      {
        name: "env_assignment[129]",
        src: "(?i)\\bexpect\\b[^\\n]*?password[^\\n]*?[;\\n][ \\t]*send[ \\t]+(?:--[ \\t]+)?(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*')",
        flags: "iu",
      },
      {
        name: "env_assignment[130]",
        src: "(?i)\\bset[ \\t]+:\\w*(?:key|secret|token|password|passwd|credential|auth)\\w*[ \\t]*,[ \\t]*(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*')",
        flags: "iu",
      },
      {
        name: "env_assignment[131]",
        src: "(\\$ANSIBLE_VAULT;[0-9.]+;[A-Z0-9_]+(?:(?:[ \\t]*\\r?\\n)+[ \\t]*[0-9a-fA-F]+)*)",
        flags: "u",
      },
      {
        name: "env_assignment[132]",
        src: "(?i)\\bpassword[ \\t]+(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\#])+)",
        flags: "iu",
      },
      {
        name: "env_assignment[133]",
        src: "(?im)^[ \\t]*(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)[ \\t]+([^\\s][^\\r\\n]*?)[ \\t]*(?:\\r?$|$)",
        flags: "imu",
      },
    ],
  },
  {
    category: "connection_uri",
    patterns: [
      {
        name: "uri_userinfo",
        src: "(?i)[a-z][a-z0-9+.-]{1,31}://([^\\s\\\"'`@/:]+:[^\\s\\\"'`@/]*)@",
        flags: "iu",
      },
    ],
  },
  {
    category: "webhook_url",
    patterns: [
      {
        name: "slack_webhook_url",
        src: "(?i)https://hooks\\.slack\\.com/services/[0-9A-Za-z_-]+/[0-9A-Za-z_-]+/[0-9A-Za-z_-]+",
        flags: "iu",
      },
      {
        name: "discord_webhook_url",
        src: "(?i)https://(?:canary\\.|ptb\\.)?discord(?:app)?\\.com/api/webhooks/[0-9]+/[0-9A-Za-z._~-]+",
        flags: "iu",
      },
      {
        name: "office365_webhook_url",
        src: "(?i)https://[a-z0-9.-]*office\\.com/webhookb2/[0-9A-Za-z@/._-]+",
        flags: "iu",
      },
    ],
  },
  {
    category: "devin_pairing_code",
    patterns: [
      {
        name: "devin_pairing_code",
        src: "(?i)(?:pairing|pair)[ -]?code\\s*[:=]?\\s*([A-Z0-9]{4}(?:-[A-Z0-9]{4}){1,3})",
        flags: "iu",
      },
    ],
  },
  {
    category: "email",
    patterns: [
      {
        name: "email",
        src: "\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}\\b",
        flags: "u",
      },
    ],
  },
  {
    category: "absolute_path",
    patterns: [
      {
        name: "windows_user_path",
        src: "\\b[A-Za-z]:\\\\Users\\\\[^\\s\\\"'<>|]+",
        flags: "u",
      },
      {
        name: "posix_home_path",
        src: "(?<![\\w/.-])/(?:home|Users)/[^\\s\\\"'<>|]+",
        flags: "u",
      },
    ],
  },
];

// Patterns gated to specific blob names (FILE_GATED_PATTERNS).
// Keyed `category[index]`; the check is file.lower().endswith(gate).
export const FILE_GATED: Record<string, string[]> = {
  "env_assignment[133]": [".properties", ".props"],
  "env_assignment[132]": ["msmtprc", "esmtprc", "fetchmailrc"],
  "env_assignment[111]": [".pgpass", "pgpass.conf"],
};

// Arms exempt from the env code-assignment guard
// (GUARD_EXEMPT_PATTERNS): the capture declares the sensitive token.
export const GUARD_EXEMPT = new Set<string>([
  "env_assignment[75]",
  "env_assignment[80]",
]);

// Run-capture arms (SUBMASK_PATTERNS): group 1 spans an argument run;
// redact_text re-scans it with the sub-pattern so only secret-bearing
// tokens mask. Keyed `category[index]` -> sub-pattern source.
export const SUBMASK: Record<string, { src: string; flags: string }> = {
  "env_assignment[29]": { src: "(?<!\\S)--from-literal=[\\w.-]+=(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "u" },
  "env_assignment[14]": { src: "[ \\t](?:-p)[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "iu" },
  "env_assignment[15]": { src: "[ \\t](?:-u|-U|--user(?![\\w-])|--proxy-user(?![\\w-]))[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "iu" },
  "env_assignment[16]": { src: "[ \\t](?:-a)[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "iu" },
  "env_assignment[17]": { src: "[ \\t](?:-w)[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "iu" },
  "env_assignment[18]": { src: "[ \\t](?:-a|--auth(?![\\w-]))[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "iu" },
  "env_assignment[19]": { src: "[ \\t](?:-p(?![\\s=]))[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "u" },
  "env_assignment[23]": { src: "[ \\t](?:-p)[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "iu" },
  "env_assignment[24]": { src: "[ \\t](?:-P)[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "u" },
  "env_assignment[33]": { src: "[ \\t](?:-[AX])[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "u" },
  "env_assignment[34]": { src: "[ \\t](?:-p)[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "u" },
  "env_assignment[35]": { src: "[ \\t](?:-P)[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "u" },
  "env_assignment[36]": { src: "[ \\t](?:-k|-K|-iv(?![\\w-]))[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "u" },
  "env_assignment[37]": { src: "[ \\t](?:-t)[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "u" },
  "env_assignment[45]": { src: "[ \\t](?:-[PN])[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "u" },
  "env_assignment[47]": { src: "[ \\t](?:-p(?!r\\b))[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "u" },
  "env_assignment[51]": { src: "[ \\t](?:-pw)[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "u" },
  "env_assignment[52]": { src: "[ \\t](?:-P)[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "u" },
  "env_assignment[53]": { src: "[ \\t](?:-p)[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "u" },
  "env_assignment[57]": { src: "[ \\t](?:-passwd(?:word)?(?=[ \\t=]))[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "iu" },
  "env_assignment[60]": { src: "[ \\t](?:-P)[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "u" },
  "env_assignment[61]": { src: "[ \\t](?:-p)[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "u" },
  "env_assignment[62]": { src: "[ \\t](?:-t)[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "u" },
  "env_assignment[89]": { src: "[ \\t](?:-p)[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "u" },
  "env_assignment[92]": { src: "[ \\t](?:-(?:pw|w)(?![\\w-]))[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "iu" },
  "env_assignment[94]": { src: "[ \\t](?:-p)[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "iu" },
  "env_assignment[95]": { src: "[ \\t](?:-K)[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "u" },
  "env_assignment[96]": { src: "[ \\t](?:-t)[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "iu" },
  "env_assignment[97]": { src: "[ \\t](?:--key(?![\\w-]))[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "iu" },
  "env_assignment[98]": { src: "[ \\t](?:--auth-params(?![\\w-]))[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "iu" },
  "env_assignment[99]": { src: "[ \\t](?:--privatekey(?![\\w-]))[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "iu" },
  "env_assignment[101]": { src: "[ \\t](?:--password[12](?![\\w-]))[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "iu" },
  "env_assignment[107]": { src: "[ \\t](?:-w)[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "iu" },
  "env_assignment[108]": { src: "[ \\t](?:-s(?![\\w-]))[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "iu" },
  "env_assignment[120]": { src: "[ \\t](?:-v(?![\\w-]))[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "iu" },
  "env_assignment[122]": { src: "[ \\t](?:-password(?![\\w-]))[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "iu" },
  "env_assignment[123]": { src: "[ \\t](?:-xp(?![\\w-]))[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "iu" },
  "env_assignment[125]": { src: "[ \\t](?:-Password(?![\\w-]))[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "iu" },
  "env_assignment[126]": { src: "[ \\t](?:-p(?![\\s=]))[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "u" },
  "env_assignment[127]": { src: "[ \\t](?:-p)[ \\t=]*(?!-[-\\w])(\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*'|(?:\\\\.|[^\\s\\\\|&;])+)", flags: "iu" },
};

// Engine helper regexes (verbatim Python sources + flag letters).
export interface PyHelper { src: string; flags: string }
export const HELPERS = {
  CODE_VALUE: { src: "^\\s*(?:[(\\[{]|[A-Za-z_][\\w.]*\\s*\\(|lambda\\b)", flags: "u" },
  TYPE_EXPR: { src: "[A-Za-z_][\\w.]*(?:\\[[^\\[\\]\\n]*(?:\\[[^\\[\\]\\n]*\\][^\\[\\]\\n]*)*\\])?(?:\\s*\\|\\s*[A-Za-z_][\\w.]*(?:\\[[^\\[\\]\\n]*(?:\\[[^\\[\\]\\n]*\\][^\\[\\]\\n]*)*\\])?)*", flags: "u" },
  REWRITE_TYPE: { src: "(?:(?:&\\s*(?:'\\w+\\s*)?|mut\\s+)+)?[A-Za-z_][\\w.]*(?:\\[[^\\[\\]\\n]*(?:\\[[^\\[\\]\\n]*\\][^\\[\\]\\n]*)*\\])?(?:\\s*\\|\\s*[A-Za-z_][\\w.]*(?:\\[[^\\[\\]\\n]*(?:\\[[^\\[\\]\\n]*\\][^\\[\\]\\n]*)*\\])?)*", flags: "u" },
  SEP: { src: "::[ \\t]*=|:[ \\t]*=|[+?][ \\t]*=|=|:(?![ \\t]*=)", flags: "u" },
  DOTTED_PATH: { src: "[A-Za-z_]\\w*(?:\\.[A-Za-z_]\\w*)+", flags: "u" },
  IMPORT: { src: "(?m)^\\s*import\\s+([^#\\n]+)", flags: "mu" },
  FROM_IMPORT: { src: "(?m)^\\s*from\\s+(\\.*[A-Za-z_]\\w*(?:\\.[A-Za-z_]\\w*)*)\\s+import\\s+([^#\\n(]+)", flags: "mu" },
  FROM_IMPORT_PAREN: { src: "(?m)^\\s*from\\s+(\\.*[A-Za-z_]\\w*(?:\\.[A-Za-z_]\\w*)*)\\s+import\\s*\\(((?:[^)#]|(?=(#[^\\n]*))\\3)*)\\)", flags: "mu" },
  COMMENT: { src: "#[^\\n]*", flags: "u" },
  ASSIGN_NAME: { src: "(?m)^\\s*(?:([A-Za-z_]\\w*)\\s*[-+*/%&|^@<>]{0,2}=(?!=)|for\\s+([A-Za-z_]\\w*)\\s+in\\b|case\\s+([A-Za-z_]\\w*)\\s*[:,]|([A-Za-z_]\\w*)\\s*:\\s*[^=\\n]*=|(?:def|class)\\s+([A-Za-z_]\\w*)\\s*[(:]|(?:with|except)\\b[^\\n]*?\\bas\\s+([A-Za-z_]\\w*)|del\\s+([A-Za-z_]\\w*)\\b)", flags: "mu" },
  TRIPLE_QUOTE: { src: "('''|\\\"\\\"\\\")", flags: "u" },
  TAG_RUN: { src: "<REDACTED:[^>\\n]*>", flags: "u" },
  ENV_FRAGMENT: { src: "[\\s\\ufeff]*(?<!\\w)(?:export\\s+)?[\\\"']?(?:[A-Za-z_][A-Za-z0-9_]*?(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:key|secret|token|password|passwd|credential|auth)[0-9]*s?(?:_[A-Za-z0-9]+)*|[A-Za-z_][A-Za-z0-9_]*?(?i:key|secret|token|password|passwd|credential|auth|pw)s?|[A-Za-z_][A-Za-z0-9_]*[a-z0-9](?:Key|Secret|Token|Password|Passwd|Credential|Auth)[A-Za-z0-9_]*|(?:[A-Za-z_][A-Za-z0-9_]*_)?(?i:pass|pwd|pw|sshpass|passphrase|passcode|userpass)[0-9]*s?)[\\\"']?\\s*[:=]\\s*(?:(?:\\\"(?:\\\\.|[^\\\"\\\\\\r\\n])*?\\\"|'(?:\\\\.|[^'\\\\\\r\\n])*?'|`(?:\\\\.|[^`\\\\\\r\\n])*?`)(?=[ \\t]*[,}\\]]|[ \\t]*$)|\\S[^\\n]*)", flags: "u" },
  NAME: { src: "[A-Za-z_]\\w*", flags: "u" },
} as const satisfies Record<string, PyHelper>;

// _TYPE_ATOM is a fragment spliced into _TYPE_EXPR/_REWRITE_TYPE by
// Python f-string composition — the extracted sources are already
// fully expanded, so no separate constant is needed.

export const TYPE_NAMES: ReadonlySet<string> = new Set([
  "Annotated",
  "Any",
  "Awaitable",
  "Callable",
  "ClassVar",
  "ContextManager",
  "Coroutine",
  "Decimal",
  "Ellipsis",
  "False",
  "Final",
  "Generator",
  "IO",
  "Iterable",
  "Iterator",
  "Literal",
  "Mapping",
  "Match",
  "Never",
  "NoReturn",
  "None",
  "NotImplemented",
  "Optional",
  "Path",
  "PathLike",
  "Pattern",
  "SecretStr",
  "Self",
  "Sequence",
  "Text",
  "True",
  "UUID",
  "Union",
  "bool",
  "bytearray",
  "bytes",
  "complex",
  "date",
  "datetime",
  "dict",
  "float",
  "frozenset",
  "int",
  "list",
  "memoryview",
  "object",
  "range",
  "set",
  "slice",
  "str",
  "time",
  "timedelta",
  "tuple",
  "type",
]);

export const LOWER_DOTTED_TYPES: Record<string, ReadonlySet<string>> = {
  "numpy": new Set([
    "bool_",
    "dtype",
    "generic",
    "ndarray",
  ]),
  "collections": new Set([
    "defaultdict",
    "deque",
    "namedtuple",
  ]),
  "datetime": new Set([
    "date",
    "datetime",
    "time",
    "timedelta",
    "timezone",
    "tzinfo",
  ]),
  "socket": new Set([
    "socket",
  ]),
  "mmap": new Set([
    "mmap",
  ]),
  "array": new Set([
    "array",
  ]),
  "weakref": new Set([
    "proxy",
    "ref",
  ]),
};

export const PY_SOURCE_SUFFIXES = [
  ".py",
  ".pyi",
  ".pyw",
  ".pyx",
  ".pxd",
] as const;

export const PY_SOURCE_NAMES: ReadonlySet<string> = new Set([
  "SConscript",
  "SConstruct",
  "wscript",
]);

export const SECRET_CATEGORIES: ReadonlySet<string> = new Set([
  "api_key",
  "bearer_token",
  "connection_uri",
  "devin_pairing_code",
  "env_assignment",
  "github_token",
  "private_key",
  "webhook_url",
]);

// ---------------------------------------------------------------------------
// Python `re` -> JS `RegExp` translator.
//
// devin-redact's 168 patterns + engine helpers use a deliberately small `re`
// subset. This translator covers exactly that subset and throws on anything
// else (loud failure beats silent divergence):
//
//   escapes   \d \D \s \S \w \W \b \B \A \Z \z \n \r \t \f \v \a
//             \xHH \uXXXX \UXXXXXXXX \0-\777 (octal) \1-\9 (backrefs)
//             \<punct> (literal)
//   classes   [...] with ranges, negation, shorthand expansion, icase folding
//   groups    () (?:) (?=) (?!) (?<=) (?<!) (?i:...) (?-i:...)
//   anchors   ^ $ — translated per the pattern's re.M flag (JS gets no m flag)
//   dot       . — [^\n] or [\s\S] per re.S (JS gets no s flag)
//   icase     re.I and scoped (?i:)/(?-i:) — expanded manually to [xX] atoms
//             and class-range counterparts (JS has no scoped flag groups)
//
// The emitted source always compiles with flags 'gud': g for finditer-style
// iteration, d for m.indices group spans, u for Unicode code-point semantics
// (Python str patterns are Unicode by default). 'i'/'m'/'s' are NEVER passed —
// every flag effect is baked into the emitted source so Python and JS agree.
// ---------------------------------------------------------------------------

const W_INNER = '\\p{L}\\p{N}_';
// Python \b: transition between \w and \W (or string edge). \w = [\p{L}\p{N}_].
const WB = `(?:(?<![${W_INNER}])(?=[${W_INNER}])|(?<=[${W_INNER}])(?![${W_INNER}]))`;
const WB_NEG = `(?:(?<=[${W_INNER}])(?=[${W_INNER}])|(?<![${W_INNER}])(?![${W_INNER}]))`;
// Python \s = str.isspace() set: \t\n\v\f\r \x1c-\x1f \x85 space \xa0 \u1680
// \u2000-\u200a \u2028 \u2029 \u202f \u205f \u3000. (JS \s differs: it adds
// \ufeff and misses \x1c-\x1f/\x85 — spelled out explicitly.)
const PY_SPACE_INNER =
  '\\t\\n\\v\\f\\r\\x1c-\\x1f\\x85 \\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000';
const PY_SPACE = `[${PY_SPACE_INNER}]`;
const PY_SPACE_NEG = `[^${PY_SPACE_INNER}]`;

// Characters that are regex syntax in JS u-mode and must stay escaped.
const SYNTAX_CHARS = new Set('^$\\.*+?()[]{}|'.split(''));

function isAsciiLetter(c: string): boolean {
  return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z');
}
function isDigit(c: string): boolean {
  return c >= '0' && c <= '9';
}
function isHex(c: string): boolean {
  return isDigit(c) || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F');
}
function isOct(c: string): boolean {
  return c >= '0' && c <= '7';
}

// Literal char outside a class. Under icase, ASCII letters become [xX] atoms
// (Python's Unicode case folding also maps a few exotic code points like
// U+212A/Kelvin — accepted divergence, unreachable by the pattern alphabet).
function litChar(c: string, icase: boolean): string {
  if (icase && isAsciiLetter(c)) {
    const lo = c.toLowerCase();
    const up = c.toUpperCase();
    if (lo.length === 1 && up.length === 1 && lo !== up) return `[${lo}${up}]`;
  }
  if (SYNTAX_CHARS.has(c)) return '\\' + c;
  const cp = c.codePointAt(0) ?? 0;
  if (cp < 0x20 || cp === 0x7f) return '\\x' + cp.toString(16).padStart(2, '0');
  return c;
}

// Literal char inside a class (endpoints and singles).
function classChar(cp: number): string {
  if (cp >= 0x30 && cp <= 0x39) return String.fromCodePoint(cp);
  if ((cp >= 0x41 && cp <= 0x5a) || (cp >= 0x61 && cp <= 0x7a)) {
    return String.fromCodePoint(cp);
  }
  const named: Record<number, string> = {
    0x08: '\\b', 0x09: '\\t', 0x0a: '\\n', 0x0b: '\\v',
    0x0c: '\\f', 0x0d: '\\r',
  };
  const n = named[cp];
  if (n !== undefined) return n;
  if (cp < 0x20 || cp === 0x7f) return '\\x' + cp.toString(16).padStart(2, '0');
  const c = String.fromCodePoint(cp);
  if (c === '\\' || c === ']' || c === '^' || c === '-') return '\\' + c;
  if (cp > 0x7e) return '\\u{' + cp.toString(16) + '}';
  return c;
}

interface ClassItem {
  lo?: number | undefined;
  hi?: number | undefined;
  atom?: string | undefined;
}

class PyTranslator {
  private s: string;
  private i = 0;
  private ml: boolean;
  private dot: boolean;
  private ic: boolean;

  constructor(src: string, flags: string) {
    this.s = src;
    this.ml = flags.includes('m');
    this.dot = flags.includes('s');
    this.ic = flags.includes('i');
  }

  private err(msg: string): never {
    const from = Math.max(0, this.i - 30);
    throw new Error(
      `py2js: ${msg} at ${this.i} in …${this.s.slice(from, this.i + 30)}…`,
    );
  }

  private peek(n = 0): string {
    return this.s[this.i + n] ?? '';
  }

  translate(): string {
    // One leading global flag group (?ims...) — letters OR into the
    // flag-derived state (the group's own letters are not in `flags`).
    const m = /^\(\?([ims]+)\)/.exec(this.s);
    if (m !== null) {
      this.i = m[0].length;
      for (const f of m[1]!) {
        if (f === 'i') this.ic = true;
        else if (f === 'm') this.ml = true;
        else if (f === 's') this.dot = true;
      }
    }
    const out = this.parseAlt();
    if (this.i !== this.s.length) this.err('trailing input');
    return out;
  }

  // seq ('|' seq)* — stops before ')' or EOS.
  private parseAlt(): string {
    const parts = [this.parseSeq()];
    while (this.peek() === '|') {
      this.i++;
      parts.push(this.parseSeq());
    }
    return parts.join('|');
  }

  private parseSeq(): string {
    let out = '';
    while (this.i < this.s.length) {
      const c = this.peek();
      if (c === '|' || c === ')') break;
      const atom = this.parseAtom();
      out += atom + this.parseQuant();
    }
    return out;
  }

  private parseQuant(): string {
    const c = this.peek();
    let q = '';
    if (c === '*' || c === '+' || c === '?') {
      q = c;
      this.i++;
    } else if (c === '{') {
      const m = /^\{(\d*)(?:,(\d*))?\}/.exec(this.s.slice(this.i));
      if (m !== null && (m[1] !== '' || m[2] !== undefined)) {
        const a = m[1] === '' ? '0' : m[1]; // Python {,m} == {0,m}; JS rejects {,m}
        const b = m[2];
        q = b === undefined ? `{${a}}` : `{${a},${b}}`;
        this.i += m[0].length;
      } else {
        return ''; // '{' not a quantifier → literal, parsed as atom next
      }
    } else {
      return '';
    }
    if (this.peek() === '?') {
      q += '?';
      this.i++;
    }
    if (this.peek() === '+') this.err('possessive quantifier');
    return q;
  }

  private parseAtom(): string {
    const c = this.peek();
    if (c === '(') return this.parseGroup();
    if (c === '[') return this.parseClass();
    if (c === '\\') return this.parseEscape();
    if (c === '.') {
      this.i++;
      return this.dot ? '[\\s\\S]' : '[^\\n]'; // Python '.' excludes only \n
    }
    if (c === '^') {
      this.i++;
      // Python ^M = string start or after \n; ^ = string start only.
      return this.ml ? '(?:^|(?<=\\n))' : '^';
    }
    if (c === '$') {
      this.i++;
      // Python $M = before \n or at end; $ = at end or before trailing \n.
      return this.ml
        ? '(?=\\n|(?![\\s\\S]))'
        : '(?=\\n?(?![\\s\\S]))';
    }
    this.i++;
    return litChar(c, this.ic);
  }

  private parseGroup(): string {
    if (this.peek(1) !== '?') {
      this.i++;
      const inner = this.parseAlt();
      if (this.peek() !== ')') this.err('unclosed group');
      this.i++;
      return `(${inner})`;
    }
    const n2 = this.peek(2);
    if (n2 === ':' || n2 === '=' || n2 === '!') {
      this.i += 3; // '(', '?', marker
      const inner = this.parseAlt();
      if (this.peek() !== ')') this.err('unclosed group');
      this.i++;
      return n2 === ':' ? `(?:${inner})` : `(?${n2}${inner})`;
    }
    if (this.s.startsWith('?<=', this.i + 1) || this.s.startsWith('?<!', this.i + 1)) {
      const op = this.s.substr(this.i + 1, 3); // '?<=' or '?<!'
      this.i += 4;
      const inner = this.parseAlt();
      if (this.peek() !== ')') this.err('unclosed lookbehind');
      this.i++;
      return `(${op}${inner})`;
    }
    // Scoped flag group: (?i:...) or (?-i:...) — only 'i' occurs in the table.
    if (n2 === '-' || isAsciiLetter(n2)) {
      let j = this.i + 2;
      let neg = false;
      const letters: string[] = [];
      if (this.s[j] === '-') {
        neg = true;
        j++;
      }
      while (j < this.s.length && /[aiLmsux]/.test(this.s[j] ?? '')) {
        letters.push(this.s[j] ?? '');
        j++;
      }
      if (this.s[j] === ':' && letters.length > 0) {
        for (const f of letters) {
          if (f !== 'i') this.err(`scoped flag '${f}' unsupported`);
        }
        this.i = j + 1;
        const saved = this.ic;
        this.ic = !neg;
        const inner = this.parseAlt();
        this.ic = saved;
        if (this.peek() !== ')') this.err('unclosed scoped group');
        this.i++;
        return `(?:${inner})`;
      }
    }
    this.err(`unsupported group ${this.s.substr(this.i, 12)}`);
  }

  private parseEscape(): string {
    const c = this.peek(1);
    if (c === '') this.err('trailing backslash');
    this.i += 2;
    switch (c) {
      case 'd': return '[\\p{Nd}]';
      case 'D': return '[^\\p{Nd}]';
      case 'w': return `[${W_INNER}]`;
      case 'W': return `[^${W_INNER}]`;
      case 's': return PY_SPACE;
      case 'S': return PY_SPACE_NEG;
      case 'b': return WB;
      case 'B': return WB_NEG;
      case 'A': return '^'; // \A == JS ^ with no m flag
      case 'Z':
      case 'z': return '(?![\\s\\S])';
      case 'n': return '\\n';
      case 'r': return '\\r';
      case 't': return '\\t';
      case 'f': return '\\f';
      case 'v': return '\\v';
      case 'a': return '\\x07';
      case 'x': {
        const h = this.s.substr(this.i, 2);
        if (h.length !== 2 || !isHex(h[0] ?? '') || !isHex(h[1] ?? '')) this.err('bad \\x');
        this.i += 2;
        return '\\x' + h;
      }
      case 'u': {
        if (this.peek() === '{') {
          const m = /^\{([0-9a-fA-F]+)\}/.exec(this.s.slice(this.i));
          if (m === null) this.err('bad \\u{}');
          this.i += m[0].length;
          return '\\u{' + m[1] + '}';
        }
        const h = this.s.substr(this.i, 4);
        if (h.length !== 4 || ![...h].every((ch) => isHex(ch))) this.err('bad \\u');
        this.i += 4;
        return '\\u' + h;
      }
      case 'U': {
        const h = this.s.substr(this.i, 8);
        if (h.length !== 8 || ![...h].every((ch) => isHex(ch))) this.err('bad \\U');
        this.i += 8;
        const cp = parseInt(h, 16);
        return cp <= 0xffff ? '\\u' + h.toLowerCase() : '\\u{' + cp.toString(16) + '}';
      }
      case 'N':
        this.err('\\N unsupported');
        break;
      default:
        if (isDigit(c)) {
          if (c === '0') {
            // Octal \0 - \777 (Python allows up to 3 digits total incl. the 0).
            let oct = '0';
            while (this.i < this.s.length && oct.length < 3 && isOct(this.peek())) {
              oct += this.peek();
              this.i++;
            }
            const cp = parseInt(oct, 8);
            return cp <= 0xff ? '\\x' + cp.toString(16).padStart(2, '0') : '\\u{' + cp.toString(16) + '}';
          }
          return '\\' + c; // backreference \1-\9 (group numbering preserved)
        }
        if (SYNTAX_CHARS.has(c) || c === '/') return '\\' + c;
        // u-mode forbids identity escapes of non-syntax chars (\" \# \- \  …)
        // — emit the bare char; none of them are JS metacharacters.
        return litChar(c, this.ic);
    }
    return '';
  }

  // Parse one class escape at index of '\'; returns {cp} or {atom} + next pos.
  private classEscape(j: number): { cp?: number; atom?: string; next: number } {
    const c = this.s[j + 1] ?? '';
    const adv = (n: number): number => j + n;
    switch (c) {
      case 'd': return { atom: '\\p{Nd}', next: adv(2) };
      case 'w': return { atom: '\\p{L}\\p{N}_', next: adv(2) };
      case 's': return { atom: PY_SPACE_INNER, next: adv(2) };
      case 'D':
      case 'W':
      case 'S':
        this.err('negated shorthand inside class');
        break;
      case 'b': return { cp: 0x08, next: adv(2) }; // [\b] = backspace in both
      case 'n': return { cp: 0x0a, next: adv(2) };
      case 'r': return { cp: 0x0d, next: adv(2) };
      case 't': return { cp: 0x09, next: adv(2) };
      case 'f': return { cp: 0x0c, next: adv(2) };
      case 'v': return { cp: 0x0b, next: adv(2) };
      case 'a': return { cp: 0x07, next: adv(2) };
      case 'x': {
        const h = this.s.substr(j + 2, 2);
        if (h.length !== 2 || !isHex(h[0] ?? '') || !isHex(h[1] ?? '')) this.err('bad \\x in class');
        return { cp: parseInt(h, 16), next: adv(4) };
      }
      case 'u': {
        if (this.s[j + 2] === '{') {
          const m = /^\{([0-9a-fA-F]+)\}/.exec(this.s.slice(j + 2));
          if (m === null) this.err('bad \\u{} in class');
          return { cp: parseInt(m[1] ?? '0', 16), next: j + 2 + m[0].length };
        }
        const h = this.s.substr(j + 2, 4);
        if (h.length !== 4 || ![...h].every((ch) => isHex(ch))) this.err('bad \\u in class');
        return { cp: parseInt(h, 16), next: adv(6) };
      }
      case 'U': {
        const h = this.s.substr(j + 2, 8);
        if (h.length !== 8 || ![...h].every((ch) => isHex(ch))) this.err('bad \\U in class');
        return { cp: parseInt(h, 16), next: adv(10) };
      }
      default:
        if (isDigit(c)) {
          if (c === '0') {
            let oct = '0';
            let k = j + 2;
            while (k < this.s.length && oct.length < 3 && isOct(this.s[k] ?? '')) {
              oct += this.s[k];
              k++;
            }
            return { cp: parseInt(oct, 8), next: k };
          }
          this.err('backreference inside class');
        }
        return { cp: c.codePointAt(0) ?? 0, next: adv(2) };
    }
    return { next: adv(2) };
  }

  private parseClass(): string {
    let j = this.i + 1;
    let neg = false;
    if (this.s[j] === '^') {
      neg = true;
      j++;
    }
    const items: ClassItem[] = [];
    let first = true;
    let closed = false;
    while (j < this.s.length) {
      const c = this.s[j] ?? '';
      if (c === ']' && !first) {
        closed = true;
        j++;
        break;
      }
      first = false;
      let it: { cp?: number; atom?: string; next: number };
      if (c === '\\') {
        it = this.classEscape(j);
        j = it.next;
      } else {
        const cp = this.s.codePointAt(j) ?? 0;
        it = { cp, next: j + String.fromCodePoint(cp).length };
        j = it.next;
      }
      // Range? '-' followed by something other than ']'.
      if (this.s[j] === '-' && this.s[j + 1] !== ']' && this.s[j + 1] !== undefined) {
        let ep: { cp?: number; atom?: string; next: number };
        let k = j + 1;
        const ec = this.s[k] ?? '';
        if (ec === '\\') {
          ep = this.classEscape(k);
          k = ep.next;
        } else {
          const ecp = this.s.codePointAt(k) ?? 0;
          ep = { cp: ecp, next: k + String.fromCodePoint(ecp).length };
          k = ep.next;
        }
        if (it.cp === undefined || ep.cp === undefined) this.err('shorthand inside range');
        if (it.cp > ep.cp) this.err('reversed class range');
        items.push({ lo: it.cp, hi: ep.cp });
        j = k;
      } else if (it.atom !== undefined) {
        items.push({ atom: it.atom });
      } else {
        items.push({ lo: it.cp, hi: it.cp });
      }
    }
    if (!closed) this.err('unclosed class');
    this.i = j;
    return this.emitClass(neg, items);
  }

  private emitClass(neg: boolean, items: ClassItem[]): string {
    const atoms: string[] = [];
    const ranges: [number, number][] = [];
    for (const it of items) {
      if (it.atom !== undefined) atoms.push(it.atom);
      else if (it.lo !== undefined && it.hi !== undefined) ranges.push([it.lo, it.hi]);
    }
    if (this.ic) {
      let total = 0;
      for (const [lo, hi] of ranges) total += hi - lo + 1;
      if (total <= 4096) {
        // Per-code-point case expansion, then re-merge into ranges.
        const set = new Set<number>();
        for (const [lo, hi] of ranges) {
          for (let cp = lo; cp <= hi; cp++) {
            set.add(cp);
            const ch = String.fromCodePoint(cp);
            const lo2 = ch.toLowerCase();
            const up2 = ch.toUpperCase();
            if (lo2.length === 1) set.add(lo2.codePointAt(0) ?? cp);
            if (up2.length === 1) set.add(up2.codePointAt(0) ?? cp);
          }
        }
        const cps = [...set].sort((a, b) => a - b);
        const merged: [number, number][] = [];
        let start = cps[0] ?? 0;
        let prev = start;
        for (let k = 1; k <= cps.length; k++) {
          const cur = cps[k];
          if (cur !== undefined && cur === prev + 1) {
            prev = cur;
            continue;
          }
          merged.push([start, prev]);
          if (cur !== undefined) {
            start = cur;
            prev = cur;
          }
        }
        ranges.length = 0;
        ranges.push(...merged);
      } else {
        // Huge range: only add counterparts for pure ASCII letter spans.
        const extra: [number, number][] = [];
        for (const [lo, hi] of ranges) {
          if (lo >= 0x61 && hi <= 0x7a) extra.push([lo - 0x20, hi - 0x20]);
          else if (lo >= 0x41 && hi <= 0x5a) extra.push([lo + 0x20, hi + 0x20]);
        }
        ranges.push(...extra);
      }
    }
    const parts: string[] = [];
    for (const [lo, hi] of ranges) {
      parts.push(lo === hi ? classChar(lo) : `${classChar(lo)}-${classChar(hi)}`);
    }
    parts.push(...atoms);
    return `[${neg ? '^' : ''}${parts.join('')}]`;
  }
}

/** Translate a Python `re` source + flag letters to a JS RegExp ('gud'). */
export function translatePy(src: string, flags = 'u'): RegExp {
  const t = new PyTranslator(src, flags);
  const js = t.translate();
  try {
    return new RegExp(js, 'gud');
  } catch (e) {
    throw new Error(`py2js compile failed for ${JSON.stringify(src.slice(0, 80))}: ${(e as Error).message}`);
  }
}

/** Same translation, returning the emitted JS source (for debugging/tests). */
export function translatePySource(src: string, flags = 'u'): string {
  return new PyTranslator(src, flags).translate();
}

// ---------------------------------------------------------------------------
// Compiled pattern table — mirrors PATTERNS iteration order exactly.
// ---------------------------------------------------------------------------

export interface CompiledEntry {
  category: string;
  /** Pattern index within its category (drives pattern_name + gates). */
  index: number;
  /** Resolved pattern name (explicit name or `category[index]`). */
  name: string;
  /** `category[index]` key used by FILE_GATED / GUARD_EXEMPT / SUBMASK. */
  key: string;
  re: RegExp;
  /** SUBMASK sub-regex for run-capture arms, else undefined. */
  sub?: RegExp | undefined;
}

const NAME_FALLBACK: Record<string, string[]> = {
  api_key: [
    'openai_key', 'stripe_live_key', 'stripe_restricted_key',
    'aws_access_key_id', 'google_api_key', 'slack_token',
    'slack_app_token', 'gitlab_pat', 'gitlab_scoped_token',
    'npm_token', 'pypi_token', 'digitalocean_pat', 'sendgrid_key',
    'square_token', 'shopify_token', 'google_oauth_token',
    'huggingface_token', 'stripe_webhook_secret', 'age_secret_key',
  ],
  bearer_token: ['bearer_header', 'basic_auth_header', 'jwt'],
  github_token: ['github_token', 'github_fine_grained_pat'],
  private_key: ['pem_private_key', 'pem_private_key_unterminated'],
  env_assignment: ['env_assignment', 'env_assignment_json'],
  connection_uri: ['uri_userinfo'],
  webhook_url: ['slack_webhook_url', 'discord_webhook_url', 'office365_webhook_url'],
  devin_pairing_code: ['devin_pairing_code'],
  email: ['email'],
  absolute_path: ['windows_user_path', 'posix_home_path'],
};

function entryName(category: string, index: number, explicit?: string): string {
  if (explicit !== undefined) return explicit;
  const names = NAME_FALLBACK[category] ?? [];
  return index < names.length ? names[index]! : `${category}[${index}]`;
}

// env_assignment patterns beyond the two named arms report as
// `env_assignment[i]` — upstream _PATTERN_NAMES only names indices 0-1.
function envEntryName(index: number): string {
  return index < 2 ? NAME_FALLBACK.env_assignment![index]! : `env_assignment[${index}]`;
}

export const COMPILED: CompiledEntry[] = [];
for (const cat of PATTERN_DATA) {
  cat.patterns.forEach((p, i) => {
    const key = `${cat.category}[${i}]`;
    const subSpec = SUBMASK[key];
    const name =
      cat.category === 'env_assignment'
        ? envEntryName(i)
        : p.name !== ''
          ? p.name
          : entryName(cat.category, i);
    COMPILED.push({
      category: cat.category,
      index: i,
      name,
      key,
      re: translatePy(p.src, p.flags),
      sub: subSpec !== undefined ? translatePy(subSpec.src, subSpec.flags) : undefined,
    });
  });
}

/** FILE_GATED lookup: pattern key -> suffixes the blob name must end with. */
export const FILE_GATED_MAP: ReadonlyMap<string, readonly string[]> = new Map(
  Object.entries(FILE_GATED),
);
export const GUARD_EXEMPT_KEYS: ReadonlySet<string> = new Set(GUARD_EXEMPT);

// Engine helper regexes, compiled once.
export interface CompiledHelpers {
  codeValue: RegExp;
  typeExpr: RegExp;
  rewriteType: RegExp;
  sep: RegExp;
  dottedPath: RegExp;
  imp: RegExp;
  fromImp: RegExp;
  fromImpParen: RegExp;
  comment: RegExp;
  assignName: RegExp;
  tripleQuote: RegExp;
  tagRun: RegExp;
  envFragment: RegExp;
  name: RegExp;
}

function helperRx(h: { src: string; flags: string }, anchored = false): RegExp {
  // Anchored helpers (fullmatch/search-at-start) get no 'g' flag.
  const re = translatePy(h.src, h.flags);
  if (anchored) {
    const src = re.source;
    return new RegExp(src, 'ud');
  }
  return re;
}

export const HELPERS_RX: CompiledHelpers = {
  codeValue: helperRx(HELPERS.CODE_VALUE, true),
  typeExpr: helperRx(HELPERS.TYPE_EXPR, true),
  rewriteType: helperRx(HELPERS.REWRITE_TYPE, true),
  sep: helperRx(HELPERS.SEP),
  dottedPath: helperRx(HELPERS.DOTTED_PATH),
  imp: helperRx(HELPERS.IMPORT),
  fromImp: helperRx(HELPERS.FROM_IMPORT),
  fromImpParen: helperRx(HELPERS.FROM_IMPORT_PAREN),
  comment: helperRx(HELPERS.COMMENT),
  assignName: helperRx(HELPERS.ASSIGN_NAME),
  tripleQuote: helperRx(HELPERS.TRIPLE_QUOTE),
  tagRun: helperRx(HELPERS.TAG_RUN),
  envFragment: helperRx(HELPERS.ENV_FRAGMENT),
  name: helperRx(HELPERS.NAME, true),
};
