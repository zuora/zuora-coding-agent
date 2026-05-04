# Zuora Coding Agent

A plugin for **Claude Code** and **Cursor** that accelerates Zuora-specific development work including API integrations, workflow development, migrations, template design, and best-practice validation.

Powered by [zuora-mcp](https://www.npmjs.com/package/zuora-mcp).

## Prerequisites

- [Claude Code](https://claude.ai/code) or [Cursor](https://cursor.com) installed
- Zuora tenant credentials (OAuth client ID and secret)
- Node.js >= 18 (for zuora-mcp via npx)

## Setup

### 1. Install the plugin

#### Claude Code

Clone this repo and load for a single session:

```bash
git clone git@github.com:zuora/zuora-coding-agent.git
claude --plugin-dir /path/to/zuora-coding-agent
```

The `--plugin-dir` flag loads the plugin for that session only. Provide the absolute path to the cloned folder.

**Verify:** Open Claude Code and type `/help` — you should see all `/zuora-*` commands listed.

#### Cursor

Clone this repo, then run in the Cursor chat window:

```
/add-plugin /path/to/zuora-coding-agent --no-symlink
```

> **Note:** The `--no-symlink` flag is required due to a [known Cursor issue](https://github.com/cursor/plugins/issues/35).

Then reload Cursor: **Cmd+Shift+P → Developer: Reload Window**

### 2. Configure Zuora credentials

The plugin connects to your Zuora tenant via the zuora-mcp server. You need to set environment variables so zuora-mcp can authenticate.

**Create an OAuth client in Zuora:**
1. Log in to your Zuora tenant
2. Go to **Settings > Administration > Manage Users**
3. Navigate to **OAuth Clients** tab
4. Click **Create OAuth Client**
5. Select the appropriate permissions and save
6. Copy the **Client ID** and **Client Secret**

**Zuora environment URLs:**

| Environment | URL |
|---|---|
| US API Sandbox (Cloud 2) | `https://rest.apisandbox.zuora.com` |
| US Central Sandbox | `https://rest.test.zuora.com` |
| EU Sandbox | `https://rest.sandbox.eu.zuora.com` |
| US Production | `https://rest.zuora.com` |
| EU Production | `https://rest.eu.zuora.com` |

#### Claude Code

Add the variables to `~/.claude/settings.json` under the `"env"` key:

```json
{
  "env": {
    "ZUORA_BASE_URL": "https://rest.apisandbox.zuora.com",
    "ZUORA_CLIENT_ID": "your-client-id",
    "ZUORA_CLIENT_SECRET": "your-client-secret"
  }
}
```

If `"env"` already exists, merge the Zuora keys into it.

#### Cursor

**Option A — Cursor plugin settings**

After installing, go to **Settings → Plugins → zuora-coding-agent → Zuora Mcp** and set `ZUORA_BASE_URL`, `ZUORA_CLIENT_ID`, and `ZUORA_CLIENT_SECRET`.

**Option B — Shell profile**

Add to `~/.zshrc` or `~/.bashrc`:

```bash
export ZUORA_BASE_URL="https://rest.apisandbox.zuora.com"
export ZUORA_CLIENT_ID="your-client-id"
export ZUORA_CLIENT_SECRET="your-client-secret"

# Optional — for multi-entity or multi-org tenants
export ZUORA_ENTITY_IDS="entity-id-1,entity-id-2"
export ZUORA_ORG_IDS="org-id-1,org-id-2"
```

Then reload: `source ~/.zshrc`

**Note:** The plugin's `.mcp.json` uses `${ZUORA_BASE_URL}` syntax to read these from your environment at runtime. No secrets are stored in the plugin files.

## Available commands

| Command | Purpose |
|---|---|
| `/zuora-api-design` | Propose the right Zuora API approach for a business requirement |
| `/zuora-api-build` | Generate or update integration code using the selected APIs |
| `/zuora-workflow-design` | Design a Zuora Workflow-based solution |
| `/zuora-workflow-build` | Implement workflow assets or related code/config |
| `/zuora-is-migration-plan` | Produce IS migration strategy, mappings, phases, and risks |
| `/zuora-is-migration-build` | Generate IS migration implementation artifacts |
| `/zuora-order-migration-plan` | Produce order migration design, sequencing, and edge-case analysis |
| `/zuora-order-migration-build` | Generate order migration implementation artifacts |
| `/zuora-validate` | Validate generated code/payloads/approach against Zuora patterns |
| `/zuora-review` | Review work for Zuora best practices |

The plugin also provides **passive Zuora awareness** — when you discuss Zuora topics in any conversation, it will suggest relevant commands and use zuora-mcp tools to provide accurate answers.

## Architecture

```
User in Claude Code / Cursor
  └── Zuora Coding Agent Plugin
        ├── Skills (workflow orchestration and domain playbooks)
        ├── zuora-mcp (live API specs, metadata, validation, code generation)
        └── IDE built-in tools (file editing, search, shell)
```

Skills tell the AI **how** to approach a Zuora task. zuora-mcp provides **what** — authoritative API specs, object metadata, and code generation capabilities.

## Troubleshooting

**Commands not showing:**
- If using `--plugin-dir`, verify the path points to the folder containing `.claude-plugin/plugin.json`
- If installed via marketplace: `claude plugin list` to verify, then reinstall

**MCP server not connecting:**
- Check env vars are set: `echo $ZUORA_BASE_URL`
- Check npx works: `npx -y zuora-mcp@latest --help`
- Check Node.js version: `node --version` (must be >= 18)

**Authentication errors:**
- Verify OAuth client is active in Zuora
- Check `ZUORA_BASE_URL` matches your tenant environment
- Ensure `ZUORA_CLIENT_ID` and `ZUORA_CLIENT_SECRET` are correct

## Contributing

We welcome contributions. Please open an issue or pull request on [GitHub](https://github.com/zuora/zuora-coding-agent).

For significant changes, open an issue first to discuss the proposed change.

## License

MIT — see [LICENSE](LICENSE) for details.

Copyright (c) 2026 Zuora, Inc.
