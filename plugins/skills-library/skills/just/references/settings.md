# Settings, Modules, and Imports

Verified against just 1.58.0.

## Settings

Syntax: `set name` (boolean, equals `set name := true`) or `set name := value`. Each setting at most once per file, anywhere in the file (not only at the top). Values may be const expressions (no backticks, no function calls). Settings are per-module: a submodule does not inherit `set unstable`, `set shell`, or any other parent setting.

| Setting                    | Type / default                 | Purpose and notes                                                                                                                                                             |
| -------------------------- | ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `allow-duplicate-recipes`  | bool / false                   | Later recipe with the same name replaces the earlier one (within a file).                                                                                                    |
| `allow-duplicate-variables`| bool / false                   | Later variable with the same name replaces the earlier one (within a file).                                                                                                  |
| `default-list`             | bool / false                   | `just` with no arguments lists recipes instead of running the default recipe. CLI: `--default-list`. (1.52)                                                                  |
| `default-script`           | bool / false                   | Recipes are `[script]` recipes by default; override per recipe with `[shell]`. (1.52)                                                                                        |
| `dotenv-command`           | string (list with lists) / none | Run a command with the configured shell and load its stdout as an env file. Root module only. Skipped under `--dry-run`. Conflicts with `dotenv-filename`. (1.54)         |
| `dotenv-filename`          | string or list / `.env`        | Env file name(s) searched in the working directory and its ancestors. Implies loading. (list form 1.53)                                                                     |
| `dotenv-load`              | bool / false                   | Load `.env` from the working directory or an ancestor.                                                                                                                       |
| `dotenv-override`          | bool / false                   | Env file values override variables already in the environment. (1.45)                                                                                                        |
| `dotenv-path`              | string or list / none          | Env file path(s) relative to the working directory only, no ancestor search. Overrides `dotenv-filename`. Missing file is silent unless `dotenv-required`. (list form 1.53) |
| `dotenv-required`          | bool / false                   | Error if no env file is found.                                                                                                                                               |
| `export`                   | bool / false                   | Export all variables as environment variables. Parameters are exported too.                                                                                                  |
| `fallback`                 | bool / false                   | If the first recipe on the command line is not found, retry with the justfile in a parent directory. Stops at a justfile without `fallback`.                                 |
| `guards`                   | bool / false                   | Enable the `?` line-prefix sigil in recipe bodies. Without it `?` is part of the command. (1.47)                                                                             |
| `ignore-comments`          | bool / false                   | Skip recipe body lines starting with `#` in shell (linewise) recipes: not echoed, not evaluated. Does not apply to `[script]` or shebang recipes. Unrelated to `--list`.    |
| `indentation`              | string / none                  | Recipe body indentation used by `--fmt` and `--dump`. (1.56)                                                                                                                 |
| `lazy`                     | bool / false                   | Evaluate variables only when used. Mark exceptions with `eager x := ...`. Respected in submodules. (1.47)                                                                    |
| `lists`                    | bool / false, unstable         | Enable list values, list operators, `split()`, `show()`, `which()`, `bool()`, mapped dependencies. Requires `set unstable`. (1.53)                                          |
| `minimum-version`          | string / none                  | Error if running just is older than `"MAJOR.MINOR.PATCH"`. Put it first in the file. (1.55)                                                                                  |
| `no-cd`                    | bool / false                   | Recipes run in the invocation directory, not the justfile directory. Affects only recipe cwd, not dotenv search, backticks, or `shell()`. Conflicts with `working-directory`. (1.51) |
| `no-exit-message`          | bool / false                   | Suppress the error message when a recipe fails. `[exit-message]` re-enables per recipe. (1.39)                                                                              |
| `positional-arguments`     | bool / false                   | Pass recipe arguments as `$0`, `$1`, ... to the shell in addition to `{{ }}` interpolation.                                                                                  |
| `quiet`                    | bool / false                   | Do not echo recipe lines. `[no-quiet]` re-enables per recipe.                                                                                                                |
| `script-interpreter`       | `[CMD, ARGS...]` / `['sh','-eu']` | Interpreter for recipes with a bare `[script]` attribute. Independent of `set shell`. (1.33)                                                                             |
| `shell`                    | `[CMD, ARGS...]` / `['sh','-cu']` | Shell for recipe lines, backticks, and `shell()`. Combine with `[windows]` / `[unix]` attributes for per-OS shells.                                                       |
| `tempdir`                  | string / system temp           | Directory for temporary files (script and shebang recipe bodies). Relative to the justfile directory.                                                                        |
| `unstable`                 | bool / false                   | Enable unstable features: user-defined functions, `set lists`, `[cache]`. Not inherited by submodules. Alternative: `--unstable` or `JUST_UNSTABLE=1`.                       |
| `windows-powershell`       | bool / false, deprecated       | Use `powershell.exe -NoLogo -Command` on Windows. Prefer `[windows]` + `set shell`.                                                                                          |
| `windows-shell`            | `[CMD, ARGS...]`, deprecated   | Shell used on Windows only. Deprecated in 1.56. Prefer `[windows]` + `set shell`.                                                                                            |
| `working-directory`        | string / justfile dir          | Default working directory for recipes and backticks, relative to the justfile (or module file) directory. Conflicts with `no-cd`. (1.33)                                     |

### Shell selection

```just
set shell := ["bash", "-euo", "pipefail", "-c"]   # strict bash on unix

[windows]
set shell := ["pwsh", "-NoLogo", "-Command"]      # conditional attributes work on settings (1.56)
```

Do not use `windows-shell` or `windows-powershell` in new files.

### Lazy and eager

`set lazy` defers every top-level assignment until first use, so unused backticks never run. `eager` forces evaluation at load time for a single assignment and does not require `set unstable`:

```just
set lazy

eager started := `date +%s`   # always evaluated
slow := `expensive-command`   # only evaluated if a recipe uses it
```

## Imports

```just
import "./just/base.just"
import? "./local.just"        # optional; silent if missing
import "~/shared.just"        # ~/ expands to home
```

- Paths resolve relative to the importing file. A file imported more than once is processed once.
- Imported recipes and variables act as if they were in the root file. Depth decides precedence: the shallower definition always wins regardless of source order. At equal depth the earlier import wins (known bug). Within one file, duplicates need `allow-duplicate-recipes` / `allow-duplicate-variables`.
- `import` replaced `!include` (stable since 1.18).

## Modules

Stable since 1.31. No `set unstable` needed.

```just
mod foo                       # searches foo.just, foo/mod.just, foo/justfile, foo/.justfile
mod bar "path/to/file.just"   # explicit file, or a directory containing one of the above
mod? optional                 # absent module is skipped; recipes depending on it are disabled

# Doc comment shown in --list
mod docs

[doc("Build tooling")]
[private]                     # hidden from --list and --choose, still callable
mod tools

alias fe := frontend          # module alias (1.55): `just fe build`; not shown in --list
alias b := foo::build         # alias to a submodule recipe

all: foo::build bar::test     # depend directly on submodule recipes
```

Facts:

- Search must match exactly one candidate; two matching files (`foo.just` and `foo/mod.just`) is an error.
- Invoke with `just foo::build` or `just foo build`. Override submodule variables with `just foo::var=value` or `--set foo::var value`. Evaluate with `--evaluate foo::var`.
- Each module has its own settings and variables. Parent variables are not visible in a submodule and vice versa. Environment variables and loaded `.env` values from the parent are visible; a submodule can load its own `.env`.
- Default working directory for a submodule recipe is the directory containing the module file. `set working-directory` inside a module resolves against that directory.
- `justfile()` and `justfile_directory()` return root paths from any module. Use `module_file()`, `module_directory()`, `module_path()` for the current module (see syntax.md).
- `--list` shows modules as `name ...`; `just --list foo` lists one module; `--list-submodules` expands all; `--summary` prints `foo::build`.
- `--allow-missing` also ignores absent optional modules (1.57).
