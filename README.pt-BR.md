<div align="center">

<img src="assets/banner.svg" alt="devin-powerups" width="100%"/>

</div>

# devin-powerups

> Ferramentas comunitárias não oficiais para Devin. Sem afiliação, endosso ou
> patrocínio da Cognition AI. Devin é marca da Cognition AI.
>
> **[English](README.md)** · Português (BR)

Toolkit público de manutenção dos projetos Devin para a comunidade. Inclui um
catálogo legível por máquina, um template inicial, um scaffolder local e um
gerador de relatórios semanais de atividade. Utilizadores finais instalam as
ferramentas nos respetivos repositórios; não precisam deste hub em runtime.

## O que está incluído

| Caminho | Propósito |
|---|---|
| `registry.json` | Catálogo de projetos públicos e registos de maintainer claramente marcados. O relatório semanal filtra `kind=project` e `visibility=public`. |
| `template/` | Repositório inicial bilingue com documentação Windows/Linux e CI. |
| `tools/new-repo.py` | Cria um checkout irmão `devin-<nome>` a partir do template, inicializa Git e regista o repo em `registry.json` (validado contra o schema antes de escrever). `--dry-run` pré-visualiza sem efeitos. Não cria repositório no GitHub nem faz push. |
| `tools/weekly_repo_report.py` | Lê metadados públicos de commits do GitHub e gera um relatório HTML autónomo. O envio por email é opcional. |
| `tools/validate_registry.py` | Valida `registry.json` contra `registry.schema.json` — sem dependências, sai com erro nas violações. |
| `tools/reconcile_registry.py` | Reconcilia o registry contra a conta GitHub e os clones locais: entradas em falta, repos ausentes, campos version/tag obsoletos. Read-only. |
| `registry.schema.json` | JSON Schema (2020-12) do `registry.json`. |
| `capability-profile.schema.json` + `docs/capability-profile.md` | O contrato F10: perfis `corporate` (fail-closed, padrão) vs `personal`, chaves de capacidade e como extras declaram `requires:`. |
| `.github/workflows/` | Template de CI por projeto e workflows opcionais para publicar/enviar relatórios já existentes. |

O motor local de scout/ideação não faz parte deste repositório público. Os
workflows de notificação apenas entregam ficheiros de relatório fornecidos
pelo maintainer; não executam discovery, testes ou sessões de agentes.

## O método

Cada projeto adapta uma ferramenta comprovada com uma capacidade específica do
Devin que:

1. faz algo que a ferramenta base não consegue;
2. deixa de fazer sentido sem Devin; e
3. pode ser explicada numa frase.

As ferramentas do ecossistema são local-first e read-only por omissão, com
escritas explícitas quando necessárias e sem telemetria.

## Executar as ferramentas de manutenção

Requisitos: Python 3.10 ou superior e Git. Os scripts usam a biblioteca padrão
do Python. `gh` é opcional e só é necessário se decidires criar um repositório
remoto depois do scaffolding.

**Windows (PowerShell):**

```powershell
py -3 tools/new-repo.py history "Export and audit Devin session history"
py -3 tools/weekly_repo_report.py --days 7 --out report\weekly-repo-report.html
```

**Linux:**

```bash
python3 tools/new-repo.py history "Export and audit Devin session history"
python3 tools/weekly_repo_report.py --days 7 --out report/weekly-repo-report.html
```

`new-repo.py` recebe `<nome> "<descrição>"` mais opções. Valida um nome
kebab-case, cria um irmão `devin-<nome>` a partir de `template/`, executa
`git init -b main` e depois regista o repo em `registry.json` — o documento
resultante é validado contra `registry.schema.json` antes de qualquer
escrita, por isso uma violação do schema aborta sem efeitos secundários.
`--dry-run` mostra os ficheiros que criaria e a entrada que acrescentaria ao
registry sem tocar em nada; `--no-register` apenas gera o scaffold. `--kind`,
`--visibility` e `--wave` sobrepõem os defaults do registry
(`project`/`public`/`0`). Não cria um remote no GitHub. Revê os ficheiros
gerados e escolhe o remote/visibilidade explicitamente.

`weekly_repo_report.py` usa a API pública de commits do GitHub. `GITHUB_TOKEN`
é opcional e pode aumentar os limites de API. Opções:

| Opção | Propósito |
|---|---|
| `--registry PATH` | Registry JSON (padrão: `registry.json` deste repo). |
| `--out PATH` | Destino do relatório HTML. |
| `--days N` | Janela retrospetiva (padrão: 7). |
| `--max-commits N` | Limite mostrado por repo (padrão: 25). |
| `--timeout SECONDS` | Timeout HTTP (padrão: 15). |
| `--send HTML --to ADDRESS --from "Name <verified-address>"` | Envia um relatório existente; requer secrets SMTP e `REPORT_SENDER`. |

As duas ferramentas podem ser executadas no PowerShell ou num shell Linux com
os comandos acima.

## Relatório público semanal

O workflow GitHub Actions `weekly-repo-report` corre aos domingos e também
pode ser iniciado com `workflow_dispatch`. Publica um artifact HTML que inclui
apenas projetos públicos selecionados em `registry.json`.

O envio opcional por email requer estes GitHub Actions repository secrets:

- `MAILERSEND_SMTP_HOST`
- `MAILERSEND_SMTP_PORT`
- `MAILERSEND_SMTP_USER`
- `MAILERSEND_SMTP_PASSWORD`

E estas repository variables:

- `REPORT_RECIPIENT`: endereço de destino;
- `REPORT_SENDER`: identidade de remetente verificada pelo fornecedor de email.

Se faltar qualquer configuração, o artifact do relatório continua disponível e
o email é ignorado. O código público não contém endereço de remetente ou
recipiente predefinido.

Os workflows `scout-notify` e `testgen-notify` enviam um relatório fornecido
como input quando iniciados manualmente — os relatórios não ficam guardados
neste repositório. Um fork configura os seus próprios secrets/variables.

## Registry e privacidade

O registry distingue projetos públicos de registos de maintainer. O relatório
semanal filtra projetos públicos e não lê conteúdo de repositórios privados.
Paths pessoais, credenciais, endereços de serviços e dados de sessões não
pertencem a este repositório público.

## Funciona só com o Devin (modo Devin-only)

O hub em si é opcional — cada ferramenta do `registry.json` instala-se e corre
de forma autónoma. O que funciona localmente sem serviços externos:

- `registry.json` — JSON simples; lê, filtra, usa em scripts.
- `tools/validate_registry.py` — valida o registry contra o schema, sem deps.
- `tools/reconcile_registry.py` — audita registry vs GitHub vs clones locais.
  Usa `gh` para dados do GitHub (precisa de `gh auth` ou `GITHUB_TOKEN`);
  sem eles, ainda reporta os achados locais.
- `tools/new-repo.py` — gera um checkout local e regista-o em
  `registry.json` (`git init` apenas, sem chamadas ao GitHub; criar um
  remote é um passo separado e explícito). `--dry-run` não tem efeitos.
- `tools/weekly_repo_report.py --out report.html` — gera um relatório HTML
  autónomo. Lê a API pública de commits do GitHub, por isso precisa de acesso
  de rede não autenticado a `github.com` (`GITHUB_TOKEN` só aumenta os rate
  limits).
- O envio por email (`--send`) e os workflows GitHub Actions são extras
  opcionais de maintainer. Salta-os à vontade — precisam dos *teus* secrets
  SMTP, não dos nossos. Numa máquina restrita, correr o gerador localmente
  num agendamento (cron ou Task Scheduler) produz o mesmo relatório HTML sem
  qualquer email.

## Suporte de plataformas

Os scripts de manutenção Python funcionam em Windows e Linux. `new-repo.py`
invoca Git; criar um remote no GitHub é uma ação separada e explícita. O CI do
template testa projetos Python em Windows e Ubuntu; `devin-bridge` testa Node
nas duas plataformas.

## Contribuir

Issues e pull requests são bem-vindos. Projetos novos devem documentar
propósito, prior art, instalação e uso, plataformas suportadas, limitações e
como a capacidade Devin melhora a ferramenta base.

## Quando usar

- Você mantém o ecossistema Devin do Icaro0310 (ou faz fork do padrão) e precisa do registry, scaffolder, relatório semanal ou workflow `pypi-publish.yml` partilhado.
- Você está a começar um novo projeto `devin-*` e quer o template bilingue com docs, CI e convenções já em lugar (`tools/new-repo.py`).
- Você quer um relatório público de atividade que lê apenas metadados públicos de commits do GitHub — sem conteúdo de repos privados, sem dados de sessões.
- Você quer um único workflow de publicação PyPI por token reutilizado em todos os repos Python em vez de plumbing de publicação por repo.

## Quando NÃO usar

- Você é um utilizador final de uma ferramenta `devin-*` específica — instale o repositório dessa ferramenta; este hub é infraestrutura de mantenedor e não é necessário em runtime.
- Você procura o motor privado de scout/ideação — está deliberadamente não publicado neste repositório.
- Você quer relatórios por email out of the box — a entrega precisa dos *seus* segredos SMTP e de um remetente verificado; o artefacto HTML funciona sem nada disso.

## FAQ

**O que é o devin-powerups?** O hub público do mantenedor para o ecossistema da comunidade Devin. Contém o catálogo `registry.json` legível por máquina, o template bilingue de arranque, o scaffolder `new-repo.py`, o gerador de relatórios `weekly_repo_report.py`, e o workflow reutilizável `pypi-publish.yml` de GitHub Actions que os repos Python partilham.

**Preciso deste repo para usar as ferramentas do ecossistema?** Não. Cada projeto em `registry.json` instala-se e corre standalone a partir do seu próprio repositório. Este hub existe para o workflow do mantenedor — scaffolding, catalogação e reporting — não para utilizadores finais.

**O relatório semanal expõe dados privados?** Não. Filtra o registry para `kind=project` e `visibility=public`, e lê apenas a API pública de commits do GitHub. A entrega por email é opcional e usa segredos e variáveis que configura no seu próprio fork; se faltarem, o workflow mantém o artefacto HTML e salta o email.

**Como os outros repos publicam no PyPI?** Chamam o workflow reutilizável: `uses: Icaro0310/devin-powerups/.github/workflows/pypi-publish.yml@main` com um segredo `PYPI_API_TOKEN`. Um workflow por token, sem setup OIDC por repo.

## Licença

MIT — vê [LICENSE](LICENSE).
