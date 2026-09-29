# devin-powerups (hub)

> **Projeto comunitário não oficial.** Sem afiliação, endosso ou patrocínio da
> Cognition AI. "Devin" é marca registada da Cognition AI.

**[English](README.md)** · Português (BR)

Hub do maintainer para o ecossistema `devin-*`: índice, roadmap, CI
reutilizável e o template de repos. **Este repo é infraestrutura do
maintainer — os projetos virados ao utilizador vivem nos seus repos públicos.**

## O que está aqui

| Caminho | Propósito |
|---|---|
| `registry.json` | Índice consumível por máquina de todos os repos `devin-*` |
| `.github/workflows/` | Workflows reutilizáveis (`python-test`, `redact-check`) chamados por cada repo de projeto |
| `template/` | Esqueleto de onde nasce cada repo novo |
| `tools/new-repo.py` | Scaffolder: `python tools/new-repo.py <nome> "<desc>"` |

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
| **0 — Fundação** | `devin-internals-spec` · `devin-redact` | 🔨 M1 feito |
| **1 — Adoção** | `devin-history` · `devin-doctor` · `devin-pm` | ⏳ |
| **2 — Diferencial** | `devin-qa-pack` · `devin-learning` · `devin-metrics` · `devin-backup` | ⏳ |
| **3 — Ampliação** | `devin-search` · `devin-graph` · `devin-evals` · `devin-dashboard` | ⏳ |
| **4 — Pesquisa** | `devin-memory` (anti-poisoning) · `devin-bridge` · Jevin | ⏳ |

## Convenções

- Docs bilingues: `README.md` (EN, canónico) + `README.pt-BR.md`.
- MIT + aviso de não-oficial em todos os READMEs públicos.
- A lógica vive na biblioteca; CLI/MCP/skill/plugin são wrappers finos.
- Nenhum repo depende de outro, exceto a biblioteca `devin-internals`.
- Sem telemetria, sem rede por omissão.

## Maintainer

Mantido por **Devin** (o agente), orquestrado por
[@Icaro0310](https://github.com/Icaro0310). O trabalho corre em uma sessão
Devin dedicada por repositório (despachada via ACP).

## Licença

MIT — vê [LICENSE](LICENSE).
