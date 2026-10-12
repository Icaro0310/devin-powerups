"use strict";

// Skeleton test for the <pkg> VS Code face — minimal vscode stub injected
// before requiring the extension, enough for the pure rendering paths to
// run outside the editor. Modeled on devin-doctor's extension.test.js.

const vscodeStub = {
  ThemeColor: class {
    constructor(id) {
      this.id = id;
    }
  },
  StatusBarAlignment: { Left: 1, Right: 2 },
  window: {
    createStatusBarItem: () => ({ show() {}, hide() {} }),
    createOutputChannel: () => ({ appendLine() {}, clear() {}, show() {} }),
    showWarningMessage: () => Promise.resolve(),
    showErrorMessage: () => Promise.resolve(),
    showTextDocument: () => Promise.resolve({ edit: async () => true }),
  },
  workspace: {
    getConfiguration: () => ({ get: (k, d) => (k === "executable" ? "<pkg-cli>" : d) }),
    openTextDocument: () => Promise.resolve({}),
  },
  commands: { registerCommand: () => ({ dispose() {} }) },
};

const Module = require("module");
const origRequire = Module.prototype.require;
Module.prototype.require = function (id) {
  if (id === "vscode") return vscodeStub;
  return origRequire.apply(this, arguments);
};

const { __internals__ } = require("../extension.js");
const test = require("node:test");
const assert = require("node:assert");

test("severityBadge maps CLI overall values case-insensitively", () => {
  const badge = __internals__.severityBadge;
  assert.strictEqual(badge("PASS").text, "$(pass) <pkg>: PASS");
  assert.strictEqual(badge("warn").text, "$(warning) <pkg>: WARN");
  assert.strictEqual(badge("FAIL").text, "$(error) <pkg>: FAIL");
  assert.strictEqual(badge("FAIL").bg.id, "statusBarItem.errorBackground");
  assert.strictEqual(badge("bogus").text, "$(question) <pkg>: ?");
  assert.strictEqual(badge(undefined).text, "$(question) <pkg>: ?");
});
