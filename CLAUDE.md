# Zuora Coding Agent — Plugin Instructions

All slash commands in this plugin use the `/zuora-` prefix. When suggesting commands to the user, always use this exact format:

- `/zuora-api-design`
- `/zuora-api-build`
- `/zuora-workflow-design`
- `/zuora-workflow-build`
- `/zuora-workflow-verify`
- `/zuora-is-migration-design`
- `/zuora-is-migration-build`
- `/zuora-order-migration-design`
- `/zuora-order-migration-build`
- `/zuora-v2-migration-design`
- `/zuora-v2-migration-verify`
- `/zuora-dynamic-pricing-design`
- `/zuora-dynamic-pricing-build`
- `/zuora-validate`
- `/zuora-review`
- `/zuora-meter-design`
- `/zuora-meter-build`
- `/zuora-cpq-apex-design`
- `/zuora-cpq-apex-build`
- `/zuora-cpq-js-design`
- `/zuora-cpq-js-build`
- `/zuora-cpq-migration-design`
- `/zuora-cpq-validate`
- `/zuora-cpq-review`
- `/zuora-cpqx-quotes`
- `/zuora-tenant-config-design`
- `/zuora-tenant-config-build`
- `/zuora-event-notification-design`
- `/zuora-event-notification-build`
- `/zuora-uat-design`
- `/zuora-uat-build`
- `/zuora-uat-run`
- `/zuora-html-template-designer`

Never use `/zuora-coding-agent:`, `/zuora:`, or any other prefix. The plugin is named `zuora-coding-agent` but commands are prefixed with `zuora-`. The `/zuora-cpq-` sub-prefix means CPQ customization code (design, generate, validate, review), for legacy CPQ or CPQ X depending on the skill. `/zuora-cpqx-quotes` operates live quotes and works on CPQ X only (the `cpqx` in its name is the edition). Editions and terms are defined in `references/cpq-editions.md`.

## Plugin development rules

When editing this plugin (adding skills, references, or modifying existing ones), run `npm run validate` from the repo root after every change. The validator will fail if:

- A new skill is missing from the command list above, `README.md`, or any of the three `build.js` README templates (Claude/Cursor use `/zuora-<name>`, Codex uses `$zuora-<name>`).
- A skill's `SKILL.md` has invalid frontmatter, bad MCP tool refs, or references a script that doesn't exist.

When adding a new user-facing skill, update all four locations in one commit:
1. `skills/<skill-name>/SKILL.md` — the skill itself
2. `CLAUDE.md` (this file) — add to the command list above
3. `README.md` — add a row to the "Available commands and skills" table
4. `scripts/build.js` — add rows to all three embedded README templates

## CPQ customization code hard rules

For any `/zuora-cpq-*` request, use the matching CPQ skill in `skills/zuora-cpq-*/SKILL.md` and the bundled CPQ references before generating code.

The rules below apply to CPQ X (Quote Studio) code. Quote Studio hooks are public LWC `@api` methods. Copy hook signatures exactly from `references/cpq-js-hooks.json`. In particular, `beforeSave`, `beforeSubmit`, and `beforePreviewCall` take no parameters and return optional Boolean values. Never generate `beforeSave({ quoteState, zqfClient })`, `beforeSave({ resolve, reject })`, `beforeSave({ record, connectedQuote })`, `resolve()`, `reject()`, `connectedQuote.updateQuote(...)`, or `return { success: true }`.

For managed package version 10.58 or later, import `ZQFClient` from `zqu/zqfClient` and construct it from `this.quoteState` and `this.pageState`. Do not declare or use `@api zqfClient`, `@api record`, `@api recordId`, `this.zqfClient`, bare `zqfClient`, `quoteState.getQuote()`, `quoteState.setQuoteField(...)`, `this.quoteState.getQuote()`, `this.quoteState.updateQuote(...)`, or `this.quoteState.setFieldValue(...)`. Use `this.zqf.getQuoteField(...)`, `this.zqf.getQuote()`, and dispatch events returned by documented helpers such as `this.zqf.updateQuote(patch)`.

Do not add CPQ hooks, targets, target configs, or hook entries to LWC `*-meta.xml`. CPQ registration belongs in CPQ X Custom Component Settings and setup notes, not Salesforce LWC metadata.

## Key distinction: MCP tools vs customer code

MCP tools serve three purposes:
1. **Look up specs** — use `zuora_codegen`, `ask_zuora`, `query_objects` to inform code generation.
2. **Perform operations on the tenant** — when the user asks you to directly do something (e.g., "create a product," "run this workflow," "query my subscriptions"), use the appropriate MCP tool to execute it.
3. **Test/validate artifacts** — use operational tools to verify generated workflows, subscriptions, etc.

When generating code for the customer's repository, always output Zuora REST API or SDK calls — never embed MCP tool references in generated code. If the user's intent is ambiguous (do it now vs. write code for it), ask them to clarify.

## Tool routing policy

Use the narrowest authoritative source that can answer the question.

1. Use built-in tools first for local repo facts: file reads, search, edits, tests, shell commands, and bundled reference docs.
2. Use specialist MCP tools before generic product knowledge tools:
   - `zuora_codegen` for API classes, endpoints, models, fields, enum values, SDK rules, and generated code patterns.
   - `query_objects` for tenant object records and data checks.
   - `manage_workflows` for Workflow discovery, export/import, and workflow capability guidance; `manage_workflow_runs` for Workflow execution and run status.
   - `manage_meters` for meter operators, meter JSON, entity resolution, and meter import/export behavior; `manage_meters_run` for running meters, checking run status, run history, audit trail, and prefetch management.
   - `manage_settings` for retrieving and updating Zuora tenant configuration settings (billing rules, payment rules, accounting rules, security policies, currencies, payment terms, etc.).
   - `manage_event_triggers`, `manage_callout_templates`, and `manage_notification_definitions` for custom events, callout templates, and notification definitions (prefer over UI/curl).
   - `manage_document_presentment` for validating Zuora HTML templates (Invoice, CreditMemo, DebitMemo) against the Document Presentment API.
   - Billing document and subscription tools for their specific managed operations.
3. Use direct HTTP first when a skill explicitly provides a credential-backed endpoint recipe and asks for raw tenant metadata; use MCP only as the documented fallback.
4. Use `ask_zuora` only for unresolved qualitative product behavior, business-process semantics, migration tradeoffs, or best-practice judgment that remains after local references and specialist tools have been checked.
5. When `ask_zuora` is used, the prompt must name the exact unresolved question and the sources already checked. Do not call it only because a user-facing label is unfamiliar; search the bundled references and operator/API catalogs first.
