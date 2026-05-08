---
name: zuora-workflow-build
description: Compose an importable Zuora Workflow JSON from a design or requirement
argument-hint: <workflow design or requirement>
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash, Agent, mcp__zuora-mcp__manage_workflows, mcp__zuora-mcp__run_workflows, mcp__zuora-mcp__ask_zuora, mcp__zuora-mcp__zuora_codegen, mcp__zuora-mcp__query_objects]
---

Codex-only path resolution: When an instruction refers to `${CLAUDE_PLUGIN_ROOT}`, treat it as the root of this installed plugin. In Codex, resolve that root as the ancestor directory containing `skills/`, `references/`, and `.codex-plugin/`.


You are building an importable Zuora Workflow JSON from a design (produced by `/zuora-workflow-design` or provided directly).

## Input

The user's workflow design or requirement: $ARGUMENTS

## Correctness strategy

Format correctness is non-negotiable. A slightly malformed JSON fails `import_workflow`. Defense is layered:

1. **Compose** from a canonical skeleton + per-action_type templates. Never hand-write structure.
2. **Lint** with `scripts/lint-workflow-json.js` — the client-side enforcement layer, since `Task.import` runs with `validate: false` and skips each task's `task_setup_validation`.
3. **Self-check** against the checklist below before writing the file.
4. **Optional dry-run** in a sandbox: `import_workflow activate=false`, then `delete_workflow` to clean up. Rails has no `validate_only` flag.

## Workflow

### Step 1: Load references

Read these in parallel before composing:

- `${CLAUDE_PLUGIN_ROOT}/references/workflow-skeleton.json` — the canonical empty envelope (start here).
- `${CLAUDE_PLUGIN_ROOT}/references/workflow-task-templates.json` — per-`action_type` templates (description, hooks, template, required_params, required_at_import, param_enums, boolean_string_params, **`data_contract`** for Tier-1).
- `${CLAUDE_PLUGIN_ROOT}/references/workflow-enums.json` — global enums, typo hints, `standard_events`, `supported_ui_pages`, schemas, and `version_regex`.
- `${CLAUDE_PLUGIN_ROOT}/references/workflow-patterns.md` — composition strategy.
- `${CLAUDE_PLUGIN_ROOT}/references/workflow-task-catalog.md` — task category overview and format pitfalls.
- `${CLAUDE_PLUGIN_ROOT}/references/workflow-triggers-and-linkages.md` — trigger modes, call_type matrix, linkage catalog, and the **Workflow-level field derivation** cheat-sheet.
- `${CLAUDE_PLUGIN_ROOT}/references/workflow-events.md` — standard event catalog, name corrections, and event_parameters derivation.
- `${CLAUDE_PLUGIN_ROOT}/references/workflow-data-flow.md` — `Data.*` symbol-table model, opaque-task protocol, walker algorithm. **Required reading before Step 3d.**
- `${CLAUDE_PLUGIN_ROOT}/references/workflow-liquid.md` — Liquid scopes.
- `${CLAUDE_PLUGIN_ROOT}/references/workflow-examples.md` — annotated, lint-clean workflow JSONs.

### Step 2: Optional — check existing workflows to clone

Only if the user is modifying an existing workflow or has an obvious near-match:

Call `mcp__zuora-mcp__manage_workflows`:

- `list_workflows` — find candidates.
- `get_workflow_details` or `export_workflow` — pull the JSON as a starting point.

If cloning, still run the output through the composer steps below (and the linter) to ensure it matches the current template schema.

### Step 3: Compose the workflow JSON

Use the skeleton + templates composer. Do not hand-write structure.

1. **Start from a deep copy of `workflow-skeleton.json`.**

2. **Populate `workflow_definition`** (name, description, category, `ui_page_roles`).

3. **Set trigger flags and config on `workflow`** (see Step 3b for the full envelope):
   - Exactly one of `ondemand_trigger`, `callout_trigger`, `scheduled_trigger`, `event_trigger` set to `true`.
   - Scheduled: `interval` (6-token Rufus/Fugit cron `SEC MIN HOUR DOM MON DOW`; bare `/N` = `*/N` step; the React UI always emits 6 tokens with `second=0`) **and** `timezone` (Rails `ActiveSupport::TimeZone` friendly name -- e.g. `"UTC"`, `"Eastern Time (US & Canada)"`, `"London"`, `"Tokyo"`). The full allowlist is in `references/rails-timezones.json`. **Never emit a bare IANA string** like `"America/New_York"` -- it fails Rails validation (`workflow/setup.rb` L32) and the linter raises `E175`. If the user gives you an IANA name, look it up in `rails-timezones.json -> iana_to_friendly_recommendations` and convert.
   - Event: `parameters.event_triggers` (non-empty array of canonical event names) + `parameters.event_parameters` (array of `{eventName, params: [...]}`).
   - Choose `call_type` from `workflow-enums.json` -> `workflow_call_types.user_facing` (default `BATCH`; never emit `ASYNC`/`RULE`/`UI`).

4. **For each task** in the design:
   a. Look up the matching `action_type` in `workflow-task-templates.json`.
   b. Deep-copy the `template` object.
   c. Assign a unique integer `id` (simple sequence like 100, 101, 102).
   d. Replace every `<<REQUIRED: …>>` sentinel with a real value. Use Liquid from `Data.*`, `Credentials.zuora.*`, `GlobalConstants.*` as appropriate.
   e. Populate every field listed under `required_at_import` with a non-empty value (top-level attrs like `object`, `object_id` that Rails validates via ActiveRecord column presence).
   f. Guarantee `parameters` is an object, not `null` or missing. An empty task uses `"parameters": {}`.
   g. For boolean params listed in `boolean_string_params`, always emit the STRING `"true"` or `"false"`, never JSON booleans.
   h. For enum params listed in `param_enums`, pick one of the listed values — do not invent new ones.
   i. **Logic::Case special handling:** pre-normalize `parameters.case_condition` keys to sequential `Case_1`, `Case_2`, … `Case_N` before emitting. This matches the server-side `before_save :validate_labels` rewrite so no linkages are destroyed.
   j. Set `css.top`/`css.left` using the defaults in `workflow-enums.json.css_layout_defaults` (adjust for branches).
   k. Set `task_id` to the id of the primary upstream task (for layout/dependency purposes), or `null` for the entry task.

5. **Emit linkages**:
   a. First linkage is always the Start: `{ "source_workflow_id": <workflow.id>, "source_task_id": null, "target_task_id": <entry_task.id>, "linkage_type": "Start" }`.
   b. For every task-to-task edge in the design, add `{ "source_workflow_id": null, "source_task_id": <upstream.id>, "target_task_id": <downstream.id>, "linkage_type": <hook> }`.
   c. `linkage_type` must be one of the upstream task's `hooks` (see the template). Use exact spelling — `"For Each"` with a space; `"Case_1"` not `"case_1"`; `"Complete"` not `"Iterate"`.
   d. Emit `Case_N` linkages in order and ensure the keys match the pre-normalized `parameters.case_condition`. Emit `Case_Else` as a linkage (not a `case_condition` key).
   e. Verify: tasks array non-empty, linkages array non-empty, exactly one Start linkage, no `For Each` linkage on any path to a `Logic::Merge` task.

### Step 3a: Describe before selecting fields (HARD REQUIREMENT)

**Before finalizing any field list or any `<Object.Field>` merge-field token, you MUST resolve it against the live tenant (or, at worst, the bundled catalog).** Inventing field names is the single most common way a generated workflow fails at runtime: Rails accepts the JSON on import (`validate: false`) but the task then errors out on the first SOAP/ZOQL call, or an event binding silently resolves to `nil` because the merge field does not exist in the live payload.

Two describe surfaces must both be satisfied before emitting the JSON:

1. **Task field describe** — for `Export`, `Query`, `Create`, `Update`, `CustomObject::Query`, `CustomObject::Create`, `CustomObject::Update` field lists **and** for any `parameters.where_clause` that references object fields.
2. **Event merge-field describe** — for every `workflow.parameters.event_parameters[*].params[*].value` that is not one of the hard-coded special tokens.

The linter encodes these gates as `W177` (task fields), `E177` (wrong event BaseObject), and `W179` (unverifiable event merge field).

#### 3a-0. Pick a channel (direct HTTP or MCP — either is fine)

Claude Code injects the Zuora credentials from `~/.claude/settings.json -> env` into every `Bash` invocation (keys: `ZUORA_BASE_URL`, `ZUORA_CLIENT_ID`, `ZUORA_CLIENT_SECRET`). That means the **direct HTTP path with `curl` is the primary describe channel** — it returns the raw tenant response with no intermediary. Use MCP (`mcp__zuora-mcp__ask_zuora`) if either (a) the env vars are not present (check with `printenv ZUORA_BASE_URL ZUORA_CLIENT_ID`), or (b) you want the MCP's structured summarization rather than raw JSON.

One-time OAuth exchange per session (store the token, reuse for all describes):

```bash
ACCESS_TOKEN=$(curl -sS -X POST "$ZUORA_BASE_URL/oauth/token" \
  --data-urlencode "grant_type=client_credentials" \
  --data-urlencode "client_id=$ZUORA_CLIENT_ID" \
  --data-urlencode "client_secret=$ZUORA_CLIENT_SECRET" \
  | jq -r '.access_token')
```

If `printenv ZUORA_BASE_URL` is empty, call `mcp__zuora-mcp__ask_zuora` instead — the MCP sub-process reads the same vars from Cursor's credential store (see `.mcp.json`).

The `configuration_contract.fields[*].source` value `describe-call` (per-task) tells you which field-bearing parameters need channel 1. From `workflow-task-configuration.md`:

| Task | Describe scope | Configurable parameter |
| --- | --- | --- |
| `Export` | ZOQL/AQuA describe of `parameters.object` (+ joinable `related_objects`) | `parameters.fields[<object>][]` **and** any `parameters.where_clause` field |
| `Query` | SOAP describe of `parameters.object` | `parameters.fields[<object>][]` **and** any `parameters.where_clause` field |
| `Create` | SOAP describe of `parameters.object` (createable fields only) | `parameters.fields[<object>]` map |
| `Update` | SOAP describe of `parameters.object` (updateable fields only) | `parameters.fields[<object>]` map |
| `CustomObject::Query` | Custom Object describe of `parameters.object` | implicit (selected via `parameters.query` Lucene refs) |
| `CustomObject::Create` | Custom Object describe of `parameters.object` (origin != system) | `parameters.fields[<object>]` map |
| `CustomObject::Update` | Custom Object describe of `parameters.object` (origin != system) | `parameters.fields[<object>]` map |

#### 3a-1. Run the describe (Bash recipe, with MCP as the fallback)

**Direct HTTP (preferred when `$ZUORA_BASE_URL` / `$ZUORA_CLIENT_ID` are set):**

```bash
# Standard SOAP/ZOQL describe — used for Export, Query, Create, Update.
# Response is XML; pipe through xmllint / xsltproc, or just grep for <name>.
curl -sS "$ZUORA_BASE_URL/v1/describe/Invoice" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Accept: application/xml" \
  | xmllint --xpath '//fields/field/name/text()' - 2>/dev/null \
  | tr -s '[:space:]' '\n' | sort -u

# Related-object list (second pass) — needed for Export joins like Invoice.Account.Name:
curl -sS "$ZUORA_BASE_URL/v1/describe/Invoice" \
  -H "Authorization: Bearer $ACCESS_TOKEN" -H "Accept: application/xml" \
  | xmllint --xpath '//related-objects/object/name/text()' - 2>/dev/null

# Custom Object describe — used for CustomObject::Query / Create / Update.
# Replace <namespace> (e.g. "default") and <object> accordingly.
curl -sS "$ZUORA_BASE_URL/objects/definitions/<namespace>/<object>" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq '.schema.properties'
```

Cache the describe response per `(tenant, object, entity_id)` for the duration of the agent session — subsequent tasks targeting the same object should reuse the cached field list (do not re-hit the endpoint each time).

**MCP fallback** (if `printenv ZUORA_BASE_URL` is empty, or `curl` returns 401 even after a fresh token): call `mcp__zuora-mcp__ask_zuora` with:

> Return a JSON array of selectable fields for `<object>` matching the shape Zuora's `/describe/<object>` endpoint returns. For each field include `name`, `type` (`string|number|boolean|datetime|picklist|reference|...`), `required` (bool), `createable` (bool), `updateable` (bool), and (if reference) `referenceTo`. Also list every `related_objects` entry that can be joined via dot notation in a ZOQL `SELECT`. If the tenant uses Custom Objects, return the `properties` map from `/objects/definitions/<namespace>/<object>` (origin != system) instead. Do not invent fields. Tenant: `<tenant>`. Entity: `<entity_id | 'default'>`.

#### 3a-2. Fall back to the bundled catalog (standard fields only)

If **both** channels fail (no `curl` credentials AND MCP unavailable), use `references/zuora-standard-fields.json`. It bundles the standard-field catalog for the most common Zuora SOAP/ZOQL objects (`Account`, `Subscription`, `RatePlan`, `RatePlanCharge`, `Invoice`, `InvoiceItem`, `Payment`, `PaymentMethod`, `CreditMemo`, `DebitMemo`, `Contact`, `Amendment`, `Product`, `ProductRatePlan`, `ProductRatePlanCharge`, `BillingPreviewRun`, `BillingRun`, `Order`, `OrderAction`). Custom fields (`*__c`) are never in the fallback — if the design needs custom fields and neither describe channel works, ask the user for the exact `name` + `type` per field.

#### 3a-3. Cross-check during composition

When you fill in `parameters.fields[<object>]` (Export/Query) or `parameters.fields[<object>].<FieldName>` (Create/Update/CustomObject::*), every field name MUST be either:

1. Present in the describe response (curl or MCP) for that object, OR
2. Present in the matching `references/zuora-standard-fields.json` entry, OR
3. Explicitly confirmed by the user (with type) when both describe channels failed AND the field is not in the fallback.

The same rule applies to fields referenced inside `parameters.where_clause` (e.g., `BillRunId = '{{ Data.BillingRun.Id }}'` on an `Export Invoice` task must be backed by `Invoice.BillRunId` in describe or in `zuora-standard-fields.json`).

The linter rule `W177 undeclared-describe-field` enforces this — any field name in `parameters.fields` or `parameters.fields[<object>]` that is unknown to both describe and the fallback catalog emits a warning. When describe was unavailable for the lint run, `W177` is downgraded to a notice (the linter cannot prove the field doesn't exist in the live tenant, only that the static fallback doesn't know it).

#### 3a-4. Custom Object specifics

For `CustomObject::*` tasks, `parameters.fields` is **nested**: `parameters.fields.<self.object>.<FieldName>`. The Custom Object describe lives at `GET /objects/definitions/<namespace>/<object>` (origin != system). The fallback catalog never carries Custom Objects (they are tenant-specific) — if both channels fail, ask the user directly for the field map. Required `__c` fields (per the schema) MUST be supplied for Create or save fails with `Missing fields: ...`.

#### 3a-5. Event merge-field describe (event_parameters values)

`workflow.parameters.event_parameters[*].params[*].value` is the binding between Kafka event payload and `Data.<object>.<key>` scope. The UI picker at `WorkflowSettingsForm.js` L383-401 fetches the live merge-field list from:

```
GET {base_url}/notifications/email-templates/info/selections?category=<category>
```

where `category` is the event id for standard events (`event.id.length < 5`) or `${event.namespace}:${event.name}` for custom events. This endpoint returns a hash of `<object>: [<field path>, ...]` that the UI flattens into `<Object.Field>` strings (e.g. `<BillingRun.Id>`, `<Account.WorkEmail>`). The corresponding Rails method is `ZuoraConnect::AppInstance#get_custom_event_fields` (`app/models/zuora_connect/app_instance.rb` L1452-1494).

At runtime, `BusinessEvent#parse_event` (`app/models/business_event.rb`) resolves these tokens in exactly two paths:

1. **Special tokens** are resolved explicitly: `<Event.Category>`, `<Event.EventName>`, `<Event.EventId>`, `<Event.Id>`, `<Event.DataSource>`, `<Event.Tenant>`, `<Event.TriggerDateTime>`, `<Event.DisplayName>`, `<Functions.Today>` (the full list lives in `references/zuora-standard-fields.json` → `$event_special_tokens.tokens`). These always work and do not need a describe call.
2. **Everything else** has angle brackets stripped, then any `DataSource.` / `Event.` prefix stripped, then the remainder is used as a **literal key** into the event payload. `<BillingRun.Id>` becomes the payload key `BillingRun.Id`; if that key is not present in the payload, the binding resolves to `nil` with no error. This is why you cannot invent tokens.

**Required flow per event:**

1. Resolve the canonical event name (via `workflow-enums.json` → `standard_events.$canonical_name_corrections`). Confirm it exists in `standard_events.events` or via `/events/event-triggers` (see Step 3c).
2. Fetch the merge-field list for the event category using either channel:

   **Direct HTTP (preferred):**

   ```bash
   # Standard event: category is the 4-char numeric event id (look up in
   # workflow-enums.json -> standard_events.events[*].id).
   # Example: BillingRunCompletion -> category=1410.
   curl -sS "$ZUORA_BASE_URL/notifications/email-templates/info/selections?category=1410" \
     -H "Authorization: Bearer $ACCESS_TOKEN" | jq

   # Custom event: category is "<namespace>:<name>".
   curl -sS "$ZUORA_BASE_URL/notifications/email-templates/info/selections?category=user.notification:MyCustomEvent" \
     -H "Authorization: Bearer $ACCESS_TOKEN" | jq
   ```

   Apply the UI's filter (`WorkflowSettingsForm.js` L388-400): for **standard** events drop every path containing `DataSource`; for **custom** events keep only paths containing `DataSource` OR matching `.<baseObject>.`.

   **MCP fallback:** call `mcp__zuora-mcp__ask_zuora` with:

   > For the Zuora event category `<event.id-or-namespaced-name>`, call `GET {base_url}/notifications/email-templates/info/selections?category=<category>` and return the raw JSON. For a `Standard` event (id < 5 chars) I want the list **excluding** any field that contains `DataSource`. For a custom event I want only fields that contain `DataSource` OR whose path matches `.<baseObject>.`.

3. Pick the `<Object.Field>` strings you need from the returned list. Every `value` you emit must be one of:
   - A special token from `$event_special_tokens.tokens`, OR
   - A `<BaseObject.Field>` string where `BaseObject` matches the event's declared `baseObject` (from `references/zuora-standard-fields.json` → `$event_base_objects.events`) AND `Field` appears in the fetched merge-field payload, OR
   - A `<DataSource.Foo.Bar>` string (custom events only) confirmed by the endpoint response.
4. If both describe channels fail, fall back to `references/zuora-standard-fields.json` for well-known base objects (the catalog lists `Id`, core status/amount fields, etc.), **and** tell the user the token list is unverified — the linter will emit `W179 unverifiable-event-parameter-value` so the user can decide whether to proceed.

**Linter gates:**

- `E177 invalid-event-parameter-value`: `<BaseObject.Field>` where `BaseObject` is not the event's declared `baseObject` and has no `DataSource.`/`Event.` prefix. Hard error.
- `W179 unverifiable-event-parameter-value`: any `<...>` value that is neither a known special token nor a statically-confirmed `<BaseObject.Field>`. Prompts you to run the describe in Step 3a-5 and confirm.

### Step 3b: Materialize the workflow envelope

After tasks and linkages are in place, fill out the rest of `workflow.*`. Use `workflow-triggers-and-linkages.md` -> "Workflow-level field derivation" as the single source of truth. Apply these rules in order:

1. **`workflow.id`**: keep at `1` (skeleton default). The Start linkage's `source_workflow_id` MUST equal this value.
2. **`workflow.name`** and **`workflow.description`**: copy from the user's design / `workflow_definition.name`.
3. **`workflow.type`**: must be the literal string `"Workflow::Setup"`.
4. **`workflow.data`**: always `{}`.
5. **`workflow.status`**: always `"Inactive"` on import. The `import_workflow` tool flips it to `Active` via `activate_version: true`.
6. **`workflow.css`**: keep skeleton default `{"top":"40px","left":"35px"}`.
7. **Trigger flags**: set exactly one to `true`; the others MUST be `false`. NEVER set `ui_trigger` (it is not a column on the `workflows` table and is silently dropped).
8. **`workflow.interval`** + **`workflow.timezone`**: required IFF `scheduled_trigger == true`. Use `interval_schema.examples` and `interval_schema.timezone.examples` from `workflow-enums.json`.
9. **`workflow.parameters`** — start from the skeleton's seven always-present keys (`fields`, `entity_name`, `entity_id`, `skipping_check: "db"`, `file_encryption: "false"`, `secure_error_msgs: "false"`, `show_run_prompt`, `callout_response`). Then layer in:
   - **For event triggers**: append `event_triggers: ["<canonical name>"]` and `event_parameters: [{eventName, params: [...]}]`. Resolve the user's intent through `workflow-enums.json` -> `standard_events.$canonical_name_corrections` first. Emit BOTH `event_parameters` AND each `params` value as JSON arrays (not Hashes).
   - **For callout triggers**: populate `parameters.fields[]` with the inbound payload schema if known.
   - **For multi-entity tenants**: set `parameters.entity_id` and `parameters.entity_name` if the user named an entity. Otherwise leave `null` and let the server default.
   - **NEVER emit** `parameters.merge_task_ids` — `Workflow::Setup.import` deletes it on save.
10. **`workflow.notifications`** — keep skeleton default unless the user requested email alerts. If they did:
    - Populate `emails: ["alice@example.com", "{{Data.Account.WorkEmail__c}}", ...]`.
    - Set the relevant booleans (`failure`, `success`, `pending`, `skipped_scheduled_run`).
    - Optional `error_ignore`: a Ruby regex string. Validated by `Regexp.new` at import — invalid patterns reject the workflow.
    - At least one boolean must be `true` if `emails[]` is non-empty (and vice versa).
11. **`workflow.call_type`** — default `"BATCH"`. Validate against `workflow_call_types.user_facing[*].value`. If the user requested `UIACTION` or `SYNC_UI_ACTION`, jump to step 12.
12. **`workflow.ui_pages`** — `{}` for non-UIACTION call types. For `UIACTION` / `SYNC_UI_ACTION`: exactly one entry from `supported_ui_pages.pages`, shape `{ "<value>": { "label": "<button label>" } }`.
13. **`workflow.priority`**: default `"Medium"`; `"High"` for time-critical event workflows; `"Low"` for low-priority background work.
14. **`workflow.delete_ttl`**: default `30`. Acceptable range depends on tenant retention policy; do not emit `0` unless the user explicitly asks for "no retention".
15. **`workflow.version`**: default `"0.0.1"` for new; increment for new versions of the same `workflow_definition`. Must match `^\d+(?:\.\d+)?(?:\.\d+)?$`.
16. **`workflow.solution_id`**, **`workflow.extension_id`**: `null` unless packaging as a Connect extension.
17. **`workflow.zuora_org_id`**: `null` (deprecated). **`workflow.zuora_org_ids`**: `[]` to allow all accessible orgs.

### Step 3c: Optional event-trigger preflight

When the workflow is event-triggered AND any value in `parameters.event_triggers[]` is **not** in `workflow-enums.json` -> `standard_events.events` (after applying `$canonical_name_corrections`), verify that the custom event is registered before considering the workflow lint-clean.

Try this lookup once, in order:

1. **Direct HTTP (preferred):**

   ```bash
   curl -sS "$ZUORA_BASE_URL/events/event-triggers" \
     -H "Authorization: Bearer $ACCESS_TOKEN" | jq '.data[] | .eventType.name'
   curl -sS "$ZUORA_BASE_URL/events/scheduled-events" \
     -H "Authorization: Bearer $ACCESS_TOKEN" | jq '.data[] | .name'
   ```

   Both endpoints are paginated (`body.next`); follow cursors until you exhaust the list or confirm the event name.

2. **MCP fallback:** call `mcp__zuora-mcp__ask_zuora` with prompt: `List event triggers from /events/event-triggers and tell me whether an event named "<name>" is registered. Also list event triggers from /events/scheduled-events.`
3. If the event exists, proceed.
4. If the event is NOT registered (or the list is empty), tell the user the event must be registered first, and offer:
   - Manual: Settings -> Notifications -> Custom Events.
   - API: `POST /events/event-triggers` with `{baseObject, condition, eventType: {name, displayName, description}}`.
   - Alternative design: switch to `callout_trigger` and configure a standard Zuora Notification to hit the workflow's callout URL — this avoids needing a custom event.
5. If both channels fail (no credentials in env AND MCP unavailable), the linter will surface `W121` for the unconfirmed event name; carry on but flag the warning to the user.

This step is OPTIONAL by design — never block emission if neither channel can reach the tenant.

### Step 3d: Static data accessibility check

Walk the task graph topologically and validate every `{{ Data.X.Y }}` Liquid reference against an `available_data` set you accumulate. This catches the most common composition bug class: referencing data that no upstream task produces.

Required reading: `workflow-data-flow.md` (sections 1-3 + 10) and `workflow-enums.json` → `default_data_workflow_keys` / `trigger_seeding_rules` / `data_flow_lint_rules`.

Algorithm:

1. **Seed `available_data`** with the workflow-level inputs:
   - Always: `{ Workflow: [ExecutionDate, ExecutionDateTime, Name, Id, Tenant, User] }`.
   - If `call_type` ∈ `{UIACTION, SYNC_UI_ACTION}`: `{ UIAction: [ObjectId, ObjectName, ObjectNumber] }`.
   - For each `workflow.parameters.fields[]`: union `{ <object_name>: [<field_name>] }`.
   - For each `workflow.parameters.event_parameters[*].params[*]`: union `{ <param.object>: [<param.key>] }`.
   - For **callout-trigger** workflows: `{ Callout: OPAQUE }` (the inbound POST body — treat as opaque unless the workflow carries `parameters._expected_response_schema` or `parameters._opaque_trusted`).

2. **Topological sort** the tasks via linkages from the Start (`source_task_id == null`). Each task inherits the union of its predecessors' final `available_data`.

3. **For each task in topological order:**
   a. Look up the task's `data_contract` block in `workflow-task-templates.json` (fall back to `$default_data_contract` if absent — treats it as opaque).
   b. **Validate reads**: scan every value in `task.parameters` (recursively) for `{{ Data.X[.Y…] }}` and `{% if/elsif/case Data.X… %}` patterns. For each reference:
      - If `Data.X` scope is **not in `available_data`**: emit `E170` and STOP (must fix). Suggest closest match if one exists.
      - If inside an Iterate For-Each branch and `Data.X` is the iterated key, treat as single-Hash mode. References like `Data.X.Field` are OK; `Data.X[0].Field` or `Data.X | size` trigger `W173`.
      - If `Data.X` came from a `Logic::Case` branch (one of `Case_1`, `Case_2`, …, `Case_Else`) and the current task is downstream of a `Logic::Merge`, AND `X` is in the union but not the intersection of branch contributions: emit `W174`.
      - If the producing task is **OPAQUE** (predictability=opaque) AND has neither `parameters._opaque_trusted="true"` nor `parameters._expected_response_schema.<X>`: emit `W172`.
      - If the producing task is OPAQUE AND has `parameters._expected_response_schema.<X>` declared: validate `Y` against the declared field set; emit `W171`-equivalent if missing.
      - If the producing task is **DETERMINISTIC** and `Y` is not in `data_contract.writes[].fields` (or `parameters.fields[X][]` for Query/Export/Create/Update/CustomObject::Query): emit `W171`.
      - If the producing task is **SEMI-DETERMINISTIC** and `fields_partial_known: true`: scope-level only (no `W171`).
   c. **Apply writes** from the task's contract to compute the contribution to downstream `available_data`:
      - Resolve `scope_template` placeholders against the task's `parameters` and `object` (e.g. `Data.{parameters.placement | self.object}` → `Data.InvoicesFromBR`).
      - Resolve `fields` strings (`from_param:fields[<obj>]` → read the actual params; `LIQUID_SCOPE` → scan `parameters.code` for `{% assign %}` / `{% capture %}` names; `OPAQUE` → mark key opaque).
      - For `Logic::Liquid` with `parameters.placement` set, scope is `Data.<placement>` not `Data.Liquid`.
   d. **Iterate special case**: when this task is `Iterate(object='X')`, for tasks reachable via `For Each` linkage, mark `Data.X` as "single-Hash mode". For tasks reached via `Complete`, restore the array binding (or whatever the inner-loop tasks rebound).
   e. **Logic::Case branch partitioning**: each `Case_N` linkage's downstream subtree contributes its writes only to that branch. When two branches converge at a `Logic::Merge`, the post-merge `available_data` is the **intersection** of per-branch contributions; scopes only in the union (not the intersection) are flagged as `branch_partial` so downstream references emit `W174`.
   f. **Logic::Merge** itself is a no-op for writes.

4. **Output**: a small report listing, per task, what it consumes from `Data.*` and what it adds. Include the report in the design notes / commit message so reviewers can audit the data flow at a glance. The linter (`scripts/lint-workflow-json.js`, rules `E170`/`W171`/`W172`/`W173`/`W174`) is the final authority — never bypass it.

### Step 3e: Opaque-task confirmation (three-option prompt)

While running Step 3d, the moment you encounter the FIRST downstream reference to an OPAQUE task's scope (predictability=opaque per `workflow-task-templates.json`: `Callout`, `AsynchronousCallout`, `Logic::Lambda`, `Script::JavaScript`, `Logic::JSONTransform`, `Logic::XMLTransform`, `Logic::CSVTranslator`, `Logic::ResponseFormatter`, `Execute::WorkflowTask`, `Mediation::SendEvents`), pause the walker and prompt the user. **One prompt per opaque task** (covers all downstream references), not one per reference.

> Task `<opaque task name>` (`<action_type>`, predictability=opaque) returns a payload whose shape is unknown statically. Downstream `<downstream task name(s)>` reference `Data.<scope>.<field…>`. Choose how to proceed:
>
> **(a) Declare expected response schema** — list the fields you expect (e.g. `acknowledgmentId, receivedAt, errors[].code, errors[].message`). I'll add this to the opaque task:
>
> ```jsonc
> "parameters": {
>   ...,
>   "_expected_response_schema": {
>     "<scope>": {
>       "acknowledgmentId": "string",
>       "receivedAt": "string",
>       "errors": [{ "code": "string", "message": "string" }]
>     }
>   }
> }
> ```
>
> The linter then performs field-level validation on every downstream `Data.<scope>.<field>` reference (treats the scope as if DETERMINISTIC). Best choice when the response shape is known.
>
> **(b) Opt out** — set `parameters._opaque_trusted = "true"` on the opaque task to suppress all `W172` warnings on `Data.<scope>.*` references. Best when the response shape is too dynamic to declare (e.g. variable webhook payloads) and you trust runtime.
>
> **(c) Insert a normalizer** — I'll auto-insert a `Logic::JSONTransform` (or `Logic::ResponseFormatter`) right after `<opaque task name>` that maps the response into a deterministic scope (e.g. `Data.NormalizedInvoice`). Downstream tasks then reference the normalized scope instead of the opaque one. Best when only a few fields are needed and the user wants type-safe downstream usage.
>
> **(d) Pause for offline confirmation** — I'll annotate the workflow as draft, leave the W172 warnings in place, and stop. Confirm the protocol choice before re-running build.

Apply the user's choice immediately, then continue Step 3d. Encode the choice as follows:

- **(a)** add `parameters._expected_response_schema = { "<scope>": { ...field declarations... } }` to the opaque task. The leading `_` prevents Rails from persisting it (unknown keys in `parameters` JSONB are accepted but no Ruby code reads `_`-prefixed keys).
- **(b)** add `parameters._opaque_trusted = "true"` (string, not boolean — matches the `boolean_string_params` convention).
- **(c)** insert the normalizer task with its own `_expected_response_schema` declaring the normalized scope. Wire linkages: `<opaque task> --Success--> <normalizer> --Success--> <original downstream task>`. Update downstream Liquid references to use `Data.<normalized scope>` instead of `Data.<opaque scope>`.
- **(d)** persist the workflow with W172 warnings; report to the user; do NOT proceed to Step 5 (lint) until the user picks (a)/(b)/(c).

This step is a **hard gate** for OPAQUE tasks with downstream consumers. Skipping it leaves W172 warnings the linter will surface in Step 5 anyway.

### Step 4: Self-check

Before writing to disk, confirm every item:

- [ ] **Describe gate (hard pre-condition):**
  - [ ] For every `Export`/`Query`/`Create`/`Update`/`CustomObject::*` task emitted, one of these held: (a) a `curl $ZUORA_BASE_URL/v1/describe/<object>` (or Custom Object endpoint) call was made and cached, (b) `mcp__zuora-mcp__ask_zuora` was called with the Step 3a-1 prompt, (c) the object is in `references/zuora-standard-fields.json`, or (d) the user confirmed the field list explicitly.
  - [ ] Every field in `parameters.fields[<object>]` and every field referenced inside `parameters.where_clause` is present in that describe response (or the fallback catalog, or user-confirmed).
  - [ ] For every event in `parameters.event_triggers[]`, the merge-field list from `GET /notifications/email-templates/info/selections?category=<category>` was fetched via `curl` or MCP (Step 3a-5), OR the only tokens used are recognised special tokens (`$event_special_tokens.tokens`).
  - [ ] Every `parameters.event_parameters[*].params[*].value` is either a special token OR a `<BaseObject.Field>` whose `BaseObject` matches the event's declared `baseObject` (`$event_base_objects.events`) AND whose `Field` appeared in the fetched merge-field payload.
- [ ] Deep-copied `workflow-skeleton.json` as the base.
- [ ] Exactly one trigger flag set; scheduled / event config populated as needed.
- [ ] `workflow.type === "Workflow::Setup"` (literal string).
- [ ] `workflow.id === 1` and the Start linkage's `source_workflow_id === 1`.
- [ ] `workflow.data === {}`, `workflow.status === "Inactive"`, `workflow.css` matches the skeleton default.
- [ ] No `ui_trigger` key anywhere in `workflow` (it is not a column and is silently dropped).
- [ ] No `parameters.merge_task_ids` key (auto-derived by Rails; deleted on save).
- [ ] `workflow.parameters` carries the seven always-present keys (`fields`, `entity_name`, `entity_id`, `skipping_check`, `file_encryption`, `secure_error_msgs`, `show_run_prompt`, `callout_response`).
- [ ] `workflow.call_type` is one of `workflow-enums.json` -> `workflow_call_types.user_facing[*].value` (no `ASYNC`/`RULE`/`UI`).
- [ ] `workflow.version` matches `^\d+(?:\.\d+)?(?:\.\d+)?$`.
- [ ] If `event_trigger == true`: `parameters.event_triggers[]` non-empty AND every entry in `parameters.event_parameters[*].eventName` matches one of those names; both `event_parameters` and inner `params` are JSON arrays.
- [ ] If `scheduled_trigger == true`: `interval` is a 6-token cron string and `timezone` is an IANA name.
- [ ] If `notifications.{failure|success|pending|skipped_scheduled_run}` includes any `true`: `notifications.emails[]` is non-empty.
- [ ] If `call_type == "UIACTION"` or `"SYNC_UI_ACTION"`: `ui_pages` has exactly one entry from `supported_ui_pages.pages`.
- [ ] `tasks` array non-empty; `linkages` array non-empty.
- [ ] Every task has a unique integer `id`, an `action_type` that exists in `workflow-enums.json.action_types`, and a `parameters` object (even if `{}`).
- [ ] Every `required_at_import` attribute for the task's `action_type` is populated with a non-empty value.
- [ ] Every `<<REQUIRED: …>>` sentinel replaced.
- [ ] Every boolean in a `boolean_string_params` list is emitted as `"true"` / `"false"`.
- [ ] Enum params use values from `param_enums`.
- [ ] `Logic::Case.parameters.case_condition` keys are sequential `Case_1`, `Case_2`, … and the linkages use the same keys.
- [ ] Exactly one `Start` linkage with `source_workflow_id = workflow.id`, `source_task_id = null`.
- [ ] Every non-Start linkage has `source_workflow_id = null` and non-null `source_task_id`.
- [ ] `linkage_type` values match upstream task hooks (see `workflow-task-templates.json.hooks`).
- [ ] No `For Each` linkage sits on any path to a `Logic::Merge` task (if any exists).
- [ ] **Data-flow walker (Step 3d) ran clean**: no `E170` (unknown `Data.X` reference). Any `W171` / `W172` / `W173` / `W174` warnings either resolved or explicitly accepted.
- [ ] **Opaque-task confirmation (Step 3e) completed for every OPAQUE task with downstream consumers**: each `Callout` / `AsynchronousCallout` / `Logic::Lambda` / `Script::JavaScript` / `Logic::JSONTransform` / `Logic::XMLTransform` / `Logic::CSVTranslator` / `Logic::ResponseFormatter` / `Execute::WorkflowTask` / `Mediation::SendEvents` whose output is referenced downstream carries either:
  - `parameters._expected_response_schema = { "<scope>": { ... } }`, OR
  - `parameters._opaque_trusted = "true"`, OR
  - a downstream normalizer task (`Logic::JSONTransform` / `Logic::ResponseFormatter`) that rebinds the response into a deterministic scope.
- [ ] Inside any `Iterate(object=X)` For-Each branch, downstream references use `Data.X.Field` (single-record form), NOT `Data.X[0].Field` or `Data.X | size` (array forms — would trigger `W173`).
- [ ] After a `Logic::Merge` following a `Logic::Case`, downstream references only use scopes produced on **all** branches (or `W174` will surface for branch-partial scopes).

### Step 5: Lint the output

Write the JSON to a temp path, then run:

```bash
node scripts/lint-workflow-json.js <path-to-generated.json>
```

The linter uses `workflow-task-templates.json` (per-task templates and `data_contract` blocks) and `workflow-enums.json` as its rule source. It prints errors and warnings with file paths and line numbers where possible. Fix every error; address warnings where they apply. Loop compose → lint until the linter exits with status 0.

### Step 6: Optional sandbox dry-run

When the user wants an authoritative import check (e.g., AR column validations, call_type-enablement checks), run:

1. `mcp__zuora-mcp__manage_workflows` with `import_workflow`:
   - `activate: false`
   - `name`: prefixed with `lint-dryrun-` so it is easy to identify and delete.
2. On success, call `delete_workflow` immediately to clean up.
3. If import fails, read the error, auto-repair (most common: missing `required_at_import`, unsupported `call_type`, empty tasks/linkages), and loop.

Note: `activate: false` still **persists** the workflow. It is not a free-form "validate-only" endpoint. Always delete after a dry-run.

### Step 7: Write supporting artifacts

In addition to the workflow JSON, generate as appropriate:

- Callout handler code — use `mcp__zuora-mcp__zuora_codegen` for endpoints that receive / respond to the workflow's callout tasks. Follow the codegen flow: `code_guidance` → `get_api_details` → `get_model_details` → `code_rules`.
- Test scripts — for `run_workflows waitForCompletion=true` + `get_run_status` assertions.
- Monitoring / operational notes.

### Step 8: Suggest next steps

- Sandbox import (for real): `import_workflow activate=true` in sandbox.
- Functional test: `run_workflows waitForCompletion=true` and inspect task-level results via `get_run_status`.
- Production promotion: re-export the sandbox workflow and re-import into production.
- Run `/zuora-validate` on any generated callout handler code.
