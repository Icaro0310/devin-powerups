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
| `tools/new-repo.py` | Cria um checkout irmão `devin-<nome>` a partir do template e inicializa Git. Não cria repositório no GitHub nem faz push. |
| `tools/weekly_repo_report.py` | Lê metadados públicos de commits do GitHub e gera um relatório HTML autónomo. O envio por email é opcional. |
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

`new-repo.py` recebe exatamente `<nome> "<descrição>"`. Valida um nome
kebab-case, cria um irmão `devin-<nome>` a partir de `template/`, executa
`git init -b main` e mostra os próximos passos. Não cria um remote no GitHub.
Revê os ficheiros gerados e escolhe o remote/visibilidade explicitamente.

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
- `tools/new-repo.py` — gera um checkout local (`git init` apenas, sem
  chamadas ao GitHub; criar um remote é um passo separado e explícito).
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

## Licença

MIT — vê [LICENSE](LICENSE).
