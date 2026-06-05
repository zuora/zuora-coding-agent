# Zuora Workflow Examples

Six end-to-end, lint-clean workflow JSONs for the canonical use cases. Each example is annotated with the design decisions and the patterns the linter looks for. Use them as fixtures when composing a new workflow.

These JSONs double as regression fixtures for `scripts/lint-workflow-json.js`. Keep them lint-clean.

## Use Case 1 — Event-triggered invoice export to external ERP

**Requirement.** When an invoice is posted in Zuora, export it to the ERP's `/invoices` endpoint.

**Design choice:** single-task linear flow, event-triggered on `InvoicePosted`. The event payload maps the described `<Invoice.Id>` merge field into `Data.Invoice.Id`, so a single `Callout` can POST the invoice id.

```json
{
  "workflow_definition": {
    "name": "ERP Invoice Export",
    "description": "Push newly-posted invoices to the ERP.",
    "category": "Default",
    "ui_page_roles": []
  },
  "workflow": {
    "id": 1,
    "name": "ERP Invoice Export",
    "description": "Event-triggered export to external ERP on InvoicePosted.",
    "parameters": {
      "event_triggers": ["InvoicePosted"],
      "event_parameters": [
        {
          "eventName": "InvoicePosted",
          "params": [
            { "object": "Invoice", "key": "Id",        "value": "<Invoice.Id>" },
            { "object": "Invoice", "key": "AccountId", "value": "<Invoice.AccountId>" }
          ]
        }
      ]
    },
    "data": {},
    "type": "Workflow::Setup",
    "ondemand_trigger": false,
    "callout_trigger": false,
    "scheduled_trigger": false,
    "event_trigger": true,
    "interval": null,
    "timezone": null,
    "status": "Inactive",
    "css": { "top": "40px", "left": "35px" },
    "notifications": {},
    "call_type": "BATCH",
    "priority": "Medium",
    "delete_ttl": 30
  },
  "tasks": [
    {
      "id": 101,
      "name": "Export Invoice to ERP",
      "parameters": {
        "url": "{{ GlobalConstants.ERP_BASE_URL }}/invoices",
        "method": "POST",
        "body_type": "raw",
        "raw_body": "{\n  \"zuora_invoice_id\": \"{{ Data.Invoice.Id }}\",\n  \"account_id\": \"{{ Data.Invoice.AccountId }}\"\n}",
        "headers": [
          { "key": "Content-Type", "value": "application/json" },
          { "key": "X-API-Key",    "value": "{{ GlobalConstants.ERP_API_KEY }}" }
        ],
        "authorization": { "type": "none" },
        "validation": { "status_codes": ["200", "201", "202"] },
        "retry_rules": { "retry_count": "3", "retry_window": "30" },
        "strict_variables": "true"
      },
      "action_type": "Callout",
      "object": null,
      "object_id": null,
      "call_type": "SOAP",
      "task_id": null,
      "css": { "top": "40px", "left": "350px" },
      "concurrent_limit": 9999999,
      "tags": [],
      "priority": "Medium",
      "assignment": []
    }
  ],
  "linkages": [
    { "source_workflow_id": 1, "source_task_id": null, "target_task_id": 101, "linkage_type": "Start" }
  ]
}
```

Checklist highlights:

- `event_trigger: true`, other trigger flags `false`.
- `parameters.event_triggers` array present and non-empty.
- `parameters.event_parameters` maps the event payload into `Data.Invoice.*`.
- Exactly one `Start` linkage from workflow to the entry task.
- `parameters` object present on every task (here, a complex one).
- `strict_variables: "true"` is a string, not boolean.
- Status codes as string-array.

## Use Case 2 — Scheduled dunning workflow with 3-level escalation

**Requirement.** Every morning, find invoices overdue by more than 7 days and escalate: gentle email at 7–14 days, firm email at 15–30 days, handoff to collections above 30 days.

**Design choice:** `scheduled_trigger` daily at 08:00 UTC. `Query` overdue invoices, `Iterate` over them, evaluate a `Logic::Case` clause with three branches (`Case_1`, `Case_2`, `Case_Else`), and fan out to three downstream tasks. No `Logic::Merge` — the iterator's `Complete` hook converges the paths.

```json
{
  "workflow_definition": {
    "name": "Daily Dunning Escalation",
    "description": "Triages overdue invoices into gentle / firm / collections.",
    "category": "Collections",
    "ui_page_roles": []
  },
  "workflow": {
    "id": 2,
    "name": "Daily Dunning Escalation",
    "description": "Scheduled daily at 08:00 UTC.",
    "parameters": {},
    "data": {},
    "type": "Workflow::Setup",
    "ondemand_trigger": false,
    "callout_trigger": false,
    "scheduled_trigger": true,
    "event_trigger": false,
    "interval": "0 8 * * *",
    "timezone": "UTC",
    "status": "Inactive",
    "css": { "top": "40px", "left": "35px" },
    "notifications": {},
    "call_type": "BATCH",
    "priority": "Medium",
    "delete_ttl": 30
  },
  "tasks": [
    {
      "id": 201,
      "name": "Query Overdue Invoices",
      "parameters": {
        "fields": { "Invoice": { "Id": "true", "AccountId": "true", "Balance": "true", "DueDate": "true" } },
        "where_clause": "Status = 'Posted' AND Balance > 0 AND DueDate < '{{ 'now' | date: \"%Y-%m-%d\" }}'",
        "placement": "",
        "zero_query_proceed": "false",
        "strict_variables": "true"
      },
      "action_type": "Query",
      "object": "Invoice",
      "object_id": null,
      "call_type": "SOAP",
      "task_id": null,
      "css": { "top": "40px", "left": "350px" },
      "concurrent_limit": 5,
      "tags": [],
      "priority": "Medium",
      "assignment": []
    },
    {
      "id": 202,
      "name": "Iterate Over Invoices",
      "parameters": { "file_type": "CSV", "fetched_data_is_array": "true", "strict_variables": "true" },
      "action_type": "Iterate",
      "object": "Invoice",
      "object_id": null,
      "call_type": "BATCH",
      "task_id": 201,
      "css": { "top": "40px", "left": "700px" },
      "concurrent_limit": 150,
      "tags": [],
      "priority": "Medium",
      "assignment": []
    },
    {
      "id": 207,
      "name": "Query Invoice Account",
      "parameters": {
        "fields": {
          "Account":       { "Id": "true", "AccountNumber": "true" },
          "BillToContact": { "WorkEmail": "true", "FirstName": "true", "LastName": "true" }
        },
        "where_clause": "Account.Id = '{{ Data.Invoice.AccountId }}'",
        "placement": "",
        "zero_query_proceed": "false",
        "strict_variables": "true"
      },
      "action_type": "Query",
      "object": "Account",
      "object_id": null,
      "call_type": "SOAP",
      "task_id": 202,
      "css": { "top": "40px", "left": "900px" },
      "concurrent_limit": 5,
      "tags": [],
      "priority": "Medium",
      "assignment": []
    },
    {
      "id": 203,
      "name": "Classify Overdue Days",
      "parameters": {
        "case_clause": "{% assign today = 'now' | date: '%s' | plus: 0 %}{% assign due = Data.Invoice.DueDate | date: '%s' | plus: 0 %}{% assign days = today | minus: due | divided_by: 86400 %}{% if days <= 14 %}gentle{% elsif days <= 30 %}firm{% else %}collections{% endif %}",
        "case_condition": {
          "Case_1": "gentle",
          "Case_2": "firm"
        },
        "disable_regex": "true",
        "strict_variables": "true",
        "disable_validation": "false"
      },
      "action_type": "Logic::Case",
      "object": null,
      "object_id": null,
      "call_type": "SOAP",
      "task_id": 207,
      "css": { "top": "40px", "left": "1050px" },
      "concurrent_limit": 9999999,
      "tags": [],
      "priority": "Medium",
      "assignment": []
    },
    {
      "id": 204,
      "name": "Gentle Reminder Email",
      "parameters": {
        "email": {
          "to": ["{{ Data.Account.BillToContact.WorkEmail }}"],
          "cc": [], "bcc": [],
          "from": "dunning@zuora.com",
          "reply_to": "", "name": "",
          "subject": "Friendly reminder: invoice {{ Data.Invoice.Id }} is past due",
          "template": "<p>Hi,</p><p>Invoice {{ Data.Invoice.Id }} with balance {{ Data.Invoice.Balance | money }} is past its due date. We appreciate prompt payment. Thank you.</p>",
          "attachments": { "invoices": "false" },
          "preview_only": "false",
          "disable_editor": "false"
        },
        "files": {},
        "strict_variables": "true"
      },
      "action_type": "Email",
      "object": null,
      "object_id": null,
      "call_type": "SOAP",
      "task_id": 203,
      "css": { "top": "-80px", "left": "1400px" },
      "concurrent_limit": 9999999,
      "tags": [],
      "priority": "Medium",
      "assignment": []
    },
    {
      "id": 205,
      "name": "Firm Warning Email",
      "parameters": {
        "email": {
          "to": ["{{ Data.Account.BillToContact.WorkEmail }}"],
          "cc": ["collections@zuora.com"], "bcc": [],
          "from": "dunning@zuora.com",
          "reply_to": "", "name": "",
          "subject": "URGENT: invoice {{ Data.Invoice.Id }} is {{ Data.Invoice.Balance | money }} overdue",
          "template": "<p>Your invoice {{ Data.Invoice.Id }} is significantly past due. Please remit payment within 7 business days to avoid escalation.</p>",
          "attachments": { "invoices": "true" },
          "preview_only": "false",
          "disable_editor": "false"
        },
        "files": {},
        "strict_variables": "true"
      },
      "action_type": "Email",
      "object": null,
      "object_id": null,
      "call_type": "SOAP",
      "task_id": 203,
      "css": { "top": "40px", "left": "1400px" },
      "concurrent_limit": 9999999,
      "tags": [],
      "priority": "Medium",
      "assignment": []
    },
    {
      "id": 206,
      "name": "Handoff to Collections System",
      "parameters": {
        "url": "{{ GlobalConstants.COLLECTIONS_WEBHOOK }}",
        "method": "POST",
        "body_type": "raw",
        "raw_body": "{\n  \"invoice_id\": \"{{ Data.Invoice.Id }}\",\n  \"account_id\": \"{{ Data.Invoice.AccountId }}\",\n  \"balance\": \"{{ Data.Invoice.Balance }}\"\n}",
        "headers": [{ "key": "Content-Type", "value": "application/json" }],
        "authorization": { "type": "none" },
        "validation": { "status_codes": ["200", "201", "202"] },
        "retry_rules": { "retry_count": "3", "retry_window": "30" },
        "strict_variables": "true"
      },
      "action_type": "Callout",
      "object": null,
      "object_id": null,
      "call_type": "SOAP",
      "task_id": 203,
      "css": { "top": "160px", "left": "1400px" },
      "concurrent_limit": 9999999,
      "tags": [],
      "priority": "Medium",
      "assignment": []
    }
  ],
  "linkages": [
    { "source_workflow_id": 2,    "source_task_id": null, "target_task_id": 201, "linkage_type": "Start" },
    { "source_workflow_id": null, "source_task_id": 201,  "target_task_id": 202, "linkage_type": "Success" },
    { "source_workflow_id": null, "source_task_id": 202,  "target_task_id": 207, "linkage_type": "For Each" },
    { "source_workflow_id": null, "source_task_id": 207,  "target_task_id": 203, "linkage_type": "Success" },
    { "source_workflow_id": null, "source_task_id": 203,  "target_task_id": 204, "linkage_type": "Case_1" },
    { "source_workflow_id": null, "source_task_id": 203,  "target_task_id": 205, "linkage_type": "Case_2" },
    { "source_workflow_id": null, "source_task_id": 203,  "target_task_id": 206, "linkage_type": "Case_Else" }
  ]
}
```

Checklist highlights:

- `scheduled_trigger: true`; `interval` is a 5- or 6-token Rufus cron string; `timezone` is a Rails ActiveSupport friendly name (e.g. `"UTC"`, `"Eastern Time (US & Canada)"`, `"London"`, `"Tokyo"`) — see `references/rails-timezones.json`. Bare IANA names like `"America/New_York"` fail server validation.
- `Logic::Case.parameters.case_condition` keys are pre-normalized to `Case_1`, `Case_2`.
- `Case_Else` is emitted as a linkage, not a `case_condition` key (the fall-through is implicit).
- `For Each` linkage has the space — matches `Iterate`'s published hook.
- No `Logic::Merge` in the workflow, so the For-Each-before-Merge rule does not apply.
- All three Email/Callout branches share the same upstream (`source_task_id: 203`).
- Graph is acyclic, every task reachable from Start.

## Use Case 3 — Event-triggered payment confirmation email

**Requirement.** When a payment is processed, send a confirmation email to the account's bill-to contact.

**Design choice:** `event_trigger` on `PaymentProcessed`. Payload gives us `Data.Payment.Id` and `Data.Payment.AccountId`. We query the Account for contact info, then send the email.

```json
{
  "workflow_definition": {
    "name": "Payment Confirmation Email",
    "description": "Email customer when a payment is processed.",
    "category": "Default",
    "ui_page_roles": []
  },
  "workflow": {
    "id": 3,
    "name": "Payment Confirmation Email",
    "description": "Event-triggered on PaymentProcessed.",
    "parameters": {
      "event_triggers": ["PaymentProcessed"],
      "event_parameters": [
        {
          "eventName": "PaymentProcessed",
          "params": [
            { "object": "Payment", "key": "Id",        "value": "<Payment.Id>" },
            { "object": "Payment", "key": "AccountId", "value": "<Payment.AccountId>" },
            { "object": "Payment", "key": "Amount",    "value": "<Payment.Amount>" }
          ]
        }
      ]
    },
    "data": {},
    "type": "Workflow::Setup",
    "ondemand_trigger": false,
    "callout_trigger": false,
    "scheduled_trigger": false,
    "event_trigger": true,
    "interval": null,
    "timezone": null,
    "status": "Inactive",
    "css": { "top": "40px", "left": "35px" },
    "notifications": {},
    "call_type": "BATCH",
    "priority": "Medium",
    "delete_ttl": 30
  },
  "tasks": [
    {
      "id": 301,
      "name": "Query Account Contact",
      "parameters": {
        "fields": {
          "Account":        { "Id": "true", "Name": "true", "AccountNumber": "true" },
          "BillToContact":  { "WorkEmail": "true", "FirstName": "true", "LastName": "true" }
        },
        "where_clause": "Account.Id = '{{ Data.Payment.AccountId }}'",
        "placement": "",
        "zero_query_proceed": "false",
        "strict_variables": "true"
      },
      "action_type": "Query",
      "object": "Account",
      "object_id": null,
      "call_type": "SOAP",
      "task_id": null,
      "css": { "top": "40px", "left": "350px" },
      "concurrent_limit": 5,
      "tags": [],
      "priority": "Medium",
      "assignment": []
    },
    {
      "id": 302,
      "name": "Send Confirmation Email",
      "parameters": {
        "email": {
          "to": ["{{ Data.Account.BillToContact.WorkEmail }}"],
          "cc": [], "bcc": [],
          "from": "billing@zuora.com",
          "reply_to": "", "name": "",
          "subject": "Payment received - thank you",
          "template": "<p>Hi {{ Data.Account.BillToContact.FirstName }},</p><p>Thank you. We've received your payment of {{ Data.Payment.Amount | money }} for account {{ Data.Account.AccountNumber }}.</p><p>Regards,<br>Zuora Billing</p>",
          "attachments": { "invoices": "false" },
          "preview_only": "false",
          "disable_editor": "false"
        },
        "files": {},
        "strict_variables": "true"
      },
      "action_type": "Email",
      "object": null,
      "object_id": null,
      "call_type": "SOAP",
      "task_id": 301,
      "css": { "top": "40px", "left": "700px" },
      "concurrent_limit": 9999999,
      "tags": [],
      "priority": "Medium",
      "assignment": []
    }
  ],
  "linkages": [
    { "source_workflow_id": 3,    "source_task_id": null, "target_task_id": 301, "linkage_type": "Start" },
    { "source_workflow_id": null, "source_task_id": 301,  "target_task_id": 302, "linkage_type": "Success" }
  ]
}
```

Checklist highlights:

- `event_trigger: true`, with `event_triggers` and `event_parameters` populated.
- Minimal linear flow — simplest possible working workflow.
- `object: "Account"` satisfies `Query`'s `required_at_import`.
- Account and BillToContact fields both selected in one `Query`.

## Use Case 4 — Bill-run-completion: export invoices + items to external system

**Requirement.** After a Zuora bill run completes, export every invoice that was created during the run, fetch each invoice's line items, and POST the combined payload to `https://myexternalsystem.com/invoices`.

**Design choice:** `event_trigger` on `BillingRunCompletion` (the canonical name — natural-language requests like "BillRunCompleted" are corrected through `workflow-enums.json` -> `standard_events.$canonical_name_corrections`). `Export` invoices scoped by `BillRunId`, `Iterate` over each row, `Query` its line items, then `Callout` POST. No `Logic::Merge` because the iterator's `Complete` hook converges naturally.

**Two hard rules this example demonstrates** (both are enforced by the linter):

1. **`Iterate.object` after an `Export`/`File::*`/`Data::Link` must be the file-holder name, not the bare object.** The Iterate UI dropdown only exposes three groups and after a file-producing parent the only selectable object is the file holder (see `app/views/tasks/partials/_iterate.html.erb` lines 7-14). Runtime `Iterate#task_process` checks `self.data['Files'].keys.include?(self.object)` — a bare object like `"Invoice"` fails that check and raises *"The selected file or object 'Invoice' could not be found. Please ensure correct iterate setup."* The correct value is `"<Object>__<ExportTaskId>.csv.zip"` (or `.csv` when `zip = "false"`).
2. **`event_parameters[].value` must be either a Rails-recognised special token or a merge-field token discovered from the live notifications selections API.** `BusinessEvent` (`app/models/business_event.rb` L143-185) hard-codes these tokens: `<Event.Category>`, `<Event.Date>`, `<Event.Timestamp>`, `<Functions.Today>`, `<Tenant.ID>`, `<Tenant.Name>`. Any other token has its angle brackets (and optional `DataSource.`/`Event.` prefix) stripped and is used as a literal payload key. The canonical set of payload keys for a given event category is published per tenant at `GET {base_url}/notifications/email-templates/info/selections?category={category}` and cached in Redis under `CustomEventFields:{app_instance_id}:Entity-{entity_reference}:{category}`. The agent MUST call this endpoint — either directly with `curl` (Zuora credentials live in `~/.claude/settings.json -> env` as `ZUORA_BASE_URL` / `ZUORA_CLIENT_ID` / `ZUORA_CLIENT_SECRET` and are injected into every `Bash` invocation) or, when they are not in the shell environment, via `mcp__zuora-mcp__ask_zuora` — and pick a token from the returned `mergeFields` hash before emitting a workflow. Guessing a token is not safe because the keyspace varies by tenant and event definition.

```json
{
  "workflow_definition": {
    "name": "Bill Run Invoice Export",
    "description": "After a bill run completes, export all invoices created during the run and POST each invoice with its line items to an external system.",
    "category": "Default",
    "ui_page_roles": []
  },
  "workflow": {
    "id": 1,
    "name": "Bill Run Invoice Export",
    "description": "Event-triggered on BillingRunCompletion. Exports invoices scoped to the bill run, iterates over each invoice, queries its line items, and POSTs the combined payload to the external system.",
    "parameters": {
      "fields": [],
      "entity_name": null,
      "entity_id": null,
      "skipping_check": "db",
      "file_encryption": "false",
      "secure_error_msgs": "false",
      "show_run_prompt": null,
      "callout_response": "workflow instance",
      "event_triggers": ["BillingRunCompletion"],
      "event_parameters": [
        {
          "eventName": "BillingRunCompletion",
          "params": [
            { "object": "BillingRun", "key": "Id", "value": "<BillingRun.Id>" }
          ]
        }
      ]
    },
    "data": {},
    "type": "Workflow::Setup",
    "ondemand_trigger": false,
    "callout_trigger": false,
    "scheduled_trigger": false,
    "event_trigger": true,
    "interval": null,
    "timezone": null,
    "status": "Inactive",
    "css": { "top": "40px", "left": "35px" },
    "notifications": {
      "emails": [],
      "failure": false,
      "success": false,
      "pending": false,
      "skipped_scheduled_run": false,
      "error_ignore": ""
    },
    "call_type": "BATCH",
    "priority": "Medium",
    "delete_ttl": 30,
    "version": "0.0.1",
    "ui_pages": {},
    "solution_id": null,
    "extension_id": null,
    "zuora_org_id": null,
    "zuora_org_ids": []
  },
  "tasks": [
    {
      "id": 101,
      "name": "Export Invoices from Bill Run",
      "parameters": {
        "fields": {
          "Invoice": {
            "Id": "true",
            "InvoiceNumber": "true",
            "AccountId": "true",
            "Amount": "true",
            "Balance": "true",
            "Status": "true",
            "DueDate": "true",
            "CreatedDate": "true"
          }
        },
        "where_clause": "BillRunId = '{{ Data.BillingRun.Id }}'",
        "zip": "true",
        "encrypt": "false",
        "zero_result_stop": "false",
        "strict_variables": "true"
      },
      "action_type": "Export",
      "object": "Invoice",
      "object_id": null,
      "call_type": "SOAP",
      "task_id": null,
      "css": { "top": "40px", "left": "350px" },
      "concurrent_limit": 5,
      "tags": [],
      "priority": "Medium",
      "assignment": []
    },
    {
      "id": 102,
      "name": "Iterate Over Invoices",
      "parameters": {
        "file_type": "CSV",
        "skip_trailer": "false",
        "generate_auto_headers": "false",
        "fetched_data_is_array": "false",
        "strict_variables": "true"
      },
      "action_type": "Iterate",
      "object": "Invoice__101.csv.zip",
      "object_id": null,
      "call_type": "BATCH",
      "task_id": 101,
      "css": { "top": "40px", "left": "750px" },
      "concurrent_limit": 150,
      "tags": [],
      "priority": "Medium",
      "assignment": []
    },
    {
      "id": 103,
      "name": "Query Invoice Items",
      "parameters": {
        "fields": {
          "InvoiceItem": {
            "Id": "true",
            "InvoiceId": "true",
            "AccountId": "true",
            "ChargeName": "true",
            "ChargeAmount": "true",
            "ServiceStartDate": "true",
            "ServiceEndDate": "true"
          }
        },
        "where_clause": "InvoiceId = '{{ Data.Invoice.Id }}'",
        "placement": "",
        "zero_query_proceed": "true",
        "strict_variables": "true"
      },
      "action_type": "Query",
      "object": "InvoiceItem",
      "object_id": null,
      "call_type": "SOAP",
      "task_id": 102,
      "css": { "top": "40px", "left": "1150px" },
      "concurrent_limit": 5,
      "tags": [],
      "priority": "Medium",
      "assignment": []
    },
    {
      "id": 104,
      "name": "POST Invoice to External System",
      "parameters": {
        "url": "https://myexternalsystem.com/invoices",
        "method": "POST",
        "body_type": "raw",
        "raw_body": "{\n  \"invoice_id\": \"{{ Data.Invoice.Id }}\",\n  \"invoice_number\": \"{{ Data.Invoice.InvoiceNumber }}\",\n  \"account_id\": \"{{ Data.Invoice.AccountId }}\",\n  \"amount\": \"{{ Data.Invoice.Amount }}\",\n  \"balance\": \"{{ Data.Invoice.Balance }}\",\n  \"status\": \"{{ Data.Invoice.Status }}\",\n  \"due_date\": \"{{ Data.Invoice.DueDate }}\",\n  \"invoice_items\": {{ Data.InvoiceItem | to_json }}\n}",
        "headers": [
          { "key": "Content-Type", "value": "application/json" }
        ],
        "authorization": { "type": "none" },
        "validation": { "status_codes": ["200", "201", "202"] },
        "retry_rules": { "retry_count": "3", "retry_window": "30" },
        "strict_variables": "true",
        "disable_validation": "false"
      },
      "action_type": "Callout",
      "object": null,
      "object_id": null,
      "call_type": "SOAP",
      "task_id": 103,
      "css": { "top": "40px", "left": "1550px" },
      "concurrent_limit": 9999999,
      "tags": [],
      "priority": "Medium",
      "assignment": []
    }
  ],
  "linkages": [
    { "source_workflow_id": 1,    "source_task_id": null, "target_task_id": 101, "linkage_type": "Start" },
    { "source_workflow_id": null, "source_task_id": 101,  "target_task_id": 102, "linkage_type": "Success" },
    { "source_workflow_id": null, "source_task_id": 102,  "target_task_id": 103, "linkage_type": "For Each" },
    { "source_workflow_id": null, "source_task_id": 103,  "target_task_id": 104, "linkage_type": "Success" }
  ]
}
```

Checklist highlights:

- Canonical event name `BillingRunCompletion` (not `BillRunCompleted`); `baseObject = BillingRun`, so `Data.BillingRun.Id` is the runtime reference.
- `parameters` carries all seven always-present keys from the skeleton, plus `event_triggers` and `event_parameters` for the event style.
- Both `event_parameters` and the inner `params` are JSON arrays (not Hashes).
- `notifications` uses the fully-shaped default; an empty `{}` would also be lint-clean.
- `ui_trigger` is intentionally absent (it is not a column on the workflows table; emitting it would trigger linter rule `E119`).
- `For Each` linkage on the `Iterate` task uses the exact spelling with a space.
- No `Logic::Merge` task, so the For-Each-before-Merge rule does not apply.
- The `Callout` validates HTTP 200/201/202 with three retries, 30s window.

Provenance notes (what the generator must verify before emitting this JSON):

- **`event_parameters[0].params[0].value = "<BillingRun.Id>"`.** The agent MUST have called `GET $ZUORA_BASE_URL/notifications/email-templates/info/selections?category=<BillingRunCompletion.category>` (either directly via `curl` with the bearer token from `POST /oauth/token`, or through `mcp__zuora-mcp__ask_zuora` when the env vars are not present in the shell) and confirmed that `BillingRun.Id` is one of the keys returned in `mergeFields`. Linter rule `E177` rejects any `<BaseObject.Field>` token whose `BaseObject` does not match the event's declared `baseObject` (from `references/zuora-standard-fields.json#/$event_base_objects`). Special tokens `<Event.Category>`, `<Event.Date>`, `<Event.Timestamp>`, `<Functions.Today>`, `<Tenant.ID>`, `<Tenant.Name>` are always allowed.
- **`Export.parameters.where_clause = "BillRunId = '{{ Data.BillingRun.Id }}'"`.** `Invoice.BillRunId` must be verified against the SOAP describe for the tenant — `curl -sS "$ZUORA_BASE_URL/v1/describe/Invoice" -H "Authorization: Bearer $ACCESS_TOKEN"` is the direct path; `mcp__zuora-mcp__ask_zuora` (with `object=Invoice, context=soap`) is the fallback. The bundled catalog at `references/zuora-standard-fields.json#/objects/Invoice/fields` must list `BillRunId`, which was added specifically so this example is lint-clean. Linter rule `W177` warns if a field in a data-bearing task is absent from both the describe response and the bundled catalog.
- **`Iterate.object = "Invoice__101.csv.zip"`.** Required because the parent (task 101) is an `Export` with `zip = "true"`. If `zip = "false"` the value would be `"Invoice__101.csv"`. Linter rule `E176` will hard-fail if you set `object` to the bare `"Invoice"` string when the parent is file-producing.

## Use Case 5 — Callout with declared response schema (opaque-with-confirmation)

**Requirement.** When an invoice is posted, call an external risk-scoring API to assess fraud risk, then email the fraud team with the score, level, and reason.

**Design choice:** `event_trigger` on `InvoicePosted`. The trigger seeds `Data.Invoice.{Id, AccountId, Amount}` from the event payload. The `Callout` POSTs to the risk-scoring endpoint, redirects the response to `Data.RiskScore` via `parameters.validation.payload_location`, and **declares the expected response schema** through the linter sentinel `parameters._expected_response_schema`. The downstream `Email` task then references `Data.RiskScore.score`, `Data.RiskScore.level`, etc. without tripping `W172` (unconfirmed-opaque) — because the producing Callout's declared schema is treated by the linter as resolution.

This is the **declare-schema** protocol from Step 3e of `zuora-workflow-build/SKILL.md`. It is the recommended pattern when downstream tasks need field-level access to the response of an opaque task (`Callout`, `AsynchronousCallout`, `Logic::Lambda`, `Script::JavaScript`, `Execute::WorkflowTask`).

```json
{
  "workflow_definition": {
    "name": "Invoice Risk Assessment",
    "description": "On invoice posting, score risk via external API and email the fraud team.",
    "category": "Default",
    "ui_page_roles": []
  },
  "workflow": {
    "id": 5,
    "name": "Invoice Risk Assessment",
    "description": "Event-triggered on InvoicePosted. Calls external risk-scoring API and emails fraud team with the assessment.",
    "parameters": {
      "event_triggers": ["InvoicePosted"],
      "event_parameters": [
        {
          "eventName": "InvoicePosted",
          "params": [
            { "object": "Invoice", "key": "Id",        "value": "<Invoice.Id>" },
            { "object": "Invoice", "key": "AccountId", "value": "<Invoice.AccountId>" },
            { "object": "Invoice", "key": "Amount",    "value": "<Invoice.Amount>" }
          ]
        }
      ]
    },
    "data": {},
    "type": "Workflow::Setup",
    "ondemand_trigger": false,
    "callout_trigger": false,
    "scheduled_trigger": false,
    "event_trigger": true,
    "interval": null,
    "timezone": null,
    "status": "Inactive",
    "css": { "top": "40px", "left": "35px" },
    "notifications": {},
    "call_type": "BATCH",
    "priority": "Medium",
    "delete_ttl": 30
  },
  "tasks": [
    {
      "id": 501,
      "name": "Score Invoice Risk",
      "parameters": {
        "url": "{{ GlobalConstants.RISK_SCORE_BASE_URL }}/score",
        "method": "POST",
        "body_type": "raw",
        "raw_body": "{\n  \"invoice_id\": \"{{ Data.Invoice.Id }}\",\n  \"account_id\": \"{{ Data.Invoice.AccountId }}\",\n  \"amount\": \"{{ Data.Invoice.Amount }}\"\n}",
        "headers": [
          { "key": "Content-Type", "value": "application/json" },
          { "key": "X-API-Key",    "value": "{{ GlobalConstants.RISK_SCORE_API_KEY }}" }
        ],
        "authorization": { "type": "none" },
        "validation": {
          "status_codes": ["200"],
          "payload_location": "RiskScore"
        },
        "retry_rules": { "retry_count": "2", "retry_window": "30" },
        "strict_variables": "true",
        "_expected_response_schema": {
          "RiskScore": {
            "score": "integer 0-100",
            "level": "low | medium | high",
            "reason": "string explaining the score",
            "model_version": "semver string of the scoring model"
          }
        }
      },
      "action_type": "Callout",
      "object": null,
      "object_id": null,
      "call_type": "SOAP",
      "task_id": null,
      "css": { "top": "40px", "left": "350px" },
      "concurrent_limit": 9999999,
      "tags": [],
      "priority": "Medium",
      "assignment": []
    },
    {
      "id": 502,
      "name": "Notify Fraud Team",
      "parameters": {
        "email": {
          "to": ["fraud-review@zuora.com"],
          "cc": [], "bcc": [],
          "from": "workflow@zuora.com",
          "reply_to": "", "name": "",
          "subject": "Risk score {{ Data.RiskScore.level }} for invoice {{ Data.Invoice.Id }}",
          "template": "<p>Invoice <strong>{{ Data.Invoice.Id }}</strong> ({{ Data.Invoice.Amount | money }}) was scored <strong>{{ Data.RiskScore.score }}/100</strong> ({{ Data.RiskScore.level }}) by risk model {{ Data.RiskScore.model_version }}.</p><p>Reason: {{ Data.RiskScore.reason }}</p>",
          "attachments": { "invoices": "false" },
          "preview_only": "false",
          "disable_editor": "false"
        },
        "files": {},
        "strict_variables": "true"
      },
      "action_type": "Email",
      "object": null,
      "object_id": null,
      "call_type": "SOAP",
      "task_id": 501,
      "css": { "top": "40px", "left": "750px" },
      "concurrent_limit": 9999999,
      "tags": [],
      "priority": "Medium",
      "assignment": []
    }
  ],
  "linkages": [
    { "source_workflow_id": 5,    "source_task_id": null, "target_task_id": 501, "linkage_type": "Start" },
    { "source_workflow_id": null, "source_task_id": 501,  "target_task_id": 502, "linkage_type": "Success" }
  ]
}
```

Checklist highlights:

- `parameters.validation.payload_location: "RiskScore"` redirects the parsed Callout response from the default `Data.Callout` to `Data.RiskScore`. The data-flow walker resolves the producing scope from `data_contract.writes[].to_template = "Data.{parameters.validation.payload_location | 'Callout'}"`.
- `parameters._expected_response_schema = { RiskScore: { score, level, reason, model_version } }` declares the response shape. The linter:
  - lifts `Data.RiskScore` from "opaque + unresolved" to "opaque + resolved", clearing rule `W172` for any downstream `Data.RiskScore.*` reference;
  - records the four keys as the known field set so the schema survives in the available-data trace.
- The downstream Email references `Data.RiskScore.score`, `Data.RiskScore.level`, `Data.RiskScore.reason`, `Data.RiskScore.model_version`. None trip a warning because the schema declared every field referenced.
- The same pattern works with `parameters._opaque_trusted: "true"` instead of `_expected_response_schema` if the user prefers to opt out of field-level analysis entirely (use only when the response shape genuinely cannot be enumerated).
- Both sentinel keys (`_opaque_trusted`, `_expected_response_schema`) are free-form keys in `parameters`. Rails' Workflow runtime ignores them (the JSONB column accepts any keys); they exist solely to inform the linter / agent.

## Use Case 6 — File-name `Iterate.object` after an Export

**Requirement.** Once a month, dump every active account with a non-zero balance to a file, iterate over each row, and POST a per-account audit snapshot to an external compliance endpoint.

**Design choice:** `scheduled_trigger` on the 1st of every month at 03:00 in `Eastern Time (US & Canada)` (Rails friendly name). `Export` writes the file holder `Account__601.csv.zip` into the workflow's `Files` map. The downstream `Iterate` references that holder via the **explicit file-name form** `parameters.object = "Account__601.csv.zip"` -- not the bare object name `"Account"`.

This is the canonical pattern when you want the For-Each branch to definitively bind to the file payload (rather than to a parent's in-memory `Array<Hash>` scope), which matters when:

- Multiple parents could supply an `Array<Hash>` named `Account` and you need disambiguation.
- The file went through `File::FileOperations` (filter / merge) before iteration -- after such a step, only the file holder name is meaningful.
- You want grep-friendly self-documenting JSON: `Account__601.csv.zip` makes the data lineage explicit.

Inside the `For Each` branch, `Data.Account` rebinds to a single Hash per row (one CSV line). The downstream `Callout` reads `Data.Account.Id`, `Data.Account.AccountNumber`, etc. as scalar fields, exactly as if the source had been the object-name form. Both forms route through the same file-streaming code path (`tasks/iterate.rb`).

```json
{
  "workflow_definition": {
    "name": "Monthly Account Compliance Snapshot",
    "description": "Monthly dump of accounts with non-zero balances; POST per-account snapshot to compliance endpoint.",
    "category": "Default",
    "ui_page_roles": []
  },
  "workflow": {
    "id": 6,
    "name": "Monthly Account Compliance Snapshot",
    "description": "Scheduled on the 1st of each month at 03:00 ET. Exports active accounts with non-zero balance, iterates over the export file holder, and POSTs each account snapshot to the compliance audit endpoint.",
    "parameters": {},
    "data": {},
    "type": "Workflow::Setup",
    "ondemand_trigger": false,
    "callout_trigger": false,
    "scheduled_trigger": true,
    "event_trigger": false,
    "interval": "0 0 3 1 * *",
    "timezone": "Eastern Time (US & Canada)",
    "status": "Inactive",
    "css": { "top": "40px", "left": "35px" },
    "notifications": {},
    "call_type": "BATCH",
    "priority": "Medium",
    "delete_ttl": 30
  },
  "tasks": [
    {
      "id": 601,
      "name": "Export Active Accounts",
      "parameters": {
        "fields": {
          "Account": {
            "Id": "true",
            "AccountNumber": "true",
            "Name": "true",
            "Status": "true",
            "Currency": "true",
            "Balance": "true",
            "CreatedDate": "true"
          }
        },
        "where_clause": "Status = 'Active' AND Balance != 0",
        "zip": "true",
        "encrypt": "false",
        "zero_result_stop": "false",
        "strict_variables": "true"
      },
      "action_type": "Export",
      "object": "Account",
      "object_id": null,
      "call_type": "SOAP",
      "task_id": null,
      "css": { "top": "40px", "left": "350px" },
      "concurrent_limit": 5,
      "tags": [],
      "priority": "Medium",
      "assignment": []
    },
    {
      "id": 602,
      "name": "Iterate Over Account Export File",
      "parameters": {
        "file_type": "CSV",
        "skip_trailer": "false",
        "generate_auto_headers": "false",
        "fetched_data_is_array": "false",
        "strict_variables": "true"
      },
      "action_type": "Iterate",
      "object": "Account__601.csv.zip",
      "object_id": null,
      "call_type": "BATCH",
      "task_id": 601,
      "css": { "top": "40px", "left": "750px" },
      "concurrent_limit": 150,
      "tags": [],
      "priority": "Medium",
      "assignment": []
    },
    {
      "id": 603,
      "name": "POST Account Snapshot to Compliance",
      "parameters": {
        "url": "{{ GlobalConstants.COMPLIANCE_BASE_URL }}/snapshots",
        "method": "POST",
        "body_type": "raw",
        "raw_body": "{\n  \"account_id\":     \"{{ Data.Account.Id }}\",\n  \"account_number\": \"{{ Data.Account.AccountNumber }}\",\n  \"name\":           \"{{ Data.Account.Name }}\",\n  \"currency\":       \"{{ Data.Account.Currency }}\",\n  \"balance\":        \"{{ Data.Account.Balance }}\",\n  \"created_date\":   \"{{ Data.Account.CreatedDate }}\"\n}",
        "headers": [
          { "key": "Content-Type", "value": "application/json" },
          { "key": "X-API-Key",    "value": "{{ GlobalConstants.COMPLIANCE_API_KEY }}" }
        ],
        "authorization": { "type": "none" },
        "validation": { "status_codes": ["200", "201", "202"] },
        "retry_rules": { "retry_count": "3", "retry_window": "30" },
        "strict_variables": "true"
      },
      "action_type": "Callout",
      "object": null,
      "object_id": null,
      "call_type": "SOAP",
      "task_id": 602,
      "css": { "top": "40px", "left": "1150px" },
      "concurrent_limit": 9999999,
      "tags": [],
      "priority": "Medium",
      "assignment": []
    }
  ],
  "linkages": [
    { "source_workflow_id": 6,    "source_task_id": null, "target_task_id": 601, "linkage_type": "Start" },
    { "source_workflow_id": null, "source_task_id": 601,  "target_task_id": 602, "linkage_type": "Success" },
    { "source_workflow_id": null, "source_task_id": 602,  "target_task_id": 603, "linkage_type": "For Each" }
  ]
}
```

Checklist highlights:

- `parameters.object` on `Iterate` is the **file holder name** `"Account__601.csv.zip"`, matching the format `<Object>__<TaskId>.csv.zip` produced by an upstream `Export` (`zip: "true"`). Linter rule `E176` walks upstream and accepts this because task 601 is an `Export` whose `object` is `"Account"` and whose file holder shape matches.
- The same workflow with `parameters.object: "Account"` would also pass `E176` (object-name form). Use the file-name form when you want explicit lineage in the JSON.
- `interval: "0 0 3 1 * *"` is 6-token Rufus cron: monthly on day 1 at 03:00:00. `timezone` is the Rails friendly name `"Eastern Time (US & Canada)"`; bare IANA names like `"America/New_York"` would trip `E175`.
- The `For Each` branch (task 603) reads `Data.Account.<scalar>` -- inside the loop, `Data.Account` is a single Hash, so single-field references like `Data.Account.Id` are correct (no array-index syntax). Mistakenly writing `Data.Account[0].Id` inside the loop would trip `W173`.
- No `Logic::Merge` -- the iterator's implicit `Complete` hook converges the path naturally.

## Cross-references

- Canonical composition skeleton: `workflow-skeleton.json`
- Per-task templates and rules: `workflow-task-templates.json`
- Enums (action_types, call_types): `workflow-enums.json`
- Linkage and trigger reference: `workflow-triggers-and-linkages.md`
- Task catalog: `workflow-task-catalog.md`
- Liquid scopes: `workflow-liquid.md`
- Linter script (validates all three examples): `scripts/lint-workflow-json.js`
