import os from 'node:os';
import path from 'node:path';

/**
 * Where each supported agent looks for skills.
 *
 * `global` is relative to the user's home directory, `project` is relative to
 * the directory `uipro` was run from. Both end in `skills` because every
 * supported agent discovers skills as one directory per skill inside it.
 */
export const TARGETS = {
  claude: {
    label: 'Claude Code',
    global: ['.claude', 'skills'],
    project: ['.claude', 'skills'],
  },
  cursor: {
    label: 'Cursor',
    global: ['.cursor', 'skills'],
    project: ['.cursor', 'skills'],
  },
  universal: {
    label: 'Universal (AGENTS.md convention)',
    global: ['.agents', 'skills'],
    project: ['.agents', 'skills'],
  },
};

export const TARGET_NAMES = Object.keys(TARGETS);

export class UiproError extends Error {}

/**
 * Resolve the skills directory for one agent.
 *
 * @param {string} ai one of TARGET_NAMES
 * @param {object} [options]
 * @param {boolean} [options.global] install into the home directory instead of the project
 * @param {string} [options.home] override the home directory (tests)
 * @param {string} [options.cwd] override the project directory (tests)
 * @returns {{ai: string, label: string, dir: string, scope: 'global'|'project'}}
 */
export function resolveTarget(ai, options = {}) {
  const key = String(ai || '').toLowerCase();
  const target = TARGETS[key];
  if (!target) {
    throw new UiproError(
      `Unknown --ai value ${JSON.stringify(ai)}. Expected one of: ${TARGET_NAMES.join(', ')}, all.`
    );
  }
  const scope = options.global ? 'global' : 'project';
  const base = scope === 'global' ? options.home || os.homedir() : options.cwd || process.cwd();
  return {
    ai: key,
    label: target.label,
    scope,
    dir: path.join(base, ...target[scope]),
  };
}

/** Resolve every target named by `ai`, where `all` fans out to all of them. */
export function resolveTargets(ai, options = {}) {
  const key = String(ai || '').toLowerCase();
  const names = key === 'all' ? TARGET_NAMES : [key];
  return names.map((name) => resolveTarget(name, options));
}
