---
name: learned-git
description: "Licoes aprendidas automaticamente sobre git neste workspace"
triggers:
  - model
---

# Licoes aprendidas: git

Gerada automaticamente pelo loop de aprendizado (SessionEnd hook).
Aplique estas licoes quando trabalhar em tarefas relacionadas.

## Licoes

- (2026-10-02) never propose as new something the workspace already does; do not commit or push anything; when done, reply with just DONE
- (2026-10-04) never propose as new something the workspace already does; do not commit or push anything; when done, reply with just DONE
- (2026-10-21) Token `gh` sem scope `workflow` — escrita em
  `.github/workflows/*` falha de forma enganadora: REST
  `PUT /contents` devolve **404** (indistinguivel de "ficheiro
  inexistente") e `git push` HTTPS e recusado explicitamente
  ("refusing to allow an OAuth App to create or update workflow").
  Caminho que funciona: clone/push via **SSH** (`git@github.com:...`)
  — chave SSH autentica como o utilizador e nao carrega scopes OAuth.
  E a 5a redescoberta do mesmo facto em 2 semanas (memorias
  10-08/09/15/20/21): nao diagnosticar o 404 como path errado, ir
  directo ao SSH. Diagnosticar com `gh auth status` → scopes sem
  `workflow`.

## Changelog

- v3 (2026-10-07): 0 nova(s) licao(oes)
- v4 (2026-10-21): gh token sem workflow scope → 404 mascarado /
  HTTPS push recusado → SSH e o caminho (5a redescoberta)
