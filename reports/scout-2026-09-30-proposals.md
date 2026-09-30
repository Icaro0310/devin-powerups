# Ecosystem scout 2026-09-30

## Novos projetos (trends)

- **devin-scout** — inspirado por sansan0/TrendRadar (★62632) — transformar este pipeline semanal (trends GitHub + E2E + relatório) num repo público próprio, com briefing JSON versionado e histórico de propostas aceites/rejeitadas.
- **devin-codegraph** — inspirado por colbymchenry/codegraph (★72564) — índice AST persistente dos repos em que o Devin trabalha, complementando o devin-graph (que mapeia atividade de sessões, não código); arestas código↔sessão ligam os dois grafos.
- **devin-skill-catalog** — inspirado por sickn33/agentic-awesome-skills (★47124) — control plane local para o catálogo `.devin/skills`: descoberta, validação de frontmatter, lifecycle de skills `learned-*` e diffs de versão por workspace.
- **devin-primer** — inspirado por thedotmack/claude-mem (★95021) — injeção de contexto entre sessões: resume a última sessão relevante por repo (via devin-history/memory) e gera um bloco de priming para o prompt seguinte.
- **devin-switch** — inspirado por farion1231/cc-switch (★139126) — gestor de perfis de configuração Devin CLI+Desktop (credentials.toml, hooks.v1.json, mcp_config.json, modelos) com presets nomeados e `doctor` de compatibilidade.

## Por repositório

### devin-powerups

1. **Publicar `registry.schema.json`** — o `$schema` apontado em registry.json não existe no repo; publicá-lo permite validação externa e por `devin-pm`.
   Porquê: o registry é a fonte de verdade do ecossistema; schema real evita drift silencioso entre os 16 repos.
   Esforço: S
2. **Coluna de saúde de CI no weekly report** — estender `weekly_repo_report.py` com o estado do último run de CI por repo (endpoint público de workflow runs).
   Porquê: o relatório mostra commits mas não diz se o código está verde — a pergunta seguinte do maintainer.
   Esforço: M
3. **`new-repo.py --dry-run` + escrita automática no registry** — o scaffolder cria o repo mas não regista a entrada; um flag dry-run + append validado fecha o ciclo.
   Porquê: remove o passo manual mais esquecido no bootstrap de novos projetos.
   Esforço: S

### devin-internals-spec

1. **Catálogo tipado das chaves `windsurfSpace.*`** — documentar em tabela as chaves conhecidas de `state.vscdb` (existem mas não estão enumeradas no SPEC).
   Porquê: é a única store coberta sem mapa de conteúdo — aumenta a superfície útil de todos os consumidores.
   Esforço: M
2. **`devin-inspect watch` / check de drift em CI** — comparar a versão de schema da instalação real com as suportadas e falhar alto no semanal.
   Porquê: deteta a próxima migração (v18) no dia em que sai, em vez de quando um tool quebra.
   Esforço: M
3. **CLI `make-fixture` público** — expor `devin_internals.fixtures` como subcomando para gerar stores sintéticos versionados partilhados por todos os repos irmãos.
   Porquê: cinco projetos já geram fixtures em runtime; uma CLI oficial padroniza e facilita testes manuais.
   Esforço: S

### devin-redact

1. **`SessionEnd` hook integrado** — o README lista isto como M2 pendente: scan automático ao fechar cada sessão, com relatório gravado.
   Porquê: apanha segredos no momento em que entram no transcript, antes de qualquer export/share.
   Esforço: M
2. **Deteção de segredos divididos entre chunks** — janela deslizante sobre eventos adjacentes para apanhar tokens partidos em dois payloads (falso negativo documentado).
   Porquê: fecha a falha de recall mais provável em outputs de tools grandes.
   Esforço: M
3. **Saída SARIF (`--format sarif`)** — emitir o relatório no formato que o GitHub code scanning consome.
   Porquê: integra o scan no CI dos repos públicos sem parser custom.
   Esforço: S

### devin-history

1. **Export das sessões GUI (`acp-messages/*.db`)** — a limitação M1 "CLI sessions only" é a maior lacuna de cobertura.
   Porquê: quem usa o Desktop perde metade do histórico no export.
   Esforço: L
2. **Modo `--watch` incremental** — daemon leve que re-exporta notas ao detetar `last_activity` novo, em vez de re-run manual.
   Porquê: torna o vault Obsidian sempre atual sem intervenção.
   Esforço: M
3. **`index.md` com estatísticas** — o export já computa agrupamentos de audit; reutilizá-los num índice com sessões/dia e projetos top.
   Porquê: zero custo novo de dados, valor imediato de navegação no vault.
   Esforço: S

### devin-doctor

1. **`--fix` para os itens seguros** — STATUS.md já o planeia: locks obsoletos e limpeza de `session_locks/` com confirmação.
   Porquê: converte diagnóstico em remediação num comando, o passo natural do género `brew doctor`.
   Esforço: M
2. **Check de hooks/MCP que abrem janelas** — validar `hooks.v1.json`/`mcp_config.json` à procura de `python`/`node` sem `pythonw`/wrapper (lição aprendida no workspace).
   Porquê: é o bug de UX mais frequente em Windows e hoje só se deteta vendo a janela piscar.
   Esforço: S
3. **Cobertura de testes para paths macOS** — os paths existem mas estão "unverified"; fixtures com layout `~/Library/Application Support/devin`.
   Porquê: fecha a única plataforma declarada sem verificação.
   Esforço: S

### devin-pm

1. **Agrupamento de sessões GUI** — incluir `acp-messages/*.db` nos rollups por projeto (limitação M1 documentada).
   Porquê: os rollups ficam incompletos para quem trabalha maioritariamente no Desktop.
   Esforço: M
2. **`devin-pm verify`** — lint do `registry.json` do hub contra a realidade das sessões (repos com sessões mas sem entrada, e vice-versa).
   Porquê: o registry é fonte de verdade mas nada o audita contra o ground truth.
   Esforço: S
3. **Normalização de paths Windows no agrupamento** — colapsar diferenças só-de-case no `working_directory` (edge documentado).
   Porquê: em Windows o mesmo repo aparece como dois projetos; fix pequeno, correção permanente.
   Esforço: S

### devin-qa-pack

1. **Auditoria live via hook `SessionEnd`** — correr o audit no fim de cada sessão e anexar o veredito ao transcript (M2 já prevê MCP).
   Porquê: feedback de claims-falsos no momento, em vez de auditoria forense semanas depois.
   Esforço: M
2. **Claims de deploy/release** — extrair "deployed", "published", "tagged v*" e verificar contra runs de CI/`gh release list`.
   Porquê: são as afirmações de maior risco hoje não cobertas pelo extrator.
   Esforço: M
3. **Relatório HTML agregado para `--all`** — página única com veredictos por sessão para o weekly report do hub.
   Porquê: reutiliza o pipeline de artifact já existente e dá visibilidade contínua à qualidade de claims.
   Esforço: S

### devin-metrics

1. **Séries temporais no dashboard** — custo/tokens por dia e por modelo no HTML single-file (subpackage absorvido do devin-dashboard).
   Porquê: "estou a gastar mais ou menos?" é a pergunta que os rollups estáticos não respondem.
   Esforço: M
2. **Alertas de budget** — `--budget X --period week` com exit code/warning quando o gasto excede o limite.
   Porquê: transforma métricas passivas em guarda ativa; trivial sobre os agregados existentes.
   Esforço: S
3. **Modo de validação de shape real** — flag que compara `extract_usage()` contra payloads acp reais e reporta drift (gap "unverified" documentado).
   Porquê: converte a maior incerteza do projeto num check reproduzível.
   Esforço: S

### devin-backup

1. **Subcomando `install` (Task Scheduler/cron)** — o README declara "not a scheduler" como M2; um comando que regista o snapshot diário resolve.
   Porquê: backup manual não existe na prática; agendamento é o que torna a ferramenta real.
   Esforço: M
2. **Destino remoto/secundário** — copiar o snapshot+manifest para um segundo diretório/mount com re-verificação de hashes.
   Porquê: backups no mesmo disco não protegem contra falha de hardware.
   Esforço: M
3. **`devin-backup diff <snapshot>`** — mostrar o que mudou entre um snapshot e as stores live antes de restaurar.
   Porquê: responde "vale a pena restaurar?" sem arriscar escrita.
   Esforço: S

### devin-search

1. **Pesquisa semântica opt-in (M2)** — embeddings locais sobre o corpus FTS5, atrás de flag, com BM25 como fallback.
   Porquê: "aquela decisão sobre migrar X" raramente usa as palavras exatas — a limitação keyword-only está documentada.
   Esforço: L
2. **Links dos hits para notas devin-history** — resolver `ref` (`node:1234`) para URI Obsidian quando o vault de export existir.
   Porquê: salta diretamente do resultado para a nota completa — integração barata e de alto valor.
   Esforço: S
3. **Modo browse/TUI** — navegação interativa de resultados com preview do contexto da sessão.
   Porquê: exploração ("não sei bem o que procuro") é o caso onde a CLI one-shot falha.
   Esforço: M

### devin-graph

1. **Sessões GUI + `state.vscdb` (M2)** — estender a extração de arestas para `acp-messages/*.db` e KV relevantes.
   Porquê: metade da atividade real fica fora do grafo hoje.
   Esforço: M
2. **Viewer HTML/D3 embutido** — o export já emite JSON D3-friendly; falta a página que o renderiza offline.
   Porquê: transforma dados em ferramenta de exploração sem dependências externas.
   Esforço: M
3. **Query "ficheiros partilhados entre projetos"** — promover a análise de configs comuns (ex: `.devin/` patterns) a canned query de primeira classe.
   Porquê: é a pergunta arquitetural mais útil do ecossistema e hoje exige SQL manual.
   Esforço: S

### devin-evals

1. **Grader LLM-judge opt-in** — atrás de `--judge` explícito e desligado por omissão, para rubricas que `contains` não consegue avaliar.
   Porquê: a limitação determinística está documentada; um judge opcional mantém M1 puro e desbloqueia rubricas semânticas.
   Esforço: M
2. **`session_ref` por janela/projeto** — `{"latest_in_project": "devin-x", "days": 7}` para suites de regressão auto-atualizadas.
   Porquê: hoje cada caso está preso a um id/título — o corpus não roda contra trabalho novo.
   Esforço: M
3. **Corpus de golden cases do ecossistema** — fixtures `evals/` para cada repo irmão corridos no workflow semanal do hub.
   Porquê: dogfooding barato — deteta regressões de tooling no pipeline real de sessões.
   Esforço: S

### devin-memory

1. **Auto-extração M2 ponta-a-ponta** — ligar o pipeline devin-learning absorvido: sessão → candidatos → quarantine → review.
   Porquê: "retain armazena o que lhe é dito" é a limitação central; sem extração a memória nunca escala.
   Esforço: M
2. **Deteção de contradição no `supersede`** — avisar quando uma nova entry contradiz ativas com as mesmas tags antes de substituir.
   Porquê: anti-poisoning é a promessa do projeto; conflitos silenciosos são o envenenamento mais subtil.
   Esforço: M
3. **Servidor MCP de retain/recall/quarantine** — expor o store ao Devin Desktop diretamente, substituindo o memory MCP sem quarantine.
   Porquê: fecha o loop — a memória deixa de ser editada à mão e passa a ser escrita com screening.
   Esforço: M

### devin-janitor

1. **`devin-janitor install --daily`** — registar o run no Task Scheduler/cron (o script legacy já corria diário via schtasks).
   Porquê: o pipeline provado fica inerte sem agendamento — um comando fecha a lacuna.
   Esforço: M
2. **Tiers para checkpoints/workspaces/`state.vscdb`** — o README diz que só apaga sessões; estender a classificação aos restantes acumuladores.
   Porquê: sessions.db não é a única store que cresce sem bound.
   Esforço: M
3. **`report` de espaço recuperável** — histograma de tiers + projeção de bytes sem apagar nada.
   Porquê: convence o utilizador do valor antes do primeiro `--apply`.
   Esforço: S

### devin-bridge

1. **Probe de compatibilidade ACP no arranque** — detetar versão do `devin.exe` e capacidades antes de abrir sessão, falhando alto sobre protocolo undocumented (a fragilidade declarada do projeto).
   Porquê: hoje uma mudança da Cognition falha como erro estranho de stream, não como incompatibilidade identificada.
   Esforço: M
2. **Presets de policy** — `policy --init --preset tests-only|read-only|full` com templates comentados por tipo de tarefa.
   Porquê: o gate é o diferencial mas configurá-lo de raiz é o maior atrito de adoção.
   Esforço: S
3. **Intake por mailbox/webhook** — fila de ficheiros de tarefa que o dispatcher consome e despacha via `prompt` (padrão já provado no Slack-bridge do workspace).
   Porquê: permite ao hub e a jobs agendados delegarem trabalho sem TTY interativo.
   Esforço: M

### devin-orchestrator

1. **Publicar o planner como biblioteca + JSON Schema do spec** — hoje o input é um JSON ad-hoc; um schema permite validação e reuso pelo hub.
   Porquê: torna o contrato determinístico consumível por outras tools (scout, pm) sem duplicar regras.
   Esforço: S
2. **`--explain`** — traço legível das decisões do plano (porque 0/1/3 workers, que regra disparou).
   Porquê: uma policy "que não pode ser negociada" precisa de ser auditável para ser confiável.
   Esforço: S
3. **Telemetria de planos** — registar plano vs. desfecho real (duração, falhas) em store local para calibrar `estimated_scope` futuro.
   Porquê: hoje os sinais são intuição do modelo; dados fecham o loop de melhoria do planner.
   Esforço: M

## E2E failures

Nenhuma.
