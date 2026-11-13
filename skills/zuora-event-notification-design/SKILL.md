---
name: zuora-event-notification-design
description: Design a Zuora custom event, callout template, and/or notification definition plan using Zuora MCP discovery (optional components)
argument-hint: <custom event / callout template / notification definition requirement>
allowed-tools: [Read, Write, Glob, Grep, Bash, Agent, AskUserQuestion, mcp__zuora-mcp__manage_event_triggers, mcp__zuora-mcp__manage_callout_templates, mcp__zuora-mcp__manage_notification_definitions, mcp__zuora-mcp__ask_zuora, mcp__zuora-mcp__query_objects]
---

Codex-only path resolution: When an instruction refers to `${CLAUDE_PLUGIN_ROOT}`, treat it as the root of this installed plugin. In Codex, resolve that root as the ancestor directory containing `skills/`, `references/`, and `.codex-plugin/`.

You design Zuora **Events & Notifications** resources so an agent (or user) can later create/update them safely. You produce a reviewed **plan artifact** — you do **not** create or update tenant resources in this skill.

Scope is limited to custom event triggers, callout templates, and notification definitions. Do not design or hand off workflows in this skill.

## Input

The user's requirement: $ARGUMENTS

## Defaults

For ambiguous asks like "custom event/callout" or "build an event/callout integration":

1. Prefer registering (or reusing) a **custom event** via `manage_event_triggers`.
2. Include **callout template** + **notification definition** only when Zuora must fire an HTTPS callout and/or email on that event.
3. For event-only needs (register a custom event; no HTTPS/email action), set callout and notification plan actions to `none`.

Read `${CLAUDE_PLUGIN_ROOT}/references/workflow-events.md` for custom-event naming, JEXL condition guidance, and MCP list/create patterns.

## Tool routing

- `manage_event_triggers` — list/get custom event triggers (read-only in this skill).
- `manage_callout_templates` — list/get callout templates (read-only in this skill).
- `manage_notification_definitions` — list/get notification definitions (read-only in this skill).
- `query_objects` — tenant data needed to validate baseObject assumptions.
- `mcp__zuora-mcp__ask_zuora` — only for unresolved product-behavior questions after MCP list/get and references are checked. Name the exact question and sources already checked.

**Never** call create/update operations in this design skill. Never invent REST paths when MCP covers the operation.

---

### Step 1: Clarify scope

Determine which of these the plan must cover:

| Component | Include when |
|---|---|
| Event trigger | Custom (non-standard) event, or user wants a new/updated JEXL condition on a base object |
| Callout template | HTTPS action (URL/method/headers/auth/body) on the event |
| Notification definition | Bind event → callout and/or email actions; `calloutActive=true` when callouts are in scope; `emailActive=true` + `emailTemplateId` when email is in scope |

Ask only what is missing. Mark out-of-scope components as `action: "none"` in the plan.

---

### Step 2: Resolve event name

1. Check `workflow-enums.json` → `standard_events.$canonical_name_corrections`, then `standard_events.events`.
2. If standard: note the canonical name; skip custom-event create unless the user needs callout/notification binding for that standard event (`eventCategory`) or a new custom condition.
3. If custom: keep the user-provided `eventTypeName` candidate (`^[A-Za-z][\w-]*$`, no spaces).

---

### Step 3: Discover existing resources (MCP list/match)

Run independent reads in parallel where possible (skip tools for components marked out of scope):

```
Tool: manage_event_triggers
operation: list_event_triggers
eventTypeName: <candidate>   # and/or baseObject
```

```
Tool: manage_callout_templates
operation: list_callout_templates
eventTypeName: <candidate>   # and/or name
```

```
Tool: manage_notification_definitions
operation: list_notification_definitions
eventTypeName: <candidate>
```

Record matches to **reuse** vs **create** vs **update**. Prefer reuse when names/URLs/bindings already satisfy the requirement.

---

### Step 4: Draft specs

#### Event trigger spec (when in scope)

| Field | Guidance |
|---|---|
| `eventTypeName` | Unique event type name |
| `eventTypeDisplayName` | Human label |
| `baseObject` | Case-sensitive standard object (`Invoice`, …) or `default__<api_name>` for custom objects |
| `condition` | JEXL; use `changeType` and `Object.Field` / `Object.Field_old` — no joined data-source fields |
| `active` | Usually `true` |
| Action | `create` / `update` / `reuse` / `none` (+ id when update/reuse) |

#### Callout template spec (when in scope)

| Field | Guidance |
|---|---|
| `name` | Unique template name |
| `calloutBaseurl` | Must start with `https://` |
| `httpMethod` | Usually `POST` |
| Event binding | Prefer `eventTypeName` (same as trigger); XOR with `eventCategory` for standard events |
| `eventTypeNamespace` | Default `user.notification` for tenant custom events |
| headers / body / auth | As required; do not invent secrets — ask user |
| Action | `create` / `update` / `reuse` / `none` |

#### Notification definition binding (when in scope)

| Field | Guidance |
|---|---|
| `name` | Unique per communication profile |
| Event binding | Same `eventTypeName` (prefer over `eventCategory`) |
| `calloutTemplateIds` | From callout template step (prefer over inline `callout`); omit for email-only |
| `calloutActive` | **`true`** when callout templates are in scope; else omit/`false` |
| `emailActive` / `emailTemplateId` | Set when email is in scope (`emailTemplateId` required if `emailActive=true`); email-only needs no callout template |
| `communicationProfileId(s)` | Optional; omit → Default Profile |
| Action | `create` / `update` / `reuse` / `none` |

**MVP preference:** callout-first when the user needs HTTPS delivery. Email-only (or callout+email) is supported when the user asks for email — capture `emailTemplateId` from the user or tenant discovery; do not invent template IDs.

---

### Step 5: Write the plan artifact

Write:

`${CLAUDE_PLUGIN_ROOT}/output/<slug>.event-notification.plan.json`

Choose a short kebab-case `<slug>` from the event or integration name.

Suggested JSON shape:

```json
{
  "version": 1,
  "summary": "<one paragraph>",
  "event_trigger": { "action": "create|update|reuse|none", "...": "..." },
  "callout_template": { "action": "create|update|reuse|none", "...": "..." },
  "notification_definition": { "action": "create|update|reuse|none", "...": "..." },
  "discovery": {
    "existing_event_triggers": [],
    "existing_callout_templates": [],
    "existing_notification_definitions": []
  },
  "confirmations_required": [
    "User must approve creates/updates before /zuora-event-notification-build mutates the tenant"
  ]
}
```

For event-only plans, set `"callout_template": { "action": "none" }` and `"notification_definition": { "action": "none" }`.

Also present a short human-readable summary of the same plan in chat.

---

### Step 6: Confirm before build

STOP — wait for explicit user approval of the plan (especially creates/updates and any HTTPS URL / auth).

After confirmation:

> Run `/zuora-event-notification-build` with this plan (`${CLAUDE_PLUGIN_ROOT}/output/<slug>.event-notification.plan.json`) to apply event/callout/notification resources via MCP.
