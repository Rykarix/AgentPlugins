# Recipes: Parameters, Options, Dependencies, Attributes, Execution

Verified against just 1.58.0. "lists" means the item needs `set unstable` + `set lists`.

## Anatomy

```just
# Doc comment: shown by --list and --explain. Empty doc comments are ignored.
[group("build")]
build target="debug" +flags="": (setup target) && notify
    @echo "building {{ target }} {{ flags }}"   # @ suppresses echo of this line
    -rm -f stale.lock                          # - ignores a non-zero exit
alias b := build                                # alias immediately after the recipe
```

- Recipe bodies are indented with spaces or tabs, never mixed within one recipe.
- Each line of a shell recipe runs in a separate shell invocation. Use `\` at line end to continue a command; continuation lines ignore leading sigils.
- `{{ expr }}` interpolates any expression; `{{{{` yields a literal `{{`.
- Line prefixes (sigils), shell recipes only: `@` quiet, `-` ignore failure, `?` guard (needs `set guards`; stops this recipe on exit code 1, other recipes continue). Combine as `@-`.
- Recipe-level `@recipe:` quiets every line. `set quiet` quiets all recipes; `[no-quiet]` opts out.

## Parameters

| Form                              | Meaning                                                                                              |
| --------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `name`                            | Required positional                                                                                  |
| `name="x"`                        | Default; expressions with operators must be parenthesized: `triple=(arch() + "-x")`                 |
| `+args`                           | One or more; `+args="-q"` gives a default                                                             |
| `*args`                           | Zero or more                                                                                         |
| `$NAME` / `$NAME="x"`             | Also exported as an environment variable (not visible to backticks in the same scope)                |

- Variadic parameter must be last. Under `set lists` variadics are lists, otherwise a space-joined string.
- `{{ arg }}` loses quoting when the shell re-splits it. Safe forms: `'{{ arg }}'`, `$NAME` export, or `set positional-arguments` with `"$1"` / `"$@"`.
- `set positional-arguments` / `[positional-arguments]`: shell recipes get `$0` = recipe name, `$1..` = arguments. In `[script]` and shebang recipes `$0` is the temp file path.
- Recipes with parameters consume following command-line words: `just build serve` passes `serve` as `target`. `--one` forbids multiple recipes per invocation.
- Same recipe with the same arguments runs once per invocation (`just a a` or shared dependencies); different arguments re-run it.

## Options: `[arg(...)]`

Turn a parameter into a CLI option. `--list` shows `[OPTIONS]`; `just --usage recipe` prints the option help.

```just
[arg("target", long, short, help="Build target")]      # bare short = first letter (1.55)
[arg("release", long, value="true")]                   # --release sets "true"; default needed
[arg("profile", long, pattern='dev|prod')]             # regex; list of patterns allowed (1.55)
build target release="false" profile="dev":
    cargo build --target {{ target }} {{ if release == "true" { "--release" } else { "" } }}
```

| Key                     | Effect                                                                                       | Since / gating |
| ----------------------- | -------------------------------------------------------------------------------------------- | -------------- |
| `long`                  | `--name`; `--name=v` and `--name v` both accepted                                             | 1.46           |
| `short="c"` / `short`   | `-c`; bare `short` defaults to first character of the parameter                              | 1.46 / 1.55    |
| `value="x"`             | Option takes no argument; sets this value when present. May be an expression.                | 1.46 / 1.54    |
| `help="..."`            | Shown by `--usage`; expression or list allowed                                               | 1.46 / 1.55    |
| `pattern='re'`          | Argument must match; single-quote regexes (`'\d+'`). Expression or list of patterns allowed. Not with `flag`. | 1.45 / 1.55 |
| `flag`                  | Boolean: `"true"` when passed, `[]` otherwise; no default allowed                             | 1.53, lists    |
| `multiple`              | Repeatable option; value is a list; `-vv` combines                                           | 1.55, lists    |
| `min="n"` / `max="n"`   | Bounds for variadic or `multiple` counts; `min > 0` recipe cannot be the default recipe      | 1.56, lists    |

- Options are optional only if the parameter has a default. Variadic `+`/`*` parameters may be options. Short flags combine (`-ab`). Option names may not start with `-`. Duplicate keys in one `[arg]` are an error.
- Works with `set positional-arguments`: `$1` receives the option's value.

## Dependencies

```just
test: build (lint "strict") && report      # before: build, lint("strict"); after: report
deploy target: (build target)              # forward a parameter
all: foo::build                            # depend on a submodule recipe
```

- Dependencies run before the recipe body; `&&` dependencies run after it succeeds.
- Multi-line dependency lists: wrap in parentheses or end lines with `\`.
- `&&` dependencies and their transitive dependencies are not deduplicated against earlier ones in the same run (`x: a && b` with `b: a` runs `a` twice).
- `[parallel]` runs a recipe's direct dependencies concurrently; `--jobs N` (1.56) caps parallelism; `num_jobs()` reads it (lists).
- Mapped dependencies (lists): `build target *platforms: *(compile target *platforms)` runs `compile` once per element of `platforms`.
- `--no-deps` skips dependencies. `--dry-run` prints without running.

## Attributes

Attribute forms: `[name]`, `[name("arg")]`, `[name: "arg"]` (colon form for single-argument attributes), several per line `[no-cd, private]`, or stacked on separate lines. Duplicate keys and duplicate `[group("x")]` on one recipe are errors.

| Attribute                                   | Applies to             | Effect                                                                                                                       | Since        |
| ------------------------------------------- | ---------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ------------ |
| `[arg("p", ...)]`                           | recipe                 | Parameter becomes an option; see above                                                                                       | 1.45-1.56    |
| `[cache]` / `[cache(inputs="in.txt", outputs="out.txt", extra="v1")]` | script recipe | Skip when key (body, env, inputs hash, args, cwd, `extra`) unchanged; stored in `.justcache/`. Missing output after a run is an error. `--no-cache` bypasses; `--clean [path]` clears. Only those three keys. Unstable. | 1.54 |
| `[confirm]` / `[confirm("Prompt?")]`        | recipe                 | Prompt before running; prompt may be an expression. An empty prompt still prompts. `--yes` / `JUST_YES=1` auto-confirms.   | 1.17 / 1.49  |
| `[continue]` / `[continue("SIGINT", ...)]`  | recipe                 | Continue if the child exits 0 after the listed signals (default SIGINT; only `SIGHUP`, `SIGINT`, `SIGQUIT` allowed)         | 1.54         |
| `[default]`                                 | recipe                 | Module default recipe; one per module; must run with zero args                                                               | 1.43         |
| `[doc("text")]`                             | recipe, mod, alias     | Override doc comment; const expression allowed (1.56)                                                                        | 1.27         |
| `[env("NAME", "value")]`                    | recipe                 | Env var for this recipe; both may be expressions (1.51). Overrides `export` variables; visible to `shell()` (1.57).          | 1.47         |
| `[exit-message]` / `[no-exit-message]`      | recipe                 | Force / suppress `error: recipe X failed` message; exit code still propagates                                                | 1.39 / 1.7   |
| `[extension(".ext")]`                       | script/shebang recipe  | Extension of the temp script file; include the dot. Needed for `.mjs`, `.ps1`                                                | 1.32         |
| `[group("name")]`                           | recipe, mod            | Group in `--list`; multiple distinct groups allowed; `--groups` lists them                                                    | 1.27         |
| `[linux]` `[macos]` `[windows]` `[unix]` `[freebsd]` `[netbsd]` `[openbsd]` `[dragonfly]` `[android]` | any item | Enable only on that OS. Same-named items on different OSes may coexist. Applies to `set`, `mod`, `alias`, assignments too (1.56). | freebsd/netbsd/dragonfly 1.47, openbsd 1.38, android 1.50 |
| `[metadata("a", "b")]`                      | recipe                 | Attach strings visible in `--dump --dump-format json`                                                                        | 1.42         |
| `[no-cd]`                                   | recipe                 | Run in the invocation directory                                                                                              | 1.9          |
| `[no-quiet]`                                | recipe                 | Override `set quiet`                                                                                                         | 1.23         |
| `[parallel]`                                | recipe                 | Run direct dependencies concurrently                                                                                         | 1.42         |
| `[positional-arguments]`                    | recipe                 | Per-recipe `set positional-arguments`                                                                                        | 1.29         |
| `[private]`                                 | recipe, alias, mod, assignment | Hide from `--list`, `--choose`, `--evaluate`; same as `_` prefix                                                    | 1.10         |
| `[script]` / `[script("cmd", "arg", ...)]`  | recipe                 | Run body as one file via `set script-interpreter` (default `sh -eu`) or the given command. Stable.                          | 1.33 / 1.44  |
| `[shell]`                                   | recipe                 | Force a linewise shell recipe when `set default-script` is on                                                                | 1.52         |
| `[timestamp]` / `[timestamp("%H:%M:%S")]`   | recipe                 | Per-recipe `--timestamp`; format may be an expression                                                                        | 1.58         |
| `[working-directory("path")]`               | recipe                 | Run from `path` (relative to the default working directory); expression allowed (1.51)                                       | 1.38         |

## Execution model: shell, script, shebang

| Kind     | Trigger                        | How it runs                                                                                                          |
| -------- | ------------------------------ | -------------------------------------------------------------------------------------------------------------------- |
| Shell    | default                        | Each line via `set shell` (default `sh -cu`). Sigils, `set ignore-comments`, `\` continuation handled by just.       |
| Script   | `[script]` / `[script("cmd")]` | Whole body written to a temp file, run as `interpreter <file>`. Bare `[script]` uses `set script-interpreter`.       |
| Shebang  | body starts with `#!`          | Body written to a temp file and executed directly (Unix). Use `#!/usr/bin/env -S bash -x` for interpreter args.    |

Script and shebang facts:

- Quiet by default; `@recipe:` inverts and echoes the whole body. Sigils `@ - ?` are not processed inside the body.
- `\` line continuations are passed to the interpreter verbatim. `set ignore-comments` does not apply. `{{ }}` interpolation happens before the file is written.
- Temp dir: `--tempdir` / `JUST_TEMPDIR` > `set tempdir` > `$XDG_RUNTIME_DIR` (Linux) > system temp. Shebang recipes fail on `noexec` mounts; set `tempdir` elsewhere.
- Windows: shebang lines are split into command + args, `/` paths translated with cygpath (`--cygpath`), file appended as last arg. `#!/usr/bin/env bash` works with Git Bash. PowerShell scripts get a UTF-8 BOM. `[script("pwsh", "-NoProfile", "-File")]` works.
- Default `sh -eu` already stops on error and unset variables. For bash: `set script-interpreter := ["bash", "-euo", "pipefail"]` or `[script("bash", "-euo", "pipefail")]`.
- Node: temp files have no extension, so ESM syntax needs `[extension(".mjs")]`.
- Failure message: `recipe X failed with exit code N` (no line number for scripts). Exit code propagates.

```just
set script-interpreter := ["bash", "-euo", "pipefail"]

[script]
release version:
    git tag "v{{ version }}"
    git push origin "v{{ version }}"

[script("python3")]
stats:
    import json, pathlib
    print(len(json.loads(pathlib.Path("data.json").read_text())))

[script("node")]
[extension(".mjs")]
bump:
    import { readFile } from "node:fs/promises";
    console.log(JSON.parse(await readFile("package.json")).version);
```

Choose shell recipes for one-liners and when `-`/`@` per line matter; `[script]` for multi-line logic needing shared variables, loops, or functions; shebang only when the interpreter must be pinned in the body.

## Listing and visibility

- `just --list` shows recipes, parameters (`[OPTIONS]` for `[arg]` recipes), doc comments, groups, and aliases; `--list-submodules` expands modules; `--unsorted` keeps source order.
- Private: `_name` or `[private]`; still callable.
- `--choose` opens a chooser (`fzf`); `--choose --group x` filters; each pick runs as a separate invocation.
- `--show recipe` prints source with doc comment and attributes; `--usage recipe` prints option help.

## Gotchas

- `[dragonflybsd]` does not exist; the attribute is `[dragonfly]`.
- An empty `[confirm("")]` prompt does not skip confirmation; use `--yes`.
- `set lazy` never evaluates an unreferenced `x := require("x")`; use `eager x := require("x")` or avoid `set lazy` when relying on top-level dependency checks.
- `{{ require("tool") }}` interpolates an absolute path that breaks in `sh` on Windows (`C:\Program Files\...`). Invoke tools by bare name in bodies; keep `require()` at top level for the existence check.
- `if`/`assert` conditions must be comparisons unless `set lists`: write `path_exists("x") == "true"`.
- `&&` dependencies are not deduplicated against earlier dependencies.
