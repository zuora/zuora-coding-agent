# Field Mappings and Agent Conventions

## Field Mapping Structure

Field mappings appear in: ZUORA_USAGE and ZUORA_RATING sink `metadata.fieldMappings`, and in predefined meter `typeDefinition.fieldMappings`.

```json
{
  "name": "standardFieldName",
  "field": "sourceEventFieldName",
  "required": true,
  "dateFormat": "yyyy-MM-dd'T'HH:mm:ssZ",
  "type": "USAGE_CUSTOM"
}
```

- **`name`**: Standard output field name (or custom field name for custom fields)
- **`field`**: Source field in the event
- **`required`**: Mark critical fields
- **`dateFormat`**: Java SimpleDateFormat pattern — required for all datetime fields
- **`type`**: Set to `"USAGE_CUSTOM"` for custom fields (prefix name with `c_`)

---

## ZUORA_USAGE Standard Fields (camelCase)

| Field Name | Required | Notes |
|------------|----------|-------|
| `accountNumber` | **Yes** | Zuora account identifier |
| `quantity` | **Yes** | Numeric usage amount |
| `uom` | **Yes** | Unit of measure (must match charge config in Zuora) |
| `startDateTime` | **Yes** | Usage timestamp — needs `dateFormat` |
| `subscriptionNumber` | Conditional | At least one of sub/charge required |
| `chargeNumber` | Conditional | At least one of sub/charge required |
| `endDateTime` | No | End of usage period — needs `dateFormat` |
| `description` | No | Free-text usage note |
| `uniqueKey` | No | Dedup key (used with `usageKeyGenerationMethod: "RAW"`) |
| `c_<name>` | No | Custom fields — add `"type": "USAGE_CUSTOM"` |

---

## ZUORA_RATING Standard Fields (PascalCase — DIFFERENT from ZUORA_USAGE)

| Field Name | Required | Notes |
|------------|----------|-------|
| `AccountNumber` | **Yes** | PascalCase |
| `Quantity` | **Yes** | PascalCase |
| `StartDateTime` | **Yes** | PascalCase, needs `dateFormat` |
| `SubscriptionNumber` | Conditional | PascalCase |
| `ChargeNumber` | Conditional | PascalCase |
| `PRPC_id` | **Yes** | Product Rate Plan Charge ID — replaces `uom` |

**Critical**: ZUORA_RATING uses PascalCase field names AND uses `PRPC_id` instead of `uom`.

---

## Entity Resolution Rules

**Always resolve every entity reference** (event store, schema, connection) through the API — regardless of whether the user provides a name or a numeric ID. The `query` parameter accepts either; the API matches by both name and ID and returns all matches.

Use the appropriate operation on `mcp__zuora-mcp__manage_mediation_meters`:

- **Event store** → call with `operation: "list_event_stores"` and `query: "<name or id>"` — use the `id` from the returned result as `storeId`; the response also contains store metadata
- **Schema** → call with `operation: "list_schemas"` and `query: "<name or id>"` — use the `id` from the returned result as `schemaId`; the response also contains the full field definitions
- **Connection** (Kafka, S3, Snowflake, HTTP) → call with `operation: "list_connections"` and `query: "<name or id>"` — verify `status` is `ACTIVE` and use the returned `id`

### If Multiple Matches Are Returned
Show the list to the user and ask them to choose one before continuing:
> "I found multiple matches for `<input>`. Which one did you mean?"
> 1. `<id>` — `<name>` (`<type/status>`)
> 2. `<id>` — `<name>` (`<type/status>`)

### If Resolution Fails
If the API returns no matching result, **do not finalize the meter**. Return draft JSON with unresolved fields set to `null`, include explicit blockers telling the user which references could not be found, and ask them to verify the name or ID before finalizing.

Do not invent, guess, or silently substitute IDs for unresolved entries. Only use IDs returned by the list operations.

---

## Connection Names

External connectors use `connectionName` (never inline credentials):

| Operator | Required field |
|----------|----------------|
| KAFKA source or sink | `connectionName` |
| S3 source or sink | `connectionName` |
| SNOWFLAKE source or sink | `connectionName` |
| HTTP processor or sink | `connectionName` |

Connection names are managed separately in the Connections feature. If the user has not provided a connection name, ask for it before generating.

---

## ID Rules for Task IDs

- Use simple sequential numeric string IDs: `"101"` for sources, `"201"–"299"` for processors, `"301"` for sinks
- Use `"202"`, `"203"`, etc. for additional processors in the same meter
- IDs are provisional — they are rewritten to UUIDs by the local linter (`lint-meter-json.js --assign-uuids`) before import. Do NOT generate UUIDs yourself and do NOT rely on `validate_meter` to assign them.
- `predecessors[].id` must reference an existing task ID from the same meter

---

## Common Field Mapping Patterns

### Pattern 1: Basic ZUORA_USAGE fields
```json
[
  {"name": "accountNumber", "field": "CustomerID", "required": true},
  {"name": "subscriptionNumber", "field": "SubNumber", "required": true},
  {"name": "quantity", "field": "Usage", "required": true},
  {"name": "uom", "field": "Unit", "required": true},
  {"name": "startDateTime", "field": "EventTime", "dateFormat": "yyyy-MM-dd'T'HH:mm:ssZ", "required": true}
]
```

### Pattern 2: After AGGREGATOR (source field is targetField from aggregator)
```json
[
  {"name": "accountNumber", "field": "accountNumber", "required": true},
  {"name": "subscriptionNumber", "field": "subscriptionNumber", "required": true},
  {"name": "quantity", "field": "totalQuantity", "required": true},
  {"name": "uom", "field": "uom", "required": true},
  {"name": "startDateTime", "field": "timestamp", "dateFormat": "yyyy-MM-dd'T'HH:mm:ssZ", "required": true}
]
```

### Pattern 3: With Custom Fields
```json
[
  {"name": "accountNumber", "field": "accountNumber", "required": true},
  {"name": "chargeNumber", "field": "chargeNumber", "required": true},
  {"name": "quantity", "field": "dailyTotal", "required": true},
  {"name": "uom", "field": "uom", "required": true},
  {"name": "startDateTime", "field": "timestamp", "dateFormat": "yyyy-MM-dd'T'HH:mm:ssZ", "required": true},
  {"name": "c_region", "field": "region", "type": "USAGE_CUSTOM"},
  {"name": "c_serviceType", "field": "serviceType", "type": "USAGE_CUSTOM"}
]
```

### Pattern 4: With Deduplication Key
```json
[
  {"name": "accountNumber", "field": "accountNumber", "required": true},
  {"name": "subscriptionNumber", "field": "subscriptionNumber", "required": true},
  {"name": "quantity", "field": "quantity", "required": true},
  {"name": "uom", "field": "uom", "required": true},
  {"name": "startDateTime", "field": "timestamp", "dateFormat": "epoch_ms", "required": true},
  {"name": "uniqueKey", "field": "eventId"}
]
```

---

## S3 Source vs S3 Sink Path Fields

**CRITICAL DIFFERENCE**:

| | Field Name | Type |
|-|------------|------|
| S3 **Source** | `paths` | **Array** of strings |
| S3 **Sink** | `path` | **Single** string |

---

## AGGREGATOR triggerType Valid Values

Valid for AGGREGATOR: `"Timeout"`, `"AllFiles"`, `"EachFile"`
- `"AllFiles"` — trigger once after all files processed (file-based sources only)
- `"EachFile"` — trigger after each individual file (file-based sources only)
- `"Timeout"` — time-window based (most common, use with `timeoutDuration`)

**NOT valid** for AGGREGATOR: `"Realtime"`, `"Event"`, `"Realtime_Event"` — use `REALTIME_EVENT_AGGREGATOR` operator instead for real-time streaming aggregations.

---

## Clarifying Questions Before Generating

Always clarify if unknown:
1. **Source type** — where does data come from? (Zuora Bulk API, Kafka, S3, etc.)
2. **Schema / EventStore** — which schema or event store ID/name?
3. **Connection names** — for Kafka, S3, Snowflake, HTTP operators
4. **Field names** — what are the actual field names in the source data?
5. **Aggregation period** — daily, weekly, monthly?
6. **Subscription lookup needed?** — do events already have subscriptionNumber/chargeNumber, or need lookup?

---

## AGGREGATION: ZUORA_USAGE Field Source After Different Processors

When events flow through processors, field names in the ZUORA_USAGE `fieldMappings.field` must reference the OUTPUT field names from the last processor, not the original source fields:

- After **AGGREGATOR**: `field` references `targetField` names from `aggregationFields` (e.g., `"totalQuantity"`, `"dailyTotal"`)
- After **MAP**: `field` references `targetField` names from `mapFields`
- After **SUBSCRIPTION_LOOKUP**: `field` can reference `eventField` names from `appendFields` (e.g., `"subscriptionNumber"`, `"chargeNumber"`)
- Original source fields that were preserved (in `groupFields`, `extraKeepFields`, not in `excludedFields`) are still available by their original names
