import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { parseArgs, run } from '../src/cli.js';

function capture() {
  const out = [];
  const err = [];
  return { out: (s) => out.push(s), err: (s) => err.push(s), stdout: () => out.join('\n'), stderr: () => err.join('\n') };
}

async function tempHome() {
  return fs.mkdtemp(path.join(os.tmpdir(), 'uipro-cli-'));
}

test('parseArgs reads the documented init invocation', () => {
  const args = parseArgs(['init', '--ai', 'claude', '--global']);
  assert.equal(args.command, 'init');
  assert.equal(args.ai, 'claude');
  assert.equal(args.global, true);
});

test('parseArgs accepts --ai=value', () => {
  assert.equal(parseArgs(['init', '--ai=cursor']).ai, 'cursor');
});

test('parseArgs rejects unknown options', () => {
  assert.throws(() => parseArgs(['init', '--nope']), /Unknown option/);
});

test('uipro init --ai claude --global installs into ~/.claude/skills', async () => {
  const home = await tempHome();
  const io = { ...capture(), home };
  const code = await run(['init', '--ai', 'claude', '--global'], io);

  assert.equal(code, 0);
  const installed = await fs.readdir(path.join(home, '.claude', 'skills'));
  assert.ok(installed.includes('ui-components'));
  assert.match(io.stdout(), /\.claude/);
});

test('uipro init --ai all --global installs into all three directories', async () => {
  const home = await tempHome();
  const io = { ...capture(), home };
  assert.equal(await run(['init', '--ai', 'all', '--global'], io), 0);

  for (const dir of ['.claude', '.cursor', '.agents']) {
    const installed = await fs.readdir(path.join(home, dir, 'skills'));
    assert.ok(installed.includes('ui-accessibility'), `${dir} missing skills`);
  }
});

test('without --global the install lands in the project directory', async () => {
  const cwd = await tempHome();
  const io = { ...capture(), cwd };
  assert.equal(await run(['init', '--ai', 'cursor'], io), 0);
  await fs.access(path.join(cwd, '.cursor', 'skills', 'ui-components', 'SKILL.md'));
  assert.match(io.stdout(), /Pass --global/);
});

test('init without --ai fails with a usable message', async () => {
  const io = capture();
  assert.equal(await run(['init'], io), 1);
  assert.match(io.stderr(), /requires --ai/);
});

test('an unknown agent exits non-zero and writes nothing', async () => {
  const home = await tempHome();
  const io = { ...capture(), home };
  assert.equal(await run(['init', '--ai', 'copilot', '--global'], io), 1);
  await assert.rejects(fs.access(path.join(home, '.claude')));
});

test('an unknown command exits non-zero', async () => {
  const io = capture();
  assert.equal(await run(['install'], io), 1);
  assert.match(io.stderr(), /Unknown command/);
});

test('--help prints usage and exits zero', async () => {
  const io = capture();
  assert.equal(await run(['--help'], io), 0);
  assert.match(io.stdout(), /uipro init --ai claude --global/);
});

test('list names the bundled skills', async () => {
  const io = capture();
  assert.equal(await run(['list'], io), 0);
  assert.match(io.stdout(), /ui-design-review/);
});
