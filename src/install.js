import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { UiproError } from './targets.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));

/** Directory holding the skills that ship with this package. */
export const BUNDLED_SKILLS_DIR = path.join(HERE, '..', 'skills');

/**
 * List the skills available in a source directory. A skill is any immediate
 * subdirectory containing a SKILL.md; anything else is ignored so that stray
 * files in the pack never get installed.
 */
export async function listSkills(sourceDir = BUNDLED_SKILLS_DIR) {
  let entries;
  try {
    entries = await fs.readdir(sourceDir, { withFileTypes: true });
  } catch (err) {
    if (err.code === 'ENOENT') {
      throw new UiproError(`Skill source directory not found: ${sourceDir}`);
    }
    throw err;
  }

  const skills = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const dir = path.join(sourceDir, entry.name);
    try {
      await fs.access(path.join(dir, 'SKILL.md'));
    } catch {
      continue;
    }
    skills.push({ name: entry.name, dir });
  }
  return skills.sort((a, b) => a.name.localeCompare(b.name));
}

async function copyDir(from, to) {
  await fs.mkdir(to, { recursive: true });
  const entries = await fs.readdir(from, { withFileTypes: true });
  for (const entry of entries) {
    const src = path.join(from, entry.name);
    const dest = path.join(to, entry.name);
    if (entry.isDirectory()) {
      await copyDir(src, dest);
    } else if (entry.isFile()) {
      await fs.copyFile(src, dest);
    }
  }
}

async function exists(target) {
  try {
    await fs.access(target);
    return true;
  } catch {
    return false;
  }
}

/**
 * Install every bundled skill into one resolved target directory.
 *
 * Existing skills are left alone unless `force` is set, so re-running `uipro
 * init` never silently discards a skill the user edited by hand.
 *
 * @returns {Promise<{dir: string, results: Array<{name: string, status: 'installed'|'updated'|'skipped'}>}>}
 */
export async function installInto(target, options = {}) {
  const { force = false, dryRun = false, sourceDir = BUNDLED_SKILLS_DIR } = options;
  const skills = await listSkills(sourceDir);
  if (skills.length === 0) {
    throw new UiproError(`No skills found in ${sourceDir}.`);
  }

  const results = [];
  for (const skill of skills) {
    const dest = path.join(target.dir, skill.name);
    const present = await exists(dest);
    if (present && !force) {
      results.push({ name: skill.name, status: 'skipped' });
      continue;
    }
    const status = present ? 'updated' : 'installed';
    if (!dryRun) {
      if (present) await fs.rm(dest, { recursive: true, force: true });
      await copyDir(skill.dir, dest);
    }
    results.push({ name: skill.name, status });
  }

  return { dir: target.dir, results };
}
