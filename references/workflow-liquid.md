# Liquid Templating in Zuora Workflows

Every task parameter that accepts a dynamic value is parsed with Liquid. This document lists the scopes available to Liquid expressions, their shape, and the gotchas that most often cause run-time errors. Distilled from `Task#template_parse` (`~/Workspace/workflow/rails/app/models/task.rb:1423-1480`).

## Scopes

Six root scopes are always in context when a task runs:

| Scope              | Purpose                                                                             |
| ------------------ | ----------------------------------------------------------------------------------- |
| `Data`             | The workflow payload — everything upstream tasks have written.                      |
| `Credentials`      | Zuora tenant credentials, gated by auth type.                                       |
| `WorkflowInstance` | The current workflow run (id, timings, status, call_type, …).                       |
| `WorkflowSetup`    | The workflow *definition* (original_workflow): name, description, parameters, etc.  |
| `TaskInstance`     | The currently-executing task (id, name, retry state, timings, …).                   |
| `GlobalConstants`  | Tenant-level key/value store, populated via Workflow Settings → Global Constants.   |

Inside a Liquid `{% for row in Data.Invoice %}` block, the `forloop` scope is also defined (`forloop.index`, `forloop.first`, etc.).

## `Data` — the workflow payload

Tasks write their output under a named key inside `Data`. The conventional key is the object name (`Account`, `Invoice`, `Subscription`) or an explicit `parameters.placement` override.

| Task                          | Writes to                                                |
| ----------------------------- | -------------------------------------------------------- |
| `Query` / `Export` / `Data::Aqua` | `Data.<object>` (array of hashes) unless `parameters.placement` is set, then `Data.<placement>`. |
| `Callout`                     | `Data.Callout` (single object). Multiple callouts chain into `Data.Callout[0]`, `Data.Callout[1]`, … |
| `Logic::Liquid`               | `Data.Liquid` (single object) unless `parameters.placement` overrides. |
| `Iterate`                     | Current row available as `Data.<object>` (singular, a hash) inside the For-Each body. |
| `GraphQuery`                  | `Data.<baseObject>` (array).                              |
| `Create`                      | `Data.<object>[<ResponseFields>]`.                        |
| `Update` / `Delete`           | Updates `Data.<object>` if the record was loaded upstream. |

Access patterns:

```liquid
{{ Data.Account.Name }}
{{ Data.Invoice[0].Id }}
{{ Data.Callout.ResponseBody.subscription_id }}

{% for inv in Data.Invoice %}
  {{ inv.Id }} - {{ inv.Balance | money }}
{% endfor %}
```

### Workflow input parameters

When a workflow is triggered with ordinary input parameters (ondemand form, callout body, sub-workflow call), define each prompt field with `object_name: "Workflow"` and read those values at `Data.Workflow.<key>`. Do not invent object names to group inputs.

```liquid
{{ Data.Workflow.accountNumber }}
{{ Data.Workflow.ExecutionDate }}
```

### Event-trigger payload

Event-triggered workflows get their event payload mapped through `workflow.parameters.event_parameters` into `Data.<object>.<key>`. The server accepts special tokens that are expanded at trigger time:

| Token                    | Meaning                                               |
| ------------------------ | ----------------------------------------------------- |
| `<Event.Category>`       | `data['name']` — the event name (e.g., `InvoicePosted`). |
| `<Event.Date>`           | `data['eventTime']` formatted as `%F` (UTC date).     |
| `<Event.Timestamp>`      | `data['eventTime']`.                                  |
| `<Functions.Today>`      | Current date formatted as `%F`.                       |
| `<Tenant.ID>`            | `data['tenantId']`.                                   |
| `<Tenant.Name>`          | Empty string in the current Rails implementation.     |

Any other angle-bracket token is treated as a notifications merge-field token: Rails strips the brackets plus an optional `Event.` or `DataSource.` prefix, then looks up that literal key in the event payload. Before emitting tokens such as `<Invoice.Id>` or `<BillingRun.Id>`, fetch the event's merge fields from `/notifications/email-templates/info/selections?category=<event-id-or-custom-category>` and pick a published value. A typical `event_parameters` entry for InvoicePosted writes `Data.Invoice.Id`, `Data.Invoice.AccountId`, etc., which downstream tasks then reference as usual.

## `Credentials` — Zuora tenant access

`Credentials.zuora` exposes a drop object whose method return value depends on the authentication type configured for the tenant:

| Access                         | When available                                             |
| ------------------------------ | ---------------------------------------------------------- |
| `Credentials.zuora.url`        | Always.                                                    |
| `Credentials.zuora.rest_endpoint` | Always. This value is the Zuora REST v1 base URL and already includes the `v1` segment (for example `https://rest.zuora.com/v1/`). Do NOT append `/v1` to it -- that can produce a `/v1/v1/` double-prefix. |
| `Credentials.zuora.username`   | Only for Basic auth tenants. Raises on OAuth tenants; do not use for Zuora API Callout headers. |
| `Credentials.zuora.password`   | Only for Basic auth tenants; do not use for Zuora API Callout headers. |
| `Credentials.zuora.client_id`  | Only for OAuth tenants.                                    |
| `Credentials.zuora.client_secret` | Only for OAuth tenants.                                 |

Canonical Zuora API Callout auth block:

```json
{
  "authorization": { "type": "zuora" },
  "headers": [
    { "key": "Content-Type", "value": "application/json" }
  ]
}
```

For v1 APIs, append only the resource path after `v1/`: `{{ Credentials.zuora.rest_endpoint }}orders`, `{{ Credentials.zuora.rest_endpoint }}subscriptions/{{ Data.Subscription.Id }}`. Do not emit `{{ Credentials.zuora.rest_endpoint }}/v1/orders`, and do not use the fragile `{{ Credentials.zuora.rest_endpoint | replace: "/v1/", "" }}/v1/orders` form. For non-v1 APIs, first normalize the base explicitly, for example `{{ Credentials.zuora.rest_endpoint | split: "/v1" | first }}/oauth/token`.

Do not hard-code tenant URLs or credentials in callouts; for Zuora APIs, always use `Credentials.zuora.rest_endpoint` with `authorization.type = "zuora"`. Do not add `apiAccessKeyId`, `apiSecretAccessKey`, `Authorization`, or bearer-token headers; Rails rejects some plain-text credential headers and the built-in Zuora auth path is what preserves tenant/entity context.

## `WorkflowInstance`, `WorkflowSetup`, `TaskInstance`

These are read-only introspection scopes.

- `WorkflowInstance.id`, `WorkflowInstance.call_type`, `WorkflowInstance.started_at`, `WorkflowInstance.external_track_id`.
- `WorkflowSetup.id`, `WorkflowSetup.name`, `WorkflowSetup.description`, `WorkflowSetup.parameters`.
- `TaskInstance.id`, `TaskInstance.name`, `TaskInstance.attempts`, `TaskInstance.task_setup_id`.

Common usage:

```liquid
Run {{ WorkflowInstance.id }} at {{ WorkflowInstance.started_at }}
For Workflow "{{ WorkflowSetup.name }}"
Processing {{ TaskInstance.name }} (task {{ TaskInstance.id }})
```

These scopes are blanked out when a task is exported/imported between tenants, so relying on them for business logic is fine but their values should not be compared across tenants.

## `GlobalConstants`

Tenant-level configuration stored at the app-instance level.

```liquid
{{ GlobalConstants.SLACK_WEBHOOK_URL }}
{{ GlobalConstants.DUNNING_THRESHOLD_AMOUNT }}
```

Define constants in Workflow Settings → Global Constants; they are loaded on every task render.

## Filters

Zuora registers stock Liquid filters plus the Workflow-specific `Liquid::Filters` module from `~/Workspace/workflow/rails/lib/liquid/filters.rb`. Before writing a `Logic::Liquid` task, check whether a standard Liquid filter or a Workflow-specific filter already expresses the operation. Prefer built-in filters over manual `for` / `if` / `push` loops for simple array selection or grouping. See `workflow-liquid-filters.md` for argument counts, argument types, return values, and examples.

| Filter        | Example                                                | Purpose                                  |
| ------------- | ------------------------------------------------------ | ---------------------------------------- |
| `date`        | `{{ "now" | date: "%Y-%m-%d" }}`                       | Format timestamps.                       |
| `money`       | `{{ Data.Invoice.Balance | money }}`                   | Currency formatting.                     |
| `to_json`     | `{{ Data.Account | to_json }}`                         | Serialize to JSON for logging.           |
| `escape`      | `{{ body | escape }}`                                  | HTML-escape user input.                  |
| `default`     | `{{ Data.Account.Name | default: "Anonymous" }}`       | Fallback value.                          |
| `replace`     | `{{ Data.Account.Name | replace: "-", "_" }}`          | String replacement.                      |
| `split` / `join` | `{{ "a,b,c" | split: "," | join: " - " }}`          | Token manipulation.                      |
| `size`        | `{{ Data.Invoice | size }}`                            | Collection length.                       |

Standard Liquid filters (`upcase`, `downcase`, `strip`, `slice`, `truncate`, `first`, `last`, …) all work. Workflow-specific filters most relevant to composition:

- `where` / `where_exp`: select rows without manual `for` + `if` + `push` loops, e.g. `{% assign active = Data.Subscription | where: "Status", "Active" %}` or `{% assign overdue = Data.Invoice | where_exp: "inv", "inv.Balance > 0" %}`.
- `group_by` / `group_by_exp`: bucket rows without constructing grouping hashes by hand.
- `parse_json` / `to_json` / `to_xml`: parse or emit structured payloads without string-concatenating JSON/XML.
- `date_manip`, `date_between`, `date_diff`, `in_time_zone`, `timezone`, `http_date`: date math and timezone formatting.
- `regex`, `money`, `base64_encode` / `base64_decode`, `md5`, `sha1`, `sha2`, `hmac*`: validated text, numeric, encoding, and signing helpers.
- `push` / `pop` / `shift` / `unshift`: array mutation helpers; use them for true array construction, not simple filtering that `where` or `where_exp` can express.

Anti-pattern: `{% assign active = null | array %}{% for sub in Data.Subscription %}{% if sub.Status == "Active" %}{% assign active = active | push: sub %}{% endif %}{% endfor %}`. Preferred: `{% assign active = Data.Subscription | where: "Status", "Active" %}`. Keep manual loops only when transforming rows or building a custom shape; the linter reports obvious manual selection loops as `W184`.

## Strict mode and `strict_variables`

Every task supports a `parameters.strict_variables` toggle (string `"true"` / `"false"`, default `"true"`). When strict:

- Accessing a missing key raises `Liquid::UndefinedVariable`.
- Template parse errors raise `Liquid::SyntaxError`.

When non-strict, missing variables render to empty strings. Always prefer strict mode; disable only for free-form email bodies or preview scenarios.

## Gotchas

1. **Missing braces or typos render empty in non-strict mode.** Always set `strict_variables: "true"` in templates you care about.

2. **`Data.<object>` for a Query result is an array unless `placement` is set and the query returns a single row.** Use `Data.Invoice[0].Id` or iterate with `{% for inv in Data.Invoice %}`.

3. **Inside an `Iterate` body, `Data.<object>` is the single current row.** Outside the iterator, the same key is the full collection. Writing consistent templates means testing both shapes.

4. **`Data.Callout` is scalar for one callout but an array if multiple callouts exist.** Tasks that appear after the second callout must reference `Data.Callout[0]`, `Data.Callout[1]`, etc.

5. **Liquid validation is skipped on import.** `Logic::Case#task_setup_validation` and `If#task_setup_validation` parse their `case_clause` / `if_clause` at save time, but `Task.import` calls `save!(validate: false)`, which bypasses this. The only pre-run check is the client-side linter; Liquid syntax errors surface at first execution, not import.

6. **Do not use Liquid tags in a `Logic::Case.parameters.case_condition` key.** Keys must be sequential `Case_1`, `Case_2`, …, `Case_Else`. Put Liquid in the case *values*, not the keys.

7. **Strict filters** — `Liquid::Template.parse` uses `:error_mode => :strict`, so unknown filter names raise, not silently fail.

8. **Template timeout.** Liquid parse is capped at `LIQUID_TEMPLATE_PARSE_TIMEOUT` (three minutes in production). Heavy nested loops or huge payloads will error with `Evaluation takes more than 3 minutes to finish…`. Prefer filtered queries over client-side iteration.

9. **`{{ "now" | date: "%Y-%m-%d" }}`** is the idiomatic "today" expression. Don't inject Ruby-level times.

## Cross-references

- Task-specific Liquid requirements: `workflow-task-catalog.md` and `workflow-task-templates.json`.
- Where Liquid shows up in each task's parameters: `workflow-examples.md`.
- Machine-readable: `workflow-task-templates.json` entries mark templated params via placeholder text such as `"<<REQUIRED: Liquid expression>>"`.
