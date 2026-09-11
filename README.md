# Agent Plugins

Collection of agent related stuff for various harnesses I use

## Installing

Add this repo as a marketplace in VS Code `settings.json`:

```jsonc
"chat.plugins.marketplaces": ["TODO-owner/TODO-repo"]
```

Then browse and install individual plugins via `@agentPlugins` in the Extensions view.

## Local development

Point VS Code at plugin folders directly — one entry per plugin, no marketplace needed:

```jsonc
"chat.pluginLocations": {
  "c:\\path\\to\\this\\repo\\plugins\\developer-agent-plugin": true
}
```

## Adding a plugin

See [`plugins/README.md`](plugins/README.md). Short version: copy `templates/plugin-template`
into `plugins/<name>/`, fill in its `plugin.json`, and add an entry to
`.claude-plugin/marketplace.json` with `"source": "./plugins/<name>"`.

## Reference

- Agent Plugins spec: https://agent-plugins.org/specification
- VS Code plugin docs: https://code.visualstudio.com/docs/agent-customization/agent-plugins
- Agent Skills spec: https://agentskills.io/specification
- Marketplace schema: https://code.claude.com/docs/en/plugin-marketplaces
