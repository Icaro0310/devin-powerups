# Evidence Equivalence Study

**Data:** 2026-10-09 → 2026-10-11
**Autor:** Devin
**Estado:** investigação concluída

> Pre-milestone gate: the official-API adapter may only be scheduled after
> this investigation proves (or disproves) that the official surfaces carry
> evidence equivalent to the local stores. Verdict below.

## Sumário executivo

Veredicto global: **parcial**, com cobertura oficial mais larga do que
esperado. O MCP expõe um event stream verificado ao vivo funcionalmente
equivalente à evidência local para tool calls (comando, output integral
em base64, exit code, timestamps, ordering) — e mais rico em pontos
(`chain[]` com operações de ficheiro, timestamps por evento). A REST API
v3 é metadata + narrativa apenas (sem tool calls). `devin --export`
(ATIF) e o SDK TS `@cognition-ai/sdk` expõem tool calls + tokens + modelo
oficialmente — superfícies novas vs o estudo de outubro. Stores locais
seguem insubstituíveis para raw ACP, `working_directory` e branching;
cache/cascade/approvals granulares não existem em lado nenhum. Um adapter
MCP para "sessões cloud" é viável e já tem prova de conceito
(`devin-qa-pack`); a baseline local permanece.

## Metodologia

Investigação em três vagas, todas read-only:

1. **Leg local (2026-10-09):** inspeção direta dos stores SQLite —
   `sessions.db` (schema v17, 9 tabelas, N=10 sessões amostradas em
   `docs/evidence-equivalence/local-fixture-n10.json`), `acp-messages/*.db`,
   `state.vscdb`. Schemas confirmados por `sqlite_master` + `PRAGMA
   table_info`; conteúdo de linhas nunca publicado.
2. **Discovery não autenticado (2026-10-09):** `tools/list` no MCP público,
   `api.devin.ai` sem credencial (403 confirmado), OpenAPI publicado.
3. **Verificação autenticada (2026-10-06 e 2026-10-11):** o estudo de
   referência em `devin-internals-spec/docs/EVIDENCE-EQUIVALENCE.md` já
   tinha criado duas sessões-probe taggeadas `evidence-study` e documentado
   GETs na API v3 com PAT de teste. Hoje (2026-10-11) foram repetidos —
   com o mesmo PAT, GETs apenas — `tools/list` MCP (25 tools, schema de
   `devin_session_events`), `GET /v3/self`, `GET
   /v3/organizations/{org}/sessions` (4 sessões), `devin_session_events`
   `action=list` nas duas probes arquivadas e `action=details` em 3 eventos
   shell. Nenhuma sessão nova criada; nenhuma escrita; nenhum dado de
   produção de terceiros lido.

Fontes primárias por afirmação em §6. Onde a evidência não cobre, o campo
está marcado `unverified` — não inventado.

## 1. Inventário local (baseline)

Stores verificados nesta máquina (Linux; equivalente Windows documentado em
`devin-internals-spec/docs/SCHEMA.md`):

| Store | Path | Conteúdo | Verificado |
|---|---|---|---|
| `sessions.db` v17 | `~/.local/share/devin/cli/sessions.db` | 9 tabelas, 97 sessões, 529k `message_nodes`, 30k `tool_call_state` | hoje, direto |
| `acp-messages/*.db` | `~/.config/Devin/User/acp-messages/` | 47 DBs por sessão GUI; `meta` + `messages(position,kind,payload)`; kinds: `tool_call`, `agent_thought`, `agent_message`, `user_message` | hoje, direto |
| `state.vscdb` | `~/.config/Devin/User/globalStorage/` | KV VS Code-style, 990 itens; chaves `windsurf.acp.messageStore.session.acp/devin-cli/*` | hoje, direto |
| `memory/memories.jsonl` | `~/.config/Devin/memory/` | memória persistente | presente |
| `plugins/discovered.json` | `~/.local/share/devin/cli/plugins/` | manifestos de plugins instalados | presente |
| `summaries/`, `logs/`, `session_locks/`, `skill_events_spool.lock` | `~/.config/Devin/` + `~/.local/share/devin/cli/` | artefactos auxiliares | presente |

Campos consumidos pelo ecossistema (fonte: `SCHEMA.md` + fixture N=10):

| # | Campo | Onde vive | Formato | Consumidor |
|---|---|---|---|---|
| 1 | Session ID | `sessions.id` | TEXT UUID | todos |
| 2 | Mensagens | `message_nodes.chat_message` (role/content), acp `messages` | JSON opaco | explore, qa-pack, history-export |
| 3 | Tool invocation | `tool_call_state.tool_call_json` | ACP `ToolCall` | qa-pack, judge |
| 4 | Tool name | `tool_call_json.kind`/`title` | ACP kinds: `execute`,`edit`,`read`,`search`,`fetch` | qa-pack |
| 5 | Tool args | `tool_call_json.rawInput`, `locations[].path` | JSON | qa-pack |
| 6 | Tool result | `tool_call_update_json` content | ACP `ToolCallUpdate` | qa-pack |
| 7 | Exit code | `tool_call_update_json._meta.terminal_exit.exit_code` | int | qa-pack |
| 8 | Timestamps | `message_nodes.created_at` (ms), `sessions.created_at`/`last_activity_at` | epoch ms | metrics, doctor |
| 9 | Ordering | `node_id`/`parent_node_id` forest; **sem seq em `tool_call_state`** | — | explore |
| 10 | Final state | derivado (`last_activity`, `hidden`, locks) | — | state, doctor |
| 11 | Metadata | `model`, `agent_mode`, `backend_type`, `working_directory`, `workspace_dirs`, `cogs_json` (unreliable), `metadata.num_tokens_preceding` | misto | doctor, metrics |
| 12 | Sub-agent | `subagent_heads` (tabela morta: 0 linhas em 97 sessões) | — | ninguém (dead) |

A unidade de equivalência do ecossistema é o `ParsedToolCall` do qa-pack:
`{kind, commands, status, search_text, http_statuses}` dentro de um
`SourceSession{source, session_id, title, working_directory, claims, calls,
raw_call_count}` — `raw_call_count` preserva a distinção
vazio-vs-ilegível (ground truth unreadable → `unverifiable`, nunca
`disputed`).

## 2. Superfícies oficiais

### 2.1 API v3

Base `https://api.devin.ai/v3`, org-scoped. Verificado hoje com PAT:

- `GET /v3/self` → principal/org ids (funciona).
- `GET /v3/organizations/{org}/sessions?qs={json}` → lista; `qs` é um
  `SessionsQueryParams` JSON **obrigatório**. 4 sessões, incl. as 2 probes.
- `GET .../sessions/{devin_id}` → `SessionResponse`: `status`,
  `status_detail`, `title`, `url`, `is_archived`, `created_at`,
  `updated_at`, `acus_consumed`, `devin_mode` (enum inclui `swe-2-*` —
  carrega a família do modelo), `origin`, `parent_session_id`,
  `child_session_ids`, `pull_requests`, `structured_output`, `tags`,
  `security_profile`, `playbook_id`, `automation_id`, `category`,
  `subcategory`.
- `GET .../sessions/{devin_id}/messages` → narrativa flat
  (`event_id`, `source`, `message`, `created_at`, `username`).
- `GET .../sessions/{devin_id}/attachments` existe; conteúdo não amostrado.
- Enterprise: `consumption/daily/sessions/{id}`, `metrics/sessions`,
  `audit-logs`, `sessions/insights` — enumerados na spec, não testados.

**Não existe** endpoint de tool calls nem de eventos granulares na v3
(o SDK REST de events devolveu 404 no estudo de outubro — MCP-only ou
unshipped). OpenAPI: `docs.devin.ai/{v1,v2,v3}-openapi.yaml`.

### 2.2 MCP

`https://mcp.devin.ai/mcp` (JSON-RPC sobre SSE). `tools/list` é público sem
auth; invocação exige o PAT. **25 tools** hoje (24 em 2026-10-06):
`devin_session_create/events/interact/search/insights/gather`,
`devin_review_manage`, manages de automation/knowledge/playbook/schedule/
oncall/campaign/blueprint/code-scan/billing-tag/mcp-server, `devin_user_list`,
`devin_find_setting`, `devin_list_integrations`, e 4 tools wiki
(`ask_wiki_question`, `generate_wiki`, `list_wiki_repos`,
`read_wiki_contents/structure`).

`devin_session_events` — verificado ao vivo nas probes arquivadas:

- `action`: `list` | `details` | `search`. `list`/`search` paginam
  (`first`≤100, cursor `after`, `has_next_page`), filtram por
  `event_types`, `categories` (enum público de **16**: shell, file, search,
  browser, mcp, git, message, status, secret, todo, recording, knowledge,
  playbook, webhook, lifecycle, other), `direction`, janela
  `created_after/before`. `details` devolve `contents` JSON completo de até
  20 `event_ids` — **novo vs outubro**, fecha o gap de truncamento.
- Shapes observados ao vivo (`action=details`):
  - `shell_process_started.contents`: `command` integral + `chain[]` por
    sub-comando (`command`, `certainly_ran`, `operation:{kind,paths}` para
    I/O de ficheiro), `shell_id`, `process_id`, `starting_dir`,
    `is_major_action`, `timestamp` ISO.
  - `terminal_update.contents.contents`: **base64 do output integral**
    (não truncado) — stitching recupera output completo; fecha o gap
    `output_trunc` do estudo de outubro.
  - `shell_process_completed.contents`: `exit_code` (**string**, `"0"`),
    `output_trunc` (cauda truncada), `process_id`, `timestamp`.
- Tipos observados nas 2 probes (41/40 eventos cada): `initial_user_message`,
  `devin_message`, `devin_thoughts`, `one_line_thoughts`,
  `shell_process_started/completed`, `terminal_update`, `status_update`,
  `initialized`, `repo_setup_initialized`, `plugins_activated`,
  `is_typing`, `live_chain_update`, `context_growth_update`,
  `iteration_stats`, `iteration_checkpoint`, `simple_activity_update`,
  `shared_file_updated`, `acu_consumption_at_last_user_interaction`,
  `first_session_message`, `archive`, `session_snapshot`,
  `checkpoint_created`, `session_analysis`, `devin_suspended` (~26 tipos).
- A listagem sai como **texto renderizado** (`[event-id] ts <<< type
  (category): preview truncado`), não JSON — o parse da lista é
  frágil/derivado; `details` devolve JSON estruturado. Eventos `<<<` são
  incoming (user/lifecycle), `>>>` outgoing (agente).

### 2.3 Plugins / Skills oficiais

Superfície de **extensibilidade**, não de evidência: plugins
(`.devin-plugin/plugin.json` + skills/rules/hooks/MCPs/subagents) são a
camada de customização partilhada entre cloud sessions, CLI e Desktop
(`docs.devin.ai/cli/extensibility/plugins`, `product-guides/plugins`).
O store de plugins do CLI vive em `~/.local/share/devin/cli/plugins/`
(`discovered.json` — verificado hoje). `plugins_activated` é o vestígio no
event stream; `PreToolUse` hooks recebem `tool_provenance` (skill/MCP de
origem — changelog v3000.10.21). Nenhuma superfície de plugins expõe
evidência de sessão — gap é de natureza, não de implementação.

### 2.4 Outras

- **Devin CLI** (`docs.devin.ai/cli`): produz a baseline local, mas também
  **expõe evidência oficial por cima dela**:
  - `devin --export [PATH]` — exporta a conversação após cada turno em
    formato ATIF (Agent Trajectory Interchange Format): por step,
    `tool_calls[].function_name`, `observation.results[]`, métricas
    `prompt_tokens`/`completion_tokens`/`cache_*`, `generation_model`,
    `session_id`, `final_metrics` (help local confirmado; formato por
    docs/changelog). **O export local oficial mais rico.**
  - `devin list --format json|csv` — lista de sessões machine-readable.
  - **OTEL export** (v3000.11.1): eventos+métricas do agente para um
    collector OpenTelemetry via `otel` block / `OTEL_EXPORTER_OTLP_*` —
    superfície de telemetria oficial, não testada.
  - `devin --cloud`, `devin ssh <session>`, `/handoff`/`/pickup` —
    interação com sessões cloud (operacional, não evidência).
- **Devin Desktop** (fork Windsurf): produz `acp-messages`, `state.vscdb`,
  `memory/`, `summaries/` — baseline, não superfície nova.
- **VS Code**: extensão oficial `CognitionAI/devin-extension` — lista de
  sessões, chat, diffs globais/por-ficheiro read-only, Remote-SSH para a VM
  da sessão, archive. UI sobre a API; não expõe transcripts/tool logs.
- **SDK TypeScript `@cognition-ai/sdk`** (npm, `beta` tag, 0.0.1-beta.7 —
  verificado hoje): `session.events()` stream **tipado** com tool calls
  normalizados (`detail` com command/exit_code/path), `status`, `activity`,
  `message_delta`, `pull_request`. Cloud sessions via ACP WebSocket;
  locais spawn do CLI. **Cobre per-tool-call — mais rico que REST.**
  Companions: `@cognition-ai/harness-devin`, `devin-sdk-cli-*` binaries.
- **SDK `devinai`** (PyPI 0.1.0): **provavelmente não-oficial** — aponta
  para `github.com/usacognition/devin-sdk-python`, fora da org
  CognitionAI. O estudo de outubro tratou-o como oficial; corrigido aqui.
- **API interna não documentada**: `api.devin.ai/docs` (FastAPI Swagger)
  expõe endpoints fora da v3 — `terminal_contents/`, `editor_files/`,
  `images/` com presigned URLs, `upload-attachment`. Evidence-bearing mas
  **interna/não suportada** — registada, não contada como superfície oficial.
- **Enterprise audit-logs** (`/v3/enterprise/audit-logs`): eventos de ação
  (`create_session`, `send_message`, `expose_port`,
  `authorize_ssh_access`, `ai_guardrail_violation`…) — prova que ações
  ocorreram, sem conteúdo. Não testado (tier).
- **Enterprise insights** (`/v3/enterprise/sessions/{id}/insights`):
  análise gerada — `timeline[]`, `classification.tools_and_frameworks`,
  `skill_usage`, `note_usage`. Parcial para evidência de tools.
- **`devin_review_manage`** (MCP): `get_findings` expõe findings do Devin
  Review programaticamente — evidência de review, não de sessão.

## 3. Comparação campo-por-campo

`✅` equivalente · `⚠️` parcial (existe com perda) · `❌` ausente ·
`?` não verificável · `+` mais rico que local

| # | Campo | Local (stores) | API v3 | MCP | CLI export / SDK TS | Veredicto |
|---|---|---|---|---|---|---|
| 1 | Session ID | `sessions.id` | `session_id`/`devin_id` ✅ | `session_id` (`devin-` prefix) ✅ | `session_id` ATIF ✅ | **equivalente** |
| 2 | Mensagens | forest `message_nodes` (role+content+branching) | `messages` flat narrative ⚠️ | `devin_message`, `initial_user_message` ✅ | ATIF steps ✅ | **equivalente*** (linear; branching é local-only) |
| 3 | Tool invocation | `tool_call_state` (30k calls) | ❌ | `shell_process_*`, `*_update` por categoria ✅ | ATIF `tool_calls[]` ✅, SDK `events()` typed ✅ | **equivalente** (MCP/SDK/ATIF) |
| 4 | Tool name | `kind` ACP | ❌ | `event_type`/`category` ✅ | ATIF `function_name` ✅ | **equivalente** |
| 5 | Tool args | `rawInput` integral | ❌ | `contents.command`+`chain[]` (shell) ✅; outras categorias `?` | ATIF args + SDK `detail` ✅ | **equivalente** |
| 6 | Tool result | `tool_call_update_json` | ❌ | `terminal_update` base64 integral + `output_trunc` + | ATIF `observation.results[]` ✅ | **equivalente** |
| 7 | Exit code | `_meta.terminal_exit.exit_code` int | ❌ | `exit_code` **string** + | ATIF/SDK normalized ✅ | **equivalente** (normalização de tipo) |
| 8 | Timestamps | por-nó ms; tool_call_state **sem ts** | `created_at`/`updated_at` sessão | por-evento `created_at` + `contents.timestamp` **+** | ATIF `metadata.created_at` ✅ | **equivalente** |
| 9 | Ordering | forest + `created_at`; tool calls sem seq | ordem implícita `messages` | stream cronológico paginado + | ATIF step order ✅ | **equivalente** |
| 10 | Final state | derivado de locks/activity | `status`/`status_detail` autoritativo **+** | `status_update`, `devin_suspended` + | `final_metrics` ATIF ⚠️ | **equivalente** (cloud autoritativo) |
| 11 | Metadata sessão | `model`✅, `agent_mode`✅, `wd`✅, `cogs_json`⚠️ unreliable, `num_tokens_preceding`⚠️ | `devin_mode` (enum incl. `swe-2-*` → família de modelo), `acus_consumed`, `origin`, `pull_requests`, `tags`, `category` ⚠️ | idem via `interact get`/`insights` ⚠️ | ATIF: `generation_model`, `prompt/completion/cache_*` tokens, `final_metrics` **+** | **parcial** — tokens/model granular só via ATIF; `working_directory` local-only |
| 12 | Sub-agent calls | `subagent_heads` morta (0/97); PAS próprios | `parent_session_id`/`child_session_ids` + | idem + | trays/ACP subagent (changelog) ⚠️ | **cloud-only** |
| 13 | File edits (path+diff) | `edit` kind + `rawInput`/`locations` ✅ | ❌ | `chain[].operation{kind,paths}` via shell ✅; categoria `file` existe, shape `?` | ATIF `observation.results` + SDK `detail.path` ⚠️ | **parcial** |
| 14 | Bash + stdout/stderr | integral | ❌ | `command` + output base64 integral + | ATIF `tool_calls`+`results` ✅ | **equivalente** |
| 15 | Erros/warnings | `status` em updates | `status_detail` ⚠️ | `status_update`, `session_analysis` ⚠️ | ATIF results ⚠️ | **parcial** |
| 16 | Cache hits/misses | ❌ não registado nos stores | ❌ | ❌ | ATIF `metrics.cache_*` ✅ | **parcial** — só via `--export` |
| 17 | Cascade rules aplicadas | regras são config local; aplicação não registada | ❌ | `plugins_activated` (nome apenas) ⚠️ | `tool_provenance` em hooks ⚠️ | **parcial→ausente** |
| 18 | Permissions/approvals | rows `permission` em updates + `agent_mode` | `status_detail=waiting_for_approval` ⚠️ | idem ⚠️ | hooks `.devin` locais ⚠️ | **parcial** |

## 4. Análise de gaps

| Gap | Descrição | Impacto | Mitigação (hipotética) | Custo |
|---|---|---|---|---|
| **API v3 sem tool calls** | REST expõe narrativa + metadata apenas; granularidade de tool call é MCP/SDK-only | explore/qa-pack não podem operar sobre REST sozinhos | usar MCP/SDK para evidência; REST para enriquecimento (ACU, PRs, tags) | já coberto pelo adapter MCP existente |
| **Shapes não-shell MCP** | `file`, `git`, `browser`, `mcp`, `secret`, `recording` enumerados como categorias mas `contents` nunca observados ao vivo (probes só usaram shell) | verificação de edits/git/browser degrada para `unverified` | probe dedicado que exercite editor/browser/git numa sessão sintética | ~1h + ACU mínimo |
| **Lista MCP é texto, não JSON** | `action=list` devolve markdown renderizado com previews truncados; só `details` dá JSON | parser frágil; previews cortam comando/output | pedir `details` por `event_id` (≤20/call) ou `search` | baixo (pattern já existe no adapter) |
| **`working_directory` local-only** | nenhuma superfície cloud expõe o cwd (`starting_dir` do MCP é o VM cloud `/home/ubuntu`, não a máquina do utilizador) | produtos que verificam contra disco/git local não aplicam na nuvem | por natureza — não há equivalência possível | unresolvable |
| **Tokens/model granular** | `SessionResponse` dá `devin_mode` (família) e `acus_consumed`, não tokens nem nome exato do modelo; `cogs_json` local não é fiável | metrics perde precisão de custo por turno | ATIF `--export` expõe `generation_model` + tokens por step — cobertura local oficial | baixo (consumir o export) |
| **Sub-agent** | `subagent_heads` local está morta (0/97); cloud expõe `child_session_ids` — cobertura cloud melhor que local | campo local sem evidência real | usar `parent/child_session_ids` da API | baixo |
| **Cache / cascade rules / approvals por-evento** | cache só em ATIF `metrics.cache_*`; rules só `plugins_activated`/`tool_provenance`; approvals só como `status_detail` | campos 16-18 parciais, sem granularidade por-evento | aceitar como `unverified` | n/a |
| **Formato `contents` por tipo** | ~26 tipos observados, ~90 estimados; payloads variam | cada tipo novo exige mapper | `details` devolve JSON — mapear incrementalmente | incremental |
| **Rate limits / paginação grande** | não medidos | sessões longas podem paginar muito | `first`≤100 + cursor; filtrar por `categories` | baixo |
| **API interna `api.devin.ai/docs`** | terminal_contents/editor_files/images via presigned URLs existem mas são internas/não documentadas | poderiam cobrir artefactos ricos; não contáveis como superfície oficial | documentar como gap de suporte; não construir sobre ela | n/a |

## 5. Recomendação

**Veredicto global: `adapter-partial`** — e a cobertura é mais larga do
que o estudo de outubro sugeria.

- **Viável:** adapter MCP como fonte de evidência para **sessões cloud**
  cobrindo o núcleo de verificação (campos 1-10, 14): session id, mensagens
  lineares, tool invocation/args/result/exit code/timestamps/ordering/estado
  final, bash+output. Prova de conceito já existe em
  `devin-qa-pack/adapters/mcp.py` (auditoria PASS sobre a probe de
  outubro). Combinado com REST v3 para metadata (ACU, PRs, tags,
  `child_session_ids`, `devin_mode`), a cobertura sobe para ~14/18 campos.
- **Também viável, local:** `devin --export` (ATIF) é uma superfície
  oficial que cobre tool calls + resultados + tokens + modelo por step —
  mais limpa que ler SQLite bruto, se o formato for estável. SDK TS beta
  cobre o mesmo espaço para integrações programáticas.
- **Não viável / não vale a pena:** substituir os stores locais como
  baseline **local** — continuam a ser a única fonte de raw ACP,
  `working_directory` real, forest branching e KV Windsurf, e não exigem
  credencial nem rede. REST-only é insuficiente para verificação. Cache,
  cascade rules e approvals por-evento ficam `unverified` — gap aceite,
  não de implementação.
- **Consequência para o gate:** o adapter milestone pode cobrir o
  subconjunto equivalente; os sinais `local-only` ficam enumerados acima
  (§3). `UNVERIFIED` continua a significar "o registo não resolve", nunca
  "a claim é falsa".

## 6. Fontes

- `devin-internals-spec/docs/SCHEMA.md` — DDL v17 dos três stores
  (verificado de novo hoje: 97 sessões, 47 acp DBs, 990 items vscdb).
- `devin-internals-spec/docs/EVIDENCE-EQUIVALENCE.md` — estudo-mãe
  (2026-10-06): OpenAPI v1-v3, GETs autenticados, probes `evidence-study`,
  mapeamento MCP→`ParsedToolCall`.
- `docs/evidence-equivalence/local-fixture-n10.json` — N=10 sessões
  (4 GUI / 2 CLI / 4 automation), sanitizado.
- OpenAPI: `docs.devin.ai/v1-openapi.yaml`, `/v2-openapi.yaml`,
  `/v3-openapi.yaml` (também `devin.ai/openapi.json|yaml`).
- Docs: `docs.devin.ai/cli`, `docs.devin.ai/cli/reference/commands`,
  `docs.devin.ai/cli/changelog/stable`, `docs.devin.ai/cli/extensibility/
  plugins/*`, `docs.devin.ai/product-guides/plugins`,
  `docs.devin.ai/api-reference/v3/*` (sessions, messages, attachments,
  insights, audit-logs), `docs.devin.ai/work-with-devin/devin-mcp`.
- `github.com/CognitionAI/devin-extension` — extensão VS Code oficial.
- npm `@cognition-ai/sdk` (beta.7), `@cognition-ai/harness-devin`,
  `github.com/COG-GTM/devin-sdk-examples`.
- PyPI `devinai` 0.1.0 — **provavelmente não-oficial** (org
  `usacognition`, não `CognitionAI`).
- `api.devin.ai/docs` — Swagger interno (endpoints fora da v3: presigned
  terminal/editor/images).
- Live (hoje, read-only, PAT de teste): `tools/list` MCP → 25 tools;
  schema `devin_session_events` (actions/categories/filters); `GET /v3/self`;
  `GET /v3/organizations/{org}/sessions?qs={"limit":20}` → 4 sessões;
  `devin_session_events list` × 2 probes arquivadas (40/41 eventos);
  `details` × 3 eventos shell (shapes completos em §2.2); `devin --help`
  (`--export`, `--format json`); npm registry (`@cognition-ai/sdk`).
- `devin-assure/packages/qa-pack/src/devin_qa_pack/adapters/{base,mcp}.py`
  — contrato `SourceSession`/`ParsedToolCall` e implementação MCP prévia
  (evidência, não scope deste estudo).

## 7. Trabalho futuro (hipotético, não plano)

Se autorizado, poder-se-ia: (a) correr uma probe sintética que exercite as
categorias `file`/`git`/`browser`/`mcp`/`secret` para fechar os shapes por
tipo — ~1h + ACU mínimo; (b) medir paginação/rate limits em sessão longa;
(c) verificar `devin --export` numa sessão local real e confirmar o formato
ATIF campo-a-campo (pode cobrir campos 11/16 hoje `parcial`); (d) testar
`session.events()` do `@cognition-ai/sdk` contra uma sessão cloud; (e)
verificar se `/v3/enterprise/audit-logs` e `sessions/insights` cobrem
metadata que o `SessionResponse` omite (gated por tier?); (f) avaliar a
superfície OTEL como fonte de telemetria. Nenhum destes itens muda o
veredicto `adapter-partial` nem a arquitetura: locais e cloud são fontes
complementares, não substituíveis.
