# devin-{{name}}

> **Projeto comunitário não oficial.** Sem afiliação, endosso ou patrocínio da
> Cognition AI. "Devin" é marca registada da Cognition AI.

**[English](README.md)** · Português (BR)

Descrição numa linha do que esta ferramenta faz.

## O problema

<!-- Dor real, com evidência. Quem sofre, quando, com que frequência. -->

## Trabalho anterior (prior art)

<!-- O que já existe para outros agentes/ferramentas. Sê honesto e linka.
     Este projeto adapta <X>; não reinventa a roda. -->

## O que o torna Devin-native

<!-- O diferencial. Tem de passar 3 testes:
     1. Lado a lado: faz algo que a base NÃO consegue de todo?
     2. Sem Devin: o extra desaparece se o Devin sair da equação?
     3. Uma frase: consegues explicá-lo sem jargão? -->

## Instalação

Requer Python ≥ 3.10 e `pipx`. No Windows (PowerShell), instala `pipx` com
`py -m pip install --user pipx`, executa `py -m pipx ensurepath` e reabre o
terminal. No Linux Debian/Ubuntu, executa `sudo apt install pipx python3-venv`
e `pipx ensurepath`; reabre o terminal.

Depois de criares um repositório público no GitHub para este projeto, instala:

```bash
pipx install "devin-{{name}} @ git+https://github.com/Icaro0310/devin-{{name}}.git"
```

## Uso

```bash
devin-{{name}} --help
```

## Suporte de plataformas

<!-- OBRIGATÓRIO — paridade Linux é convenção do projeto (ver README do
     hub). Tudo o que for entregue tem de funcionar em Windows E Linux.
     Indica os paths de dados de sessão (%APPDATA% vs XDG_DATA_HOME) e de
     config da UI (XDG_CONFIG_HOME), além dos overrides. Se algo não puder
     correr em Linux, diz isso em Limitações em vez de omitir. -->

Testado em **Windows e Linux** (o CI corre em `windows-latest` +
`ubuntu-latest`). No Linux, os dados de sessão usam por omissão
`~/.local/share/devin` e a config da UI `~/.config/Devin`. Documenta os
paths e overrides específicos que a ferramenta utilizar.

## Limitações

<!-- Sê explícito: internals privados/voláteis, comportamento por versão,
     o que NÃO faz. -->

## Desenvolvimento

```bash
pip install -e ".[dev]"
pytest
```

## Licença

MIT — vê [LICENSE](LICENSE).
