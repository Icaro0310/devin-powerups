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
| `.github/workflows/` | Workflows reutilizáveis antigos, mantidos como referência; os projetos usam CI inline |
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
| **0 — Fundação** | `devin-internals-spec` · `devin-redact` | Entregue · 56 testes |
| **1 — Adoção** | `devin-history` · `devin-doctor` · `devin-pm` | Entregue · 150 testes |
| **2 — Diferencial** | `devin-qa-pack` · `devin-learning` · `devin-metrics` · `devin-backup` | Entregue · 166 testes |
| **3 — Ampliação** | `devin-search` · `devin-graph` · `devin-evals` · `devin-dashboard` | Entregue · 176 testes |
| **4 — Pesquisa** | `devin-memory` · `devin-bridge` · Jevin | Projetos entregues · 126 testes; pesquisa Jevin pendente |
| **5 — Lifecycle** | `devin-janitor` | Entregue · 54 testes |

## Estado do CI

Em 2026-09-30, as execuções mais recentes do GitHub Actions passaram nos 16
repos de projeto. Projetos Python testam em Windows e Ubuntu; `devin-bridge`
testa Node 22 e 24 nos dois sistemas. O CI é inline porque repos públicos não
conseguem depender com confiabilidade de workflows reutilizáveis neste hub
privado. O secrets-scan inclui o código de testes e exclui `.git`, `fixtures/`
e `node_modules/`; corpora sintéticos ficam intencionalmente em `fixtures/`.

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
