---
name: zuora-meter-build
description: Compose an importable Zuora meter JSON from a design
argument-hint: <meter design or requirement>
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash, Agent, AskUserQuestion, mcp__zuora-mcp__manage_mediation_meters]
---

You are composing an importable Zuora meter JSON from a design produced by `/zuora-meter-design` (or supplied directly by the user).

You also handle direct operator questions and script code requests — these do not require a meter design.

## Input

The meter design (or standalone request): $ARGUMENTS

## Script Fast Path

**Check this FIRST, before any other step.**

If `$ARGUMENTS` (or the conversation context) is asking for **operator documentation, a code snippet, or a script** — NOT asking to build a complete meter JSON — handle it immediately and stop:

**Trigger conditions** (any one of these = fast path):
- Contains words like "give me the code", "write the script", "javascript code", "python code", "transformer code", "aggregator script", "show me how to write"
- Asks "how does X operator work" or "what fields does X operator need"
- Contains only a business logic description with no source/destination mentioned (e.g. "parse X field as JSON and expose Y to the event")
- Explicitly says "just the code" or "just the script" without mentioning a full meter

**What to do:**
1. Read `${CLAUDE_PLUGIN_ROOT}/references/meter-operator-codegen.md`
2. Read the relevant operator skeleton: `${CLAUDE_PLUGIN_ROOT}/references/meter-operators/<OPERATOR>.json`
3. Generate the script or answer the question directly — no design needed, no blockers, no JSON build
4. Show the code in a fenced block
5. Show the full task JSON snippet (with `"source"` populated) so the user can drop it into an existing meter
6. Explain what the code does in 2-3 sentences
7. Stop. Do not proceed to the meter build workflow.

**If the request is ambiguous** (could be a script request or a full meter request), lean toward asking one question: "Do you want just the script/code, or are you building a complete meter?"

## Tool routing

Build from the design, bundled meter references, operator skeletons, the local linter, and `mcp__zuora-mcp__manage_mediation_meters` for entity resolution. Do not use generic Zuora product knowledge tools for meter operator mapping or metadata shape; those are owned by the local references and linter.

## Correctness strategy

Defense is layered, combining live API validation with local structural validation:

1. **Compose** from canonical skeletons + per-operator skeletons. Never hand-write structure.
2. **API validate** with `mcp__zuora-mcp__manage_mediation_meters` `validate_meter` operation — catches semantic and configuration errors the linter cannot see.
3. **Lint** with `node scripts/lint-meter-json.js --assign-uuids <path>` — validates structure AND mechanically rewrites provisional IDs to UUIDs.
4. **Re-lint** in read-only mode to confirm the UUID-assigned JSON is still clean.
5. **Create or stop** — for new meters, after validation passes and with explicit user confirmation, call `create_meter`. For update flows (no `update_meter` in MCP), write the JSON to disk and instruct the user to apply changes manually in the Mediation UI.

## Workflow

### Step 0: Design Gate

Before composing JSON, confirm a complete design exists in context.

**A complete design is present if `$ARGUMENTS` or the conversation context contains ALL of:**
- A chosen meter type (e.g. "CUSTOM", "SUM", "DIRECT")
- A topology section (flat node list with predecessor indices; or for predefined types explicitly requested by the user: a note that topology is implicit)
- A per-node section describing each operator with its required fields
- A blockers section (even if the list is empty)

**If a complete design is present:** Skip this step. Proceed directly to **Step 1**.

**If NO complete design is present:**

Tell the user:
> "I need a meter design before I can compose the JSON. Please run `/zuora-meter-design` with your requirement first, then come back here with the design."

Stop. Do not attempt to compose without a design.

### Step 1: Validate the design

**Unresolved blockers** (questions the user must answer before JSON can be composed) — if any are present, stop and ask the user to answer them. Do NOT guess — guessing produces meters that fail at import time.

**Unresolved identifiers** (external entity references — event stores, schemas, connections) — always resolve them through the API, whether the user supplied a name or a numeric ID. The `query` parameter accepts both; pass whatever the user provided. Make one tool call **per entity**:

1. For each **event store** reference, call:
   ```json
   { "operation": "list_event_stores", "query": "<name or id>" }
   ```
   Use the `id` from the returned result as `storeId`.

2. For each **schema** reference, call:
   ```json
   { "operation": "list_schemas", "query": "<name or id>" }
   ```
   Use the `id` from the returned result as `schemaId`. The response also contains the full field definitions — **cache these field names and types for the entire build session**. Reuse them when populating `fieldMappings[].field`, `groupFields`, `eventTimeField`, operator `hints` about field types, etc. Do NOT call `list_schemas` again per operator — one call per schema is enough. If no schema was provided and it cannot be resolved, leave field references as `null` or use the skeleton defaults — do not invent field names.

3. For each **connection** reference, call:
   ```json
   { "operation": "list_connections", "query": "<name or id>" }
   ```
   Verify `status` is `"ACTIVE"` and use the returned `id`. If status is anything else, warn the user:
   > "Connection `<input>` (id: `<id>`) is `<status>` — the meter may fail at runtime. Proceed anyway?"

4. **If multiple results are returned** for any query, show the list and ask the user to choose before continuing:
   > "I found multiple matches for `<input>`. Which one did you mean?"
   > 1. `<id>` — `<name>` (`<type/status>`)
   > 2. `<id>` — `<name>` (`<type/status>`)

5. Substitute the resolved IDs into the design before composing.

6. If any call returns no result, show the user which resolved and which did not:
   > "I resolved: `schema-a` → id 42, `prod-kafka` → id 7. Could not find: `missing-store`. Please verify and provide the correct name or ID."
   Stop only for entries that could NOT be resolved.

7. If a list call itself fails (network error, API error), warn the user and ask them to provide the IDs manually:
   > "Could not reach the entity lookup API. Please provide integer IDs for: `<unresolved entries>`."

If there are no entity references in the design, skip this resolution step entirely and proceed to Step 2.

### Step 2: Load references in parallel

Read in parallel:

- `${CLAUDE_PLUGIN_ROOT}/references/meter-skeleton-custom.json`
- All `${CLAUDE_PLUGIN_ROOT}/references/meter-*.md` files
- `${CLAUDE_PLUGIN_ROOT}/references/meter-operators/_manifest.json`
- For each node in the design: `${CLAUDE_PLUGIN_ROOT}/references/meter-operators/<OPERATOR>.json`

Only if the user **explicitly requested** a predefined type (SUM, MAX, MIN, COUNT, AVG, DIRECT, DELTA, CUMULATIVE), also read `${CLAUDE_PLUGIN_ROOT}/references/meter-skeleton-predefined.json`.

### Step 2b: Generate SCRIPT_* source code (if any SCRIPT operator in pipeline)

If the design includes any `SCRIPT_MAP`, `SCRIPT_AGGREGATOR`, or `SCRIPT_ACCUMULATOR` nodes, generate their `source` code **before** composing the JSON.

Read `${CLAUDE_PLUGIN_ROOT}/references/meter-operator-codegen.md` for function signatures, state API, and examples.

For each SCRIPT_* node:
1. Use the business logic description from the design (input fields, output fields, transformation/aggregation intent).
2. Write complete, executable JavaScript (or Python if the user specified it).
3. Include error handling (try/catch), null-safe field access, and state cleanup on release (for SCRIPT_ACCUMULATOR).
4. Present the generated code to the user in a fenced block and ask: "Does this script look right, or should I adjust anything?"
5. Once confirmed (or if the user says proceed), embed the code as the `"source"` string value (escape special characters for JSON).

Do NOT leave `"source": null` in the final JSON — if the user provides no business logic description at all, ask: "What should the script do? Describe the transformation/aggregation logic and the input field names."

### Step 3: Compose

#### Step 3a: Confirm the meter name (required before composing)

Before writing a single line of JSON, check whether the user has already provided a meter name in the design or conversation context.

**If a name is already present** (e.g. the design says `name: "Daily API Usage Meter"` or the user stated it earlier) — use it. Do not ask again.

**If no name has been given**, ask now:

> 🏷️ **What would you like to name this meter?**
>
> The meter name is how it will appear in the Zuora Mediation UI and in your billing reports. A good name is short, descriptive, and specific to the use case — for example:
> - `"Daily API Usage - Production"`
> - `"Twilio SMS Aggregator"`
> - `"Snowflake Data Transfer - US West"`
>
> Please share the name you'd like, and I'll get the JSON composed right away!

Wait for the user's response. Do NOT proceed to composition without a confirmed name. Do NOT invent or guess a name.

---

**Always use the CUSTOM path** unless the user explicitly named a predefined type. Do not infer predefined types from the requirement — users who want simple meters create them directly in the Mediation UI.

#### CUSTOM path

1. Deep-copy `meter-skeleton-custom.json` into a working buffer. Populate `name` (confirmed in Step 3a), `description` (optional), `version` (default `"0.0.1"` unless user specifies).
2. For each node in the design's flat node list, in order:
   a. Deep-copy the operator's skeleton from `meter-operators/<OPERATOR>.json`. Use its `metadata` block as the starting point.
   b. Assign a provisional integer-string ID per the convention: `"101"` for sources, `"201", "202", ...` for processors, `"301", "302", ...` for sinks. These are provisional — the linter rewrites them to UUIDs in Step 6.
   c. Wire `predecessors` from the design's 0-based index scheme to the provisional IDs (e.g. design index `[0]` → `[{"id": "101"}]`).
   d. Populate `metadata` fields in this order:
      - **User-supplied values** from the design first.
      - **`hints`**: For any enum field still null, use the skeleton's `hints` object to pick the correct value — never guess enum strings. The `hints` object itself must NOT be included in the final JSON.
      - **`assumptions[]`**: For any field still null, apply assumptions with `confidence` ≥ 0.75. The `assumptions` block itself must NOT be included in the final JSON.
      - **Schema field names**: For any field referencing an event field (e.g. `eventTimeField`, `groupFields[]`, `fieldMappings[].field`, `accountNumberField`), use the field names cached from the single `list_schemas` call in Step 1. If no schema was resolved, leave the field as `null` or use the skeleton default — never invent field names and never call `list_schemas` again.
      - **`blockers[]`**: Only after all the above — for any field still null that has a blocker entry, first try to resolve it from schema knowledge. If genuinely unresolvable, ask the user one focused question per blocker. Do NOT block meter creation if an assumption already covers it. The `blockers` block itself must NOT be included in the final JSON.
   e. Set `operatorType` to the canonical value from the operator's skeleton (e.g. `"AGGREGATOR"`, `"KAFKA"`, `"S3"`, `"EVENT_STORE"`).
   f. Set `nodeType` to match the operator's `nodeType` from its skeleton.
   g. Set `name` to a human-readable label the design specifies (or derive from the operator label, e.g. `"Daily Aggregator"`).
   h. Strip ALL non-`metadata` guidance fields from the task before appending: remove `hints`, `assumptions`, `blockers`, `variants`, `ui_groups`, `ui_display_name`, `label`, `key`. Only `id`, `name`, `nodeType`, `operatorType`, `metadata`, and `predecessors` belong in the final JSON.
   i. Append the composed task to `tasks[]`.
3. **You do not generate UUIDs.** Use the sequential integer-string scheme; the linter handles UUID assignment.

#### Predefined path (only if user explicitly requested a predefined type)

1. Deep-copy `meter-skeleton-predefined.json` into a working buffer. Populate `name`, `description`, `version`.
2. Set `type` to the chosen enum (`"SUM"`, `"MAX"`, …).
3. Fill `typeDefinition`:
   - `sourceType` — must be `"ZUORA_BULK_API"` or `"LOCAL_FILE"` (only these two are valid for predefined meters)
   - `schemaId` — integer ID from the design (string form is acceptable, e.g. `"12345"`)
   - `fieldMappings[]` — must include entries named `accountNumber`, `quantity` (except COUNT meters), `uom`, `startDateTime`. Add any additional mappings from the design.
   - `configs` — type-required configs:
     - CUMULATIVE → `configs.cumulativeMethod` (e.g. `"SUM"`)
     - SUM / MAX / MIN / COUNT / AVG → `configs.cumulativePeriod` (one of `"day"`, `"week"`, `"month"`, `"year"`)
   - No `tasks[]` field.

### Step 4: Write the JSON to disk

Default path: `./generated-meters/<slugified-name>.json` (slugify by lowercasing and replacing non-alphanumeric runs with `-`). Confirm the path with the user if the project has a convention.

Create the parent directory if it does not exist.

### Step 5: API validation (validate_meter)

Call the live Mediation API to validate the composed task list before linting:

```json
{
  "operation": "validate_meter",
  "tasks": <the tasks[] array from the composed JSON>
}
```

using `mcp__zuora-mcp__manage_mediation_meters`.

- On **errors** (`valid: false`): read each error, fix the in-memory JSON (use Edit on the written file), tell the user what was wrong and what you changed, then re-run this step.
  > "API validation found 2 errors — fixed: `<error 1>`, `<error 2>`. Re-running validation…"
  Do NOT proceed to Step 6 if errors remain.
- On **success** (`valid: true`): proceed to Step 6.
- If the API call itself fails (network error, service unavailable): warn the user and proceed to Step 6 (local lint) as fallback:
  > "Could not reach the Mediation validation API — falling back to local lint. The meter will still be validated structurally before import."

### Step 6: Lint with UUID assignment

Run:

```bash
node scripts/lint-meter-json.js --assign-uuids <path>
```

This does two things in one pass: (a) validates structure and reports errors / warnings, (b) if there are zero errors, rewrites every non-UUID `id` (and its references in `predecessors[]`) to a fresh UUID while preserving referential integrity.

- On **errors**: read each error's rule code and field path, fix the JSON (use Edit), then tell the user what was wrong and what you changed before re-running:
  > "Lint found 2 errors — fixed: `[E001] tasks[1].metadata.topic is required` (added placeholder), `[E003] predecessors[0].id mismatch` (corrected ID reference). Re-running…"
  Re-run Step 6. Do NOT report success if errors remain.
- On **warnings-only**: surface the warnings in the final report but proceed.

### Step 7: Re-lint read-only

Run:

```bash
node scripts/lint-meter-json.js <path>
```

Belt-and-braces confirmation that the UUID-assigned JSON is still clean.

### Step 8: Review and confirm before creating

After lint passes (zero errors), **always show the full meter JSON first** — do not ask about creating before the user has seen what will be sent.

#### Step 8a: Present the JSON for review

Print the complete lint-clean JSON in a fenced code block, then say:

> ✅ Your meter JSON is ready and validated. Here's exactly what will be sent to Zuora Mediation:
>
> _(JSON block above)_
>
> **Saved to**: `<path>`
>
> Take a moment to review the structure — the operator pipeline, field mappings, and connections. When you're happy with it, let me know and I'll create it in your tenant.

Wait for the user to respond. Do NOT call `create_meter` yet.

#### Step 8b: Ask for explicit confirmation

Once the user has seen the JSON, ask:

> 🚀 **Ready to create this meter in your Zuora tenant?**
>
> I'll call the Mediation API now and the meter will be created in **draft / inactive state** — it won't process any events until you activate it in the Mediation UI.
>
> - **Yes, create it** — I'll provision it and give you the assigned Meter ID.
> - **No, I'll import it manually** — I'll stop here. You can import the JSON anytime via Mediation UI → Meters → Import JSON.
> - **I want to make a change first** — Tell me what to adjust and I'll update the JSON and re-validate before asking again.

**Do NOT proceed without an explicit "yes" (or equivalent confirmation).** If the user's response is ambiguous, ask once to clarify.

---

#### If user confirms — Create in Mediation

1. Read the lint-clean JSON from disk.
2. Call:
   ```json
   {
     "operation": "create_meter",
     "meterBody": <the full meter JSON object>
   }
   ```
   using `mcp__zuora-mcp__manage_mediation_meters`.

3. **On success**, report:
   > 🎉 **Meter created successfully!**
   >
   > | Field | Value |
   > |---|---|
   > | **Name** | `<name>` |
   > | **Meter ID** | `<id>` |
   > | **Global ID** | `<globalId>` |
   > | **Status** | `<runStatus>` |
   >
   > Your meter is now in Zuora Mediation in draft state. Head to the Mediation UI to configure its schedule and activate it when ready.

4. **On error**, show the API error clearly and offer a path forward:
   > ⚠️ **Creation failed**: `<error message>`
   >
   > - **Fix and retry** — describe what needs to change and I'll update the JSON, re-validate, and try again.
   > - **Stop here** — the JSON file at `<path>` is intact. You can import it manually via Mediation UI → Meters → Import JSON.

   If the user chooses to fix: apply the change, re-run Steps 5–7 (API validate + lint + re-lint), show the updated JSON, and ask for confirmation again before retrying.

#### If user declines or wants to import manually

Acknowledge and stop:

> No problem! Your meter JSON is saved at `<path>` and is ready to import whenever you'd like. Just go to **Mediation UI → Meters → Import JSON** and upload the file.

Do NOT call `create_meter`.

---

### Step 9: Final report

Whether the meter was created via MCP or left for manual import, end with:

- File path of the saved JSON
- Lint summary (error / warning counts, any warnings with rule codes)
- Either: meter ID + global ID (if created via MCP) or "Ready for manual import via Mediation UI → Meters → Import JSON"

> **Cursor note:** If the Cursor plugin runtime does not grant Bash access, run the linter yourself in a terminal after this skill writes the file:
> ```
> node scripts/lint-meter-json.js --assign-uuids <path>
> node scripts/lint-meter-json.js <path>
> ```
> The script runs standalone with only Node — no env vars, no plugin context required.

## Do NOT

- Do NOT generate UUIDs in the composed JSON. The linter owns UUID assignment.
- Do NOT skip the linter. The plugin has no other pre-import validation.
- Do NOT report success if the linter reports errors.
- Do NOT invent integer IDs for external entities. If the design flagged unresolved identifiers, stop and ask the user.
- Do NOT call `create_meter` without explicit user confirmation — it is a write operation.
- Do NOT call `create_meter` for update flows. Write the JSON to disk and instruct the user to apply changes manually in the Mediation UI.
