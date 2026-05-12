# Operator Selection Guide

## Overview

Every task in a CUSTOM meter uses an `operatorType` that determines its behavior and required metadata. Operators are grouped by pipeline position: SOURCE (read data in), PROCESSOR (transform/filter/aggregate/enrich), SINK (write data out).

---

## SOURCE Operators

| Operator | When to Use |
|----------|-------------|
| `ZUORA_BULK_API` | Receive events pushed via Zuora Bulk API — **primary Zuora integration**. Max 1 per meter. Requires `metadata.schemaId`. |
| `KAFKA` | Real-time streaming from Kafka topics (use skeleton `KAFKA_SOURCE.json`, nodeType SOURCE). Requires `connectionName`, `topic`, `dataFormat`. |
| `S3` | Batch file processing from S3 (use skeleton `S3_SOURCE.json`, nodeType SOURCE). Requires `connectionName`, `paths` (array), `fileFormat`. |
| `LOCAL_FILE` | Manual file uploads for testing/backfill. Requires `schemaId`. |
| `SNOWFLAKE` | Pull from Snowflake data warehouse. Requires `connectionName`. |
| `EVENT_STORE` | Replay previously stored events (use skeleton `EVENT_STORE_SOURCE.json`, nodeType SOURCE). Requires `storeId`. |

### Source Operator Selection by User Intent

**User says → operatorType**
- "read from Zuora", "Zuora events", "Zuora bulk API", "ingest from Zuora" → `ZUORA_BULK_API`
- "Kafka stream", "real-time events", "streaming source", "consume from Kafka topic" → `KAFKA` (nodeType SOURCE, skeleton `KAFKA_SOURCE.json`)
- "read from S3", "S3 files", "batch file input", "process files from S3 bucket" → `S3` (nodeType SOURCE, skeleton `S3_SOURCE.json`)
- "replay events", "reprocess stored events", "event store source", "read from event store" → `EVENT_STORE` (nodeType SOURCE, skeleton `EVENT_STORE_SOURCE.json`)
- "test file", "upload file", "backfill from file", "local file input" → `LOCAL_FILE`
- "Snowflake source", "pull from Snowflake", "Snowflake data" → `SNOWFLAKE`

---

## PROCESSOR Operators

### Filtering & Deduplication

| Operator | When to Use |
|----------|-------------|
| `FILTER` | Remove events that don't match conditions using declarative rules (field comparisons: gt, equal, contains, blank, etc.). **`ruleCombiner` must be lowercase: `"and"` or `"or"`.** |
| `SCRIPT_FILTER` | Complex filter conditions requiring JavaScript logic. Returns boolean. |
| `DEDUPLICATE` | Remove duplicate events within a time window. Requires `checkType` (All or SpecificFields) and optionally `ttl`. |

**User says → Operator key**
- "filter events", "remove events where", "keep only events that", "drop invalid events", "filter by field value", "exclude zero quantity", "only events where field equals" → `FILTER`
- "complex filter", "filter with custom logic", "JavaScript filter", "conditional filter" → `SCRIPT_FILTER`
- "remove duplicates", "deduplicate", "prevent duplicate processing", "avoid reprocessing", "idempotent events" → `DEDUPLICATE`

### Transformation

| Operator | When to Use |
|----------|-------------|
| `MAP` | Rename fields, copy values, apply simple arithmetic formulas. Uses `mapFields` array with `transformType: "direct"` or `"transform"`. |
| `SCRIPT_MAP` | Complex per-event transformations, business logic, event expansion (1→many), or consolidation. JavaScript `exports.step = function(event, context) { return result; }`. |
| `PARTITION` | Route events into parallel processing paths by key. |

**User says → Operator key**
- "rename fields", "copy field value", "map fields", "convert units", "simple arithmetic", "field transformation", "field remapping" → `MAP`
- "complex transformation", "JavaScript transform", "custom logic per event", "split one event into multiple", "expand event", "business logic transform" → `SCRIPT_MAP`
- "route by key", "split events by type", "parallel paths by field", "partition events" → `PARTITION`

### Aggregation & Accumulation

| Operator | When to Use |
|----------|-------------|
| `AGGREGATOR` | **Most common aggregation**. Time-windowed aggregations (SUM, MAX, MIN, AVG, COUNT, DELTA). Uses `triggerType: "Timeout"` with `timeoutDuration`. Outputs one record per window per group. Valid `triggerType` values: `"Timeout"`, `"AllFiles"`, `"EachFile"`. **`"Realtime"` and `"Realtime_Event"` are NOT valid for AGGREGATOR** — use `REALTIME_EVENT_AGGREGATOR` instead. |
| `SCRIPT_AGGREGATOR` | Custom aggregation with JavaScript. Same window config as AGGREGATOR plus `language` and `source` script. |
| `ACCUMULATOR` | Running total per key across all time (persists across pipeline runs). |
| `REALTIME_EVENT_AGGREGATOR` | Streaming aggregation — outputs updated aggregate after EACH event (no window boundary). Low-latency. |
| `CORRELATOR` | Pair start and stop events into a single derived event. Session-based billing, duration calculation. |

**User says → Operator key**
- "group events by time window", "sum per hour", "hourly totals", "time-based aggregation", "bucket events", "window function", "aggregate per period", "count per window", "max per interval", "rolling average", "periodic aggregation", "sum usage every hour", "group by time" → `AGGREGATOR`
- "custom aggregation logic", "JavaScript aggregation", "custom window function" → `SCRIPT_AGGREGATOR`
- "running total", "cumulative sum per account", "running counter", "total across all time", "persist total across runs", "lifetime total per customer" → `ACCUMULATOR`
- "low latency aggregation", "aggregate on every event", "streaming aggregate", "real-time aggregate", "update aggregate immediately", "per-event aggregate output" → `REALTIME_EVENT_AGGREGATOR`
- "pair start and stop", "session billing", "duration calculation", "correlate start and end events", "match open and close events", "session length", "start stop pair" → `CORRELATOR`

### Enrichment & Lookup

| Operator | When to Use |
|----------|-------------|
| `SUBSCRIPTION_LOOKUP` | **Add Zuora subscription/charge numbers to events**. Most common enrichment. Supports `lookupType: "AccountAndChargeName"` (requires `accountNumberField` + `chargeNameField`), `"SubscriptionId"`, `"Account"`, `"Product"`, `"Advanced"` (custom SQL). Appends fields via `appendFields`. |
| `CURRENCY_LOOKUP` | Convert currency values between denominations using exchange rates. |
| `HTTP` | Call external HTTP API and merge response into event. Third-party enrichment. |

**User says → Operator key**
- "add subscription info", "enrich with subscription", "add charge number", "add subscription number", "lookup subscription", "append subscription data", "add Zuora subscription to events" → `SUBSCRIPTION_LOOKUP`
- "currency conversion", "convert currency", "exchange rate", "multi-currency", "FX conversion" → `CURRENCY_LOOKUP`
- "call external API", "enrich from third party", "HTTP enrichment", "external lookup", "call REST API per event" → `HTTP` (as PROCESSOR)

### Rating & Charging

| Operator | When to Use |
|----------|-------------|
| `BILLING_RATING` | Delegate rating to Zuora's billing engine. |
| `REALTIME_CHARGING` | Real-time charge calculation with immediate balance deduction. Prepaid/wallet scenarios. |

**User says → Operator key**
- "calculate charge", "apply pricing rules", "rate usage", "billing engine", "Zuora rating" → `BILLING_RATING`
- "real-time charge", "prepaid billing", "wallet deduction", "immediate charge", "balance deduction" → `REALTIME_CHARGING`

---

## SINK Operators

| Operator | When to Use |
|----------|-------------|
| `ZUORA_USAGE` | **Standard billing output** — post usage records to Zuora for billing. Requires `fieldMappings`. Standard fields: accountNumber, quantity, uom, startDateTime + subscriptionNumber or chargeNumber. |
| `ZUORA_RATING` | Post pre-rated usage to Zuora. PascalCase field names: AccountNumber, Quantity, StartDateTime, PRPC_id (Product Rate Plan Charge ID). |
| `S3` | Write files to S3 (use skeleton `S3_SINK.json`, nodeType SINK). Requires `connectionName`, `path` (single string — NOT array like S3 source), `fileFormat`. For CSV: `formatOption` with `hasHeader` and `delimiter` is required. |
| `SNOWFLAKE` | Load records into Snowflake. Requires `connectionName`, `table`. |
| `KAFKA` | Publish processed events to Kafka topic (use skeleton `KAFKA_SINK.json`, nodeType SINK). Requires `connectionName`, `topic`, `dataFormat`. |
| `HTTP` | POST events to HTTP endpoints. Requires `connectionName`, `httpRequestConfig`. |
| `EVENT_STORE` | Persist events to internal event store for replay/audit (use skeleton `EVENT_STORE_SINK.json`, nodeType SINK). |
| `NOOP` | Discard all output — use only for pipeline testing. |

**User says → operatorType**
- "post usage to Zuora", "send billing records", "write usage", "Zuora billing output", "submit usage records", "standard billing sink" → `ZUORA_USAGE`
- "post rated usage", "pre-rated billing", "already priced usage", "Zuora rating output" → `ZUORA_RATING`
- "write to S3", "archive to S3", "output files to S3", "S3 output", "save to S3 bucket" → `S3` (nodeType SINK, skeleton `S3_SINK.json`)
- "load into Snowflake", "Snowflake output", "write to Snowflake" → `SNOWFLAKE` (nodeType SINK, skeleton `SNOWFLAKE_SINK.json`)
- "publish to Kafka", "send to Kafka topic", "Kafka output", "downstream Kafka" → `KAFKA` (nodeType SINK, skeleton `KAFKA_SINK.json`)
- "store events for replay", "save to event store", "audit events", "persist events" → `EVENT_STORE` (nodeType SINK, skeleton `EVENT_STORE_SINK.json`)
- "test pipeline", "discard output", "no output", "testing only" → `NOOP`

---

## Common Pipeline Patterns

### Pattern 1: Simple Zuora Pass-Through (use DIRECT type instead when no processors needed)
```
ZUORA_BULK_API → ZUORA_USAGE
```

### Pattern 2: Aggregation Pipeline
```
ZUORA_BULK_API → AGGREGATOR → ZUORA_USAGE
```

### Pattern 3: Enrichment + Aggregation
```
ZUORA_BULK_API → SUBSCRIPTION_LOOKUP → AGGREGATOR → ZUORA_USAGE
```

### Pattern 4: Filter Before Aggregation (always filter BEFORE aggregating)
```
ZUORA_BULK_API → FILTER → AGGREGATOR → ZUORA_USAGE
```

### Pattern 5: Full Pipeline with Enrichment
```
ZUORA_BULK_API → FILTER → SUBSCRIPTION_LOOKUP → AGGREGATOR → ZUORA_USAGE
```

### Pattern 6: Multi-Sink Fan-Out
```
KAFKA → FILTER → MAP → AGGREGATOR → ZUORA_USAGE
                                   → S3
```
Both sinks reference the same predecessor task ID.

### Pattern 7: Real-Time Streaming
```
KAFKA → DEDUPLICATE → REALTIME_EVENT_AGGREGATOR → ZUORA_USAGE + KAFKA
```

### Pattern 8: Rating Pipeline
```
KAFKA → CORRELATOR → AGGREGATOR → RATING_RULE_ENGINE → ZUORA_RATING
```

### Pattern 9: File Backfill
```
S3 → DEDUPLICATE → MAP → SUBSCRIPTION_LOOKUP → AGGREGATOR → ZUORA_USAGE
```

---

## Operator Selection Matrix

| Scenario | Use |
|----------|-----|
| Remove invalid/zero-quantity events | `FILTER` |
| Complex filter conditions | `SCRIPT_FILTER` |
| Prevent duplicate processing | `DEDUPLICATE` |
| Rename fields, unit conversion | `MAP` |
| Complex per-event logic | `SCRIPT_MAP` |
| Sum/count/max per time window | `AGGREGATOR` |
| Custom windowed aggregation | `SCRIPT_AGGREGATOR` |
| Running counter per account | `ACCUMULATOR` |
| Low-latency per-event aggregation | `REALTIME_EVENT_AGGREGATOR` |
| Session-based billing (start/stop) | `CORRELATOR` |
| Add subscription/charge IDs | `SUBSCRIPTION_LOOKUP` |
| Multi-currency billing | `CURRENCY_LOOKUP` |
| Calculate charge from usage | `RATING` |
| Post usage to Zuora billing | `ZUORA_USAGE` |
| Post already-priced usage | `ZUORA_RATING` |
| Archive data | `S3` sink |
| Test pipeline without writing | `NOOP` sink |

---

## Performance Anti-Patterns to Avoid

- ❌ **FILTER after AGGREGATOR** — filter before aggregating for better performance
- ❌ **Multiple AGGREGATOR without clear windows** — creates nested aggregation complexity
- ❌ **SCRIPT_MAP followed by MAP** — combine into single SCRIPT_MAP
- ❌ **Multiple DEDUPLICATE** — use single deduplicate with comprehensive key
