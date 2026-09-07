"""Task-type-scoped guidance for the planning LLM.

Injected into get_task_catalog responses so the LLM gets behavioral/API hints
alongside the parameter schemas. These hints capture domain knowledge that is
NOT part of the generated schema (e.g., REST-only, param relationships, Query
limits, when to use Export vs Query).

Ported from the old agent's workflow_agent/orchestration/planning_guidance.py.
"""

from __future__ import annotations

from typing import Collection

TASK_TYPE_GUIDANCE: dict[str, str] = {
    "Suspend": (
        "REST only. config.fields and config.options must nest under Amendment: use fields: { Amendment: { suspendPolicy: 'SpecificDate'|'EndOfLastInvoicePeriod'|'FixedPeriodsFromToday', contractEffectiveDate: <Date>, ... } }, options: { Amendment: { GenerateInvoice, ProcessPayments, targetDate, ... } } when set. "
        "suspendPolicy: SpecificDate, EndOfLastInvoicePeriod, or FixedPeriodsFromToday. For FixedPeriodsFromToday use suspendPeriods + suspendPeriodsType, for SpecificDate use suspendSpecificDate. extendsTerm optional. "
        "Requires object_id (Subscription ID)."
    ),
    "Resume": (
        "REST only. config.fields and config.options must nest under Amendment: use fields: { Amendment: { resumePolicy: 'Today'|'SpecificDate'|'FixedPeriodsFromSuspendDate'|'FixedPeriodsFromToday', contractEffectiveDate, ... } }. "
        "For FixedPeriods policies use resumePeriods + resumePeriodsType. For SpecificDate use resumeSpecificDate. extendsTerm optional. "
        "Requires object_id, which is the Subscription's ID."
    ),
    "Cancel": (
        "REST only. config.fields and config.options must nest under Amendment: use fields: { Amendment: { ... } }, options: { Amendment: { ... } }. "
        "cancellationPolicy required (EndOfCurrentTerm, EndOfLastInvoicePeriod, SpecificDate); cancellationEffectiveDate required when cancellationPolicy is SpecificDate. "
        "Requires object_id, which is the Subscription's ID."
    ),
    "InvoiceGenerate": (
        "REST only. config.fields must nest under Invoice: use fields: { Invoice: { InvoiceDate, TargetDate, IncludesOneTime, IncludesRecurring, IncludesUsage, IgnoreBlankInvoices, ... } }. "
        "Use EffectiveDate, SubscriptionIds (comma-separated or empty for all), AutoPost, AutoRenew as needed."
    ),
    "WriteOff": (
        "config.fields must nest under write_off: use fields: { write_off: { AdjustmentDate, ReasonCode, ... } }. "
        "ReasonCode required; must match configured codes in Zuora. AdjustmentDate required. "
        "Use for invoice balance write-off; do not use Create CreditMemo. Behavior depends on tenant: Invoice Settlement uses REST (creates CreditMemo), others use InvoiceItemAdjustments."
    ),
    "Email": (
        "Deliver real customer-facing messages -- the final workflow JSON must render as "
        "professional, responsive HTML. Full HTML is authored by a creative sub-agent at "
        "build time; the plan carries only a brief. "
        "Put these fields under `parameters.email`: "
        '`to[]` (recipient expressions, e.g. ["{{Data.BillToContact.WorkEmail}}"]); '
        "`from` (must be a verified sender in the tenant email config); "
        '`subject` (specific + customer-ready -- never "Notification"; interpolate the '
        'most identifying Liquid variable like "Payment reminder -- Invoice #{{Data.Invoice.InvoiceNumber}}"); '
        '`intent` (one-sentence purpose, e.g. "Notify the bill-to contact an invoice was posted and link the billing portal."); '
        "`data_vars` (list of Liquid expressions the body must surface, in priority order, "
        'e.g. ["{{Data.BillToContact.FirstName}}", "{{Data.Invoice.InvoiceNumber}}", '
        '"{{Data.Invoice.Amount | money}}", "{{Data.Invoice.DueDate}}", "{{Data.Invoice.URL}}"]); '
        '`tone` (optional -- "professional" | "friendly" | "urgent"; default "professional"); '
        '`cta` (optional -- {"label": "View Invoice", "href": "{{Data.Invoice.URL}}"}). '
        "PLAN-TIME BRIEF FIELDS (intent, data_vars, tone, cta) are consumed by the creative sub-agent at build time -- "
        "they are NOT final model fields. The model's actual fields include cc, bcc, name (display name), reply_to, "
        "return_path, preview_only, attachments, notification_history_enabled. "
        "Do NOT write the full HTML `template` in the plan -- build phase renders it. "
        "If the user supplies pre-approved HTML, pass it through `template`; otherwise omit "
        "`template` entirely. "
        'Example plan block: {"email": {"to": ["{{Data.BillToContact.WorkEmail}}"], '
        '"from": "billing@zuora.com", '
        '"subject": "Payment reminder -- Invoice #{{Data.Invoice.InvoiceNumber}}", '
        '"intent": "Remind the bill-to contact that an invoice is due within 3 days and link them to the payment page.", '
        '"data_vars": ["{{Data.BillToContact.FirstName}}", "{{Data.Invoice.InvoiceNumber}}", '
        '"{{Data.Invoice.Amount | money}}", "{{Data.Invoice.DueDate}}", "{{Data.Invoice.URL}}"], '
        '"tone": "friendly", "cta": {"label": "Pay Now", "href": "{{Data.Invoice.URL}}"}}}.'
    ),
    "If": (
        "if_clause must be a Liquid expression that evaluates to 'True' or 'False' "
        "(e.g. {% if Data.Invoice.size > 0 %}True{% else %}False{% endif %}). "
        "Always emit capitalized True/False branch literals — never lowercase true/false. "
        "Edges: edge_type True and False to target step_id. Use for binary decisions; use Logic::Case for 3+ branches. "
        "Prefer Query zero_query_proceed instead of If to gate on empty query results."
    ),
    "Logic::Case": (
        "case_clause: a field (e.g. Data.Invoice.Status) or Liquid expression that returns a string value (e.g. Posted, Draft, Canceled). "
        'case_condition MUST map each return value to the edge key: keys Case_1, Case_2, Case_3, etc.; values are the string values matching case_clause (e.g. {"Case_1": "Posted", "Case_2": "Draft", ...}). '
        "Edges use edge_type Case_1, Case_2, etc. to target step_id; Case_Else for no match. Include one edge per branch. "
        "For simple string matching set disable_regex='true' (default is regex). First matching case wins. Use for 3+ way branch; use If for binary."
    ),
    "Logic::Liquid": (
        "REQUIRED parameter: code (Liquid template to execute). "
        "Read upstream workflow data with Data.* (e.g. {{ Data.Invoice.Id }}, {% assign example = Data.Workflow %}). "
        "Use {% assign <name> = ... %} for each top-level assign; each is persisted under Data.Liquid.<name> "
        "(payload shape Liquid: { <name>: ... }) **after this task finishes**. "
        "Do NOT reference Data.Liquid.* anywhere inside this task's code — that namespace does not exist during "
        "execution of this task; only **later** tasks may use {{ Data.Liquid.<name> }}. "
        "For accumulation or shaping inside one task, use plain {% assign name = ... %} / {% capture %} only; "
        "never read Data.Liquid.<same_name> mid-template. "
        "Downstream tasks use {{ Data.Liquid.<name> }}. "
        "Use {% capture %} for complex string building. "
        "Stock Liquid filters may exist; Zuora adds many custom filters (different signatures than common docs, e.g. where). "
        "Call lookup_workflow_reference(topic='liquid_custom_filters') for the full Zuora filter list."
    ),
    "Query": (
        "Standard ZOQL via SOAP API. Results at Data.<object>[] (array). "
        "LIMITATIONS: hard limit of 2000 records (task FAILS if exactly 2000 returned); "
        "single object only (no JOINs); no ORDER BY (arbitrary result order); "
        "no GROUP BY / HAVING; no relative dates. "
        "PREFER QUERY WHEN: "
        "(1) SPECIFIC RECORD BY ID -- you have the exact ID from the event payload or a "
        "prior task (e.g. Query Invoice WHERE Id = '{{Data.Invoice.Id}}'). "
        "(2) REALTIME / UIACTION WORKFLOWS -- Export is not available in REALTIME; Query is the "
        "default for per-record events and UI-triggered flows. "
        "(3) PER-RECORD CHILD LOOKUPS INSIDE AN ITERATE -- fetch 1:N children for each parent "
        "(e.g. Query InvoiceItem WHERE InvoiceId = '{{Data.Invoice.Id}}'). Per-parent child "
        "count is typically <2000, so Query is safe and cheaper than Export. "
        "(4) ENRICHMENT IN A REALTIME FLOW -- fetch Account / Contact / Subscription fields "
        "that aren't in the event payload (e.g. Query Account by event Data.Invoice.AccountId "
        "before Email or Callout). "
        "(5) COUNT GUARANTEED <2000 -- any deterministic small dataset. "
        "USE SOMETHING ELSE WHEN: large/unknown volume ('get all X', polling, run results) -> "
        "use Export; multi-object JOINs -> Data::Link; hierarchical single record -> GraphQuery; "
        "custom objects -> CustomObject::Query. For the full decision matrix call "
        "lookup_workflow_reference(topic='data_retrieval'). "
        "SOAP OBJECT RESTRICTION: Query uses the SOAP API -- not all objects are available. "
        "Objects like CreditMemo, DebitMemo, and other billing-document objects have no "
        "SOAP-context fields and CANNOT be used with Query; use Export for those. "
        "Before selecting fields call lookup_zuora_schema(object_name=X, context_filter='soap') "
        "to confirm which fields are SOAP-accessible. Using an export-only field or object will "
        "cause the build step to remove it and may produce an empty fields list. "
        "CONFIG: config.fields MUST be an object keyed by object name with array of field "
        'names, e.g. {"Invoice": ["Id", "Balance", "AccountId"]}. NOT a comma-separated string. '
        "Use only field names from lookup_zuora_schema(context_filter='soap'). "
        "Set zero_query_proceed=false by default (true only when downstream tasks must run "
        "with empty results -- prefer this over a separate If task for empty-result gating)."
    ),
    "Export": (
        "Export ZOQL via SOAP. Unlimited records; BATCH / async only (NOT available in "
        "REALTIME / UIACTION). Produces a CSV file consumed by a downstream Iterate. "
        "UNIQUE CAPABILITIES (things Query cannot do): ORDER BY (ASC/DESC, multiple fields), "
        "GROUP BY (max 5 fields) + HAVING, aggregate functions (Sum, Count, Max, Min, Average), "
        "relative dates (today, now - 7 days), data-source ZOQL field paths for 1:1 / N:1 joins. "
        "PREFER EXPORT WHEN: "
        "(1) POLLING / UNKNOWN VOLUME -- 'get all X', 'fetch recent X', 'check for new X'. "
        "Use ORDER BY / relative-date filters to bound the window. "
        "(2) RUN-COMPLETION RESULTS -- BillingRunCompletion, PaymentRunCompletion, "
        "JournalRunCompletion. Runs produce large datasets (>2000 records is normal) so "
        "Query would fail. Filter with where_clause \"<Object>.SourceId = '{{Data.<RunObject>.ID}}'\" "
        "(e.g. \"Invoice.SourceId = '{{Data.BillingRun.ID}}'\"). Use Data::Link instead only "
        "if you need a SQL JOIN across multiple objects. "
        "(3) REPORTING / ANALYTICS -- any aggregation (COUNT, SUM, AVG), GROUP BY, or sorting. "
        "(4) TIME-BASED QUERIES -- 'last 30 days', 'since yesterday' via relative dates "
        "(e.g. where_clause Invoice.PostedDate > 'today - 30 days'). "
        "Relative dates and any modifiers must be quoted as strings, e.g. 'today - 30 days'. "
        "(5) BULK OPERATIONS -- processing many records without specific IDs. "
        "USE SOMETHING ELSE WHEN: single record by ID -> Query; multi-object JOIN -> Data::Link; "
        "single record with nested related objects -> GraphQuery; per-parent 1:N children inside "
        "Iterate -> Query (cheaper); REALTIME / UIACTION workflows -> Query. "
        "For the full decision matrix call lookup_workflow_reference(topic='data_retrieval'). "
        "JOIN ON THE UPSTREAM EXPORT: pull every 1:1 / N:1 related object up front via the "
        "multi-object `fields` shape (see FIELD KEY PLACEMENT below) so the Iterate body has the "
        "data without extra per-iteration Queries. Only spawn an inner Query for true 1:N "
        "relationships that would multiply rows. "
        "WHERE CLAUSE ORDER: filter conditions, GROUP BY, HAVING, ORDER BY, LIMIT -- must be in "
        "this order. "
        "OUTPUT: CSV file named <Object>__<task_id>.csv.zip (default zip=true) or .csv "
        "(zip=false); downstream Iterate auto-resolves the filename. "
        "CONFIG: config.fields MUST be an object keyed by object name(s) mapping field names "
        "to a value string. Valid values: 'true' (plain selection), 'Sum', 'Count', 'Max', "
        "'Min', 'Average' (aggregate functions). "
        'Example simple: {"Invoice": {"Id": "true", "Balance": "true"}, "Account": {"Id": "true", "Name": "true"}}. '
        'Example with aggregation: {"Invoice": {"Amount": "Sum", "Id": "Count", "Balance": "Max"}}. '
        "Aggregated output columns are prefixed: Sum_Amount, Count_Id, Max_Balance. "
        "When using aggregates, include a GROUP BY in where_clause. "
        "NOT a comma-separated string. Set zero_result_stop=true by default (false only when "
        'downstream tasks must run without data). zip defaults to "true". '
        "FIELD KEY PLACEMENT (critical): each field belongs under the object key that OWNS it "
        "in /describe. Related-object fields go under their OWN key, not under the base object. "
        'CORRECT: {"Invoice": {"Id": "true", "InvoiceNumber": "true"}, "Account": '
        '{"Id": "true", "AccountNumber": "true"}, "BillToContact": {"FirstName": "true", "LastName": "true", '
        '"WorkEmail": "true"}}. WRONG: {"Invoice": {"AccountNumber": "true", "WorkEmail": "true"}} '
        "(AccountNumber belongs on Account; WorkEmail belongs on Contact). "
        "MATCHING LIQUID PATHS: downstream references use the object key from `fields`, flat -- "
        "`{{Data.Account.AccountNumber}}`, `{{Data.BillToContact.WorkEmail}}`, NOT "
        "`{{Data.Invoice.Account.AccountNumber}}` or "
        "`{{Data.Invoice.BillToContact.WorkEmail}}`. Mis-nesting fields triggers "
        "`LIQUID_FIELD_NOT_SELECTED` errors."
    ),
    "Data::Link": (
        "SQL-like queries with full JOIN support (INNER, LEFT, RIGHT). Best for: complex multi-object queries, JOINs, large datasets. BATCH/async in production; unlimited records via file. "
        "REQUIRED parameter: query (SQL query string using Zuora Data Query syntax, supports Liquid, e.g. "
        "SELECT Account.Name, Subscription.Status FROM Subscription JOIN Account ON Subscription.AccountId = Account.Id). "
        "USE CASE PATTERNS - PREFER DATA::LINK FOR: "
        "(1) BILL RUN/PAYMENT RUN RESULTS WITH JOINS: 'Get invoices from bill run with account details', 'payment run results with invoice info' -> Data::Link (need JOIN across objects). "
        "(2) MULTI-OBJECT RELATIONSHIPS: 'Invoices with their line items', 'accounts with subscriptions and invoices' -> Data::Link (SQL JOIN required). "
        "(3) COMPLEX AGGREGATIONS: SQL-style GROUP BY with multiple tables -> Data::Link. "
        "(4) DENORMALIZED REPORTING: Combining data from multiple objects into flat structure -> Data::Link. "
        "WHEN TO USE: (1) Need SQL JOINs across multiple objects, (2) Complex SQL aggregations/grouping, (3) Need datahub/warehouse mode, (4) Run results requiring related object data. "
        "WHEN NOT TO USE: (1) Simple single-object query (use Query if <2000 or Export), (2) REALTIME/UIACTION workflow (not supported), (3) Single object without JOINs (use Export). "
        "DECISION: Multi-object JOINs -> Data::Link. Single object regardless of volume -> Export. Single record by ID -> Query. "
        "Output: async file (LinkRun__<task_id>.csv); iterate over file with data at Data.LinkData.* inside loop. "
        "synchronous mode (synchronous=true, Data.LinkData array, max 2000) only available in non-production tenants. "
        "Optional parameters: file_format (csv/tsv/dsv/json/json.zip, default 'csv'), compressed (default false), "
        "mode ('live' default, 'datahub', or 'warehouse'), index_join (default false, optimization for large joins), "
        "read_deleted (default false, include soft-deleted records), polling_interval (1-60 seconds, default '30'). "
        "Set zero_result_stop = true. Only set to false if the tasks that follow need to be executed without the data from this task."
    ),
    "GraphQuery": (
        "GraphQL queries for hierarchical/nested data. Best for: single record with nested related objects (e.g., Account -> Subscriptions -> RatePlans). Returns nested structure in one call; no JOINs needed. "
        "WHEN TO USE: (1) Need single record with related objects, (2) Hierarchical data structure, (3) Need nested format in one call, (4) Related collections <200 records each. "
        "WHEN NOT TO USE: (1) Simple single-object query (use Query), (2) Bulk/large data (use Export or Data::Link), (3) Related collections >200 records, (4) Need aggregations (use Export/Data::Link). "
        "VOLUME LIMITS: Max 200 records per related object collection. For larger related collections, use Data::Link or Export with iteration. "
        "REQUIRED parameters: query (GraphQL query string, supports Liquid), variables (JSON string of GraphQL variables, supports Liquid), "
        "baseObject (primary Zuora object type, lowercase), baseObjectID (ID of base object, supports Liquid), "
        "querySelection (JSON string defining query structure and field selections). "
        "Optional: placement (alphanumeric, defaults to baseObject value -- result stored at Data.<placement>). "
        "Only a single base object ID supported. Results in Data.<baseObject>[] with nested structure. Works in all workflow modes including REALTIME/UIACTION."
    ),
    "Iterate": (
        "One edge with edge_type For Each from this step to the first step inside the loop. Do not create linkages back to the Iterate task; iteration is automatic. "
        "REQUIRED task-level field: object -- the iteration source. Three modes: "
        "(1) Array name after Query: set object to the queried object name (e.g. 'Invoice' after Query object Invoice), data at Data.Invoice.Field. "
        "(2) Filename after Export/Data::Link: set object to the output filename (e.g. 'Invoice__<task_id>.csv.zip' for Export, 'LinkRun__<task_id>.csv' for Data::Link). "
        "(3) Custom Liquid: set object to 'CUSTOM LIQUID' and provide liquid_statement parameter with Liquid code. "
        "No Complete edge unless there is a step after the loop. Inside the loop use Data.<ObjectName>.Field (not [*]). "
        "Optional parameters: iteration_type ('Default' or 'Unique-Field'), iteration_field (field name for de-duplication when iteration_type='Unique-Field', first per value only). "
        "File processing options: file_type ('CSV' default or 'FIXED'), skip_headers (number of header rows to skip, default '0'), "
        "chunk_size (process N rows per iteration, default '0' = one at a time), delimiter (custom CSV delimiter), encoding (file encoding). "
        "Do not use Unique-Field for parent+child. For parent+child: Query parent, Iterate, inside loop Query child by parent ID."
    ),
    "Data::Aqua": (
        "AQuA (SOAP-based) queries with related-object joins and aggregate functions. BATCH only (not REALTIME/UIACTION). "
        "REQUIRED task-level field: object (primary Zuora object name, e.g. 'Invoice', 'Account'). "
        "fields: nested structure {ObjectName: {FieldName: {value: 'true'|'Max'|'Min'|'Count'|'Average'|'Sum', column: int, order: int}}}. "
        "Use 'true' for plain selection; use aggregate function name for computed fields. column controls output order. "
        "where_clause: ZOQL WHERE clause (without WHERE keyword), supports Liquid. "
        "Use ONLY field names from lookup_zuora_schema(context_filter='soap') in fields and where_clause. "
        "Optional: format (default 'csv'), encrypt (PGP encrypt output, default false), use_query_labels (use field labels in headers, default false), "
        "datetime_utc (default true), delay (0-60s initial delay, default '60'), partner/project (job tracking), "
        "convert_to_currencies (array of currency codes, e.g. ['USD', 'EUR']). "
        "Output: iterate over Aqua__<id>.csv; data in loop at Data.<object>.*; also Data.AQuA.<object> and Data.Files. "
        "Set zero_result_stop = true unless tasks that follow should run without data."
    ),
    "Callout": (
        "GENERAL-PURPOSE ACTION TASK -- use in two scenarios: "
        "(1) ZUORA API FALLBACK -- any Zuora REST operation with no dedicated task type "
        "(Orders, bill-run post/email, invoice post/email, usage, payment apply/unapply, "
        "etc.). Use `call_zuora_api` for one-off planning lookups; the **workflow itself** "
        "must use a Callout so the call runs at execute time. "
        "(2) EXTERNAL SYSTEM INTEGRATION -- POST/PUT/PATCH/DELETE to any third-party webhook "
        "or REST endpoint (ERP, CRM, tax engine, notification service, internal systems). "
        "Parameters sit directly on `parameters` (no `callout` sub-object). "
        "REQUIRED: `url` (string), `method` (GET/POST/PUT/PATCH/DELETE). "
        "Response stored at `Data.Callout` or custom `response_path`. "
        '`headers` default to [{"key": "Content-Type", "value": "application/json"}]; '
        "override only when needed -- format is a list of key-value dicts. "
        '`authorization` format: {"type": "none"} (dict, NOT a string). For external auth: call '
        '`call_workflow_api(action="list_auth_providers")`, narrow by `auth_type`, pick provider by '
        '`description`, set `authorization: {"type": "saved_provider:{id}"}`. Zuora REST → `type: "zuora"`. '
        "Manual creds fallback when user supplies them. Never put UUID in username/password. "
        "Build step auto-fills default callout params (retry_rules, validation, ...) and "
        "auto-populates `files` references from upstream Export / Data::Link tasks. "
        "TWO-PHASE BODY AUTHORING -- HARD RULE. Body is authored by the MAIN agent, never a "
        "creative sub-agent. Phase 3 (plan validation) and Phase 4 (build) have DIFFERENT "
        "parameter shapes for mutating Callouts (POST / PUT / PATCH); mixing them triggers "
        "the `CALLOUT_BODY_TOO_LARGE` warning and wastes tokens. "
        "(A) PLAN TIME (Phase 3) -- set `body_brief` (one-sentence payload description, e.g. "
        '"POST invoice header + line items to the tax-calc service for the current invoice.") '
        "and `body_vars` (Liquid expressions the payload must include, in priority order, e.g. "
        '["{{Data.Invoice.Id}}", "{{Data.Invoice.Amount}}", "{{Data.Invoice.InvoiceItems[*].Id}}"]). '
        "DO NOT set `raw_body` at plan time -- the only exception is when the user supplied an "
        "exact JSON payload. "
        "(B) raw_body IS RENDERED AUTOMATICALLY AT BUILD TIME -- do not expand it before "
        "calling build_workflow_definition. After the user confirms the plan, call "
        "build_workflow_definition directly with body_brief and body_vars in the plan as-is. "
        "The build tool renders raw_body from these fields at build time using the same "
        "LLM-at-build-time pattern as Email templates, including calling lookup_zuora_api_spec "
        "internally for Zuora API endpoints and inferring minimal payloads for external systems. "
        "Do NOT call lookup_zuora_api_spec or set raw_body yourself before the build call. "
        "Do NOT re-validate the plan after user confirmation -- confirmation is the gate. "
        "LIQUID IN raw_body: "
        'Quote Liquid strings: "id": "{{Data.Invoice.Id}}". Leave numbers and booleans unquoted: '
        '"amount": {{Data.Invoice.Amount}}, "active": {{Data.Subscription.IsActive}}. '
        "Use `{% for item in Data.Invoice.InvoiceItems %} ... {% endfor %}` for repeated sections "
        "(line-items, bulk payloads); drop `{% unless forloop.last %},{% endunless %}` between "
        "elements to keep JSON valid. "
        "Use `{% if %} / {% elsif %} / {% else %} / {% endif %}` to branch optional fields. "
        'Use filters: {{ amount | money }}, {{ date | date: "%Y-%m-%dT%H:%M:%SZ" }}, '
        '{{ name | downcase | strip }}, {{ "now" | date: "%Y-%m-%dT%H:%M:%SZ" }}. '
        "Every {{Data.X.Y}} reference must come from the event trigger or a preceding task -- "
        "walk `data_payload_trace` after each task to confirm availability; if missing, add a "
        "Query/Export upstream instead of inventing a path. "
        "If `build_workflow_definition` is called while a mutating Callout is missing `raw_body`, "
        "the tool returns an actionable error listing each task -- resolve with `lookup_zuora_api_spec` "
        "(or an inferred external-system payload) and re-call the build. "
        "Example plan-time block (brief only): "
        '{"url": "https://tax.example.com/v1/calc", "method": "POST", '
        '"body_brief": "Send invoice header + line items to the tax service for calculation.", '
        '"body_vars": ["{{Data.Invoice.Id}}", "{{Data.Invoice.InvoiceNumber}}", '
        '"{{Data.Invoice.Amount}}", "{{Data.Invoice.InvoiceItems[*].Id}}", '
        '"{{Data.Invoice.InvoiceItems[*].ChargeAmount}}"]}. '
        "Example post-approval block (raw_body populated before build): "
        '{"url": "https://tax.example.com/v1/calc", "method": "POST", "raw_body": '
        '"{\\n  \\"invoice_id\\": \\"{{Data.Invoice.Id}}\\",\\n  \\"total\\": {{Data.Invoice.Amount}},\\n'
        '  \\"line_items\\": [\\n    {% for item in Data.Invoice.InvoiceItems %}\\n'
        '    {\\"id\\": \\"{{item.Id}}\\", \\"amount\\": {{item.ChargeAmount}}}'
        '{% unless forloop.last %},{% endunless %}\\n    {% endfor %}\\n  ]\\n}"}.'
    ),
    "AsynchronousCallout": (
        "Initial HTTP callout then polls a follow-up endpoint until `finish_status` matches at `response_path` "
        "(or retries exhaust). Initial request params match Callout (`url`, `method`, `headers`, `authorization`, "
        "`raw_body`, ...); polling params use the `polling_` prefix (`polling_url`, `polling_method`, "
        "`polling_authorization`, ...). Result stored at `Data.<polling_payload_location>` from polling_validation. "
        "REQUIRED polling fields: `polling_url`, `polling_method`, `finish_status`, `response_path`. "
        "Use when an external system returns async job IDs and exposes a status URL — not for synchronous "
        "request/response (use Callout). "
        '`authorization` on the initial request matches Callout: {"type": "none"} by default. For external auth, call '
        '`call_workflow_api(action="list_auth_providers")`, narrow by `auth_type`, pick provider by `description`, '
        'set `authorization: {"type": "saved_provider:{id}"}`. Zuora REST → `type: "zuora"`. '
        "When the polling endpoint also requires auth, set the same provider on "
        '`polling_authorization: {"polling_type": "saved_provider:{id}"}` (field is `polling_type`, not `type`). '
        "Manual creds fallback when the user supplies them; never put a provider UUID in username/password. "
        "Two-phase body authoring applies to the initial request: use `body_brief` + `body_vars` at plan time for "
        "POST/PUT/PATCH; `raw_body` is rendered at build time."
    ),
    "NewProduct": (
        "SOAP only. config.fields must nest under Amendment: use fields: { Amendment: { RatePlanId, ContractEffectiveDate, ... } }. "
        "RatePlanId is ProductRatePlanId. Query Subscription first for subscription_id. object_id is the subscription ID."
    ),
    "RemoveProduct": (
        "SOAP only. config.fields must nest under Amendment: use fields: { Amendment: { RatePlanId, ContractEffectiveDate, ... } }. "
        "RatePlanId is SubscriptionRatePlanId (from existing subscription data), not ProductRatePlanId. Query Subscription first for subscription_id. object_id is the subscription ID."
    ),
    "Execute::WorkflowTask": (
        "ALWAYS SET EXPLICITLY (they have defaults but should be intentional): enable_polling, target_workflow_response, include_response_code. "
        "workflow_id: ID of sub-workflow to execute (preferred). workflow_name: name as fallback (fails if duplicate names exist). "
        "enable_polling: false (fire-and-forget, default) or true (wait for completion). When true, target workflow must have Logic::ResponseFormatter. "
        "target_workflow_response: 'last_task' (default) or 'last_response_formatter' -- which task output to return when polling. "
        "include_response_code: false (default) or true -- wraps response with URL, ResponseCode, ResponseBody, ResponseHeaders. "
        "advanced_mode: false (default, use fields array) or true (use raw_body JSON string). "
        "fields: array of {field_name, object_name, datatype, value, index} mappings for sub-workflow inputs. "
        "placement: where output is stored in Data (default 'ExecuteWorkflow'). "
        "replace_payload: false (default) or true -- replaces existing data at placement path instead of merging. "
        'Example minimal fire-and-forget: {"workflow_id": "{{Data.WorkflowId}}", "enable_polling": false, '
        '"target_workflow_response": "last_task", "include_response_code": false}.'
    ),
    "Delay": (
        "delay_time (REQUIRED): seconds as string or ISO datetime. Maximum delay 30 days. "
        "blocking: false (default, releases thread and re-enqueues -- efficient for long delays) or true (blocks thread, sync wait). "
        "Use for rate limiting, scheduling, or waiting for external processes."
    ),
    "Approval": (
        "Pauses for human approval. REQUIRED task-level field: delivery_method (enum: zuoraInbox, email, slack, webex, teams). "
        "REQUIRED parameter: approvalNote (message displayed to approvers, supports Liquid). "
        "Channel-specific REQUIRED parameters by delivery_method: "
        "zuoraInbox: approver_emails (email/username list, or '*' for any user with zuoraInbox access). "
        "slack: slackToken (bot token, store in GlobalConstants), slackBody (message, supports Liquid+Slack markdown). "
        "webex: webexToken (bot token), webexBody (message, supports Liquid). "
        "teams: teamsClientId, teamsClientSecret, teamsUsername, teamsPassword, teamsBody (supports Liquid). "
        "email: senderEmail, subjectEmail (supports Liquid), emailBody (HTML, supports Liquid). "
        "Optional: rejecter (restrict who can reject), selected_approvers (JSON string for multi-step). "
        "Result at Data.Approval with action ('approve'/'reject'), user, and optional data. Expires after 3 months."
    ),
    "Attachment": (
        "Attaches files from Data.Files to Zuora objects via REST. object: Account, CreditMemo, DebitMemo, Invoice, or Subscription. "
        "object_id = target record ID. files map: keys are filenames from Data.Files, each value has 'name' (display name) and 'upload' ('true'/'false'). "
        "At least 1 file must be selected. description: optional metadata note. Result at Data.Attachment."
    ),
    "Create": (
        'SOAP only. object = Zuora object type (Account, Contact, Subscription, etc.). fields: {"ObjectName": {"FieldName": "value"}}. '
        "Created record (including Id) stored at Data.<object>. Use ONLY valid SOAP API object names."
    ),
    "Update": (
        'SOAP only. object, object_id. fields: {"ObjectName": {"FieldName": "value", "fieldsToNull": ["FieldToNull"]}}. '
        "Supports [*] in object_id for batch updates in iteration context (e.g. {{ Data.Account[*].Id }})."
    ),
    "Delete": (
        "SOAP only. object, object_id. Not all objects support deletion (e.g. Invoice, Payment, Subscription cannot be deleted). "
        "Check Zuora SOAP API docs. Deletion is permanent. Child relationships may require child deletion first."
    ),
    "CustomObject::Create": (
        'object = custom object API name (e.g. default__CustomConfig). fields: {"object_name": {"Field__c": "value"}} nested under object name. '
        "Created record at Data.<object> with generated Id."
    ),
    "CustomObject::Update": (
        'object = custom object API name, object_id = record UUID. fields: {"object_name": {"Field__c": "value"}}. '
        "Nested under object name. Only specified fields are updated; others unchanged. Supports Liquid in values."
    ),
    "CustomObject::Delete": (
        "object = custom object API name, object_id = record UUID. Removes custom object record. Not all custom objects support delete."
    ),
    "CustomObject::Query": (
        "object = custom object API name. query (filter expression) or ids (direct ID filter). "
        "Results at Data.<object> or Data.<alternate_location>. zero_result_stop to stop workflow when no records."
    ),
    "Billing::BillRun": (
        "BillRunMode (REQUIRED): 'single' (one account), 'adhoc' (batch/BCD filter), or 'replicate' (copy existing run). "
        "single mode requires: AccountId, InvoiceDate, TargetDate. SubscriptionIds optional (comma-separated; blank = all). "
        "adhoc mode requires: InvoiceDate, TargetDate. Batch (default 'AllBatches'), BillCycleDay (default 'AllBillCycleDays') optional filters. "
        "replicate mode requires: SourceBillRunId (bill run ID or number to copy). "
        "AutoPost: true to auto-post invoices. AutoEmail: true to auto-email invoices. AutoRenewal: true to auto-renew subscriptions. "
        "NoEmailForZeroAmountInvoice: true to suppress email for $0 invoices. "
        "ChargeTypeToExclude: array of charge types to skip (e.g. ['OneTime', 'Recurring', 'Usage']). "
        "BillRunApi: 'v1/object/bill-run' (default) or 'v1/bill-runs' (supports SubscriptionIds filter). "
        "poll_time: max wait in 4-hour units (default '8' = 32 hours). Task polls every 2 minutes. "
        "Results at Data.BillRun."
    ),
    "Billing::ReverseInvoice": (
        "Only available with Invoice Settlement enabled. "
        "object_id (REQUIRED, top-level task field) = Invoice ID to reverse. "
        "memo_date: credit memo date (YYYY-MM-DD, defaults to today). Supports Liquid. "
        "apply_effective_date: effective date for applying the credit memo (YYYY-MM-DD). Supports Liquid. "
        "Creates a credit memo that fully offsets the invoice balance. "
        "Results at Data.ReverseInvoiceCreditMemo."
    ),
    "Billing::CurrencyConversion": (
        "OANDA only. currency_vendor, source_currency, target_currency, date required. Oanda.oauth required for authentication. "
        "currency_fields: map of output field names to Liquid expressions for amounts to convert. Results at Data.CurrencyConversion."
    ),
    "Billing::CustomBillingDocument": (
        "object_id (REQUIRED, top-level task field) = billing document ID (Invoice, CreditMemo, or DebitMemo). "
        "document_type: 'invoice' (default), 'CreditMemo', or 'DebitMemo'. "
        "template (REQUIRED) = HTML content for PDF. Supports Liquid. "
        "preload_data: true to auto-load related Zuora data into template context "
        "(Invoice/CreditMemo/DebitMemo, Account, BillToContact, SoldToContact, Subscription, RatePlan, "
        "RatePlanCharge, Product, InvoiceItem, TaxationItem, Usage -- max 200 per type). "
        "email_invoice: true to email the PDF after attachment. email_address: array of recipient addresses (Liquid supported). "
        "email_additional_email: true to include AdditionalEmailAddresses from contact. "
        "use_email_template: true to use the tenant's configured invoice email template. "
        "query_options: array -- add 'include_zero_dollar_items' to include $0 line items. "
        "advanced: {paper_size, header_template, footer_template, margin_top/bottom/left/right, skip_pdf_generate, generate_docx}. "
        "Output at Data.Files; PDF attached to billing document automatically."
    ),
    "Data::BillingPreviewRun": (
        "TargetDate (REQUIRED): billing preview through date (YYYY-MM-DD). Supports Liquid. "
        "storageOption: 'Database' (stored in Zuora, viewable in UI) or 'File' (CSV at Data.Files -- use for workflow processing). "
        "AssumeRenewal: 'None' (default, exclude renewals), 'Autorenew' (include auto-renewing), or 'All' (assume all renew). "
        "Batch: account batch filter ('Batch1'-'Batch50', or 'Batch51' for no-batch accounts). "
        "ChargeTypeToExclude: array of charge types to skip (e.g. ['OneTime', 'Recurring', 'Usage']). "
        "IncludeEvergreen: true (default) to include evergreen (no end date) subscriptions. "
        "Simulates invoice generation without creating real invoices. "
        "Results at Data.BillingPreviewRun and Data.Files when storageOption='File'."
    ),
    "Data::Warehouse": (
        "REQUIRED parameter: query (SQL against Zuora Data Warehouse, supports Liquid). SELECT only -- no DML. "
        "Batch mode only (async). For analytics and reporting. "
        "Results at Data.WarehouseResult[]."
    ),
    "Download::SFTP": (
        "REQUIRED parameters: host, folder_path, file_path. port defaults to '22'. "
        "credentials: {username, password | private_key, passphrase}. "
        "authorization.type: 'basic' (username+password, default) or 'key_based' (username+private_key). "
        "folder_path: remote directory to search. "
        "file_path: filename or glob pattern (e.g. '*.csv', 'report_*.zip'). First matching file is downloaded. "
        "case_insensitive: true to match filenames case-insensitively (e.g. '*.CSV' matches 'report.csv'). "
        "halt_no_file: true to succeed silently when no file matches (no error thrown); false (default) throws an error. "
        "post_processing_actions: '' (leave file, default), 'move_file', or 'delete_file' -- action taken on remote file after successful download. "
        "new_file_path: destination path for move_file; supports Liquid with OriginalFilePath, OriginalDirectory, OriginalFileName variables. "
        "Output stored at Data.Files (for use in downstream Upload/Email/Attachment tasks) and Data.SFTPDownload. "
    ),
    "Download::S3": (
        "Downloads files from Amazon S3 into workflow Data.Files. "
        "REQUIRED parameters: s3_provider_id (configured S3 provider ID in Zuora), bucket, path_pattern "
        "(S3 key pattern; wildcards supported, e.g. data/2024/report-*.csv; must not contain '..'). "
        "max_files defaults to 10 (max 30). no_file_action: 'error' (default), 'halt' (stop silently), or "
        "'success' (continue with no files). Prefer no_file_action over legacy halt_no_file. "
        "Optional destination_path (move after download) and new_filename (rename template). "
        "Output: matching files in Data.Files as S3__{task_id}__{filename}; metadata at Data.S3Download "
        "(CSV headers in Data.S3Download.Headers). Typical downstream: File::BulkDataLoader or Upload::S3."
    ),
    "File::DownloadFile": (
        "source (REQUIRED): 'zuora' or 'external'. "
        "source='zuora': file_id (required) = Zuora file ID. include_timestamp (default true) appends timestamp to filename. "
        "source='external': url (required). method: GET (default), POST, or PUT. "
        'For external auth: call `call_workflow_api(action="list_auth_providers")`, narrow by `auth_type`, '
        'pick provider by `description`, set `authorization: {"type": "saved_provider:{id}"}`. '
        "Manual fallback: authorization: {type: 'none' (default) | 'basic' | 'bearer' | 'api_key', "
        "username+password for basic, token for bearer/api_key}. "
        "filename: optional output name (defaults to URL or Content-Disposition header). "
        "For POST/PUT with form-data: body_type='form-data', form_datas=[{key, value}]. "
        "Output at Data.Files for use in downstream Upload/Email/Attachment tasks."
    ),
    "File::BulkDataLoader": (
        "Submits a CSV/JSONL file to the Zuora Bulk Data API (create job → upload → poll → download results). "
        "BATCH only -- not available in REALTIME, SYNC, SYNC_UI_ACTION, or RULE workflows. "
        "REQUIRED task-level field: object = input filename key in Data.Files (required at runtime even though "
        "not in schema required list). REQUIRED parameters: name, objectType, jobType "
        "('Import'|'Update'|'Delete'|'Cancel'). "
        "Only .csv and .jsonl input (zipped OK). Custom objects: objectType = namespace__ObjectName. "
        "Optional: fileType (csv|jsonl), hasHeaders (default true), delimiter, mappings, rowIdHeader "
        "(Update/Delete), poll_timeout (minutes, default 180, max 1440), "
        "fail_task_if_any_records_fail (default true). "
        "Results at Data.BulkDataLoader (jobId, jobSummary, successRows, errorRows); result files in Data.Files. "
        "Typical chain: Download::S3 → File::BulkDataLoader."
    ),
    "File::FileOperations": (
        "action (REQUIRED). Each action has different required params: "
        "Zip / Unzip: object = input filename from Data.Files. Output file stored at Data.Files. "
        "FileEncryption: object = input filename, public_key (required) = PGP public key. "
        "Optional: signer, signer_passphrase, signer_private_key, signer_public_key for signed encryption. "
        "encrypted_filename = output name (without .pgp extension). "
        "FileDecryption: object = encrypted filename, private_key (required) + passphrase (required) = PGP credentials. "
        "Optional signer_public_key for signature verification. decrypted_filename = output name. "
        "CSVCreation: field_name (required) = array of column headers. "
        "columns = map of file index ('1','2',...) to array of 1-based column indices to pull from that file. "
        "csv_filename = output name. "
        "ZipFiles: filename_regex (required) = regex to match filenames in workflow storage. zipped_filename = output name. "
        "AttachXMLtoPDF: object = PDF filename from Data.Files, xml_file (required) = XML filename from Data.Files. "
        "attached_filename = display name of embedded XML. "
        "PDFCreation: pdf_content (required) = binary/base64 PDF content (Liquid). pdf_filename = output name. "
        "All actions output to Data.Files. Store PGP keys in GlobalConstants and reference via Liquid."
    ),
    "File::ZuoraImport": (
        "object = CSV filename from Data.Files. action: CreateRevenueSchedule, UpdateRevenueSchedule, DeleteRevenueSchedule, UpdateAccountingCode, ImportFXRate. "
        "CSV must have columns appropriate for the action type. Polls for completion; success/error result files."
    ),
    "File::CustomPDF::CustomDocument": (
        "template (REQUIRED) = HTML content for PDF. Supports Liquid templates for dynamic content. "
        "Output at Data.Files as a PDF (and optionally DOCX). "
        "advanced: paper_size ('Letter' default, or 'A4', 'A3', 'Legal', 'Ledger', etc.), "
        "header_template / footer_template (HTML for repeating header/footer), "
        "margin_top/bottom/left/right (pixels, default 20), "
        "skip_pdf_generate: true to output HTML only (for debugging), "
        "generate_docx: true to also produce a .docx alongside the PDF. "
        "NOTE: This task converts HTML to PDF only. To generate a billing document PDF with automatic data loading, "
        "use Billing::CustomBillingDocument instead (it supports preload_data and direct attachment to Zuora objects)."
    ),
    "Logic::JSONTransform": (
        "processor (REQUIRED): 'JSONata', 'liquid', 'xml', or 'csv'. "
        "If processor is JSONata: template (required) = JSONata query/transform expression. version: '1.8.1', '1.8.6', or '2.0.2'. "
        "If processor is liquid: template (required) = Liquid template that outputs JSON. "
        "If processor is xml: data_source = Data path or Liquid expression for source data (default 'Data'). RootElement = root XML element name. "
        "If processor is csv: liquid_statement (required for csv, NOT 'template') = Liquid template outputting a JSON array; each element becomes a row. "
        "csv_headers: JSON object mapping source keys to header names, or omit to use object keys. csv_filename = output name. "
        "placement: Data key for result (default 'JSONTransform'). replace_payload: true to overwrite. "
        "Powerful for reshaping Data between tasks -- use before Callout to build request bodies, or after Export to transform results. "
        "Also use this task type to create CSV files."
    ),
    "Logic::XMLTransform": (
        "object (REQUIRED): 'XML Text' for inline input, or a filename from Data.Files. "
        "mode (REQUIRED): 'to_json' or 'to_xml'. "
        "to_json mode: converts XML to JSON stored at Data.XMLTransform. "
        "include_tag_attr: true to include XML attributes in JSON output. "
        "to_xml mode: applies XSLT to produce an output file. REQUIRED: template (XSLT content, must include xsl:output with method), "
        "filename (output name without extension -- extension determined by xsl:output method). "
        "xsd_input: optional XSD schema to validate the output XML. "
        "When object='XML Text': xml_text (REQUIRED) = inline XML content as Liquid string. "
        "When object is a filename: must reference an existing file in Data.Files."
    ),
    "Logic::CSVTranslator": (
        "action (REQUIRED): 'Filter', 'xml', 'to_json', or 'merge'. "
        "object: file from Data.Files (required for Filter, xml, to_json -- not for merge). "
        "Filter: Value (required) = string or regex to match. Column (column name) or column_number (1-based index) selects which column. "
        "filter_regex: true to treat Value as regex. OutputFormat: 'JSON' (stored in Data), 'CSV', or 'CSV.ZIP' (file). "
        "zero_result_stop: true to stop workflow when filter yields empty result. "
        "to_json: converts CSV to JSON at Data.<placement> (default 'CSVTranslator'). replace_payload: true to overwrite. "
        "xml: converts CSV to XML file in Data.Files. "
        "merge: files (required) = map of filenames to {selected: true, order_index: '1'}. "
        "csv_filename: output name for merged file (default 'MergedCSV'). "
        "placement: custom Data key for JSON output. Must be alphanumeric + underscores only."
    ),
    "Logic::Lambda": (
        "To invoke EXISTING function: LambdaFunction = function name (without WF- prefix). Function must be tenant-owned. "
        "async_invoke: false (sync, default, max 4 min via TimeOut) or true (async callback, max 10 min via TimeOutAsync; requires tenant async_lambda feature). "
        "Lambda receives Data, Credentials, TaskInstance, WorkflowInstance, GlobalConstants in the event payload. "
        "To UPLOAD NEW function: use FunctionName, Handler (e.g. 'index.handler'), Runtime (e.g. 'nodejs18.x', 'python3.10'), "
        "Memory (128-10240 MB string), TimeOut (<=240s for sync) or TimeOutAsync (<=600s for async). "
        "env_var: optional array of {env_key, env_val} environment variables. "
        "Store sensitive values in GlobalConstants; access via Credentials in Lambda event."
    ),
    "Logic::Merge": (
        "Merges parallel branches into single flow. Waits for all incoming branches. merge_paths and merge_start are typically auto-calculated. "
        "Combines data from all branch endpoints. parameters MUST be {} -- server computes merge_paths. "
        "Never add For Each linkages on paths leading to a Merge."
    ),
    "Logic::ResponseFormatter": (
        "REQUIRED: processor, template, code. "
        "processor: 'Liquid' or 'JSONata'. "
        "template: must output valid JSON (object or array). "
        "code: HTTP status code string (e.g. '200', '400', '500') -- required by schema even for internal sub-workflow use. "
        "parent_workflow_status: 'Success' (default) or 'Error' -- signals the parent workflow's outcome when called via Execute::WorkflowTask. "
        "Required when Execute::WorkflowTask has enable_polling=true and target_workflow_response='last_response_formatter'. "
        "Output returned to calling workflow or API at Data.ResponseFormatter."
    ),
    "Mediation::SendEvents": (
        "POSTs usage events JSON to Zuora Usage Bulk API for a mediation meter. "
        "REQUIRED parameters: meter_id (meter globalId from Mediation/meters API), json_body "
        "(JSON string, Liquid-rendered -- typically an array of event objects). "
        "json_body must parse as valid JSON after Liquid rendering. "
        "Response stored at Data.MediationSendEventsResponse. "
        "Build events upstream with Logic::Liquid or Logic::JSONTransform before this task."
    ),
    "Notifications::SMS": (
        "All SMS fields nest under a required 'sms' sub-object on parameters: parameters.sms.numbers and parameters.sms.message. "
        "numbers: array of E.164 phone numbers (e.g. ['+14155551234']). Supports Liquid per element. "
        "message: SMS text body. Supports Liquid. Standard SMS is 160 characters; longer messages are split into multiple billed segments. "
        'Via Twilio. Example: {"sms": {"numbers": ["+14155551234"], "message": "Invoice {{Data.Invoice.InvoiceNumber}} is due."}}.'
    ),
    "Notifications::Kafka": (
        "topic_name, message (JSON string). Internal use only; requires Zuora internal context. BusinessEvent topic uses Avro encoding."
    ),
    "Payment::PaymentRun": (
        "action (REQUIRED): 'create', 'update', 'get', or 'delete'. "
        "create requires: mode + date (TargetDate or RunDate -- mutually exclusive). "
        "mode: 'single' (requires AccountId), 'adhoc' (optional Batch, BillCycleDay, Currency, PaymentGatewayId, BillingRunId), "
        "or 'file_data' (requires InputFile from Data.Files -- CSV/JSON with accountId, amount, documentId). "
        "get/delete require: PaymentRunId. "
        "TargetDate: collect invoices due on or before this date. RunDate: schedule for future execution. "
        "Collection behavior flags: "
        "CollectPayment (default true), ApplyCreditBalance (default false), ConsolidatedPayment (default false). "
        "Invoice Settlement flags: AutoApplyCreditMemo (default false), AutoApplyUnappliedPayment (default false). "
        "ProcessPaymentWithClosedPM: true to attempt even when payment method is closed. "
        "retry_on_timeout: true to auto-retry on API timeout. "
        "Polls for completion. Results at Data.PaymentRun."
    ),
    "Payment::GatewayReconciliation": (
        "action: settle, reject, reverse. PaymentId required. SettledOn required for settle; Amount for reverse. "
        "Updates payment status from gateway. Results at Data.GatewayReconciliation."
    ),
    "Reporting::RunReport": (
        "object_id (REQUIRED, top-level task field) = pre-saved report ID (no runtime user-input params supported). "
        "viewType: 'Detail' (row-level, default) or 'Summary' (aggregated/pivoted). "
        "default_filters: true to use the report's saved filter values. "
        "pivoted: true to export pivoted data (Summary view only). "
        "filename: custom output filename (defaults to '<viewType>.csv'). "
        "Polls for completion. Results at Data.Files and optionally Data.Report."
    ),
    "Reporting::OracleFusionReport": (
        "SOAP. url (Oracle BI Publisher endpoint), username, password, report_absolute_path (catalog path). from_date, to_date for report params. "
        "Output at Data.Files (CSV)."
    ),
    "Revenue::AllocateAction": (
        "RevPro-only. Runs an allocation action on a Revenue Contract. "
        "REQUIRED: rc_id, object_version (optimistic lock from prior Revenue API response -- refresh after each mutation), "
        "action (Revenue API identifier, e.g. REALLOCATE, ALLOCATION_ELIGIBLE). "
        "Optional output_key (default 'Revenue' → Data.Revenue.*). Most string params support Liquid."
    ),
    "Revenue::ApplyImpairment": (
        "RevPro-only. Applies impairment entries to one or more RC lines. "
        "REQUIRED: rc_id, object_version, lines (array of ≥1 entry, each with id, comments, impairment_type). "
        "lines is an array, not a hash (contrast Revenue::Hold RC-mode lines). "
        "Optional output_key (default 'Revenue' → Data.Revenue.*)."
    ),
    "Revenue::ApplyVc": (
        "RevPro-only. Applies variable consideration to a specific RC line. "
        "REQUIRED: rc_id, rc_line_id, vc_type_id, apply_value, object_version, vc_rule_type "
        "('E' Estimate, 'A' Allocation, 'S' Constraint). "
        "Optional: apply_type (AMOUNT|PERCENT), apply_on, comments, calc_method, int_freq, int_rate, "
        "start_date, end_date, output_key. Refresh object_version after each mutation."
    ),
    "Revenue::CloseRcTask": (
        "RevPro-only. Closes an RC task on a Revenue Contract (open/close lifecycle). "
        "REQUIRED: rc_id, object_version. Pair with Revenue::OpenRcTask for the open side. "
        "Optional output_key (default 'Revenue' → Data.Revenue.*)."
    ),
    "Revenue::CreateManualRc": (
        "RevPro-only. Creates a manual Revenue Contract from existing RCs or POBs/doc lines. "
        "REQUIRED: mode ('rc_level'|'pob_level'). No object_version -- creates new RCs. "
        "rc_level requires rc_ids (comma-separated). "
        "pob_level requires rc_pob_ids (array of {id, retain: 'true'|'false'}) or doc_line_ids (comma-separated). "
        "Optional: comments, sec_atr_val, grouping_template, output_key."
    ),
    "Revenue::DeferCost": (
        "RevPro-only. Defers cost on a specific contract line. "
        "REQUIRED: rc_id, line_id, object_version, comments, cost_type_id. "
        "Optional: release_amount, release_percentage, release_quantity, rule_start_date, rule_end_date, output_key. "
        "Line-level only (unlike DeferRevenue which supports RC/POB level). Mirror: Revenue::ReleaseCost."
    ),
    "Revenue::DeferRevenue": (
        "RevPro-only. Defers revenue at RC or POB level. "
        "REQUIRED: rc_id, object_version, comments, level ('RC'|'POB'). pob_id required when level=POB. "
        "Optional: rc_pob_id (RC-level body field), start_date, end_date, release_amount, release_percentage, "
        "cont_pros_type, output_key. Mirror: Revenue::ReleaseRevenue."
    ),
    "Revenue::EditLine": (
        "RevPro-only. Edits custom attributes on a single RC line. "
        "REQUIRED: rc_id, line_id, comments. object_version is optional (unusual among Revenue mutations). "
        "Populate only atr1–atr60, num1–num15, date1–date5 fields being changed; omitted fields are not sent. "
        "Optional output_key (default 'Revenue' → Data.Revenue.*)."
    ),
    "Revenue::EditPobAttributes": (
        "RevPro-only. Edits POB attributes at single-POB or bulk RC level. "
        "REQUIRED: rc_id, object_version, mode ('pob_level'|'rc_level' -- NOT 'Line'/'POB'/'RC'). "
        "pob_level also requires: pob_id, pob_template_id, name, pob_version, expiry_date, lead_line_id, comments. "
        "rc_level also requires: items (array ≥1 entry with id, name, pob_template_id, pob_version, expiry_date, "
        "lead_line_id, comments per POB). Optional output_key."
    ),
    "Revenue::ExpireVc": (
        "RevPro-only. Expires variable consideration from an RC line price adjustment. "
        "REQUIRED: rc_id, rc_line_price_adjustment_id (existing VC adjustment ID, not line ID), "
        "amount, object_version. Optional output_key."
    ),
    "Revenue::GenerateForecast": (
        "RevPro-only. Generates revenue forecast for an RC. "
        "REQUIRED: rc_id only -- no object_version needed. "
        "Optional output_key (default 'Revenue' → Data.Revenue.*)."
    ),
    "Revenue::Hold": (
        "RevPro-only. Applies or releases revenue holds at RC, POB, or Line level. "
        "REQUIRED: rc_id, hold_id (hold template ID), mode ('RC'|'POB'|'Line'). "
        "Conditional: pob_id when mode=POB; line_id when mode=Line; reason when operation=release. "
        "operation: 'apply' (default) or 'release'. "
        "RC-mode apply: lines is a hash keyed by index with {id, rcPobId, rpcNum, holdComments} per entry. "
        "RC-mode release: lines hash with {id, rcPobId, rpcNum, releaseComments, releaseReason} plus top-level reason. "
        "Line mode uses rpc_num and hold_comments. object_version optional but recommended. Optional output_key."
    ),
    "Revenue::LinkDelink": (
        "RevPro-only. Links or delinks RCs, POBs, or document lines. "
        "REQUIRED: operation ('link'|'delink'), target ('rc'|'pob'|'line'), rc_id, object_version -- "
        "use separate operation and target fields, NOT compound strings like 'link-rc'. "
        "Conditional: pob_id when target is pob or line; doc_line_id when delink+line; "
        "target_rc_ids (comma-separated) when link+rc; doc_line_ids (comma-separated) when link+line. "
        "Link-line: provide lead_line_id or rc_pob_id. Optional: comments, output_key."
    ),
    "Revenue::MovePob": (
        "RevPro-only. Moves a POB (or specific line) to a derived POB within an RC. "
        "REQUIRED: rc_id, rc_pob_id (source POB), rc_derived_pob_id (target derived POB), "
        "action (e.g. MOVE), comments, object_version. "
        "Optional: line_id (move one line; omit to move all POB lines), derived_pob_val, output_key."
    ),
    "Revenue::OpenRcTask": (
        "RevPro-only. Opens an RC task on a Revenue Contract (counterpart to CloseRcTask). "
        "REQUIRED: rc_id, object_version. Optional output_key (default 'Revenue' → Data.Revenue.*)."
    ),
    "Revenue::ReleaseCost": (
        "RevPro-only. Releases deferred cost on a contract line. "
        "REQUIRED: rc_id, line_id, object_version, comments, cost_type_id. "
        "Optional: release_amount, release_percentage, release_quantity, rule_start_date, rule_end_date, output_key. "
        "Same shape as Revenue::DeferCost."
    ),
    "Revenue::ReleaseRevenue": (
        "RevPro-only. Releases deferred revenue at RC or POB level. "
        "REQUIRED: rc_id, object_version, comments, level ('RC'|'POB'). pob_id required when level=POB. "
        "Optional: rc_pob_id, start_date, end_date, release_amount, release_percentage, cont_pros_type, output_key. "
        "Same shape as Revenue::DeferRevenue."
    ),
    "Revenue::SwitchAllocation": (
        "RevPro-only. Switches the allocation method on an RC. "
        "REQUIRED: rc_id, object_version. Optional output_key (default 'Revenue' → Data.Revenue.*)."
    ),
    "Revenue::SwitchLeadLine": (
        "RevPro-only. Changes the lead line on a POB. "
        "REQUIRED: rc_id, line_id (new lead line), rc_pob_id, object_version. Optional output_key."
    ),
    "Revenue::UnfreezeRc": (
        "RevPro-only. Unfreezes a frozen Revenue Contract. "
        "REQUIRED: rc_id, action (e.g. UNFREEZE), object_version. "
        "Optional: change_mod_date ('Y' default|'N' -- whether to update modification date), output_key."
    ),
    "Revenue::VoidBilling": (
        "RevPro-only. Voids a billing document on an RC. "
        "REQUIRED: rc_id, bill_doc_number, reason. No object_version. "
        "Optional: comment, output_key (default 'Revenue' → Data.Revenue.*)."
    ),
    "Script::JavaScript": (
        "REQUIRED parameter: code (JavaScript to execute). Has access to custom_data: WorkflowInstance, WorkflowSetup, TaskInstance, GlobalConstants. "
        "Must return a value; stored at Data.<placement>. "
        "timeout: execution timeout in seconds (default '20', can be overridden by tenant-level js_timeout). "
        "placement: Data key for output (default 'JavaScript', e.g. 'ProcessedData' stores at Data.ProcessedData). "
        "replace_payload: false (default, merges with existing data) or true (replaces data at placement path)."
    ),
    "UI::Page": (
        "UI-mode workflows only. html_code (HTML body), stylesheet_code (CSS), javascript_code (JS) -- all support Liquid when parse_liquid=true (default). "
        "route[] defines custom navigation actions (e.g. ['approve','reject']); each route creates a 'Page:<route>' linkage type. "
        "Call _submitRoute('<route>') from JS to trigger navigation. _zuora_endpoint({url, method, body}) for authenticated Zuora API calls from page. "
        "parse_liquid: true (default) processes Liquid in HTML/CSS/JS; false for static pages or to avoid Liquid/JS conflicts. "
        "page_id: optional identifier for tracking/analytics. "
        "Pauses until user submits via _submitRoute."
    ),
    "UI::Stop": (
        "Stops UI-mode workflow. Terminal task for UI workflows. Sends stop signal to custom UI channel. "
        "redirection_path: optional URL path or Liquid template to redirect the UI after the stop signal."
    ),
    "UI::WebShare": (
        "Shareable web page with JWT-secured URLs. REQUIRED parameter: html_code (HTML content, supports Liquid when parse_liquid=true, default). "
        "route[] defines callback actions (e.g. ['approve','reject']); each route creates a 'Webshare:<route>' linkage type. "
        "parse_liquid: true (default) processes Liquid in html_code. "
        "timeout: {days (1-7, default '1'), hours (0-23), minutes (0-59), seconds (0-59)} -- max 7 days total. "
        "After timeout, 'Timeout' linkage fires. "
        "files: file references from Data.Files to include/reference in the web page. "
        "Pauses until user submits via callback or timeout. Results at Data.WebContent, Data.UserContent."
    ),
    "Upload::SFTP": (
        "REQUIRED parameters: host, folder, files. port defaults to '22'. "
        "credentials: {username (required), password | private_key, passphrase}. "
        "Field is 'username', NOT 'login' or 'user'. "
        "authorization.type: 'basic' (username+password, default) or 'key_based' (username+private_key). "
        "Store passwords and private keys in GlobalConstants and reference via Liquid. "
        "create_folder: true to create the remote directory if absent. "
        "permissions: optional Unix octal string (e.g. '644') applied to uploaded files. "
        "files: REQUIRED map of filenames from Data.Files to per-file config. "
        "Keys must match filenames produced by upstream tasks (Export, Download::SFTP, File::DownloadFile, etc.) as they appear in Data.Files. "
        "FILE KEY NAMING: Export produces <Object>__<export_task_id>.csv (or .csv.zip). "
        "The numeric ID in the key is the id of the PRODUCER task, NOT the Upload task. "
        "Example: if Export task (id=1) exports Invoice with zip=false, the key is 'Invoice__1.csv'. "
        "Each value MUST have 'upload: true' -- this field is required by the schema. "
        "Optional 'name' renames the file on the remote server. "
        'Example files block: {"Invoice__1.csv": {"upload": true, "name": "invoices_export.csv"}}. '
        "file_ids: optional list of Zuora file IDs to pull from Zuora storage and upload. "
        "files cannot be empty -- at least one entry required."
    ),
    "Upload::FTP": (
        "REQUIRED parameters: host, folder, files. "
        "call_type: 'FTP' (default, unencrypted). "
        "port defaults to '21'. "
        "credentials: {username, password} -- field is 'username', NOT 'login' or 'user'. "
        "ssl_verify: 'OpenSSL::SSL::VERIFY_PEER' (default, recommended). "
        "files: REQUIRED map of filenames from Data.Files to per-file config. "
        "Keys must match filenames produced by upstream tasks (Export, Download::SFTP, File::DownloadFile, etc.) as they appear in Data.Files. "
        "FILE KEY NAMING: Export produces <Object>__<export_task_id>.csv (or .csv.zip). "
        "The numeric ID in the key is the id of the PRODUCER task, NOT the Upload task. "
        "Example: if Export task (id=1) exports Invoice with zip=false, the key is 'Invoice__1.csv'. "
        "Each value MUST have 'upload: true' -- this field is required by the schema. "
        "Optional 'name' renames the file on the remote server. "
        'Example files block: {"Invoice__1.csv": {"upload": true, "name": "invoices_export.csv"}}. '
        "file_ids: optional list of Zuora file IDs to pull from Zuora storage and upload. "
        "files cannot be empty -- at least one entry required."
    ),
    "Upload::S3": (
        "Uploads files from workflow Data.Files to Amazon S3. "
        "REQUIRED parameters: s3_provider_id (configured S3 provider ID in Zuora), bucket, path "
        "(S3 key prefix; must not contain '..'). "
        "Must select at least one file via files map and/or file_ids. "
        "files: map of filenames from Data.Files to per-file config. "
        "Keys must match upstream producer filenames as they appear in Data.Files "
        "(Export, Download::S3, File::DownloadFile, etc.). "
        "Each files entry MUST have 'upload: true'. Optional 'name' renames the object key suffix. "
        "path is prefix only -- filename appended from workflow file or files[id].name. "
        'Example: {"Invoice__1.csv": {"upload": true, "name": "invoices_export.csv"}}.'
    ),
    "Usage::ImportUsage": (
        "object = CSV filename from Data.Files containing usage records. use_active_rating: true for Active Rating API (async, validation), false for legacy v1/usage. "
        "Polls for completion. Input file uploaded to Zuora for processing."
    ),
}


def get_scoped_guidance(task_types: Collection[str]) -> str:
    """Return guidance section only for task types that have an entry."""
    parts = [
        f"### {tt}\n{TASK_TYPE_GUIDANCE[tt]}"
        for tt in sorted(task_types)
        if tt in TASK_TYPE_GUIDANCE
    ]
    if not parts:
        return ""
    return "\n\n## Behavioral Guidance for These Tasks\n\n" + "\n\n".join(parts)
