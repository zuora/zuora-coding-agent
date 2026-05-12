---
name: zuora-mediation-meter-design
description: Design a Zuora Mediation meter — pick type, define topology, and collect per-operator field values
argument-hint: <business requirement for the meter>
allowed-tools: [Read, Glob, Grep, Bash, Agent, mcp__zuora-mcp__manage_mediation_meters]
---

You are designing a Zuora Mediation meter. The user has described a usage-billing requirement; your job is to turn it into a prose design detailed enough that `/zuora-mediation-meter-build` can compose an importable meter JSON without re-interviewing the user.

## Input

The user's meter requirement: $ARGUMENTS

## Workflow

### Step 0: Update or Create?

Before anything else, determine whether the user is updating an existing meter or creating a new one.

**Detect an update scenario if ANY of the following are true:**
- `$ARGUMENTS` contains a numeric meter ID (e.g. `456`, `1234`) or a UUID
- `$ARGUMENTS` or conversation context contains phrases like "update meter", "modify meter", "clone meter", "change meter", "edit meter"
- The user has provided a `meterId` in their request

**If update scenario detected:**

1. Call `mcp__zuora-mcp__manage_mediation_meters` with:
   ```json
   { "operation": "get_meter", "meterId": "<the id from user input>" }
   ```

2. If the call returns an error or the meter is not found:
   - Tell the user: "I couldn't find meter `<id>`. Please verify the ID and try again."
   - Stop. Do not proceed with the design flow.

3. If the meter is found, study the returned JSON and produce a plain-English walkthrough in chat:
   - **Meter name and type** — e.g. "This is a CUSTOM meter named 'Daily API Usage'."
   - **Topology** — describe the pipeline in human terms, e.g. "It has 3 nodes: a Kafka source → a daily SUM aggregator → a Zuora Usage sink."
   - **Per-node summary** — for each task in the JSON: operator type, its purpose in one sentence, key configured fields (e.g. schema name, aggregation window, field mappings)
   - **What it does end-to-end** — one paragraph summarising the full data flow

4. After the walkthrough, ask the user:
   > "Based on the above, what changes would you like to make to this meter?"

5. Collect the user's answer. Then continue into **Step 1** below, using the fetched meter JSON as additional context alongside the user's change request.

**If no update scenario detected (create flow):**

Skip this step entirely. Proceed directly to **Step 1**.

### Step 1: Understand the requirement

If the input is vague, ask targeted questions (one per message):

- What raw event source is feeding usage data? (Kafka topic, S3 bucket, Zuora Bulk upload, Snowflake, HTTP, …)
- What's the billable outcome? (raw pass-through, aggregation over time windows, real-time rating, …)
- If aggregating: what function (SUM, MAX, MIN, COUNT, AVG), what window (hour, day, month)?
- Where do finalized records go? (Zuora Usage, Zuora Rating, S3 archive, Snowflake, multi-sink fan-out, …)
- Filtering, enrichment, deduplication, subscription lookup needed?

### Step 2: Read references in parallel

Read in parallel:

- `${CLAUDE_PLUGIN_ROOT}/references/meter-types-and-concepts.md` — meter type decision tree, CUSTOM vs predefined shapes, the 9 type enums.
- `${CLAUDE_PLUGIN_ROOT}/references/meter-operator-selection-guide.md` — how to pick operators for common patterns.
- `${CLAUDE_PLUGIN_ROOT}/references/meter-operator-configuration-reference.md` — per-operator field semantics and constraints.
- `${CLAUDE_PLUGIN_ROOT}/references/meter-field-mappings-and-conventions.md` — required field mappings (accountNumber, quantity, uom, startDateTime), custom field conventions, date formats.
- `${CLAUDE_PLUGIN_ROOT}/references/meter-validation-rules-and-errors.md` — rules the user will hit at import time; you must honor them in the design.
- `${CLAUDE_PLUGIN_ROOT}/references/meter-complete-examples.md` — 11 worked examples spanning all common patterns. Use these as templates.
- `${CLAUDE_PLUGIN_ROOT}/references/meter-operators/_manifest.json` — the full operator catalog grouped by nodeType.

### Step 3: Pick the meter type

**Default to CUSTOM.** The predefined types (DIRECT, DELTA, CUMULATIVE, SUM, MAX, MIN, COUNT, AVG) are simple and users can create them directly in the Mediation UI — do NOT steer the user toward them. Only acknowledge a predefined type if the user **explicitly names one** (e.g., "I want a SUM meter").

- Everything else → **CUSTOM**
- User explicitly says "SUM meter", "DIRECT meter", etc. → that predefined type

The `type` field is the STRING enum (`"CUSTOM"`, `"SUM"`, …) — never a numeric code.

### Step 4: Pick the topology (CUSTOM only)

For CUSTOM meters, express the pipeline as a flat node list with 0-based predecessor indices:

```
node 0 (SOURCE):    predecessors []
node 1 (PROCESSOR): predecessors [0]
node 2 (SINK):      predecessors [1]
```

This scheme supports linear, fan-out, fan-in, diamond, and multi-sink shapes. Examples:

- **Fan-out** (one source, two parallel processors, merged): `[], [0], [0], [1, 2]`
- **Multi-sink** (one pipeline, two sinks): `[], [0], [1], [1]` (two SINKs both depend on node 1)

For predefined meter types (non-CUSTOM), topology is implicit source→sink and you capture `typeDefinition` directly instead.

### Step 5: Walk each node operator-by-operator

For each node, do the following in order:

1. **Read the operator skeleton** from `${CLAUDE_PLUGIN_ROOT}/references/meter-operators/<OPERATOR>.json`. The file contains the canonical `metadata` shape with required fields represented as `null`, plus an `assumptions[]` block listing safe defaults with their reasoning, plus a `blockers[]` block listing fields that must be answered.
2. **Record user-supplied values** for fields the user has already stated.
3. **Apply safe defaults** from the operator's `assumptions[]` block. Surface the default and its reason explicitly in the design so the user sees what you chose.
4. **Flag remaining nulls as BLOCKERS.** Every `blockers[]` entry and every required field with no user value and no default becomes a numbered blocker in the design output. Do not guess.
5. **Flag unresolved identifiers.** If a field references an external entity by name (e.g. `"schemaId": "usage-events"`, `"storeId": "es1"`, `"connectionName": "prod-kafka"`), flag it as an **unresolved identifier** in the design. Do not attempt to resolve them here — entity resolution is the build skill's responsibility (it calls `resolve_entities` before composing JSON).

### Step 6: Produce the final design

Output in chat (no file writes, no JSON):

- **Meter type** — chosen type + reason
- **Topology** — the flat node list (CUSTOM only)
- **Per-node design** — for each node: `operatorType`, purpose, required fields with source (user / default / blocker), assumptions applied
- **Data flow** — what each node emits to the next, any schemas / field mappings
- **Unresolved identifiers** — names that need real integer IDs before import
- **Blockers** — numbered list of questions the user MUST answer before `/zuora-mediation-meter-build` can run
- **Next step** — "Run `/zuora-mediation-meter-build` with this design once blockers are resolved."

## Do NOT

- Do NOT emit a meter JSON.
- Do NOT write any files.
- Do NOT run the linter.
- Do NOT generate UUIDs.
- Do NOT invent integer IDs for external entities (EventStore, schema, connection). Flag them as unresolved.

The build skill composes the JSON; this skill only designs it.
