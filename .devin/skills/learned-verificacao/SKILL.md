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
  mecanismos paralelos sao onde os erros vivem (heartbeat-wake.py orfao,
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

## Changelog

- v1 (2026-10-11): criada na onda corporate-docs + devkit extras target
