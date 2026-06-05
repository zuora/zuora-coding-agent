# Script Operator Code Generation Guide

This guide covers writing source code for the three Zuora Mediation script operators:
- **SCRIPT_MAP** — transform one event into one event (or null to drop it, or an array to expand it)
- **SCRIPT_AGGREGATOR** — aggregate many events into one per partition over a time window
- **SCRIPT_ACCUMULATOR** — accumulate events with custom release logic (emits on every event)

Both JavaScript and Python are supported. Default to **JavaScript** unless the user specifies Python.

---

## Function Signatures

### JavaScript

```js
// SCRIPT_MAP and SCRIPT_AGGREGATOR
exports.step = function(payload, context) {
    return newPayload;  // object, array, or null
}

// SCRIPT_ACCUMULATOR — receives batched events
exports.step = function(events, context) {
    return result;  // object or null
}
```

### Python

```python
# SCRIPT_MAP and SCRIPT_AGGREGATOR
def step(payload, context):
    return new_payload  # dict, list, or None

# SCRIPT_ACCUMULATOR — receives batched events
def step(events, context):
    return result  # dict or None
```

---

## State API (`context.state`)

State is keyed, persistent, and scoped to the partition key. Use it to maintain values across events.

### JavaScript

```js
// Reading
const value = context.state.get('myKey');               // returns object or null
const str = context.state.getString('myKey');           // returns string or null
const values = context.state.getAll(['k1', 'k2']);      // returns {k1: ..., k2: ...}

// Writing
context.state.set('myKey', { count: 1, total: 0 });    // store any JSON-serializable value
context.state.setString('myKey', 'rawString');
context.state.remove('myKey');
context.state.set('myKey', null);                       // same as remove
```

### Python

```python
# Reading
value = context.state.get('myKey')
string_value = context.state.getString('myKey')
values = context.state.getAll(['k1', 'k2'])

# Writing
context.state.set('myKey', {'count': 1, 'total': 0})
context.state.setString('myKey', 'rawString')
context.state.remove('myKey')
context.state.set('myKey', None)  # same as remove
```

**State constraints:**
- State is JSON-serialized — no functions, `undefined`, or circular references
- State is scoped to the partition key group — different partition keys cannot share state
- State survives job restarts (persisted at checkpoints)
- Always check for null/None before using a state value

---

## SCRIPT_MAP

Transforms one event. Returns the transformed event object, `null` to drop the event, or an array to expand one event into multiple.

### JavaScript skeleton

```js
exports.step = function(payload, context) {
    try {
        // Validate required fields
        if (!payload.accountNumber) {
            throw new Error('Missing required field: accountNumber');
        }

        // Your transformation logic
        const result = {
            accountNumber: payload.accountNumber,
            quantity: parseFloat(payload.rawQuantity) || 0,
            // ... other mapped fields
        };

        return result;
    } catch (error) {
        console.error('SCRIPT_MAP error:', error.message);
        throw error;
    }
}
```

### State-based enrichment example (JavaScript)

```js
exports.step = function(payload, context) {
    const key = 'customer_' + payload.customerId;
    let profile = context.state.get(key) || { totalOrders: 0, totalAmount: 0, tier: 'BRONZE' };

    profile.totalOrders += 1;
    profile.totalAmount += payload.amount;
    profile.tier = profile.totalAmount > 10000 ? 'GOLD'
                 : profile.totalAmount > 5000  ? 'SILVER'
                 : 'BRONZE';

    context.state.set(key, profile);

    payload.customerTier = profile.tier;
    payload.customerTotalOrders = profile.totalOrders;
    return payload;
}
```

---

## SCRIPT_AGGREGATOR

Aggregates multiple events over a time window. The framework calls `step` for every incoming event; use `context.state` to accumulate. The framework emits a final result when the time window closes — the last return value from `step` becomes the output for that window.

### JavaScript skeleton

```js
exports.step = function(payload, context) {
    try {
        const aggKey = 'agg_' + payload.windowKey;
        let agg = context.state.get(aggKey) || { count: 0, total: 0 };

        agg.count += 1;
        agg.total += parseFloat(payload.quantity) || 0;

        context.state.set(aggKey, agg);

        return {
            accountNumber: payload.accountNumber,
            totalQuantity: agg.total,
            eventCount: agg.count,
            processedAt: new Date().toISOString()
        };
    } catch (error) {
        console.error('SCRIPT_AGGREGATOR error:', error.message);
        throw error;
    }
}
```

---

## SCRIPT_ACCUMULATOR

Accumulates events per partition key and releases (emits output) when a custom trigger condition is met. The framework passes events in batches; return `null` to keep accumulating, or a result object to release and clear state.

### JavaScript skeleton

```js
exports.step = function(events, context) {
    if (!events || !events.length) return null;

    const key = context.groupKey || events[0].accountNumber || 'default';
    const stateKey = 'acc_' + key;
    let acc = context.state.get(stateKey) || { count: 0, total: 0, createdAtMs: Date.now(), events: [] };

    for (const event of events) {
        acc.count += 1;
        acc.total += parseFloat(event.quantity) || 0;
        acc.events.push(event);
    }

    // Release conditions
    const shouldRelease = acc.count >= 100
        || acc.total >= 10000
        || (Date.now() - acc.createdAtMs) > 300000; // 5 minutes

    if (!shouldRelease) {
        context.state.set(stateKey, acc);
        return null;
    }

    context.state.remove(stateKey);
    return {
        key: key,
        eventCount: acc.count,
        totalQuantity: acc.total,
        events: acc.events,
        releasedAt: new Date().toISOString()
    };
}
```

---

## Code Generation Guidelines

When generating source code for a SCRIPT_* operator:

1. **Start from the user's business logic description.** Map their input fields and output fields to the function parameters and return value.
2. **Always include error handling.** Wrap logic in try/catch (JS) or try/except (Python). Validate required input fields at the top.
3. **Use descriptive state keys.** Prefer `'agg_' + accountNumber` over `'k1'`.
4. **Clean up state when done.** Call `context.state.remove(key)` in SCRIPT_ACCUMULATOR when releasing.
5. **Use safe defaults.** `parseFloat(x) || 0`, `payload.field || ''`, `context.state.get(k) || { default }`.
6. **Do not store functions, `undefined`, or circular references in state** — they cannot be serialized.
7. **In SCRIPT_MAP**, returning `null` drops the event; returning an array expands it into multiple events.
8. **In SCRIPT_AGGREGATOR**, the last return value before window close is emitted — keep it up to date on every call.

---

## Python equivalents

Python uses the same patterns with `dict.get()` for safe access:

```python
def step(payload, context):
    try:
        if 'account_number' not in payload:
            raise ValueError('Missing required field: account_number')

        key = 'agg_' + payload['account_number']
        agg = context.state.get(key) or {'count': 0, 'total': 0}

        agg['count'] += 1
        agg['total'] += float(payload.get('quantity', 0))
        context.state.set(key, agg)

        return {
            'accountNumber': payload['account_number'],
            'totalQuantity': agg['total'],
            'eventCount': agg['count']
        }
    except Exception as e:
        print(f'SCRIPT error: {e}')
        raise
```
