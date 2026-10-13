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
  de permissao do GITHUB_TOKEN, nao falha real — visto em
  dashboard#9, state#37, PAS#26/27/28. Sintoma reconhecido => retry ou
  ignora; nao diagnosticar como regressao.
- (2026-10-13) teste que pina marcadores de conteudo testa o snapshot,
  nao o contrato: `test_skill_policy.py` ficou verde enquanto pinava
  strings que o SKILL.md ja nao tinha — so falhou quando um PR reescreveu
  o ficheiro. Mesma classe do smoke-que-nao-cobre-regressao: pins devem
  seguir o contrato vivo, e todo rewrite de ficheiro pinado exige
  re-pin do teste no mesmo commit.
- (2026-10-13) pin declarado vs lock real e o mesmo eixo do lockstep
  versao: `uv.lock` ficou em internals-spec 0.3.0 quando o pin subiu
  para >=0.3.1 — invisivel porque CI usa pip, nunca `uv sync --locked`.
  Todo bump de pin exige `uv lock` no mesmo commit; sem gate, o lock
  so diverge em silencio para quem corre `uv run` local.
- (2026-10-13) "parece ausente" != "esta ausente" — o verso do default
  invertido. Antes de pedir credenciais ou declarar "sem sessao",
  inventario obrigatorio de mecanismos existentes: `ps aux` para
  launchers (CDP, playwright, MCP), `ls ~/.local/share/` e
  `~/.config/` para perfis/kits persistentes, vault com 2-3 variantes
  de query (vault-first). Caso real: um kit de scraping persistente
  (dir proprio em `~/.local/share/`, browser com porta CDP aberta,
  sessao GitHub viva, launcher running) ficou invisivel durante ~4
  turnos porque a busca
  foi MCP-browser -> vault-credenciais -> "pede ao user" — nunca `ps`.
  Pedir credencial que a maquina ja tem e a falha, nao a ausencia.
  Regras violadas: vault-first (queries minimas) e
  inventario-antes-de-negar (memoria-e-vault-primeiro SS4).

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
