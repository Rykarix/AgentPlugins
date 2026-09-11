#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

import json
import re
import sys

BLOCK_REASON = (
    "Shell command blocked: User has explicitly told you to use existing tools "
    "instead of shell commands."
)

VSCODE_COMMAND_MAP = {
    "cat": "readFile",
    "ls": "listDirectory",
    "grep": ["textSearch", "codebase"],
    "find": "fileSearch",
    "glob": "fileSearch",
    "curl": ["web", "githubRepo", "githubTextSearch"],
}

COMMAND_PATTERN = re.compile(
    r"(?:^|[;&|]\s*)(?:sudo\s+|command\s+|env\s+)*"
    r"(?P<command>[A-Za-z][A-Za-z0-9_-]*)(?=\s|$)"
)


def get_tool_name(payload: dict) -> str:
    tool_name = str(payload.get("toolName") or payload.get("tool_name") or "").lower()
    return re.split(r"[/.]", tool_name)[-1]


def get_tool_input(payload: dict) -> dict:
    tool_input = payload.get("tool_input") or payload.get("toolInput")
    if tool_input is None:
        tool_input = payload.get("toolArgs")

    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except json.JSONDecodeError:
            return {}

    return tool_input if isinstance(tool_input, dict) else {}


def build_result(reason: str) -> dict:
    return {
        "systemMessage": reason,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
    }


def format_tool_suggestion(tools: str | list[str]) -> str:
    if isinstance(tools, str):
        return f"Use {tools} instead."

    if len(tools) == 1:
        return f"Use {tools[0]} instead."

    return f"Use one of {', '.join(tools)} instead."


def main() -> None:
    try:
        input_data = sys.stdin.buffer.read().decode("utf-8")
        if not input_data:
            return

        request = json.loads(input_data)
        if not isinstance(request, dict):
            return

        tool_name = get_tool_name(request)
        tool_input = get_tool_input(request)
        command = str(tool_input.get("command", ""))
        shell = str(tool_input.get("shell", "")).lower()

        named_shell_tool = tool_name in {"bash", "powershell", "pwsh"}
        terminal_tool = tool_name in {
            "run_in_terminal",
            "runterminalcommand",
            "runterminalcommandtool",
        }
        bash_or_powershell = "bash" in shell or "powershell" in shell or "pwsh" in shell

        # Match mapped commands at command positions, including chained commands.
        blocked_command = next(
            (
                match.group("command").lower()
                for match in COMMAND_PATTERN.finditer(command.strip())
                if match.group("command").lower() in VSCODE_COMMAND_MAP
            ),
            None,
        )

        if blocked_command and (
            named_shell_tool or terminal_tool or bash_or_powershell
        ):
            vscode_tools = VSCODE_COMMAND_MAP[blocked_command]
            reason = (
                f"{BLOCK_REASON} Do not use `{blocked_command}`. "
                f"{format_tool_suggestion(vscode_tools)}"
            )
            result = build_result(reason)
            sys.stdout.buffer.write(json.dumps(result).encode("utf-8") + b"\n")
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, AttributeError):
        # Hook failures should not interrupt the agent session.
        return


if __name__ == "__main__":
    main()
