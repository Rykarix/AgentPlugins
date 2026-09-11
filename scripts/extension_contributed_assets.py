#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "typer>=0.15",
#     "rich>=13.7",
# ]
# ///
"""Quarantine and restore extension-contributed skills, prompts and hooks.

VS Code extensions inject skills, prompt files and hooks into every agent session with
no supported way to remove them. This moves the offending files into a content-addressed
store outside the extension tree and leaves a tombstone behind so the extension cannot
quietly slot a replacement into the same path.

Nothing is ever deleted: every quarantined byte is recoverable via `restore`.

Usage:
    uv run scripts/extension_contributed_assets.py nuke --kind skills
    uv run scripts/extension_contributed_assets.py restore
    uv run scripts/extension_contributed_assets.py status
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import shutil
import stat
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

SENTINEL = "AGENTPLUGINS-QUARANTINE-V1"
MARKER_NAME = ".agentplugins-quarantine"
MANIFEST_NAME = "manifest.json"
MANIFEST_VERSION = 1
BLOBS_DIRNAME = "blobs"

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

console = Console()


class Kind(str, Enum):
    SKILLS = "skills"
    PROMPTS = "prompts"
    HOOKS = "hooks"


# Case-insensitive filename globs. Extensions ship these alongside their own source.
PATTERNS: dict[Kind, tuple[str, ...]] = {
    Kind.SKILLS: ("skill.md",),
    Kind.PROMPTS: (
        "*.prompt.md",
        "*.instructions.md",
        "*.chatmode.md",
        "*.agent.md",
    ),
    Kind.HOOKS: ("hooks.json", "*.hooks.json"),
}


class Tombstone(str, Enum):
    STUB = "stub"  # inert read-only placeholder; the loader sees a disabled asset
    DIR = "dir"  # a directory in the file's place; no process can write a file there
    NONE = "none"  # plain removal; the extension is free to recreate it


class Outcome(str, Enum):
    CHANGED = "changed"
    UNCHANGED = "unchanged"
    SKIPPED = "skipped"
    CONFLICT = "conflict"
    FAILED = "failed"


STYLES = {
    Outcome.CHANGED: "green",
    Outcome.UNCHANGED: "dim",
    Outcome.SKIPPED: "yellow",
    Outcome.CONFLICT: "magenta",
    Outcome.FAILED: "red",
}


@dataclass(frozen=True)
class Result:
    path: Path
    outcome: Outcome
    detail: str


# ---------------------------------- helpers ---------------------------------------


def parse_bool(raw: str) -> bool:
    word = raw.strip().lower()
    if word in TRUE_WORDS:
        return True
    if word in FALSE_WORDS:
        return False
    raise typer.BadParameter(f"expected a boolean, got {raw!r}")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


ELEVATION_HINT = "needs an elevated shell"


def denied(error: Exception) -> bool:
    return isinstance(error, PermissionError) or getattr(error, "winerror", None) == 5


def describe(error: Exception) -> str:
    if denied(error):
        filename = getattr(error, "filename", None) or "?"
        return f"access denied ({Path(filename).name}); {ELEVATION_HINT}"
    return str(error)


def fault(path: Path, error: Exception) -> Result:
    """A locked-down install is a solvable skip, not a failure that should abort the run."""
    outcome = Outcome.SKIPPED if denied(error) else Outcome.FAILED
    return Result(path, outcome, describe(error))


def key_for(path: Path) -> str:
    """Manifest key: case-folded on Windows so a re-scan matches the stored entry."""
    return os.path.normcase(str(path))


def owner_of(entry: dict, path: Path) -> Path:
    """The extension folder that owns an asset; recovered from the path for old entries."""
    if recorded := entry.get("owner"):
        return Path(recorded)
    parts = path.parts
    for index in range(len(parts) - 1, 0, -1):
        if parts[index - 1].lower() == "extensions":
            return Path(*parts[: index + 1])
    return path.parent


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


def set_writable(path: Path) -> None:
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass


def set_read_only(path: Path) -> None:
    try:
        os.chmod(path, stat.S_IREAD)
    except OSError:
        pass


def remove_path(path: Path) -> None:
    """Remove a file or directory, clearing read-only bits Windows would trip over."""
    if path.is_dir() and not path.is_symlink():
        for child in path.rglob("*"):
            set_writable(child)
        shutil.rmtree(path)
        return
    if path.exists() or path.is_symlink():
        set_writable(path)
        path.unlink()


def prune_empty_parents(path: Path, stop: Path) -> None:
    """Walk up from a deleted file removing directories it emptied, never past `stop`."""
    stop = stop.resolve()
    parent = path.parent.resolve()
    while parent != stop and stop in parent.parents:
        try:
            next(parent.iterdir())
            return
        except StopIteration:
            pass
        except OSError:
            return
        try:
            parent.rmdir()
        except OSError:
            return
        parent = parent.parent


def default_roots(insiders: bool) -> list[Path]:
    home = Path.home()
    candidates = INSIDERS_ROOTS if insiders else STABLE_ROOTS
    return [root for candidate in candidates if (root := home / candidate).is_dir()]


def builtin_roots() -> list[Path]:
    """Bundled extensions ship inside the install tree; writing there needs an admin shell."""
    bases: list[Path] = []
    for name in ("code-insiders", "code", "code-oss"):
        if launcher := shutil.which(name):
            bases.extend(Path(launcher).resolve().parents)
    for variable in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        if not (value := os.environ.get(variable)):
            continue
        for product in ("Microsoft VS Code Insiders", "Microsoft VS Code"):
            bases.append(Path(value) / product)
            bases.append(Path(value) / "Programs" / product)

    roots: list[str] = []
    for base in bases:
        if not base.is_dir():
            continue
        # Installers add a build-hash directory between the product root and `resources`.
        for candidate in (base, *(p for p in base.iterdir() if p.is_dir())):
            extensions = candidate / "resources" / "app" / "extensions"
            if extensions.is_dir() and str(extensions) not in roots:
                roots.append(str(extensions))
    return [Path(root) for root in roots]


def default_store() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / "AgentPlugins" / "extension-quarantine"


def is_writable(path: Path) -> bool:
    probe = path / f".agentplugins-probe-{os.getpid()}"
    try:
        probe.touch()
        probe.unlink()
        return True
    except OSError:
        return False


def matches(path: Path, kind: Kind) -> bool:
    name = path.name.lower()
    return any(fnmatch.fnmatch(name, pattern) for pattern in PATTERNS[kind])


def iter_candidates(roots: list[Path], kind: Kind) -> Iterator[tuple[Path, Path]]:
    """Yield each matching file with the extension folder that owns it."""
    seen: set[str] = set()
    for root in roots:
        resolved_root = root.resolve()
        for path in root.rglob("*"):
            # is_file() also filters out directory tombstones from a previous run.
            if not matches(path, kind) or not path.is_file():
                continue
            resolved = path.resolve()
            if (identity := key_for(resolved)) in seen:
                continue
            seen.add(identity)
            try:
                owner = resolved_root / resolved.relative_to(resolved_root).parts[0]
            except (ValueError, IndexError):
                owner = resolved_root
            yield resolved, owner


# ---------------------------------- store -----------------------------------------


def blob_path(store: Path, digest: str) -> Path:
    return store / BLOBS_DIRNAME / digest[:2] / digest


def sidecar_path(store: Path, digest: str) -> Path:
    return blob_path(store, digest).with_suffix(".json")


def put_blob(store: Path, data: bytes, kind: Kind, source: Path, dry_run: bool) -> str:
    """Write content-addressed bytes plus a sidecar that can rebuild a lost manifest."""
    digest = hashlib.sha256(data).hexdigest()
    if dry_run:
        return digest

    target = blob_path(store, digest)
    if not target.is_file():
        atomic_write(target, data)

    sidecar = sidecar_path(store, digest)
    payload = {"kind": kind.value, "sources": [], "first_seen": now_iso()}
    if sidecar.is_file():
        try:
            existing = json.loads(sidecar.read_text("utf-8"))
            if isinstance(existing, dict):
                payload = existing | {"kind": kind.value}
        except (OSError, json.JSONDecodeError):
            pass
    sources = [str(s) for s in payload.get("sources", [])]
    if str(source) not in sources:
        sources.append(str(source))
    payload["sources"] = sources
    payload["last_seen"] = now_iso()
    atomic_write(sidecar, json.dumps(payload, indent=2).encode("utf-8") + b"\n")
    return digest


def rebuild_entries(store: Path) -> dict[str, dict]:
    """Recover the index from blob sidecars when the manifest is missing or corrupt."""
    blobs = store / BLOBS_DIRNAME
    if not blobs.is_dir():
        return {}

    entries: dict[str, dict] = {}
    sidecars = sorted(blobs.rglob("*.json"), key=lambda p: p.stat().st_mtime)
    for sidecar in sidecars:
        try:
            payload = json.loads(sidecar.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for source in payload.get("sources", []):
            entries[key_for(Path(source))] = {
                "kind": payload.get("kind", Kind.SKILLS.value),
                "source": source,
                "sha256": sidecar.stem,
                "tombstone": Tombstone.STUB.value,
                "quarantined_at": payload.get("first_seen", ""),
                "recovered": True,
            }
    return entries


@dataclass
class Manifest:
    path: Path
    entries: dict[str, dict]

    @classmethod
    def load(cls, store: Path) -> Manifest:
        path = store / MANIFEST_NAME
        if not path.is_file():
            return cls(path, rebuild_entries(store))
        try:
            payload = json.loads(path.read_text("utf-8"))
            entries = payload["entries"]
            if not isinstance(entries, dict):
                raise TypeError("entries is not a mapping")
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
            quarantined = path.with_name(
                f"manifest.corrupt-{int(datetime.now().timestamp())}.json"
            )
            console.print(
                f"[red]unreadable manifest[/] ({error}); moved to {quarantined}"
            )
            path.rename(quarantined)
            return cls(path, rebuild_entries(store))
        return cls(path, entries)

    def save(self, dry_run: bool) -> None:
        if dry_run:
            return
        payload = {
            "version": MANIFEST_VERSION,
            "updated_at": now_iso(),
            "entries": self.entries,
        }
        atomic_write(self.path, json.dumps(payload, indent=2).encode("utf-8") + b"\n")

    def of_kind(self, kinds: set[Kind]) -> list[tuple[str, dict]]:
        wanted = {kind.value for kind in kinds}
        return [
            (k, e) for k, e in sorted(self.entries.items()) if e.get("kind") in wanted
        ]


# ---------------------------------- tombstones ------------------------------------


def is_tombstone(path: Path) -> bool:
    if path.is_dir():
        return (path / MARKER_NAME).is_file()
    try:
        return SENTINEL.encode() in path.read_bytes()
    except OSError:
        return False


def digest_of(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def stub_bytes(path: Path, kind: Kind) -> bytes:
    if path.suffix.lower() == ".json":
        payload = {
            "_comment": f"{SENTINEL}: contents quarantined by AgentPlugins.",
            "hooks": {},
        }
        return json.dumps(payload, indent=2).encode("utf-8") + b"\n"

    name = path.parent.name if path.name.lower() == "skill.md" else path.stem
    return (
        "---\n"
        f"name: {json.dumps(name)}\n"
        'description: ""\n'
        "disable-model-invocation: true\n"
        f"# {SENTINEL}\n"
        "---\n"
        "\n"
        f"<!-- {SENTINEL}\n"
        f"     This extension-contributed {kind.value[:-1]} was quarantined by AgentPlugins.\n"
        "     Restore it with: just scripts::extensions-restore\n"
        "-->\n"
    ).encode("utf-8")


def apply_tombstone(
    path: Path, owner: Path, kind: Kind, strategy: Tombstone, digest: str
) -> str:
    remove_path(path)
    if strategy is Tombstone.NONE:
        prune_empty_parents(path, owner)
        return "deleted"
    if strategy is Tombstone.DIR:
        path.mkdir(parents=True, exist_ok=True)
        marker = {
            "sentinel": SENTINEL,
            "kind": kind.value,
            "sha256": digest,
            "at": now_iso(),
        }
        atomic_write(
            path / MARKER_NAME, json.dumps(marker, indent=2).encode("utf-8") + b"\n"
        )
        return "directory tombstone"
    atomic_write(path, stub_bytes(path, kind))
    set_read_only(path)
    return "read-only stub"


# ---------------------------------- operations ------------------------------------


def quarantine(
    path: Path,
    owner: Path,
    kind: Kind,
    store: Path,
    manifest: Manifest,
    strategy: Tombstone,
    dry_run: bool,
) -> Result:
    identity = key_for(path)
    entry = manifest.entries.get(identity)

    try:
        data = path.read_bytes()
    except OSError as error:
        return fault(path, error)

    if SENTINEL.encode() in data:
        if entry is None:
            return Result(path, Outcome.UNCHANGED, "foreign tombstone, left alone")
        if entry.get("tombstone") == strategy.value:
            if not dry_run:
                entry["verified_at"] = now_iso()
            return Result(path, Outcome.UNCHANGED, "tombstone intact")
        # A weaker tombstone from an earlier run; upgrade it without re-archiving.
        if dry_run:
            return Result(
                path, Outcome.CHANGED, f"retombstone as {strategy.value} (dry run)"
            )
        try:
            note = apply_tombstone(path, owner, kind, strategy, entry.get("sha256", ""))
        except OSError as error:
            return fault(path, error)
        entry["tombstone"] = strategy.value
        entry["owner"] = str(owner)
        entry["updated_at"] = now_iso()
        return Result(path, Outcome.CHANGED, f"tombstone upgraded to {note}")

    respawns = int(entry.get("respawns", 0)) + 1 if entry else 0
    history = list(entry.get("history", [])) if entry else []

    try:
        digest = put_blob(store, data, kind, path, dry_run)
        note = (
            apply_tombstone(path, owner, kind, strategy, digest)
            if not dry_run
            else strategy.value
        )
    except OSError as error:
        return fault(path, error)

    if digest not in history:
        history.append(digest)
    manifest.entries[identity] = {
        "kind": kind.value,
        "source": str(path),
        "owner": str(owner),
        "sha256": digest,
        "size": len(data),
        "tombstone": strategy.value,
        "quarantined_at": entry.get("quarantined_at", now_iso())
        if entry
        else now_iso(),
        "updated_at": now_iso(),
        "respawns": respawns,
        "history": history,
    }

    detail = f"{note}, {len(data)} bytes held"
    if respawns:
        detail = f"{detail} (respawn #{respawns})"
    return Result(path, Outcome.CHANGED, f"{detail}{' (dry run)' if dry_run else ''}")


def sweep_tombstones(
    kinds: set[Kind], manifest: Manifest, strategy: Tombstone, dry_run: bool
) -> list[Result]:
    """Directory tombstones are invisible to the file scan, so migrate them separately."""
    results: list[Result] = []
    for _, entry in manifest.of_kind(kinds):
        path = Path(entry["source"])
        if entry.get("tombstone") == strategy.value or not path.is_dir():
            continue
        if not is_tombstone(path):
            continue
        if dry_run:
            results.append(
                Result(
                    path, Outcome.CHANGED, f"retombstone as {strategy.value} (dry run)"
                )
            )
            continue
        owner = owner_of(entry, path)
        try:
            note = apply_tombstone(
                path, owner, Kind(entry["kind"]), strategy, entry.get("sha256", "")
            )
        except (OSError, ValueError) as error:
            results.append(fault(path, error))
            continue
        entry["tombstone"] = strategy.value
        entry["owner"] = str(owner)
        entry["updated_at"] = now_iso()
        results.append(Result(path, Outcome.CHANGED, f"tombstone upgraded to {note}"))
    return results


def restore(
    identity: str,
    entry: dict,
    store: Path,
    manifest: Manifest,
    force: bool,
    prune: bool,
    dry_run: bool,
) -> Result:
    path = Path(entry["source"])
    digest = entry.get("sha256", "")
    blob = blob_path(store, digest)

    def drop() -> None:
        if not dry_run:
            manifest.entries.pop(identity, None)

    if not blob.is_file():
        return Result(path, Outcome.FAILED, f"backup blob {digest[:12]} is missing")
    try:
        data = blob.read_bytes()
    except OSError as error:
        return fault(path, error)

    if path.exists() or path.is_symlink():
        if path.is_dir():
            if not is_tombstone(path):
                return Result(
                    path, Outcome.CONFLICT, "a real directory now occupies this path"
                )
        else:
            try:
                current = path.read_bytes()
            except OSError as error:
                return fault(path, error)
            if current == data:
                drop()
                return Result(path, Outcome.UNCHANGED, "already restored")
            if SENTINEL.encode() not in current and not force:
                return Result(
                    path,
                    Outcome.CONFLICT,
                    "extension rewrote this file; use --force to overwrite",
                )
    else:
        # Deletion prunes emptied folders, so judge by the extension root, not the parent.
        owner = owner_of(entry, path)
        if not owner.is_dir():
            if prune:
                drop()
                return Result(
                    path, Outcome.SKIPPED, "extension gone; entry pruned, blob kept"
                )
            return Result(
                path, Outcome.SKIPPED, "extension gone; use --prune to forget it"
            )

    if dry_run:
        return Result(path, Outcome.CHANGED, "restore (dry run)")

    try:
        remove_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(path, data)
        set_writable(path)
    except OSError as error:
        return fault(path, error)

    drop()
    return Result(path, Outcome.CHANGED, f"restored {len(data)} bytes")


# ---------------------------------- reporting -------------------------------------


def report(results: list[Result], verbose: bool) -> None:
    table = Table(box=None, pad_edge=False)
    table.add_column("outcome")
    table.add_column("path", overflow="fold")
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
    summary = ", ".join(f"{c} {o.value}" for o, c in counts.items() if c)
    console.print(f"[bold]{len(results)} files[/]: {summary or 'nothing to do'}")

    if blocked := sum(ELEVATION_HINT in r.detail for r in results):
        console.print(
            f"[yellow]{blocked} files live in the VS Code install tree.[/] "
            "Re-run from an administrator terminal to clear them."
        )


def resolve_kinds(kinds: list[Kind] | None) -> set[Kind]:
    return set(kinds) if kinds else set(Kind)


def collect_roots(insiders: str, builtin: str, roots: list[Path] | None) -> list[Path]:
    resolved: list[Path] = []
    for root in roots or []:
        if root.is_dir():
            resolved.append(root)
        else:
            console.print(f"[yellow]skipping missing root:[/] {root}")
    if not roots:
        resolved.extend(default_roots(parse_bool(insiders)))
        if parse_bool(builtin):
            resolved.extend(builtin_roots())
    return resolved


# ---------------------------------- commands --------------------------------------

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Quarantine and restore extension-contributed skills, prompts and hooks.",
)

KindOption = Annotated[
    list[Kind] | None,
    typer.Option(
        "--kind", "-k", help="Asset kind to act on. Repeatable. Defaults to all."
    ),
]
StoreOption = Annotated[
    Path | None,
    typer.Option("--store", help="Quarantine directory. Defaults to local app data."),
]
DryRunOption = Annotated[
    bool, typer.Option("--dry-run", help="Report changes without writing.")
]
VerboseOption = Annotated[
    bool, typer.Option("--verbose", "-v", help="Include unchanged files in the report.")
]


@app.command()
def nuke(
    kind: KindOption = None,
    insiders: Annotated[
        str,
        typer.Option(
            "--insiders", help="Target VS Code Insiders; false targets stable."
        ),
    ] = "true",
    builtin: Annotated[
        str,
        typer.Option(
            "--builtin", help="Also scan bundled extensions; needs an elevated shell."
        ),
    ] = "true",
    roots: Annotated[
        list[Path] | None,
        typer.Option("--root", help="Extension directory to scan. Repeatable."),
    ] = None,
    tombstone: Annotated[
        Tombstone,
        typer.Option(
            "--tombstone",
            help="What to leave behind: nothing, a blocking dir, or a stub.",
        ),
    ] = Tombstone.NONE,
    store: StoreOption = None,
    dry_run: DryRunOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Move extension-contributed assets into the quarantine store."""
    kinds = resolve_kinds(kind)
    search_roots = collect_roots(insiders, builtin, roots)
    if not search_roots:
        console.print("[red]no VS Code extension directories found[/]")
        raise typer.Exit(code=1)

    store = store or default_store()
    manifest = Manifest.load(store)
    for root in search_roots:
        writable = (
            "" if is_writable(root) else " [red](read-only: needs an elevated shell)[/]"
        )
        console.print(f"[dim]scanning[/] {root}{writable}")
    console.print(
        f"quarantining [bold]{', '.join(sorted(k.value for k in kinds))}[/] "
        f"leaving [bold]{tombstone.value}[/] behind, archiving into {store}"
    )

    results = [
        quarantine(path, owner, kind_, store, manifest, tombstone, dry_run)
        for kind_ in sorted(kinds, key=lambda k: k.value)
        for path, owner in iter_candidates(search_roots, kind_)
    ]
    results.extend(sweep_tombstones(kinds, manifest, tombstone, dry_run))
    manifest.save(dry_run)
    report(results, verbose)
    if any(r.outcome is Outcome.FAILED for r in results):
        raise typer.Exit(code=1)


@app.command(name="restore")
def restore_command(
    kind: KindOption = None,
    store: StoreOption = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force", help="Overwrite a file the extension recreated itself."
        ),
    ] = False,
    prune: Annotated[
        bool,
        typer.Option(
            "--prune", help="Forget entries whose extension no longer exists."
        ),
    ] = False,
    dry_run: DryRunOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Put quarantined assets back where they came from."""
    kinds = resolve_kinds(kind)
    store = store or default_store()
    manifest = Manifest.load(store)
    entries = manifest.of_kind(kinds)
    if not entries:
        console.print(
            f"[yellow]nothing quarantined[/] for {', '.join(k.value for k in kinds)}"
        )
        return

    console.print(f"restoring [bold]{len(entries)}[/] entries from {store}")
    results = [
        restore(identity, entry, store, manifest, force, prune, dry_run)
        for identity, entry in entries
    ]
    manifest.save(dry_run)
    report(results, verbose)
    if any(r.outcome is Outcome.FAILED for r in results):
        raise typer.Exit(code=1)


@app.command()
def status(store: StoreOption = None, verbose: VerboseOption = False) -> None:
    """Show what is currently held in quarantine."""
    store = store or default_store()
    manifest = Manifest.load(store)
    console.print(f"[dim]store[/] {store}")
    if not manifest.entries:
        console.print("[bold]quarantine is empty[/]")
        return

    table = Table(box=None, pad_edge=False)
    table.add_column("kind")
    table.add_column("tombstone")
    table.add_column("state")
    table.add_column("path", overflow="fold")
    for _, entry in sorted(manifest.entries.items()):
        path = Path(entry["source"])
        owner = owner_of(entry, path)
        if not path.exists():
            state, style = (
                ("held", "green") if owner.is_dir() else ("extension gone", "yellow")
            )
        elif is_tombstone(path):
            state, style = "held", "green"
        elif path.is_file() and digest_of(path) == entry.get("sha256"):
            state, style = "restored", "dim"
        else:
            state, style = "respawned", "red"
        if verbose or state != "held":
            table.add_row(
                entry.get("kind", "?"),
                entry.get("tombstone", "?"),
                f"[{style}]{state}[/]",
                str(path),
            )

    if table.row_count:
        console.print(table)
    counts: dict[str, int] = {}
    for entry in manifest.entries.values():
        counts[entry.get("kind", "?")] = counts.get(entry.get("kind", "?"), 0) + 1
    summary = ", ".join(f"{count} {name}" for name, count in sorted(counts.items()))
    console.print(f"[bold]{len(manifest.entries)} entries held[/]: {summary}")


if __name__ == "__main__":
    app()
