# Syntax: Strings, Variables, Expressions, Functions, Constants, CLI

Verified against just 1.58.0. "lists" in a gating column means the item needs `set unstable` + `set lists`.

## Strings

| Form                | Example                    | Behavior                                                                                                     |
| ------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Double-quoted       | `"a\tb\n"`                 | Escapes: `\n \r \t \" \\ \u{1F600}`; `\` + newline continues the line.                                        |
| Single-quoted (raw) | `'C:\path\{{x}}'`          | No escapes, no interpolation. Use for regexes: `'\d+'` (`"\d+"` is an invalid escape).                        |
| Triple-quoted       | `"""..."""` / `'''...'''`  | Multi-line; common leading whitespace stripped; escapes (if any) processed after unindent.                   |
| Shell-expanded      | `x"$HOME/bin"` `x'~/src'`  | Expands `$VAR`, `${VAR}`, `${VAR:-default}`, leading `~`, `~user` at parse time. Unset var without default is an error. Sees the process env only, not `.env` or `export` variables. Allowed in `set` values, `import`/`mod` paths, attributes. (1.27) |
| Format string       | `f"Hi {{ name }}"` `f'...'` `f'''...'''` | `{{ expr }}` interpolates any expression. Literal `{{` is `{{{{`; `}}` needs no escape. `f'...'` interpolates but skips backslash escapes. No backticks or shell-expanded identifiers inside interpolations. Stable. (1.44) |

Plain strings never interpolate `{{ }}`; use f-strings or `+`. Recipe bodies interpolate `{{ }}`; write `{{{{` for a literal `{{`.

## Variables and assignments

```just
name := "value"                 # string
cmd  := `git rev-parse HEAD`    # backtick: run with `set shell`, stdout with trailing newline stripped
export TOKEN := env("TOKEN")    # exported to recipe environment (not visible to backticks in same scope)
unexport HOME                   # remove from recipe environment (1.29)
[private]                       # hidden from --evaluate / --variables (or prefix name with _)
_internal := "x"
eager now := `date +%s`         # evaluated even under `set lazy` (1.47.1)
```

- Top-level assignments are evaluated once per invocation in dependency order, before recipes run. Backticks are skipped under `--dry-run`. With `set lazy`, unused assignments are never evaluated (exports always are).
- Override from the CLI: `just NAME=VALUE recipe`, `--set NAME VALUE`, `just foo::NAME=VALUE` for submodules. Overrides are visible inside user-defined functions.
- Recipe parameter shorthand `test $RUST_BACKTRACE="1":` exports the parameter as an env var.
- A top-level `error("msg")` aborts every invocation; only call it inside a branch or under `set lazy`.

## Expressions

| Operator / form               | Meaning                                                                   | Gating |
| ----------------------------- | ------------------------------------------------------------------------- | ------ |
| `a + b`                       | Concatenate                                                               |        |
| `a / b`                       | Join with `/` (always `/`, even on Windows; `/ "b"` -> `"/b"`)             |        |
| `a == b`, `a != b`            | Equality                                                                  |        |
| `a =~ 'regex'`, `a !~ 'regex'`| Regex match / no match (Rust regex syntax)                                |        |
| `if c { x } else { y }`       | Conditional; `else if` chains allowed. Condition must be a comparison.    |        |
| `if c { x }` (no else)        | Evaluates to `[]` when false                                              | lists  |
| `a && b`, `a \|\| b`, `!a`    | Logical operators; false is `[]`, `''` is truthy                          | lists  |
| `assert(cond, "msg")`         | Abort with `msg` if false; `msg` optional (1.53). Evaluates to `""`.      |        |
| `assert(path_exists("f"))`    | Non-comparison conditions in `if`/`assert` need lists; else write `== "true"` | lists |
| `name(a, b) := expr`          | User-defined function; call `{{ name("x", "y") }}`. Separate namespace from variables; may shadow builtins; duplicate parameter names rejected. Body sees module variables. (1.49) | unstable |

`set unstable` can be replaced by `--unstable` or `JUST_UNSTABLE=1`.

```just
set unstable

base := "app"
artifact(ext) := f"{{ base }}.{{ ext }}"
level := if env("CI", "") == "true" { "error" } else if env("DEBUG", "") != "" { "debug" } else { "info" }

build:
    tar czf {{ artifact("tar.gz") }} dist/
```

## Constants

All 1.37 unless noted. Not exported as environment variables. Use in `echo -e` or `printf`.

| Constant                                                                             | Value                       |
| ------------------------------------------------------------------------------------ | --------------------------- |
| `BLACK` `RED` `GREEN` `YELLOW` `BLUE` `MAGENTA` `CYAN` `WHITE`                       | `\e[30m` .. `\e[37m`        |
| `BG_BLACK` `BG_RED` `BG_GREEN` `BG_YELLOW` `BG_BLUE` `BG_MAGENTA` `BG_CYAN` `BG_WHITE` | `\e[40m` .. `\e[47m`      |
| `BOLD` `ITALIC` `UNDERLINE` `INVERT` `HIDE` `STRIKETHROUGH`                          | `\e[1m` `\e[3m` `\e[4m` `\e[7m` `\e[8m` `\e[9m` |
| `NORMAL`                                                                             | `\e[0m` (reset)             |
| `CLEAR`                                                                              | `\ec` (clear screen)        |
| `HEX` = `HEXLOWER`                                                                   | `0123456789abcdef` (1.27)   |
| `HEXUPPER`                                                                           | `0123456789ABCDEF` (1.27)   |
| `PATH_SEP`                                                                           | `/` unix, `\` windows (1.41)|
| `PATH_VAR_SEP`                                                                       | `:` unix, `;` windows (1.41)|

## Built-in functions

Every `*_directory()` function has a `*_dir()` alias (1.31). Functions are called inside `{{ }}` or in assignments.

### System and process

| Function            | Returns                                                            | Gating |
| ------------------- | ------------------------------------------------------------------ | ------ |
| `arch()`            | `x86_64`, `aarch64`, ...                                           |        |
| `os()`              | `linux`, `macos`, `windows`, `android`, ...                        |        |
| `os_family()`       | `unix` or `windows`                                                |        |
| `num_cpus()`        | Logical CPU count                                                  |        |
| `num_jobs()`        | Value of `--jobs`, or `[]` (1.56)                                  | lists  |
| `just_executable()` | Absolute path of the running `just`                                |        |
| `just_pid()`        | Process ID (1.23)                                                  |        |
| `just_version()`    | e.g. `1.58.0` (1.55)                                               |        |
| `is_dependency()`   | `"true"` if running as a dependency (1.29); correct inside `[confirm]` |     |
| `recipe_name()`     | Name of the executing recipe; error outside a recipe body (1.53)   |        |

### Environment and executables

| Function                               | Returns                                                                                        | Gating |
| -------------------------------------- | ---------------------------------------------------------------------------------------------- | ------ |
| `env(key)` / `env(key, default)`       | Env var; error if unset and no default. With lists, `key` may be a list; first set wins.       |        |
| `env_var(key)` / `env_var_or_default(key, d)` | Deprecated aliases of `env()`                                                           |        |
| `require(name)`                        | Absolute path of executable on `PATH`; error if missing. Evaluated when the assignment is.     |        |
| `which(name)`                          | Absolute path or `[]` if not found (1.39)                                                      | lists  |
| `shell(cmd, args...)`                  | Runs `cmd` with `set shell`, args as `$1..`; returns stdout. Skipped under `--dry-run`. Sees `[env]` values. (1.27) |  |

`require()` returns an absolute path. Interpolating it (`{{ jq }}`) breaks under `sh` on Windows (`C:\Program Files\...`), so this skill's convention is: assign at top level as an existence check (`jq := require("jq")`) and invoke the tool by bare name in recipe bodies, where the shell resolves it via `PATH`. Under `set lazy` an unreferenced `require()` is never evaluated; use `eager jq := require("jq")`.

### Invocation, justfile, and module paths

| Function                                                  | Returns                                                                 |
| --------------------------------------------------------- | ----------------------------------------------------------------------- |
| `invocation_directory()`                                  | Directory `just` was run from (cygpath-converted on Windows shells)     |
| `invocation_directory_native()`                           | Same, without conversion (1.13)                                         |
| `justfile()` / `justfile_directory()`                     | Root justfile path / its directory (root even from submodules)          |
| `source_file()` / `source_directory()`                    | File currently being evaluated (import-aware)                           |
| `module_file()` / `module_directory()`                    | Current module's file / directory (1.28)                                |
| `module_path()`                                           | Module path such as `foo::bar`; `""` in root (1.50)                     |

### Paths and filesystem

| Function                        | Returns                                                                     |
| ------------------------------- | --------------------------------------------------------------------------- |
| `absolute_path(p)`              | Absolute path relative to working directory (1.1); maps over lists          |
| `canonicalize(p)`               | Resolve symlinks, `.` and `..`; must exist (1.24)                            |
| `clean(p)`                      | Lexical cleanup, no filesystem access                                        |
| `join(a, b, ...)`               | Join path components (2 or more)                                             |
| `parent_directory(p)`           | Parent; `"."` for a bare filename (1.51)                                     |
| `file_name(p)` / `file_stem(p)` | Last component / without extension                                           |
| `extension(p)` / `without_extension(p)` | Extension (no dot) / path without it                                 |
| `path_exists(p)`                | `"true"` / `"false"`; `""` -> `"false"` (1.56)                              |
| `read(p)`                       | File contents (1.39)                                                         |

### Strings

| Function                                                        | Notes                                                        |
| --------------------------------------------------------------- | ------------------------------------------------------------ |
| `quote(s)`                                                      | Single-quote for POSIX shells                                |
| `replace(s, from, to)` / `replace_regex(s, re, to)`             | Regex replacement supports `$1` capture groups (1.9)         |
| `trim(s)` `trim_start(s)` `trim_end(s)`                         | Whitespace                                                   |
| `trim_start_match(s, pat)` `trim_end_match(s, pat)`             | Remove one occurrence                                        |
| `trim_start_matches(s, pat)` `trim_end_matches(s, pat)`         | Remove repeated occurrences                                  |
| `append(suffix, s)` / `prepend(prefix, s)`                      | Applied to each whitespace-separated word (1.27); map lists  |
| `uppercase(s)` `lowercase(s)` `capitalize(s)`                   |                                                              |
| `kebabcase` `snakecase` `shoutysnakecase` `shoutykebabcase` `titlecase` `lowercamelcase` `uppercamelcase` | Case conversion (1.7) |
| `encode_uri_component(s)`                                       | Percent-encode (1.27)                                        |
| `error(msg)`                                                    | Abort evaluation                                             |

### Hash, random, time, versions, style

| Function                                  | Notes                                                                                                                                    |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `sha256(s)` / `sha256_file(p)`            |                                                                                                                                          |
| `blake3(s)` / `blake3_file(p)`            | (1.25)                                                                                                                                   |
| `uuid()`                                  | Random v4                                                                                                                                |
| `choose(n, alphabet)`                     | `n` random chars from `alphabet`, no repeated chars allowed in `alphabet` (1.27)                                                          |
| `datetime(fmt)` / `datetime_utc(fmt)`     | strftime format, local / UTC (1.30). Invalid format errors.                                                                             |
| `semver_matches(ver, req)`                | `"true"` / `"false"` (1.16)                                                                                                              |
| `style(names)` / `style(names, text)`     | ANSI prefix. Names: `command` `error` `warning`; colors `black..white`, `0`-`255`, `#RRGGBB`, `fg:`/`bg:` prefixes; `bold dim italic underline blink reverse hidden strikethrough`; `stdout`/`stderr` gates apply only when that stream is a tty. Two-arg form wraps `text` and resets. One name per call, or a list (`style(["bold", "red"])`, lists); space-separated names and `rgb(...)` are invalid. (1.37; extended 1.55) |

### User directories (1.23)

`cache_directory()` `config_directory()` `config_local_directory()` `data_directory()` `data_local_directory()` `executable_directory()` `home_directory()`. `executable_directory()` and `runtime_directory()` error on Windows; `runtime_directory()` (1.49) is Linux-only (`$XDG_RUNTIME_DIR`).

## Lists (unstable, 1.53)

Requires `set unstable` and `set lists`. Values may be lists of strings.

```just
set unstable
set lists

targets := ["linux", "macos"]
all := targets ++ ["windows"]          # ++ concatenates lists; + and / map over elements
words := split("a b c")                # optional separator; split(s, '') splits into chars
count := len(all)                      # element count; works without lists but a string counts as 1
dbg := show(all)                       # literal representation
joined := join_list(all, ",")          # default separator: space
truthy := bool("1")                    # "true"; bool("") -> []
```

- Variadic parameters (`+args`, `*args`) become lists. Lists interpolate space-joined in recipe bodies and in `assert`/`[confirm]` messages; any other string context is an error. Empty lists are not exported as env vars.
- Mapped dependencies: `build target *platforms: *(compile target *platforms)` runs `compile` once per element of `platforms`; `[parallel]` applies. No list indexing exists.
- `==`/`!=` compare structurally; `=~`/`!~` accept list operands.

## Command line

Every option has a `JUST_<OPTION_IN_UPPER_SNAKE>` environment variable (`just --help` shows them). Nothing on the CLI requires `--unstable`; only language features do.

### Options

| Option                                     | Purpose                                                                                            |
| ------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| `-f, --justfile <PATH>`                    | Use this justfile; `-` reads stdin (1.51)                                                          |
| `-d, --working-directory <DIR>`            | Working directory; requires `--justfile`                                                           |
| `--justfile-name <NAME>[,<NAME>]`          | Filenames to search for, comma-separated or repeated (1.49, list 1.57)                             |
| `-g, --global-justfile`                    | Use `~/.config/just/justfile` or `~/.justfile` (1.27)                                              |
| `--ceiling <DIR>`                          | Stop justfile search at this directory                                                             |
| `--unstable`                               | Enable unstable features                                                                           |
| `-u, --unsorted`                           | `--list` in source order                                                                           |
| `--group <GROUP>`                          | Filter `--list` and `--choose` by group                                                            |
| `--indentation <TEXT>` `--check`           | `--fmt` controls (forbidden by this skill's formatter policy)                                       |
| `--set <VAR> <VALUE>`                      | Override variable; also `just VAR=VALUE`                                                           |
| `-E, --dotenv-path <PATH>` / `-F, --dotenv-filename <NAME>` | Env file path / name; repeatable (1.53); `-F` 1.55                                |
| `--dotenv-command <CMD>`                   | Load env from command output; repeatable (1.54)                                                    |
| `--no-dotenv`                              | Do not load env files                                                                              |
| `--shell <SHELL>` `--shell-arg <ARG>` `--clear-shell-args` | Override `set shell`                                                               |
| `--shell-command`                          | Treat positional args as a shell command to run in the justfile environment                        |
| `--allow-missing`                          | Ignore missing recipes and absent optional modules (1.38; modules 1.57)                            |
| `-n, --dry-run`                            | Print commands without running; skips backticks, `shell()`, `dotenv-command`                       |
| `--no-deps`                                | Skip dependencies (1.23)                                                                           |
| `--one`                                    | Forbid multiple recipes on the command line (1.36)                                                 |
| `--jobs <N>`                               | Parallelism limit for `[parallel]` (1.56)                                                          |
| `--yes`                                    | Auto-confirm `[confirm]` prompts                                                                    |
| `--no-cache`                               | Bypass `[cache]` (1.54)                                                                            |
| `-q, --quiet` / `-v, --verbose`            | Echo control; verbose shows recipe paths and cache keys                                             |
| `--explain`                                | Print recipe doc comment before running (1.36)                                                     |
| `--timestamp` `--timestamp-format <FMT>`   | Print time before each command; default `%H:%M:%S` (1.28)                                          |
| `--time`                                   | Print recipe execution durations (1.49)                                                            |
| `--highlight` / `--no-highlight`           | Highlight echoed lines                                                                             |
| `--color <always\|auto\|never>` `--command-color <COLOR>` | Color control                                                                        |
| `--alias-style <left\|right\|separate>` `--no-aliases` | `--list` alias display (1.39, 1.26)                                                    |
| `--list-heading <TEXT>` `--list-prefix <TEXT>` `--list-submodules` | `--list` formatting; `--list-submodules` expands modules (1.28)             |
| `--dump-format <json\|just>`               | Format for `--dump`; `--json` = `--dump --dump-format json` (1.48)                                 |
| `--evaluate-format <just\|shell>`          | `--evaluate` output; `shell` renames `-` to `_` (1.49)                                             |
| `--tempdir <DIR>`                          | Override `set tempdir` (1.41)                                                                      |
| `--cygpath <PATH>`                         | cygpath binary for Windows path conversion (1.41)                                                  |
| `--chooser <CHOOSER>`                      | Program for `--choose` (default `fzf`)                                                             |
| `--complete-aliases`                       | Include aliases in completions (1.49)                                                              |
| `--default-list`                           | Same as `set default-list` (1.52)                                                                  |

### Subcommands

| Subcommand                            | Purpose                                                                                      |
| ------------------------------------- | -------------------------------------------------------------------------------------------- |
| `-l, --list [<MODULE>...]`            | List recipes with doc comments and groups; `--list foo` lists a module                       |
| `--groups`                            | List recipe groups                                                                           |
| `--summary`                           | Space-separated recipe names, including `foo::bar`                                           |
| `-s, --show <RECIPE_PATH>...`         | Print recipe source with doc comment, attributes, dependency paths (1.56)                    |
| `--usage <RECIPE_PATH>...`            | Print argument help for `[arg]` recipes                                                      |
| `--variables`                         | List variable names                                                                          |
| `--evaluate [<VAR>]`                  | Print all variables, one variable, or `foo::var` in a module (1.49)                          |
| `--choose`                            | Pick recipes with a chooser; `--group` filters (1.50); each pick runs separately (1.51)      |
| `-c, --command <CMD>...`              | Run a command in the justfile environment                                                    |
| `--dump`                              | Print the justfile (`--fmt` semantics; forbidden by this skill's formatter policy)           |
| `--fmt` `--check`                     | Format justfile in place / check only (stable 1.50; forbidden by this skill's formatter policy) |
| `--clean [<RECIPE_PATH>...]`          | Clear `[cache]` entries (1.54)                                                               |
| `--init`                              | Create a starter justfile                                                                    |
| `-e, --edit`                          | Open justfile in `$VISUAL`/`$EDITOR`                                                         |
| `--completions <SHELL>`               | `bash elvish fish nushell powershell zsh`                                                    |
| `--changelog` `--man`                 | Print changelog / man page                                                                   |
