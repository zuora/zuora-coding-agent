# Zuora Workflow Triggers & Linkages

Reference for selecting the right trigger style, the correct `call_type`, and for wiring tasks together with valid `linkage_type` values. Distilled from `~/Workspace/workflow/rails/app/models/workflow/setup.rb`, `~/Workspace/workflow/rails/app/models/linkage.rb`, and each task class.

## Trigger types

Every workflow carries four boolean flags on the `workflow` envelope. At least one must be `true`; multiple flags are valid when the same task graph should run in more than one way. Leaving all four `false` makes the workflow unreachable.

| Flag                | Purpose                                                               | Additional fields required                                          |
| ------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------------- |
| `ondemand_trigger`  | User clicks Run in the Zuora Workflow UI, or the tenant API fires it. | none                                                                |
| `callout_trigger`   | External system POSTs to the workflow's callout URL.                  | Every `required` field in `workflow.parameters.fields` must have a non-blank `callout_id`. |
| `scheduled_trigger` | Runs on a cron schedule.                                              | `workflow.interval` (cron string) and `workflow.timezone` (must be in `ActiveSupport::TimeZone.all.map(&:name)`). |
| `event_trigger`     | Runs when a Zuora business event fires.                               | `workflow.parameters.event_triggers = [EventName, …]`; optional `workflow.parameters.event_parameters` to map event payload into `Data`. |

Default when in doubt: `ondemand_trigger: true`, all others `false` (the empty-skeleton default).

### Event-trigger details

See `workflow-events.md` for the full standard event catalog, the `<canonical_name_corrections>` table, and how to use the `mcp__zuora-mcp__ask_zuora` tool to verify custom event registration via `GET /events/event-triggers`.

- `parameters.event_triggers` is an array of canonical standard event names or exact registered custom event names. The 32 standard events are listed in `workflow-enums.json` -> `standard_events.events` (sourced from `WorkflowDefinitionForm.js` `defaultEvents`). Common gotcha: "BillRunCompleted" is **not** a real event name; the canonical value is `BillingRunCompletion`. If the user provides a tenant-custom event name, keep it in `event_triggers[]`, set `workflow.event_trigger: true`, and verify or document that the custom event must already be registered.
- `parameters.event_parameters` is the contract that tells Rails which event payload fields to bind into the workflow's `Data` scope. Shape:

```json
{
  "event_parameters": [
    {
      "eventName": "BillingRunCompletion",
      "params": [
        { "object": "BillingRun", "key": "Id", "value": "<BillingRun.Id>" }
      ]
    }
  ]
}
```

  Both `event_parameters` and the inner `params` MUST be JSON arrays (not Hashes). Downstream tasks read these as `{{ Data.BillingRun.Id }}`.

### Scheduled-trigger details

- `interval` is 6-token cron parsed by `Rufus::Scheduler.parse` (`workflow/setup.rb:161-166`). Tokens: `<sec> <min> <hour> <day-of-month> <month> <day-of-week>`. The React UI always emits second=0, e.g., `0 30 09 /1 * *` = "daily at 09:30". The `/N` syntax means "every N units".
- `timezone` must be a Rails `ActiveSupport::TimeZone` friendly name (`UTC`, `Pacific Time (US & Canada)`, `London`, `Tokyo`, …). Bare IANA names such as `America/Los_Angeles` can be resolved by `find_tzinfo`, but they fail the `Workflow::Setup` inclusion validator (`workflow/setup.rb:32`) during import. At runtime Rails resolves the friendly name via `ActiveSupport::TimeZone.find_tzinfo(self.timezone).name` (`workflow.rb:335`).
- Both `interval` and `timezone` are required when `scheduled_trigger == true` (`workflow/setup.rb:31`).

## `call_type` matrix

`workflow.call_type` selects the execution mode of the workflow and determines which `action_type` values may appear in its tasks. The user-facing options (post-filter from `Task.task_mode.keys - %w(ASYNC RULE UI)`, `workflows_controller.rb:20-21`) are:

| call_type          | Use case                                                     | Tenant prerequisite                                                                                      |
| ------------------ | ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| `BATCH`            | **Default.** Standard background workflows (reporting, integration, scheduled jobs). | none                                                                                       |
| `SYNC`             | Synchronous response. Caller waits for the workflow inline.  | `extra_settings.synchronous_mode`. Task set filtered to those with `task_mode['SYNC'] == true`.          |
| `REALTIME`         | Sub-second priority lane for low-latency callouts.           | none                                                                                                     |
| `UIACTION`         | Workflow surfaces as a button on a Zuora UI page.            | `ui_pages` must be set with exactly one `supported_ui_pages` entry.                                      |
| `SYNC_UI_ACTION`   | Synchronous UIACTION variant. Caller blocks on the UI thread.| `extra_settings.sync_ui_action_mode`.                                                                    |
| `DATASTREAM`       | Streaming pipeline (`UsageMediation::*` tasks).              | `extra_settings.data_stream_mode`.                                                                       |
| `BUSINESS_PROCESS` | Long-running business process (`Approval`, `Delay`, UI page tasks). | `extra_settings.business_process`.                                                                |

**Deprecated / internal** (rejected by linter rule `E150`): `ASYNC`, `RULE`, `UI`. Although `Task.task_mode` still lists them, the React settings page hides them and `Workflow::Setup.import` will silently coerce or reject them. Use `BATCH` instead of `ASYNC`, `BUSINESS_PROCESS` instead of `RULE`, and `UIACTION` instead of `UI`.

The tenant enablement checks (`sync_not_enabled`, `ui_not_enabled`, `data_stream_not_enabled`) fire during `Workflow::Setup.import`; a client-side workflow with an unavailable `call_type` is rejected outright. When unsure, use `BATCH`.

## Linkage shape

Every task-to-task or workflow-to-task edge is one linkage object:

```json
{
  "source_workflow_id": null,
  "source_task_id": null,
  "target_task_id": null,
  "linkage_type": ""
}
```

Two patterns:

- **Start linkage (always exactly one per workflow):** `source_workflow_id = workflow.id`, `source_task_id = null`, `linkage_type = "Start"`, `target_task_id` = id of the entry task.
- **Task-to-task linkage:** `source_workflow_id = null`, `source_task_id` = upstream task's `id`, `target_task_id` = downstream task's `id`, `linkage_type` = one of the upstream task's published hooks (see catalog below).

Source invariant (client-side only; the server-side check is commented out at `app/models/linkage.rb:33`): a linkage sets either `source_workflow_id` or `source_task_id`, never both and never neither. The linter warns on any violation.

## Canonical linkage catalog

The server stores `linkage_type` as a free string and does **not** cross-check it against the source task's `hooks`. The linter is the only enforcement.

| Task (`action_type`)           | Published hooks (`linkage_type` values)                        |
| ------------------------------ | --------------------------------------------------------------- |
| All tasks (base class default) | `Success`, `Failure`                                            |
| `If`                           | `True`, `False`, `Failure`                                      |
| `Logic::Case`                  | `Case_1`, `Case_2`, … (sequential), `Case_Else`, `Failure`      |
| `Iterate`                      | `For Each` (space!), `Complete`, `Failure`                      |
| `Approval`                     | `Approve`, `Reject`, `Failure`                                  |
| `UI::Page`                     | `Page:<route>` for each non-blank `parameters.route`; `Success`, `Failure` |
| `UI::WebShare`                 | `Webshare:<route>` for each route, `Upload`, `Timeout`, `Success`, `Failure` |
| `UsageMediation::*`            | `next`, `error` (lowercase, on purpose)                          |
| Workflow start                 | `Start`                                                         |

Common typos the linter rewrites to "did-you-mean" suggestions:

| Wrong           | Correct    |
| --------------- | ---------- |
| `Iterate`       | `For Each` |
| `ForEach`       | `For Each` |
| `for_each`      | `For Each` |
| `case_1`        | `Case_1`   |
| `case_else`     | `Case_Else`|
| `success`/`SUCCESS` | `Success` |
| `failure`/`FAILURE` | `Failure` |
| `true`/`false`  | `True`/`False` |
| `start`         | `Start`    |

## The For-Each-before-Merge rule

If a workflow contains any `Logic::Merge` task, then no `For Each` linkage may lie on a path from the workflow start to any Merge task. Rails enforces this via `Linkage#avoid_for_each_linkage_before_merge_task` (`app/models/linkage.rb:72-122`) with a DFS. The linter approximates with a path-substring check that is enough to catch nearly every violation in practice.

Corollary: if you need to fan out with `Iterate` and then converge, drop the Merge — just connect the iteration body's `Success` (or the iterator's `Complete`) directly to the next task. Use `Logic::Merge` only for fan-outs that do NOT use `For Each`, e.g. parallel branches from a `Logic::Case` or an `If` + `If`.

## Composition rules for linkages

1. Emit the Start linkage first; `target_task_id` points at the workflow entry task.
2. For every subsequent task, add one linkage per upstream task-to-this-task edge, using the upstream task's `linkage_type`.
3. `Case_N` linkages must be emitted in numeric order and must match the sequentialized `Case_1`, `Case_2`, … keys in the Case task's `parameters.case_condition`.
4. Every task needs at least one inbound linkage (except the one targeted by Start, which is the entry). Orphan tasks are lint warnings.
5. The linter warns on cycles; Rails does not detect cycles and will happily import a workflow that hangs at runtime.

## Workflow-level field derivation by trigger style

This is the authoritative cheat-sheet for filling out the `workflow.*` envelope. Every key is sourced from the React settings page (`app/javascript/components/WorkflowSettingsForm.js`), `WorkflowsController#workflow_params`, `Workflow::Setup` validations, and the `workflows` table schema. Items marked `[lint-enforced]` have a corresponding rule in `scripts/lint-workflow-json.js`.

### Always-set fields (independent of trigger style)

| Field | How to derive | Default | Notes |
|---|---|---|---|
| `id` | Always `1` `[lint E114]` | `1` | Cosmetic. Server assigns the real PK. The Start linkage's `source_workflow_id` must equal this value. |
| `name` | Same as `workflow_definition.name` `[lint E115]` | from definition | Overwritten by controller on import (`workflows_controller.rb:328`). |
| `description` | Free text describing this version | `""` | Should differ from `workflow_definition.description`. |
| `data` | Always `{}` `[lint E116]` | `{}` | Set at runtime by `Workflow::Instance#set_data`. |
| `type` | Always `"Workflow::Setup"` `[lint E117]` | `"Workflow::Setup"` | `Workflow::Setup.import` overrides anyway (`workflow/setup.rb:418`). |
| `status` | Always `"Inactive"` on import `[lint E118]` | `"Inactive"` | Use `activate_version: true` on import to flip to Active. |
| `css` | Constant | `{"top":"40px","left":"35px"}` | DB default; placement on canvas. |
| `priority` | Default `"Medium"`. Use `"High"` for time-critical event workflows. | `"Medium"` | Validated by Rails (`workflow/setup.rb:34`). |
| `delete_ttl` | Default `30` (Sandbox) / `45` (Production). | `30` | Days of retention for completed instances. Rails validates `0 <= delete_ttl <= retention`. |
| `version` | Default `"0.0.1"` for new; increment for new versions. `[lint E153]` | `"0.0.1"` | Must match `^\d+(?:\.\d+)?(?:\.\d+)?$`. |
| `call_type` | Default `"BATCH"`. See call_type matrix above. `[lint E150]` | `"BATCH"` | Linter rejects `ASYNC`/`RULE`/`UI`. |
| `notifications` | Default-shaped `{}`-equivalent. Populate only on user request. `[lint E140]` | empty defaults | Schema in `workflow-enums.json` -> `notifications_schema`. |
| `ui_pages` | `{}` for non-UIACTION; for UIACTION: exactly one entry from `supported_ui_pages`. `[lint E160]` | `{}` | Required when `call_type == "UIACTION"`. |
| `solution_id`, `extension_id` | `null` for tenant-authored workflows. Set when packaging as a Connect extension. | `null` | |
| `zuora_org_id` | `null` (deprecated column). | `null` | Use `zuora_org_ids[]` instead. |
| `zuora_org_ids` | `[]` = all accessible orgs. Specific UUIDs restrict the workflow. | `[]` | |
| **NEVER emit** `ui_trigger`, `merge_task_ids` `[lint E119]` | — | — | `ui_trigger` is not a column on `workflows`; `merge_task_ids` is auto-derived. |

### Trigger-flag combinations and their additional requirements

Set at least one of the four trigger flags to `true`. Multiple trigger flags are valid when the same workflow task graph should be launched in multiple ways; Rails runs each enabled trigger's validation independently. Do not create duplicate workflows with identical tasks just to support both scheduled and on-demand execution. `[lint E005]`

When combining triggers, satisfy every enabled trigger's prerequisites. In particular, scheduled runs cannot prompt a user, so every required `parameters.fields[]` input needs a non-blank `default` when `scheduled_trigger == true`.

#### Common combined shape: Ondemand + Scheduled

```json
{
  "ondemand_trigger": true,
  "callout_trigger": false,
  "scheduled_trigger": true,
  "event_trigger": false,
  "interval": "0 30 09 /1 * *",
  "timezone": "Pacific Time (US & Canada)"
}
```

Use this when the user wants the same workflow to run manually and on a schedule. The task graph should be shared; use defaults or a small normalizer step if scheduled runs need values that an on-demand user would normally enter.

#### A. Ondemand only (the default)

```json
{
  "ondemand_trigger": true,
  "callout_trigger": false,
  "scheduled_trigger": false,
  "event_trigger": false
}
```

No additional fields required. The `parameters.fields[]` array can optionally define a structured Run prompt. The user clicks Run in the UI or calls `POST /workflows/:id/run`.

#### B. Callout only

```json
{
  "ondemand_trigger": false,
  "callout_trigger": true,
  "scheduled_trigger": false,
  "event_trigger": false
}
```

Required additional fields:

- `parameters.fields[]`: optional but recommended. Defines the inbound JSON body schema. Each field is `{object_name, field_name, default, required, datatype, index}` where `datatype` is one of `JSON | Boolean | Text | Integer | Decimal | Date | DateTime-Local | File-Field`. Use `object_name: "Workflow"` for ordinary workflow inputs, `object_name: "Files"` for file uploads, or a real supported Zuora object from the run-prompt dropdown; do not invent grouping objects such as `BillRunConfig`.
- `parameters.callout_response`: usually `"workflow instance"` (default).

External system POSTs to `/workflows/:id/callout`. Use this for "trigger workflow from a Zuora notification" patterns (configure a standard Notification to hit the callout URL).

#### C. Scheduled only

```json
{
  "ondemand_trigger": false,
  "callout_trigger": false,
  "scheduled_trigger": true,
  "event_trigger": false,
  "interval": "0 30 09 /1 * *",
  "timezone": "Pacific Time (US & Canada)"
}
```

Required additional fields `[lint E131, E133, E175]`:

- `interval`: 6-token Rufus/Fugit cron string `SEC MIN HOUR DOM MON DOW`. The React UI's `CronScheduler` always emits 6 tokens with `second=0` and uses bare `/N` (= `*/N`) step syntax. 5-token Unix cron is also accepted by Rufus but the UI never emits it. Day-of-week names (`MON-FRI`) and ordinals (`MON#2`) are supported. See `workflow-enums.json` -> `interval_schema.examples`.
- `timezone`: Rails `ActiveSupport::TimeZone` friendly name (e.g. `"UTC"`, `"Eastern Time (US & Canada)"`, `"London"`, `"Tokyo"`). The full allowlist is in `references/rails-timezones.json`. Bare IANA strings like `"America/Los_Angeles"` fail Rails validation (`workflow/setup.rb` L32) -- use `"Pacific Time (US & Canada)"` instead. At runtime, Rails resolves the friendly name to its IANA target via `ActiveSupport::TimeZone.find_tzinfo(name).name` and appends it to the Rufus cron string (`workflow.rb` L335-336).

#### D. Event only

```json
{
  "ondemand_trigger": false,
  "callout_trigger": false,
  "scheduled_trigger": false,
  "event_trigger": true,
  "parameters": {
    "event_triggers": ["BillingRunCompletion"],
    "event_parameters": [
      {
        "eventName": "BillingRunCompletion",
        "params": [
          { "object": "BillingRun", "key": "Id", "value": "<BillingRun.Id>" }
        ]
      }
    ]
  }
}
```

Required additional fields `[lint E007, E122]`:

- `parameters.event_triggers[]`: array of canonical standard event-name strings or exact registered custom event names. Resolve via `workflow-enums.json` -> `standard_events` first (the lookup includes `$canonical_name_corrections` for natural-language requests like "BillRunCompleted"); if no match, preserve the user-provided custom event name and verify registration.
- `parameters.event_parameters[]`: array of `{eventName, params: [...]}`. Both the outer and inner arrays MUST be JSON arrays (not Hashes). Each `params[*].value` uses `<Object.Field>` placeholder syntax sourced from `GET /notifications/email-templates/info/selections?category=<category>`.

For the full event derivation guide, see `workflow-events.md`.

### Multi-entity tenants (optional)

If the tenant has more than one Zuora entity attached, `parameters.entity_id` and `parameters.entity_name` SHOULD be set. `Workflow::Setup.import` (`workflow/setup.rb:435-442`) auto-fills them when the tenant has exactly one entity, so you only need to set them explicitly when the user names a specific entity.

## Cross-references

- Task catalog (all `action_type` values): `workflow-task-catalog.md`
- Liquid scopes (for building dynamic `parameters`): `workflow-liquid.md`
- Standard event catalog and API derivation: `workflow-events.md`
- Full annotated examples: `workflow-examples.md`
- Machine-readable enums (canonical `linkage_type` list, `standard_events`, `supported_ui_pages`, schemas): `workflow-enums.json`
- Machine-readable templates with `hooks`: `workflow-task-templates.json`
