# ECOSYSTEM.md — Levantamento total do ecossistema Devin

> Data do levantamento: **2026-10-01** · Gerado por Devin
> Âmbito: `personal-agent-system` (PAS) + `devin-ecosystem/` (powerups `devin-*`)
> + VM `devin-vm` + Obsidian + Slack.

---

## 1. Visão geral

O ecossistema transforma o **Devin Desktop** num agente pessoal autónomo com:

- **Memória persistente** — MCP `memory`/`unified` (store JSONL local) + vault
  Obsidian como segundo cérebro curado.
- **Aprendizado contínuo** — hooks determinísticos (`prompt_logger`,
  `session_learning`) extraem lições e promovem temas a skills `learned-*`;
  camada model-driven via regras always-on.
- **Presença multicanal** — Slack é o canal principal (bot `@devin2`, daemon
  24/7); Discord/WhatsApp opcionais; "Slack Brain" = sessão ACP persistente.
- **Proatividade** — heartbeat emulado (agendamento + checklist + state.json),
  sinais determinísticos do ecossistema, janitor de sessões, scout semanal,
  calibração Djævin.
- **Família de produtos open-source** — 16 repos públicos `devin-*` + hub
  privado `devin-powerups` (registry, roadmap, template, ferramentas).
- **Offload para VM** — `devin-vm` (Debian 12 via Tailscale) hospeda PM2,
  Ollama, browser MCP e serviços pesados para aliviar os ~8 GB de RAM do host.

```
 Slack (@devin2 DM) ──► slack-poll ──► responder (triage→ollama→devin-cli→queue)
        ▲                                   │
        │                            Slack Brain (ACP persistente)
        │                                   │
 heartbeat (Task Sched. 15min) ──► HEARTBEAT.md ──► checklist ──► slack-notify
        │                                   │
 scripts SO ──► state.json / inbox ──► webhook/API Devin
                                        │
              .devin/memory/memories.jsonl ◄── MCP unified (27 tools)
              .devin/skills/learned-*/   ◄── session_learning (Stop/SessionEnd)
              Obsidian vault             ◄── obsidian-bridge MCP (REST :27123)
```

---

## 2. Este repositório — `personal-agent-system`

**Localização:** `C:\Users\Utilizador\Desktop\feat\personal-agent-system`
**Git:** branch `main` → `origin` = `github.com/Icaro0310/personal-agent-system`
(**privado**, criado 2026-10-01; histórico completo pushed, scan de segredos limpo).
**Docs-âncora:** `README.md`, `AGENT-SYSTEM.md`, `HEARTBEAT.md`,
`DJAEVIN-LOCAL.md`, `OBSIDIAN_SETUP.md`, `RAM-OFFLOAD-PLAN.md`.

### 2.1 Componentes

| Pasta | Componente | Estado |
|-------|-----------|--------|
| `mcp/` | Servidores MCP: `unified-server.py` (agrega 27 tools: memory/nlsql/obsidian/gh/ecc), `memory-server.py`, `obsidian-bridge-server.py`, `gh-bridge-server.py`, `nlsql-server.py`, `ecc-bridge-server.py`, `browser-server.py`, `mcp-hub.py` (dedup HTTP :8764) | Ativo (`unified` global) |
| `.devin/hooks.v1.json` | Hooks nativos: SessionStart (obsidian-recall + bootstrap ECC + plan-canvas), UserPromptSubmit (prompt_logger), PreToolUse (GateGuard, config-protection, governance…), PostToolUse, PostCompaction, Stop (session_learning + ECC), SessionEnd (history-export + learning) | Ativo |
| `.devin/rules/` | Regras always-on (heartbeat, obsidian-brain, memoria-persistente, learning-loop, exportar-historico, subagent-triage) + pacote ECC completo (regras por linguagem) | Ativo |
| `.devin/skills/` | ~120 skills ECC + 11 `learned-*` geradas pelo loop (deploy, geral, git, heartbeat, janitor, mailbox, seguranca, shell-windows, testes…) | Ativo |
| `.devin/agents/` | ~65 agentes ECC (reviewers por linguagem, planners, resolvers) | Ativo |
| `.devin/memory/` | Store: `memories.jsonl`, `learning-state.json`, `hook-fires.jsonl`, logs de janitor/calibração/quiz Djævin | Local (gitignored) |
| `gateways/` | Presença multicanal: Slack polling (`slack-poll.js`, bot `@devin2`), `slack-brain.js` (sessão ACP persistente), `responder.js` (cadeia triage→ollama→devin-cli→queue), `slack-notify.js`, `mailbox-wake.js`, heartbeat-wake/rotation, Discord/WhatsApp opcionais | Ativo (daemon via Startup) |
| `heartbeat/` | `email-checker.py`, `calendar-checker.py`, `ecosystem-signals.py`, `state.py`/`state.json` (dedup 2h), README do ciclo | Ativo (tasks 15min) |
| `acp-agent/` | Agente ACP standalone (JSON-RPC stdio) — mesmo learning loop para hosts ACP externos (Zed/Windsurf) | Completo + testes |
| `plugin/personal-agent/` | Núcleo empacotado como plugin instalável (`devin plugins install --local`) | Pronto (install CLI bloqueado por auth — integração de projeto cobre) |
| `plugin/ecc/` + `plugin/ecc-src/` | Fonte e build do pacote ECC (gerado por `scripts/build-ecc-devin.py`) | Ativo |
| `scripts/` | ~45 utilitários — ver §2.2 | — |
| `office/` | `devin-office`: dashboard pixel-art do ecossistema — `probe.py` local (~5-70 MB) + `hub.py` na VM (PM2, :8790) + assets pixel-agents | Em produção (VM) |
| `deploy/agentscope/` | `setup-vm.sh` + `RUNBOOK.md` — bootstrap da VM `devin-vm` | Documentado |
| `planning/` | `00-ROADMAP.md` (plano mestre powerups) + `specs/` (01 internals-spec, 02 redact, 03 office) | Ativo |
| `vendor/poordjaevin/` | Djævin open-source: camada de decisão "System One" calibrada (Choice/Score/Noul, NLI local, temperature scaling, conformal abstention, MCP server) | Ativo, consultivo opt-in |
| `heartbeat/`, `office/state/` | Estado runtime (gitignored) | — |

### 2.2 Scripts por função

| Função | Scripts |
|--------|---------|
| **Learning loop** | `prompt_logger.py`, `session_learning.py`, `memory_context.py`, `obsidian-recall.py` |
| **Histórico/sessões** | `devin-history-export.py` (→ Obsidian `Sessões/`), `audit_sessions.py`, `session_compact.py`, `session-db-maintenance.py`, `session-janitor.py`, `cleanup-slack-sessions.py`, `cleanup-pending-gui-sessions.py`, `devin-space-groups.py` |
| **Djævin** | `djaevin-weekly-calibration.py`, `djaevin-nightly-quiz.py` (300 pares sim/não), `djaevin-vault-sync.py`, `djaevin_curate.py`, `djaevin-acp-bridge.mjs`, testes `test_djaevin_*.py` |
| **Scout/relatórios** | `weekly-ecosystem-scout.mjs` (gh trends + E2E + ideation → Slack/email), `devin-daily-repo-maintenance.mjs`, `devin-repo-task.js`, `fetch_readmes.py` |
| **ECC bridge** | `ecc-hook-runner.js` (tradução tool-names Devin→Claude + dispatch), `build-ecc-devin.py` |
| **VM/offload** | `vm-offload-run.py`, `vm-browser-mcp.py`, `bandwidth-guardian.ps1`, `browser-reaper.ps1`, `register-devin-repo-maintenance.ps1`, `obsidian-watchdog.ps1` |
| **Infra Windows** | `devin-closed-cleanup.bat/.py`, `disable-esrv.bat`, `disable-bloatware.bat`, `stdio-hidden.py` (esconde consolas de subprocessos) |
| **Testes** | `e2e_agent_system.py` (10 checks), `test_session_janitor.py`, `test_ecosystem_signals.py`, `test-devin-*.mjs`, `test-djaevin-*.py/mjs` |

### 2.3 Automação (Task Scheduler do Windows)

Família ~17 tarefas (inventário em `RAM-OFFLOAD-PLAN.md` §2):

| Tarefa | Trigger | Papel |
|--------|---------|-------|
| `DevinDaemon-Boot` + `DevinDaemon-Watchdog` | Logon / intervalo | Núcleo slack-bridge |
| `DevinVM-OllamaTunnel` | Logon | Túnel SSH p/ Ollama + browser MCP na VM |
| `DevinVM-KeepAlive` / `-UptimeCheck` / `-Backup` | Vários | Saúde e backup da VM |
| `DevinHeartbeat-Email` / `-Calendar` | 15 min | Checkers → `state.json` |
| `DevinMailboxRunner` | Intervalo | Mailbox Slack-bridge |
| `DevinSessionJanitor` | Diário 04:30 | Limpeza de sessões-poluição |
| `DevinSlack-Cleanup` | Diário 03:00 | Esconde sessões efémeras |
| `DevinDailyMaintenance` | Diário | Manutenção da DB de sessões |
| `DevinDjaevinWeeklyCalibration` | Semanal (dom 05:00) | Calibração adversarial Djævin |
| `DevinWeeklyEcosystemScout` | Semanal (dom 06:30) | Scout do ecossistema |
| `DevinVM-Offload` | Diário 04:00 | Snapshot → export na VM |
| `DevinBandwidthGuardian` / `DevinBrowserReaper` | 5 min | Janela 23h–07h para apps de banda |
| `ObsidianMCP-Watchdog` | 5 min | Relança REST do Obsidian |
| `ObsidianVault-AutoStart` | Logon | Abre o vault com flags anti-throttling |
| `JevGate-Watchdog` | Disabled | Enforcement legado — removido |
| `DevinMcpHub` (HKCU Run) | Logon | MCP hub HTTP :8764 |

---

## 3. Ecossistema `devin-powerups` (`feat\devin-ecosystem\`)

**Modelo:** multi-repo — 1 repo por projeto, conta `Icaro0310`, MIT, docs
bilingues EN+pt-BR, CI **inline** por repo (Windows + Linux), sem telemetria.
**Maintainer:** Devin (este agente). **Hub privado:** `devin-powerups`
(registry.json, roadmap, template/, tools/, reports/).

### 3.1 Repositórios e vagas (registry v4, 2026-09-30)

| Vaga | Repo | Visib. | Versão | Testes | Estado |
|------|------|--------|--------|-------:|--------|
| 0 Fundação | `devin-powerups` (hub) | privado | — | — | ativo |
| | `devin-internals-spec` | público | 0.2.0 | 33 | entregue |
| | `devin-redact` | público | 0.2.0 (tag) | 23 | entregue |
| 1 Adoção | `devin-history` | público | 0.1.0 | 44 | entregue |
| | `devin-doctor` | público | 0.1.0 | — | entregue |
| | `devin-pm` | público | 0.1.0 | — | entregue |
| 2 Diferencial | `devin-qa-pack` | público | — | — | entregue |
| | `devin-memory` | público | — | — | entregue (absorveu devin-learning) |
| | `devin-metrics` | público | — | — | entregue (absorveu devin-dashboard) |
| | `devin-backup` | público | — | — | entregue |
| 3 Ampliação | `devin-search` | público | — | — | entregue |
| | `devin-graph` | público | — | — | entregue |
| | `devin-evals` | público | — | — | entregue |
| | `devin-orchestrator` | público | — | — | entregue (ex-subagent-orchestrator) |
| 4 Pesquisa | `devin-bridge` | público (JS) | — | — | entregue; Jevin pendente |
| 5 Lifecycle | `devin-janitor` | público | — | — | entregue |

**Totais:** 15 projetos públicos `devin-*` + hub privado `devin-powerups` +
`personal-agent-system` (privado) = **17 repos no ecossistema** · ~728 testes
locais · CI inline verde · stack Python + `devin-bridge` em Node.

> Correção 2026-10-01: o registry/roadmap diziam "16 projetos" porque ainda
> contavam `devin-dashboard` e `devin-learning`, já absorvidos
> (`→devin-metrics`, `→devin-memory`). Contagem real no GitHub: 15 públicos.

**Consolidações:** `devin-dashboard`→`devin-metrics`, `devin-learning`→
`devin-memory`, `devin-subagent-orchestrator`→`devin-orchestrator`,
`devin-ci`+`devin-repo-template`→absorvidos pelo hub.

**Estado git local (2026-10-01):** todos limpos contra `origin/main` exceto
`devin-qa-pack`, `devin-backup`, `devin-orchestrator` (1 ficheiro dirty cada,
não commitado).

### 3.2 Gaps contra o plano

- Publicação PyPI/npm pendente (instalação em 1 comando ainda não existe).
- Integrações M2/M3 nas filas de cada `STATUS.md` (hooks, Obsidian, Slack,
  MCP, dashboards, sync externo).
- Jevin (descongelar) = linha de pesquisa separada; rotação da sessão
  heartbeat e handoff por keywords não implementados.
- `devin-redact` ainda não integrado por omissão no exportador de histórico.

---

### 3.3 Outros repositórios da conta (fora do ecossistema `devin-*`)

Conta `Icaro0310` — 21 repos no total (2026-10-01). Os 4 seguintes são
projetos separados, fora do âmbito deste levantamento:

| Repo | Visib. | Nota |
|------|--------|------|
| `PetSaas` | público | PetCare micro-SaaS (QR + medição + cuidadores) — acoplado ao Obsidian |
| `qwenpaw-sync` | público | Sync QwenPaw (AgentScope + RAW.hq + local); `qwenpaw` corre na VM |
| `ai-survival-trader-refactored` | privado | Refactoring do trading agent |
| `pokeemerald-hackrom` | privado | ROM hack |

**Arquivados** (removidos do GitHub em 2026-09-29, segundo o índice do vault):
`wilson-reborn`, `living-island`, `unyleya-projeto-cicd`, `MobEAD`,
`azure-voting-app-redis`.

## 4. Infra externa

| Recurso | Detalhe |
|---------|---------|
| **VM `devin-vm`** | Debian 12, Tailscale `100.102.159.65`, SSH :2222, 2 vCPU/3.7 GB. Corre sob PM2: `devin-office` (:8790), `qwenpaw` (:8088), `devin-bridge` stack (keepalive/watchdog/slack-poll/uptime-email/poll-watchdog), `ollama serve`, `browser-mcp` (:8765, Playwright headless + Xvfb), `janitor-purge` |
| **Obsidian** | Vault `C:\Users\Utilizador\ObsidianVault` + plugin Local REST API (HTTP :27123). Bridge MCP próprio (`obsidian-bridge-server.py`) porque o `/mcp` nativo do plugin pendura. Watchdog relança a cada 5 min. Flags anti-throttling obrigatórias |
| **Slack** | Workspace "Personal": bot `@devin2` (app "Devin", polling daemon via Startup folder), `@hermes` (sessão Hermes, Socket Mode opt-in). DM `D0C4NQ3QXUN`. Sessão ACP persistente "Slack Brain" — **nunca apagar** |
| **Devin Cloud** | Webhook automation ligado (`DEVIN_WEBHOOK_URL`+secret); emails do scout via workflow `scout-notify` no hub (SMTP secrets no repo) |
| **GitHub** | `gh` autenticado como `Icaro0310` (scopes: repo, workflow, gist, delete_repo, read:org) |
| **MCP `unified`** | Agregador global (27 tools: memory, nlsql, obsidian, github/gh, ecc) — 1 processo por sessão em vez de 5-8 |

---

## 5. Adaptações para utilizadores Linux

O ecossistema foi construído em Windows. Esta secção documenta **o que muda**
para correr em Linux (testado em CI nos repos `devin-*`; o PAS precisa das
adaptações abaixo).

### 5.1 Caminhos

| Windows | Linux |
|---------|-------|
| `C:\Users\<user>\Desktop\feat\personal-agent-system` | `~/personal-agent-system` (ou onde clonares) |
| `%APPDATA%\devin\` (config, `mcp_config.json`, `cli/sessions.db`) | `~/.config/devin/` |
| `%APPDATA%\devin\cli\sessions.db` | `~/.config/devin/cli/sessions.db` |
| Vault `C:\Users\<user>\ObsidianVault` | `~/ObsidianVault` |
| `~/.slack-bridge/*-session.json` | igual (`$HOME/.slack-bridge/`) |

> ⚠️ **`hooks.v1.json` e `mcp_config.json` usam caminhos absolutos de Windows** —
> regenerar com os caminhos Linux equivalentes antes de copiar.

### 5.2 Processos e daemons

| Windows | Linux |
|---------|-------|
| `pythonw` (sem consola) | `python3` + `nohup`/systemd (não existe janela de consola) |
| `scripts/stdio-hidden.py` (esconde janelas de subprocessos) | **Desnecessário** — invocar o comando diretamente nos hooks |
| `run-devin-bot.cmd` + pasta Startup | `systemd --user` unit ou `@reboot` no cron |
| Task Scheduler (`schtasks`) | `cron` ou systemd timers |
| `obsidian-watchdog.ps1` | cron `*/5 * * * *` + `curl -sf http://127.0.0.1:27123/` + relançar `obsidian` se falhar |
| `bandwidth-guardian.ps1`, `browser-reaper.ps1`, `register-devin-repo-maintenance.ps1`, `devin-closed-cleanup.bat`, `disable-*.bat` | **Windows-only** — sem equivalente; reescrever em bash se necessário |

Exemplo — daemon do bot Slack (systemd user):

```ini
# ~/.config/systemd/user/devin-bot.service
[Service]
ExecStart=/usr/bin/node %h/personal-agent-system/gateways/src/slack-poll.js
WorkingDirectory=%h/personal-agent-system/gateways
Restart=always
EnvironmentFile=%h/personal-agent-system/gateways/.env

[Install]
WantedBy=default.target
```

Exemplo — checkers (cron):

```cron
*/15 * * * * /usr/bin/python3 ~/personal-agent-system/heartbeat/email-checker.py
*/15 * * * * /usr/bin/python3 ~/personal-agent-system/heartbeat/calendar-checker.py
30 4  * * * /usr/bin/python3 ~/personal-agent-system/scripts/session-janitor.py
```

### 5.3 Dependências equivalentes

- **Python 3.10+**, **Node 22+** (WebSocket nativo para Socket Mode) — iguais.
- `gh` CLI autenticado (`gh auth login`) — igual.
- **Obsidian**: AppImage/deb; plugin Local REST API idêntico; as flags
  `--disable-background-timer-throttling` etc. aplicam-se da mesma forma
  (lançar via wrapper ou `.desktop` editado).
- **Tailscale/VM**: `deploy/agentscope/setup-vm.sh` já é bash — a VM alvo é
  Debian; a parte host traduz-se para systemd/cron.
- O MCP hub (`mcp-hub.py`, `unified-server.py`) é Python stdio/HTTP —
  portável sem alterações; trocar `command: pythonw` → `python3`.
- Hooks: `pythonw` → `python3`; remover `stdio-hidden.py` da cadeia de
  comando (só existe para esconder janelas no Windows).

### 5.4 O que **não** portar

- Tasks `DevinVM-*` no host e scripts `.ps1/.bat` — reescrever ou eliminar.
- Registry Run keys (`HKCU`) — substituir por `systemd --user`/`~/.config/autostart`.
- `devin.exe` — no Linux é `devin`/`devin-cli`; verificar `devin acp` e paths
  com `devin --help` antes de copiar configs.

---

### 5.5 Estado da cobertura Linux nos repos `devin-*`

Auditado 2026-10-01 — **todos os 15 repos públicos já eram cross-platform no
código** (deteção de plataforma em `paths.py`/equivalente) e todos têm CI em
`windows-latest` + `ubuntu-latest`. O que faltava era a nota explícita: cada
repo ganhou uma secção **"Platform support" / "Suporte de plataformas"** no
`README.md` + `README.pt-BR.md` (12 repos atualizados e pushed; `devin-doctor`,
`devin-memory`, `devin-bridge` e o hub já mencionavam Linux).

**Inconsistência encontrada (a harmonizar):** `devin-pm` resolve a
`sessions.db` em `~/.local/share/devin/` (`XDG_DATA_HOME`), enquanto todos os
outros usam `~/.config/devin/` (`XDG_CONFIG_HOME`). Decidir qual é o canónico
na próxima vaga — provavelmente `XDG_CONFIG_HOME`, alinhado com a store real
do Devin CLI.

## 6. Limites conhecidos

- ~~PAS não tem remote git~~ → **resolvido 2026-10-01**: remote privado
  `Icaro0310/personal-agent-system` criado e histórico pushed.
- Heartbeat é emulação (não nativo); cada ciclo é sessão nova — estado via
  `state.json`/MCP/ficheiros.
- Djævin é **consultivo opt-in** — a infra de enforcement foi desmontada
  (2026-09-30); `vendor/poordjaevin` é a base open-source.
- Sessões `SLACK-BRAIN` e de heartbeat são protegidas do janitor — apagá-las
  perde histórico irrecuperável.
- RAM do host segue pressionada (~8 GB); o grosso é o próprio Devin
  (~2.2 GB) + language_server — não offloadable.

## 7. Próximos passos (backlog consolidado)

1. Publicar `devin-*` em PyPI/npm (DoD: instalação em 1 comando).
2. Integrar `devin-redact` por omissão no `devin-history-export.py`.
3. Fechar M2/M3 por repo (hooks, Obsidian, Slack, dashboards).
4. `disable-bloatware.bat`/`disable-esrv.bat` pendentes de admin.
5. Investigação Jevin + rotação automática da sessão heartbeat.
