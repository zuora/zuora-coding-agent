# Zuora Coding Agent Plugin

The **Zuora Coding Agent plugin (ZCA)** is a bundle of skills and related material for developers building against Zuora. ZCA combines task-specific skills with Zuora reference material so your agentic creations can help complete Zuora implementation work. In this content:

```
plugin = package of capabilities

skill = task-specific instructions/workflow, often inside a plugin
```
A plugin can contribute many skills, but a skill is what your AI client or tool will leverage for work. This is a developers tool, to aid development that then undergoes rigourous testing prior to deployment, do not run any of these skills directly against a Zuora Production tenant. How to avoid doing this is detailed below.

## What's Included

- **Skills**: task playbooks for API design, code generation, Workflow design, Order API migration, Invoice Settlement migration, meter design, dynamic pricing setup, CPQ Apex/Quote Studio customization and migration, validation, and review.
- **Local Zuora MCP Server**: Provides Zuora API and product helpers for API specs, SDK patterns, object queries, reports, workflows, billing documents, and tenant-aware validation.
- **Reference material**: Zuora-specific migration mappings, workflow patterns, meter operator schemas, Liquid filter reference, and integration best practices.
- **Local linter scripts**: `scripts/lint-workflow-json.js` and `scripts/lint-meter-json.js` for pre-import structural and semantic validation of generated artifacts.

## What You Can Use ZCA For

You can our ZCA for work such as:
- Choosing the right Zuora API for a business requirement.
- Generating SDK or cURL integration code.
- Migrating legacy Subscribe, Amendment, or REST v1 flows to the Orders API.
- Planning or building Invoice Settlement migration artifacts.
- Designing or generating Zuora Workflow JSONs (Workflow uses JSON to export/import Workflows).
- Designing usage-based billing meters.
- Designing or executing Commerce Catalog dynamic pricing setups.
- Designing, generating, or migrating Zuora CPQ legacy Apex/Visualforce customizations to Quote Studio JavaScript hooks and LWC components.
- Validating payloads, reviewing code, or checking Zuora-specific edge cases.

The ZCA is self documenting, you can simply ask your client for more examples or if a particular use case of interest to you would be helped by using ZCA.

## Quick Start

If you're already familiar with REST API development with Zuora, Zuora OAuth clients, and plugins, here are the basics. The following sections provide more details on installation and

1. Obtain `ZUORA_BASE_URL`, `ZUORA_CLIENT_ID`, and `ZUORA_CLIENT_SECRET` OAuth credentials if you don't already have suitable ones.
2. Install the plugin in Codex, Cursor, or Claude Code.
3. Configure `ZUORA_BASE_URL`, `ZUORA_CLIENT_ID`, and `ZUORA_CLIENT_SECRET`.
4. Review the [Disclaimer](#disclaimer)
5. Start with design-oriented prompts, such as:

   ```text
   Use Zuora Coding Agent to design an Orders API integration for creating a termed subscription with usage charges.
   ```

6. Move to build prompts once the approach is clear.
7. Run validation or review checks before merging or deploying.


## Complete Get Started

### 1. A Supported Coding Environment

The plugin can be used from:

- Codex
- Claude Code
- Cursor

ZCA also requires Node.js `>= 18`, because the plugin runs `zuora-mcp` through `npx`. Installation instructions for each of these clients are below the [Disclaimer](#disclaimer) section.

### 2. A Zuora OAuth Client

You need standard REST API tenant OAuth credentials from your Zuora tenant:

- `ZUORA_BASE_URL`
- `ZUORA_CLIENT_ID`
- `ZUORA_CLIENT_SECRET`

If you don't already suitable credentials [how to obtain them is described in this short video](https://developer.zuora.com/docs/get-started/introduction), but you need to be your tenant's Zuora Administrator, or you need to ask for their assistence. The same page as the video includes instructions on how to identify the URL for the new credentials. Again, do not specify a production tenant in your ZUORA_BASE_URL. You will need these values for the install.


#### Security Considerations

Remember that your client id is tied to a tenant login, that, in turn, has various roles and permissions defined. Be sure to use permissions that match your intended work. Read-only permissions are enough for design, query, and review workflows. Additional permissions are needed only when you want the agent to create subscriptions, create or run workflows, export reports, or perform other tenant-changing operations.

### 3. Access To The Relevant Codebase Or Artifact

For migrations and code generation, ZCA is most useful when it can inspect the existing integration code.

For Workflow or meter generation, supply your business requirements and enough tenant-specific detail to avoid guessing. 

### 4. Sandbox-First, Always

Only use ZCA with an API, Developer or Central Sandbox. Review and test the generated outputs prior to running any outputs against a production tenant. Despite ZCA being developed by Zuora, you remain responsible for any results as if the ZCA outputs, such as code or Workflows, had been created solely by you.


### Example Prompts

```text
Use Zuora Coding Agent to propose the right API approach for creating a subscription with a setup fee, recurring charge, and usage charge.
```

```text
Use Zuora Coding Agent to generate Node.js SDK code for creating a subscription through the Orders API.
```

```text
Use Zuora Coding Agent to analyze this legacy Amendment API code and produce an Orders API migration plan.
```

```text
Use Zuora Coding Agent to review this Zuora Workflow JSON for best practices and likely runtime issues.
```

## Why This Matters

ZCA gives your general purpose coding agent Zuora-specific superpowers. ZCA can help with field mappings, API selection, SDK conventions, migration traps, and validation patterns that you would otherwise have to specify.

## Disclaimer

This plugin uses AI to generate code, API payloads, and migration artifacts. All output should be reviewed and tested before use in any customer-facing environment. Zuora, Inc. makes no warranties regarding the accuracy, completeness, or fitness for purpose of any generated content. **Use at your own risk.**

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
| `/zuora-meter-design` | Design a Zuora meter, or ask any Mediation question — operator config, SQL, transformer scripts, troubleshooting |
| `/zuora-meter-build` | Compose an importable Zuora meter JSON from a design, or generate operator script code |
| `/zuora-dynamic-pricing-design` | Design a Commerce Catalog setup with dynamic pricing |
| `/zuora-dynamic-pricing-build` | Execute the dynamic pricing setup on the tenant |
| `/zuora-cpq-apex-design` | Design legacy CPQ Apex, Visualforce, Component Library, zQuoteUtil, or plugin-interface customizations |
| `/zuora-cpq-apex-build` | Generate CPQ Apex, Visualforce, zQuoteUtil, or plugin-interface artifacts into a Salesforce DX repo |
| `/zuora-cpq-js-design` | Design Quote Studio or CPQ X JavaScript hooks, events, quote state, and ZQFClient patterns |
| `/zuora-cpq-js-build` | Generate Quote Studio or CPQ X LWC headless/sidebar components and registration notes into a Salesforce DX repo |
| `/zuora-cpq-migration-design` | Map or modernize legacy CPQ Apex, Visualforce, zQuoteUtil, or plugin-interface customizations to Quote Studio |
| `/zuora-cpq-validate` | Validate CPQ Apex, Visualforce, LWC hooks/events, quote-state usage, ZQFClient usage, and global Apex methods |
| `/zuora-cpq-review` | Review CPQ Apex, Visualforce, Quote Studio LWC, hook/event usage, registration, tests, and best-practice risks |
| `/zuora-tenant-config-design` | Infer Zuora tenant settings from business documents, URLs, or descriptions and produce a reviewed configuration change plan |
| `/zuora-tenant-config-build` | Apply a tenant configuration plan to a Zuora tenant using manage_settings |
| `/zuora-uat-design` | Design a UAT test plan and test matrix for a Zuora implementation |
| `/zuora-uat-build` | Generate UAT test artifacts — feature files, API/UI test scripts, and configuration |
| `/zuora-uat-run` | Execute UAT tests and report results |
| `/zuora-validate` | Validate generated code/payloads/approach against Zuora patterns |
| `/zuora-review` | Review work for Zuora best practices |

The plugin also provides **passive Zuora awareness** — when you discuss Zuora topics in any conversation, it will suggest relevant commands and use zuora-mcp tools to provide accurate answers.

Powered by [zuora-mcp](https://www.npmjs.com/package/zuora-mcp).

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
| Gautam | Meter |
| Raja | CPQ |
| Zhaowei | UAT |

## License

MIT — see [LICENSE](LICENSE) for details.

Copyright (c) 2026 Zuora, Inc.
