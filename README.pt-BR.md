# devin-powerups (hub)

> **Projeto comunitário não oficial.** Sem afiliação, endosso ou patrocínio da
> Cognition AI. "Devin" é marca registada da Cognition AI.

**[English](README.md)** · Português (BR)

Hub privado do maintainer para o ecossistema `devin-*`: registry, roadmap,
template e scaffolder. Os projetos públicos vivem em repos próprios e cada um
agora contém o seu workflow de CI inline.

## O que está aqui

| Caminho | Propósito |
|---|---|
| `registry.json` | Índice consumível por máquina de todos os repos `devin-*` |
| `.github/workflows/` | Workflows reutilizáveis antigos, mantidos como referência, mais `weekly-repo-report.yml` (abaixo); os projetos usam CI inline |
| `template/` | Esqueleto de onde nasce cada repo novo |
| `tools/new-repo.py` | Scaffolder: `python tools/new-repo.py <nome> "<desc>"` |
| `tools/weekly_repo_report.py` | Relatório semanal de atividade dos projetos públicos → HTML (stdlib, API pública do GitHub) |

## O método

Cada projeto adapta uma ferramenta existente **mais** um extra Devin que tem
de passar três testes: faz algo que a base *não consegue de todo* · o extra
desaparece sem o Devin · explicável numa frase.

## Os 10 superpoderes do Devin

`S1` store relacional de sessões · `S2` três superfícies (cloud+CLI+Desktop) ·
`S3` hooks (`PermissionRequest`, `PostToolUse`, `PostCompaction`) ·
`S4` `permissions.allow/deny/ask` · `S5` frontmatter rico de skills ·
`S6` subagents locais · `S7` plugins/governança de marketplace · `S8` sessões
Cloud API · `S9` sessões recuperáveis · `S10` schema versionado.

## Vagas

| Vaga | Projetos | Estado |
|---|---|---|
| **0 — Fundação** | `devin-internals-spec` · `devin-redact` | Entregue · 56 testes |
| **1 — Adoção** | `devin-history` · `devin-doctor` · `devin-pm` | Entregue · 150 testes |
| **2 — Diferencial** | `devin-qa-pack` · `devin-metrics` · `devin-backup` | Entregue |
| **3 — Ampliação** | `devin-search` · `devin-graph` · `devin-evals` · `devin-metrics` (absorveu `devin-dashboard`) | Entregue |
| **4 — Pesquisa** | `devin-memory` · `devin-bridge` · Djævin | Projetos entregues · 126 testes; pesquisa Djævin pendente |
| **5 — Lifecycle** | `devin-janitor` | Entregue · 54 testes |

### Consolidação (2026-09-30)

Projetos dependentes/duplicados foram unificados:

- `devin-dashboard` → fundido em `devin-metrics` v0.2 (subpacote `devin_metrics.dashboard`,
  subcomando `devin-metrics dashboard`, alias `devin-dashboard`). Repo apagado.
- `devin-learning` → fundido em `devin-memory` v0.2 (subpacote `devin_memory.learning`,
  alias `devin-learning`, dependência `devin-redact`). Repo apagado.
- `devin-subagent-orchestrator` (rascunho local não publicado) → fundido em
  `devin-orchestrator` v0.2.

### Instalação (sem PyPI ainda)

Todo projeto público instala direto do GitHub — as dependências `devin-* @ git+https://…`
resolvem automaticamente:

```bash
pip install "git+https://github.com/Icaro0310/devin-metrics.git"
```

Publicação PyPI/npm pendente de credenciais; até lá, instalação via git é o caminho suportado.

## Estado do CI

Em 2026-09-30, as execuções mais recentes do GitHub Actions passaram nos 15
repos de projeto. Projetos Python testam em Windows e Ubuntu; `devin-bridge`
testa Node 22 e 24 nos dois sistemas. O CI é inline porque repos públicos não
conseguem depender com confiabilidade de workflows reutilizáveis neste hub
privado. O secrets-scan inclui o código de testes e exclui `.git`, `fixtures/`
e `node_modules/`; corpora sintéticos ficam intencionalmente em `fixtures/`.

## Relatório semanal de repos

O `weekly-repo-report.yml` corre aos domingos às 07:00 UTC (04:00 Brasília) (e via
`workflow_dispatch`): o `tools/weekly_repo_report.py` consulta a API pública
de commits do GitHub para os últimos 7 dias nos 15 repos públicos de projeto
em `registry.json`, gera um relatório HTML autónomo agrupado por repo e dia,
e publica-o como artifact em todas as execuções. Só metadados de repos
públicos são usados — commits do hub privado nunca são incluídos.

O envio por email requer adicionalmente os quatro secrets MailerSend
configurados neste hub privado (`MAILERSEND_SMTP_HOST`, `MAILERSEND_SMTP_PORT`,
`MAILERSEND_SMTP_USER`, `MAILERSEND_SMTP_PASSWORD` — os mesmos nomes de secrets
usados pelo PetSaas). O email é enviado via TLS verificado com o remetente
sandbox trial documentado do PetSaas
(`PetSaas Bot <petsaas@test-z0vklo638kvl7qrx.mlsender.net>`), que é distinto do
login SMTP. Se algum faltar, a execução emite um aviso e deixa apenas o
artifact HTML.

## Scout semanal do ecossistema

O `DevinWeeklyEcosystemScout` (Task Scheduler, domingos 06:30 local) corre o
`scripts/weekly-ecosystem-scout.mjs` no workspace `personal-agent-system`:

1. **Scout** — `gh search repos` sobre queries do ecossistema de agentes
   (mcp-server, agent-client-protocol, devin agent, claude code, coding agent
   cli, agent skill), ordenado por estrelas; o top alimenta ideias de projetos.
2. **E2E** — corre a suite de testes de cada repo do registry localmente,
   serial, 3 min por repo. Read-only: testes nunca modificam nem commitam.
3. **Ideation** — despacha para a sessão Devin dedicada deste repo
   (`devin-repo-task.js --resume-only`), que escreve
   `reports/scout-<data>-proposals.md`: exatamente 3 propostas de features por
   repo mais até 5 ideias de projetos novos vindas das trends.
4. **Deliver** — DM no Slack + email MailerSend com o resumo, issue
   `e2e-failure` em qualquer repo que falhou, e commit+push do relatório.

Propostas são propostas: nada é implementado sem aprovação do maintainer.
Trabalho aprovado retoma a sessão mapeada do repo em `.sessions.json` — nunca
uma duplicada. Fail-open em tudo; a execução sai com código não-zero se algum
E2E falhar.

## Convenções

- Docs bilingues: `README.md` (EN, canónico) + `README.pt-BR.md`.
- MIT + aviso de não-oficial em todos os READMEs públicos.
- A lógica vive na biblioteca; CLI/MCP/skill/plugin são wrappers finos.
- Dependências partilhadas (`devin-internals-spec`, `devin-redact`) são fixadas por tag; evite ciclos.
- Sem telemetria, sem rede por omissão.

## Maintainer

Mantido por **Devin** (o agente), orquestrado por
[@Icaro0310](https://github.com/Icaro0310). O trabalho corre em uma sessão
Devin dedicada por repositório (despachada via ACP).

## Licença

MIT — vê [LICENSE](LICENSE).
