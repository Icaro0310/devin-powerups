# Agendamento — jobs recorrentes do ecossistema

Um único lugar que lista **toda** automação recorrente do ecossistema e como
recriá-la em cada sistema operacional. Lendo só este arquivo, um agente (ou
uma pessoa) consegue remontar a camada de agendamento numa máquina nova sem
vasculhar os repositórios.

Duas camadas distintas:

- **Camada CI (GitHub Actions `schedule:`)** — roda no GitHub, mantida pelo
  mantenedor. Não precisa de equivalente local; documentada por awareness.
- **Camada usuário (jobs instaláveis)** — jobs que ferramentas do
  ecossistema registram na máquina do usuário (snapshot diário, limpeza,
  varreduras semanais). Estes precisam de equivalente por SO.

Sem segredos: todos os caminhos usam `<PLACEHOLDERS>` ou variáveis de
ambiente. Nunca copie um caminho absoluto de uma máquina específica.

---

## 1. Camada usuário — jobs instaláveis

Três backends, resolvidos em `auto` nesta ordem: **Task Scheduler**
(Windows) → **cron** (Linux/macOS) → **elapsed** (fallback corporate, sempre
disponível). Dois implementadores com a mesma tabela de decisão:

- `tools/schedule.py` (neste repo) — CLI genérico:
  `python3 tools/schedule.py install <nome> "<comando>" --daily`
- `devin-install-scheduler` (`devin-state/shared/install-scheduler`) —
  biblioteca embutida; os pacotes `devin-backup` e `devin-janitor` expõem
  `<tool> install` que a consome.

O backend **elapsed** não usa agendador do SO: registra o job em
`<config-dir>/.devin-ecosystem/scheduled.json` e um hook `UserPromptSubmit`
(chamando `schedule.py check --run`) executa o que estiver vencido — "o
prompt é o tick". É a resposta correta quando a política bloqueia o Task
Scheduler ou quando não há cron.

| Job | O que faz | Cadência | Onde vive |
|---|---|---|---|
| `devin-backup` | snapshot dos dados Devin | diário 03:15 | `devin-state/packages/backup` — ou `devin-backup install` (self-schedule) |
| `devin-backup rotate` | rotação de snapshots | semanal | mesmo pacote |
| `devin-janitor` | relatório/limpeza diária | diário 04:30 | `devin-state/packages/janitor` — `devin-janitor install` |
| `devin-doctor` | health check read-only | semanal seg 09:00 | `devin-explore/packages/doctor` |
| `devin-history` | export de sessões p/ notas | semanal dom 05:00 | `devin-explore/packages/history` |
| `devin-memory` | extração de conhecimento | semanal dom 07:00 | `devin-brain` |
| `devin-evals` | replay de regressão | semanal dom 06:00 | `devin-assure/packages/evals` |
| `devin-metrics` | resumo de uso | diário 04:45 | `devin-assure/packages/metrics` |
| `devin-graph` | rebuild do graph.db | semanal dom 06:00 | `devin-explore/packages/graph` |
| `devin-office` | daemon dashboard (restart) | `@reboot`/logon | `devin-control/packages/office` — daemon, usar serviço, não intervalo |
| `weekly-repo-report` | relatório HTML de atividade | semanal | `devin-powerups/tools/weekly_repo_report.py` — o único job de CI com equivalente local documentado |

### 1.1 Linux (cron ou systemd --user)

Entradas de `crontab -e` literais:

```cron
15 3 * * * devin-backup create --out $HOME/backups
30 4 * * * devin-janitor run --apply
0 9 * * 1 devin-doctor check
0 5 * * 0 devin-history export --out $HOME/devin-history-export
0 7 * * 0 devin-memory --db $HOME/devin-memory/memory.db extract --latest --sessions-db $HOME/.local/share/devin/cli/sessions.db
0 6 * * 0 devin-evals run --evals $HOME/devin-evals/cases --sessions-db $HOME/.local/share/devin/cli/sessions.db
45 4 * * * devin-metrics summary
0 6 * * 0 devin-graph build
@reboot python3 <CAMINHO_DO_REPO>/devin-control/packages/office/daemon.py --port 8788
```

Equivalente `systemd --user` timer funciona para todos; ative *lingering*
(`loginctl enable-linger`) se o job precisa rodar sem sessão de login. Para
daemons (office), prefira uma unit `Restart=on-failure` a `@reboot` — e
lembre que unidades em crash-loop ficam invisíveis a `systemctl --failed`
(ver o README.linux.md do pacote office para o diagnóstico).

### 1.2 Windows Personal (Task Scheduler, escopo de usuário)

Jobs com caminho que pode ter espaço (`%USERPROFILE%`, `%APPDATA%`,
`<CAMINHO_DO_REPO>`) usam um wrapper `.cmd` — embutir aspas dentro do
`/tr` falha diferente em cmd.exe e PowerShell 5.1. Salve o comando em
`%USERPROFILE%\devin-tasks\<nome>.cmd` (dentro do arquivo a aspa funciona
normal) e aponte o `/tr` para o arquivo:

```batch
:: %USERPROFILE%\devin-tasks\devin-backup.cmd
devin-backup create --out "%USERPROFILE%\backups"

:: %USERPROFILE%\devin-tasks\devin-history.cmd
devin-history export --out "%USERPROFILE%\devin-history-export"

:: %USERPROFILE%\devin-tasks\devin-brain.cmd
devin-memory --db "%USERPROFILE%\devin-memory\memory.db" extract --latest --sessions-db "%APPDATA%\devin\cli\sessions.db"

:: %USERPROFILE%\devin-tasks\devin-evals.cmd
devin-evals run --evals "%USERPROFILE%\devin-evals\cases" --sessions-db "%APPDATA%\devin\cli\sessions.db"

:: %USERPROFILE%\devin-tasks\devin-office.cmd
py "<CAMINHO_DO_REPO>\daemon.py" --port 8788
```

```powershell
schtasks /create /tn "devin-backup"   /tr "%USERPROFILE%\devin-tasks\devin-backup.cmd"   /sc daily  /st 03:15 /f
schtasks /create /tn "devin-janitor"  /tr "devin-janitor run --apply"                     /sc daily  /st 04:30 /f
schtasks /create /tn "devin-explore"  /tr "devin-doctor check"                            /sc weekly /d MON /st 09:00 /f
schtasks /create /tn "devin-history"  /tr "%USERPROFILE%\devin-tasks\devin-history.cmd"  /sc weekly /d SUN /st 05:00 /f
schtasks /create /tn "devin-brain"    /tr "%USERPROFILE%\devin-tasks\devin-brain.cmd"    /sc weekly /d SUN /st 07:00 /f
schtasks /create /tn "devin-evals"    /tr "%USERPROFILE%\devin-tasks\devin-evals.cmd"    /sc weekly /d SUN /st 06:00 /f
schtasks /create /tn "devin-metrics"  /tr "devin-metrics summary"                         /sc daily  /st 04:45 /f
schtasks /create /tn "devin-graph"    /tr "devin-graph build"                             /sc weekly /d SUN /st 06:00 /f
schtasks /create /tn "devin-office"   /tr "%USERPROFILE%\devin-tasks\devin-office.cmd"   /sc onlogon /f
```

`schtasks` em escopo de usuário não pede admin. Para o daemon, `/sc onlogon`
(disparo no logon) é o trigger correto — não um intervalo. Dois detalhes
práticos: `schtasks` não tem opção "Start in" — o wrapper `.cmd` do office
chama `daemon.py` por caminho absoluto (acima), ou edite a tarefa depois em
Task Scheduler → Actions → Edit → "Start in" = diretório do checkout.

### 1.3 Windows Corporate (mesma sintaxe, restrições reais)

A sintaxe é a mesma de 1.2; o que muda são as premissas:

- **Escopo de usuário, nunca elevado.** "Run whether user is logged on or
  not" e qualquer opção com privilégio elevado costuma estar bloqueada por
  política. Sintoma: erro `0x80070005` "Access is denied" ao criar a tarefa.
- **Máquina pode estar desligada/suspensa no horário.** Quando o agendador
  por horário não serve, o trigger realista é `/sc onlogon` (roda quando o
  usuário entra), ou o backend **elapsed** (abaixo), que não usa Task
  Scheduler nenhum.
- **Verifique antes de assumir.** Se `schtasks /create` falhar com
  `0x80070005`, a política do ambiente bloqueia tarefas — use o comando
  manualmente ou o subcomando `install` da própria ferramenta (que seleciona
  `elapsed` quando Task Scheduler e cron estão ausentes).

Backend elapsed (sem agendador do SO — dispara quando o Devin recebe prompt):

```powershell
python <CAMINHO_DO_REPO>\devin-powerups\tools\schedule.py install devin-backup "devin-backup create --out %USERPROFILE%\backups" --daily --backend elapsed
```

O registro fica em `<config-dir>/.devin-ecosystem/scheduled.json` e o tick
vem de um hook `UserPromptSubmit` que chama `schedule.py check --run`
(`tools/hooks_dispatch.py` despacha o evento). Para `devin-backup` e
`devin-janitor`, `<tool> install` escolhe `elapsed` automaticamente quando
não há Task Scheduler nem cron.

### 1.4 Registro de jobs (independente do backend)

Todos os backends gravam `<config-dir>/.devin-ecosystem/scheduled.json`
(nome, comando, `interval_h`, `installed_at`, `last_run`). O diretório de
config resolve por `DEVIN_CONFIG_DIR` → `%APPDATA%\Devin` (Windows) →
`~/Library/Application Support/Devin` (macOS) →
`${XDG_CONFIG_HOME:-~/.config}/Devin` (Linux). Em cron, a linha carrega a
tag `# devin-ecosystem:<nome>`; no Task Scheduler, o nome é `devin-<nome>`.

---

## 2. Camada CI — GitHub Actions com `schedule:` (awareness)

Estes jobs rodam no GitHub; não precisam (e não devem) ser recriados na
máquina do usuário. Listados para que um agente novo saiba que automação
existe e onde vive. Horários em UTC.

### devin-powerups (`.github/workflows/`)

| Job | Cron | O que faz |
|---|---|---|
| `registry-refresh` | `33 7 * * 1` (seg) | `refresh_devkit_refs.py` avança pins do devkit; commita `registry.json` |
| `registry-drift` | `41 5 * * 0` (dom) + push | valida registry + regenera superfícies (`--check`) incl. banners DIST-STATUS |
| `contract-check` | `17 6 * * 1` (seg) | exercita `devin-inspect contract` em fixtures sintéticos |
| `baseline-snapshot` | `15 8 * * 1` (seg) + `15 8 3 12 *` | P5: `snapshot_baseline.py` + `fork_visibility.py` → `snapshots/`; no-op após 2026-12-03 (window guard) |
| `weekly-repo-report` | `0 7 * * 0` (dom) | relatório HTML; email MailerSend opcional via secrets |
| `scorecard` / `codeql` | sáb / sex | OpenSSF Scorecard / CodeQL |

### Outros repos

| Repo | Jobs agendados |
|---|---|
| `devin-devkit` | `manifest-sync` ter 07:44 (re-exporta manifest do registry); scorecard |
| `devin-state` | fuzz (ClusterFuzzLite) seg 04:40; codeql sex; scorecard sáb |
| `devin-assure` | fuzz seg; codeql sex; scorecard sáb |
| `devin-explore`/`devin-control`/`devin-brain`/`devin-internals-spec`/`devin-judge` | codeql sex; scorecard sáb; fuzz seg (internals-spec, judge) |
| `awesome-devin` | `links.yml` seg 05:17 (lychee link-check); scorecard |
| Dependabot | `interval: weekly` na maioria dos repos (`pip` + `github-actions`) |

A camada de automação **pessoal** do mantenedor (crontab do laptop, systemd
--user, PM2 na VM, hooks Devin) fica fora dos repos públicos — está
inventariada em `docs/audits/2026-10-10/AUTOMATION-CATALOG.md` (projeção
sanitizada) e, em detalhe, no PAS privado. Não replica segredos nem caminhos
de máquina aqui.

---

## 3. Referências cruzadas

- `tools/schedule.py` — CLI de agendamento multi-backend (F6).
- `devin-state/shared/install-scheduler` — biblioteca consumida por
  `devin-backup install` / `devin-janitor install`.
- `docs/capability-profile.md` — por que `scheduler` é `off` no perfil
  corporate (e `elapsed` é o fallback).
- `tools/migrate_platform_docs.py` (`_RECURRING_JOBS`) — fonte das seções
  "Recurring runs" dos READMEs de plataforma; cadências deste doc e daquelas
  devem convergir.
- `docs/audits/2026-10-10/AUTOMATION-CATALOG.md` — inventário completo da
  camada de máquina do mantenedor (sanitizado).
