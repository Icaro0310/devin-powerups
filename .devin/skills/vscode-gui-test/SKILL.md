---
name: vscode-gui-test
description: "Testar extensões VS Code/VSCodium end-to-end em Linux headless-ish: tarball + --remote-debugging-port + CDP (driver em tools/cdp-drive.mjs), sem X interativo, sem deps"
triggers:
  - model
---

# VS Code / VSCodium GUI testing via CDP

Técnica provada 2026-10-14 (G3 do agent-sessions): conduzir a UI real de
uma instância VS Code/VSCodium instalada de tarball, verificar
contribuições (views, chat participants, commands) e produzir evidência
visual — tudo sem monitor interativo e sem dependências além de Node ≥22
(WebSocket/fetch nativos).

## Setup

- **Binários**: VSCodium via GitHub releases tarball; VS Code official via
  `https://update.code.visualstudio.com/latest/linux-x64/stable` (redirect
  → tarball). Extrair para `/tmp/vscode*` — nada de root.
- **Electron sem sandbox**: tarball perde o setuid do `chrome-sandbox` →
  arrancar sempre com `--no-sandbox` (senão o processo morre silencioso).
- **CLI vs binário**: `bin/code` é o wrapper CLI (aceita
  `--install-extension`, `--extensions-dir`, `--user-data-dir`); o `code`
  da raiz é o Electron puro e rejeita essas flags.
- **Profile isolado**: `--extensions-dir /tmp/x/extensions
  --user-data-dir /tmp/x/user` — mantém o teste hermético.
- **Marketplace VSIX**: `.../_apis/public/gallery/publishers/<pub>/
  vsextensions/<name>/latest/vspackage` devolve **gzip** — `gunzip` antes
  de `--install-extension`. `github.copilot-chat` vem **bundled** no VS
  Code ≥1.140 (`resources/app/extensions/`), não precisa de marketplace.
- **Debug**: `--remote-debugging-port=<N>` + abrir um workspace. Targets
  em `http://127.0.0.1:<N>/json`; o workbench é o target `vscode-file://`.

## Driver

`tools/cdp-drive.mjs` — um ficheiro, zero deps:

```
node tools/cdp-drive.mjs --port 9333 --list                 # targets
node tools/cdp-drive.mjs --port 9333 --eval 'JS expr'       # DOM probe
node tools/cdp-drive.mjs --port 9333 --type '@sess'         # char events
node tools/cdp-drive.mjs --port 9333 --key Enter            # tecla
node tools/cdp-drive.mjs --port 9333 --click 640,400        # rato
node tools/cdp-drive.mjs --port 9333 --shot /tmp/o.png      # screenshot
node tools/cdp-drive.mjs --port 9333 --eval-file f.js       # script
```

Para sequências longas, escrever um `.mjs` ad-hoc que replica o padrão
(fetch targets → WebSocket → `Runtime.evaluate`/`Input.*`) — o driver
cobre os primitivos; orquestração fica no script do teste.

## Gotchas medidos

- **Monaco/suggest**: `Input.insertText` injeta texto mas NÃO dispara o
  suggest widget. Para completions (`@participants`, snippets) usar
  `Input.dispatchKeyEvent` com `type:'char'`.
- **Screenshots**: `Page.captureScreenshot` (CDP) captura a janela sem
  depender do window manager — preferir a `spectacle`/scrot quando a
  janela pode estar tapada. Se o WM interessa: KDE Wayland → script KWin
  via `gdbus org.kde.KWin /Scripting loadScript <file>` +
  `workspace.activeWindow`.
- **Reload**: `Ctrl+R` em VS Code é "Open Recent", não reload. Para
  recarregar extension host usar `workbench.action.reloadWindow` ou
  relançar o processo — o extension host sobrevive a Ctrl+R (um handler
  instrumentado só corre depois de reload REAL).
- **`Runtime.evaluate`**: top-level `return` é ilegal — embrulhar em
  IIFE; promessas precisam de `awaitPromise:true`.
- **Self-kill**: `pkill -f <pattern>` mata o próprio shell se o pattern
  constar no cmdline — usar `pgrep`+`kill <pid>` ou pattern que não se
  auto-matcheia (aprendido duas vezes nesta sessão).
- **Chat participants**: "Language model unavailable" no primeiro submit
  é warmup do workbench (ver `learned-verificacao`), não falha do
  participant; VS Code 1.140 resolve model free built-in sem sign-in.
