---
name: zuora-mediation-meter-build
description: Compose an importable Zuora Mediation meter JSON from a design
argument-hint: <meter design or requirement>
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash, Agent, mcp__zuora-mcp__manage_mediation_meters]
---

You are composing an importable Zuora Mediation meter JSON from a design produced by `/zuora-mediation-meter-design` (or supplied directly by the user).

## Input

The meter design: $ARGUMENTS

## Correctness strategy

Because the plugin has no live access to the Zuora mediation validator, `scripts/lint-meter-json.js` is the only pre-import safety net. Defense is layered:

1. **Compose** from canonical skeletons + per-operator skeletons. Never hand-write structure.
2. **Lint** with `node scripts/lint-meter-json.js --assign-uuids <path>` — validates structure AND mechanically rewrites provisional IDs to UUIDs.
3. **Re-lint** in read-only mode to confirm the UUID-assigned JSON is still clean.
4. **Report and stop.** GS user imports via the Mediation UI.

## Workflow

### Step 0: Design Gate

Before composing JSON, confirm a complete design exists in context.

**A complete design is present if `$ARGUMENTS` or the conversation context contains ALL of:**
- A chosen meter type (e.g. "CUSTOM", "SUM", "DIRECT")
- A topology section (flat node list with predecessor indices; or for predefined types explicitly requested by the user: a note that topology is implicit)
- A per-node section describing each operator with its required fields
- A blockers section (even if the list is empty)

**If a complete design is present:** Skip this step. Proceed directly to **Step 1**.

**If NO complete design is present AND a `meterId` or update request is in `$ARGUMENTS`:**

Invoke the design skill via the Agent tool:
```
Use the zuora-mediation-meter-design skill to design the meter update. Pass the full user request as the argument: "$ARGUMENTS"
```

Wait for the design skill to complete. It will walk the user through the current meter (via `get_meter`), collect their changes, and produce a complete prose design. Once the design is returned, proceed to **Step 1** using that design.

**If NO complete design is present AND no `meterId` or update language in `$ARGUMENTS`:**

Tell the user:
> "I need a meter design before I can compose the JSON. Please run `/zuora-mediation-meter-design` with your requirement first, then come back here with the design."

Stop. Do not attempt to compose without a design.

### Step 1: Validate the design

**Unresolved blockers** (questions the user must answer before JSON can be composed) — if any are present, stop and ask the user to answer them. Do NOT guess — guessing produces meters that fail at import time.

**Unresolved identifiers** (external entity names that need real integer IDs, e.g. `"schemaId": "usage-events"`, `"storeId": "es1"`, `"connectionName": "prod-kafka"`) — do NOT stop immediately. First try to resolve them automatically:

1. Collect all unresolved names from the design:
   - Event store names → `eventStoreNames`
   - Schema names → `schemaNames`
   - Connection names → `connectionNames`

2. Call `mcp__zuora-mcp__manage_mediation_meters` with:
   ```json
   {
     "operation": "resolve_entities",
     "eventStoreNames": ["<names from design, omit if none>"],
     "schemaNames": ["<names from design, omit if none>"],
     "connectionNames": ["<names from design, omit if none>"]
   }
   ```
   Only include lists that have entries — omit empty lists entirely.

3. For each resolved entity, substitute its integer ID into the design before composing:
   - Event store: use `id` field
   - Schema: use `id` field
   - Connection: use `id` field

4. If a resolved connection has `status` other than `"ACTIVE"`, warn the user:
   > "Connection `<name>` (id: `<id>`) is `<status>` — the meter may fail at runtime. Proceed anyway?"

5. If `hasUnresolved: true` in the response, show the user which names resolved and which did not:
   > "I resolved: `schema-a` → id 42, `prod-kafka` → id 7. Could not find: `missing-store`. Please provide the integer ID for `missing-store` before I continue."
   Stop only for the names that could NOT be resolved.

6. If the `resolve_entities` call itself fails (network error, API error), warn the user and ask them to provide the IDs manually:
   > "Could not reach the entity resolution API. Please provide integer IDs for: `<unresolved names>`."

If there are no unresolved identifiers in the design, skip this resolution step entirely and proceed to Step 2.

### Step 2: Load references in parallel

Read in parallel:

- `${CLAUDE_PLUGIN_ROOT}/references/meter-skeleton-custom.json`
- All six `${CLAUDE_PLUGIN_ROOT}/references/meter-*.md` files
- `${CLAUDE_PLUGIN_ROOT}/references/meter-operators/_manifest.json`
- For each node in the design: `${CLAUDE_PLUGIN_ROOT}/references/meter-operators/<OPERATOR>.json`

Only if the user **explicitly requested** a predefined type (SUM, MAX, MIN, COUNT, AVG, DIRECT, DELTA, CUMULATIVE), also read `${CLAUDE_PLUGIN_ROOT}/references/meter-skeleton-predefined.json`.

### Step 3: Compose

**Always use the CUSTOM path** unless the user explicitly named a predefined type. Do not infer predefined types from the requirement — users who want simple meters create them directly in the Mediation UI.

#### CUSTOM path

1. Deep-copy `meter-skeleton-custom.json` into a working buffer. Populate `name`, `description` (optional), `version` (default `"0.0.1"` unless user specifies).
2. For each node in the design's flat node list, in order:
   a. Deep-copy the operator's skeleton from `meter-operators/<OPERATOR>.json`. Use its `metadata` block as the starting point.
   b. Assign a provisional integer-string ID per the convention: `"101"` for sources, `"201", "202", ...` for processors, `"301", "302", ...` for sinks. These are provisional — the linter rewrites them to UUIDs in Step 5.
   c. Wire `predecessors` from the design's 0-based index scheme to the provisional IDs (e.g. design index `[0]` → `[{"id": "101"}]`).
   d. Populate `metadata` fields: user-supplied values first, then the operator's `assumptions[]` block applied for any field still null.
   e. Set `operatorType` to the canonical value from the operator's skeleton (e.g. `"AGGREGATOR"`, `"KAFKA"`, `"S3"`, `"EVENT_STORE"`).
   f. Set `nodeType` to match the operator's `nodeType` from its skeleton.
   g. Set `name` to a human-readable label the design specifies (or derive from the operator label, e.g. `"Daily Aggregator"`).
   h. Append the composed task to `tasks[]`.
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

### Step 5: Lint with UUID assignment

Run:

```bash
node scripts/lint-meter-json.js --assign-uuids <path>
```

This does two things in one pass: (a) validates structure and reports errors / warnings, (b) if there are zero errors, rewrites every non-UUID `id` (and its references in `predecessors[]`) to a fresh UUID while preserving referential integrity.

- On **errors**: read the rule codes, fix the JSON (use Edit), re-run Step 5. Do NOT report success if errors remain.
- On **warnings-only**: surface the warnings in the final report but proceed.

### Step 6: Re-lint read-only

Run:

```bash
node scripts/lint-meter-json.js <path>
```

Belt-and-braces confirmation that the UUID-assigned JSON is still clean.

### Step 7: Report

Final chat output:

- File path
- Lint summary (error / warning counts)
- Any warnings still present (each with its rule code)
- Next step: "Import via Mediation UI → Meters → Import JSON"

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
- Do NOT import the meter to Zuora. The GS user imports via the Mediation UI.
