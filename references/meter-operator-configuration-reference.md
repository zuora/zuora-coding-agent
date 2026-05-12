# Operator Configuration Reference

Complete metadata field reference for each operator. All metadata goes in the `metadata` object of a task.

---

## ZUORA_BULK_API Source

```json
{
  "id": "101",
  "name": "Zuora Events Source",
  "nodeType": "SOURCE",
  "operatorType": "ZUORA_BULK_API",
  "metadata": {
    "schemaId": "12345"
  },
  "predecessors": []
}
```

**Required**: `schemaId` (string — numeric schema ID)
**Limit**: Maximum 1 ZUORA_BULK_API source per meter.

---

## KAFKA Source

```json
{
  "id": "101",
  "name": "Kafka Usage Events",
  "nodeType": "SOURCE",
  "operatorType": "KAFKA",
  "metadata": {
    "connectionName": "my-kafka-connection",
    "topic": "usage-events",
    "dataFormat": "JSON",
    "offsetResetStrategy": "latest",
    "schemaId": "12345",
    "keyFields": ["accountNumber"]
  },
  "predecessors": []
}
```

**Required**: `connectionName`, `topic`, `dataFormat` (JSON, AVRO, CSV)
**Optional**: `offsetResetStrategy` (earliest/latest, default latest), `schemaId`, `keyFields`
**Note**: Never inline credentials — use `connectionName` only.

---

## S3 Source

```json
{
  "id": "101",
  "name": "S3 Usage Files",
  "nodeType": "SOURCE",
  "operatorType": "S3",
  "metadata": {
    "connectionName": "my-s3-connection",
    "paths": ["s3://bucket/events/2026/03/*", "s3://bucket/usage-*.json"],
    "fileFormat": "JSON",
    "formatOption": {"delimiter": ",", "hasHeader": true},
    "incremental": false
  },
  "predecessors": []
}
```

**Required**: `connectionName`, `paths` (ARRAY — multiple paths/wildcards supported), `fileFormat` (JSON, PARQUET, CSV, AVRO)
**Conditional**: `formatOption` required for CSV: `{"delimiter": ",", "hasHeader": true}`. Delimiter: `,` `;` `|` `\t`
**Optional**: `incremental` (boolean, monitor for new files), `schemaId`

---

## LOCAL_FILE Source

```json
{
  "id": "101",
  "name": "Uploaded File",
  "nodeType": "SOURCE",
  "operatorType": "LOCAL_FILE",
  "metadata": {
    "schemaId": "12345"
  },
  "predecessors": []
}
```

**Required**: `schemaId`

---

## SNOWFLAKE Source

```json
{
  "id": "101",
  "name": "Snowflake Source",
  "nodeType": "SOURCE",
  "operatorType": "SNOWFLAKE",
  "metadata": {
    "connectionName": "my-snowflake-connection",
    "database": "USAGE_DB",
    "schema": "PUBLIC",
    "table": "USAGE_EVENTS",
    "warehouse": "COMPUTE_WH"
  },
  "predecessors": []
}
```

**Required**: `connectionName`. Use `table` for simple table scan or `query` for custom SQL (not both).

---

## EVENT_STORE Source

```json
{
  "id": "101",
  "name": "Event Store Reader",
  "nodeType": "SOURCE",
  "operatorType": "EVENT_STORE",
  "metadata": {"storeId": "337"},
  "predecessors": []
}
```

**Required**: `storeId`

---

## FILTER Processor

```json
{
  "id": "201",
  "name": "Data Quality Filter",
  "nodeType": "PROCESSOR",
  "operatorType": "FILTER",
  "metadata": {
    "ruleCombiner": "and",
    "rules": [
      {"sourceField": "quantity", "operator": "gt", "value": "0"},
      {"sourceField": "accountNumber", "operator": "notBlank"},
      {
        "ruleCombiner": "or",
        "rules": [
          {"sourceField": "tier", "operator": "equal", "value": "Premium"},
          {"sourceField": "tier", "operator": "equal", "value": "Enterprise"}
        ]
      }
    ]
  },
  "predecessors": [{"id": "101"}]
}
```

**CRITICAL**: `ruleCombiner` must be **lowercase**: `"and"` or `"or"` — NOT `"AND"` or `"OR"`. This is a react-querybuilder convention.

**Required**: `ruleCombiner`, `rules`

**Filter operators**: `gt` `gte` `lt` `lte` `equal` `notEqual` `contains` `notContains` `startsWith` `notStartsWith` `endsWith` `notEndsWith` `in` `notIn` `blank` `notBlank`

**Nested rules**: A rule object can contain `rules` + `ruleCombiner` for AND/OR nesting.

**`value` field**: Required for all operators EXCEPT `blank` and `notBlank`.

---

## MAP Processor

```json
{
  "id": "202",
  "name": "Field Transformer",
  "nodeType": "PROCESSOR",
  "operatorType": "MAP",
  "metadata": {
    "mapFields": [
      {"transformType": "direct", "sourceField": "CustomerID", "targetField": "accountNumber"},
      {"transformType": "direct", "sourceField": "Qty", "targetField": "quantity"},
      {"transformType": "transform", "sourceField": "StorageKB", "targetField": "StorageGB", "formula": "value / 1048576"},
      {"transformType": "transform", "sourceField": "price", "targetField": "total", "formula": "value * event['quantity']"},
      {"transformType": "transform", "targetField": "currency", "formula": "'USD'"}
    ],
    "excludedFields": ["internalId", "tempFlag"]
  },
  "predecessors": [{"id": "101"}]
}
```

**Required**: `mapFields`
**`transformType`**: `"direct"` (copy as-is) or `"transform"` (apply JavaScript formula)
**Formula variables**: `value` (current sourceField value), `event` (entire event object), `event['fieldName']`
**`excludedFields`**: Fields to remove from output

---

## AGGREGATOR Processor

```json
{
  "id": "201",
  "name": "Daily Usage Aggregator",
  "nodeType": "PROCESSOR",
  "operatorType": "AGGREGATOR",
  "metadata": {
    "triggerType": "Timeout",
    "timeoutType": "EventTime",
    "eventTimeField": "timestamp",
    "eventTimeFormat": "yyyy-MM-dd'T'HH:mm:ssZ",
    "timeoutDuration": "1 day",
    "maxOutOfOrderness": "5m",
    "idleness": "10m",
    "groupFields": ["accountNumber", "productId"],
    "aggregationFields": [
      {"field": "quantity", "aggregation": "SUM", "targetField": "totalQuantity"},
      {"field": "quantity", "aggregation": "COUNT", "targetField": "eventCount"},
      {"field": "quantity", "aggregation": "MAX", "targetField": "peakQuantity"},
      {"field": "quantity", "aggregation": "AVG", "targetField": "avgQuantity"},
      {"field": "counter", "aggregation": "DELTA", "targetField": "deltaValue"}
    ],
    "extraKeepFields": ["region", "uom"],
    "stateExpireTime": "7 days"
  },
  "predecessors": [{"id": "101"}]
}
```

**Required**: `triggerType`, `groupFields`, `aggregationFields`
**`triggerType`**: `"Timeout"` (time window), `"AllFiles"` (file sources only), `"EachFile"` (file sources only)
  - **NOT valid**: `"Realtime"`, `"Event"`, `"Realtime_Event"` — use `REALTIME_EVENT_AGGREGATOR` for streaming
**If `triggerType: "Timeout"`**: also required: `timeoutType` (EventTime or ProcessingTime), `timeoutDuration`
**If `timeoutType: "EventTime"`**: also required: `eventTimeField`
**`timeoutDuration`**: `"1 day"`, `"1 hour"`, `"7 days"`, `"30 days"`, `"1 month"`, etc.
**`aggregationFields`**: Each item needs `field`, `aggregation` (SUM/MIN/MAX/AVG/COUNT/DELTA), `targetField`. No duplicate `targetField` names.
**`extraKeepFields`**: Additional fields to preserve in output beyond `groupFields`
**Output fields**: `groupFields` + `extraKeepFields` + all `targetField` names

---

## SUBSCRIPTION_LOOKUP Processor

### AccountAndChargeName (Most Common)

```json
{
  "id": "201",
  "name": "Subscription Lookup",
  "nodeType": "PROCESSOR",
  "operatorType": "SUBSCRIPTION_LOOKUP",
  "metadata": {
    "lookupType": "AccountAndChargeName",
    "accountNumberField": "CustomerId",
    "chargeNameField": "ProductName",
    "eventTimeField": "UsageDate",
    "eventTimeFormat": "yyyy-MM-dd'T'HH:mm:ssZ",
    "includeSegmentsActiveOnDateOnly": true,
    "continueWhenNoDataFound": false,
    "appendFields": [
      {"eventField": "subscriptionNumber", "referenceField": "Subscription.Name"},
      {"eventField": "chargeNumber", "referenceField": "RatePlanCharge.ChargeNumber"},
      {"eventField": "uom", "referenceField": "RatePlanCharge.UOM"}
    ]
  },
  "predecessors": [{"id": "101"}]
}
```

**Required**: `lookupType`, `accountNumberField`, `chargeNameField`, `appendFields`
**`continueWhenNoDataFound`**: false=drop events with no match (default); true=emit events with null enrichment fields
**Available reference fields**: `Subscription.Name`, `Subscription.Status`, `Subscription.AccountNumber`, `RatePlanCharge.ChargeNumber`, `RatePlanCharge.Name`, `RatePlanCharge.UOM`, `RatePlanCharge.ChargeType`, `Account.AccountNumber`, `Account.Name`, `Account.Currency`

### SubscriptionId Lookup

```json
{
  "lookupType": "SubscriptionId",
  "subscriptionIdField": "SubscriptionID",
  "appendFields": [
    {"eventField": "accountNumber", "referenceField": "Subscription.AccountNumber"}
  ]
}
```

---

## DEDUPLICATE Processor

```json
{
  "id": "202",
  "name": "Deduplicator",
  "nodeType": "PROCESSOR",
  "operatorType": "DEDUPLICATE",
  "metadata": {
    "checkType": "SpecificFields",
    "specificFields": ["eventId", "accountNumber"],
    "ttl": "1 hour",
    "continueWhenDedup": false
  },
  "predecessors": [{"id": "101"}]
}
```

**Required**: `checkType` (All or SpecificFields)
**If `checkType: "SpecificFields"`**: `specificFields` required
**`continueWhenDedup`**: false=discard duplicates; true=emit with flag

---

## RATING Processor

```json
{
  "id": "202",
  "name": "Usage Rating",
  "nodeType": "PROCESSOR",
  "operatorType": "RATING",
  "metadata": {
    "keyFields": ["eventId", "accountNumber", "chargeNumber"],
    "eventTimeField": "UsageDate",
    "eventTimeFormat": "yyyy-MM-dd'T'HH:mm:ssZ",
    "qtyField": "Quantity",
    "outputAmountField": "ratingAmount"
  },
  "predecessors": [{"id": "201"}]
}
```

**Required**: `keyFields`, `eventTimeField`, `eventTimeFormat`, `qtyField`, `outputAmountField` — ALL required.

---

## ACCUMULATOR Processor

Stateful per-group running totals — accumulates values across events without a time window trigger. Use when you need a live running counter/sum per group that persists across events.

```json
{
  "id": "202",
  "name": "Running Totals",
  "nodeType": "PROCESSOR",
  "operatorType": "ACCUMULATOR",
  "metadata": {
    "groupFields": ["accountNumber", "productId"],
    "aggregationFields": [
      {"field": "quantity", "aggregation": "SUM", "targetField": "totalQuantity"},
      {"field": "quantity", "aggregation": "COUNT", "targetField": "eventCount"}
    ]
  },
  "predecessors": [{"id": "101"}]
}
```

**Required**: `groupFields`, `aggregationFields`
**Difference from AGGREGATOR**: AGGREGATOR emits results on a time window (Timeout); ACCUMULATOR emits an updated running total on every event — no time window.
**`aggregationFields`**: Each needs `field`, `aggregation` (SUM/MIN/MAX/AVG/COUNT/DELTA), `targetField`.

---

## CORRELATOR Processor

Correlates a start event and a stop event for the same session/span, accumulates values in between, and emits one output record when the stop event arrives.

```json
{
  "id": "202",
  "name": "Session Correlator",
  "nodeType": "PROCESSOR",
  "operatorType": "CORRELATOR",
  "metadata": {
    "startEventField": "eventType",
    "startEventValue": "session_start",
    "stopEventField": "eventType",
    "stopEventValue": "session_end",
    "timeoutDuration": "1 day",
    "groupFields": ["sessionId", "accountNumber"],
    "aggregationFields": [
      {"field": "bytesUsed", "aggregation": "SUM", "targetField": "totalBytes"}
    ]
  },
  "predecessors": [{"id": "101"}]
}
```

**Required**: `startEventField`, `startEventValue`, `stopEventField`, `stopEventValue`, `timeoutDuration`, `groupFields`, `aggregationFields`
**Use when**: you have paired start/stop events (e.g. session begin/end, call open/close) and want to measure the span.

---

## PARTITION Processor

Re-partitions the data stream by key fields to ensure events with the same key are processed by the same task node (required before stateful operators in parallel pipelines).

```json
{
  "id": "202",
  "name": "Partition by Account",
  "nodeType": "PROCESSOR",
  "operatorType": "PARTITION",
  "metadata": {
    "keyType": "SpecificFields",
    "specificFields": ["accountNumber", "chargeNumber"]
  },
  "predecessors": [{"id": "101"}]
}
```

**Required**: `keyType` (`All` or `SpecificFields`)
**If `keyType: "SpecificFields"`**: `specificFields` required
**Use when**: upstream fan-out (parallel branches) feed into a stateful operator that needs per-key consistency.

---

## HTTP Processor

Calls an external HTTP API per event to enrich it with data from an external service. Use this for enrichment from any REST endpoint (currency rates, product catalogs, external lookups).

```json
{
  "id": "202",
  "name": "External Enrichment",
  "nodeType": "PROCESSOR",
  "operatorType": "HTTP",
  "metadata": {
    "connectionName": "my-http-connection",
    "httpRequestConfig": {
      "urlPath": "/api/enrich",
      "httpMethod": "POST",
      "contentType": "application/json",
      "headers": [{"key": "X-Api-Version", "value": "2"}],
      "parameters": [],
      "body": "{\"accountId\": \"${event.accountNumber}\"}",
      "retries": 3,
      "timeout": 30000
    },
    "httpOutputConfig": {
      "responseSample": "{\"currency\": \"USD\", \"rate\": 1.0}",
      "responseToOutputMapper": [
        {"responseField": "currency", "eventField": "currency"},
        {"responseField": "rate", "eventField": "exchangeRate"}
      ],
      "continueOnFailure": false
    }
  },
  "predecessors": [{"id": "101"}]
}
```

**Required**: `connectionName`, `httpRequestConfig.urlPath`, `httpRequestConfig.httpMethod`
**`body`**: Use `${event.fieldName}` template syntax to inject event fields into the request body.
**`responseToOutputMapper`**: Maps response JSON fields back onto the event. `continueOnFailure: true` emits the event with null enrichment fields if the HTTP call fails.
**Note**: This is an HTTP *Processor* (per-event enrichment call), distinct from the HTTP *Source* (which receives incoming webhooks).

---

## CURRENCY_LOOKUP Processor

Enriches each event with the current exchange rate between two currencies. Use when you need to convert amounts from a source currency to a target currency.

```json
{
  "id": "202",
  "name": "Currency Enrichment",
  "nodeType": "PROCESSOR",
  "operatorType": "CURRENCY_LOOKUP",
  "metadata": {
    "sourceCurrencyField": "currency",
    "targetCurrency": "USD",
    "rateOutputField": "exchangeRate",
    "continueWhenNoDataFound": false
  },
  "predecessors": [{"id": "101"}]
}
```

**Required**: `sourceCurrencyField`, `targetCurrency`, `rateOutputField`
**`continueWhenNoDataFound`**: false=drop events with no rate (default); true=emit with null rate field
**Use when**: events arrive in mixed currencies and need conversion before rating/aggregation.

---

## REALTIME_EVENT_AGGREGATOR Processor

Streaming real-time aggregation triggered on every event (not on a time window). Use for low-latency running totals where you need to emit after every event, not after a time period.

```json
{
  "id": "202",
  "name": "Realtime Aggregator",
  "nodeType": "PROCESSOR",
  "operatorType": "REALTIME_EVENT_AGGREGATOR",
  "metadata": {
    "triggerType": "Realtime",
    "groupFields": ["accountNumber", "productId"],
    "aggregationFields": [
      {"field": "quantity", "aggregation": "SUM", "targetField": "totalQuantity"}
    ],
    "stateExpireTime": "7 days"
  },
  "predecessors": [{"id": "101"}]
}
```

**Required**: `groupFields`, `aggregationFields`
**Difference from AGGREGATOR**: AGGREGATOR uses `triggerType: "Timeout"` (emits after a time window). REALTIME_EVENT_AGGREGATOR emits an updated aggregate after every single event — suitable for real-time dashboards and low-latency billing.
**`stateExpireTime`**: How long to retain group state (e.g. `"7 days"`).
**Note**: Use `AGGREGATOR` with `triggerType: "Timeout"` for batch/windowed aggregation. Use `REALTIME_EVENT_AGGREGATOR` for streaming/per-event aggregation.

---

## BILLING_RATING Processor

Applies Zuora billing rating logic inline as a processor step, computing rated amounts against subscription charges.

```json
{
  "id": "203",
  "name": "Billing Rater",
  "nodeType": "PROCESSOR",
  "operatorType": "BILLING_RATING",
  "metadata": {
    "fieldMappings": [
      {"name": "StartDateTime", "field": "usageDate", "dateFormat": "yyyy-MM-dd", "required": true},
      {"name": "ChargeNumber", "field": "chargeNumber", "required": true},
      {"name": "Quantity", "field": "quantity", "required": true},
      {"name": "UniqueId", "field": "eventId", "required": true},
      {"name": "AccountNumber", "field": "accountNumber", "required": true},
      {"name": "SubscriptionNumber", "field": "subscriptionNumber", "required": true}
    ]
  },
  "predecessors": [{"id": "201"}]
}
```

**Required** (`fieldMappings` entries): `StartDateTime`, `ChargeNumber`, `Quantity`, `UniqueId`, `AccountNumber`, `SubscriptionNumber` — all required.
**Note**: Field names in `name` are **PascalCase** (Zuora billing convention). Use `RATING` processor instead when you need simpler rating without full subscription lookup.

---

## REALTIME_CHARGING Processor

Real-time in-flight charging with configurable price model. Computes a charge amount per event using per-unit or tiered pricing.

```json
{
  "id": "203",
  "name": "Realtime Charger",
  "nodeType": "PROCESSOR",
  "operatorType": "REALTIME_CHARGING",
  "metadata": {
    "groupFields": ["accountNumber"],
    "usageQuantityField": "quantity",
    "usageQuantityAggregation": "SUM",
    "priceModel": "PerUnit",
    "unitPrice": 0.05,
    "priceTable": []
  },
  "predecessors": [{"id": "201"}]
}
```

**Required**: `groupFields`, `usageQuantityField`, `priceModel`
**`priceModel`**: `"PerUnit"` (flat rate × quantity) or `"Tiered"` (use `priceTable`)
**`priceTable`** (for Tiered): array of `{"upTo": number, "price": number}` entries
**`usageQuantityAggregation`**: SUM/MAX/MIN (how to aggregate quantity within group)

---

## SCRIPT_MAP Processor

```json
{
  "id": "203",
  "name": "Custom Transformer",
  "nodeType": "PROCESSOR",
  "operatorType": "SCRIPT_MAP",
  "metadata": {
    "language": "JS",
    "source": "exports.step = function(event, context) { return { accountNumber: event.CustomerId, quantity: event.Qty * event.PricePerUnit }; }"
  },
  "predecessors": [{"id": "101"}]
}
```

**Required**: `language` (JS or PYTHON), `source`
**Script**: `exports.step = function(event, context)` — can return single object, array (expand stream), or null (filter)

---

## SCRIPT_FILTER Processor

Custom JavaScript/Python filter — return `true` to keep the event, `false` to drop it.

```json
{
  "id": "202",
  "name": "Custom Filter",
  "nodeType": "PROCESSOR",
  "operatorType": "SCRIPT_FILTER",
  "metadata": {
    "language": "JS",
    "source": "exports.step = function(event, context) { return event.quantity > 0 && event.accountNumber != null; }"
  },
  "predecessors": [{"id": "101"}]
}
```

**Required**: `language` (JS or PYTHON), `source`
**Script**: Return `true` to keep the event, `false` to discard. Use `FILTER` for declarative rule-based filtering; use `SCRIPT_FILTER` when the logic is too complex for the rule builder.

---

## SCRIPT_AGGREGATOR Processor

Custom JavaScript/Python aggregator with a configurable time window trigger.

```json
{
  "id": "202",
  "name": "Custom Aggregator",
  "nodeType": "PROCESSOR",
  "operatorType": "SCRIPT_AGGREGATOR",
  "metadata": {
    "triggerType": "Timeout",
    "timeoutType": "EventTime",
    "timeoutDuration": "1 day",
    "eventTimeField": "timestamp",
    "eventTimeFormat": "yyyy-MM-dd'T'HH:mm:ssZ",
    "groupFields": ["accountNumber"],
    "language": "JS",
    "source": "exports.step = function(acc, event, context) { acc.total = (acc.total || 0) + event.quantity; return acc; }"
  },
  "predecessors": [{"id": "101"}]
}
```

**Required**: `triggerType`, `groupFields`, `language`, `source`
**Script**: `exports.step = function(accumulator, event, context)` — mutate and return the accumulator object.

---

## SCRIPT_ACCUMULATOR Processor

Custom JavaScript/Python stateful accumulator — emits updated state on every event.

```json
{
  "id": "202",
  "name": "Custom Accumulator",
  "nodeType": "PROCESSOR",
  "operatorType": "SCRIPT_ACCUMULATOR",
  "metadata": {
    "groupFields": ["accountNumber"],
    "language": "JS",
    "source": "exports.step = function(acc, event, context) { acc.runningTotal = (acc.runningTotal || 0) + event.quantity; return acc; }"
  },
  "predecessors": [{"id": "101"}]
}
```

**Required**: `groupFields`, `language`, `source`
**Difference from SCRIPT_AGGREGATOR**: emits on every event (no time window). Use for running totals with custom logic.

---

## SCRIPT_CORRELATOR Processor

Custom JavaScript/Python correlator — matches start/stop event pairs and accumulates state in between.

```json
{
  "id": "202",
  "name": "Custom Correlator",
  "nodeType": "PROCESSOR",
  "operatorType": "SCRIPT_CORRELATOR",
  "metadata": {
    "startEventField": "type",
    "startEventValue": "start",
    "stopEventField": "type",
    "stopEventValue": "end",
    "timeoutDuration": "1 day",
    "groupFields": ["sessionId"],
    "language": "JS",
    "source": "exports.step = function(acc, event, context) { acc.bytes = (acc.bytes || 0) + event.bytes; return acc; }"
  },
  "predecessors": [{"id": "101"}]
}
```

**Required**: `startEventField`, `startEventValue`, `stopEventField`, `stopEventValue`, `timeoutDuration`, `groupFields`, `language`, `source`

---

## ZUORA_USAGE Sink

```json
{
  "id": "301",
  "name": "Zuora Usage Output",
  "nodeType": "SINK",
  "operatorType": "ZUORA_USAGE",
  "metadata": {
    "fieldMappings": [
      {"name": "accountNumber", "field": "accountNumber", "required": true},
      {"name": "subscriptionNumber", "field": "subscriptionNumber", "required": true},
      {"name": "chargeNumber", "field": "chargeNumber"},
      {"name": "quantity", "field": "totalQuantity", "required": true},
      {"name": "uom", "field": "uom", "required": true},
      {"name": "startDateTime", "field": "timestamp", "dateFormat": "yyyy-MM-dd'T'HH:mm:ssZ", "required": true},
      {"name": "endDateTime", "field": "endTime", "dateFormat": "yyyy-MM-dd'T'HH:mm:ssZ"},
      {"name": "description", "field": "usageNote"},
      {"name": "uniqueKey", "field": "eventId"},
      {"name": "c_region", "field": "region", "type": "USAGE_CUSTOM"}
    ],
    "usageKeyGenerationMethod": "SPECIFIC_FIELDS",
    "specificFields": ["accountNumber", "chargeNumber", "startDateTime"]
  },
  "predecessors": [{"id": "201"}]
}
```

**Required field mappings** (use camelCase name values):
- `accountNumber` (required)
- `quantity` (required)
- `uom` (required)
- `startDateTime` (required, needs `dateFormat`)
- `subscriptionNumber` OR `chargeNumber` (at least one required)

**Optional field mappings**: `endDateTime`, `description`, `uniqueKey`
**Custom fields**: prefix with `c_`, set `"type": "USAGE_CUSTOM"`
**`usageKeyGenerationMethod`**: UUID (default, no dedup), INTERNAL (MD5 hash), SPECIFIC_FIELDS (MD5 of `specificFields`), RAW (use `uniqueKey` field value)

---

## ZUORA_RATING Sink

```json
{
  "id": "301",
  "name": "Zuora Rating Output",
  "nodeType": "SINK",
  "operatorType": "ZUORA_RATING",
  "metadata": {
    "fieldMappings": [
      {"name": "AccountNumber", "field": "accountNumber", "required": true},
      {"name": "SubscriptionNumber", "field": "subscriptionNumber", "required": true},
      {"name": "ChargeNumber", "field": "chargeNumber"},
      {"name": "PRPC_id", "field": "prpcId", "required": true},
      {"name": "Quantity", "field": "quantity", "required": true},
      {"name": "StartDateTime", "field": "startDateTime", "dateFormat": "yyyy-MM-dd'T'HH:mm:ssZ", "required": true}
    ]
  },
  "predecessors": [{"id": "201"}]
}
```

**CRITICAL difference from ZUORA_USAGE**: Field names are **PascalCase** (`AccountNumber`, `Quantity`, `StartDateTime`, `SubscriptionNumber`, `ChargeNumber`). Uses `PRPC_id` (Product Rate Plan Charge ID) instead of `uom`.

---

## S3 Sink

```json
{
  "id": "301",
  "name": "S3 Archive",
  "nodeType": "SINK",
  "operatorType": "S3",
  "metadata": {
    "connectionName": "my-s3-connection",
    "path": "s3://bucket/output/",
    "fileFormat": "PARQUET",
    "partitionFields": ["year", "month", "day"],
    "rollingFileSize": 128,
    "rollingFileSizeUnit": "MB"
  },
  "predecessors": [{"id": "201"}]
}
```

**CRITICAL difference from S3 Source**: `path` is a **single string** (NOT an array). S3 source uses `paths` (array).
**Required**: `connectionName`, `path`, `fileFormat`
**For CSV**: `formatOption` with `hasHeader` and `delimiter` is **required**
**Optional**: `partitionFields`, `excludeFields`, `rollingFileSize`, `rollingFileSizeUnit`

---

## SNOWFLAKE Sink

```json
{
  "id": "301",
  "name": "Snowflake Loader",
  "nodeType": "SINK",
  "operatorType": "SNOWFLAKE",
  "metadata": {
    "connectionName": "my-snowflake-connection",
    "database": "USAGE_DB",
    "schema": "PUBLIC",
    "table": "USAGE_RECORDS"
  },
  "predecessors": [{"id": "201"}]
}
```

**Required**: `connectionName`, `table`

---

## KAFKA Sink

```json
{
  "id": "302",
  "name": "Kafka Publisher",
  "nodeType": "SINK",
  "operatorType": "KAFKA",
  "metadata": {
    "connectionName": "my-kafka-connection",
    "topic": "processed-usage",
    "dataFormat": "JSON",
    "keyFields": ["accountNumber", "chargeNumber"]
  },
  "predecessors": [{"id": "201"}]
}
```

**Required**: `connectionName`, `topic`, `dataFormat` (JSON or AVRO)
**Optional**: `keyFields` (determine Kafka partition assignment), `schemaId` (for AVRO)

---

## EVENT_STORE Sink

Writes processed events to a Zuora Event Store for later replay or downstream consumption.

```json
{
  "id": "301",
  "name": "Event Store Writer",
  "nodeType": "SINK",
  "operatorType": "EVENT_STORE",
  "metadata": {
    "storeId": 12345,
    "schemaId": 67890,
    "fieldMappings": [
      {"name": "accountNumber", "field": "accountNumber"},
      {"name": "quantity", "field": "quantity"}
    ]
  },
  "predecessors": [{"id": "201"}]
}
```

**Required**: `storeId` (integer), `schemaId` (integer)
**`fieldMappings`**: Maps event fields to Event Store schema fields. If empty, all event fields are written as-is.
**Note**: `operatorType` is `"EVENT_STORE"` (same string as EVENT_STORE Source). The `nodeType` distinguishes source from sink.

---

## NOOP Sink

A no-operation sink that discards all events. Use for testing pipelines or when the output of a branch is intentionally discarded.

```json
{
  "id": "302",
  "name": "Discard Branch",
  "nodeType": "SINK",
  "operatorType": "NOOP",
  "metadata": {},
  "predecessors": [{"id": "201"}]
}
```

**No required fields** — `metadata` is always empty `{}`.
**Use when**: one branch of a fan-out pipeline should be discarded (e.g. debug/audit branch in test).

---

## Date Format Patterns

| Pattern | Example | Use When |
|---------|---------|----------|
| `yyyy-MM-dd'T'HH:mm:ssZ` | 2026-03-31T10:30:00+0000 | ISO8601 with timezone (recommended) |
| `yyyy-MM-dd'T'HH:mm:ss` | 2026-03-31T10:30:00 | ISO8601 without timezone |
| `yyyy-MM-dd HH:mm:ss` | 2026-03-31 10:30:00 | Standard datetime |
| `yyyy-MM-dd` | 2026-03-31 | Date only |
| `epoch_ms` | 1743421800000 | Milliseconds since epoch |
| `epoch_s` | 1743421800 | Seconds since epoch |
| `MM/dd/yyyy` | 03/31/2026 | US date format |
