---
name: learned-release
description: "Licoes aprendidas sobre release fan-out, OIDC e publicacao multi-plataforma neste workspace"
triggers:
  - model
---

# Licoes aprendidas: release e publicacao

Aplique estas licoes quando desenhar workflows de release, trusted
publishing, OIDC federation ou checks de versao.

## Licoes

- (2026-10-12) OIDC trust e por repo; workflow reutilizavel cross-repo
  NAO herda. O PyPI valida `job_workflow_ref` = `<repo-caller>/...`, um
  `uses:` para outro repo nunca casa com o TP por-repo — mesma regra no
  Entra: cada repo precisa da sua propria federated credential no app
  registration. O fan-out deve DETECTAR o mismatch e skipar com warning;
  o caminho canonico fica no workflow inline do repo.
- (2026-10-12) subject `environment:release` cobre tag + dispatch +
  reusable call com um so federated credential — entity type por branch
  ou tag obrigaria uma credencial por superficie.
- (2026-10-12) version drift extensao↔pacote e estrutural, nao
  acidental: 3 ocorrencias em 3 semanas (redact, evals, memory/search) —
  publish da extensao desacopla do release do pacote. O check de
  lockstep pertence ao CI de PR (adapter-test.yml), nao so ao release.
- (2026-10-12) `vsce publish --azure-credential` e o caminho sem PAT:
  GitHub OIDC → federated credential → token Entra → marketplace. O
  member-add do publisher espera o marketplace identity id
  (`az rest profiles/me` autenticado como o SP), NAO o object id do
  app registration. Flags CLI sao kebab-case (`--skip-duplicate`),
  mesmo quando a API interna usa camelCase.
- (2026-10-12) `vsce publish --oidc` (trusted publishing direto, estilo
  PyPI) existe na CLI mas a policy do marketplace ainda nao e
  configuravel no portal — caminho documentado, nao utilizavel hoje.
  Re-avaliar quando a issue do vsce fechar.
- (2026-10-15) `gpg --batch --import --show-keys` e um par de comandos
  CONFLITUOSO ("gpg: conflicting commands") — falhou em producao em 5
  workflows (explore/assure/control/devkit). Extracao de fingerprint e
  `gpg --batch --show-keys --with-colons` SOZINHO sobre a key armored;
  o `--import` fica no step anterior separado. Padrao copiavel:
  `KEYID=$(gpg --batch --show-keys --with-colons < key.asc | awk -F: '/^fpr/{print $10; exit}')`.
- (2026-10-15) Caller workflows de release: `fanout` (reusable publish)
  precisa de `needs: [validate, release]` E `if: github.event_name ==
  'push' && github.ref_type == 'tag'`. Sem isso: (a) workflow_dispatch
  publica em OVSX/Marketplace sem tag (o tag gate do reusable e
  `ref_type=='tag'` e skipa em dispatch); (b) a extensao publica mesmo
  quando o release GitHub falha. Dispatch fica dry-run de validate.
- (2026-10-15) `gh workflow run` so enfileira — publish fire-and-forget
  deixa o release verde com npm nao publicado. Poll bounded por
  `gh run list --workflow X --commit $SHA` filtrando `createdAt >=`
  instante do dispatch (sem o filtro, um retry le a conclusao do run
  ANTERIOR no mesmo commit).
- (2026-10-15) Publishers npm precisam de 2 guards proprios: merged-origin
  (`gh api compare/main...SHA`) — uma tag num commit nao mergeado
  publica codigo nao revisto — e dup-skip via `npm view pkg@ver` antes
  de `npm publish` (retry falha E403 em versao existente).
- (2026-10-15) Entra/Marketplace JA ESTA provisionado nos 6 repos —
  `vsce publish --azure-credential` publicou em todos em 2026-10-15.
  A premissa "Marketplace espera Entra" ficou obsoleta; o skip limpo do
  reusable continua correto como fallback.
- (2026-10-15) devin-brain tem 2 linhas de versao independentes: wheel
  `devin-memory` 0.3.x (pypi-publish.yml) vs extensao 0.1.x
  (release-memory.yml, tag `memory-v*`). O fanout usa
  `package-dir: adapters/vscode` — sem pyproject ali, o reusable corre
  o path extension-only e o tag gate so valida o manifest da extensao.
  Lockstep NAO se aplica entre os dois artefactos.
- (2026-10-15) leg com credencial opcional: o fix do azure/login
  evoluiu em duas camadas — padrao reutilizavel para qualquer leg que
  dependa de provisioning externo. (1) `continue-on-error: true` +
  `id:` no passo de login, publish gated em `steps.X.outcome ==
  'success'` (outcome, nao conclusion — continue-on-error mascara
  conclusion): a credencial pendente vira warning e o resto do job
  (Open VSX) corre. (2) gate opt-in `AZURE_MARKETPLACE_REQUIRED=true`
  no fim do job: repos pos-provisioning voltam a falhar vermelho em
  qualquer non-success do marketplace (vars em falta, login ou vsce),
  mas so DEPOIS do OVSX ter corrido. Sem a camada 1, uma credencial
  por provisionar segura 4 legs por uma; sem a camada 2, o defer vira
  silencio permanente e ninguem nota que o marketplace nunca publicou.
- (2026-10-15) floor-check CLI↔extensao tem 2 fases e a dependencia entre
  elas nao e obvia: (heuristica) stderr do argparse `unrecognized
  arguments|invalid choice` -> msg "CLI too old, upgrade" — detecta CLI
  mais velho que a flag minima SEM probe; (estrutural) `version`
  self-reported no payload JSON -> cliCompatStatus preciso. A heuristica
  assume que o texto de erro do argparse e estavel entre versoes — se um
  CLI futuro mudar a mensagem (outra flag, subcommand, reescrita), o
  fallback deixa de detectar e volta ao silencio. Regra: o campo
  `version` no payload e o que torna o check robusto; antes de remover a
  heuristica de stderr confirmar que o payload-version esta em TODOS os
  CLIs publicados (e vice-versa: nao apagar o caminho estrutural porque
  "a heuristica ja cobre"). Fase actual: heuristic-only ate os CLIs
  publicados emitirem version (qa-pack/search >=0.1.3).
