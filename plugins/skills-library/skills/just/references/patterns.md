# Justfile Conventions

Project conventions used across this user's justfiles. Follow them when creating or editing a justfile. Language facts live in `settings.md`, `recipes.md`, `syntax.md`.

## File layout

Settings first, then banner-delimited sections in this order. Banner is 80 columns, title centered and uppercase:

```just
set allow-duplicate-recipes
set allow-duplicate-variables
set shell := ["bash", "-euo", "pipefail", "-c"]

# ---------------------------------------------------------------------------- #
#                                 DEPENDENCIES                                 #
# ---------------------------------------------------------------------------- #
```

| Section        | Contents                                                       |
| -------------- | -------------------------------------------------------------- |
| DEPENDENCIES   | `tool := require("tool")` lines, each preceded by a URL comment |
| CONSTANTS      | `GLOBS_*` patterns, exported env defaults                       |
| COMMANDS       | Main entry points (`default`, `build`, `clean`, ...)            |
| CHECKS         | Lint / format / type-check recipes, `[group("checks")]`         |
| TESTS          | Test recipes, `[group("test")]`                                 |
| UTILITIES      | Private helpers (`_` prefix)                                    |

Add `set unstable` only when the file uses user-defined functions, `set lists`, or `[cache]`. Do not add `set lazy` to files that rely on top-level `require()` checks (see recipes.md gotchas).

## Dependencies section

```just
# Bun: https://bun.sh
bun := require("bun")

# Ni: https://github.com/antfu-collective/ni
na := require("na")
ni := require("ni")

build:
    bun next build        # bare name, not {{ bun }}
```

`require()` fails fast when any recipe runs. Tools are invoked by bare name in bodies (interpolated paths break on Windows).

## Constants section

Glob patterns are double-quoted inside the string so the shell does not expand them before the tool sees them:

```just
GLOBS_PRETTIER := "\"**/*.{json,jsonc,yaml,yml}\""
GLOBS_SOLIDITY := "{scripts,src,tests}/**/*.sol"
GLOBS_CLEAN := "**/{.logs,bindings,build,generated}"

export LOG_LEVEL := env("LOG_LEVEL", "info")
export NODE_ENV := env("NODE_ENV", "development")
```

Pass globs as a variadic default so callers can override: `prettier-check +globs=GLOBS_PRETTIER:`.

## Default recipe

```just
# Show available commands
default:
    @just --list
```

Alternative when the primary action should run by default: `default: full-check`. `set default-list` is available but the explicit recipe is preferred for consistency with existing files.

## Groups and aliases

Groups: `checks`, `codegen`, `test`, `cli`, `dev`, `deploy`, `print`. A recipe may carry several distinct groups: `[group("codegen"), group("envio")]`.

Alias line goes immediately after the recipe body. Standard vocabulary:

| Recipe          | Alias | Recipe           | Alias |
| --------------- | ----- | ---------------- | ----- |
| `build`         | `b`   | `install`        | `i`   |
| `full-check`    | `fc`  | `full-write`     | `fw`  |
| `biome-check`   | `bc`  | `biome-write`    | `bw`  |
| `biome-lint`    | `bl`  | `prettier-check` | `pc`  |
| `prettier-write`| `pw`  | `type-check`     | `tc`  |
| `test`          | `t`   | `test-ui`        | `tui` |
| `_run-with-status` | `rws` |               |       |

Check recipes carry `[no-cd]` so they operate on the current package in a monorepo.

## Run-with-status helper

Keep verbatim; the arrow and check-mark output matches `@sablier/devkit`:

```just
# Private recipe to run a check with formatted output
@_run-with-status recipe *args:
    echo ""
    echo -e '{{ CYAN }}→ Running {{ recipe }}...{{ NORMAL }}'
    just {{ recipe }} {{ args }}
    echo -e '{{ GREEN }}✓ {{ recipe }} completed{{ NORMAL }}'
alias rws := _run-with-status

# Run all code checks
[group("checks")]
@full-check:
    just _run-with-status biome-check
    just _run-with-status prettier-check
    just _run-with-status type-check
    echo ""
    echo -e '{{ GREEN }}All code checks passed!{{ NORMAL }}'
alias fc := full-check
```

## Imports

Devkit projects (has `@sablier/devkit` in `package.json`):

```just
# See https://github.com/sablier-labs/devkit/blob/main/just/base.just
import "./node_modules/@sablier/devkit/just/base.just"
import "./node_modules/@sablier/devkit/just/npm.just"
```

Devkit already sets `allow-duplicate-*`, `unstable`, and `lists`; local recipes with the same name override devkit ones. Other projects: `import "./just/settings.just"` first, `import? "./just/local.just"` last for optional overrides.

## Monorepo

```just
mod client "apps/client"      # no set unstable needed
mod server "apps/server"

[no-cd]
build-all: client::build server::build
```

Prefer direct submodule dependencies (`client::build`) over `just client::build` in a body.

## Environment per recipe

```just
[env("DATABASE_URL", "postgres://localhost/test")]
test-integration:
    npm run test:integration

set dotenv-load                     # or: set dotenv-path := ".env.local"
```

## Preconditions

```just
deploy:
    {{ assert(path_exists("dist/") == "true", "Run 'just build' first") }}
    aws s3 sync dist/ s3://bucket/
```

The `== "true"` is required without `set lists`.

## Multi-line logic

Use `[script("bash")]` for case statements, loops, or shared shell variables; `set -e` inside is redundant when the interpreter is `bash -euo pipefail` via `set script-interpreter`, but harmless with `[script("bash")]`:

```just
[script("bash")]
deploy chain_slug:
    set -euo pipefail
    case {{ chain_slug }} in
        mainnet) DEPLOY_URL="https://prod.example.com" ;;
        testnet) DEPLOY_URL="https://test.example.com" ;;
        *) echo "Unknown chain: {{ chain_slug }}"; exit 1 ;;
    esac
    curl -X POST "$DEPLOY_URL/deploy"
```

Combine with `[confirm("Deploy to production?")]` and `[no-cd]` for destructive commands.
