import { TARGET_NAMES, UiproError, resolveTargets } from './targets.js';
import { installInto, listSkills } from './install.js';

export const USAGE = `uipro - install the UI Pro skill pack for your coding agent

Usage:
  uipro init --ai <agent> [--global] [options]
  uipro list
  uipro --help

Agents:
  claude      Claude Code      (~/.claude/skills or ./.claude/skills)
  cursor      Cursor           (~/.cursor/skills or ./.cursor/skills)
  universal   Any agent        (~/.agents/skills or ./.agents/skills)
  all         every agent above

Options:
  --ai <agent>   Which agent to install for. Required for init.
  --global       Install into the home directory instead of the current project.
  --force        Overwrite skills that are already installed.
  --dry-run      Report what would change without writing anything.
  -h, --help     Show this message.

Examples:
  uipro init --ai claude --global      # ~/.claude/skills
  uipro init --ai cursor --global      # ~/.cursor/skills
  uipro init --ai universal --global   # ~/.agents/skills
`;

const FLAGS = new Set(['--global', '--force', '--dry-run']);

/** Parse argv (without node/script) into a command descriptor. */
export function parseArgs(argv) {
  const parsed = {
    command: null,
    ai: null,
    global: false,
    force: false,
    dryRun: false,
    help: false,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '-h' || arg === '--help') {
      parsed.help = true;
    } else if (FLAGS.has(arg)) {
      if (arg === '--global') parsed.global = true;
      if (arg === '--force') parsed.force = true;
      if (arg === '--dry-run') parsed.dryRun = true;
    } else if (arg === '--ai' || arg.startsWith('--ai=')) {
      const value = arg.startsWith('--ai=') ? arg.slice('--ai='.length) : argv[++i];
      if (!value) throw new UiproError('--ai requires a value.');
      parsed.ai = value;
    } else if (arg.startsWith('-')) {
      throw new UiproError(`Unknown option ${arg}. Run "uipro --help" for usage.`);
    } else if (parsed.command === null) {
      parsed.command = arg;
    } else {
      throw new UiproError(`Unexpected argument ${JSON.stringify(arg)}.`);
    }
  }

  return parsed;
}

function describe(target, result, dryRun) {
  const counts = { installed: 0, updated: 0, skipped: 0 };
  for (const item of result.results) counts[item.status] += 1;
  const verb = dryRun ? 'would install' : 'installed';
  const lines = [`${target.label} -> ${result.dir}`];
  lines.push(
    `  ${counts.installed} ${verb}, ${counts.updated} ${dryRun ? 'would update' : 'updated'}, ${counts.skipped} already present`
  );
  for (const item of result.results) {
    lines.push(`  ${item.status === 'skipped' ? '-' : '+'} ${item.name} (${item.status})`);
  }
  if (counts.skipped > 0 && !dryRun) {
    lines.push('  Re-run with --force to overwrite the skills already present.');
  }
  return lines.join('\n');
}

/**
 * Run the CLI. Returns a process exit code; never throws for user errors.
 *
 * @param {string[]} argv arguments after the node binary and script path
 * @param {{out?: (s: string) => void, err?: (s: string) => void, home?: string, cwd?: string, sourceDir?: string}} [io]
 */
export async function run(argv, io = {}) {
  const out = io.out || ((s) => process.stdout.write(`${s}\n`));
  const err = io.err || ((s) => process.stderr.write(`${s}\n`));

  let args;
  try {
    args = parseArgs(argv);
  } catch (error) {
    err(error.message);
    return 1;
  }

  if (args.help || (!args.command && argv.length === 0)) {
    out(USAGE);
    return 0;
  }

  try {
    if (args.command === 'list') {
      const skills = await listSkills(io.sourceDir);
      out(`${skills.length} skill${skills.length === 1 ? '' : 's'} in the UI Pro pack:`);
      for (const skill of skills) out(`  ${skill.name}`);
      return 0;
    }

    if (args.command !== 'init') {
      err(`Unknown command ${JSON.stringify(args.command)}. Run "uipro --help" for usage.`);
      return 1;
    }

    if (!args.ai) {
      err(`init requires --ai. Expected one of: ${TARGET_NAMES.join(', ')}, all.`);
      return 1;
    }

    const targets = resolveTargets(args.ai, { global: args.global, home: io.home, cwd: io.cwd });
    for (const target of targets) {
      const result = await installInto(target, {
        force: args.force,
        dryRun: args.dryRun,
        sourceDir: io.sourceDir,
      });
      out(describe(target, result, args.dryRun));
    }
    if (!args.global) {
      out('Installed into the current project. Pass --global to install for every project.');
    }
    return 0;
  } catch (error) {
    if (error instanceof UiproError) {
      err(error.message);
      return 1;
    }
    err(`uipro failed: ${error.message}`);
    return 1;
  }
}
