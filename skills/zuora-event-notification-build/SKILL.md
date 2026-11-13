---
name: zuora-event-notification-build
description: Create or update Zuora event triggers, callout templates, and/or notification definitions from an approved plan via Zuora MCP
argument-hint: <plan path from /zuora-event-notification-design or direct approved instructions>
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash, Agent, AskUserQuestion, mcp__zuora-mcp__manage_event_triggers, mcp__zuora-mcp__manage_callout_templates, mcp__zuora-mcp__manage_notification_definitions, mcp__zuora-mcp__ask_zuora, mcp__zuora-mcp__query_objects]
---

Codex-only path resolution: When an instruction refers to `${CLAUDE_PLUGIN_ROOT}`, treat it as the root of this installed plugin. In Codex, resolve that root as the ancestor directory containing `skills/`, `references/`, and `.codex-plugin/`.

You **execute** an approved Events & Notifications plan against the connected Zuora tenant using MCP tools. You do not invent REST when MCP covers the operation. Scope is event triggers, callout templates, and notification definitions only.

## Input

Plan path or instructions: $ARGUMENTS

Prefer a design artifact: `${CLAUDE_PLUGIN_ROOT}/output/<slug>.event-notification.plan.json` from `/zuora-event-notification-design`. If the request is multi-resource and no plan exists, recommend running design first.

Read `${CLAUDE_PLUGIN_ROOT}/references/workflow-events.md` before mutating.

## Hard gates (STOP_AND_CONFIRM)

Before **every** create or update MCP call:

1. Show the exact operation, key fields (names, URLs, conditions — mask secrets), and target resource.
2. Ask for explicit user confirmation (`AskUserQuestion` or clear yes/no).
3. Do not proceed on silence, "looks good" about an earlier design-only summary, or partial approval of a different step.

List/get operations do not require this gate.

---

## Preferred execution order

Honor each plan component’s `action`. Skip any component whose action is `none` or which is absent/out of scope.

1. Event trigger (`manage_event_triggers`) — only when `event_trigger.action` is `create` / `update` / `reuse`
2. Callout template (`manage_callout_templates`) — only when `callout_template.action` is `create` / `update` / `reuse`
3. Notification definition (`manage_notification_definitions`) — only when `notification_definition.action` is `create` / `update` / `reuse`

Do **not** invent callout templates or notification definitions for an event-only plan.

---

### Step 1: Load plan and re-discover

Read the plan file. For each component with action other than `none`, re-run list/get so IDs and names are current:

- `list_event_triggers` / `get_event_trigger` (if event in scope)
- `list_callout_templates` / `get_callout_template` (if callout in scope)
- `list_notification_definitions` / `get_notification_definition` (if notification in scope)

For `reuse`, record the matched id/name in evidence and do not create. For `none` or missing components, skip that step entirely.

---

### Step 2: Event trigger

Skip when `event_trigger.action` is `none` or absent.

#### Create (`action: create`)

```
Tool: manage_event_triggers
operation: create_event_trigger
active: true
baseObject: <e.g. Invoice>
condition: <JEXL>
eventTypeName: <Name>
eventTypeDisplayName: <Display>
```

#### Update (`action: update`)

```
Tool: manage_event_triggers
operation: update_event_trigger
eventTriggerId: <uuid>
# optional: active, condition, eventTypeDisplayName
# baseObject and eventTypeName are immutable
```

Capture `eventTypeName` (and id) for later in-scope steps.

---

### Step 3: Callout template

Skip when `callout_template.action` is `none` or absent. Do not prompt the user to add a callout for an event-only plan.

#### Create (`action: create`)

```
Tool: manage_callout_templates
operation: create_callout_template
name: <unique>
calloutBaseurl: https://...
httpMethod: POST
eventTypeName: <same as trigger>   # XOR eventCategory for standard events
# optional: active, description, eventTypeNamespace, headers, auth, body, ...
```

#### Update (`action: update`)

```
Tool: manage_callout_templates
operation: update_callout_template
calloutTemplateId: <id>
# event binding immutable; update URL/method/headers/active/etc.
```

Capture returned `id` for `calloutTemplateIds` when Step 4 is in scope.

---

### Step 4: Notification definition

Skip when `notification_definition.action` is `none` or absent. Do not create a notification definition solely because an event was created.

Preferred create path — **callout-first** (`action: create`, when callouts are in scope):

```
Tool: manage_notification_definitions
operation: create_notification_definition
name: <unique>
eventTypeName: <same as trigger>
calloutTemplateIds: ["<id>"]
calloutActive: true
# optional: active, description, communicationProfileId(s), filterRule, ...
```

**Email-only** (when plan has email and no callout):

```
Tool: manage_notification_definitions
operation: create_notification_definition
name: <unique>
eventTypeName: <same as trigger>
emailActive: true
emailTemplateId: <existing template id from plan/user>
# optional: active, description, communicationProfileId(s), filterRule, ...
```

**Callout + email:** combine both action sets from the plan (`calloutActive` + `calloutTemplateIds` and `emailActive` + `emailTemplateId`).

Notes from MCP:

- Prefer `eventTypeName` over `eventCategory` for creates.
- Prefer `calloutTemplateIds` over inline `callout`.
- `calloutActive` / `emailActive` default to **false** — set **true** only for actions in scope.
- At least one action path (callout and/or email) is required for create.
- Do not invent `emailTemplateId`; require it from the plan or user.
- Event binding is immutable after create.

---

### Step 5: Evidence artifact

Write:

`${CLAUDE_PLUGIN_ROOT}/output/<slug>.event-notification.evidence.json`

```json
{
  "version": 1,
  "plan": "<path>",
  "event_trigger": { "action": "create|update|reuse|none", "id": "...", "eventTypeName": "..." },
  "callout_template": { "action": "create|update|reuse|none", "id": "...", "name": "..." },
  "notification_definition": { "action": "create|update|reuse|none", "id": "...", "name": "..." },
  "errors": []
}
```

Also summarize successes/failures in chat (including skipped `none` components).

---

## Critical constraints

- **Honor plan `action`** — never create/update a component whose action is `none` or out of scope.
- **No silent live writes** — STOP_AND_CONFIRM before every create/update.
- **Never invent REST** for event triggers, callout templates, or notification definitions when MCP tools are available.
- **Do not default to UI/curl** — MCP is primary; UI/curl only if tools are unavailable.
- Mask secrets (auth passwords, OAuth client secrets) in chat and evidence files.

## Tool routing

- `manage_event_triggers` / `manage_callout_templates` / `manage_notification_definitions` — primary mutate/list/get path.
- `query_objects` — resolve sample object ids if needed for condition validation notes.
- `mcp__zuora-mcp__ask_zuora` — unresolved product behavior only, after MCP + references; name the exact question and sources already checked.
