# Plugins

Each subdirectory here is an independent Agent Plugin with its own `plugin.json`.
A plugin is only visible to users once it is listed in `../.claude-plugin/marketplace.json`.

## Adding a new plugin

1. Copy the template:
   ```bash
   cp -r ../templates/plugin-template ./my-new-plugin
   ```
2. Fill in `my-new-plugin/plugin.json` — `name` must be lowercase `a-z0-9-.`, 1-64 chars.
3. Add an entry to `../.claude-plugin/marketplace.json`:
   ```json
   { "name": "my-new-plugin", "source": "./plugins/my-new-plugin", "description": "..." }
   ```
   `source` is relative to the **repo root**, not to `.claude-plugin/`.
4. Author components inside the plugin folder:
   - `skills/<skill-name>/SKILL.md` — portable skills
   - `mcp.json` — MCP servers
   - `com.github.copilot/agents/*.agent.md`
   - `com.github.copilot/commands/*.prompt.md`
   - `com.github.copilot/rules/*.instructions.md`
   - `com.github.copilot/hooks/hooks.json`

## Rules of thumb

- Plugins are independent units: no cross-plugin file references. If two plugins need
  the same skill, duplicate it or split it into a third plugin.
- `${PLUGIN_ROOT}` in hooks and `mcp.json` resolves to *that plugin's* folder, not the repo root.
- Each plugin carries its own `version` in `plugin.json`; bump them independently.
