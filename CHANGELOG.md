# Changelog

## [1.5.4] - 2026-08-17

### Added
- Dynamic pricing rate cards now support **effective dating**: schedule a future price change by adding a new rate card row with a later `EffectiveDate` — the prior price is preserved as bounded history automatically, with no need to delete old rows
- `cpq-salesforce-fields.json` — new static field catalog for `zqu__Quote__c`, `zqu__QuoteRatePlan__c`, `zqu__QuoteRatePlanCharge__c`, and related objects; powers linter rules EAPEX050/052, WAPEX050/051, and WJS080

### Improved
- CPQ JS skills now generate a colocated `<componentName>Helper.js` module for non-trivial hook logic, keeping hook methods thin and business logic testable in isolation
- CPQ JS skills and review now flag incorrect reads from `quoteState.quote` (use `getQuote()`/`getQuoteField(...)`), missing `.record` on wrapper object field access, and direct iteration of `quoteState.productTimelines` (use `getProductTimelines()`)
- CPQ Apex build and design skills validate every `zqu__*`/`Zuora__*` field against `cpq-salesforce-fields.json` before generating SOQL, DML, or `quoteParams.put(...)` maps — preventing hallucinated field names and type mismatches at generation time
- CPQ validate skill runs the updated `lint-cpq-apex.js` and `lint-cpq-hooks-events.js` linters against generated artifacts for schema, hook-signature, and ZQFClient correctness
- Dynamic pricing build skill now requires an approved design artifact before mutating the catalog; build skill recognizes `Account.BillToContact` and `Account.SoldToContact` as valid attribute mapping objects

## [1.5.3] - 2026-08-05

### Improved
- Workflow linter now catches four new Custom Object anti-patterns: trailing `__c` on object names (E187), flat `parameters.fields` instead of the required nested shape (E188), `parameters.id` instead of top-level `object_id` for Update/Delete (E189), and `parameters.placement` on Query/Create/Update (E190)
- Workflow build and reference docs updated to document all four Custom Object shape rules with linter codes so generated workflows pass E187–E190 on first import
- Context skill now shows a setup guide with environment URLs when the zuora-mcp server is not registered, instead of failing silently

## [1.5.2] - 2026-07-28

### Improved
- Workflow skills and linter updated with accurate built-in data keys (`ExecutionDateTimeUTC`, `WorkflowRunUser`); removed stale `UIAction` scope that is no longer seeded at runtime
- Meter build skill now clearly separates the create-meter and importable-meter JSON formats — the correct skeleton is selected based on the requested output
- Meter linter gains operator config schema validation (rule E143) using bundled JSON schemas; `SUBSCRIPTION_LOOKUP` operator schema added to references

## [1.5.1] - 2026-07-13

### Improved
- Tenant config design skill now infers custom fields from business artifacts — identifies fields with no native Zuora representation, maps them to the correct object type, and checks existing tenant custom fields before proposing new ones

## [1.5.0] - 2026-07-13

### Added
- New skills: `zuora-tenant-config-design` and `zuora-tenant-config-build` — infer Zuora tenant settings from business documents or descriptions and apply them directly to your tenant via the Settings API

### Improved
- Workflow design and build skills now guide correct async polling patterns, error summaries via workflow task query, and away from unnecessary custom objects
- Meter skills updated for the renamed `manage_meters` and `manage_meters_run` MCP tools; added a custom importable meter skeleton and expanded validation rules

## [1.4.2] - 2026-06-29

### Added
- IS migration now assesses your Data Warehouse layer and generates IS-compatible SQL rewrites for legacy settlement objects (`InvoicePayment`, `RefundInvoicePayment`, `CreditBalanceAdjustment`), adapting to dbt, Fivetran, or raw SQL pipelines

## [1.4.1] - 2026-06-17

### Added
- New UAT skill set: `zuora-uat-design`, `zuora-uat-build`, and `zuora-uat-run` for designing, generating, and executing UAT test suites
- UAT reference docs, execution scripts, test utilities, and a starter template with pytest scaffolding

## [1.4.0] - 2026-06-10

### Added
- New CPQ skill set: `zuora-cpq-apex-design`, `zuora-cpq-apex-build`, `zuora-cpq-js-design`, `zuora-cpq-js-build`, `zuora-cpq-migration-design`, `zuora-cpq-validate`, and `zuora-cpq-review`
- CPQ reference library covering hooks, events, quote state model, ZQFClient, Component Library, global Apex methods, registration, and patterns
- Local linter scripts `lint-cpq-apex.js` and `lint-cpq-hooks-events.js` for pre-submit validation of CPQ artifacts
- LWC headless/sidebar and Visualforce/Apex starter templates

## [1.3.5] - 2026-06-05

### Added
- Local linter scripts: `scripts/lint-meter-json.js` and `scripts/lint-workflow-json.js` for pre-import structural and semantic validation

### Improved
- Workflow build and design skills now correctly handle tenant-custom events — a non-standard event name is kept in `event_triggers[]` with `event_trigger: true` rather than dropping the trigger
- Fixed linter rule code `E121` → `E007`; added new rule `W123` (event parameters configured but `event_trigger` flag not set)
- Workflow triggers reference updated to clarify that multiple trigger flags are valid on one workflow

## [1.3.4] - 2026-06-05

### Added
- New reference docs for meter script codegen (JS/Python signatures, per-operator patterns) and workflow Liquid filter signatures sourced from `filters.rb`

### Improved
- Meter design skill now classifies requests upfront — operator questions, troubleshooting, and existing-meter review are answered directly without triggering the full intake flow
- Meter build skill adds a script fast-path for code/snippet requests, and now runs API `validate_meter` before the local linter; can call `create_meter` after user confirmation
- Workflow build skill adds correctness checks for bill run filter limits, Zuora callout auth, Data Query consolidation, Liquid shim minimization, CRUD update consolidation, duplicate `/v1/` URLs, and run-prompt `default: null` crash
- Fixed workflow event special-token list — only tokens in `$event_special_tokens.tokens` are safe; multi-trigger workflows (e.g. on-demand + scheduled) are now explicitly supported

## [1.3.3] - 2026-05-29

### Improved
- Workflow design and build now correctly guide task-type selection — `Query` as the default data-read, `Logic::Liquid` over `Script::JavaScript` for transforms, and clearer distinctions between `Export`, `Data::Aqua`, and `Data::Warehouse`
- Error handlers in workflows no longer reference failed task output scopes (avoids silent Liquid rendering failures)
- Custom field names (`__c`) are now resolved from the live tenant before code generation — never guessed or lowercased
- Fixed a common `Credentials.zuora.rest_endpoint` double-prefix bug (`/v1/v1/`) in workflow Liquid templates

## [1.3.2] - 2026-05-28

### Improved
- Meter design skill now opens with a guided intake flow and confirms the design before generating JSON
- Meter build skill surfaces clearer validation errors with rule codes and field paths

## [1.3.1] - 2026-05-27

### Improved
- Clarified when to use MCP tools vs. generated REST/SDK code — agents now follow a consistent tool routing policy across all skills

## [1.3.0] - 2026-05-20

### Added
- New skills: `zuora-dynamic-pricing-design` and `zuora-dynamic-pricing-build` for Commerce Catalog setup

## [1.2.1] - 2026-05-13

### Added
- New skills: `zuora-meter-design` and `zuora-meter-build` for Mediation meter authoring
- Full operator reference library with JSON schemas and configuration guides

## [1.2.0] - 2026-04-30

### Added
- Codex (OpenAI) plugin support

## [1.0.0] - 2026-04-15

### Added
- Initial release with skills for API integration, workflow development, IS/order migration, validation, and review
- Claude Code and Cursor plugin support
