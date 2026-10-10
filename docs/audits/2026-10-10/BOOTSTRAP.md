# New-agent bootstrap guide — 2026-10-10

Como um agente novo (Devin ou outro) reconstrói o ambiente pretendido a
partir de um checkout limpo, sem conhecimento pessoal do mantenedor.

## Passo 0 — Identificar o ambiente

| Sinal | Ambiente |
|---|---|
| Linux + pode usar VM QwenPaw/recursos externos | `linux` (extended) |
| Windows + uso pessoal, VM/externos autorizados | `personal_windows` (extended) |
| Windows + restrição corporativa (proxy/Zscaler, sem admin, sem delegação) | `corporate_windows` (local-only) |

O DevKit **nunca infere** corporate pelo SO — um Windows sem flag vira
`personal_windows`. Se há qualquer restrição, passe `--environment
corporate-windows` explicitamente em `install`, `update` e `outdated`.

## Passo 1 — Fonte da verdade

1. `registry.json` (devin-powerups) — canônico: artefatos, ambientes,
   perfis, status de distribuição. Não edite artefatos gerados; a correção
   vai no registry ou no gerador em `tools/`.
2. `devin-devkit` — o instalador. Manifest gerado embutido no pacote.
3. Produtos: devin-explore, devin-assure, devin-state, devin-control,
   devin-judge, devin-brain (+ devin-internals-spec, devin-powerups,
   awesome-devin, qwenpaw-suite opcional). Repos `devin-*` antigos estão
   arquivados com banner MOVED — siga o redirect.

## Passo 2 — Instalar o DevKit

```bash
uv tool install devin-devkit          # PyPI — Linux e Windows
```

Pré-requisitos: `uv` (gerencia o Python), Node ≥20 + npm só se o perfil
incluir `devin-bridge`, `git` só para `devin-skill-catalog`/checkouts manuais.
Corporate: se `uv`/PyPI forem bloqueados, o guia corporate cobre o download
standalone do binário uv e o offline-bundle com `pip download`.

## Passo 3 — Preview e apply

```bash
devin-devkit profiles
devin-devkit install <perfil> --environment <env>          # dry-run SEMPRE
devin-devkit install <perfil> --environment <env> --apply
```

O plano falha fechado: ferramenta sem suporte no ambiente, dependência
externa/delegação em corporate, colisão parcial de comandos ou gerenciador
ausente → `BLOCKED`, nada é instalado. Comandos já no PATH são reportados
`preexisting`, nunca sobrescritos.

## Passo 4 — Rede e proxy (corporate)

- Instalação baixa de `pypi.org`, `files.pythonhosted.org`,
  `registry.npmjs.org`, `github.com`/`codeload.github.com` e
  `raw.githubusercontent.com` — são necessidades de **install-time**,
  documentadas; se bloqueadas, peça allowlist ou use o offline-bundle.
- Proxy: `HTTPS_PROXY`/`HTTP_PROXY` são honrados por uv/pip/npm/git e pelo
  `urllib` dos tools. Inspeção TLS: a CA corporativa entra pela loja de
  sistema (GPO/IT) — `urllib` lê a system store; `uv` aceita
  `SSL_CERT_FILE`; npm aceita `NODE_EXTRA_CA_CERTS`. Nunca desabilite verify.
- Runtime: tools não exigem rede. Exceções opt-in: freshness do devkit
  (desligável com `DEVIN_DEVKIT_OFFLINE=1`), update-check do doctor
  (`DEVIN_DOCTOR_OFFLINE=1`), `--online` do qa-pack, adapters MCP,
  backend ollama do judge.

## Passo 5 — Automação

O DevKit **não cria** jobs agendados. A camada de automação pessoal (hooks
Devin, cron/systemd ou Task Scheduler) é opcional e documentada em
`AUTOMATION-CATALOG.md` desta auditoria — é tooling do ambiente pessoal,
nunca instalar em corporate.

## Passo 6 — Verificar

```bash
devin-devkit list                 # inventário
devin-devkit outdated             # pins remotos vs instalados
devin-doctor check                # diagnóstico do install/ambiente
```

Recuperação: install é por-tool isolado (`uv tool`) — falha num tool não
desfaz os anteriores; reinstale com `uv tool install --force <spec>` ou
desinstale com `uv tool uninstall <pkg>`. Não há rollback global; o plano
dry-run é a fonte para repetir.

## Passo 7 — Limites honestos

- Corporate Windows atrás de Zscaler: **não testado** — rode o plano de
  teste em `REPORT.md` §Zscaler na máquina real antes de declarar pronto.
- macOS: planejado, não suportado.
- `devin-office` é manual/source-only; `qwenpaw-suite` não entra em perfis
  corporate.
