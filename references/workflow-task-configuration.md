# Zuora Workflow Task Configuration Reference

**What this is.** A per-task walkthrough of how each `parameters.*` field flows from the Rails UI partial -> the Rails controller's strong-params filter -> the model's `task_setup_validation` and `task_process` runtime. Tier-1 + common-Tier-2 task types are documented here. The machine-readable counterpart lives in `references/workflow-task-templates.json` under each task's `configuration_contract` block; this file is the human-readable narrative.

**Why it exists.** `Task.import` runs with `validate: false` (and `tasks_controller.rb` permits a different subset of keys per `action_type`), so the schema enforced by the UI is the *only* schema enforced before runtime. The composer/build skill needs to know:

1. Which fields a real user of the Workflow UI is forced to fill in.
2. Which fields are user-input vs. dropdowns sourced from the upstream task's `data_structure` / `object_structure`.
3. Which fields require an authenticated describe call against Zuora (`Export`, `Query`, `Create`, `Update`, `CustomObject::Query`).
4. Which fields are conditional (visible/required only when another sibling parameter has a particular value).
5. Which fields the controller silently drops (and therefore must NOT appear in import JSON, even if you can imagine a use for them).

When the build skill composes a task body, it uses these contracts to (a) only emit permitted fields, (b) prompt the user (or describe Zuora) for fields whose `source` is `user-input` / `describe-call`, and (c) skip fields whose `visible_when` predicate evaluates false against sibling parameters.

The new linter rules `W177` (undeclared describe field) and `W178` (UI-only parameter leaked into import) consult this contract.

## Format per task

Each task section follows the same shape:

- **Purpose.** One-line summary of what the task does at runtime.
- **UI partial.** Path under `workflow/rails/app/views/tasks/partials/`.
- **Controller permit.** The `case` branch in `workflow/rails/app/controllers/tasks_controller.rb` -- exactly which top-level columns and `parameters.*` keys are accepted.
- **Model validation.** Validators / `task_setup_validation` rules from `workflow/rails/app/models/tasks/<file>.rb`.
- **`task_process` notes.** Mentioned only when the runtime rewrites or reads parameters in a non-obvious way.
- **Field-by-field table.** One row per parameter that the UI lets the user touch. Columns: `field`, `source`, `options_source`, `required/visible when`, `default`, `controller_permit`, `notes`.
- **Common gotchas.** Cross-field rules, deprecated keys, layout pitfalls.

Source-of-truth references for every section:

- UI partial: `workflow/rails/app/views/tasks/partials/_<task>.html.erb` (and `_<task>_<sub>.html.erb` shared partials).
- Controller permit: `workflow/rails/app/controllers/tasks_controller.rb`. The relevant `case action_type` branches start around L597 and run through L805. The fall-through branch (L801-802) accepts `parameters` as an opaque hash for action types not explicitly listed -- the contracts here flag every key that is silently merged in via that fall-through.
- Model: `workflow/rails/app/models/tasks/<file>.rb`. Most tasks subclass `Task` and override `task_process`. `task_setup_validation` is bypassed by `Task.import` but enforced when saving from the UI.

The `data_contract` blocks in `workflow-task-templates.json` (covered separately in `references/workflow-data-flow.md`) describe what each task **writes** at runtime; the configuration contracts here describe what each task **reads** from its own `parameters`.

---

## Tier 1 -- data selection and movement (Batch A)

### Export

**Purpose.** Stream a SOAP `query` for one Zuora object into a CSV file (optionally zipped/encrypted). Downstream `Iterate(object=<file_holder_name>)` consumes the rows.

**UI partial.** `app/views/tasks/partials/_export.html.erb` (object dropdown comes from the shared `partials/_object_id_type.html.erb` L9-12).

**Controller permit.** Falls through to the generic `else` branch in `tasks_controller.rb` L800-802. The controller permits `parameters` as an opaque hash, so per-key validation comes from the UI partial and the model. Top-level `object` is permitted via `common_params` (L585).

**Model validation (`app/models/tasks/export.rb`).**

- L2: `validates :object, presence: true`.
- L4-15 `task_setup_validation`: at least one selected `(Object, Field)` pair; `delay` <= 60 (L13).
- L169-194 `export_test`: live SOAP query test at save; **skipped** on `Task.import` (`validate: false`).

**`task_process` notes.** L218-226 builds the ZOQL string `Select <selected_fields> From <object> [Where <parsed_where_clause>]`. Selected aggregations (`Min`/`Max`/`Count`/`Sum`/`Average`) wrap the column. `parameters.fields` shape is `{<Object>: {<FieldName>: "true" | "Min" | "Max" | "Count" | "Sum" | "Average"}}`. L141 checks `zero_result_stop`. L42 sleeps `parameters.fetch("delay", "60").to_i` seconds.

**Field-by-field.**

| Field | Source | Options source / format | Required when | Default | Notes |
| --- | --- | --- | --- | --- | --- |
| `object` | `describe-call` | `@appinstance.describe_helper(...).keys` filtered by `_object_id_type.html.erb` L9-12 | always | -- | Composer must run the describe helper / `mcp__zuora-mcp` describe before guessing. |
| `parameters.fields` | `describe-call` | `describe_helper(object:, entity_id:).select { |_, v| v[:selectable] == 'true' && v[:context].include?('export') }` (`_export.html.erb` L22) | at least one entry | `{}` | Per-field value is a string: `"true"` for plain select, or one of `"Min"`, `"Max"`, `"Count"`, `"Sum"`, `"Average"`. `Sum`/`Average` only apply to numeric fields (L59). |
| `parameters.where_clause` | `code-editor` | -- | optional | `""` | ZOQL filter; do **not** include the keyword `Where` -- model prepends it. Liquid is evaluated. |
| `parameters.delay` | `user-input` (number) | 0..60 (`_export.html.erb` L192) | optional | `0` | Seconds to wait before issuing the SOAP query (data-source replication delay). |
| `parameters.zip` | boolean-string checkbox | `"true"` / `"false"` | optional | `"true"` | When `"true"`, output filename is `*.csv.zip` (export.rb L229). |
| `parameters.encrypt` | boolean-string checkbox | `"true"` / `"false"` | optional | `"false"` | Asks Zuora to encrypt the export. |
| `parameters.zero_result_stop` | boolean-string checkbox | `"true"` / `"false"` | optional | `"false"` | Halts downstream tasks when the export returned 0 rows (export.rb L141). |

**Common gotchas.**

- Use `Query`, not `Export`, if the next task needs direct `Data.<Object>.<Field>` variables such as `Data.RatePlan.SubscriptionId`. `Export` does not populate `Data.<Object>` directly; it writes file/reference metadata, and row fields are available only after an `Iterate` task consumes the export file holder.
- The downstream `Iterate.object` should be the *file* (e.g. `Invoice__1.csv.zip`), not the bare object name. Picking the bare object name iterates `Data.Export.<object>` which is the file-reference object, not the row Array.
- `parameters.fields` keys must use the canonical SOAP object name (case-sensitive). A typo silently filters down to an empty selection.

### Query

**Purpose.** Synchronous SOAP `query` (max 2000 rows) returning a `Data.<placement|object>` Array<Hash>.

**UI partial.** `app/views/tasks/partials/_query.html.erb` (object dropdown shared via `partials/_object_id_type.html.erb`).

**Controller permit.** Generic `else` branch (`tasks_controller.rb` L800-802). `parameters` accepted as opaque hash; `object` via `common_params`.

**Model validation (`app/models/tasks/query.rb`).**

- L2: `validates :object, presence: true`.
- L4-9 `task_setup_validation`: at least one selected field.
- `query_test` at save (live tenant); skipped on `Task.import`.

**`task_process` notes.** L33 builds `Select <fields> From <object> [Where <parsed_where_clause>]`. L29 caps `batch_size` at 2000. Each row becomes a Hash keyed by the selected field names. `payload_location` (L88-90) defaults to `self.object` when `parameters.placement` is blank.

**Field-by-field.**

| Field | Source | Options source / format | Required when | Default | Notes |
| --- | --- | --- | --- | --- | --- |
| `object` | `describe-call` | `describe_helper(...).keys` (Query path of `_object_id_type.html.erb` L9-11) | always | -- | Composer must describe before populating. |
| `parameters.fields` | `describe-call` | `describe_helper(object:, entity_id:).select { |_, v| v[:selectable] == 'true' && v[:context].include?('select') }` (`_query.html.erb` L18) | at least one entry | `{}` | Each value is the literal string `"true"`. |
| `parameters.where_clause` | `code-editor` | -- | optional | `""` | ZOQL filter. Liquid-evaluated. Do not include the `Where` keyword. |
| `parameters.placement` | `user-input` | free-form string | optional | `""` (resolves to `self.object`) | Use to disambiguate two Query tasks on the same object. Downstream Liquid must reference `Data.<placement>`. |
| `parameters.batch_size` | `user-input` (number) | int <= 2000 (capped) | optional | `2000` | For more than 2000 rows use `Export`. |
| `parameters.zero_query_proceed` | boolean-string checkbox | `"true"` / `"false"` | optional | `"true"` | When `"false"`, halts the workflow if Query returned 0 rows. |

**Common gotchas.**

- If you set `placement`, every downstream `{{Data.<object>...}}` reference must be rewritten to `{{Data.<placement>...}}`. The linter cross-checks this.
- `Query` returns the same field shape as `Export`, but the upstream `data_contract.predictability` differs (`deterministic` vs `semi-deterministic`).
- `parameters.where_clause` fields must exist on the described Query object. If the business requirement needs a field that Object Query does not expose, such as filtering `Subscription` directly by `InvoiceScheduleId`, do not build a `Query` task with that unsupported predicate; use a supported API/Data::Link path or ask for the supported relationship. The linter reports this as `W177`.

### Iterate

**Purpose.** Loop over an Array<Hash>, file rows, or custom Liquid array; emit one `For Each` linkage per row (or chunk).

**UI partial.** `app/views/tasks/partials/_iterate.html.erb`.

**Controller permit.** Generic `else` branch (`tasks_controller.rb` L800-802). `parameters` accepted as opaque hash; `object` via `common_params`.

**Model validation (`app/models/tasks/iterate.rb`).**

- L4: `validates :object, presence: true`.
- L99-194 `task_setup_validation` -> `validate_object` classifies the `object` value into one of `:liquid`, `:flash`, `:query`, `:export`, `:billing_preview`, `:custom_file`, `:file_operations`, `:report`, `:zuora_import`, `:other`, `:fix_length`, `:json_file` based on the upstream task's `action_type` and `object_structure` entry. Errors when no upstream producer exists, the scope is unknown, or the shape is wrong.

**`task_process` notes.** L196+ dispatches by classification. File modes (`:export`, `:custom_file`, `:file_operations`) stream the file row-by-row honoring `parameters.skip_headers`, `csv_header_filter`, `generate_auto_headers`, encoding, and FIXED-width offsets. `:query` / `:other` walk the parent's Array<Hash> directly. `data_structure` (L605-695) overrides downstream visibility so that inside a `For Each` branch `Data.{object}` resolves to a single Hash (or an Array of length `chunk_size` when `chunk_size > 1`).

**Field-by-field.**

| Field | Source | Options source / format | Required when | Default | Notes |
| --- | --- | --- | --- | --- | --- |
| `object` | `dropdown-from-parent-task` | `iterate.rb#objects` (L740-841): walks the parent task's `data_structure` + Files entries + literal `'CUSTOM LIQUID'` | always | -- | After an `Export`, picks should be the file_holder_name (e.g. `Invoice__1.csv.zip`), not the bare object name. |
| `parameters.iteration_type` | `dropdown-static` | `["Default", "Unique-Field"]` (`_iterate.html.erb` L43-49) | optional | `"Default"` | `Unique-Field` requires `iteration_field`; one branch per distinct value. |
| `parameters.iteration_field` | `user-input` | column name | when `iteration_type == 'Unique-Field'` | -- | -- |
| `parameters.chunk_size` | `user-input` (number) | 1..`appinstance.limits['chunking']` (default 2000) | optional | `1` | When >1, the branch sees `Data.{object}` as `Array<Hash>`. |
| `parameters.liquid_statement` | `code-editor` | Liquid expression yielding a JSON Array | when `object == 'CUSTOM LIQUID'` | -- | -- |
| `parameters.file_type` | `dropdown-static` | `["CSV", "FIXED"]` (`_iterate.html.erb` L101) | when iterating a file | `"CSV"` | -- |
| `parameters.skip_headers` | boolean-string OR int | -- | optional | `"false"` | UI accepts checkbox or numeric (`N` lines). |
| `parameters.skip_trailer` | boolean-string checkbox | -- | optional | `"false"` | -- |
| `parameters.csv_header_filter` | `user-input` | comma-separated column list | optional (CSV) | -- | Drops other columns before iteration. |
| `parameters.generate_auto_headers` | boolean-string checkbox | -- | optional (CSV) | `"false"` | Synthesizes `col_1`, `col_2`, ... when CSV has no header row. |
| `parameters.encoding` | `user-input` | encoding name | optional (FIXED) | `"UTF-8"` | -- |
| `parameters.skip_from_beginning` | `user-input` (number) | -- | optional (FIXED) | `0` | -- |
| `parameters.skip_from_bottom` | `user-input` (number) | -- | optional (FIXED) | `0` | -- |
| `parameters.input_constants_form` | `form-array` | array of `{name, start, length}` | when `file_type == 'FIXED'` | `[]` | Defines fixed-width column slices. |

**Common gotchas.**

- "After an Export, iterate on the *file*" -- the dropdown shows both the file (`Invoice__1.csv.zip`) and the bare object (`Invoice`), but only the file form gives row-level Liquid for downstream tasks.
- `CUSTOM LIQUID` requires `parameters.liquid_statement`. The earlier name `parameters.custom_liquid` is **not** valid -- the model reads `liquid_statement` (see `iterate.rb` Liquid branch).
- `chunk_size > 1` changes the inner-branch shape from a Hash to an Array<Hash>; downstream Liquid must use a `{% for row in Data.<object> %}` loop instead of `Data.<object>.<Field>`.
- Hook is `Complete`, not `Iterate` -- `Iterate` is the *scope* name only. Linter `W170` flags the typo.

### Delete

**Purpose.** SOAP `delete` of one Zuora record by Id.

**UI partial.** `app/views/tasks/partials/_delete.html.erb` (renders shared `partials/_object_id_type.html.erb`).

**Controller permit.** Generic `else` branch (`tasks_controller.rb` L800-802). `object` and `object_id` permitted via `common_params`; `parameters` is opaque.

**Model validation (`app/models/tasks/delete.rb`).**

- L2: `validates :object, presence: true`.
- L3: `validates :object_id, presence: true`.
- No `task_setup_validation` -- the SOAP `delete` is exercised at runtime, not save.

**`task_process` notes.** L9-37: parses `object_id_parsed` (Liquid), issues SOAP `delete` with `[object_id_parsed]`, records the response and any per-row errors. **No new keys are written to `Data`.** When `Data.<object>` was a singular Hash whose Id matched the deleted record, that Hash is unbound; otherwise, no change.

**Field-by-field.**

| Field | Source | Options source / format | Required when | Default | Notes |
| --- | --- | --- | --- | --- | --- |
| `object` | `describe-call` | `describe_helper(...).keys` filtered (`_object_id_type.html.erb` L9-11) | always | -- | Composer must describe before guessing. |
| `object_id` | `user-input` or Liquid | `accessible_payload` dropdown (`_object_id_type.html.erb` L26) | always | -- | Liquid like `{{Data.Account.Id}}` is supported and cross-checked by the linter. |

**Common gotchas.**

- `Delete` does not produce downstream data; treat it as a sink. Subsequent tasks must not assume `Data.<object>.Id` still resolves.

### File::FileOperations

**Purpose.** A single task that performs one of eight file-level operations (zip, unzip, encrypt, decrypt, multi-file zip, attach XML to PDF, generate CSV from input files, generate PDF from Liquid HTML).

**UI partial.** `app/views/tasks/partials/file/_file_operations.html.erb`.

**Controller permit.** Generic `else` branch (`tasks_controller.rb` L800-802). `parameters` opaque; `object` via `common_params`.

**Model validation (`app/models/tasks/file/file_operations.rb`).**

- L19-69 `task_setup_validation` requires `parameters.action`. Per action it then requires:

  - `Zip`, `Unzip`: `object`.
  - `FileEncryption`: `object`, `public_key`, `encrypted_filename`.
  - `FileDecryption`: `object`, `private_key`, `passphrase`, `decrypted_filename`.
  - `CSVCreation`: `csv_filename`, `field_name`, `columns`.
  - `PDFCreation`: `pdf_filename`, `pdf_content`.
  - `ZipFiles`: `filename_regex`, `zipped_filename`.
  - `AttachXMLtoPDF`: `object`, `xml_file`, `attached_filename`.

**`task_process` notes.** Dispatches by `parameters.action` and writes the resulting blob(s) to `Data.Files` keyed by the action-specific filename parameter (`zipped_filename`, `encrypted_filename`, `decrypted_filename`, `csv_filename`, `pdf_filename`, `attached_filename`). The UI auto-submits when `parameters.action` changes, so the rest of the field set is always coherent with the chosen action.

**Field-by-field.**

| Field | Source | Options source / format | Required when | Default | Notes |
| --- | --- | --- | --- | --- | --- |
| `parameters.action` | `dropdown-static` | `["Zip", "Unzip", "CSVCreation", "PDFCreation", "FileEncryption", "FileDecryption", "ZipFiles", "AttachXMLtoPDF"]` | always | -- | Action labels in the UI use spaces (`"Zip File"`, `"CSV Creation"`, ...) but the persisted value is the right-hand identifier. |
| `object` | `dropdown-from-parent-task` | `f.object.setup_file_list` (`_file_operations.html.erb` L21-23) | when `action in [Zip, Unzip, FileEncryption, FileDecryption, AttachXMLtoPDF]` | -- | -- |
| `parameters.encrypted_filename` | `user-input` | -- | when `action == 'FileEncryption'` | -- | -- |
| `parameters.public_key` | `user-input-textarea` | PEM | when `action == 'FileEncryption'` (also accepted for `FileDecryption` for signature verification) | -- | -- |
| `parameters.signer` | `user-input` | -- | optional (FileEncryption) | -- | -- |
| `parameters.signer_passphrase` | `user-input` | -- | optional (FileEncryption) | -- | -- |
| `parameters.signer_private_key` | `user-input-textarea` | PEM | optional (FileEncryption) | -- | -- |
| `parameters.decrypted_filename` | `user-input` | -- | when `action == 'FileDecryption'` | -- | -- |
| `parameters.private_key` | `user-input-textarea` | PEM | when `action == 'FileDecryption'` | -- | -- |
| `parameters.passphrase` | `user-input` | -- | when `action == 'FileDecryption'` | -- | -- |
| `parameters.signer_public_key` | `user-input-textarea` | PEM | optional (FileDecryption) | -- | -- |
| `parameters.pdf_filename` | `user-input` | -- | when `action == 'PDFCreation'` | -- | -- |
| `parameters.pdf_content` | `code-editor` | HTML + Liquid | when `action == 'PDFCreation'` | -- | -- |
| `parameters.csv_filename` | `user-input` | -- | when `action == 'CSVCreation'` | -- | -- |
| `parameters.field_name` | `form-array` | array of column header strings (`parameters[field_name][]`) | when `action == 'CSVCreation'` | -- | -- |
| `parameters.columns` | `form-matrix` | `parameters[columns][<file_idx>][]` -> source-column index per output column | when `action == 'CSVCreation'` | -- | -- |
| `parameters.filename_regex` | `user-input` | regex | when `action == 'ZipFiles'` | -- | UI surfaces the 10,000-file soft cap. |
| `parameters.zipped_filename` | `user-input` | -- | when `action == 'ZipFiles'` | -- | -- |
| `parameters.xml_file` | `dropdown-from-parent-task` | same `setup_file_list` as `object` | when `action == 'AttachXMLtoPDF'` | -- | -- |
| `parameters.attached_filename` | `user-input` | -- | when `action == 'AttachXMLtoPDF'` | -- | Name the XML attachment will have inside the PDF. |

**Common gotchas.**

- Old `param_enums` documented `["Zip", "Unzip", "Encrypt", "Decrypt", "SplitCSV", "PDF", "ZipFiles"]`; that list is **wrong**. The real persisted action values are the eight identifiers above (`Encrypt` -> `FileEncryption`, `Decrypt` -> `FileDecryption`, `SplitCSV` -> `CSVCreation`, `PDF` -> `PDFCreation`, plus the new `AttachXMLtoPDF`).
- `CSVCreation` does not consume an `object` -- it consumes the *list* of upstream files (`f.object.setup_file_list`) and maps columns from each into the new CSV. The `field_name` array is the new CSV's headers and the `columns` matrix is `field_name.length` columns wide times `setup_file_list.length` rows tall.
- The output filename appears under `Data.Files.<filename>`. Downstream `Iterate(object="<filename>")` requires the same string.

## Tier 1 -- writes and integrations (Batch B)

### Create

**Purpose.** SOAP `create` of one record on a Zuora object; downstream tasks can read the new Hash (with `Id`) at `Data.<object>`.

**UI partial.** `app/views/tasks/partials/_create.html.erb` (object dropdown via `partials/_object_id_type.html.erb`).

**Controller permit.** Generic `else` branch (`tasks_controller.rb` L800-802). `parameters` accepted as opaque; `object` via `common_params`.

**Model validation (`app/models/tasks/create.rb`).**

- L2: `validates :object, presence: true`.
- L4-10 `task_setup_validation`: requires at least 1 entry under `parameters.fields[<self.object>]`.

**`task_process` notes.** L12-37 emits one SOAP `create` with the (key, value) pairs under `parameters.fields[<object>]` (each value Liquid-evaluated). The returned record + `Id` is merged via `write_data` into `Data.<object>`. `data_structure` (L39-43) advertises the new field set + `Id` to downstream tasks, so Liquid like `{{Data.<object>.Id}}` is statically valid in subsequent tasks.

**Field-by-field.**

| Field | Source | Options source / format | Required when | Default | Notes |
| --- | --- | --- | --- | --- | --- |
| `object` | `describe-call` | `describe_helper(...).keys` filtered by Create-specific exclusions in `_object_id_type.html.erb` L9-14 | always | -- | Excludes `Subscription`, `Invoice`, `InvoiceItem`, `TaxationItem`, `RatePlanCharge`, `RatePlan`, `ProductRatePlanChargeTier`, `JournalRun`, `RatePlanChargeTier`, `Order`, `OrderAction`, `ProcessedUsage` (those are managed by Order/Amendment APIs). |
| `parameters.fields` | `describe-call` (selectable list) + `user-input` (per-field value) | `describe_helper(object:, entity_id:).select { |_, v| v[:context].include?('soap') }` (`_create.html.erb` L7); fields whose `v[:createable]` is true are auto-prefilled when required | at least one entry | `{}` | Shape: `{<Object>: {<FieldName>: <value or Liquid>}}`. Values are the literal value to write -- **not** booleans like Query/Export. |

**Common gotchas.**

- The UI explicitly warns when a chosen field isn't `createable` per describe but still allows it. The composer should mirror that judgment: if describe says `createable: false`, prefer not to set the field.
- `Id` is auto-assigned by Zuora; do not set it in `parameters.fields`.

### Update

**Purpose.** SOAP `update` of one record (or fan-out across an iterated Array<Hash>) on a Zuora object.

**UI partial.** `app/views/tasks/partials/_update.html.erb` (object/object_id via `partials/_object_id_type.html.erb`).

**Controller permit.** Generic `else` branch (`tasks_controller.rb` L800-802). `parameters` accepted as opaque; `object` and `object_id` via `common_params`.

**Model validation (`app/models/tasks/update.rb`).**

- L2: `validates :object, presence: true`.
- L3: `validates :object_id, presence: true`.
- L9-15 `task_setup_validation`: requires at least 1 entry under `parameters.fields[<self.object>]`.
- L144-146 `object_id_parsed`: parsed Id must be 32 chars at runtime.

**`task_process` notes.** L29-36 chooses `single_object` vs `multiple_objects` based on whether `object_id` contains the literal `[*]`. `multiple_objects` (L38-107) walks `Data.<iterated_object>[]` and issues one SOAP `update` per row, persisting `success_objects` in `transient_fields` to support resume. Both paths `write_data` the updated Hash back to `Data.<object>`.

**Field-by-field.**

| Field | Source | Options source / format | Required when | Default | Notes |
| --- | --- | --- | --- | --- | --- |
| `object` | `describe-call` | `describe_helper(...).keys` filtered by `_object_id_type.html.erb` L9-12 | always | -- | -- |
| `object_id` | `user-input-or-liquid` | `accessible_payload` dropdown (`_object_id_type.html.erb` L26) | always | -- | Supports `[*]` to fan out across an upstream Array<Hash>. The model walks `Data.<iterated_object>[]` and substitutes the index per call. |
| `parameters.fields` | `describe-call` (selectable list) + `user-input` (per-field value) | `describe_helper(object:).select { |_, v| v[:updateable] == 'true' && v[:context].include?('soap') }` (`_update.html.erb` L7) | at least one entry | `{}` | Special key `fieldsToNull` is an `Array<String>` telling Zuora to NULL those fields. Other entries are field name -> value (or Liquid). |

**Common gotchas.**

- `object_id` with `[*]` triggers fan-out. The portion before `[*]` is treated as a Liquid path into `Data` (e.g. `Data.Subscription[*].Id`), and the model derives the `iterated_object` (`Subscription`) from the substring before `[*]`. If that scope is not bound, `task_process` raises `Object '...' not found in data payload.`
- `fieldsToNull` is the only allowed nested array under `parameters.fields[<object>]`; other arrays will be SOAP-encoded as a single concatenated string.
- Do not emit one `Update` task per field for the same record. A single `Update` task sends every key under `parameters.fields[<object>]` in one SOAP update, so changes to the same object record should be consolidated into one object update unless independent retry/failure behavior or an intermediate validation step is required. ProductRatePlanCharge (PRPC) changes such as `Name`, `AccountingCode`, and `TaxCode` are one common example. The linter flags adjacent same-record per-field updates as `W183`.
- **`Subscription.PaymentTerm` and Flexible Billing:** On tenants where Flexible Billing is enabled, updating `PaymentTerm` at the subscription level via the SOAP `Update` task may not work as expected. Before using a SOAP `Update` task to change `PaymentTerm` on a `Subscription` object, confirm with the user whether Flexible Billing is enabled on their tenant. If it is, use `mcp__zuora-mcp__ask_zuora` to determine the correct API path for updating `PaymentTerm` in that configuration.

### Callout

**Purpose.** Generic HTTP callout to an external (or Zuora REST) endpoint. Response is parsed (JSON / XML / text) and written under a configurable `Data` scope. Strongly **opaque**: downstream Liquid against the response should be wrapped with `_opaque_trusted` or `_expected_response_schema` hints.

**UI partial.** `app/views/tasks/partials/_callout.html.erb` (with tabs Headers / Body / Authentication / Response / Help, plus an Advanced tab when the appinstance enables `concurrency_subsequent_task`).

**Controller permit.** Explicit `when :callout` branch in `tasks_controller.rb` L596-653 with a fully enumerated parameter allowlist. Top-level `headers_attributes`, `form_datas_attributes`, and `datas_attributes` ride alongside `common_params`. Files (`parameters.files`) is coerced from a hash to an Array (L647-649); `cert.p12_file` is read into bytea (L643-645).

**Model validation (`app/models/tasks/callout.rb`).**

- L11-49 `task_setup_validation`: `url` required; GET cannot have `raw_body`; URL_BLACKLIST (Zuora file API, S3 owl) rejected; cannot point at `/workflows/.../run`; `retry_count` 0..10; `retry_window` 0..60; rejects plain-text `apiAccessKeyId` / `apiSecretAccessKey` / `Authorization Basic` headers; `payload_location` must match `[a-zA-Z0-9_]+`; `entity_id` required when `authorization.type == 'zuora'` and tenant has multiple entities; `notification_history_account_id` required when enabled.

**`task_process` notes.** Parses `url` via Liquid, performs the HTTP request honoring `authorization.type`, then writes `Data.<payload_location | 'Callout'>` with the parsed response. When `include_response_code` is true, the value is `{ResponseBody, ResponseCode, URL}`; otherwise it's the body directly. `validation.replace` replaces the entire `Data` scope; `validation.zuora_call` enables Zuora-specific retry semantics (rate limit / session / locking).

**Field-by-field (high-traffic subset; see the contract block in `workflow-task-templates.json` for the full list).**

| Field | Source | Options source / format | Required when | Default | Notes |
| --- | --- | --- | --- | --- | --- |
| `parameters.api_name` | `dropdown-static` | `f.object.retrieve_apis` grouped by tag (`_callout.html.erb` L72-76) | optional | -- | Selecting a value autofills `url`/`method`/`raw_body`/`authorization` from the API metadata and reloads the form. |
| `parameters.method` | `dropdown-static` | `["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE"]` (`_callout.html.erb` L87) | always | `POST` | When `GET`, `raw_body` must be blank. |
| `parameters.url` | `user-input` | -- | always | -- | Liquid evaluated. Rejected when matches URL_BLACKLIST or `/workflows/.../run`. UI auto-enables `validation.zuora_call` when host ends in `.zuora.com`. |
| `parameters.body_type` | `dropdown-static` | `["none", "form-data", "x-www-form-urlencoded", "raw", "binary"]` | optional | `raw` | UI disables `x-www-form-urlencoded`. |
| `parameters.raw_body` | `code-editor` | -- | when `body_type == 'raw'` | `""` | Liquid evaluated. Must be blank when method is GET. |
| `headers_attributes` | `form-array` | free-form `(key, value)` | first row required | `[{Content-Type, application/json}]` | In import JSON we pass these as `parameters.headers = [{key, value}, ...]`; the controller normalizes them. |
| `form_datas_attributes` | `form-array` | -- | when `body_type == 'form-data'` | `[]` | -- |
| `parameters.file_binary` | `dropdown-from-parent-task` | `data_structure['Files']` (`_callout.html.erb` L267-275) | when `body_type == 'binary'` | -- | -- |
| `parameters.files` | `form-array` | `data_structure['Files']` | when `body_type == 'form-data'` | `[]` | Controller hash->array coerces. |
| `parameters.authorization.type` | `dropdown-static` | `['none', 'zuora', 'basic_auth', 'oauth1', 'oauth2', 'hmac', 'cert', 'netsuite_tba']` | optional | `none` | Selecting a type unlocks the matching nested credentials block. For Zuora API endpoints, set this to `zuora`; do not hand-roll Zuora credential headers. |
| `parameters.basic_auth / oauth1 / oauth2 / hmac / cert / netsuite_tba` | nested-hash | per-block | when `authorization.type` matches | -- | Only the block matching `authorization.type` should be populated. |
| `parameters.retry_rules` | nested-hash | `{retry_count, retry_window, current_retry_count, on_timeout}` | optional | `{retry_count: 0, retry_window: 30, on_timeout: false}` | `retry_count` 0..10; `retry_window` 0..60. |
| `parameters.validation.status_codes` | `multi-select-with-tags` | `f.object.http_codes` union existing list | optional | `["200"]` | Array of integer-strings (NOT integers). |
| `parameters.validation.payload_location` | `user-input` | `[a-zA-Z0-9_]+` | optional | `"Callout"` | Names the `Data` scope where the response is written. |
| `parameters.validation.replace` | boolean-string checkbox | -- | optional | `"false"` | Replace vs merge into the scope. |
| `parameters.validation.zuora_call` | boolean-string checkbox | -- | optional | auto-set when host ends in `.zuora.com` | Enables Zuora-aware retry/error handling. |
| `parameters.include_response_code` | boolean-string checkbox | -- | optional | `"true"` | When true, response is wrapped as `{ResponseBody, ResponseCode, URL}`. |
| `parameters.validate_response` | boolean-string checkbox | -- | optional | `"false"` | When true, requires `validation_scheme` (Liquid) to evaluate to `'true'`. |
| `parameters.validation_scheme` | code-editor | -- | when `validate_response == 'true'` | -- | -- |
| `parameters.notification_history_*` | bool + user-input | -- | optional | -- | `notification_history_account_id` required when enabled. |
| `parameters.enable_polling` etc. | user-input | -- | optional | -- | Only available when `appinstance.extra_settings['concurrency_subsequent_task']` is true. |

**Common gotchas.**

- `validation.status_codes` must be **strings** (`"200"`), not integers. JSON booleans / integers will fail the W178/E109 lint rules once they land.
- The full permit list is at `tasks_controller.rb` L596-653 -- any key outside that list is silently dropped on save.
- For Zuora REST endpoints, use `authorization.type = 'zuora'`, not `authorization.type = 'none'` plus `apiAccessKeyId`, `apiSecretAccessKey`, `Authorization`, or bearer-token headers. The model handles tenant credentials and entity-id propagation; add `authorization.entity_id` only when a multi-entity tenant requires it.
- For Zuora API callouts, emit `validation.replace = "true"` and `validation.zuora_call = "true"` so Workflow replaces the response payload scope and applies Zuora-aware retry/error handling.
- `include_response_code` defaults to `"true"`; downstream tasks must read parsed response fields under `Data.<payload_location | 'Callout'>.ResponseBody.*` unless the producing callout explicitly sets `include_response_code = "false"`.
- For Create a bill run, use the modern REST resource path `{{ Credentials.zuora.rest_endpoint }}bill-runs`; do not call the legacy object CRUD endpoint `/object/bill-run`.
- `Credentials.zuora.rest_endpoint` already includes the Zuora REST v1 base path. For v1 APIs, emit `{{ Credentials.zuora.rest_endpoint }}orders`, not `{{ Credentials.zuora.rest_endpoint }}/v1/orders` and not `{{ Credentials.zuora.rest_endpoint | replace: "/v1/", "" }}/v1/orders`; the linter flags the duplicate-v1 risk as `E182`.

### AsynchronousCallout

**Purpose.** Same as `Callout` but adds a polling leg: an initial HTTP request kicks off an async job, then Workflows polls a separate endpoint until `parameters.response_path` (Liquid) returns one of `parameters.finish_status`.

**UI partial.** Reuses the `_callout.html.erb` shape but adds a Polling tab whose fields mirror Headers/Body/Auth/Response with a `polling_` prefix on every key.

**Controller permit.** Explicit `when :asynchronous_callout` branch (`tasks_controller.rb` L654-741). Two parallel allowlists: the initial-callout keys (mirroring Callout's L597-641) and the `polling_*` counterparts (L676-728). Top-level `polling_form_datas_attributes`, `polling_headers_attributes`, `polling_datas_attributes` ride alongside the standard ones. File coercion (L735-740) is identical to Callout.

**Model validation (`app/models/tasks/asynchronous_callout.rb`).**

- L2-7 `task_setup_validation` calls `super` (Callout) plus `async_task_setup_validation` twice (`polling: false` then `polling: true`). Each pass enforces the same rules as Callout but on the `polling_*` prefix.

**`task_process` notes.** Issues the initial HTTP request, then polls `polling_url` every `parameters.polling_interval` seconds, evaluating `parameters.response_path` against each response. Polling stops when the result equals one of `parameters.finish_status`. Initial body lands at `Data.<validation.payload_location | 'Callout'>`; polling body lands at `Data.<polling_validation.polling_payload_location | 'Callout'>`.

**Field-by-field.**

| Field group | Notes |
| --- | --- |
| Initial callout (`parameters.url`, `method`, `raw_body`, `body_type`, `headers_attributes`, `form_datas_attributes`, `files`, `file_binary`, `authorization`, `basic_auth/oauth1/oauth2/hmac/cert/netsuite_tba`, `retry_rules`, `validation`, `validate_response`, `validation_scheme`, `include_response_code`, `notification_history_*`, `event_name`) | Identical semantics to Callout. See Callout's section. Permit lives at `tasks_controller.rb` L657-721. |
| Polling leg (`parameters.polling_url`, `polling_method`, `polling_raw_body`, `polling_body_type`, `polling_headers_attributes`, `polling_form_datas_attributes`, `polling_files`, `polling_file_binary`, `polling_authorization`, `polling_basic_auth/oauth1/oauth2/hmac/cert/netsuite_tba`, `polling_retry_rules`, `polling_validation`, `polling_validate_response`, `polling_validation_scheme`, `polling_include_response_code`, `polling_notification_history_*`, `polling_event_name`) | Mirror of every initial-callout field with `polling_` prefix. Validated by `async_task_setup_validation(polling: true)`. Permit lives at L676-728. |
| `parameters.polling_interval` | Seconds between polling attempts. Default `30`. |
| `parameters.response_path` | Liquid expression that extracts the polling status from each response body. Compared against `parameters.finish_status`. |
| `parameters.finish_status` | `Array<String>` of status values that mark the async job as done. |

**Common gotchas.**

- Misspell `polling_xyz` as `pollingXyz` and the controller silently drops the key; the polling leg then fails because its required field is missing.
- The same `E182` Zuora REST v1 URL rule applies to both `parameters.url` and `parameters.polling_url`.
- Two distinct `Data` scopes are written -- one for the initial response and one for the polling response. Both are opaque; both deserve `_opaque_trusted` or `_expected_response_schema` hints if you need downstream Liquid against them.

### Email

**Purpose.** Render an HTML email via Liquid and (optionally) send it; record the rendered body to `Data.Files.<file_holder_name>` for audit.

**UI partial.** `app/views/tasks/partials/_email.html.erb` (Address / Custom Headers / Body / Attachments / Help tabs).

**Controller permit.** Explicit `when :email` branch in `tasks_controller.rb` L795-799. Permits `headers_attributes: %i(key value)` at the top level and then merges `params[:email][:parameters]` raw (opaque). So the entire `parameters.email.*` tree is accepted unfiltered, exactly like the fall-through branch.

**Model validation (`app/models/tasks/email.rb`).**

- L16-27 `task_setup_validation`: `email.to`, `email.from`, `email.subject`, `email.template` required; `from` must be in `appinstance.emails` (or any address when SMTP enabled, see L57-61); `reply_to` required when org isn't Zuora and `from == 'workflow@zuora.com'`; `notification_history_account_id` required when enabled.
- L50-54 `cast`: drops blank entries from `to/cc/bcc` before save.

**`task_process` notes.** Renders the Liquid template, sends via SMTP / `WorkflowMailer`, and uploads two `Files` entries: `file_holder_name(file_type: 'html')` and `(file_type: 'encoded')`. No business-value `Data` is written, so downstream Liquid must NOT depend on Email output.

**Field-by-field.**

| Field | Source | Options source / format | Required when | Default | Notes |
| --- | --- | --- | --- | --- | --- |
| `parameters.email.to` | `multi-select-with-tags` | `accessible_payload` | always | `[]` | Each entry can be a literal email or a Liquid expression like `{{Data.Account.WorkEmail__c}}`. |
| `parameters.email.from` | `dropdown-static` | `appinstance.emails` (free-text when SMTP enabled, `_email.html.erb` L64-74) | always (unless `preview_only == 'true'`) | `"workflow@zuora.com"` | Must be in `appinstance.emails` for SES path. |
| `parameters.email.name` | user-input-or-Liquid | -- | optional | -- | Display name for the sender. |
| `parameters.email.reply_to` | user-input-or-Liquid | -- | required when org isn't Zuora and `from == 'workflow@zuora.com'` | -- | -- |
| `parameters.email.cc / .bcc` | `multi-select-with-tags` | -- | optional | `[]` | -- |
| `parameters.email.return_path` | user-input | -- | optional | -- | Domain must match `appinstance.emails` domains. |
| `parameters.email.subject` | user-input | -- | always | -- | Liquid evaluated. |
| `parameters.email.template` | code-editor (HTML or richtext) | -- | always | -- | When the template contains `<script>`/`<iframe>` the rich-text editor is force-disabled (`email.rb` L41-48). |
| `parameters.email.preview_only` | boolean-string checkbox | -- | optional | `"true"` (in UI default) | When `"true"`, render and log only -- do not send. |
| `parameters.email.disable_editor` | boolean-string checkbox | -- | optional | `"false"` | -- |
| `parameters.email.attachments.invoices` | boolean-string checkbox | -- | optional | `"false"` | UI disables this checkbox unless `Data.Invoice[].Id` is present in parent `data_structure`. |
| `parameters.email.attachments.file_ids` | `multi-select-with-tags` | -- | optional | `[]` | Liquid expressions allowed. |
| `parameters.files` | `form-array` | `prev_operation.data_structure['Files']` | optional | `{}` | Workflow Files entries from upstream tasks. |
| `parameters.notification_history_*` | bool + user-input | -- | optional | -- | `account_id` required when enabled. |
| `headers_attributes` | `form-array` | -- | optional | `[]` | Custom email headers. |

**Common gotchas.**

- `Email`'s permit branch only enumerates `headers_attributes`; everything inside `parameters` is merged in raw. The contract above is enforced entirely by the UI partial + the model validators.
- Setting `email.from` to an address not in `appinstance.emails` will pass validation locally but fail at runtime with `Cannot email from a non registered email`.
- `Email` emits **no** business `Data`; downstream tasks can read `Data.Files.<file_holder_name>` (HTML/encoded blobs) but should not reference any other shape.

## Tier 1 -- control flow and scripting (Batch C)

These five tasks are the building blocks of every non-trivial workflow: pick a branch (`If`, `Logic::Case`), join branches back together (`Logic::Merge`), shape data inline (`Logic::Liquid`), or hand work to AWS (`Logic::Lambda`). All five fall through the controller's `else` branch (`tasks_controller.rb` L800-802), so `parameters` is permitted as an opaque hash and validation lives entirely in the model + UI.

### If

- **Purpose:** Branch on a Liquid expression that must reduce to the literal string `true` or `false`. Emits exactly one of the `True`, `False`, or `Failure` linkages -- never `Success`.
- **UI partial:** [`app/views/tasks/partials/_if.html.erb`](../../../workflow/rails/app/views/tasks/partials/_if.html.erb) -- single textarea bound to `parameters.if_clause`. The placeholder shows the canonical pattern `{% if 0 > 1 %} True {% else %} False {% endif %}`.
- **Controller permit:** Fall-through `else` branch at [`tasks_controller.rb` L800-802](../../../workflow/rails/app/controllers/tasks_controller.rb): the entire `parameters` hash is accepted opaquely; `disable_validation` and `strict_variables` ride on `common_params`.
- **Model validation ([`app/models/tasks/if.rb`](../../../workflow/rails/app/models/tasks/if.rb) L2-10):** `task_setup_validation` runs `template_parse(item: parameters.if_clause, validate: true)` so any Liquid syntax error fails the save. Skipped on `Task.import` (which calls `save(validate: false)`).
- **Runtime (`task_process` L24-38):** Re-evaluates the Liquid in strict mode, lowercases + strips, and routes to either `True` or `False`. Anything else -- empty string, `"yes"`, multi-word output -- raises a `WorkflowError` with the rendered output appended for debuggability.

| Field | Required | Source / UI control | Notes |
| --- | --- | --- | --- |
| `parameters.if_clause` | Yes | Code editor (Liquid) | Must reduce to lowercase `true` / `false`. Lowercasing happens at runtime, so `True` works too. |
| `parameters.disable_validation` | No (`"false"`) | Boolean checkbox | Skips the save-time Liquid parse if the expression depends on runtime data. |
| `parameters.strict_variables` | No (`"true"`) | Boolean checkbox | When `true`, missing Liquid variables raise instead of silently rendering empty. |

**Common gotchas**

- Emitting a `Success` linkage from an `If` is a hard error -- the hooks block declares only `True`, `False`, `Failure`. The linter flags this via E110.
- Wrap the entire Liquid body in `{% if ... %}true{% else %}false{% endif %}` -- bare conditionals like `{{ Data.X | size }} > 0` render as the unparsed string `"5 > 0"` and blow up at runtime.
- Liquid scope is the standard top-level set: `Data`, `Credentials.zuora`, `WorkflowInstance`, `WorkflowSetup`, `TaskInstance`, `GlobalConstants`.

### Logic::Case

- **Purpose:** Multi-way branch. Evaluate `case_clause` (Liquid), then route to the first `Case_N` whose match value matches; fall back to `Case_Else` when nothing matches.
- **UI partial:** [`app/views/tasks/partials/logic/_case.html.erb`](../../../workflow/rails/app/views/tasks/partials/logic/_case.html.erb) -- one textarea for the clause, plus a dynamic key/value table for `case_condition`.
- **Controller permit:** Fall-through (`tasks_controller.rb` L800-802); `parameters` is opaque.
- **Model validation ([`app/models/tasks/logic/case.rb`](../../../workflow/rails/app/models/tasks/logic/case.rb)):**
  - `task_setup_validation` (L6-22) requires `case_clause`, parses the Liquid, requires `case_condition` to be present, and rejects any blank values.
  - `before_save :validate_labels` (L51-74) RENUMBERS the `case_condition` keys to `Case_1`, `Case_2`, ... in stable order **and destroys any source linkage whose `linkage_type` is not in the new keyset.** Hand-edited gaps (e.g. submitting `Case_3` without `Case_2`) are silently rewritten -- and any linkage you authored against the old key is lost.
- **Runtime (`task_process` L32-45):** Renders `case_clause` (strict Liquid), then iterates `case_condition` in insertion order. When `disable_regex` is `"true"` it does string-equality compare; otherwise it treats each value as a regex anchored with `\A...\z`. The first matching key wins; if nothing matches, `Case_Else` fires. Hooks (L47-49) advertise one hook per `Case_N` plus `Case_Else` and `Failure`.

| Field | Required | Source / UI control | Notes |
| --- | --- | --- | --- |
| `parameters.case_clause` | Yes | Code editor (Liquid) | Output is stripped before matching. UI default: `{{Data.Account.Currency}}`. |
| `parameters.case_condition` | Yes | Form-array (key=`Case_N`, value=match) | Keys MUST be sequential `Case_1`, `Case_2`, ... -- no gaps, no out-of-order numbers. |
| `parameters.disable_regex` | No (`"false"`) | Boolean checkbox | When `"true"`, match values are compared as literal strings instead of anchored regex. |
| `parameters.disable_validation` | No (`"false"`) | Boolean checkbox | Skips the save-time Liquid parse. |
| `parameters.strict_variables` | No (`"true"`) | Boolean checkbox | Raises on missing Liquid variables when `true`. |

**Common gotchas**

- ALWAYS pre-normalize `case_condition` keys to sequential `Case_1`, `Case_2`, ... before saving. Linter rules E111/E112 enforce this.
- `Case_Else` is implicit -- it does not appear in `case_condition` but should appear as a `linkage.linkage_type` to receive the no-match path.
- Default regex matching is anchored, so the value `Active` matches only the exact string `"Active"`. Set `disable_regex: "true"` to match substrings literally, or write the explicit regex (`(Active|Pending)`).

### Logic::Merge

- **Purpose:** Wait for all incoming branches to finish, then deep-merge their `Data` into a single hand-off scope. The standard "fan-in" after a fan-out (`Iterate`, `Logic::Case`, branching `If`).
- **UI partial:** [`app/views/tasks/partials/logic/_merge.html.erb`](../../../workflow/rails/app/views/tasks/partials/logic/_merge.html.erb) -- intentionally empty; Logic::Merge has NO user-configurable parameters.
- **Controller permit:** Fall-through (`tasks_controller.rb` L800-802). `parameters` is normally `{}` or `{"strict_variables": "true"}`.
- **Model validation ([`app/models/tasks/logic/merge.rb`](../../../workflow/rails/app/models/tasks/logic/merge.rb)):**
  - `task_setup_validation` (L10-13) calls `Linkage#avoid_for_each_linkage_before_merge_task` ([`app/models/linkage.rb` L72-122](../../../workflow/rails/app/models/linkage.rb)). The validator REJECTS the workflow if any `For Each` linkage sits on any directed path from start to this merge.
  - `validate_merge_start_task` performs a DFS from the merge backwards and rewrites `merge_start` and `merge_paths` on every reachable task at save time. The server is authoritative -- never try to populate those fields client-side.
- **Runtime (`task_process` L19-32):** Polls until `merge_finished?` returns true (every inbound predecessor has finished). Then `merge_data_from_branches` deep-merges the predecessor `data` hashes into `self.new_data`: `Workflow`, `Files`, and `Liquid` keys are deep-merged; arrays are concatenated; collisions for other keys are widened into arrays. Finally `iterate_tasks(linkage_type: 'Success')`.

| Field | Required | Source / UI control | Notes |
| --- | --- | --- | --- |
| `parameters` | -- | n/a (UI is empty) | Always emit `{}` or `{"strict_variables": "true"}`. The merge behavior is entirely topology-driven. |

**Common gotchas**

- A `For Each` linkage anywhere upstream of a `Logic::Merge` is a hard validation error -- the linter mirrors the Rails check via E120.
- Downstream tasks should treat the merge's `Data` as the SET-UNION of every branch's writes. Reference upstream scopes by their original keys (`Data.Liquid.X`, `Data.Account.Id`, ...); do not invent a `Data.Merge.*` namespace.
- A `Logic::Merge` with only one inbound branch is technically legal but pointless; the linter (W121) warns when it sees one.

### Logic::Liquid

- **Purpose:** Run a Liquid template purely for its side effects -- `{% assign foo = ... %}` / `{% capture foo %}` writes appear under `Data.Liquid` (or `Data.Liquid.<placement>`) for downstream tasks.
- **UI partial:** [`app/views/tasks/partials/logic/_liquid.html.erb`](../../../workflow/rails/app/views/tasks/partials/logic/_liquid.html.erb) -- single textarea bound to `parameters.code`.
- **Controller permit:** Fall-through (`tasks_controller.rb` L800-802); `parameters` is opaque.
- **Model validation ([`app/models/tasks/logic/liquid.rb`](../../../workflow/rails/app/models/tasks/logic/liquid.rb)):** No `task_setup_validation` is defined -- the Liquid template is NOT parsed at save time. Syntax errors surface at runtime when `task_process` executes the template. (Contrast with `If`, which validates at save time.)
- **Runtime (`task_process` L10-13):** `template_parse(item: parameters.code)` evaluates the template against the standard Liquid scopes; outputs land in `Data.Liquid` (or `Data.Liquid.<placement>` when `parameters.placement` is set). Then `iterate_tasks(linkage_type: 'Success')`. Only `{% assign %}` and `{% capture %}` survive into the scope -- bare `{{ ... }}` output is discarded.

| Field | Required | Source / UI control | Notes |
| --- | --- | --- | --- |
| `parameters.code` | Yes | Code editor (Liquid) | The linter scans for `{% assign %}` / `{% capture %}` to populate the W173 catalogue of producible scopes. |
| `parameters.placement` | No (`""`) | Text input | Optional override. Standard convention: results land at `Data.Liquid.<placement>` when set. |
| `parameters.disable_validation` | No (`"false"`) | Boolean checkbox | No-op for Liquid (no save-time validation runs). Included for API symmetry. |
| `parameters.strict_variables` | No (`"true"`) | Boolean checkbox | When `true`, missing Liquid variables raise at runtime instead of silently rendering empty. |

**Common gotchas**

- Forgetting to `{% assign %}` is the #1 cause of "I see the value in preview but downstream tasks can't read it." Bare `{{ ... }}` interpolations are not retained.
- Liquid syntax errors are caught only at RUN time -- the linter (W170) does a best-effort static parse, but invalid templates still pass save.
- Two sibling `Logic::Liquid` tasks with the same (or empty) `placement` will overwrite each other in `Data.Liquid`. Use distinct `placement` values when fan-out scopes need to coexist.
- Do not use Liquid only to copy `Data.LinkRun.first.*` / `Data.Link.first.*` values from one `Data::Link` into variables for another `Data::Link`. If the first query is a scalar lookup for the second query, fold it into the second query with a CTE / `CROSS JOIN` and project the scalar fields onto each row. Linter rule `W180` flags the avoidable chain.

### Logic::Lambda

- **Purpose:** Invoke an AWS Lambda function (sync or async) and write its return value to `Data.Lambda`. Useful for tenant-specific logic that doesn't fit Liquid or Zuora API calls.
- **UI partial:** [`app/views/tasks/partials/logic/_lambda.html.erb`](../../../workflow/rails/app/views/tasks/partials/logic/_lambda.html.erb) -- two modes: pick an existing function from the dropdown, or upload a new zip with `FunctionName`, `Handler`, `Runtime`, optional `Memory` / `TimeOut` / env vars.
- **Controller permit:** Fall-through (`tasks_controller.rb` L800-802). `parameters` is opaque; uploaded files ride on `common_params.files`.
- **Model validation ([`app/models/tasks/logic/lambda.rb`](../../../workflow/rails/app/models/tasks/logic/lambda.rb) L19-28):** Two modes:
  - When `parameters.LambdaFunction` is present -> require it non-blank.
  - Otherwise (upload mode) -> require `parameters.FunctionName`, `Handler`, `Runtime`, AND at least one attached file.
  - `after_validation :upload_function` (L4) packages the attached zip and uploads it to AWS Lambda when no `LambdaFunction` key is present and validation passed -- this is a side effect of `save`, so design-time saves can fail with AWS errors.
- **Runtime (`task_process` L42-...):** Builds an invocation payload `{EventType, AppInstance, Data, Credentials.zuora, TaskInstance, WorkflowInstance, ...}`, then invokes `WF-<owner>-<LambdaFunction>` (`lambda_function_name` L38-40). SYNC default uses `EXECUTION_TIMEOUT_SYNC = 240s`; async uses `EXECUTION_TIMEOUT_ASYNC = 600s`. The task self-suspends with the transient flag `ExecutingLambda` and resumes on the Lambda callback. The full Lambda response is written verbatim to `Data.Lambda`; downstream consumers must use opaque references (the linter treats `Data.Lambda.*` as opaque-allowed).

| Field | Required | Source / UI control | Notes |
| --- | --- | --- | --- |
| `parameters.LambdaFunction` | Yes (existing-function mode) | Dropdown sourced from AWS list_functions filtered by `WF-<owner>-` prefix | Mutually exclusive with the upload-mode fields below. The full AWS function name becomes `WF-<owner>-<LambdaFunction>`. |
| `parameters.FunctionName` | Yes (upload mode) | Text input | Name to register the new function under. Reuse via `LambdaFunction` afterwards. |
| `parameters.Handler` | Yes (upload mode) | Text input | Lambda handler entry point (e.g. `index.handler`, `app.lambda_handler`). |
| `parameters.Runtime` | Yes (upload mode) | Static dropdown | Standard AWS Lambda runtime identifiers (`nodejs18.x`, `python3.11`, `java17`, `ruby3.2`, ...). |
| `parameters.Memory` | No (`128`) | Integer input | UI suggests <= 512 for sync invocations. AWS upper bound applies. |
| `parameters.TimeOut` | No (`60`) | Integer input | Synchronous timeout (seconds). Hard cap: `EXECUTION_TIMEOUT_SYNC = 240`. |
| `parameters.TimeOutAsync` | No (`300`) | Integer input | Async timeout (seconds). Hard cap: `EXECUTION_TIMEOUT_ASYNC = 600`. |
| `parameters.Description` | No | Text input | Forwarded to AWS Lambda when uploading. |
| `parameters.env_var` | No (`[]`) | Form-array of `{env_key, env_val}` | Forwarded as Lambda environment variables. |
| `files` | Yes (upload mode) | File upload (top-level Task field) | Zip containing the function source. Must be present when not using an existing function. |
| `parameters.payload` | No (`"{}"`) | Code editor (Liquid + JSON) | Liquid-evaluated string (commonly JSON) sent as the Lambda invocation event body. Inject runtime values via `{{ Data.X }}`. |

**Common gotchas**

- The two configuration modes are mutually exclusive: either point at an existing function (`LambdaFunction` only) or upload a new one (`FunctionName` + `Handler` + `Runtime` + `files`). Mixing them confuses `task_setup_validation` and emits `function_name_missing` even though `LambdaFunction` is set.
- `Data.Lambda` is opaque -- the agent must not reference specific subkeys unless the user supplies an explicit response schema. The linter flags `Data.Lambda.X` references as `W181` opaque-without-schema.
- Lambda zip uploads happen during `save` (via `after_validation :upload_function`), so AWS-side errors (IAM, runtime mismatch, missing handler) surface as 422s on the workflow form -- not at runtime.

## Tier 2 -- common (Batches D / E / F)

> Phase 3 Batch D below: human-in-the-loop, time control, and ad-hoc transformation tasks. All five fall through the controller `else` branch -- `parameters` is opaque, validation lives in the model + UI.

### Approval

- **Purpose:** Pause the workflow until a human approves or rejects via Zuora's inbox UI, email, Slack, Webex, or Teams. Emits exactly one of `Approve` / `Reject` / `Failure` (no `Success`).
- **UI partial:** [`app/views/tasks/partials/_approval.html.erb`](../../../workflow/rails/app/views/tasks/partials/_approval.html.erb) holds the zuoraInbox username picker; the React component [`app/javascript/components/tasks/ApprovalTask.js`](../../../workflow/rails/app/javascript/components/tasks/ApprovalTask.js) renders the Slack/Webex/Teams/Email tabs and the Batch Review tab (business-process workflows only).
- **Controller permit:** Fall-through (`tasks_controller.rb` L800-802). `parameters` is opaque; common fields (`name`, `description`, `assignment`, `error_handler`, `priority`, ...) ride on `common_params`.
- **Model validation ([`app/models/tasks/approval.rb`](../../../workflow/rails/app/models/tasks/approval.rb) L15-70):**
  - Skipped entirely when `workflow.is_business_process?` is true.
  - For `delivery_method = zuoraInbox` (or blank): `approver_emails` must be non-empty AND every entry is either `*` or a valid Zuora username (`/^(?!\s).+(?<!\s)$/`).
  - For other delivery methods: the matching `<channel>_approver_emails` list must be non-empty AND every entry is `*` or a valid email; per-channel transport fields must all be present (Slack: `slackEndpoint`, `slackToken`, `slackBody`; Webex: `webexEndpoint`, `webexToken`, `webexBody`; Teams: `teamsTenantId`, `teamsClientId`, `teamsClientSecret`, `teamsUsername`, `teamsPassword`, `teamsBody`; Email: `senderEmail`, `subjectEmail`, `emailBody`).
  - `before_save :convert_hash_arrays_to_arrays` (L13) coerces `review_columns_config` / `row_actions_config` back to arrays when Rails has flattened them to `{0: ..., 1: ...}` hashes.
- **Runtime (`task_process` L349-452):**
  - `is_business_process?` workflows: build approver list from `selected_approvers`, publish a Kafka message to `KAFKA_APPROVAL_TOPIC`, and `raise PendingTask` until the inbox API marks the task approved/rejected.
  - Otherwise: validate approver usernames, set `self.assignment`, render `approvalNote` via Liquid, dispatch `handle_<channel>_delivery` for non-zuoraInbox modes, then `raise PendingTask` until `parameters[:approver]` or `parameters[:rejecter]` is set by the API.
  - Once handled: `add_notes` audit trail; `Data.Approval = { action: 'approve' | 'reject', user: <email>, data: <approvalData> }`; iterate to the matching `Approve` / `Reject` linkage.
  - Hooks (L84-86): `Approve`, `Reject`, `Failure` only -- never emit a `Success` linkage.

| Field | Required (when) | Source / UI control | Notes |
| --- | --- | --- | --- |
| `parameters.delivery_method` | Optional (defaults to `zuoraInbox`) | Static dropdown | Allowed: `zuoraInbox`, `email`, `slack`, `webex`, `teams` (`ALLOWED_DELIVERY_METHODS`). |
| `parameters.approver_emails` | `delivery_method = zuoraInbox` | Multi-tag select pre-populated with current entity's Zuora users | Each entry is a Zuora username or `*` (any user). Liquid expressions are template_parsed and split on commas. |
| `parameters.approvalNote` | Optional | Liquid editor | Rendered on the inbox UI and used as the Kafka message description. |
| `parameters.slackEndpoint` / `slackToken` / `slackBody` / `slack_approver_emails` | `delivery_method = slack` | Text + token validators | Token must satisfy `valid_slack_token?`. |
| `parameters.webexEndpoint` / `webexToken` / `webexBody` / `webex_approver_emails` | `delivery_method = webex` | Text + token validators | Token must satisfy `valid_webex_token?`. |
| `parameters.teamsTenantId` / `teamsClientId` / `teamsClientSecret` / `teamsUsername` / `teamsPassword` / `teamsBody` / `teams_approver_emails` | `delivery_method = teams` | Text fields (secrets stored encrypted) | All six transport fields are required. |
| `parameters.senderEmail` / `subjectEmail` / `emailBody` / `email_approver_emails` | `delivery_method = email` | Text + Liquid editor | `emailBody` is the rendered HTML body. |
| `parameters.selected_approvers` | Business-process tab only | Form-array of user objects (`{core_id, ...}`) | `formated_zuora_approver` extracts the `core_id` list for the Kafka payload. |
| `parameters.review_items_template` / `review_columns_config` / `row_actions_config` / `preset_conditions` | Business-process tab only | Liquid + form-arrays | Only used by `is_business_process?` workflows for the batch-review UI. |
| `parameters.approver` / `parameters.rejecter` | Server-set | -- | Written by `_approve` / `_reject` on the API path. **Never pre-populate** -- it makes the task look already-handled. |

**Common gotchas**

- The hooks block declares only `Approve`, `Reject`, `Failure`. Emitting a `Success` linkage is a hard error (linter E110).
- `delivery_method` blank or `zuoraInbox` validates against the **Zuora user directory**, not arbitrary emails. Use `*` as the only entry to allow any user.
- Approval tasks never expire on their own except after `EXPIRATION_PERIOD = 3.months`; build a separate `Delay` + cancellation path if you need a shorter timeout.
- `Data.Approval` is only set after a decision -- downstream tasks should branch via the `Approve` / `Reject` linkage, not by reading `Data.Approval` from a sibling.

### Delay

- **Purpose:** Pause the workflow until either a number of seconds has elapsed or an absolute timestamp is reached. Emits `Success` after the wait.
- **UI partial:** [`app/views/tasks/partials/_delay.html.erb`](../../../workflow/rails/app/views/tasks/partials/_delay.html.erb) -- single `delay_time` text input plus a hidden `blocking` checkbox.
- **Controller permit:** Fall-through (`tasks_controller.rb` L800-802); `parameters` is opaque.
- **Model validation ([`app/models/tasks/delay.rb`](../../../workflow/rails/app/models/tasks/delay.rb) L2-14):** `delay_time` required. When present, `enqueue_time` is invoked at save time; the resolved future timestamp must be <= 30 days from now and the value must be either all-digit seconds or a `Time.parse`-able string (`enqueue_time` raises a `WorkflowError` for anything else, which surfaces as `:delay_time_wrong_format`).
- **Runtime (`task_process` L28-44):** Renders `parameters.delay_time` via Liquid, classifies as digits (`Time.now + N.seconds`) or absolute (`Time.parse`). Within 10 seconds, sleeps in place; otherwise enqueues itself with `restart_at = target_enqueue_time` and `raise PendingTask`. The `transient_fields['delayed_executed']` flag prevents double-execution on resume.

| Field | Required | Source / UI control | Notes |
| --- | --- | --- | --- |
| `parameters.delay_time` | Yes | Text input (Liquid OK) | All-digit values are seconds; anything else is a `Time.parse`-able timestamp. Hard cap: 30 days from now. |
| `parameters.blocking` | No (`"false"`) | Hidden boolean checkbox | When `"true"`, blocks future scheduled runs of this workflow definition while a Delay is pending. |

**Common gotchas**

- The 30-day cap is checked both at save (`task_setup_validation`) AND at runtime (`task_process` L30) -- attempts to delay further raise a `WorkflowError`.
- Liquid expressions are evaluated at runtime, not at save -- a `delay_time` like `{{ Data.X.RetryAt }}` will pass save-time validation even if the value is junk.
- Mixing `blocking: "true"` with workflows that have many concurrent triggers can produce unexpected queue starvation; only set when intentional.

### Script::JavaScript

- **Purpose:** Run a Node.js script block in the workflow Node sidecar. The exported `step(input)` function receives the workflow `Data` plus the standard Liquid drops (`WorkflowInstance`, `WorkflowSetup`, `TaskInstance`, `GlobalConstants`) and returns the value written to `Data.{placement}`.
- **UI partial:** [`app/views/tasks/partials/script/_java_script.html.erb`](../../../workflow/rails/app/views/tasks/partials/script/_java_script.html.erb) -- placement text input plus a CodeMirror JavaScript editor.
- **Controller permit:** Fall-through (`tasks_controller.rb` L800-802); `parameters` is opaque.
- **Model validation ([`app/models/tasks/script/java_script.rb`](../../../workflow/rails/app/models/tasks/script/java_script.rb)):** No save-time validation. `task_process` (L25-30) raises a `WorkflowError` if `parameters.code` is blank at runtime.
- **Runtime (`task_process` L24-58):** Builds `node_options = {code, timeout, custom_data: {WorkflowInstance, WorkflowSetup, TaskInstance, GlobalConstants}}`, calls `get_node_response`, then `write_data(object_name: self.placement, object_data: output, overwrite: parameters.replace_payload)`. Timeout precedence: `appinstance.extra_settings.js_timeout` -> `parameters.timeout` -> `20s` default.

| Field | Required | Source / UI control | Notes |
| --- | --- | --- | --- |
| `parameters.code` | Yes (at runtime) | CodeMirror (JS mode) | Must export `step(input)`; the return value is written to `Data.<placement>`. The default snippet shows the canonical shape. |
| `parameters.placement` | No (`"Script"`) | Text input | Destination key under `Data`. |
| `parameters.replace_payload` | No (`"false"`) | Boolean checkbox | When `"true"`, overwrite `Data.<placement>` instead of deep-merging. |
| `parameters.timeout` | No (`20`) | Integer input | Per-task timeout in seconds; only applied when `appinstance.extra_settings.js_timeout` is unset. |

**Common gotchas**

- `Data.<placement>` is opaque -- the agent must not invent subkeys without an explicit response schema (linter `W181`).
- Errors thrown inside the JS code surface as `WorkflowError` with the JS stack appended; the task falls into `Failure`.
- The Node sidecar enforces a hard upper bound (~5 min) regardless of `parameters.timeout`; long-running work should be moved to `Logic::Lambda` (async).

### Logic::JSONTransform

- **Purpose:** Transform workflow JSON via one of four processors: `JSONata`, `liquid`, `xml` (write a `.xml` file), or `csv` (write a `.csv` file from a JSON array).
- **UI partial:** [`app/views/tasks/partials/logic/_json_transform.html.erb`](../../../workflow/rails/app/views/tasks/partials/logic/_json_transform.html.erb) -- the `processor` dropdown reloads the form to show processor-specific fields.
- **Controller permit:** Fall-through (`tasks_controller.rb` L800-802); `parameters` is opaque.
- **Model validation ([`app/models/tasks/logic/json_transform.rb`](../../../workflow/rails/app/models/tasks/logic/json_transform.rb) L6-23):**
  - `processor = JSONata` -> `parameters.template` required.
  - `processor = csv` -> `csv_filename` AND `liquid_statement` required; `csv_headers`, when present, must template_parse to valid JSON.
- **Runtime (`task_process` L37-56):** Dispatches by `parameters.processor`:
  - **JSONata** -> Node sidecar receives `template` + `version`; output written via `write_data(placement, output, overwrite: replace_payload)`.
  - **liquid** -> `template_parse` the Liquid template, `JSON.parse` the result, write via `write_data`. JSON parse errors raise.
  - **xml** -> Resolve `parameters.data_source` (Liquid `{{ Data.X | to_json }}` form OR a literal dot path like `Data.Account.Subscriptions[0]`), serialize to XML via Nokogiri::XML::Builder (v1.0) or `Hash#to_xml` (v2.0, default), upload as `.xml`. `RootElement` becomes the wrapping tag.
  - **csv** -> `template_parse(liquid_statement)` must yield a JSON array of flat objects; nested arrays/hashes raise. Write CSV with optional `csv_headers` mapping (`{ "key": "Header" }` controls column order + labels), upload as `.csv`.

| Field | Required (when) | Source / UI control | Notes |
| --- | --- | --- | --- |
| `parameters.processor` | Yes | Static dropdown | Values are case-sensitive: `JSONata`, `liquid`, `xml`, `csv`. |
| `parameters.template` | `processor in ['JSONata','liquid']` | Code editor | JSONata expression OR Liquid template producing JSON. |
| `parameters.placement` | Optional | Text input | Destination key for JSONata/liquid output. Defaults to `JSONTransform`. |
| `parameters.replace_payload` | Optional (`"false"`) | Boolean checkbox | Overwrite `Data.<placement>` for JSONata/liquid output. |
| `parameters.version` | Optional | Static dropdown | JSONata: `1.8.1` (default), `1.8.6`, `2.0.2`. XML: `1.0`, `2.0` (default). |
| `parameters.data_source` | `processor = xml` | Code editor | Either `{{ Data.X | to_json }}` Liquid OR dot path (`Data.Account.Subscriptions[0]`). |
| `parameters.RootElement` | Optional (XML mode) | Text input | Wrapping XML root tag. v1.0 mode requires this when input has multiple top-level nodes. |
| `parameters.csv_filename` | `processor = csv` | Text input | Base name (no extension); defaults to `JSONTransform` at runtime. |
| `parameters.liquid_statement` | `processor = csv` | Code editor (Liquid) | Must render a JSON array of flat objects. |
| `parameters.csv_headers` | Optional (CSV mode) | Code editor (JSON) | `{ "item_key": "Header Label" }` -- controls column order + labels. |

**Common gotchas**

- `processor` values are **case-sensitive** -- `JSONata` (capital J) for the JSONata path, lowercase `liquid|xml|csv` for the others. The agent MUST emit them exactly.
- `xml` and `csv` modes write to `Data.Files.JSONTransform__<task_id>.<ext>`, not to a `placement` scope. Use a downstream `Iterate` (with the file name as `object`) or `Upload::FTP` to consume the file.
- The CSV path rejects items with nested arrays/hashes -- preflight your `liquid_statement` on a `Logic::Liquid` task if you need to flatten before this task.

### Logic::XMLTransform

- **Purpose:** Either run an XSLT transformation against an upstream `.xml` file (`mode = to_xml`) or parse XML into `Data.XMLTransform` (`mode = to_json`). Inline XML can be supplied via `object = 'XML Text'` plus `parameters.xml_text`.
- **UI partial:** [`app/views/tasks/partials/logic/_xml_transform.html.erb`](../../../workflow/rails/app/views/tasks/partials/logic/_xml_transform.html.erb) -- grouped Files dropdown for `object`, Template + Validation tabs for `template` and `xsd_input`, optional `RootElement` (when XML output) and `include_tag_attr` checkbox.
- **Controller permit:** Fall-through (`tasks_controller.rb` L800-802). `object` rides on `common_params`; `parameters` is opaque.
- **Model validation ([`app/models/tasks/logic/xml_transform.rb`](../../../workflow/rails/app/models/tasks/logic/xml_transform.rb)):**
  - `validates :object, presence: true` (L2).
  - `task_setup_validation` (L6-10): requires `parameters.template`, derives `output_format` from the `<xsl:output method='...'>` directive, rejects when format is missing or not in `[csv, xml, txt, html]` (this validation always runs even for `mode = to_json`).
- **Runtime (`task_process` L28-118):**
  - When `object == 'XML Text'`, use `parameters.xml_text` directly.
  - Otherwise pull the named XML file from `Data.Files`, enforce `<100 MB` size and `.xml` extension, and unzip if the holder is a `.zip`.
  - **`mode = to_json`:** parse via `Hash.from_xml` (or `ActiveSupport::XMLConverterWithAttributes` when `include_tag_attr` is true) and `write_data` to `Data.XMLTransform`.
  - **`mode = to_xml`:** apply XSLT via `Nokogiri::XSLT`, optionally validate against `xsd_input`, upload the transformed file (filename defaults to `<source>_xslt`).

| Field | Required (when) | Source / UI control | Notes |
| --- | --- | --- | --- |
| `object` | Yes | Grouped dropdown (Files \| `XML Text`) | Must be either an upstream file holder name matching `/__\d*\.(xml)$/` or the literal `XML Text`. |
| `parameters.mode` | Yes | Static dropdown | `to_xml` (XSLT) or `to_json` (parse). `to_xml` requires a real file -- not `XML Text`. |
| `parameters.template` | `mode = to_xml` | Code editor (XML) | XSLT 1.0 or 2.0; MUST contain `<xsl:output method='xml\|csv\|txt\|html'/>`. The output extension comes from this directive. |
| `parameters.xsd_input` | Optional (`mode = to_xml`, `output = xml`) | Code editor (XSD) | Validates the transformed XML against this schema. |
| `parameters.xml_text` | `object = 'XML Text'` | CodeMirror (XML) | Inline XML payload (Liquid OK). Only valid for `to_json`. |
| `parameters.filename` | Optional | Text input | Output base name (no extension). Defaults to `<source>_xslt`. |
| `parameters.include_tag_attr` | Optional (`"false"`) | Boolean checkbox | When `"true"` (and `mode = to_json`), preserve XML attributes via `ActiveSupport::XMLConverterWithAttributes`. |

**Common gotchas**

- The XSLT `<xsl:output method='...'/>` directive is REQUIRED even for `to_json` mode (the validator parses it unconditionally). Use a no-op `<xsl:output method='xml'/>` template if you only need to_json.
- `to_xml` rejects sources >100 MB and any file whose holder name does not end in `.xml`. Use a `Logic::JSONTransform` (xml mode) or `Logic::CSVTranslator` to convert other formats first.
- Inline `XML Text` mode is only valid for `to_json`; `to_xml` requires an upstream file.

### Logic::CSVTranslator

- **Purpose:** Operate on an upstream CSV file holder. Four mutually exclusive actions: `Filter` rows by column value, convert rows to JSON (`to_json`), convert rows to XML (`xml`), or merge multiple CSVs that share an identical header row (`merge`).
- **UI partial:** [`app/views/tasks/partials/logic/_csv_translator.html.erb`](../../../workflow/rails/app/views/tasks/partials/logic/_csv_translator.html.erb) -- `action` dropdown drives all conditional fields. Filter exposes column / value / regex / output-format inputs; `to_json` exposes placement + replace_payload; `merge` exposes csv_filename + a drag-and-drop file order list (`parameters.files`).
- **Controller permit:** Fall-through (`tasks_controller.rb` L800-802). `object` rides on `common_params`; `parameters` (including the `parameters.files` map) is opaque.
- **Model validation ([`app/models/tasks/logic/csv_translator.rb`](../../../workflow/rails/app/models/tasks/logic/csv_translator.rb)):**
  - `validates :object, presence: true if action in ACTIONS_WITH_OBJECT` (`Filter | xml | to_json`) (L8).
  - `task_setup_validation` (L10-26): `action` required; for `Filter` exactly one of `Column` / `column_number` (XOR) plus `Value` and `OutputFormat`; `column_number` must be a positive integer; for `merge` at least 2 entries in `parameters.files` must have `selected == 'true'`.
- **Runtime (`task_process` L48-87):**
  - Filter / to_json / xml: resolves the file holder from `Data.Files`, rejects `.json` files, unzips when the source is `.csv.zip`, and dispatches to `filter_handler` / `xml_handler` / `merge_handler`.
  - `Filter` + `OutputFormat == 'JSON'` writes filtered rows to `Data.<placement>` (or appends to the matching object array when the source comes from Export / Data::Link / Reporting::RunReport, preserving each object's `new_fields`).
  - `Filter` + `OutputFormat in ['CSV','CSV.ZIP']` writes a file holder under `Data.Files.<source_base>.<csv|csv.zip>`.
  - `xml` writes `Data.Files.<source_base>.xml` with `<records><record><col>val</col></record></records>` rows.
  - `merge` concatenates files in `order_index` order (rejecting any header-row mismatch) and writes `Data.Files.<csv_filename | 'MergedCSV'>.csv`.

| Field | Required (when) | Source / UI control | Notes |
| --- | --- | --- | --- |
| `parameters.action` | Yes | Static dropdown | Case-sensitive values: `Filter`, `to_json`, `xml`, `merge` (UI labels: Filter / Convert to JSON / Convert to XML / Merge). |
| `object` | `action in [Filter, to_json, xml]` | Grouped dropdown (Files) | Upstream Files holder (e.g. `Account__123.csv` or `Account__123.csv.zip`). |
| `parameters.placement` | Optional (`action = to_json`, default `"CSVTranslator"`) | Text input | Destination key under `Data` for to_json output. |
| `parameters.replace_payload` | Optional (`action = to_json`, default `"false"`) | Boolean checkbox | When `"true"`, overwrite `Data.<placement>` instead of appending to the matching object array. |
| `parameters.Column` | `action = Filter` AND `column_number` blank | Picklist + tag input | CSV header name. Picklist is populated from the upstream task's `new_fields` when known. |
| `parameters.column_number` | `action = Filter` AND `Column` blank | Number input | 1-indexed positive integer. XOR with `Column`. |
| `parameters.Value` | `action = Filter` | Text input (Liquid OK) | Equality match by default; treated as a regex when `filter_regex == "true"`. |
| `parameters.filter_regex` | Optional (`action = Filter`, default `"false"`) | Boolean checkbox | When `"true"`, evaluate `Value` as a regex against each row's column value. |
| `parameters.OutputFormat` | `action = Filter` | Static dropdown | One of `JSON`, `CSV`, `CSV.ZIP` -- selects the destination shape. |
| `parameters.csv_filename` | Optional (`action = merge`, default `"MergedCSV"`) | Text input (Liquid OK) | Output filename without extension; final holder is `Data.Files.<csv_filename>.csv`. |
| `parameters.files` | `action = merge` | Form-array (drag-and-drop) | Map `{ <source_holder>: { selected: "true"\|"false", order_index: N } }`. Need >=2 selected. |
| `parameters.zero_result_stop` | Optional (default `"false"`) | Boolean checkbox | When `"true"`, halt downstream tasks if the resulting CSV / merged file has zero data rows. |

**Common gotchas**

- `action` values are case-sensitive: use `Filter`, `to_json`, `xml`, `merge` (NOT `convert_to_json`, `JSON`, `Merge`, etc.).
- `Filter`'s `Column` and `column_number` are mutually exclusive; supplying both fails save with "Either Column name or Column number...".
- `merge` requires at least two `selected == "true"` entries AND identical header rows; mismatched headers raise `"Cannot merge files with different headers"` at runtime.
- `to_json` mutates `Data.<placement>` in-memory only (no Files holder is created); use `OutputFormat = CSV` if you need the filtered file to persist.
- The model rejects `.json` source files; chain a `Logic::JSONTransform` first to convert JSON to CSV when needed.

### Logic::ResponseFormatter

- **Purpose:** Terminate a SYNC-mode workflow by rendering an HTTP response body (Liquid or JSONata) and signalling the parent listener via Redis pubsub. Only valid in `UI`, `SYNC`, `SYNC_UI_ACTION`, `REALTIME`, and `DATASTREAM` workflows -- every other task in the workflow must support `task_mode['SYNC'] == true`.
- **UI partial:** [`app/views/tasks/partials/logic/_response_formatter.html.erb`](../../../workflow/rails/app/views/tasks/partials/logic/_response_formatter.html.erb) -- `processor` dropdown (Liquid / JSONata), `code` (response status), `parent_workflow_status` (Success / Error), and a CodeMirror editor for `template`.
- **Controller permit:** Fall-through (`tasks_controller.rb` L800-802); `parameters` is opaque.
- **Model validation ([`app/models/tasks/logic/response_formatter.rb`](../../../workflow/rails/app/models/tasks/logic/response_formatter.rb)):**
  - `task_setup_validation` (L6-17): `code`, `template`, `processor` all required. When `workflow.ui_mode_workflow == true`, every task in `workflow.all_tasks` must report `task_mode['SYNC'] == true`; otherwise `:incompatible_mode` is added.
- **Runtime (`task_process` L31-56):**
  - `processor = Liquid`: `JSON.parse(template_parse(template))` and `write_data` to `Data.ResponseFormatter` (the key is HARD-CODED -- there is no `placement` override). A parse failure surfaces as "The response is not a valid JSON".
  - `processor = JSONata`: POST `{ data, template }` to the Node sidecar `/transform` endpoint and merge `response['result']` to `Data.ResponseFormatter`.
  - In both cases, mark the task `Task::SUCCESS`, save without validation, and `Redis.publish('Sync:<appinstance_id>:<original_workflow_id>', payload)`. The parent SYNC workflow listens for this and returns the formatted response.
  - Hooks (L27-29) advertise ONLY `Failure`. The task is terminal and never iterates a `Success` linkage.

| Field | Required (when) | Source / UI control | Notes |
| --- | --- | --- | --- |
| `parameters.processor` | Yes (default `"Liquid"`) | Static dropdown | Case-sensitive: `Liquid` or `JSONata`. |
| `parameters.code` | Yes (default `200`) | Number input | HTTP status code returned to the SYNC caller (1-599 typical). |
| `parameters.parent_workflow_status` | Optional (default `"Success"`) | Static dropdown | `Success` or `Error` -- whether to mark the parent workflow as completed or errored. |
| `parameters.template` | Yes | Code editor (CodeMirror, JS mode) | Liquid template that MUST render valid JSON, OR a JSONata expression that returns JSON. |

**Common gotchas**

- The output scope is HARD-CODED to `Data.ResponseFormatter`; `parameters.placement` is silently ignored.
- Liquid mode requires the rendered output to parse as JSON. Wrap strings in quotes and arrays in brackets, or use `| json` filters appropriately.
- ResponseFormatter is terminal: do NOT add a Success linkage out of it. Downstream tasks are unreachable because only the Failure hook is exposed.
- Adding any task that does not support SYNC mode (e.g. `Delay`, `Approval`) to a UI workflow with a ResponseFormatter will fail save with `:incompatible_mode`.

### Notifications::SMS

- **Purpose:** Send an SMS via Twilio. Both the message body and the recipient list are Liquid-parsed at save time (to catch syntax errors) and again at runtime (for live data).
- **UI partial:** [`app/views/tasks/partials/notifications/_sms.html.erb`](../../../workflow/rails/app/views/tasks/partials/notifications/_sms.html.erb) -- `parameters.sms.numbers` is rendered as a multi-tag Select2 input backed by `accessible_payload`; `parameters.sms.message` is a textarea.
- **Controller permit:** Fall-through (`tasks_controller.rb` L800-802); `parameters.sms.{numbers, message}` ride on the opaque parameters hash.
- **Model validation ([`app/models/tasks/notifications/sms.rb`](../../../workflow/rails/app/models/tasks/notifications/sms.rb)):**
  - `before_validation :cast` (L2 + L18-20) strips blank entries from `sms.numbers`.
  - `task_setup_validation` (L4-12): `sms.message` and `sms.numbers` both required. When present, BOTH fields are `template_parse`d in strict + validate mode against `fake_payload` so Liquid syntax errors fail save.
- **Runtime (`task_process` L22-48):**
  - Build `Twilio::REST::Client.new(secrets.twilio.sid, secrets.twilio.auth_token)`.
  - For each entry in `self.numbers` (each one `template_parse`d at runtime), call `client.messages.create(from: secrets.twilio.number, to: number, body: self.message)`.
  - Each send is logged as an `ApiCall` record. Twilio code `21408` ("permission to send to that destination") and other Twilio errors are surfaced as `WorkflowError`.
  - On success, `iterate_tasks(linkage_type: 'Success')`.

| Field | Required (when) | Source / UI control | Notes |
| --- | --- | --- | --- |
| `parameters.sms` | Yes (container) | Rails `fields_for :sms` | MUST be a nested hash; the model dereferences `parameters['sms']['numbers']` and `parameters['sms']['message']` directly. Top-level `parameters.numbers` / `parameters.message` are silently ignored. |
| `parameters.sms.numbers` | Yes | Multi-tag Select2 input | Array of E.164 strings (e.g. `["+15551234567"]`); Liquid OK. Blank entries stripped before save. |
| `parameters.sms.message` | Yes | Textarea (Liquid OK) | Up to 1600 chars per Twilio. Liquid syntax errors fail save. |

**Common gotchas**

- DO NOT put `numbers` or `message` at the top level of `parameters` -- they MUST be nested under `parameters.sms`.
- The Twilio client requires `Rails.application.secrets.twilio.{sid, auth_token, number}` to be configured on the runtime cluster; without those, every send fails with a credentials error.
- Liquid parse errors at save time emit `:invalid_message` or `:invalid_numbers` errors. Validate any embedded `{{ Data.* }}` references against the upstream task contracts before saving.

### Reporting::RunReport

- **Purpose:** Execute a Zuora Reporting report and stream the results back as a CSV file holder. Selecting a report (`object_id`) plus a `viewType` (`Detail` or `Summary`) determines the CSV columns; rows can later be projected into `Data.Report` by Iterating over the resulting `Data.Files` holder.
- **UI partial:** [`app/views/tasks/partials/reporting/_run_report.html.erb`](../../../workflow/rails/app/views/tasks/partials/reporting/_run_report.html.erb) -- two-pane layout with a tree-select for `parameters.label_id` (driven by `fetch_labels` -> Reporting `/reportlabels`) and a report dropdown for `object_id` (driven by `fetch_available_reports`). Optional Basic-auth `parameters.username` / `parameters.password` only render when the workflow's target login is OAuth.
- **Controller permit:** Fall-through (`tasks_controller.rb` L800-802). `object_id` rides on `common_params`; everything under `parameters` is opaque.
- **Model validation ([`app/models/tasks/reporting/run_report.rb`](../../../workflow/rails/app/models/tasks/reporting/run_report.rb)):**
  - `validates :object_id, presence: true` (L5).
  - `custom_initialize` (L43-47) caches `default_filters` and `viewType` (default `'Detail'`).
  - `task_setup_validation` (L16-37): rejects environments other than `Sandbox / Production / Performance / Test`; calls `fetch_report_details` to ensure no `askUser` filters are set, and that the chosen `viewType` has matching definition fields (`selectedFields` for `Detail`; `rowFields`/`colFields`/`valFields` for `Summary`).
  - `is_idempotent? == true`.
- **Runtime (`task_process` L131-201):**
  - If no transient `reportId` exists, POST `/reports/<object_id>/reportrun?viewType=<viewType>` with `body = report.definition.filters` when `default_filters` else `[]`.
  - Poll `/reportruns/<reportId>` every 60s (up to 200 times) until `status == COMPLETED` (raise on `ERROR`).
  - GET `/reportruns/export/<reportId>?pivoted=<bool>` as a file, then upload via `Task#upload_file`. The Files holder is named `<filename without extension>__<task_id>.<ext>` (`file_holder_name` L309-314).
  - `iterate_tasks(linkage_type: 'Success')`.
- **Iterate-time helper (`generate_hash_from_csv`, `data_header_lookup`):** When a downstream Iterate consumes the Files holder, the helper transforms each CSV row into `Data.Report` using `parameters.selected_fields` (a JSON map of `<parameterized_header>` -> `<human label>`). RunReport itself does NOT populate `Data.Report`.

| Field | Required (when) | Source / UI control | Notes |
| --- | --- | --- | --- |
| `object_id` | Yes | Dropdown from Reporting API | `GET <reporting_url>/reports/reportlabels/<label_id>/report-details`. Excludes `deleted` reports. |
| `parameters.label_id` | Yes | Tree-select | `GET <reporting_url>/reportlabels` (cached 24h in Redis). Rendered via `reporting_helper.nested_report_menu`. |
| `parameters.viewType` | Optional (default `"Detail"`) | Static dropdown | `Detail` or `Summary`. Cross-checked against the report definition. |
| `parameters.default_filters` | Optional (default `"false"`) | Boolean checkbox | When `"true"`, send the report's saved filters on `/reportrun`; otherwise send `[]`. |
| `parameters.pivoted` | Optional (default `"false"`) | Boolean checkbox | When `"true"`, append `?pivoted=true` to the export call (Summary reports get flattened by Reporting API). |
| `parameters.filename` | Computed | Hidden field | Auto-set to `<dsName>-<reportName>-<viewType>.csv` from `fetch_report_details`. Never hand-edit. |
| `parameters.selected_fields` | Computed | Hidden field | JSON map of header keys -> labels; produced by `Reporting::RunReport#get_file_header`. Used by Iterate to project `Data.Report`. |
| `parameters.username` | Conditional (`target_login.client.class == ZuoraAPI::Oauth`) | Text input | Reporting API requires Basic credentials. Recommend storing as global constants and templating via Liquid. |
| `parameters.password` | Conditional (`target_login.client.class == ZuoraAPI::Oauth`) | Text input | Same as above. |

**Common gotchas**

- The report definition is fetched at save time -- changing the report's columns or filters in Zuora REQUIRES re-saving the task so `parameters.filename` / `parameters.selected_fields` regenerate.
- Reports with `askUser` filters (interactive prompts) are rejected at save time; modify the report or duplicate it without `askUser`.
- The runtime polls for up to 200 minutes; very long-running reports may exceed this and surface as `ZuoraAPIUnkownError`.
- The downloaded file is a CSV (or `.xls` if pivoted=true and the report uses pivoting). Downstream Iterate must consume the Files holder to populate `Data.Report`.
- OAuth-authenticated workflows MUST supply Basic-auth `username` / `password` -- the Reporting API does not accept OAuth tokens.

### CustomObject::Query

- **Purpose:** Query Custom Object records via a Lucene `parameters.query` and/or an `parameters.ids=<uuid>&ids=<uuid>` URL fragment. Output is written as `Array<Hash>` at `Data.<alternate_location | self.object>` (with `overwrite: true`, so it REPLACES any prior binding at that scope). Idempotent.
- **UI partial:** [`app/views/tasks/partials/custom_object/_query.html.erb`](../../../workflow/rails/app/views/tasks/partials/custom_object/_query.html.erb) -- shared `partials/object_id_type` for object selection (driven by `Thread.current[:appinstance].get_custom_objects(entity_id:)`), then textareas for `query` and `ids`, plus `alternate_location` and `zero_result_stop`. Help tab renders `partials/custom_object/_lucene` cheat-sheet.
- **Controller permit:** Fall-through (`tasks_controller.rb` L800-802); `object` rides on `common_params`.
- **Model validation ([`app/models/tasks/custom_object/query.rb`](../../../workflow/rails/app/models/tasks/custom_object/query.rb)):**
  - `validates :object, presence: true` (L3).
  - `task_setup_validation` (L6-12): `object` required AND at least one of `parameters.query` / `parameters.ids` must be present (else `Please specify the query or ids...`).
  - `is_idempotent? == true`.
- **Runtime (`task_process` L30-59):**
  - Builds `GET <base_url>/objects/records/<namespace>/<object_name>/?q=<url-encoded query>&<ids fragment>`. The URI encoding uses `ERB::Util.url_encode` (the model also logs a debug entry when the encoded value differs from `to_query` - this is a known harmless mismatch). Zero-width characters in the `ids` fragment are stripped.
  - Sets `Zuora-Realtime-Read: true` so the read includes uncommitted writes.
  - Streams the response with a `remaining_size_limit` guard - exceeding `appinstance.data_size_limit` raises `DataLimitError`.
  - On HTTP 200, `write_data(object_name: payload_location, object_data: records, overwrite: true)`. `payload_location = parameters.alternate_location || self.object`.
  - When `count == 0` and `parameters.zero_result_stop == 'true'`, returns without iterating (downstream tasks halt). Otherwise `iterate_tasks(linkage_type: 'Success')`.

| Field | Required (when) | Source / UI control | Notes |
| --- | --- | --- | --- |
| `object` | Yes | Custom Object describe (`get_custom_objects`) | Format: `<namespace>__<object>` (e.g. `default__Vendor`). The namespace and object_name are split via `rpartition('__')`. |
| `parameters.query` | When `parameters.ids` is blank | Textarea (Lucene; Liquid OK) | Lucene-style filter (e.g. `status:active AND activeDate:<2018`). Liquid expressions are template_parsed at runtime. |
| `parameters.ids` | When `parameters.query` is blank | Textarea (Liquid OK) | URL fragment of repeated `ids=<uuid>` params (e.g. `ids={{ Data.xyz | map: 'id' | join: '&ids=' }}`). |
| `parameters.alternate_location` | Optional | Text input | Override the `Data.*` scope where results are written (default = `self.object`). |
| `parameters.zero_result_stop` | Optional (default `"false"`) | Boolean checkbox | When `"true"`, halt downstream tasks if the query returns 0 records. |

**Common gotchas**

- The result write is `overwrite: true`, so any prior binding at `Data.<alternate_location | self.object>` is REPLACED (not merged). If you need to preserve earlier rows, use a different `alternate_location`.
- Use `parameters.alternate_location`, **not** `parameters.placement`. Placement is the SOAP `Query` parameter; `CustomObject::Query` ignores it (`payload_location` only reads `alternate_location`). The linter flags this as `E190`.
- `object` is `<namespace>__<object>` (e.g. `default__Vendor`) and must **not** end with `__c`. Rails splits with `rpartition('__')`, so `default__Vendor__c` becomes `object_name = "c"`. The linter flags this as `E187`.
- `parameters.ids` is a raw URL fragment, NOT a JSON array - use `{{ array | map: 'id' | join: '&ids=' }}` to build it from upstream data.
- The Custom Object schema is fetched from describe; field names are case-sensitive and the `__c` suffix counts. The linter only knows the static field set (no live describe in CI), so unfamiliar custom fields will surface as W177 warnings until added to `references/zuora-standard-fields.json`.
- Custom Objects are NOT updated synchronously after writes - the help text in the UI explicitly warns "The query API is not updated synchronously and may not reflect recent changes." Chain a `Delay` task or fall back to ID-based reads after a Create/Update if you need read-after-write consistency.

### CustomObject::Create

- **Purpose:** Create a Custom Object record. `parameters.fields` is a NESTED hash of the form `parameters.fields.<self.object>.<FieldName> = <value>`. Field names MUST exist in the Custom Object schema; the model rechecks at task_process and raises if any key is unknown.
- **UI partial:** [`app/views/tasks/partials/custom_object/_create.html.erb`](../../../workflow/rails/app/views/tasks/partials/custom_object/_create.html.erb) -- shared `partials/object_id_type` for object selection, then the field picker partial (`partials/custom_object/_field_select.html.erb`) followed by per-field inputs (`partials/_field.html.erb`). Required `__c` fields are auto-injected with empty values so they cannot be skipped.
- **Controller permit:** Fall-through (`tasks_controller.rb` L800-802); `object` rides on `common_params`; `parameters` is opaque.
- **Model validation ([`app/models/tasks/custom_object/create.rb`](../../../workflow/rails/app/models/tasks/custom_object/create.rb)):**
  - `validates :object, presence: true` (L2).
  - `task_setup_validation` (L5-17): when `object` present, `parameters.fields[<self.object>]` must be non-empty AND every required custom field (those ending in `__c` whose schema marks `required: true`) must appear in the supplied keys; otherwise `Missing fields: ...`.
  - `get_schema` calls `CustomObjectTask#schema` -> `Thread.current[:appinstance].get_custom_objects(entity_id:)` (cached per appinstance).
- **Runtime (`task_process` L19-57):**
  - For each `(k, v)` in `parameters.fields[self.object]`, raise `WorkflowError` if `k` is not in `schema.properties`.
  - Coerce `v` via `template_parse` and `properties[k]['type']`: `number => to_f`, `integer => to_i`, `boolean => to_bool`, else string.
  - POST `{records: [record]}` to `<base_url>/objects/records/<namespace>/<object_name>`. On success, `write_data(object_name: object, object_data: record_returned)` and `iterate_tasks(linkage_type: 'Success')`. The returned record contains `Id` plus the standard CO audit fields (`CreatedDate`, `UpdatedDate`, `CreatedById`, `UpdatedById`).

| Field | Required (when) | Source / UI control | Notes |
| --- | --- | --- | --- |
| `object` | Yes | Custom Object describe | Format: `<namespace>__<object>` (e.g. `default__Vendor`). |
| `parameters.fields` | Yes | Describe-driven nested form | NESTED hash: `parameters.fields.<self.object>.<FieldName>`. Top-level `parameters.fields[<FieldName>]` is silently ignored. |
| `parameters.fields.<self.object>.<FieldName>` | Yes (at least one) | Per-field input (text / boolean / number / picklist) | Liquid OK. Type coercion happens at task_process based on the schema (`number/integer/boolean/string`). |

**Common gotchas**

- `parameters.fields` MUST be nested under `<self.object>`. Hand-written workflows that put the field map directly under `parameters.fields` will fail validation with "Please select at least 1 field..." even when fields are present. The linter flags flat maps as `E188`.
- `object` must be `<namespace>__<object>` without a trailing `__c` (`E187`).
- There is **no** `parameters.placement` — Create always writes `Data.<self.object>` (`E190` if placement is present). Downstream Liquid must use `Data.<object>.Id` (e.g. `{{ Data.default__Vendor.Id }}`), not a task-name alias.
- All field names are validated against the LIVE schema at task_process - stale workflows that reference removed fields raise `WorkflowError` ("Field '<name>' was not found... Please refresh cache and update the task with the correct field.").
- Required `__c` fields are auto-injected by the UI as empty strings; explicitly populate them or save will fail with `Missing fields: ...`.
- Custom Objects are NOT readable synchronously after Create - the help text explicitly warns about eventual consistency. Use the returned `Data.<object>.Id` for follow-up Update/Delete instead of querying back.

### CustomObject::Update

- **Purpose:** Update a Custom Object record by UUID. `parameters.fields` is a NESTED hash (`parameters.fields.<self.object>.<FieldName> = <value>`); `object_id` MUST template-parse to a canonical UUID. Idempotent.
- **UI partial:** [`app/views/tasks/partials/custom_object/_update.html.erb`](../../../workflow/rails/app/views/tasks/partials/custom_object/_update.html.erb) -- shared `partials/object_id_type` with `id: true`, then the same field picker / per-field partial as Create. The reserved `fieldsToNull` field is special-cased to a multi-picklist (`field_lookup[:type] = 'multi-picklist'`).
- **Controller permit:** Fall-through (`tasks_controller.rb` L800-802); `object` and `object_id` ride on `common_params`; `parameters` is opaque.
- **Model validation ([`app/models/tasks/custom_object/update.rb`](../../../workflow/rails/app/models/tasks/custom_object/update.rb)):**
  - `validates :object, presence: true` (L2); `validates :object_id, presence: true` (L3).
  - `task_setup_validation` (L7-13): `parameters.fields[<self.object>]` must be non-empty (else `Please select at least 1 field...`).
  - `is_idempotent? == true`.
- **Runtime (`task_process` L19-73):**
  - Reject when `object` is blank (`This task configuration has no value in the Object field. Please delete and reconfigure this task.`).
  - Reject when any key in `parameters.fields[<self.object>]` is missing from `schema.properties` (`This task is referencing fields which are not part of the Custom Object definition. Please refresh your Workflow cache and reconfigure this task.`).
  - Coerce values per `properties[k]['type']` (same coercion table as Create).
  - `template_parse(self.object_id)`, then match against `/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/`. If no match, raise `Invalid Object ID. <id> is not a valid UUID.`
  - PATCH `<base_url>/objects/records/<namespace>/<object_name>/<uuid>` with `Content-Type: application/merge-patch+json`. On success, `write_data(object_name: object, object_data: record.merge('Id' => parsed_id))` and iterate Success. Note: Custom Objects do NOT echo back unmodified fields, so `Data.<object>` only contains the keys you sent plus `Id`.

| Field | Required (when) | Source / UI control | Notes |
| --- | --- | --- | --- |
| `object` | Yes | Custom Object describe | Format: `<namespace>__<object>`. |
| `object_id` | Yes | Text input (Liquid OK) | MUST template_parse to a canonical UUID at runtime. |
| `parameters.fields` | Yes | Describe-driven nested form | NESTED hash: `parameters.fields.<self.object>.<FieldName>`. |
| `parameters.fields.<self.object>.<FieldName>` | Yes (at least one) | Per-field input | Same coercion as Create. |
| `parameters.fields.<self.object>.fieldsToNull` | Optional | Multi-picklist | Reserved name - sent through as a list of fields to null out. |

**Common gotchas**

- `parameters.fields` MUST be nested under `<self.object>`; otherwise validation fails with "Please select at least 1 field..." even when fields appear present (`E188`).
- The record UUID is the **top-level** `object_id` attribute, not `parameters.id` (`E189`).
- `object` must be `<namespace>__<object>` without a trailing `__c` (`E187`).
- `object_id` is template_parsed at runtime - validate any embedded `{{ Data.* }}` references against the upstream task contracts before saving. Anything other than a canonical UUID (with hyphens) raises `Invalid Object ID`. Prefer `{{ Data.<object>.Id }}` from an upstream CustomObject::Create (Create has no placement alias).
- Custom Object PATCH uses `application/merge-patch+json`, so omitting a field leaves it unchanged. Use `fieldsToNull` (when supported by the object) to explicitly null fields.
- Like Query/Create, Custom Object reads are NOT synchronous - downstream Query against an updated record may return stale data for a few seconds.

### CustomObject::Delete

- **Purpose:** Delete a Custom Object record by UUID. If the workflow had previously bound `Data.<object>` to a single record matching this Id (or an Array containing it), that entry is removed from `new_data`. No positive `Data.*` writes; idempotent.
- **UI partial:** [`app/views/tasks/partials/custom_object/_delete.html.erb`](../../../workflow/rails/app/views/tasks/partials/custom_object/_delete.html.erb) -- one-line render of the shared `partials/object_id_type` (object: true, id: true). No per-task fields.
- **Controller permit:** Fall-through (`tasks_controller.rb` L800-802); `object` and `object_id` ride on `common_params`; `parameters` is opaque (only `strict_variables` carried).
- **Model validation ([`app/models/tasks/custom_object/delete.rb`](../../../workflow/rails/app/models/tasks/custom_object/delete.rb)):**
  - `validates :object, presence: true` (L2); `validates :object_id, presence: true` (L3).
  - `task_setup_validation` is empty (no extra checks).
  - `is_idempotent? == true`.
- **Runtime (`task_process` L14-29):**
  - `template_parse(self.object_id)`, then DELETE `<base_url>/objects/records/<namespace>/<object_name>/<uuid>`.
  - On non-200, raise `WorkflowError("Cannot delete <object> with Id=<uuid>")`.
  - On success, if `new_data[<object>]` is a Hash whose `Id` matches, delete the entry. If it is an Array, `delete_if {|obj| obj['Id'] == uuid}`. Then `iterate_tasks(linkage_type: 'Success')`.

| Field | Required (when) | Source / UI control | Notes |
| --- | --- | --- | --- |
| `object` | Yes | Custom Object describe | Format: `<namespace>__<object>`. |
| `object_id` | Yes | Text input (Liquid OK) | Liquid expressions are template_parsed at runtime; no UUID regex check (just sent to the API as-is). |

**Common gotchas**

- Unlike `CustomObject::Update`, Delete does NOT validate that `object_id` resolves to a UUID - an invalid id is sent verbatim and the API call fails with a generic `Cannot delete <object> with Id=<value>` `WorkflowError`. Validate upstream.
- Idempotent: re-running the task after a successful delete will return 404 from the API and surface the same error. Wrap in an `If` guard if you re-execute workflows that may have already deleted the record.
- The `new_data[<object>]` cleanup only matches on `Id` equality, so if upstream tasks bound `Data.<object>` under a different scope or with a different Id key, the cleanup is silently a no-op (downstream tasks may still see the stale binding).
