# Meter Types and Concepts

## What is a Meter?

A meter is a data processing pipeline that transforms raw usage events into billable usage records in the Zuora Mediation Platform. Meters ingest events from sources (Kafka, S3, Zuora Bulk API, HTTP, Snowflake), process them through optional transformations and aggregations, and write results to billing sinks (Zuora Usage, Zuora Rating, S3, Snowflake).

---

## Meter Types

**`type` field is a STRING enum** — always use the string name, never an integer code:

| Type String | Code | Description | Use When |
|------------|------|-------------|----------|
| `"CUSTOM"` | 1 | Full pipeline with tasks array | Complex logic, multiple steps, custom transformations |
| `"DIRECT"` | 10 | Pass-through without transformation | Simple forwarding, no aggregation needed |
| `"DELTA"` | 11 | Difference between successive values | Source reports cumulative totals (convert to increments) |
| `"CUMULATIVE"` | 12 | Accumulate values over time | Rolling accumulation, period-based billing |
| `"SUM"` | 13 | Sum aggregation within time windows | Total usage within fixed periods |
| `"MAX"` | 14 | Maximum value within time windows | Peak usage billing, capacity charges |
| `"MIN"` | 15 | Minimum value within time windows | Minimum commitment tracking |
| `"COUNT"` | 16 | Count events within time windows | Per-transaction billing, API call counting |
| `"AVG"` | 17 | Average value within time windows | Average utilization billing |

### Decision Tree: Which Type to Use?

1. **Need custom business logic, multiple processors, scripting, subscription lookup, or rating?** → `CUSTOM`
2. **Just forwarding events unchanged?** → `DIRECT`
3. **Source reports cumulative totals (need to bill on change)?** → `DELTA`
4. **Need continuous rolling accumulation with SUM/MIN/MAX/AVG/COUNT/DELTA method?** → `CUMULATIVE` (requires `configs.cumulativeMethod`)
5. **Periodic windowed aggregation?**
   - Sum totals → `SUM`
   - Peak value → `MAX`
   - Minimum value → `MIN`
   - Count events → `COUNT`
   - Average → `AVG`
   - All of these require `configs.cumulativePeriod` (day, week, month, year)

---

## CUSTOM Meter Structure

CUSTOM meters require a `tasks` array defining the pipeline. No `typeDefinition` needed.

```json
{
  "name": "My Custom Meter",
  "type": "CUSTOM",
  "version": "0.0.1",
  "tasks": [
    {"id": "101", "name": "Source", "nodeType": "SOURCE", ...},
    {"id": "201", "name": "Processor", "nodeType": "PROCESSOR", "predecessors": [{"id": "101"}], ...},
    {"id": "301", "name": "Sink", "nodeType": "SINK", "predecessors": [{"id": "201"}], ...}
  ]
}
```

**Task ID convention**: `"101"` for sources, `"201"–"299"` for processors, `"301"` for sinks. IDs are sequential strings — they will be automatically converted to UUIDs by the system after validation.

**predecessors**: References task IDs that feed into this task. SOURCE tasks have empty `predecessors: []`. PROCESSOR and SINK tasks must have at least one predecessor.

---

## Predefined Meter Structure

Predefined types (DIRECT, DELTA, CUMULATIVE, SUM, MAX, MIN, COUNT, AVG) use `typeDefinition` instead of tasks. No `tasks` array.

```json
{
  "name": "My Predefined Meter",
  "type": "SUM",
  "version": "0.0.1",
  "typeDefinition": {
    "sourceType": "ZUORA_BULK_API",
    "schemaId": "12345",
    "fieldMappings": [
      {"name": "accountNumber", "field": "CustomerID", "required": true},
      {"name": "quantity", "field": "Usage", "required": true},
      {"name": "uom", "field": "Unit", "required": true},
      {"name": "startDateTime", "field": "Timestamp", "dateFormat": "yyyy-MM-dd'T'HH:mm:ssZ", "required": true}
    ],
    "configs": {
      "cumulativePeriod": "month",
      "eventTimeFormat": "yyyy-MM-dd'T'HH:mm:ssZ"
    }
  }
}
```

### typeDefinition Fields

- `sourceType` (required): `"ZUORA_BULK_API"` or `"LOCAL_FILE"`
- `schemaId` (required): numeric string event schema ID, or `"STANDARD"`
- `fieldMappings` (required unless schemaId is STANDARD): array mapping source fields to standard output fields
- `configs` (conditional):
  - CUMULATIVE type: must include `cumulativeMethod` (SUM, MIN, MAX, AVG, COUNT, DELTA)
  - SUM, MAX, MIN, COUNT, AVG types: must include `cumulativePeriod` (day, week, month, year)
  - Optional: `eventTimeFormat`, `timeoutDuration`

---

## Meter Version

Every meter has versions using semantic versioning (e.g., `"0.0.1"`, `"1.0.0"`).

- Default initial version: `"0.0.1"`
- `versionStatus`: 1=ACTIVE, 2=INACTIVE — only one version active at a time
- `runStatus`: 1=NEVER_RUN, 2=TESTING, 3=TESTING_FAILED, 4=TESTING_PASSED, 5=RUNNING, 6=PAUSED, 7=COMPLETED, 8=FAILED, 9=CANCELED, 10=INITIALIZING

---

## Key Constraints

- Meter name must be unique within tenant
- CUSTOM meter type cannot be changed after creation
- `tasks` only valid for CUSTOM; `typeDefinition` only valid for non-CUSTOM types
- Maximum 1 `ZUORA_BULK_API` source task per meter
- All task IDs must be unique within a meter
- Pipeline must be a connected directed acyclic graph (no cycles, no unreachable nodes)
- Every CUSTOM meter must have at least one SOURCE and at least one SINK task