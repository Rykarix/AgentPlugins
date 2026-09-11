#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "typer>=0.15",
#     "rich>=13.7",
#     "ruamel.yaml>=0.18",
# ]
# ///
"""Toggle `disable-model-invocation` in the YAML frontmatter of extension-contributed SKILL.md files.

Usage:
    uv run .scripts/extension_contributed_skills.py --enabled false
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

KEY = "disable-model-invocation"
SKILL_FILENAME = "skill.md"
UTF8_BOM = b"\xef\xbb\xbf"

# Candidate extension roots per edition, relative to the user's home directory.
INSIDERS_ROOTS = (
    Path(".vscode-insiders/extensions"),
    Path(".vscode-server-insiders/extensions"),
    Path(".vscode-exploration/extensions"),
)
STABLE_ROOTS = (
    Path(".vscode/extensions"),
    Path(".vscode-oss/extensions"),
    Path(".vscode-server/extensions"),
)

TRUE_WORDS = {"true", "t", "yes", "y", "on", "1"}
FALSE_WORDS = {"false", "f", "no", "n", "off", "0"}

OPEN_DELIM = re.compile(r"^---[ \t]*$")
CLOSE_DELIM = re.compile(r"^(?:---|\.\.\.)[ \t]*$")
KEY_LINE = re.compile(rf"^{re.escape(KEY)}[ \t]*:(?P<rest>.*)$")
TRAILING_COMMENT = re.compile(r"(?P<gap>\s+)(?P<comment>#.*)$")

console = Console()
yaml = YAML(typ="rt")


class Outcome(str, Enum):
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class Result:
    path: Path
    outcome: Outcome
    detail: str


def parse_bool(raw: str) -> bool:
    word = raw.strip().lower()
    if word in TRUE_WORDS:
        return True
    if word in FALSE_WORDS:
        return False
    raise typer.BadParameter(f"expected a boolean, got {raw!r}")


def default_roots(insiders: bool) -> list[Path]:
    home = Path.home()
    candidates = INSIDERS_ROOTS if insiders else STABLE_ROOTS
    return [root for candidate in candidates if (root := home / candidate).is_dir()]


def find_skill_files(roots: list[Path]) -> list[Path]:
    found: dict[Path, None] = {}
    for root in roots:
        for path in root.rglob("*"):
            if path.name.lower() == SKILL_FILENAME and path.is_file():
                found.setdefault(path.resolve(), None)
    return sorted(found)


def read_text(path: Path) -> tuple[str, bool]:
    """Return file text plus whether it carried a UTF-8 BOM, preserving line endings."""
    raw = path.read_bytes()
    has_bom = raw.startswith(UTF8_BOM)
    if has_bom:
        raw = raw[len(UTF8_BOM) :]
    return raw.decode("utf-8"), has_bom


def write_text(path: Path, text: str, has_bom: bool) -> None:
    payload = text.encode("utf-8")
    path.write_bytes(UTF8_BOM + payload if has_bom else payload)


def frontmatter_span(lines: list[str]) -> tuple[int, int] | None:
    """Return (body_start, close_index) for the leading frontmatter block, if present."""
    if not lines or not OPEN_DELIM.match(lines[0].rstrip("\r\n")):
        return None
    for index in range(1, len(lines)):
        if CLOSE_DELIM.match(lines[index].rstrip("\r\n")):
            return 1, index
    return None


def line_ending(line: str) -> str:
    for ending in ("\r\n", "\n", "\r"):
        if line.endswith(ending):
            return ending
    return ""


def rewrite_key_line(line: str, value: bool) -> str:
    """Replace the value on an existing key line, keeping any trailing comment and newline."""
    ending = line_ending(line)
    rest = KEY_LINE.match(line[: len(line) - len(ending)]).group("rest")
    comment = TRAILING_COMMENT.search(rest)
    suffix = f"{comment.group('gap')}{comment.group('comment')}" if comment else ""
    return f"{KEY}: {str(value).lower()}{suffix}{ending}"


def apply_value(text: str, value: bool) -> tuple[str, str]:
    """Return (new_text, detail). Raises ValueError when the file cannot be handled safely."""
    lines = text.splitlines(keepends=True)
    span = frontmatter_span(lines)
    if span is None:
        raise ValueError("no YAML frontmatter block")

    body_start, close_index = span
    body = lines[body_start:close_index]

    try:
        parsed = yaml.load("".join(body)) or {}
    except YAMLError as error:
        raise ValueError(f"unparseable frontmatter: {error}") from error
    if not isinstance(parsed, dict):
        raise ValueError("frontmatter is not a mapping")

    matches = [i for i, line in enumerate(body) if KEY_LINE.match(line.rstrip("\r\n"))]
    if len(matches) > 1:
        raise ValueError(f"{KEY} appears {len(matches)} times")

    if matches:
        index = matches[0]
        updated = rewrite_key_line(body[index], value)
        detail = "value replaced"
        if updated == body[index]:
            return text, "already set"
        body[index] = updated
    else:
        ending = next((e for line in reversed(body) if (e := line_ending(line))), None)
        ending = ending or line_ending(lines[0]) or "\n"
        if body and not line_ending(body[-1]):
            body[-1] += ending
        body.append(f"{KEY}: {str(value).lower()}{ending}")
        detail = "key added"

    new_text = "".join(lines[:body_start] + body + lines[close_index:])
    verify(new_text, value)
    return new_text, detail


def verify(text: str, value: bool) -> None:
    lines = text.splitlines(keepends=True)
    span = frontmatter_span(lines)
    if span is None:
        raise ValueError("verification failed: frontmatter lost")
    body_start, close_index = span
    try:
        parsed = yaml.load("".join(lines[body_start:close_index])) or {}
    except YAMLError as error:
        raise ValueError(f"verification failed: {error}") from error
    if parsed.get(KEY) is not value:
        raise ValueError(f"verification failed: {KEY} is {parsed.get(KEY)!r}")


def process(path: Path, value: bool, dry_run: bool) -> Result:
    try:
        text, has_bom = read_text(path)
        new_text, detail = apply_value(text, value)
    except ValueError as error:
        return Result(path, Outcome.SKIPPED, str(error))
    except OSError as error:
        return Result(path, Outcome.FAILED, str(error))

    if new_text == text:
        return Result(path, Outcome.UNCHANGED, detail)
    if dry_run:
        return Result(path, Outcome.UPDATED, f"{detail} (dry run)")
    try:
        write_text(path, new_text, has_bom)
    except OSError as error:
        return Result(path, Outcome.FAILED, str(error))
    return Result(path, Outcome.UPDATED, detail)


STYLES = {
    Outcome.UPDATED: "green",
    Outcome.UNCHANGED: "dim",
    Outcome.SKIPPED: "yellow",
    Outcome.FAILED: "red",
}


def report(results: list[Result], verbose: bool) -> None:
    table = Table(box=None, pad_edge=False)
    table.add_column("outcome")
    table.add_column("skill", overflow="fold")
    table.add_column("detail", style="dim")
    for result in results:
        if not verbose and result.outcome is Outcome.UNCHANGED:
            continue
        table.add_row(
            f"[{STYLES[result.outcome]}]{result.outcome.value}[/]",
            str(result.path),
            result.detail,
        )
    if table.row_count:
        console.print(table)

    counts = {
        outcome: sum(r.outcome is outcome for r in results) for outcome in Outcome
    }
    summary = ", ".join(
        f"{count} {outcome.value}" for outcome, count in counts.items() if count
    )
    console.print(
        f"[bold]{len(results)} SKILL.md files[/]: {summary or 'nothing to do'}"
    )


def main(
    enabled: Annotated[
        str,
        typer.Option(
            "--enabled",
            help="Whether model invocation stays enabled; false sets disable-model-invocation: true.",
        ),
    ] = "true",
    insiders: Annotated[
        str,
        typer.Option(
            "--insiders",
            help="Target VS Code Insiders; false targets stable. Ignored when --root is given.",
        ),
    ] = "true",
    roots: Annotated[
        list[Path] | None,
        typer.Option(
            "--root",
            help="Extension directory to scan. Repeatable. Defaults to installed VS Code editions.",
        ),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Report changes without writing.")
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Include unchanged files in the report."),
    ] = False,
) -> None:
    """Set `disable-model-invocation` in every extension-contributed SKILL.md."""
    disable = not parse_bool(enabled)

    search_roots = []
    for root in roots or default_roots(parse_bool(insiders)):
        if root.is_dir():
            search_roots.append(root)
        else:
            console.print(f"[yellow]skipping missing root:[/] {root}")

    if not search_roots:
        console.print("[red]no VS Code extension directories found[/]")
        raise typer.Exit(code=1)

    for root in search_roots:
        console.print(f"[dim]scanning[/] {root}")

    skills = find_skill_files(search_roots)
    if not skills:
        console.print("[yellow]no SKILL.md files found[/]")
        return

    console.print(f"setting [bold]{KEY}: {str(disable).lower()}[/]")
    results = [process(path, disable, dry_run) for path in skills]
    report(results, verbose)

    if any(result.outcome is Outcome.FAILED for result in results):
        raise typer.Exit(code=1)


if __name__ == "__main__":
    typer.run(main)
