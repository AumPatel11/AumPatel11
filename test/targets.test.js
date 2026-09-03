import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { resolveTarget, resolveTargets, UiproError } from '../src/targets.js';

const home = '/home/tester';
const cwd = '/work/project';

test('global targets resolve under the home directory', () => {
  assert.equal(resolveTarget('claude', { global: true, home }).dir, path.join(home, '.claude', 'skills'));
  assert.equal(resolveTarget('cursor', { global: true, home }).dir, path.join(home, '.cursor', 'skills'));
  assert.equal(resolveTarget('universal', { global: true, home }).dir, path.join(home, '.agents', 'skills'));
});

test('project targets resolve under the working directory', () => {
  const target = resolveTarget('claude', { cwd });
  assert.equal(target.dir, path.join(cwd, '.claude', 'skills'));
  assert.equal(target.scope, 'project');
});

test('agent name is case insensitive', () => {
  assert.equal(resolveTarget('CLAUDE', { global: true, home }).ai, 'claude');
});

test('unknown agent is rejected with the valid list', () => {
  assert.throws(() => resolveTarget('copilot'), (err) => {
    assert.ok(err instanceof UiproError);
    assert.match(err.message, /claude, cursor, universal/);
    return true;
  });
});

test('all fans out to every target', () => {
  const targets = resolveTargets('all', { global: true, home });
  assert.deepEqual(targets.map((t) => t.ai), ['claude', 'cursor', 'universal']);
});
