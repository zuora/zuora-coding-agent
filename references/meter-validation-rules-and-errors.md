# Validation Rules and Error Messages

## Meter-Level Validation

| Rule | Error Message |
|------|--------------|
| Name cannot be blank | `"Meter name cannot be blank"` |
| Name must be unique in tenant | `"Meter name already exists"` |
| Type must be valid string | `"Invalid meter type"` |
| CUSTOM meters cannot have `typeDefinition` | `"TypeDefinition not allowed for CUSTOM meters"` |
| Predefined meters (non-CUSTOM) require `typeDefinition` | `"TypeDefinition required for predefined meter types"` |

---

## Version Validation

| Rule | Error Message |
|------|--------------|
| Must match `^\d+\.\d+\.\d+$` (e.g., `"0.0.1"`, `"1.0.0"`) | `"Invalid version format"` |
| Must be unique within meter | `"Version already exists"` |
| CUSTOM meter must include `tasks`, `metadata`, or `versionDetail` | `"Version must include versionDetail, metadata, or tasks"` |

Invalid version strings: `"1.0"`, `"v1.0.0"`, `"1.0.0-beta"` — all rejected.

---

## Task Validation (CUSTOM Meters)

### Required Fields
| Rule | Error Message |
|------|--------------|
| `id` is required | `"Task id is required"` |
| `name` is required | `"Task name is required"` |
| All task IDs must be unique | `"Duplicate task ID found: {id}"` |

### Pipeline Structure
| Rule | Error Message |
|------|--------------|
| At least one SOURCE task | `"No SOURCE task found"` |
| At least one SINK task | `"No SINK task found"` |
| All tasks reachable from sources | `"Pipeline contains unreachable tasks"` |
| No cycles allowed | `"Circular dependency detected"` |
| Max 1 ZUORA_BULK_API source per meter | `"Only one ZUORA_BULK_API source allowed per meter"` |

### Predecessor Rules
| Rule | Error Message |
|------|--------------|
| SOURCE tasks must have empty `predecessors: []` | `"SOURCE task cannot have predecessors"` |
| PROCESSOR tasks need at least one predecessor | `"PROCESSOR task requires predecessors"` |
| SINK tasks need at least one predecessor | `"SINK task requires predecessors"` |
| Predecessor ID must exist in meter | `"Predecessor task not found: {id}"` |

### Operator / NodeType Consistency
| Rule | Error Message |
|------|--------------|
| `operatorType` must be valid for declared `nodeType` | `"{operatorType} is not a valid {nodeType} operator"` |

Valid nodeType / operatorType combinations:
- `SOURCE`: KAFKA, S3, ZUORA_BULK_API, LOCAL_FILE, SNOWFLAKE, HTTP, EVENT_STORE
- `PROCESSOR`: AGGREGATOR, FILTER, MAP, SCRIPT_MAP, SCRIPT_FILTER, DEDUPLICATE, SUBSCRIPTION_LOOKUP, CURRENCY_LOOKUP, HTTP, RATING, BILLING_RATING, REALTIME_CHARGING, SCRIPT_AGGREGATOR, ACCUMULATOR, REALTIME_EVENT_AGGREGATOR, CORRELATOR, PARTITION
- `SINK`: ZUORA_USAGE, ZUORA_RATING, S3, SNOWFLAKE, KAFKA, HTTP, EVENT_STORE, NOOP

---

## TypeDefinition Validation (Predefined Meters)

| Rule | Error Message |
|------|--------------|
| `sourceType` is required | `"sourceType is required"` |
| `sourceType` must be `"ZUORA_BULK_API"` or `"LOCAL_FILE"` | `"Invalid sourceType"` |
| `schemaId` is required | `"schemaId is required"` |
| `schemaId` must be numeric or `"STANDARD"` | `"Invalid schemaId"` |
| `fileId` required when `sourceType = "LOCAL_FILE"` | `"fileId required for LOCAL_FILE source"` |
| `fieldMappings` required unless `schemaId = "STANDARD"` | `"fieldMappings required"` |
| Each required standard field must be mapped | `"Missing required field mapping: {fieldName}"` |

### Configs by Meter Type

| Type | Required config | Valid values |
|------|----------------|-------------|
| `CUMULATIVE` | `cumulativeMethod` | `SUM`, `MIN`, `MAX`, `AVG`, `COUNT`, `DELTA` |
| `SUM`, `MAX`, `MIN`, `COUNT`, `AVG` | `cumulativePeriod` | `"day"`, `"week"`, `"month"`, `"year"` |
| `DELTA`, `DIRECT` | none required | — |

Error messages: `"cumulativeMethod required for CUMULATIVE type"` / `"cumulativePeriod required for aggregation types"` / `"Invalid cumulativePeriod: {value}"`

---

## AGGREGATOR Metadata Validation

| Rule | Error Message |
|------|--------------|
| `triggerType` must be `"Timeout"`, `"AllFiles"`, or `"EachFile"` | `"Invalid triggerType"` |
| When `triggerType = "Timeout"`, `timeoutType` required | `"timeoutType required"` |
| When `timeoutType = "EventTime"`, `eventTimeField` required | `"eventTimeField required for EventTime timeout"` |
| `timeoutDuration` required for Timeout trigger | `"timeoutDuration required"` |
| `aggregationFields` cannot be empty | `"aggregationFields cannot be empty"` |
| No duplicate `targetField` names | `"Duplicate aggregation targetField: {name}"` |
| At least one `groupField` or `timeField` | `"At least one group field or time field required"` |
| Each aggregationField must have `field`, `aggregation`, `targetField` | `"aggregationFields cannot be empty"` |

**Note**: `"Realtime"`, `"Realtime_Event"`, `"Event"` are NOT valid AGGREGATOR triggerType values. For real-time streaming aggregation, use the `REALTIME_EVENT_AGGREGATOR` operator instead.

Valid `aggregation` values: `SUM`, `MIN`, `MAX`, `AVG`, `COUNT`, `DELTA`

---

## FILTER Metadata Validation

| Rule | Error Message |
|------|--------------|
| When `rules` list present, `ruleCombiner` required | `"ruleCombiner required when rules present"` |
| `ruleCombiner` must be `"and"` or `"or"` (lowercase) | `"Invalid ruleCombiner"` |
| Leaf rule must have `sourceField` + `operator` | `"sourceField and operator required for leaf rule"` |
| `value` required for most operators (not `blank`/`notBlank`) | `"value required for {operator}"` |

**Critical**: `ruleCombiner` must be lowercase `"and"` / `"or"` — NOT uppercase `"AND"` / `"OR"`.

Valid `operator` values: `gt`, `gte`, `lt`, `lte`, `equal`, `notEqual`, `contains`, `notContains`, `startsWith`, `notStartsWith`, `endsWith`, `notEndsWith`, `in`, `notIn`, `blank`, `notBlank`

---

## MAP Metadata Validation

| Rule | Error Message |
|------|--------------|
| Each `mapField` must have `transformType` and `targetField` | `"transformType required"` / `"targetField required"` |
| `transformType` must be `"direct"` or `"transform"` | `"Invalid transformType"` |
| When `transformType = "transform"`, `formula` required | `"formula required for transform type"` |

---

## SUBSCRIPTION_LOOKUP Validation

| Rule | Error Message |
|------|--------------|
| `lookupType` is required | `"lookupType required"` |
| Must be one of: `AccountAndChargeName`, `SubscriptionId`, `Account`, `Product`, `CustomObject`, `Advanced`, `ZDP` | `"Invalid lookupType"` |

Type-specific requirements:
| `lookupType` | Required fields |
|---|---|
| `AccountAndChargeName` | `accountNumberField` + `chargeNameField` |
| `SubscriptionId` | `subscriptionIdField` |
| `Account`, `Product`, `CustomObject` | `mapFields` + `appendFields` |
| `Advanced` | `mapFields` + `appendFields` + `sql` |
| `ZDP` | `table` + `mapFields` + `appendFields` |

---

## RATING Metadata Validation

All five fields are required (error: `"{field} is required"`):
- `keyFields` (non-empty list)
- `eventTimeField`
- `eventTimeFormat`
- `qtyField`
- `outputAmountField`

---

## Field Mapping Validation

| Rule | Error Message |
|------|--------------|
| `name` required on each mapping | `"Field mapping name required"` |
| `field` required on each mapping | `"Field mapping field required"` |
| `accountNumber` must be mapped | `"Required field not mapped: accountNumber"` |
| `quantity` must be mapped | `"Required field not mapped: quantity"` |
| `uom` must be mapped (ZUORA_USAGE) | `"Required field not mapped: uom"` |
| `startDateTime` must be mapped | `"Required field not mapped: startDateTime"` |
| `subscriptionNumber` OR `chargeNumber` required | `"Required field not mapped: subscriptionNumber"` |
| `dateFormat` must be valid Java SimpleDateFormat | `"Invalid dateFormat: {format}"` |

**ZUORA_USAGE** uses camelCase: `accountNumber`, `quantity`, `uom`, `startDateTime`
**ZUORA_RATING** uses PascalCase: `AccountNumber`, `Quantity`, `StartDateTime` — and uses `PRPC_id` instead of `uom`

Custom fields: prefix name with `c_` and set `"type": "USAGE_CUSTOM"` (e.g., `c_region`, `c_serviceType`).

---

## Script Operator Validation

| Rule | Error Message |
|------|--------------|
| `language` required | `"language required for script operator"` |
| `language` must be `"JS"` or `"PYTHON"` | `"Invalid language"` |
| `source` (script code) required | `"source code required for script operator"` |

---

## ZUORA_USAGE Sink Special Rules

| Rule | Error Message |
|------|--------------|
| `deleteOnly=true` requires `deleteConditionColumn` | `"deleteConditionValues required for delete-only feed"` |
| `deleteConditionColumn` requires `deleteConditionValues` | `"deleteConditionValues required for delete-only feed"` |

---

## Common Self-Correction Patterns

### Error: "No SOURCE task found"
- Check that `nodeType: "SOURCE"` is set on exactly one task
- Check that `operatorType` is a valid SOURCE operator

### Error: "Predecessor task not found: {id}"
- All `predecessors[].id` values must match existing task `id` fields exactly
- Task IDs are strings (`"101"`, not `101`)

### Error: "Required field not mapped: uom"
- ZUORA_USAGE sink must have a mapping with `"name": "uom"`
- Ensure the source event has a field containing the unit of measure value

### Error: "eventTimeField required for EventTime timeout"
- AGGREGATOR with `timeoutType: "EventTime"` must specify `eventTimeField`
- The value must be the name of a field in the incoming event that contains the timestamp

### Error: "Invalid triggerType"
- Only `"Timeout"`, `"AllFiles"`, `"EachFile"` are valid for AGGREGATOR
- For real-time use `REALTIME_EVENT_AGGREGATOR` operator

### Error: "TypeDefinition not allowed for CUSTOM meters"
- Remove the `typeDefinition` block and use `tasks` array instead
- `typeDefinition` is only for predefined types (DIRECT, DELTA, SUM, etc.)
