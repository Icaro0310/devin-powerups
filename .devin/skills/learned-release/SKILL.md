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
