# devin-powerups

> **Projeto comunitário não oficial.** Sem afiliação, endosso ou patrocínio da
> Cognition AI. "Devin" é marca registada da Cognition AI.

**[English](README.md)** · Português (BR)

O hub de uma coleção de **powerups nativos do Devin Desktop**: ferramentas
que adaptam ideias provadas de outros agentes de código e acrescentam uma
capacidade que só existe porque o Devin expõe primitivos que mais ninguém
tem (store relacional de sessões, hooks de permissão, frontmatter de skills,
subagents, stores do Desktop GUI, Cloud API).

Este repo é o **índice, roadmap e registry** — não um monorepo de código.
Cada powerup vive no seu próprio repositório, criado just-in-time.

## O método

Cada projeto adapta uma ferramenta existente **mais** um extra Devin. O extra
tem de passar três testes:

1. **Lado a lado** — faz algo que a ferramenta-base *não consegue de todo*?
2. **Sem Devin** — o extra desaparece se o Devin sair da equação?
3. **Uma frase** — consegues explicá-lo sem jargão?

## Os 10 superpoderes do Devin em que construímos

`S1` store relacional de sessões (status de tool, `locations`, tokens reais,
ACU) · `S2` três superfícies (cloud + CLI + Desktop) · `S3` hooks
(`PermissionRequest`, `PreToolUse`, `PostToolUse`, `PostCompaction`) ·
`S4` `permissions.allow/deny/ask` · `S5` frontmatter rico de skills (`model`,
`allowed-tools`, `triggers`, `subagent`) · `S6` subagents locais · `S7`
plugins + governança de marketplace · `S8` sessões Cloud API · `S9` sessões
recuperáveis (locks + logs sobrevivem ao pruning) · `S10` schema versionado
(`refinery_schema_history`).

## Vagas

| Vaga | Projetos | Estado |
|---|---|---|
| **0 — Fundação** | `devin-internals-spec` · `devin-redact` | 🔨 em curso |
| **1 — Adoção** | `devin-history` · `devin-doctor` · `devin-pm` | ⏳ |
| **2 — Diferencial** | `devin-qa-pack` · `devin-learning` · `devin-metrics` · `devin-backup` | ⏳ |
| **3 — Ampliação** | `devin-search` · `devin-graph` · `devin-evals` · `devin-dashboard` | ⏳ |
| **4 — Pesquisa** | `devin-memory` (anti-poisoning) · `devin-bridge` · Jevin | ⏳ |

## Registry de repositórios

Índice consumível por máquina: [`registry.json`](registry.json).

| Repo | Propósito | Vaga |
|---|---|---|
| [`devin-repo-template`](https://github.com/Icaro0310/devin-repo-template) | Template de onde nasce cada repo | infra |
| [`devin-ci`](https://github.com/Icaro0310/devin-ci) | Workflows reutilizáveis de GitHub Actions | infra |
| `devin-powerups` | Este hub — índice + roadmap + registry | infra |

## Convenções

- **Docs bilingues**: `README.md` (EN, canónico) + `README.pt-BR.md`.
- Licença **MIT**, com o aviso de não-oficial em todos os READMEs.
- **Regra de arquitetura**: a lógica vive na biblioteca; CLI/MCP/skill/plugin
  são wrappers finos.
- **Nenhum repo depende de outro**, exceto `devin-internals` (a biblioteca de
  parsing, fonte de verdade do schema).
- **Sem telemetria, sem rede por omissão**, em qualquer projeto.

## Maintainer

Mantido por **Devin** (o agente), orquestrado por
[@Icaro0310](https://github.com/Icaro0310). Reports do que foi
feito/alterado/commitado são produzidos por marco.

## Licença

MIT — vê [LICENSE](LICENSE).
