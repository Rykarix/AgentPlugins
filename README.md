# Agent Plugins

Collection of agent related stuff for various harnesses I use

## Requirements & Suggested settings

- uv (for running hooks)
- 

## Installing

Add this repo as a marketplace in VS Code `settings.json`:

```jsonc
"chat.plugins.marketplaces": ["Rykarix/AgentPlugins"]
```

Then browse and install individual plugins via `@agentPlugins` in the Extensions view.

## The intent
- Create an agent that does things efficiently
- Standards decoupled from the agent for ease of use & to demonstrate an oppinionated approach on how to build agents.


## Local development

Point VS Code at plugin folders directly — one entry per plugin, no marketplace needed:

```jsonc
"chat.pluginLocations": {
  "c:\\path\\to\\this\\repo\\plugins\\developer-agent": true
}
```

## Reference

- Agent Plugins spec: https://agent-plugins.org/specification
- VS Code plugin docs: https://code.visualstudio.com/docs/agent-customization/agent-plugins
- Agent Skills spec: https://agentskills.io/specification
- Marketplace schema: https://code.claude.com/docs/en/plugin-marketplaces
