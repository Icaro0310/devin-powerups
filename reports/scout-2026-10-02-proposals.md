# Ecosystem scout 2026-10-02

## Novos projetos (trends)

- **devin-roles** — inspirado por garrytan/gstack (★134748) — conjunto opinativo de personas subagent (QA, release manager, doc engineer, PM) curadas do pacote ECC que o PAS já usa, empacotadas como perfis `subagent_*` instaláveis via `.devin/`.
- **devin-obsidian** — inspirado por kepano/obsidian-skills (★49081) — publicar a ponte vault↔Devin do PAS (`obsidian-bridge-server.py`, `obsidian-recall.py`, regras de distilação MOC) como pacote MCP+skills instalável.
- **devin-arch** — inspirado por tt-a1i/archify (★76148) — gerar diagramas de sequência/data-flow verificáveis a partir das arestas reais do `devin-graph` (sessões→ficheiros→ferramentas), HTML self-contained, sem adivinhar arquitetura.
- **devin-agent-rules** — inspirado por multica-ai/andrej-karpathy-skills (★216542) — compilar pitfalls documentados de coding agents num pacote `.devin/rules/` onde cada regra é validada por um caso `devin-evals` contra sessões reais.
- **devin-context** — inspirado por upstash/context7 (★62603) — MCP que serve SPECs/STATUS/registry dos repos (locais ou do ecossistema) como contexto versionado e fresco para a sessão corrente.

## Por repositório

### devin-powerups

1. [estender] Publicar `registry.schema.json` — o `$schema` apontado em registry.json continua inexistente; publicá-lo permite validação externa e por `devin-pm`.
   Porquê: o registry v5 é a fonte de verdade de 20+ repos; schema real evita drift silencioso (kind/local_dir/tests_dir novos já não têm contrato formal).
   Esforço: S
2. [novo] `tools/e2e-preflight.py` — check de ambiente que o scout corre antes do E2E: resolve `~/.venvs/<repo>/bin/python`, deteta pip/pytest/node ausentes e classifica o falhanço como `env-missing` em vez de `fail`.
   Porquê: as 16 falhas de hoje foram ambiente sem pip/pytest no python do sistema (venvs por repo existem), não código — o briefing deve distinguir as duas causas.
   Esforço: S
3. [estender] Fechar o loop do proposals-ledger — o `proposals-ledger.jsonl` já regista decisões; incluir no briefing seguinte o estado (aceite/rejeitada) de cada proposta da semana anterior para impedir re-propostas.
   Porquê: o pipeline de ideação hoje é open-loop — sem estado, o scout repete sugestões já decididas.
   Esforço: S

### devin-internals-spec

1. [novo] Documentar `jev_log.db` e `session_locks/` — stores lidas pelo office/probe e pelo janitor que não estão no SPEC.
   Porquê: são as duas stores reais usadas em produção (PAS) sem contrato — drift nelas quebra ferramentas sem aviso.
   Esforço: M
2. [estender] Fixtures para `acp-messages/*.db` — o SPEC já cobre o layout das stores GUI; um gerador de fixtures sintéticos desbloqueia testes de history/graph/search/search-M2 sem dados reais.
   Porquê: cinco repos têm "GUI sessions planned M2" bloqueados exatamente pela falta de fixture — este é o desbloqueio partilhado.
   Esforço: M
3. [novo] Spec dos formatos de config — `hooks.v1.json`, `mcp_config.json`, `.sessions.json` e `policy.json` documentados com campos/versões.
   Porquê: doctor e bridge já validam esses ficheiros por heurística; um contrato formal torna os checks falsos-negativo-resistentes.
   Esforço: M

### devin-redact

1. [portar] Gate de export por omissão — o PAS já tem `redact_gate` em `session_learning.py` e o backlog pede integração no `devin-history-export.py`; extrair a receita hook+gate para o repo público como `devin-redact hook --install`.
   Porquê: segredos entram no transcript antes de qualquer export; o gate no momento do write é a única defesa em profundidade.
   Esforço: M
2. [estender] Scan de stores JSONL — `memories.jsonl`, `hook-fires.jsonl` e o inbox do mailbox são alvos novos criados pelo PAS fora do SQLite.
   Porquê: o acumulador de segredos deixou de ser só sessions.db; as stores novas têm zero cobertura hoje.
   Esforço: S
3. [estender] Desvendorizar padrões no `no_secrets` do devin-evals — trocar a cópia local de regexes por dependência pinada na tag v0.2.0.
   Porquê: duas fontes de padrões divergem silenciosamente; uma dep pinada mantém gate de publicação e grader de evals consistentes.
   Esforço: S

### devin-history

1. [portar] Export de sessões GUI — o `devin-history-export.py` do PAS já exporta `acp-messages/*.db` para o vault no `SessionEnd`; portar essa cobertura para o pacote público.
   Porquê: a limitação "CLI sessions only" é a maior lacuna de cobertura do repo e já está resolvida em produção local.
   Esforço: L
2. [portar] Export incremental por sessão — o hook SessionEnd do PAS exporta apenas a sessão que fechou; expor `export --session <id>`/`--since-session` no CLI público.
   Porquê: é o modo que torna o export viável como hook por defeito, em vez de re-scan completo.
   Esforço: S
3. [novo] Anchors de provenance — cada mensagem exportada ganha um `ref` estável (`node:<rowid>`, `acp:<db>:<row>`) linkável por devin-search e verificável por devin-memory.
   Porquê: fecha a cadeia de provenance ponta-a-ponta: sessão → nota → hit de pesquisa → memória auditável.
   Esforço: S

### devin-doctor

1. [novo] Check de toolchain de testes — detetar pip/pytest/venv/node ausentes e reportar por OS com `fix:` concreto (`apt install python3-pip python3-venv`, `npm install`).
   Porquê: é exatamente a falha que derrubou os 16 E2E de hoje — diagnóstico instantâneo em vez de depuração manual.
   Esforço: S
2. [estender] `--fix` para itens seguros — locks obsoletos em `session_locks/` e `pre-restore-*` antigos, com confirmação e dry-run (já planeado no STATUS.md).
   Porquê: converte diagnóstico em remediação num comando — o passo natural do género `brew doctor`.
   Esforço: M
3. [novo] Check "automação órfã" — compara o manifesto de tarefas esperadas (`hooks.v1.json` agendados, janitor, heartbeat) com Task Scheduler/systemd/cron reais.
   Porquê: na migração para Linux o inventário de scheduled tasks está vazio — nada hoje avisa que a automação inteira morreu.
   Esforço: S

### devin-pm

1. [estender] Harmonizar path Linux — migrar de `XDG_DATA_HOME` (`~/.local/share/devin`) para `XDG_CONFIG_HOME` (`~/.config/devin`), alinhado com os outros repos e com a store real do Devin CLI.
   Porquê: inconsistência documentada no ECOSYSTEM.md — o único repo que procura sessions.db no sítio errado em Linux.
   Esforço: S
2. [novo] `devin-pm drift` — diff entre o registry.json do hub e os rollups reais: repos com sessões mas sem entrada, entradas sem atividade, contagens divergentes.
   Porquê: o registry cresce por decisão manual; nada o audita contra o ground truth das sessões.
   Esforço: M
3. [estender] Rollups de sessões GUI — incluir `acp-messages/*.db` nos rollups por projeto (limitação M1 documentada), partilhando o parser com devin-history.
   Porquê: quem trabalha no Desktop tem metade da atividade invisível nos status reports.
   Esforço: M

### devin-qa-pack

1. [portar] Handler `audit` agendado — o PAS já corre um handler audit via trigger manifest (waves 1-3); portar como receita `SessionEnd`/scheduled documentada no repo público.
   Porquê: feedback de claims-falsos no momento da sessão em vez de auditoria forense semanas depois.
   Esforço: M
2. [novo] Claims de delegação — nova classe de verificação: "lancei N subagentes" / "todos os workers reportaram" contra `tool_call_state` (run_subagent) + collect-before-report.
   Porquê: fan-out é o modo de trabalho mais novo do ecossistema e nenhum claim dele é verificável hoje.
   Esforço: S
3. [estender] Série histórica de veredictos — `--history` guarda veredicto por sessão e emite trend para o weekly report e devin-metrics.
   Porquê: um veredicto isolado não responde "a qualidade de claims está a melhorar?".
   Esforço: M

### devin-metrics

1. [portar] Digest agendado — o PAS tem handler `metrics-rollup` via trigger manifest; portar como `devin-metrics digest --weekly` consumível pelo scout e dashboard.
   Porquê: o valor de métricas está na cadência; o handler provado resolve o agendamento.
   Esforço: S
2. [novo] Painel custo-por-modelo pós-pin — com `DEVIN_MODEL` fixado no free (regra inquebrável), um painel que alerta se qualquer sessão chamou modelo pago.
   Porquê: transforma a regra do modelo free numa invariante verificável com dados, não confiança.
   Esforço: S
3. [novo] Export `metrics.json` — ficheiro/endpoint que o devin-dashboard consome diretamente.
   Porquê: liga o repo público ao dashboard privado sem acoplamento nem telemetria.
   Esforço: S

### devin-backup

1. [portar] `devin-backup install` — o PAS corre DevinVM-Offload diário; portar como subcomando que regista o snapshot em systemd timer/cron/schtasks conforme a plataforma.
   Porquê: backup manual não existe na prática; o agendamento provado é o que falta ao repo público.
   Esforço: M
2. [portar] Destino remoto com re-verify — o PAS já copia snapshots para a VM via Tailscale; `--to ssh://host/path` com verificação de hashes no destino.
   Porquê: backup no mesmo disco não protege contra falha de hardware — a topologia remota já existe e funciona.
   Esforço: M
3. [estender] Perfil PAS — `--profile pas` cobrindo `.devin/skills`, `memories.jsonl` e configs de gateways (excluindo `.env`), além das stores Devin.
   Porquê: a migração Windows→Linux demonstrou que os artefactos `.devin/` são tão críticos quanto as DBs e não estão no scope atual.
   Esforço: S

### devin-search

1. [portar] Re-index incremental no SessionEnd — o PAS `devin-search.py` mantém `.devin/search/index.db` FTS5; portar o hook que re-indexa só a sessão fechada.
   Porquê: índice sempre fresco sem custo de rebuild — é o modo que viabiliza o self-search durante o trabalho.
   Esforço: M
2. [novo] `devin-search serve` — MCP server expondo `search_sessions` ao próprio agente durante a sessão.
   Porquê: "como resolvi isto da última vez?" respondido dentro da sessão é o dogfooding mais valioso do ecossistema.
   Esforço: M
3. [estender] Semântico opt-in sem LLM — embeddings locais dedicados (modelo de embedding, não LLM generativo) atrás de `--semantic`, com BM25 como fallback.
   Porquê: pesquisa por conceito ("aquela decisão sobre migrar X") falha em keyword-only; respeita a regra de não chamar Ollama para LLM.
   Esforço: L

### devin-graph

1. [portar] Grafo partilhado com o codegraph do PAS — `devin-codegraph.py` já escreve nodes/edges em `.devin/graph/graph.db`; alinhar o devin-graph ao mesmo ficheiro para arestas código↔sessão coexistirem.
   Porquê: dois grafos separados respondem metade das perguntas cada; o join é o valor real.
   Esforço: M
2. [novo] `devin-graph impact <file>` — dado um ficheiro, lista projetos e sessões que o tocam (transitivo sobre `file_touched`).
   Porquê: "se eu mudar este config, o que quebra?" é a pergunta arquitetural mais útil do ecossistema e hoje exige SQL manual.
   Esforço: S
3. [novo] `devin-graph diff` — delta entre dois builds do grafo (ficheiros/tools novos por projeto) como input semanal do scout.
   Porquê: o relatório semanal mostra commits, não atividade estrutural — o diff do grafo é o sinal que falta.
   Esforço: S

### devin-evals

1. [portar] Judge via backend ACP free — o PAS tem `djaevin-acp-bridge.mjs` com `POORDJAEVIN_BACKEND=acp`; `--judge acp` implementa LLM-judge sem custo e sem Ollama.
   Porquê: desbloqueia rubricas semânticas respeitando a regra inquebrável do modelo free pinado.
   Esforço: M
2. [novo] Biblioteca de rubricas — `evals/templates/` com casos instanciáveis por repo (tests-ran, committed-sha, no-secrets, collected-workers).
   Porquê: cada repo irmão precisa dos mesmos 4 checks; templates evitam 15 cópias divergentes.
   Esforço: S
3. [novo] `session_ref` em sessões GUI — resolver refs também em `acp-messages/*.db`, não só `sessions.db`.
   Porquê: sessões GUI são metade do corpus real; sem elas as evals medem só o modo CLI.
   Esforço: M

### devin-memory

1. [portar] Extração sessão→memória — o `session_learning.py` do PAS já extrai lições por turno e promove temas a skills; portar como `devin_memory.learning.extract` escrevendo através do quarantine gate.
   Porquê: "retain armazena o que lhe é dito" é a limitação central do M1 — a extração provada é o M2 inteiro.
   Esforço: L
2. [portar] MCP server quarantine-aware — o `memory-server.py`/`unified` do PAS servem retain/recall sem gate; publicar um servidor que escreve através do quarantine.
   Porquê: fecha o loop — a memória deixa de ser escrita à mão e passa a ter screening na fronteira.
   Esforço: M
3. [novo] `expires_at` + decay no recall — memórias factuais caducam ("CI está verde"); TTL declarado e rebaixamento automático após expirar.
   Porquê: factos velhos com ranking alto são a forma mais comum de envenenamento benigno.
   Esforço: S

### devin-janitor

1. [portar] `devin-janitor install` — o PAS corre o janitor diário via Task Scheduler (hoje órfão no Linux); subcomando que regista em schtasks/systemd/cron conforme a plataforma.
   Porquê: o pipeline provado fica inerte sem agendamento — um comando fecha a lacuna nos dois OS.
   Esforço: M
2. [novo] Tiers para artefactos `.devin/` — `hook-fires.jsonl`, `search.db`, `graph.db`, `learning-state.json` são os novos acumuladores criados pelo PAS.
   Porquê: sessions.db deixou de ser o único store que cresce sem bound — o janitor deve vigiar o que ele próprio ajudou a criar.
   Esforço: S
3. [estender] Notificação pós-run — reusar o slack-notify/email do pipeline PAS para resumir cada purga (apagadas, retidas, pendentes).
   Porquê: o janitor corre silencioso; um resumo diário é o que torna a destruição agendada confiável.
   Esforço: S

### devin-bridge

1. [estender] Suporte Linux real — o host principal agora é Lubuntu: resolver `devin`/`devin-cli` + `~/.config/devin/credentials.toml` além de `devin.exe`/`%APPDATA%`.
   Porquê: README diz "Windows-first"; a máquina de produção mudou de OS e a bridge tem de segui-la.
   Esforço: M
2. [portar] Intake por mailbox — `mailbox-wake.js`/`mailbox-dispatch.py` do PAS provam o padrão; `devin-bridge intake <dir>` consome uma fila de tarefas sem TTY.
   Porquê: permite ao hub e a jobs agendados delegarem trabalho sem sessão interativa.
   Esforço: M
3. [novo] `devin-bridge rotate` — handoff de sessões persistentes (Slack Brain): resume o contexto, abre sessão nova, redireciona o dispatcher.
   Porquê: gap documentado no ECOSYSTEM.md — sessões persistentes acumulam contexto sem bound e nunca devem ser apagadas, só rotacionadas.
   Esforço: M

### devin-orchestrator

1. [novo] Sinal `ram_pressure` no planner — ler MemAvailable/carga e degradar o plano (3→1 workers) sob pressão.
   Porquê: o host tem ~8 GB e o Devin consome ~2.2 — fan-out na hora errada é o modo mais provável de OOM.
   Esforço: S
2. [novo] Plano como trigger manifest — emitir o plano do planner no formato que `devin-catalog` (Scheduled/idle) consome, para fan-out agendado.
   Porquê: liga a policy de workers ao engine de triggers provado, sem duplicar regras de agendamento.
   Esforço: M
3. [estender] Routing de perfis por stack — o planner devolve o perfil especializado por linguagem detetada (python→python-reviewer, etc., padrão dos ~65 agentes ECC).
   Porquê: `subagent_general` para tudo desperdiça os perfis especializados que o PAS já mantém.
   Esforço: S

### personal-agent-system

1. [novo] Instalador de schedulers Linux — `scheduled_tasks` no briefing veio vazio: `scripts/install-schedulers.py` gera systemd --user timers a partir de um manifesto único partilhado com a versão Windows.
   Porquê: as ~17 tasks do Windows não existem no Lubuntu — heartbeat, janitor, scout e watchdogs estão todos parados.
   Esforço: M
2. [novo] `scripts/bootstrap-linux.sh` — cria os venvs por repo, instala pytest/deps, verifica `gh` e o Obsidian REST.
   Porquê: hoje nem pip/pytest existem no python do sistema e o E2E inteiro falhou por isso — bootstrap idempotente previne a próxima migração.
   Esforço: S
3. [estender] mcp-hub como serviço — `:8764` estava no HKCU Run do Windows; unit `systemd --user` + healthcheck, fechando a última peça daemon da migração.
   Porquê: o agregador unified (27 tools) é dependência de todas as sessões — sem auto-restart, uma falha derruba memória+obsidian+nlsql juntos.
   Esforço: S

### devin-dashboard

1. [novo] Suite de testes — o repo está `no_tests`: smoke tests para `serve.py` (`/api/status`, contrato de `/api/laptop`) e para o payload do `laptop_reporter`.
   Porquê: é o serviço de observabilidade do ecossistema sem nenhuma verificação — uma regressão passa invisível.
   Esforço: S
2. [estender] Badge de E2E/scout no SPA — o reporter já recolhe probes; incluir o último scout briefing (repos falhando, timestamp) como painel.
   Porquê: a pergunta "o ecossistema está verde?" deve ser visível no dashboard que já existe para isso.
   Esforço: S
3. [novo] Alertas de threshold — RAM/disk/latência de probes com severidade, emitidos para `heartbeat/state.json` (que já faz dedup de 2h).
   Porquê: monitorização sem alerta exige que alguém olhe para a página; o heartbeat é o destino natural.
   Esforço: M

### devin-office

1. [novo] Suite de testes — `no_tests`: smoke tests de `hub.py` (`/api/ingest` com auth, `/api/state`) e de `daemon.collect_state()` sobre fixture.
   Porquê: o pipeline probe→hub→renderer tem três pontos de falha e zero cobertura.
   Esforço: S
2. [estender] Feed de eventos do ecossistema — o office já lê heartbeat/`jev_log.db`; mapear os sinais de `ecosystem-signals.py` (scout correu, E2E falhou, backup feito) como eventos visuais.
   Porquê: transforma o escritório de "quem está a trabalhar" em "o que aconteceu" — os sinais já existem.
   Esforço: M
3. [novo] Probe multi-host — generalizar `probe.py` para a VM e satellites qwenpaw, tornando o office um mapa de frota.
   Porquê: hoje só o laptop aparece; metade da infra (PM2/Ollama/serviços na VM) é invisível no mapa.
   Esforço: M

### qwenpaw-suite

1. [novo] Suite de testes — 0 casos: smoke tests para a bridge Flask (`/v1/chat/completions` contract, auth opcional) e para o JSON do healthcheck.
   Porquê: a bridge é o ponto único de falha do acesso ao Ollama; sem contrato testado, mudanças de payload passam caladas.
   Esforço: M
2. [estender] Backend ACP na bridge — adicionar backend `acp` (modelo free Devin via `djaevin-acp-bridge`) ao proxy OpenAI-compatible, além do Ollama.
   Porquê: alinha a suite com a regra inquebrável do ecossistema (LLM = free Devin via ACP) mantendo Ollama para embeddings/não-LLM.
   Esforço: M
3. [estender] Paridade Linux nos docs/scripts — o README ainda referencia `C:\...\start-all.bat`; quickstart systemd/cron + paths Linux (a suite já corre na VM Debian).
   Porquê: a convenção de paridade Linux é política oficial do ecossistema e este repo ainda documenta só Windows.
   Esforço: S

## E2E failures

Causa comum verificada: o host Linux novo **não tem pip nem pytest no python do sistema** (`python3 -m pip`/`pytest` → `No module named ...`), mas existem venvs por repo em `~/.venvs/<repo>/` com pytest 9.1.1 e os pacotes instalados. Todos os `tail` vieram vazios — o runner está a invocar o interpretador errado e a capturar nada. Direção de fix partilhada: resolver `~/.venvs/<repo>/bin/python -m pytest` por repo no `weekly-ecosystem-scout.mjs`, com fallback `python3 -m unittest` para repos stdlib-only, e logar stderr quando o tail vier vazio.

- **devin-powerups** — tail: (vazio). A suite é unittest stdlib e passa com `python3 -m unittest` (verificado: 23 testes OK); fix: runner usar unittest discover ou criar `~/.venvs/devin-powerups`.
- **devin-internals-spec** — tail: (vazio). Fix: `~/.venvs/devin-internals-spec/bin/python -m pytest` (venv existe).
- **devin-redact** — tail: (vazio). Fix: idem — venv `~/.venvs/devin-redact` presente com pytest.
- **devin-history** — tail: (vazio). Fix: `~/.venvs/devin-history/bin/python -m pytest` — confirmado pytest 9.1.1.
- **devin-doctor** — tail: (vazio). Fix: usar o venv `~/.venvs/devin-doctor`; dep `devin-internals-spec` já deve estar instalada nele.
- **devin-pm** — tail: (vazio). Fix: `~/.venvs/devin-pm/bin/python -m pytest` — confirmado pytest 9.1.1; nota: este repo resolve sessions.db em `~/.local/share/devin` (ver proposta de harmonização XDG).
- **devin-qa-pack** — tail: (vazio). Fix: venv `~/.venvs/devin-qa-pack` presente; mesma resolução de interpretador.
- **devin-metrics** — tail: (vazio). Fix: venv `~/.venvs/devin-metrics`; dep de `devin-internals-spec` resolvida dentro do venv.
- **devin-backup** — tail: (vazio). Fix: venv `~/.venvs/devin-backup` presente; mesma resolução.
- **devin-search** — tail: (vazio). Fix: venv `~/.venvs/devin-search` presente; mesma resolução.
- **devin-graph** — tail: (vazio). Fix: venv `~/.venvs/devin-graph` presente; mesma resolução.
- **devin-evals** — tail: (vazio). Fix: venv `~/.venvs/devin-evals` presente; mesma resolução.
- **devin-memory** — tail: (vazio). Fix: venv `~/.venvs/devin-memory`; atenção à dep git `devin-redact` — reinstalar no venv se stale.
- **devin-janitor** — tail: (vazio). Fix: venv `~/.venvs/devin-janitor` presente; mesma resolução.
- **devin-orchestrator** — tail: (vazio). Fix: venv `~/.venvs/devin-orchestrator` presente; mesma resolução.
- **personal-agent-system** — tail: (vazio). Fix: sem venv próprio em `~/.venvs/` — criar um (`python3 -m venv ~/.venvs/personal-agent-system` após `apt install python3-venv`), instalar pytest, e garantir `npm install` em `acp-agent/` e `gateways/` para a parte Node dos 4710 testes.
