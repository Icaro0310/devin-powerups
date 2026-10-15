---
name: learned-verificacao
description: "Licoes aprendidas sobre verificacao mecanica e checks neste workspace"
triggers:
  - model
---

# Licoes aprendidas: verificacao mecanica

Aplique estas licoes quando planear ou executar operacoes que tocam
muitos ficheiros, superficies geradas, ou merges sob guardrails.

## Licoes

- (2026-10-11) operacao que toca N ficheiros sai com check mecanico: um
  sweep sem `--check`/script proprio e onde as classes de drift
  sobrevivem (badge sweep sem check = 49 ocorrencias stale; guia manual
  do devkit fora do gerador = invisivel ao `--check`). Antes de propor
  "manual com check proprio", preferir cobrir no gerador unico —
  mecanismos paralelos sao onde os erros vivem (o job de wake orfao,
  internals-spec).
- (2026-10-11) merges de output gerado nao tem findings no sentido do
  D-record: a categoria e "generator merge" (gerado, identico entre
  repos, review dispensavel por natureza). Verificar zero threads
  `bug|security` antes de classificar; se houver finding real, aplica a
  regra par-por-finding normal.
- (2026-10-11) contagem so e fiavel apos grep global: enumeracao manual
  contou 6 repos com token PyPI; grep revelou 7. Nunca reportar
  contagem de enumeracao sem grep.
- (2026-10-11) afirmar que um env var/feature existe requer grep no
  branch certo: `DEVIN_DEVKIT_OFFLINE` existia no branch do PR #36 mas
  nao em main/published — afirmar "existe" ou "nao existe" sem dizer o
  branch e factualmente incompleto.
- (2026-10-13) "parece coberto" != "esta coberto" — DEFAULT INVERTIDO:
  quando um PR parece superseded, assume que NAO esta, verifica, depois
  decide. Sweep de 20 PRs pre-vaga: zero superseded reais — a camada
  MCP+skill+plugin parecia shipped (vscode/daemon estavam) mas nunca
  entrou em assure/control/devkit. Mesmo padrao do `--environment` so
  em install e do `merged-into-main` so no PyPI: superficie parcial le
  como cobertura total, e o reflexo natural e fechar sem verificar.
  grep em `main` e o unico juiz; nunca a aparencia.
- (2026-10-13) classe nomeada: `approve-job flake` — check
  `approve / approve` falha em <10s com `gh: Resource not accessible
  by integration (HTTP 403)` + `jq: Cannot iterate over null`. E flake
  de permissao do GITHUB_TOKEN, nao falha real — visto em varios repos
  do ecossistema (dashboard#9, state#37, entre outros). Sintoma
  reconhecido => retry ou ignora; nao diagnosticar como regressao.
- (2026-10-13) teste que pina marcadores de conteudo testa o snapshot,
  nao o contrato: `test_skill_policy.py` ficou verde enquanto pinava
  strings que o SKILL.md ja nao tinha — so falhou quando um PR reescreveu
  o ficheiro. Mesma classe do smoke-que-nao-cobre-regressao: pins devem
  seguir o contrato vivo, e todo rewrite de ficheiro pinado exige
  re-pin do teste no mesmo commit.
- (2026-10-13) pin declarado vs lock real e o mesmo eixo do lockstep
  versao: um `uv.lock` ficou em 0.3.0 quando o pin subiu para >=0.3.1 —
  invisivel porque CI usa pip, nunca `uv sync --locked`. Todo bump de
  pin exige `uv lock` no mesmo commit; sem gate, o lock so diverge em
  silencio para quem corre `uv run` local.
- (2026-10-14) relatorio de subagent sobre conteudo de ficheiro entra em
  artefacto publicado so apos medicao directa: um subagent reportou "0
  matches" para `session-state`/`events.jsonl`/`agentSessions.` num
  bundle minificado — greps directos na mesma sessao mediram 3/2/26 e
  mudaram a conclusao do G1 (o nativo le `.copilot/session-state` do
  disco). Instancia da familia "parece ausente != esta ausente", mas o
  objeto e outro: subagent report != medicao. Regra: qualquer "N
  matches"/"ausente"/"presente" vindo de subagent que vai para doc,
  D-record ou PR recebe um grep/wc de confirmacao na sessao principal —
  30 segundos, e o artefacto nao herda erro de exploracao alheia.
- (2026-10-13) "parece ausente" != "esta ausente" — o verso do default
  invertido. Antes de pedir credenciais ou declarar "sem sessao",
  inventario obrigatorio de mecanismos existentes: `ps aux` para
  launchers (CDP, playwright, MCP), `ls ~/.local/share/` e
  `~/.config/` para perfis/kits persistentes, e o store local de
  credenciais com 2-3 variantes de query. Caso real: um kit de
  scraping persistente (dir proprio em `~/.local/share/`, browser com
  porta CDP aberta, sessao GitHub viva, launcher running) ficou
  invisivel durante ~4 turnos porque a busca foi MCP-browser -> store
  de credenciais -> "pede ao user" — nunca `ps`. Pedir credencial que
  a maquina ja tem e a falha, nao a ausencia. Regras violadas:
  pesquisa de credenciais primeiro (queries minimas) e inventario
  antes de negar.

## Changelog

- v1 (2026-10-11): criada na onda corporate-docs + devkit extras target
- v2 (2026-10-13): +3 licoes do PR-sweep (parece-coberto, pins de teste,
  lockfile drift)
- v3 (2026-10-13): default invertido em superseded (assume que nao esta),
  classe `approve-job flake` nomeada
- v4 (2026-10-13): verso do default invertido — "parece ausente != esta
  ausente" (inventario de mecanismos antes de pedir credenciais/sessao)
- v5 (2026-10-13): nomes internos removidos (sensor adapters-check) —
  a licao fica intacta sem nomes de tooling privado
- (2026-10-13) limite do default invertido: o grep-em-main aplica-se a
  PRs que tocam superficie de produto ou config (.github/, pyproject,
  codigo). Para PRs docs-only ou dependabot, fechar por leitura do
  titulo e aceitavel — sem este limite a regra correcta desgasta-se por
  uso excessivo, e regra gasta morre.
- (2026-10-14) subagent report != medicao: claims de contagem/ausencia
  vindos de exploracao alheia recebem grep de confirmacao na sessao
  principal antes de entrar em doc publicado (incidente
  sessions.desktop.main.js).
- (2026-10-14) identificador introduzido por agente verifica-se na
  fonte: `paths_allowed` (o campo real e `paths-ignore`) e
  `setup-python@<sha># v6` (SHA comentado com versao inexistente) sairam
  no mesmo PR — duas alucinacoes de "nome plausivel" que o Devin Review
  apanhou. Plausibilidade nao e evidencia: campo de config, versao de
  action e path novo verificam-se na doc/origem antes de entrar no
  commit, nao a espera que o review apanhe.
- (2026-10-14) "parece que sei o que precisa" != "li o que esta
  escrito" — a direccao oposta do default invertido. O header de
  release.yml documentava os scopes exactos que o reusable exige do
  caller (contents:read, id-token:write, packages:write) e que um scope
  em falta mata o run em startup_failure com zero jobs; nao foi lido,
  dois tag-runs morreram (environment:"" invalido, depois
  packages:write ausente). Antes de invocar um mecanismo com contrato
  documentado (reusable workflow, sensor, shared helper), ler o header
  e nao inferir o contrato. Documentacao estatica existente e ignorada
  falha em silencio ate ao runtime.
- (2026-10-14) CI Windows e ambiente real, nao emulado: fixtures de
  executavel devem declarar a plataforma desde o inicio — PATHEXT nunca
  casa ficheiro sem extensao (12 falhas no bridge porque `devin`/
  `devin-bridge` POSIX-style nao resolviam em windows-latest). Assercoes
  de path/extensao sao platform-aware (`".EXE"` maiusculo casa o PATHEXT
  default); um fixture nao-resoluvel torna o teste de "skip" falso-
  positivo trivial — o binario plantado nunca sequer era candidato.
- (2026-10-15) teste de boundary guard: monkeypatch e subprocess/E2E sao
  complementares, nao alternativos. O monkeypatch (`build_server` ->
  ImportError -> assert exit 1 + hint + sem Traceback) cobre a ramificacao
  deterministicamente e nao depende de um venv sem `[mcp]` — mas mocka o
  ponto onde o hint nasce, entao NAO apanha regressao em `_make_app` (se o
  hint deixar de viajar ate ao `main`, o teste continua verde). O nivel
  subprocess/E2E (server real sem extra -> exit 1 + `error:` no stderr)
  e o unico que apanha essa deriva. Os dois niveis ficam: unit para a
  branch, E2E para o contrato. Aplicado nos 5 PRs mcp-extra-guard.
