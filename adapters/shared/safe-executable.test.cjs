"use strict";

// Tests for the canonical safe-executable.cjs. Node's built-in runner:
//   node --test adapters/shared/safe-executable.test.cjs
// Not fanned out to adapters — they carry only the byte-identical
// safe-executable.cjs copy; config-restricted-check enforces lockstep.

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { resolveSafeExecutable, isInside } = require("./safe-executable.cjs");

function fixture() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "safeexe-"));
  const userBin = path.join(tmp, "usrbin");
  const ws = path.join(tmp, "repo");
  fs.mkdirSync(userBin);
  fs.mkdirSync(ws);
  const real = path.join(userBin, "devin-demo");
  const planted = path.join(ws, "devin-demo");
  for (const f of [real, planted]) {
    fs.writeFileSync(f, "#!/bin/sh\n");
    fs.chmodSync(f, 0o755);
  }
  const oldPath = process.env.PATH;
  process.env.PATH = ws + path.delimiter + userBin + path.delimiter + oldPath;
  return {
    tmp, ws, real, planted,
    restore() {
      process.env.PATH = oldPath;
      fs.rmSync(tmp, { recursive: true, force: true });
    },
  };
}

test("untrusted: a workspace-planted binary is skipped for the user's", () => {
  if (process.platform === "win32") return; // POSIX-mode fixtures
  const f = fixture();
  try {
    const r = resolveSafeExecutable("devin-demo", {
      workspaceDir: f.ws, trusted: false,
    });
    assert.equal(r && r.file, f.real);
  } finally { f.restore(); }
});

test("trusted: a workspace-local binary is allowed (PATH order wins)", () => {
  if (process.platform === "win32") return;
  const f = fixture();
  try {
    const r = resolveSafeExecutable("devin-demo", {
      workspaceDir: f.ws, trusted: true,
    });
    assert.equal(r && r.file, f.planted);
  } finally { f.restore(); }
});

test("untrusted: an explicit path inside the workspace is rejected", () => {
  if (process.platform === "win32") return;
  const f = fixture();
  try {
    assert.equal(
      resolveSafeExecutable(f.planted, {
        workspaceDir: f.ws, trusted: false,
      }),
      null,
    );
  } finally { f.restore(); }
});

test("missing executable resolves to null, not throw", () => {
  assert.equal(
    resolveSafeExecutable("devin-nonexistent-xyz-42", {}),
    null,
  );
});

test("isInside does not confuse prefix dirs with descendants", () => {
  assert.equal(isInside("/a/b/c", "/a"), true);
  assert.equal(isInside("/ab/c", "/a"), false);
  assert.equal(isInside("/a", "/a"), true);
});
