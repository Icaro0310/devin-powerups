# Capability profile (F10)

Two machine profiles govern what devin-* tools may do. The **core is
identical on both** — Python stdlib, offline, no daemon. What differs is
which optional extras a machine is allowed to run.

## Profiles

| | `corporate` (default) | `personal` |
|---|---|---|
| network out | no | opt-in, allowlisted |
| scheduler (cron/Task Scheduler) | no — falls back to `UserPromptSubmit` | yes |
| daemons / listeners | no | loopback with token |
| local LLM (Ollama) | no | yes |
| containers | no | yes |
| outbound comms (Slack/Telegram/desktop) | flag-file read on next prompt | yes |

`corporate` is the **fail-closed default** — a tool assumes it unless the
machine declares otherwise. `personal` is never inferred; it must be
declared explicitly (see *Declaring*).

Zero telemetry holds on **both** profiles — what changes is what the
operator allows the machine to *do*, not what tools send about you.

## Declaring a profile

Resolution order (first match wins):

1. `DEVIN_ECOSYSTEM_PROFILE=corporate|personal`
2. `devin-profile.json` inside the Devin config dir
   (`%APPDATA%/Devin/` on Windows, `$XDG_CONFIG_HOME/Devin/` on Linux):
   `{"profile": "personal", "capabilities": {...}, "machine_id": "..."}`
3. default: `corporate`

## Probing capabilities

`devin-doctor capabilities` emits the effective profile as JSON conforming
to `capability-profile.schema.json`. Probing is **local only** (binaries
on PATH, env vars, RAM size); the network capabilities stay `"unknown"`
unless `--probe-network` is passed, which performs a single bounded
connectivity check and is documented loudly.

## Extras

Personal-track extras declare their needs with `requires:` and must refuse
to run when the capability is absent:

```json
{"requires": ["net.outbound", "scheduler"]}
```

Shipping shape: optional extras (`devin-x[personal]`) or separate packages,
so the core never leaves stdlib-only.

## Security invariants (both profiles)

Quarantine, human approval, deny-wins, `--apply` for any write, zero
telemetry, and no session content in notifications — identical on both
profiles. The profile only gates *capabilities*, never *safeguards*.
