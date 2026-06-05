# Complete Meter Examples

> **Default rule**: Always use `CUSTOM` type unless the user explicitly requests a predefined type by name. Examples 1–5 below are shown for reference only — do not use them as templates unless the user has specifically asked for that predefined type.

## Example 1: Direct Pass-Through (DIRECT type)

Simplest meter — no aggregation, no transformation. Use when events already have all required fields.

```json
{
  "name": "Simple Usage Pass-Through",
  "type": "DIRECT",
  "version": "0.0.1",
  "typeDefinition": {
    "sourceType": "ZUORA_BULK_API",
    "schemaId": "12345",
    "fieldMappings": [
      {"name": "accountNumber", "field": "CustomerId", "required": true},
      {"name": "subscriptionNumber", "field": "SubNumber", "required": true},
      {"name": "quantity", "field": "Quantity", "required": true},
      {"name": "uom", "field": "Unit", "required": true},
      {"name": "startDateTime", "field": "UsageDate", "dateFormat": "yyyy-MM-dd'T'HH:mm:ssZ", "required": true}
    ]
  }
}
```

---

## Example 2: Daily Sum Aggregation (SUM type)

Count or sum events per account per day. Use predefined SUM type when no enrichment or filtering needed.

```json
{
  "name": "Daily API Call Aggregation",
  "type": "SUM",
  "version": "0.0.1",
  "typeDefinition": {
    "sourceType": "ZUORA_BULK_API",
    "schemaId": "12345",
    "fieldMappings": [
      {"name": "accountNumber", "field": "CustomerId", "required": true},
      {"name": "quantity", "field": "Quantity", "required": true},
      {"name": "uom", "field": "Unit", "required": true},
      {"name": "startDateTime", "field": "UsageDate", "dateFormat": "yyyy-MM-dd'T'HH:mm:ssZ", "required": true}
    ],
    "configs": {
      "cumulativePeriod": "day",
      "eventTimeFormat": "yyyy-MM-dd'T'HH:mm:ssZ"
    }
  }
}
```

---

## Example 3: Monthly API Call Count (COUNT type)

Count events per month — no quantity field needed, just occurrence counting.

```json
{
  "name": "Monthly API Call Count",
  "type": "COUNT",
  "version": "0.0.1",
  "typeDefinition": {
    "sourceType": "ZUORA_BULK_API",
    "schemaId": "12345",
    "fieldMappings": [
      {"name": "accountNumber", "field": "AccountID", "required": true},
      {"name": "uom", "field": "'API_Calls'", "required": true},
      {"name": "startDateTime", "field": "CallTimestamp", "dateFormat": "yyyy-MM-dd'T'HH:mm:ssZ", "required": true}
    ],
    "configs": {
      "cumulativePeriod": "month",
      "eventTimeFormat": "yyyy-MM-dd'T'HH:mm:ssZ"
    }
  }
}
```

---

## Example 4: Peak Concurrent Users (MAX type)

Track peak value per account per month — useful for capacity-based billing.

```json
{
  "name": "Monthly Peak Concurrent Users",
  "type": "MAX",
  "version": "0.0.1",
  "typeDefinition": {
    "sourceType": "ZUORA_BULK_API",
    "schemaId": "11111",
    "fieldMappings": [
      {"name": "accountNumber", "field": "AccountID", "required": true},
      {"name": "quantity", "field": "ConcurrentUsers", "required": true},
      {"name": "uom", "field": "'Users'", "required": true},
      {"name": "startDateTime", "field": "CheckTime", "dateFormat": "epoch_ms", "required": true}
    ],
    "configs": {
      "cumulativePeriod": "month",
      "eventTimeFormat": "epoch_ms"
    }
  }
}
```

---

## Example 5: Bandwidth Delta Metering (DELTA type)

Source reports cumulative byte counters — DELTA converts to incremental usage.

```json
{
  "name": "Bandwidth Delta Meter",
  "type": "DELTA",
  "version": "0.0.1",
  "typeDefinition": {
    "sourceType": "ZUORA_BULK_API",
    "schemaId": "22222",
    "fieldMappings": [
      {"name": "accountNumber", "field": "CustomerID", "required": true},
      {"name": "quantity", "field": "TotalBytes", "required": true},
      {"name": "uom", "field": "'Bytes'", "required": true},
      {"name": "startDateTime", "field": "ReadingTime", "dateFormat": "yyyy-MM-dd'T'HH:mm:ssZ", "required": true}
    ]
  }
}
```

---

## Example 6: CUSTOM — Filter Then Aggregate

Filter out invalid/zero-quantity events, then aggregate daily. Always FILTER before AGGREGATOR.

```json
{
  "name": "Premium Tier Daily Usage",
  "type": "CUSTOM",
  "version": "0.0.1",
  "tasks": [
    {
      "id": "101",
      "name": "Zuora Source",
      "nodeType": "SOURCE",
      "operatorType": "ZUORA_BULK_API",
      "metadata": {"schemaId": "12345"},
      "predecessors": []
    },
    {
      "id": "201",
      "name": "Premium Tier Filter",
      "nodeType": "PROCESSOR",
      "operatorType": "FILTER",
      "metadata": {
        "ruleCombiner": "and",
        "rules": [
          {"sourceField": "Tier", "operator": "equal", "value": "Premium"},
          {"sourceField": "Quantity", "operator": "gt", "value": "0"}
        ]
      },
      "predecessors": [{"id": "101"}]
    },
    {
      "id": "202",
      "name": "Daily Aggregator",
      "nodeType": "PROCESSOR",
      "operatorType": "AGGREGATOR",
      "metadata": {
        "triggerType": "Timeout",
        "timeoutType": "EventTime",
        "eventTimeField": "EventTime",
        "eventTimeFormat": "yyyy-MM-dd'T'HH:mm:ssZ",
        "timeoutDuration": "1 day",
        "groupFields": ["AccountNumber"],
        "aggregationFields": [
          {"field": "Quantity", "aggregation": "SUM", "targetField": "totalUsage"}
        ]
      },
      "predecessors": [{"id": "201"}]
    },
    {
      "id": "301",
      "name": "Zuora Usage Sink",
      "nodeType": "SINK",
      "operatorType": "ZUORA_USAGE",
      "metadata": {
        "fieldMappings": [
          {"name": "accountNumber", "field": "AccountNumber", "required": true},
          {"name": "quantity", "field": "totalUsage", "required": true},
          {"name": "uom", "field": "Unit", "required": true},
          {"name": "startDateTime", "field": "EventTime", "dateFormat": "yyyy-MM-dd'T'HH:mm:ssZ", "required": true}
        ]
      },
      "predecessors": [{"id": "202"}]
    }
  ]
}
```

**Note**: `ruleCombiner` is lowercase `"and"`. In the ZUORA_USAGE sink, `quantity` maps to `"totalUsage"` (the `targetField` from AGGREGATOR), not the original `"Quantity"`.

---

## Example 7: CUSTOM — Subscription Lookup Then Aggregate

Events have account + charge name but not subscription/charge numbers. Lookup enriches before aggregation.

```json
{
  "name": "Daily Aggregation with Subscription Lookup",
  "type": "CUSTOM",
  "version": "0.0.1",
  "tasks": [
    {
      "id": "101",
      "name": "Zuora Source",
      "nodeType": "SOURCE",
      "operatorType": "ZUORA_BULK_API",
      "metadata": {"schemaId": "12345"},
      "predecessors": []
    },
    {
      "id": "201",
      "name": "Subscription Lookup",
      "nodeType": "PROCESSOR",
      "operatorType": "SUBSCRIPTION_LOOKUP",
      "metadata": {
        "lookupType": "AccountAndChargeName",
        "accountNumberField": "CustomerId",
        "chargeNameField": "ChargeName",
        "continueWhenNoDataFound": false
      },
      "predecessors": [{"id": "101"}]
    },
    {
      "id": "202",
      "name": "Daily Aggregator",
      "nodeType": "PROCESSOR",
      "operatorType": "AGGREGATOR",
      "metadata": {
        "triggerType": "Timeout",
        "timeoutType": "EventTime",
        "eventTimeField": "UsageDate",
        "eventTimeFormat": "yyyy-MM-dd'T'HH:mm:ssZ",
        "timeoutDuration": "1 day",
        "groupFields": ["CustomerId", "subscriptionNumber", "chargeNumber"],
        "aggregationFields": [
          {"field": "Quantity", "aggregation": "SUM", "targetField": "dailyTotal"}
        ]
      },
      "predecessors": [{"id": "201"}]
    },
    {
      "id": "301",
      "name": "Zuora Usage Sink",
      "nodeType": "SINK",
      "operatorType": "ZUORA_USAGE",
      "metadata": {
        "fieldMappings": [
          {"name": "accountNumber", "field": "CustomerId", "required": true},
          {"name": "subscriptionNumber", "field": "subscriptionNumber", "required": true},
          {"name": "chargeNumber", "field": "chargeNumber"},
          {"name": "quantity", "field": "dailyTotal", "required": true},
          {"name": "uom", "field": "Unit", "required": true},
          {"name": "startDateTime", "field": "UsageDate", "dateFormat": "yyyy-MM-dd'T'HH:mm:ssZ", "required": true}
        ]
      },
      "predecessors": [{"id": "202"}]
    }
  ]
}
```

**Pipeline**: `SOURCE(101) → SUBSCRIPTION_LOOKUP(201) → AGGREGATOR(202) → ZUORA_USAGE(301)`

---

## Example 8: CUSTOM — Monthly Transactions with Custom Fields

Aggregate monthly transaction counts and include region/service type as custom fields.

```json
{
  "name": "Monthly Transactions with Metadata",
  "type": "CUSTOM",
  "version": "0.0.1",
  "tasks": [
    {
      "id": "101",
      "name": "Zuora Source",
      "nodeType": "SOURCE",
      "operatorType": "ZUORA_BULK_API",
      "metadata": {"schemaId": "44444"},
      "predecessors": []
    },
    {
      "id": "201",
      "name": "Monthly Aggregator",
      "nodeType": "PROCESSOR",
      "operatorType": "AGGREGATOR",
      "metadata": {
        "triggerType": "Timeout",
        "timeoutType": "EventTime",
        "eventTimeField": "TransactionTime",
        "eventTimeFormat": "yyyy-MM-dd'T'HH:mm:ssZ",
        "timeoutDuration": "30 days",
        "groupFields": ["AccountID", "Region", "ServiceType"],
        "aggregationFields": [
          {"field": "TransactionID", "aggregation": "COUNT", "targetField": "transactionCount"}
        ]
      },
      "predecessors": [{"id": "101"}]
    },
    {
      "id": "301",
      "name": "Zuora Usage Sink",
      "nodeType": "SINK",
      "operatorType": "ZUORA_USAGE",
      "metadata": {
        "fieldMappings": [
          {"name": "accountNumber", "field": "AccountID", "required": true},
          {"name": "quantity", "field": "transactionCount", "required": true},
          {"name": "uom", "field": "'Transactions'", "required": true},
          {"name": "startDateTime", "field": "TransactionTime", "dateFormat": "yyyy-MM-dd'T'HH:mm:ssZ", "required": true},
          {"name": "c_region", "field": "Region", "type": "USAGE_CUSTOM"},
          {"name": "c_serviceType", "field": "ServiceType", "type": "USAGE_CUSTOM"}
        ]
      },
      "predecessors": [{"id": "201"}]
    }
  ]
}
```

**Custom fields**: `c_region` and `c_serviceType` use `"type": "USAGE_CUSTOM"`. The `Region` and `ServiceType` fields remain available in the AGGREGATOR output because they appear in `groupFields` (preserved).

---

## Example 9: CUSTOM — Real-Time Kafka with Deduplication

Real-time Kafka source with deduplication to handle retries. Uses `uniqueKey` for idempotency.

```json
{
  "name": "Real-Time Deduplicated Usage",
  "type": "CUSTOM",
  "version": "0.0.1",
  "tasks": [
    {
      "id": "101",
      "name": "Kafka Source",
      "nodeType": "SOURCE",
      "operatorType": "KAFKA",
      "metadata": {
        "connectionName": "kafka-prod",
        "topic": "usage-events",
        "dataFormat": "JSON"
      },
      "predecessors": []
    },
    {
      "id": "201",
      "name": "Deduplicator",
      "nodeType": "PROCESSOR",
      "operatorType": "DEDUPLICATE",
      "metadata": {
        "checkType": "SpecificFields",
        "specificFields": ["EventID", "AccountNumber"],
        "ttl": "3600"
      },
      "predecessors": [{"id": "101"}]
    },
    {
      "id": "301",
      "name": "Zuora Usage Sink",
      "nodeType": "SINK",
      "operatorType": "ZUORA_USAGE",
      "metadata": {
        "fieldMappings": [
          {"name": "accountNumber", "field": "AccountNumber", "required": true},
          {"name": "subscriptionNumber", "field": "SubscriptionNumber", "required": true},
          {"name": "quantity", "field": "Quantity", "required": true},
          {"name": "uom", "field": "UOM", "required": true},
          {"name": "startDateTime", "field": "Timestamp", "dateFormat": "epoch_ms", "required": true},
          {"name": "uniqueKey", "field": "EventID"}
        ]
      },
      "predecessors": [{"id": "201"}]
    }
  ]
}
```

**Note**: Kafka requires `connectionName` (never inline broker credentials). `dateFormat: "epoch_ms"` for Unix millisecond timestamps.

---

## Example 10: CUSTOM — S3 Batch File Backfill

Process CSV files from S3, deduplicate, enrich, aggregate.

```json
{
  "name": "S3 Usage Backfill",
  "type": "CUSTOM",
  "version": "0.0.1",
  "tasks": [
    {
      "id": "101",
      "name": "S3 Source",
      "nodeType": "SOURCE",
      "operatorType": "S3",
      "metadata": {
        "connectionName": "s3-prod",
        "paths": ["s3://usage-bucket/backfill/2024/"],
        "fileFormat": "CSV",
        "formatOption": {
          "hasHeader": true,
          "delimiter": ","
        }
      },
      "predecessors": []
    },
    {
      "id": "201",
      "name": "Deduplicator",
      "nodeType": "PROCESSOR",
      "operatorType": "DEDUPLICATE",
      "metadata": {
        "checkType": "SpecificFields",
        "specificFields": ["EventId"],
        "ttl": "86400"
      },
      "predecessors": [{"id": "101"}]
    },
    {
      "id": "202",
      "name": "Subscription Lookup",
      "nodeType": "PROCESSOR",
      "operatorType": "SUBSCRIPTION_LOOKUP",
      "metadata": {
        "lookupType": "AccountAndChargeName",
        "accountNumberField": "AccountNum",
        "chargeNameField": "ProductName",
        "appendFields": [
          {"eventField": "subscriptionNumber", "referenceField": "Subscription.Name"},
          {"eventField": "chargeNumber", "referenceField": "RatePlanCharge.ChargeNumber"}
        ]
      },
      "predecessors": [{"id": "201"}]
    },
    {
      "id": "203",
      "name": "Daily Aggregator",
      "nodeType": "PROCESSOR",
      "operatorType": "AGGREGATOR",
      "metadata": {
        "triggerType": "AllFiles",
        "groupFields": ["AccountNum", "subscriptionNumber", "chargeNumber"],
        "aggregationFields": [
          {"field": "UsageAmount", "aggregation": "SUM", "targetField": "totalUsage"}
        ]
      },
      "predecessors": [{"id": "202"}]
    },
    {
      "id": "301",
      "name": "Zuora Usage Sink",
      "nodeType": "SINK",
      "operatorType": "ZUORA_USAGE",
      "metadata": {
        "fieldMappings": [
          {"name": "accountNumber", "field": "AccountNum", "required": true},
          {"name": "subscriptionNumber", "field": "subscriptionNumber", "required": true},
          {"name": "chargeNumber", "field": "chargeNumber"},
          {"name": "quantity", "field": "totalUsage", "required": true},
          {"name": "uom", "field": "Unit", "required": true},
          {"name": "startDateTime", "field": "EventDate", "dateFormat": "yyyy-MM-dd HH:mm:ss", "required": true}
        ]
      },
      "predecessors": [{"id": "203"}]
    }
  ]
}
```

**Notes**:
- S3 source uses `paths` (array), S3 sink uses `path` (single string) — different field names
- `triggerType: "AllFiles"` triggers after all S3 files are processed (file-based source)
- Multiple processors use IDs `201`, `202`, `203`

---

## Example 11: CUSTOM — Multi-Sink Fan-Out (Billing + Archive)

Write processed usage to both Zuora billing and S3 archive simultaneously.

```json
{
  "name": "Usage Billing with Archive",
  "type": "CUSTOM",
  "version": "0.0.1",
  "tasks": [
    {
      "id": "101",
      "name": "Zuora Source",
      "nodeType": "SOURCE",
      "operatorType": "ZUORA_BULK_API",
      "metadata": {"schemaId": "12345"},
      "predecessors": []
    },
    {
      "id": "201",
      "name": "Daily Aggregator",
      "nodeType": "PROCESSOR",
      "operatorType": "AGGREGATOR",
      "metadata": {
        "triggerType": "Timeout",
        "timeoutType": "EventTime",
        "eventTimeField": "EventTime",
        "eventTimeFormat": "yyyy-MM-dd'T'HH:mm:ssZ",
        "timeoutDuration": "1 day",
        "groupFields": ["AccountId"],
        "aggregationFields": [
          {"field": "Amount", "aggregation": "SUM", "targetField": "dailyAmount"}
        ]
      },
      "predecessors": [{"id": "101"}]
    },
    {
      "id": "301",
      "name": "Zuora Usage Sink",
      "nodeType": "SINK",
      "operatorType": "ZUORA_USAGE",
      "metadata": {
        "fieldMappings": [
          {"name": "accountNumber", "field": "AccountId", "required": true},
          {"name": "subscriptionNumber", "field": "SubNumber", "required": true},
          {"name": "quantity", "field": "dailyAmount", "required": true},
          {"name": "uom", "field": "Unit", "required": true},
          {"name": "startDateTime", "field": "EventTime", "dateFormat": "yyyy-MM-dd'T'HH:mm:ssZ", "required": true}
        ]
      },
      "predecessors": [{"id": "201"}]
    },
    {
      "id": "302",
      "name": "S3 Archive Sink",
      "nodeType": "SINK",
      "operatorType": "S3",
      "metadata": {
        "connectionName": "s3-archive",
        "path": "s3://billing-archive/usage/",
        "fileFormat": "JSON"
      },
      "predecessors": [{"id": "201"}]
    }
  ]
}
```

**Note**: Both sinks (301 and 302) reference the same predecessor `"201"`. S3 sink uses `path` (single string, not array).

---

## Quick Reference: Type Selection

> **Reminder**: Default to `CUSTOM` unless the user explicitly names a predefined type. The table below is a reference for when a predefined type has been explicitly requested.

| Scenario | Use | Config Required |
|----------|-----|----------------|
| Pass events unchanged | `DIRECT` | `typeDefinition` with `fieldMappings` |
| Sum per period | `SUM` | `typeDefinition.configs.cumulativePeriod` |
| Count events per period | `COUNT` | `typeDefinition.configs.cumulativePeriod` |
| Peak value per period | `MAX` | `typeDefinition.configs.cumulativePeriod` |
| Average per period | `AVG` | `typeDefinition.configs.cumulativePeriod` |
| Cumulative from counters | `DELTA` | `typeDefinition` |
| Rolling accumulation | `CUMULATIVE` | `typeDefinition.configs.cumulativeMethod` |
| Filter + aggregate | `CUSTOM` | `tasks` array with FILTER → AGGREGATOR |
| Subscription lookup needed | `CUSTOM` | `tasks` with SUBSCRIPTION_LOOKUP |
| Multiple processors / scripts | `CUSTOM` | `tasks` array |
| Multi-sink output | `CUSTOM` | Multiple SINK tasks with same predecessor |
