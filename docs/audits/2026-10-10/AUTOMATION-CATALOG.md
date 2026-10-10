# Automation catalog & reconstruction runbook — 2026-10-10

Inventário de toda automação viva do ecossistema: agendada (cron/systemd/Task
Scheduler), orientada a eventos (Devin hooks) e CI. Distingue o que está
**implementado**, **instalado na máquina do mantenedor** e **documentado**.

Convenção de paths (placeholders — nunca comitar paths reais):
`<USER_HOME>` · `<PAS_ROOT>` = checkout do `personal-agent-system` ·
`<AUTOMATION_BIN>` = dir de wrappers (`~/.local/bin` no Linux) ·
`<DEVIN_DATA>` = `~/.local/share/devin` / `%APPDATA%\devin` ·
`<DEVIN_CONFIG>` = `~/.config/Devin` / `%APPDATA%\Devin`.

> ⚠️ Todo este catálogo é de ambiente **pessoal**. Nada daqui é instalado
> pelo DevKit e nada deve ser recriado num Corporate Windows: os jobs abaixo
> dependem de Slack, VM QwenPaw, LLM backends, rede livre ou paths pessoais.
> O runbook de reconstrução existe para Windows **pessoal** e Linux.

## 1. Camada de eventos (Devin hooks)

Config: `<DEVIN_CONFIG>/../devin/config.json` (`hooks` section). Despacho
genérico: `<PAS_ROOT>/scripts/session-dispatcher.py --event <E> --handler <id>`
— o catálogo de handlers vive em `<PAS_ROOT>/.devin/catalog/`.

| Evento | Handler instalado | Script | Fail | Classe |
|---|---|---|---|---|
| SessionStart | obsidian.recall | `scripts/obsidian-recall.py` | fail-open | core |
| UserPromptSubmit | prompt logger | `scripts/prompt_logger.py` → `.devin/memory/session-*.jsonl` | fail-open | core |
| Stop | learning.session-end | `scripts/session_learning.py` (incremental) | fail-open | core |
| SessionEnd | history.export + learning.session-end | `scripts/devin-history-export.py` (env DEVIN_DB/GUI_DB_DIR/DEVIN_VAULT) + `session_learning.py` | fail-open | core |

Trigger definitions (50) em `<PAS_ROOT>/.devin/catalog/triggers/*.yaml` —
cada YAML carrega `# Migra <TaskName>` com o nome da task do Windows Task
Scheduler que substitui.

## 2. Jobs agendados — Linux (estado real, verificado 2026-10-10)

Todos os paths de script referenciados existem e são executáveis.

### Sessão e memória

| Schedule (cron) | Comando | Task Windows equiv. | Essencial? |
|---|---|---|---|
| `*/30 * * * *` | `<AUTOMATION_BIN>/heartbeat-trigger.sh` | DevinHeartbeat (30m) | core |
| `7 * * * *` | `scripts/session-sweep.py` (cwd `<PAS_ROOT>`) | runtime.session-sweep | core |
| `30 4 * * *` | `<AUTOMATION_BIN>/session-janitor-run.sh` → `scripts/session-janitor.py --apply` | DevinSessionJanitor (04:30) | core |
| `0 4 * * *` | `scripts/cleanup-slack-sessions.py` | DevinSlack-Cleanup | opcional |
| `0 7 * * 0` | `session-dispatcher.py --event Scheduled --handler learning.weekly-extract` | — | opcional |
| `0 5 * * *` | `session-dispatcher.py --handler skills.audit` | — | opcional |
| `45 4 * * *` | `session-dispatcher.py --handler janitor.space-report` | — | opcional |
| `*/15 * * * *` | `heartbeat/email-checker.py` + `calendar-checker.py` — **desativado** (sem creds IMAP/GOOGLE, fail-open) | DevinHeartbeat-Email/-Calendar | desligado |

### VM / QwenPaw

| Schedule | Comando | Equiv. Windows | Classe | Notas |
|---|---|---|---|---|
| `*/15 * * * *` | `vm-keepalive.sh` | DevinVM-KeepAlive | core* | ssh via tailscale userspace |
| `15 5 * * *` | `vm-backup.sh` | DevinVM-Backup | core* | tar → ssh → scp, retenção 7d |
| `0 9 * * *` | `vm-uptime-check.py` | DevinVM-UptimeCheck | opcional* | email MailerSend só se down |
| systemd `vm-ollama-tunnel` | `ssh -N -L 11435:… -L 8765:… devin-vm` | DevinVM-OllamaTunnel (logon) | core* | Restart=always |
| systemd `devin-vm-rtunnel` | reverse tunnel VM→laptop :2223 | — | core* | |

`*` = depende da VM QwenPaw (só personal). Sem VM, todo o bloco é `n/a`.

### Ops / GitHub

| Schedule | Comando | Classe | Notas |
|---|---|---|---|
| `7,47 * * * *` | `scripts/answer-runner.py` | core | Q&A autopilot; travas denylist+categoria+humanize+gate Djævin; máx 5/dia |
| `30 4 * * 0` | `scripts/weekly-ecosystem-scout.mjs --apply` (node) | opcional | DevinWeeklyEcosystemScout |
| `0 6 * * 0` | `scripts/weekly-testgen.mjs --apply` (node) | opcional | gera casos + email cobertura |
| `45 4 * * *` | `scripts/fork-janitor.py` | opcional | apaga forks sem PR / PR >72h |
| `*/15 * * * *` | `gh-notif-silence.sh` | opcional | unsub+done em threads de repos próprios |
| `0 9 * * 1` | `scripts/gsc-report.py` | opcional | Google Search Console semanal |
| `*/20 * * * *` | `mailbox-wake-watch.sh` | core | DevinMailboxRunner parcial (sem node) |

### Monitoramento / vault

| Schedule | Comando | Classe | Notas |
|---|---|---|---|
| `*/10 * * * *` | `scripts/ecosystem-health.sh` | core | laptop+VM, alerta Slack só em transição |
| `*/5 * * * *` | `scripts/office-freshness-check.py` | core | watchdog do devin-office probe |
| `*/5 * * * *` | `obsidian-watchdog.sh` | core | relança Obsidian AppImage se morrer; opt-out `~/.config/obsidian-watchdog.disabled` |
| `*/30 * * * *` | `scripts/vault-compressor.py` | opcional | comprime notas do vault |
| `*/5 * * * *` | `devin-dashboard/tools/laptop_reporter.py` | opcional | repo privado devin-dashboard |
| `0 3 * * *` | `djaevin-quiz-run.sh` → `scripts/djaevin-nightly-quiz.py` | core | DevinDjaevinNightlyQuiz |
| `0 5 * * 0` | `djaevin-calibration-run.sh` | core | DevinDjaevinWeeklyCalibration — alimenta o gate do answer-runner |
| `15 3 * * *` | `devin-backup create` (venv) | core | já existia pré-migração |
| `30 3 * * 0` | `devin-backup rotate --keep 10 --yes` | core | |

### systemd --user services (ativos)

| Service | Classe | Notas |
|---|---|---|
| `mcp-hub` (:8764) | core | hub de MCPs |
| `slack-poll` | core | DMs→ACP (Slack brain) |
| `obsidian` (REST :27123) | core | vault MCP |
| `tailscaled` (userspace) | core | base dos túneis VM |
| `vm-ollama-tunnel` | core* | ver tabela VM |
| `devin-vm-rtunnel` | core* | ver tabela VM |
| `devin-dashboard-tray` | opcional | |
| `devin-office-probe` | core | roda `devin-control/packages/office/probe.py` — unit repontado hoje para o path canônico do monorepo |
| `qwenpaw-bridge` (:5000) | **dead/disabled** | `vm-ollama-tunnel` já serve :11435; provável órfão — confirmar antes de remover |

Linger ativo (`loginctl enable-linger`) — services arrancam no boot sem login.

## 3. CI schedulers (GitHub Actions, verificado)

| Repo | Workflow | Cron |
|---|---|---|
| devin-powerups | registry-refresh | seg 07:33 UTC |
| devin-powerups | registry-drift | dom 05:41 UTC |
| devin-powerups | contract-check | seg 06:17 UTC |
| devin-powerups | baseline-snapshot | seg 08:15 UTC (+ 3 dez) |
| devin-powerups | weekly-repo-report | dom 07:00 UTC |
| devin-powerups | codeql, scorecard | semanal |
| devin-devkit | manifest-sync | ter 07:44 UTC |
| repos produto | links.yml (awesome-devin, site), cflite, codeql, scorecard | semanal |

## 4. Reconstruction runbook

### Linux (pessoal) — ordem segura

1. **Base**: `git clone` PAS → `<PAS_ROOT>`; `python3 -m venv` dedicados
   (`<USER_HOME>/.venvs/devin-backup`, poordjaevin se usado); node em
   `~/.local` (desbloqueia scout/testgen/slack-notify).
2. **Wrappers**: instalar scripts de `<AUTOMATION_BIN>` (heartbeat-trigger,
   session-janitor-run, vm-*, djaevin-*, obsidian-watchdog,
   mailbox-wake-watch, gh-notif-silence) — cada um é idempotente por
   `flock`/state file.
3. **Hooks**: escrever `hooks` em `<DEVIN_CONFIG>/config.json` apontando para
   `<PAS_ROOT>/scripts/{obsidian-recall,prompt_logger,session_learning,
   devin-history-export}.py` — preservar hooks existentes (merge, não overwrite).
4. **Cron**: `crontab -e`, PATH=`$HOME/.local/bin:…` no topo; colar o bloco
   desejado da tabela §2 — começar pelo core (heartbeat, sweep, janitor),
   ligar o resto por demanda.
5. **systemd**: copiar units para `~/.config/systemd/user/` +
   `systemctl --user daemon-reload && enable --now <u>`;
   `loginctl enable-linger $USER` para boot sem login.
6. **Validar**: cada job tem log (`~/logs/cron.log`, `~/.slack-bridge/*.log`,
   `journalctl --user -u <svc>`); rodar cada script manualmente uma vez antes
   de agendar (todos aceitam `--dry-run` onde aplicável).

### Windows pessoal — equivalentes

- cron → **Task Scheduler** (`schtasks /create /tn <TaskName> /tr ... /sc
  minute|daily|weekly /mo <n>`). Os nomes canônicos estão nos comentários
  `# Migra …` dos trigger YAMLs.
- systemd --user → Task "At log on" (trigger) ou `Startup` folder.
- `python3` → `python`/`py -3`; wrappers `.sh` → `.ps1` originais em
  `<PAS_ROOT>` (ex.: `vm-backup.ps1`, `obsidian-watchdog.ps1`,
  `register-devin-repo-maintenance.ps1` registra o bloco de manutenção).
- Hooks `config.json` em `%APPDATA%\devin\config.json` — mesma estrutura.
- Logs em `<USER_HOME>\logs\` + `~/.slack-bridge/*.log`.

### O que NÃO portar (corporate ou geral)

- Nada que fale com Slack (`slack-notify.js`, slack-poll), VM/tailscale,
  MailerSend, GSC, ou backends LLM (djaevin-*, answer-runner, gate).
- `devin-backup install` auto-agenda — em corporate, se usado, registrar
  como ação explícita do usuário e documentar a task criada.
- Jobs que precisam de secrets em `heartbeat/.env`/`gateways/.env` ficam
  fail-open sem credenciais — não "consertar" inventando valores.

## 5. Gaps encontrados

- `AUTOMATION-LINUX.md` (a doc de migração) diz "Node não instalado" e
  "djaevin jobs skipped" — ambos **obsoletos**: node já existe em
  `~/.local/bin/node` e os jobs djaevin correm no cron. A doc vive fora do
  repo (`~/logs/`) — migrar versão sanitizada para `<PAS_ROOT>/docs/`.
- `qwenpaw-bridge.service` está dead/disabled mas o status "ollama_connected"
  é reivindicado na doc — verificar se o tunnel :11435 cobre ou se o
  bridge :5000 é órfão.
- `devin-office-probe.service` **já está correto** — verificação
  pós-auditoria (`systemctl --user cat`) mostra o unit apontando para
  `devin-control/packages/office/probe.py`, o path canônico pós-
  consolidação. Foi repontado hoje (~20:08) após ~21h morto apontando
  para o checkout removido do repo arquivado. Redação anterior deste
  catálogo dizia "atualizar para o monorepo" — era a mesma task, já
  corrigida.
- Nenhum catálogo público existia antes desta auditoria; os trigger YAMLs do
  PAS são a fonte canônica (privados) — esta página é a projeção pública.
