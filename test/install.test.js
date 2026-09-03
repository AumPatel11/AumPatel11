import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { installInto, listSkills, BUNDLED_SKILLS_DIR } from '../src/install.js';
import { resolveTarget } from '../src/targets.js';

async function tempHome() {
  return fs.mkdtemp(path.join(os.tmpdir(), 'uipro-test-'));
}

test('the bundled pack exposes every skill directory containing SKILL.md', async () => {
  const skills = await listSkills(BUNDLED_SKILLS_DIR);
  assert.ok(skills.length >= 3);
  for (const skill of skills) {
    await fs.access(path.join(skill.dir, 'SKILL.md'));
  }
});

test('install writes every skill into the global claude directory', async () => {
  const home = await tempHome();
  const target = resolveTarget('claude', { global: true, home });
  const result = await installInto(target);

  assert.equal(result.dir, path.join(home, '.claude', 'skills'));
  assert.ok(result.results.every((r) => r.status === 'installed'));
  const installed = await fs.readdir(result.dir);
  assert.deepEqual(installed.sort(), result.results.map((r) => r.name).sort());
  const body = await fs.readFile(path.join(result.dir, 'ui-components', 'SKILL.md'), 'utf8');
  assert.match(body, /name: ui-components/);
});

test('a second install skips existing skills and preserves local edits', async () => {
  const home = await tempHome();
  const target = resolveTarget('cursor', { global: true, home });
  await installInto(target);

  const edited = path.join(target.dir, 'ui-components', 'SKILL.md');
  await fs.writeFile(edited, 'local edit');

  const again = await installInto(target);
  assert.ok(again.results.every((r) => r.status === 'skipped'));
  assert.equal(await fs.readFile(edited, 'utf8'), 'local edit');
});

test('force overwrites an existing skill', async () => {
  const home = await tempHome();
  const target = resolveTarget('universal', { global: true, home });
  await installInto(target);

  const overwritten = path.join(target.dir, 'ui-components', 'SKILL.md');
  await fs.writeFile(overwritten, 'local edit');

  const again = await installInto(target, { force: true });
  assert.ok(again.results.every((r) => r.status === 'updated'));
  assert.match(await fs.readFile(overwritten, 'utf8'), /name: ui-components/);
});

test('dry run reports the plan without touching the filesystem', async () => {
  const home = await tempHome();
  const target = resolveTarget('claude', { global: true, home });
  const result = await installInto(target, { dryRun: true });

  assert.ok(result.results.every((r) => r.status === 'installed'));
  await assert.rejects(fs.access(target.dir));
});

test('an empty source directory is an error, not a silent success', async () => {
  const home = await tempHome();
  const empty = path.join(home, 'empty');
  await fs.mkdir(empty);
  const target = resolveTarget('claude', { global: true, home });
  await assert.rejects(installInto(target, { sourceDir: empty }), /No skills found/);
});
