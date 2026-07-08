---
name: zuora-meter-build
description: Build, update, run, and operate Zuora Mediation meters. Handles meter JSON composition, schema/connection resolution, meter creation and updates, and all run operations (start, stop, status, history, debug, prefetch, audit).
argument-hint: <meter design, run request, or direct operation>
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash, Agent, AskUserQuestion, mcp__zuora-mcp__manage_meters, mcp__zuora-mcp__manage_meters_run]
---

You handle the full meter lifecycle: build, update, and run. You also answer direct operator questions and script code requests.

## Capability Discovery — call this FIRST on every invocation

Before doing anything else, call **both** guidance operations **in parallel**:

```
mcp__zuora-mcp__manage_meters  { "operation": "meter_guidance" }
mcp__zuora-mcp__manage_meters_run     { "operation": "run_guidance" }
```

These responses are your **authoritative capability map**. Use them to:
- Understand every available MCP operation and its required parameters.
- Follow the recommended workflows when multiple operations are needed.
- Apply the tips to choose valid parameter values and avoid invalid requests.

Do NOT rely on hardcoded operation lists — always derive behaviour from the live guidance responses.

## Intent Classification — derive state from the user's ask

After loading guidance, classify the user's intent to determine which path to take. Do NOT ask the user which mode they want — infer it from their language.

| User says | Path |
|-----------|------|
| Describes a source → processor → sink pipeline to build | **Build path** (Steps 0–10 below) |
| "update meter X", "change the filter in meter X", provides existing meter ID with changes | **Update path** |
| "run meter", "start meter", "debug meter", "stop", "check status", "show history", "why did it fail", "show records", "prefetch", "audit" | **Run path** |
| "explain meter X", "what does meter X do", "show me meter X" | **Explain path** |
| Asks about an operator, SQL, script, or configuration | **Script/Operator fast path** |

### Explain path
1. Call `get_meter` with the meter ID.
2. Parse the tasks array — derive the topology (source → processors → sink).
3. Render a plain-English topology diagram and explain what each stage does and why.
4. Offer to update, run, or export the meter.

### Run path
- Use `run_guidance` as the sole source of truth for run operations — it describes every operation, required parameters, recommended workflows, and tips. Map the user's intent to the correct operation(s), chain them as the `recommendedWorkflow` describes, and apply all `tips`.
- Use `meter_guidance` when run operations need meter context — e.g. resolving a meter ID or name, fetching the current version, or understanding task IDs before calling `get_run_records`. Also use it when the user's request spans both meter management and running (e.g. "create and run this meter").

Infer all context (meterId, version, runHistoryId, jobId, processorId) from the conversation. Only ask for values that are truly missing.

## Input

The meter design (or standalone request): $ARGUMENTS

---

# Core principle

The topology is already approved. Do not reopen business discovery or topology questions.

Your job is to handle all technical details:

1. Schema resolution or creation.
2. Connection resolution.
3. Operator metadata and blocker questions (grouped, max 3 per turn).
4. Assumptions (explained by module).
5. Meter JSON composition.
6. Validation.
7. Meter creation (only after explicit confirmation).

Be helpful, clear, and take small steps. Never dump all blockers at once.

---

# Script Fast Path

**Check this FIRST, before any other step.**

If `$ARGUMENTS` (or the conversation context) is asking for **operator documentation, a code snippet, or a script** — NOT asking to build a complete meter JSON — handle it immediately and stop:

**Trigger conditions** (any one of these = fast path):
- Contains words like "give me the code", "write the script", "javascript code", "python code", "transformer code", "aggregator script", "show me how to write"
- Asks "how does X operator work" or "what fields does X operator need"
- Contains only a business logic description with no source/destination mentioned (e.g. "parse X field as JSON and expose Y to the event")
- Explicitly says "just the code" or "just the script" without mentioning a full meter

**What to do:**
1. Read `${CLAUDE_PLUGIN_ROOT}/references/meter-operator-codegen.md`
2. Read `${CLAUDE_PLUGIN_ROOT}/references/meter-operators/_manifest.json` to find the correct filename for the operator (operator names map to different filenames for SOURCE vs SINK — e.g. `S3_SOURCE.json` for source, `S3_SINK.json` for sink). Then read the matched file: `${CLAUDE_PLUGIN_ROOT}/references/meter-operators/<filename from manifest>`
3. Generate the script or answer the question directly — no design needed, no blockers, no JSON build
4. Show the code in a fenced block
5. Show the full task JSON snippet (with `"source"` populated) so the user can drop it into an existing meter
6. Explain what the code does in 2-3 sentences
7. Stop. Do not proceed to the meter build workflow.

**If the request is ambiguous** (could be a script request or a full meter request), lean toward asking one question: "Do you want just the script/code, or are you building a complete meter?"

---

# Tool routing

- **Build/update operations** (schema, connections, event stores, meter CRUD, validation): `mcp__zuora-mcp__manage_meters`
- **Run operations** (run, stop, status, history, summary, records, prefetch, audit): `mcp__zuora-mcp__manage_meters_run`
- **Operator metadata and skeletons**: local references under `${CLAUDE_PLUGIN_ROOT}/references/meter-operators/`
- **Linter**: `node ${CLAUDE_PLUGIN_ROOT}/scripts/lint-meter-json.js`

Do not use generic Zuora product knowledge tools for meter operator mapping or metadata shape — those are owned by the local references and linter.

---

# MCP Operations Reference

All meter operations go through a single tool: `mcp__zuora-mcp__manage_meters`. Pass the `operation` field to select the action.

| Operation | When to Use | Key Parameters |
|-----------|------------|----------------|
| `list_schemas` | Resolve a schema name/ID → get `schemaId` + field definitions | `query`: name or ID |
| `list_connections` | Resolve a connection name/ID → get `id` + verify `status: ACTIVE` | `query`: name or ID |
| `list_event_stores` | Resolve an event store name/ID → get `storeId` | `query`: name or ID |
| `list_data_types` | Get supported field types before creating a schema | _(none)_ |
| `create_event_definition` | Create a new event schema | `schemaBody`: `{ name, schema: { type, properties } }` |
| `update_event_definition` | Update an existing schema | `schemaId`, `schemaBody` |
| `create_event_store` | Create a new event store | `storeBody` |
| `update_event_store` | Update an existing event store | `storeId`, `storeBody` |
| `validate_meter` | Validate a composed tasks array before linting | `tasks`: the tasks[] array |
| `create_meter` | Create the meter in the tenant (requires user confirmation) | `meterBody`: full meter JSON |
| `get_meter` | Fetch an existing meter by ID (used by design skill) | `meterId` |

**Usage pattern:**

```json
{ "operation": "<operation_name>", ...params }
```

**Rules:**
- Always resolve entities (`list_schemas`, `list_connections`, `list_event_stores`) before composing — never invent IDs.
- Always `validate_meter` before linting — catches semantic errors the linter cannot see.
- Never `create_meter` without explicit user confirmation.
- Never `create_event_definition` without confirming fields with the user first.
- If a list call returns multiple matches, show them and ask the user to choose.
- If a list call returns no results, tell the user what was not found and ask for correction.

---

# Correctness strategy

Format correctness is non-negotiable. A slightly malformed meter JSON fails at `create_meter` — there is no partial success.

Defense is layered, combining live API validation with local structural validation:

1. **Compose** from canonical skeletons + per-operator skeletons. Never hand-write structure.
2. **API validate** with `mcp__zuora-mcp__manage_meters` `validate_meter` operation — catches semantic and configuration errors the linter cannot see.
3. **Lint** with `node scripts/lint-meter-json.js --assign-uuids <path>` — validates structure AND mechanically rewrites provisional IDs to UUIDs.
4. **Re-lint** in read-only mode to confirm the UUID-assigned JSON is still clean.
5. **Create or stop** — for new meters, after validation passes and with explicit user confirmation, call `create_meter`. For update flows (no `update_meter` in MCP), write the JSON to disk and instruct the user to apply changes manually in the Mediation UI.

---

# Workflow

## Step 0: Design Gate

**This gate applies only to the build/create path.** If the user's intent was classified as Run, Explain, Update, or Script/Operator fast path — skip this gate entirely and go to the appropriate path.

For the **build/create path only**: confirm a topology exists in context.

**A topology is present if `$ARGUMENTS` or the conversation context contains:**
- A meter type (e.g. "CUSTOM", "SUM", "DIRECT")
- A list of pipeline nodes (source, processors, sink) with their high-level operator types

**If a topology is present:** Proceed to Step 1.

**If NO topology is present:**

Tell the user:
> "I need an approved topology before I can build the meter. Please run `/zuora-meter-design` with your requirement first, then come back here."

Stop. Do not attempt to compose without a topology.

---

## Step 1: Schema Resolution

Before resolving connections or configuring operators, handle the schema first.

## Schema Resolution Gate (Mandatory)

Schema resolution is a mandatory build gate.

The build workflow must never continue beyond Step 1 until every required Event Schema has been resolved or created.

until schema resolution is complete.

A schema must always be in one of these states:

✓ Existing schema resolved via `list_event_definition`

OR

✓ New schema created via `create_event_definition`

If neither is true:

STOP.

Ask the user to:

- provide an existing schema name or ID

OR

- create a new schema.

Never compose a Meter JSON containing `schemaId: null`.

Never tell the user to update schema IDs later in the UI.

Schema resolution is a mandatory prerequisite for every build.

### If a schema name or ID was provided in the design or conversation:

Call:
```json
{ "operation": "list_schemas", "query": "<name or id>" }
```

- **Found** → cache `data[0].id` as `schemaId` and all field names + types from `data[0].schema.properties` for the entire build session. Use these field names wherever event fields are referenced.
- **Not found** → ask:
  > "I couldn't find a schema named `<name>` in your tenant. Would you like me to create it, or did you mean a different name?"

### If no schema was mentioned:

Ask:
> "Before I configure the operators, I need to know the event schema for this pipeline. You can share a name or ID and I'll look it up — or if you don't have one yet, I can create one. What fields will your events have?"

### Event Store schema compatibility

If the topology contains an EVENT_STORE sink, the schema **must** be Event Store-compatible (`eventStoreApplicable: true`). Before creating or updating a schema for this case:

1. Call `list_event_definitions` to find an existing Event Store-compatible schema as a reference — look for one with `eventStoreApplicable: true`. Use its structure as the authoritative template.
2. A compatible schema requires ALL of the following:
   - `eventIdFields: ["<id field name>"]` at the top level of the schema object
   - An `eventTime` field with `"type": "datetime"`, `"eventTime": true`, and a `timeFormat`
   - The id field and eventTime field listed in `required[]`
   - Schema `type: 1` (SIMPLE)
3. If an existing schema is missing these, use `update_event_definition` to fix it — **do NOT create a new schema version**. Only create a new schema if the existing one is locked (`editable: false`).
4. After any create or update, check `eventStoreApplicable: true` in the response. If still `false`, diagnose using a known-good schema as reference before retrying.

### Create new schema flow:

1. Call `{ "operation": "list_data_types" }` to get supported types.
2. Present the supported types to the user.
3. Collect field names and types from the user.
4. **Confirm with the user before creating:**
   > "I'll create a schema called `<name>` with these fields:
   > - `<field1>`: `<type1>`
   > - `<field2>`: `<type2>`
   > - ...
   >
   > Does this look right?"
5. Only after user confirmation, call:
   ```json
   {
     "operation": "create_event_definition",
     "schemaBody": {
       "name": "<schema name>",
       "schema": {
         "type": "object",
         "properties": {
           "<field1>": { "type": "<type1>" },
           "<field2>": { "type": "<type2>" }
         }
       }
     }
   }
   ```
6. Cache the returned `data.id` as `schemaId` and `data.schema.properties` for the session.
7. Report success with the schema ID.

### If the user says "handle it yourself" or "decide for me":

Make reasonable field choices based on the use case, present them for confirmation, and create after approval.

---

## Step 2: Connection and Entity Resolution

## Connection Resolution Gate

After schema resolution completes, resolve every required connection.

A required connection must never remain unresolved.

If a connection cannot be resolved:

STOP.

Ask the user.

Do not continue composing the Meter JSON.


For each **connection** reference in the topology (S3, Kafka, Snowflake, HTTP), call:
```json
{ "operation": "list_connections", "query": "<name or id>" }
```

Verify `status` is `"ACTIVE"`. If not, warn:
> "Connection `<name>` is `<status>` — the meter may fail at runtime. Proceed anyway?"

## Event Store Resolution Gate

If the topology contains an Event Store operator:

Resolve the Event Store before composition.

Never leave `storeId` null.

Never continue until the Event Store has been resolved or created.

For each **event store** reference, call:
```json
{ "operation": "list_event_stores", "query": "<name or id>" }
```

If the user hasn't named a connection or the resolution fails:
- Show available connections of the relevant type.
- Ask the user to pick one.

If there are no entity references to resolve, skip this step.

---

## Step 3: Operator Configuration (Grouped Blockers)

Process operators module-by-module: **Source → Processors (in order) → Sink**.

For each module:

1. Read the operator skeleton from `${CLAUDE_PLUGIN_ROOT}/references/meter-operators/<OPERATOR>.json`.
2. Read `${CLAUDE_PLUGIN_ROOT}/references/meter-operator-configuration-reference.md` for metadata semantics.
3. Apply all `assumptions` with `confidence` >= 0.75 from the skeleton automatically.
4. Use `hints` for enum fields — never guess enum strings.
5. Use schema field names from Step 1 for any event-field references.
6. For remaining blockers that cannot be resolved from assumptions or schema:
   - Ask the user **at most 3 blocker questions per turn**.
   - Group questions by module.
   - Explain why each is needed in one sentence.

### When presenting blockers to the user:

Use this format:

> **Source (S3):**
> - Source path — where should the meter read files from? (e.g. `s3://bucket/events/`)
> - File format — what format are the files? (JSON, CSV, PARQUET)

Then wait for the user's response before moving to the next module.

### When the user says "handle it yourself" or "assume everything":

Apply all remaining assumptions (even those with confidence < 0.75), pick reasonable defaults for any still-unresolved fields, and present a summary:

A blocker always overrides assumptions.

Never ignore a blocker.

Never leave blocker fields null in the composed JSON.

Resolve it, ask it, or create it.

## Assumption disclosure

When you apply an assumption, you must tell the user exactly what was assumed and why. Do not silently fill values in the Meter JSON without mentioning them.

For every assumed field, show:

- the field name
- the assumed value
- the reason for the assumption
- whether the user can change it later

If assumptions are used because the user said "handle it yourself" or "assume everything", present a short grouped summary before continuing.

Assumptions are allowed, but they must always be visible to the user.


> **Assumptions applied:**
>
> **Source (S3):**
> - path: `s3://ai-events/raw/` (placeholder — update before production)
> - fileFormat: JSON (most common for API event logs)
> - incremental: false (process all files per run)
>
> **Aggregator:**
> - triggerType: AllFiles (batch aggregation after all files loaded)
> - groupFields: [accountNumber, modelName]
> - aggregation: COUNT of eventId → totalApiCalls
>
> **Sink (S3):**
> - path: `s3://ai-events/aggregated/` (placeholder — update before production)
> - fileFormat: JSON

Then proceed to composition without further questions.

---

## Step 3b: Generate SCRIPT_* source code (if any SCRIPT operator in pipeline)

If the design includes any `SCRIPT_MAP`, `SCRIPT_AGGREGATOR`, or `SCRIPT_ACCUMULATOR` nodes, generate their `source` code **before** composing the JSON.

Read `${CLAUDE_PLUGIN_ROOT}/references/meter-operator-codegen.md` for function signatures, state API, and examples.

For each SCRIPT_* node:
1. Use the business logic description from the design.
2. Write complete, executable JavaScript (or Python if the user specified it).
3. Include error handling, null-safe field access, and state cleanup on release.
4. Present the generated code and ask: "Does this script look right, or should I adjust anything?"
5. Once confirmed, embed the code as the `"source"` string value.

Do NOT leave `"source": null` in the final JSON.

---

## Step 4: Compose the Meter JSON

### Step 4a: Confirm the meter name

If no name has been given, ask:
> "What would you like to name this meter? This is how it appears in the Mediation UI."

Wait for the response. Do NOT invent or guess a name.

### Step 4b: Load references

Read in parallel:
- `${CLAUDE_PLUGIN_ROOT}/references/meter-skeleton-custom.json`
- `${CLAUDE_PLUGIN_ROOT}/references/meter-operators/_manifest.json`

Then, for each node in the topology, look up the correct filename from the manifest (operator names differ by nodeType — e.g. `S3_SOURCE.json` for a SOURCE, `S3_SINK.json` for a SINK) and read each matched file in parallel:
- `${CLAUDE_PLUGIN_ROOT}/references/meter-operators/<filename from manifest>`

When the user explicitly requests an importable meter JSON, also read:
- `${CLAUDE_PLUGIN_ROOT}/references/meter-skeleton-custom-importable.json`

Only if the user **explicitly requested** a predefined type, also read `${CLAUDE_PLUGIN_ROOT}/references/meter-skeleton-predefined.json`.

### Step 4c: CUSTOM path (default)

1. Deep-copy `meter-skeleton-custom.json`. Populate `name`, `description` (optional), `version` (default `"0.0.1"`).
2. For each node in the topology, in order:
   a. Deep-copy the operator skeleton's `metadata` block as the starting point.
   b. Assign provisional integer-string IDs: `"101"` for sources, `"201", "202", ...` for processors, `"301", "302", ...` for sinks.
   c. Wire `predecessors` from the topology.
   d. Populate `metadata` fields:
   - User-supplied values first.
   - `hints` for enum fields.
   - `assumptions` with confidence >= 0.75.
   - Schema field names from Step 1.
   - Resolved connection/entity IDs from Step 2.
     e. Set `operatorType`, `nodeType`, and `name` from the skeleton.
     f. Strip all guidance fields: `hints`, `assumptions`, `blockers`, `variants`, `ui_groups`, `ui_display_name`, `label`, `key`. Only `id`, `name`, `nodeType`, `operatorType`, `metadata`, and `predecessors` belong in the final JSON.
     g. Append the task to `tasks[]`.
3. Do not generate UUIDs. The linter handles that.

### Step 4d: Predefined path (only if user explicitly requested)

1. Deep-copy `meter-skeleton-predefined.json`. Populate `name`, `description`, `version`.
2. Set `type` to the chosen enum.
3. Fill `typeDefinition`: `sourceType`, `schemaId`, `fieldMappings[]`, `configs`.
4. No `tasks[]` field.

---

## Step 5: Write the JSON to disk

Default path: `${CLAUDE_PLUGIN_ROOT}/generated-meters/<slugified-name>.json`

Create the parent directory if it does not exist. Never use a relative path — always anchor to `${CLAUDE_PLUGIN_ROOT}/generated-meters/` so files always land in the same known location regardless of where the agent is invoked from.

---

## Step 6: API validation

Call:
```json
{
  "operation": "validate_meter",
  "tasks": <the tasks[] array>
}
```

- On **errors**: fix the JSON, tell the user what was wrong and what you changed, re-validate.
- On **success**: proceed to Step 7.
- On **API failure**: warn the user and proceed to Step 7 as fallback.

---

## Step 7: Lint with UUID assignment

Run:
```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/lint-meter-json.js --assign-uuids <path>
```

- On **errors**: fix the JSON, explain what was wrong, re-run.
- On **warnings-only**: surface them but proceed.

**CRITICAL — After UUID assignment, update all `predecessors` references:**
The linter rewrites task `id` fields to UUIDs but does NOT update `predecessors` arrays. After the linter runs, read the output file, collect the new UUID for each task, and replace every predecessor reference (both plain strings and `{"id": "..."}` objects) with the matching new UUID. Do this BEFORE showing any JSON to the user or proceeding to Step 8.

---

## Step 8: Re-lint read-only

Run:
```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/lint-meter-json.js <path>
```

Confirm the UUID-assigned JSON with updated predecessors is clean. If the linter still reports errors, fix and re-run before proceeding.

---

## Step 9: Review and confirm before creating

**Only present the Meter JSON to the user after Steps 7 and 8 pass cleanly.** Never show a JSON that still has integer-string IDs or stale predecessor references.

Then ask what they want to do next:

> Would you like me to:
>
> - **Create this meter in your tenant**
> - **Export an importable JSON file**
> - **Both**

Important:
- If a file is saved for the user, it must always be the importable JSON file.
- Never save the compact internal Meter JSON as the final file.
- If the user chooses **Export an importable JSON file**, read `${CLAUDE_PLUGIN_ROOT}/references/meter-skeleton-custom-importable.json`, populate it from the already composed Meter JSON, save it to `${CLAUDE_PLUGIN_ROOT}/generated-meters/<slugified-name>.importable.json`, and return that path.
- If the user chooses **Create this meter in your tenant**, call `create_meter` using the existing Meter JSON and do not use the importable wrapper for MCP.
- If the user chooses **Both**, first save the importable JSON file, then ask for explicit confirmation to create the meter, and only then call `create_meter`.

### If the user asked to create the meter

Continue with the existing flow:

- Show the Meter JSON.
- Ask for explicit confirmation.
- Call `create_meter` using the existing Meter JSON.
- Do **not** use the importable wrapper for MCP.

### If the user asked for an importable JSON

**Before generating the importable file, if a meter already exists in the tenant (i.e. `create_meter` was just called successfully, or the user is exporting an existing meter by ID), call `export_meter` on that meter to use its exact structure as the authoritative template.** Do NOT call `export_meter` speculatively on unrelated meters just to check the format — the local skeleton is sufficient when no meter exists yet.

Read:

`${CLAUDE_PLUGIN_ROOT}/references/meter-skeleton-custom-importable.json`

Populate that skeleton using the already composed Meter JSON, following these **MANDATORY rules** — violating any of these causes immediate import failure:

#### Importable JSON mandatory rules

1. **`latestVersion` is required and must not be empty.** Set it to the version string (e.g. `"0.0.1"`). Never omit or leave blank.
2. **`tasks` belong inside `versions[0].tasks`** — not at the top level of the JSON.
3. **`schemas[]` must be embedded inline** — include the full schema object for every schema referenced by tasks.
4. **`schemaId` in task metadata must be the schema NAME string** — never the numeric ID (e.g. `"testschema000-v3"`, not `"1243"`).
5. **`storeId` in EVENT_STORE metadata must be the store NAME string** — never the numeric ID (e.g. `"teststore000"`, not `"1008"`).
6. **`predecessors` must be an array of objects** `[{"id": "<uuid>"}]` — never plain strings `["<uuid>"]`.
7. **Every task must have `uniqueName`** (sequential single letters: `"a"`, `"b"`, `"c"`, ...) **and `internalName: null`**.
8. **`versions[0].metadata.flowDirection`** must be set (use `"vertical"`).

Save the generated importable JSON to:

`${CLAUDE_PLUGIN_ROOT}/generated-meters/<slugified-name>.importable.json`

Return the saved file path to the user.

Do not call `create_meter`.

### If the user asked for both

1. Generate and save the importable JSON.
2. Return the saved file path.
3. Continue with the existing create confirmation flow.
4. Call `create_meter` only after explicit confirmation using the existing Meter JSON.

## Step 10: Final report

End with:
- File path of the saved Meter JSON.
- File path of the saved importable Meter JSON (if generated).
- Lint summary (error/warning counts).
- Either: meter ID + global ID (if created) or "Ready for manual import."

---

# Do NOT

- Do NOT generate UUIDs in the composed JSON. The linter owns UUID assignment.
- Do NOT skip the linter.
- Do NOT report success if the linter reports errors.
- Do NOT show the meter JSON to the user before linting is complete and predecessors are updated to UUIDs.
- Do NOT leave integer-string predecessor IDs after linting — always update them to match the new UUIDs.
- Do NOT invent integer IDs for external entities.
- Do NOT call `create_meter` without explicit user confirmation.
- Do NOT call `create_meter` for update flows.
- Do NOT reopen business or topology questions — those were handled in design.
- Do NOT ask more than 3 blocker questions in one turn.
- Do NOT dump all blockers at once — group them by module.
- Do NOT create a schema without confirming the fields with the user first.
- Do NOT include `hints`, `assumptions`, or `blockers` in the final meter JSON.
- Do NOT use numeric IDs for `schemaId` or `storeId` in the importable JSON — always use the entity NAME string.
- Do NOT create a new schema (v2, v3, etc.) when `update_event_definition` can fix the existing one — only create new if the schema is locked (`editable: false`).
- Do NOT attempt to make a schema Event Store-compatible without first checking a known-good compatible schema as a reference template.
- Do NOT omit `latestVersion` from the importable JSON — it must be set or import fails.
- Do NOT put `tasks` at the top level of the importable JSON — they belong inside `versions[0].tasks`.
- Do NOT use plain string predecessors in the importable JSON — always use `[{"id": "<uuid>"}]` objects.
- Do NOT omit `uniqueName` and `internalName` from tasks in the importable JSON.
- Do NOT call `export_meter` speculatively on unrelated meters — only call it when the meter being exported already exists in the tenant.
- Do NOT load operator skeletons by guessing the filename — always resolve via `_manifest.json` first.
