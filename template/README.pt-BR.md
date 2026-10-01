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

```bash
pipx install devin-{{name}}
```

## Uso

```bash
devin-{{name}} --help
```

## Suporte de plataformas

<!-- OBRIGATÓRIO — paridade Linux é convenção do projeto (ver README do
     hub). Tudo o que for entregue tem de funcionar em Windows E Linux.
     Indica as plataformas testadas e os paths por plataforma
     (%APPDATA% vs ~/.config/devin) ou overrides. Se algo não puder correr
     em Linux, diz isso em Limitações em vez de omitir. -->

Testado em **Windows e Linux** (o CI corre em `windows-latest` +
`ubuntu-latest`).

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
