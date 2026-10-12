"use strict";

// Skeleton — canonical location: packages/<pkg>/adapters/vscode/extension.js
//
// Thin shell over `<pkg-cli> <cmd> --json`: it shells out to the CLI and
// renders the result — no check logic is reimplemented here. Modeled on
// devin-doctor's adapter (packages/doctor/adapters/vscode), the working
// example in docs/adapter-checklist.md.

const vscode = require("vscode");
const cp = require("child_process");

let statusBar;
let output;
// Monotonic counter — a slow check finishing late must not overwrite a
// newer verdict already rendered on the status bar.
let checkSeq = 0;

function config() {
  const c = vscode.workspace.getConfiguration("<pkgCamel>");
  return {
    executable: c.get("executable", "<pkg-cli>"),
    extraArgs: c.get("extraArgs", []),
  };
}

// Runs the CLI once and resolves {code, stdout, stderr}. Never throws on a
// non-zero exit — the CLI signals findings through exit codes, which are
// results, not errors.
function runCli(args) {
  const { executable, extraArgs } = config();
  return new Promise((resolve, reject) => {
    cp.execFile(
      executable,
      args.concat(extraArgs),
      { timeout: 120000, maxBuffer: 8 * 1024 * 1024 },
      (err, stdout, stderr) => {
        if (err && err.killed) {
          reject(new Error(`<pkg-cli> timed out after 120s`));
          return;
        }
        if (err && err.code === "ENOENT") {
          reject(
            new Error(
              `<pkg-cli> not found on PATH. Install it or set <pkgCamel>.executable.`,
            ),
          );
          return;
        }
        resolve({ code: err ? err.code : 0, stdout, stderr });
      },
    );
  });
}

// Pure renderer kept separate so tests can reach it without the editor.
// The CLI emits uppercase values; normalize before matching so a casing
// change upstream can never blank the badge.
function severityBadge(overall) {
  switch (String(overall || "").toLowerCase()) {
    case "fail":
      return { text: "$(error) <pkg>: FAIL", bg: new vscode.ThemeColor("statusBarItem.errorBackground") };
    case "warn":
      return { text: "$(warning) <pkg>: WARN", bg: new vscode.ThemeColor("statusBarItem.warningBackground") };
    case "pass":
      return { text: "$(pass) <pkg>: PASS", bg: undefined };
    default:
      return { text: "$(question) <pkg>: ?", bg: undefined };
  }
}

async function check() {
  const seq = ++checkSeq;
  statusBar.text = "$(sync~spin) <pkg>: running";
  statusBar.show();
  try {
    const { stdout, stderr } = await runCli(["check", "--json"]);
    let payload;
    try {
      payload = JSON.parse(stdout);
    } catch {
      output.appendLine(stdout);
      output.appendLine(stderr);
      throw new Error("<pkg-cli> did not return JSON — see output channel");
    }
    if (seq === checkSeq) {
      const badge = severityBadge(payload.overall);
      statusBar.text = badge.text;
      statusBar.backgroundColor = badge.bg;
      statusBar.show();
    }
    return payload;
  } catch (e) {
    if (seq === checkSeq) {
      statusBar.text = "$(error) <pkg>: unavailable";
      statusBar.tooltip = e.message;
      statusBar.show();
      vscode.window.showErrorMessage(e.message);
    }
    return null;
  }
}

async function openReport() {
  const doc = await vscode.workspace.openTextDocument({ language: "markdown" });
  const editor = await vscode.window.showTextDocument(doc, { preview: true });
  const { stdout, stderr } = await runCli(["report", "--md"]);
  await editor.edit((b) => b.insert(new vscode.Position(0, 0), stdout || stderr));
}

function activate(context) {
  output = vscode.window.createOutputChannel("<pkg>");
  statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
  statusBar.command = "<pkg>.check";
  statusBar.text = "$(pulse) <pkg>";
  statusBar.tooltip = "Click to run <pkg-cli> check";
  statusBar.show();

  context.subscriptions.push(
    output,
    statusBar,
    vscode.commands.registerCommand("<pkg>.check", check),
    vscode.commands.registerCommand("<pkg>.report", openReport),
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
// Test-only surface — pure internals reachable without the editor.
module.exports.__internals__ = { severityBadge };
