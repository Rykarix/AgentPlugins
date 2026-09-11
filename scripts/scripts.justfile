set allow-duplicate-recipes
set allow-duplicate-variables
set shell := ["bash", "-euo", "pipefail", "-c"]

# ---------------------------------- DEPENDENCIES ----------------------------------

uv := require("uv") # https://docs.astral.sh/uv

# ---------------------------------- CONSTANTS -------------------------------------

SKILLS := module_directory() / "extension_contributed_skills.py"
ASSETS := module_directory() / "extension_contributed_assets.py"

# ---------------------------------- COMMANDS --------------------------------------

[doc("Lists the scripts commands.")]
list:
    @just --justfile "{{ module_file() }}" --list

[doc("Sets disable-model-invocation in extension-contributed SKILL.md files.")]
[group("skills")]
vscode-extension-contributed-skills enabled="false" insiders="true" *args:
    @uv run "{{ SKILLS }}" --enabled {{ enabled }} --insiders {{ insiders }} {{ args }}
alias ds := vscode-extension-contributed-skills

# ---------------------------------- gtfo commands... --------------------------------------
# I'm so sick of vscodes extension system spamming their ai slopcrap into my agentic workflows and NOT giving me a way to remove or disable.
# These commands solve this problem by removing anything it finds into some backup location so that it can be restored if the user wants.
#
# The files are deleted outright; a copy of every byte is archived first, so `restore` brings them back.
# VS Code's own bundled skills live under Program Files, so run this from an ADMIN terminal to clear those.
# Extension and VS Code updates reinstall into a fresh versioned folder, so re-run `gtfo` after one.
# `tombstone=dir` leaves a directory in the file's place instead, which physically blocks recreation.
[doc("Delete all extension-contributed SKILL.md files. tombstone: none|dir|stub.")]
[group("gtfo")]
vscode-nuke-extension-contributed-skills insiders="true" tombstone="none" *args:
    @uv run "{{ ASSETS }}" nuke --kind skills --insiders {{ insiders }} --tombstone {{ tombstone }} {{ args }}
alias ns := vscode-nuke-extension-contributed-skills

[doc("Delete all extension-contributed prompt, instruction, chatmode and agent files.")]
[group("gtfo")]
vscode-nuke-extension-contributed-prompts insiders="true" tombstone="none" *args:
    @uv run "{{ ASSETS }}" nuke --kind prompts --insiders {{ insiders }} --tombstone {{ tombstone }} {{ args }}
alias np := vscode-nuke-extension-contributed-prompts

[doc("Delete all extension-contributed hook files.")]
[group("gtfo")]
vscode-nuke-extension-contributed-hooks insiders="true" tombstone="none" *args:
    @uv run "{{ ASSETS }}" nuke --kind hooks --insiders {{ insiders }} --tombstone {{ tombstone }} {{ args }}
alias nh := vscode-nuke-extension-contributed-hooks

[doc("Restore all quarantined SKILL.md files.")]
[group("gtfo")]
vscode-restore-extension-contributed-skills *args:
    @uv run "{{ ASSETS }}" restore --kind skills {{ args }}
alias rs := vscode-restore-extension-contributed-skills

[doc("Restore all quarantined prompt, instruction, chatmode and agent files.")]
[group("gtfo")]
vscode-restore-extension-contributed-prompts *args:
    @uv run "{{ ASSETS }}" restore --kind prompts {{ args }}
alias rp := vscode-restore-extension-contributed-prompts

[doc("Restore all quarantined hook files.")]
[group("gtfo")]
vscode-restore-extension-contributed-hooks *args:
    @uv run "{{ ASSETS }}" restore --kind hooks {{ args }}
alias rh := vscode-restore-extension-contributed-hooks

[doc("Show what is currently held in quarantine and whether any file has respawned.")]
[group("gtfo")]
vscode-extension-quarantine-status *args:
    @uv run "{{ ASSETS }}" status {{ args }}
alias qs := vscode-extension-quarantine-status

[doc("Delete every extension-contributed skill, prompt and hook. Re-run after VS Code or extension updates.")]
[group("gtfo")]
extensions-gtfo insiders="true" tombstone="none" *args: (vscode-nuke-extension-contributed-skills insiders tombstone args) (vscode-nuke-extension-contributed-prompts insiders tombstone args) (vscode-nuke-extension-contributed-hooks insiders tombstone args)
alias gtfo := extensions-gtfo

[doc("Restore everything held in quarantine.")]
[group("gtfo")]
extensions-restore *args: (vscode-restore-extension-contributed-skills args) (vscode-restore-extension-contributed-prompts args) (vscode-restore-extension-contributed-hooks args)
alias restore := extensions-restore