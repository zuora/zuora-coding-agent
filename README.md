# Zuora Coding Agent

A plugin for **Claude Code**, **Cursor**, and **Codex** that accelerates Zuora-specific development work — API integrations, Workflow design and build, Meter design and build, Order migration, Invoice Settlement migration, and best-practice validation.

Powered by [zuora-mcp](https://www.npmjs.com/package/zuora-mcp).

## Available commands

| Command | Purpose |
|---|---|
| `/zuora-api-design` | Propose the right Zuora API approach for a business requirement |
| `/zuora-api-build` | Generate or update integration code using the selected APIs |
| `/zuora-workflow-design` | Design a Zuora Workflow-based solution |
| `/zuora-workflow-build` | Implement workflow assets or related code/config |
| `/zuora-is-migration-design` | Produce IS migration strategy, mappings, phases, and risks |
| `/zuora-is-migration-build` | Generate IS migration implementation artifacts |
| `/zuora-order-migration-design` | Produce order migration design, sequencing, and edge-case analysis |
| `/zuora-order-migration-build` | Generate order migration implementation artifacts |
| `/zuora-meter-design` | Design a Zuora meter — pick type, define topology, and collect per-operator field values |
| `/zuora-meter-build` | Compose an importable Zuora meter JSON from a design |
| `/zuora-validate` | Validate generated code/payloads/approach against Zuora patterns |
| `/zuora-review` | Review work for Zuora best practices |

The plugin also provides **passive Zuora awareness** — when you discuss Zuora topics in any conversation, it will suggest relevant commands and use zuora-mcp tools to provide accurate answers.

## Disclaimer

This plugin uses AI to generate code, API payloads, and migration artifacts. All output should be reviewed and tested before use in any customer-facing environment. Zuora, Inc. makes no warranties regarding the accuracy, completeness, or fitness for purpose of any generated content. **Use at your own risk.**

## Prerequisites

- [Claude Code](https://claude.ai/code), [Cursor](https://cursor.com), or [Codex](https://openai.com/codex) installed
- Zuora tenant credentials (OAuth client ID and secret)
- Node.js >= 18 (for zuora-mcp via npx)

## Setup

Before you begin, create a Zuora OAuth client:

1. Log in to your Zuora tenant
2. Go to **Settings > Administration > Manage Users**
3. Navigate to **OAuth Clients** tab
4. Click **Create OAuth Client**, select permissions, and save
5. Copy the **Client ID** and **Client Secret**

**Zuora environment URLs:**

| Environment | URL |
|---|---|
| US API Sandbox (Cloud 2) | `https://rest.apisandbox.zuora.com` |
| US Central Sandbox | `https://rest.test.zuora.com` |
| EU Sandbox | `https://rest.sandbox.eu.zuora.com` |
| US Production | `https://rest.zuora.com` |
| EU Production | `https://rest.eu.zuora.com` |

---

### Claude Code

**Step 1 — Install**

From the marketplace (recommended):

```
/plugin marketplace add zuora/zuora-coding-agent
/plugin install zuora-coding-agent@zuora-devex
```

Then **restart Claude Code**.

Or load locally for a single session:

```bash
git clone git@github.com:zuora/zuora-coding-agent.git
claude --plugin-dir /path/to/zuora-coding-agent
```

**Verify:** Type `/zuora` — you should see all `/zuora-*` commands listed.

**Step 2 — Configure credentials**

Add to `~/.claude/settings.json` under the `"env"` key:

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

---

### Cursor

**Step 1 — Install**

Clone this repo, then run in the Cursor chat window:

```
/add-plugin /path/to/zuora-coding-agent --no-symlink
```

> **Note:** The `--no-symlink` flag is required due to a [known Cursor issue](https://github.com/cursor/plugins/issues/35).

Then reload Cursor: **Cmd+Shift+P → Developer: Reload Window**

**Step 2 — Configure credentials**

Go to **Settings → Plugins → zuora-coding-agent → Zuora Mcp** and set `ZUORA_BASE_URL`, `ZUORA_CLIENT_ID`, and `ZUORA_CLIENT_SECRET`.

Then reload Cursor: **Cmd+Shift+P → Developer: Reload Window**

---

### Codex

**Step 1 — Install**

Register the marketplace from the remote repo:

```bash
codex plugin marketplace add https://github.com/zuora/zuora-coding-agent
```

Then start Codex and open the plugin browser:

```bash
codex
/plugins
```

In the plugin browser, switch to the **Zuora Developer Experience** marketplace, open **Zuora Coding Agent**, and choose **Install plugin**.

**Step 2 — Configure credentials**

After installing the plugin, edit the installed Codex plugin cache file with your preferred text editor:

```text
~/.codex/plugins/cache/zuora-devex/zuora-coding-agent/{replace-me-with-plugin-version}/.mcp.json
```

Replace `{replace-me-with-plugin-version}` with the installed plugin version, then update `ZUORA_BASE_URL`, `ZUORA_CLIENT_ID`, and `ZUORA_CLIENT_SECRET` in that `.mcp.json` file.

Then restart Codex to apply the changes.

---

## Architecture

```
User in Claude Code / Cursor / Codex
  └── Zuora Coding Agent Plugin
        ├── Skills (workflow orchestration and domain playbooks)
        ├── zuora-mcp (live API specs, metadata, validation, code generation)
        └── IDE built-in tools (file editing, search, shell)
```

Skills tell the AI **how** to approach a Zuora task. zuora-mcp provides **what** — authoritative API specs, object metadata, and code generation capabilities.

## Troubleshooting

**Commands not showing:**
- If installed via marketplace: verify with the IDE's plugin list, then reinstall
- If using local load: verify the path points to the correct plugin folder

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

### Maintainers

| Name | Area |
|---|---|
| WJ | Plugin Lead |
| Wenxuan | Workflow |
| Amy | Invoice Settlement Migration |
| Richard | Order Migration |
| Jianfeng | MCP Tool |
| Gautam | Mediation |

## License

MIT — see [LICENSE](LICENSE) for details.

Copyright (c) 2026 Zuora, Inc.
