# uipro

Installs the UI Pro skill pack into whichever coding agent you use. Skills are
plain directories containing a `SKILL.md`, so the same pack works for Claude
Code, Cursor, and anything that reads the `~/.agents/skills` convention.

## Install globally

```sh
uipro init --ai claude --global      # ~/.claude/skills/
uipro init --ai cursor --global      # ~/.cursor/skills/
uipro init --ai universal --global   # ~/.agents/skills/
uipro init --ai all --global         # all three
```

## Install for one project

Drop `--global` and the pack lands in the current directory instead.

```sh
uipro init --ai claude               # ./.claude/skills/
```

## Options

| Flag | Effect |
| --- | --- |
| `--ai <agent>` | `claude`, `cursor`, `universal`, or `all`. Required for `init`. |
| `--global` | Install into the home directory rather than the project. |
| `--force` | Overwrite skills that are already installed. |
| `--dry-run` | Print what would change without writing. |

A skill that already exists is skipped rather than overwritten, so re-running
`init` never discards edits you made by hand. Use `--force` when you do want the
bundled version back.

Run `uipro list` to see what is in the pack.

## What is in the pack

- **ui-components** - building and refactoring interface components against an existing codebase.
- **ui-accessibility** - auditing and fixing keyboard, semantics, naming, and contrast problems.
- **ui-design-review** - critiquing a screen and returning ranked, specific fixes.

## Development

```sh
npm test
```
