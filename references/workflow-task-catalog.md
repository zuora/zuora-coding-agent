# Zuora Workflow Task Catalog

Canonical list of Zuora Workflow `action_type` values (71 total). This is a narrative reference; the machine-readable source of truth for composing tasks is `workflow-task-templates.json`, which pairs every entry below with a ready-to-use JSON template, parameter rules, enums, and `required_at_import` columns.

Distilled from `Task.action_type` in `~/Workspace/workflow/rails/app/models/task.rb:636-681`.

When picking an `action_type`, follow this order:

1. Scan the relevant category below.
2. Read the matching entry in `workflow-task-templates.json` for the exact JSON shape.
3. Read the matching entry in `workflow-triggers-and-linkages.md` for the allowed `linkage_type` hooks.
4. When in doubt, prefer the most common Tier 1 task; do not invent an `action_type`.

## Tier 1 — the 80% cases

These thirteen action types cover the vast majority of production workflows. Know them cold.

| Action type   | Purpose                                                                        |
| ------------- | ------------------------------------------------------------------------------ |
| `Query`       | SOAP Query a Zuora object (up to 2000 rows) into `Data.<object>`.              |
| `Export`      | SOAP bulk export (> 2000 rows) emitting a CSV file.                            |
| `Iterate`     | Fan out over a collection with a `For Each` hook.                              |
| `If`          | Binary branch on a Liquid boolean expression (`True` / `False` hooks).         |
| `Logic::Case` | Multi-way branch keyed by a Liquid clause (`Case_1`, `Case_2`, …, `Case_Else`).|
| `Logic::Liquid` | Transform or compute values into `Data.Liquid` or `Data.<placement>`.        |
| `Logic::Merge`| Collapse parallel branches back into a single path after fan-out.              |
| `Callout`     | Sync HTTP callout to any URL. The workhorse for external integrations.         |
| `Email`       | Liquid-templated email via the workflow notification service.                  |
| `Update`      | SOAP update a Zuora object by `object_id`.                                     |
| `Create`      | SOAP create a Zuora object.                                                    |
| `Delete`      | SOAP delete a Zuora object by `object_id`.                                     |
| `Delay`       | Sleep for N seconds, or until a specific absolute time.                        |

## Tier 2 — specialist tasks by category

### Retrieve (data in)

- `GraphQuery` — GraphQL queries with variables (best for joined or nested reads).
- `Data::Aqua` — Async Queuing API (AQuA) stateful/stateless extracts.
- `Data::BillingPreviewRun` — run a billing preview against accounts.
- `Data::Link` — join two Data collections.
- `Data::Warehouse` — run SQL against the Zuora Data Warehouse.

### Logic / Transform

- `Logic::Lambda` — invoke AWS Lambda synchronously.
- `Logic::CSVTranslator` — filter/merge/sort CSV, or convert to XML / JSON.
- `Logic::XMLTransform` — XSLT template transforms (CSV / XML / TXT / HTML).
- `Logic::JSONTransform` — JSONata or CSV-liquid transforms.
- `Logic::ResponseFormatter` — format SYNC-mode UI responses (UI / UIACTION / REALTIME / SYNC_UI_ACTION / DATASTREAM workflows only).
- `Script::JavaScript` — arbitrary Node.js code blocks.

### CRUD

- `Create`, `Update`, `Delete` — standard SOAP object CRUD (Tier 1).

### Custom Objects

- `CustomObject::Create`, `CustomObject::Update`, `CustomObject::Delete`, `CustomObject::Query`.

### Amendments

- `NewProduct`, `RemoveProduct`, `Suspend`, `Resume`, `Cancel` — subscription amendments. Each requires `object_id` = subscription id.

### Billing

- `Billing::BillRun` — create / batch / replicate a bill run.
- `InvoiceGenerate` — SOAP InvoiceGenerate for a single account.
- `WriteOff` — settlement or amendment-based invoice write-off.
- `Billing::ReverseInvoice` — reverse an invoice.
- `Billing::CurrencyConversion` — pull FX rates and rewrite currency fields.
- `Billing::CustomBillingDocument` — render a custom billing document from a PDF template.

### Payment

- `Payment::PaymentRun` — create/update/get/delete a payment run.
- `Payment::GatewayReconciliation` — settle/reverse/reject gateway records.

### Usage

- `Usage::ImportUsage` — bulk-import usage data from a file label.

### Notifications / Messaging

- `Email` — primary (Tier 1).
- `Callout` — primary (Tier 1).
- `AsynchronousCallout` — fire-and-poll for long-running endpoints.
- `Notifications::SMS` — send SMS via the notification service.
- `Notifications::Kafka` — publish to an internal Kafka topic (internal access only).

### File / Attachments

- `Attachment` — attach a file to a Zuora object (`object` + `object_id` required).
- `File::CustomPDF::CustomDocument` — render a PDF from a template.
- `File::DownloadFile` — download file from Zuora or an external URL.
- `File::ZuoraImport` — legacy bulk-import API.
- `File::FileOperations` — Zip / Unzip / Encrypt / Decrypt / SplitCSV / PDF / ZipFiles.
- `File::FileStreamingUpload` — stream file to S3.
- `File::BulkDataLoader` — bulk-data-loader job (insert / update / upsert / delete).

### Reporting

- `Reporting::RunReport` — execute a Zuora Report (`object_id` = report id).
- `Reporting::OracleFusionReport` — run an Oracle Fusion report.

### Upload / Download

- `Upload::FTP`, `Upload::SFTP`, `Upload::S3` — upload file collections to the matching transport.
- `Download::SFTP`, `Download::S3` — download remote files.

### UI (only inside UI / UIACTION / SYNC_UI_ACTION workflows)

- `UI::Page` — render a named page; each route becomes a `Page:<route>` hook.
- `UI::Stop` — halt an interactive workflow.
- `UI::WebShare` — web-share action; exposes `Webshare:<route>`, `Upload`, `Timeout`, `Success`, `Failure`.

### Execute / Manual / Time

- `Execute::WorkflowTask` — invoke another workflow as a subroutine.
- `Approval` — human approval step with `Approve`, `Reject`, `Failure` hooks.
- `Delay` — sleep (Tier 1).

### Usage Mediation (lowercase hooks!)

- `UsageMediation::Source`
- `UsageMediation::Watermark`
- `UsageMediation::Filter`
- `UsageMediation::Map`
- `UsageMediation::Group`
- `UsageMediation::Sink`
- `Mediation::SendEvents` — downstream dispatch.

All mediation tasks use the hooks `next` and `error` (lowercase) instead of `Success` / `Failure`. The linter understands this exception.

## Format pitfalls

The Rails backend silently accepts many near-valid JSONs but fails at runtime. The linter (see `scripts/lint-workflow-json.js`) catches these explicitly.

1. **Booleans as strings.** Every `strict_variables`, `disable_validation`, `preview_only`, `encrypt`, etc. parameter is parsed with `to_bool`. Always emit the string `"true"` or `"false"`, never JSON `true` / `false`.

2. **`parameters: {}` is required on every task.** `Task.import` calls `parameters.merge!` — a missing or null `parameters` raises `NoMethodError` on import.

3. **`required_at_import` columns are validated on import.** These are top-level task attributes (not inside `parameters`) backed by ActiveRecord `validates :column, presence: true`. Examples: `Update` needs `object` and `object_id`; `Query` needs `object`. Consult `workflow-task-templates.json` → `required_at_import` for the exact list per `action_type`.

4. **`Logic::Case` keys must be `Case_1`, `Case_2`, …, `Case_Else`.** Rails renumbers non-canonical keys in `before_save` and destroys any linkage whose `linkage_type` doesn't survive the rename. The composer pre-normalizes these keys so the rename is a no-op.

5. **`Iterate` hook name is `For Each` (with the space).** Not `Iterate`, not `ForEach`, not `for_each`. Same goes for `Complete` on the completion hook.

6. **Usage mediation hooks are lowercase (`next`, `error`).**

7. **`linkage_type` is not server-validated against source-task hooks.** The backend does not check that a `Success` linkage actually emanates from a task that publishes `Success`. The linter is the only line of defense.

8. **For-Each / Merge rule.** No `For Each` linkage may sit on any path from the workflow start to a `Logic::Merge` task. The server DFS (`Linkage#avoid_for_each_linkage_before_merge_task`) catches it at save time but is slow to reproduce; the linter does a cheap path-substring check.

9. **`workflow.type` must be the literal string `"Workflow::Setup"`.** The server overrides this anyway, but writing it correctly keeps the file diff-stable and matches `Workflow::Setup#export` output.

10. **Status-code arrays on callouts are arrays of strings.** `"status_codes": ["200"]`, not `"status_codes": [200]`.

11. **Non-empty `tasks` and `linkages`.** Import rejects payloads whose `tasks` or `linkages` arrays are empty, even if the workflow is meant to be a placeholder.

12. **Start linkage.** Every workflow needs exactly one linkage where `linkage_type = "Start"`, `source_workflow_id = workflow.id`, `source_task_id = null`, and `target_task_id` points at the entry task.

## Cross-references

- Linkages, triggers, call types: `workflow-triggers-and-linkages.md`
- Liquid scopes and filters: `workflow-liquid.md`
- Three end-to-end annotated examples: `workflow-examples.md`
- Composition algorithm and composer contract: `workflow-patterns.md`
- Machine-readable templates: `workflow-task-templates.json`
- Machine-readable enums: `workflow-enums.json`
- Canonical empty envelope: `workflow-skeleton.json`
