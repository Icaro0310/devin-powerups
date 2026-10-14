"use strict";

// Tests for the canonical safe-executable.cjs. Node's built-in runner:
//   node --test adapters/shared/safe-executable.test.cjs
// Not fanned out to adapters — they carry only the byte-identical
// safe-executable.cjs copy; config-restricted-check enforces lockstep.
//
// Fixtures are platform-aware from the start: PATHEXT on Windows never
// matches an extensionless file, so every fixture binary carries the
// real executable suffix (".EXE", matching PATHEXT's case so resolved
// paths string-compare equal).

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const {
  resolveSafeExecutable,
  isInside,
  __internals__,
} = require("./safe-executable.cjs");

const EXE = process.platform === "win32" ? ".EXE" : "";

function fixture() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "safeexe-"));
  const userBin = path.join(tmp, "usrbin");
  const ws = path.join(tmp, "repo");
  fs.mkdirSync(userBin);
  fs.mkdirSync(ws);
  const real = path.join(userBin, "devin-demo" + EXE);
  const planted = path.join(ws, "devin-demo" + EXE);
  for (const f of [real, planted]) {
    fs.writeFileSync(f, "x");
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
  const f = fixture();
  try {
    const r = resolveSafeExecutable("devin-demo", {
      workspaceDirs: [f.ws], trusted: false,
    });
    assert.equal(r && r.file, f.real);
  } finally { f.restore(); }
});

test("trusted: a workspace-local binary is allowed (PATH order wins)", () => {
  const f = fixture();
  try {
    const r = resolveSafeExecutable("devin-demo", {
      workspaceDirs: [f.ws], trusted: true,
    });
    assert.equal(r && r.file, f.planted);
  } finally { f.restore(); }
});

test("untrusted: an explicit path inside the workspace is rejected", () => {
  const f = fixture();
  try {
    assert.equal(
      resolveSafeExecutable(f.planted, {
        workspaceDirs: [f.ws], trusted: false,
      }),
      null,
    );
  } finally { f.restore(); }
});

test("untrusted: a PATH symlink into the workspace is rejected", (t) => {
  const f = fixture();
  const linkDir = fs.mkdtempSync(path.join(os.tmpdir(), "safeexe-link-"));
  const link = path.join(linkDir, "devin-demo" + EXE);
  try {
    fs.symlinkSync(f.planted, link);
  } catch {
    t.skip("symlink needs privilege on this platform");
    return;
  }
  const oldPath = process.env.PATH;
  process.env.PATH = linkDir;
  try {
    const r = resolveSafeExecutable("devin-demo", {
      workspaceDirs: [f.ws], trusted: false,
    });
    assert.equal(r, null);
  } finally {
    process.env.PATH = oldPath;
    fs.rmSync(linkDir, { recursive: true, force: true });
    f.restore();
  }
});

test("untrusted: a symlinked workspace ROOT still rejects its binaries", (t) => {
  const f = fixture();
  const linkDir = fs.mkdtempSync(path.join(os.tmpdir(), "safeexe-wslink-"));
  const wsLink = path.join(linkDir, "repo-link");
  try {
    fs.symlinkSync(f.ws, wsLink, "dir");
  } catch {
    t.skip("symlink needs privilege on this platform");
    return;
  }
  try {
    const r = resolveSafeExecutable("devin-demo", {
      workspaceDirs: [wsLink], trusted: false,
    });
    assert.equal(r && r.file, f.real);
  } finally {
    fs.rmSync(linkDir, { recursive: true, force: true });
    f.restore();
  }
});

test("untrusted: multi-root — a binary in the SECOND folder is rejected", () => {
  const f = fixture();
  const ws2 = fs.mkdtempSync(path.join(os.tmpdir(), "safeexe-ws2-"));
  const planted2 = path.join(ws2, "devin-demo" + EXE);
  fs.writeFileSync(planted2, "x");
  fs.chmodSync(planted2, 0o755);
  const oldPath = process.env.PATH;
  process.env.PATH = ws2;
  try {
    const r = resolveSafeExecutable("devin-demo", {
      workspaceDirs: [f.ws, ws2], trusted: false,
    });
    assert.equal(r, null);
  } finally {
    process.env.PATH = oldPath;
    fs.rmSync(ws2, { recursive: true, force: true });
    f.restore();
  }
});

test("opts.env.PATH overrides the process PATH for the walk", () => {
  const f = fixture();
  try {
    const r = resolveSafeExecutable("devin-demo", {
      env: { PATH: path.dirname(f.real) },
      trusted: true,
    });
    assert.equal(r && r.file, f.real);
  } finally { f.restore(); }
});

test("relative PATH dir resolves against the workspace, not the host cwd", () => {
  const f = fixture();
  const toolsBin = path.join(f.ws, "tools", "bin");
  fs.mkdirSync(toolsBin, { recursive: true });
  const tool = path.join(toolsBin, "devin-demo" + EXE);
  fs.writeFileSync(tool, "x");
  fs.chmodSync(tool, 0o755);
  try {
    // trusted: the repo tools dir wins (legacy spawn-cwd semantics)
    const ok = resolveSafeExecutable("devin-demo", {
      env: { PATH: "tools/bin" },
      workspaceDirs: [f.ws],
      trusted: true,
    });
    assert.equal(ok && ok.file, tool);
    // untrusted: the same entry is inside the workspace — rejected
    const no = resolveSafeExecutable("devin-demo", {
      env: { PATH: "tools/bin" },
      workspaceDirs: [f.ws],
      trusted: false,
    });
    assert.equal(no, null);
  } finally { f.restore(); }
});

test("a '..'-prefixed dir INSIDE the workspace is not outside it", () => {
  assert.equal(isInside("/ws/..tools/x", "/ws"), true);
  assert.equal(isInside("/ws/x", "/ws"), true);
  assert.equal(isInside("/ws/../outside", "/ws"), false);
});

test("resolveShimEntry reads the %~dp0 and %dp0% launcher forms", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "safeexe-shim-"));
  try {
    const entry = path.join(dir, "sub", "x.js");
    fs.mkdirSync(path.dirname(entry));
    fs.writeFileSync(entry, "x");
    for (const body of [
      '"%~dp0\\sub\\x.js" %*',
      '"%dp0%sub\\x.js" %*',
    ]) {
      const shim = path.join(dir, "x" + body.length + ".cmd");
      fs.writeFileSync(shim, body);
      assert.equal(
        __internals__.resolveShimEntry(shim, null),
        path.join(dir, "sub", "x.js"),
      );
    }
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
});

test("missing executable resolves to null, not throw", () => {
  assert.equal(resolveSafeExecutable("devin-nonexistent-xyz-42", {}), null);
});

test("isInside does not confuse prefix dirs with descendants", () => {
  assert.equal(isInside("/a/b/c", "/a"), true);
  assert.equal(isInside("/ab/c", "/a"), false);
  assert.equal(isInside("/a", "/a"), true);
});
