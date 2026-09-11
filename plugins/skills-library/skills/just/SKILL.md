---
disable-model-invocation: false
name: just
user-invocable: true
description: Write and maintain justfiles for the just command runner (v1.58): recipes, parameters and [arg] options, attributes, settings, imports and modules, script recipes, built-in functions, and this user's devkit-based conventions. Use when the user mentions a justfile, just recipes, just settings, just modules, task automation with just, or asks to add, fix, or review commands run through just.
---

# Just Command Runner

Targets just 1.58.0. Facts below and in `references/` were verified against that version.

## Workflow

1. Check for `@sablier/devkit` in `package.json`. Present: start from `examples/devkit.just`. Absent: start from `examples/standalone.just`.
2. Settings first, then banner sections in the fixed order (DEPENDENCIES, CONSTANTS, COMMANDS, CHECKS, TESTS, UTILITIES). Read [references/patterns.md](references/patterns.md) for the conventions before writing a new file.
3. Declare every external tool in DEPENDENCIES as `tool := require("tool")` with a URL comment; invoke tools by bare name in bodies.
4. Put the alias line directly after each recipe body.
5. Verify: `just --list`, `just --summary`, `just --dry-run <recipe>`. Never run `just --fmt` or `just --dump`.

## Baseline settings

```just
set allow-duplicate-recipes
set allow-duplicate-variables
set shell := ["bash", "-euo", "pipefail", "-c"]
```

Add only when needed: `set unstable` (user-defined functions, `set lists`, `[cache]`), `set dotenv-load`, `set positional-arguments`, `set no-cd`, `set script-interpreter := ["bash", "-euo", "pipefail"]`. Avoid `set lazy` in files that rely on top-level `require()` checks; it skips unreferenced assignments.

## Most-used syntax

```just
# Doc comment shown in --list
[group("checks")]
[no-cd]
check +globs=GLOBS_PRETTIER:
    prettier --check {{ globs }}
alias pc := check

[arg("target", long, short, help="Build target")]
[confirm("Deploy " + env("APP", "app") + "?")]
[env("NODE_ENV", "production")]
[working-directory("apps/web")]
deploy target="prod": build && notify
    ./deploy.sh {{ target }}

[script("bash")]
multi:
    set -euo pipefail
    for f in *.md; do echo "$f"; done

import "./just/base.just"
import? "./local.just"
mod api "services/api"          # stable; no set unstable
all: api::build                  # depend on submodule recipes directly
```

Functions used most: `require("tool")`, `env("VAR", "default")`, `justfile_dir()`, `invocation_dir()`, `path_exists("p")`, `os()`, `arch()`, `shell("cmd")`, `datetime("%Y-%m-%d")`. Constants: `CYAN GREEN RED YELLOW BOLD NORMAL` (raw ANSI, no `-e` needed).

## Errors an agent hits on 1.58

- `if`/`assert` conditions must be comparisons: `path_exists("x") == "true"`, not `path_exists("x")`. Non-comparison conditions, `&&`, `||`, `!`, `if` without `else`, `which()`, `flag`/`multiple` arg keys all need `set unstable` + `set lists`.
- `[dragonflybsd]` is not an attribute; use `[dragonfly]`. OS attributes also apply to `set`, `mod`, `alias`, assignments.
- `{{ tool }}` from `require()` breaks on Windows paths. Use the bare name.
- `HEX` is lowercase (`HEXUPPER` exists). `PATH_SEP` is `/` or `\`; `PATH_VAR_SEP` is `:` or `;`.
- `runtime_directory()` and `executable_directory()` error outside Linux / on Windows.
- `set windows-shell` and `set windows-powershell` are deprecated; use `[windows]` on `set shell`.
- Two module candidates (`foo.just` and `foo/mod.just`) is an error, not a priority order.
- Empty `[confirm("")]` still prompts; pass `--yes` to skip.
- `&&` dependencies are not deduplicated against earlier dependencies in the same run.

## References

Read only the file needed:

- Settings table, lazy/eager, imports, modules and inheritance rules: [references/settings.md](references/settings.md)
- Parameters, `[arg]` keys, dependencies, complete attribute table, shell vs `[script]` vs shebang execution, Windows behavior: [references/recipes.md](references/recipes.md)
- Strings and f-strings, operators, user-defined functions, every built-in function, constants, lists, full CLI option and subcommand list: [references/syntax.md](references/syntax.md)
- File layout, banners, section order, groups, alias vocabulary, `_run-with-status`, devkit imports, monorepo modules: [references/patterns.md](references/patterns.md)
- Templates: [examples/devkit.just](examples/devkit.just) (minimal, imports devkit), [examples/standalone.just](examples/standalone.just) (full)

## No formatter

Do not use `just --fmt` or `just --dump`. The user has bespoke formatting the formatter does not respect. Preserve existing formatting.

## Fallback documentation

For anything not covered here: context7 MCP library `/websites/just_systems_man_en`, or https://just.systems/man/en/ (single page: https://just.systems/man/en/print.html). Source: https://github.com/casey/just.
