---
name: zuora-order-migration-plan
description: Analyze customer code and produce Order API migration plan with field-accurate mappings
argument-hint: [customer code file paths or migration requirements]
allowed-tools: [Read, Write, Glob, Grep, Bash, Agent, mcp__zuora-mcp__ask_zuora, mcp__zuora-mcp__query_objects, mcp__zuora-mcp__zuora_codegen, mcp__zuora-mcp__get_account_summary]
---

You are analyzing customer integration code and producing an Order API migration plan. This migration moves subscription management from legacy Subscription/Amendment API and Subscribe Action API to the Order API, which provides a unified, action-based model.

## Input

The user's migration context: $ARGUMENTS

This could be:
- Customer source code file paths
- Code snippets pasted directly
- Description of their current integration approach
- Tenant context for data-driven analysis

## Workflow

### Step 1: Analyze Customer Code

If the user provides source code:

**1.1 Read the provided code**
- Use Read tool for file paths
- Accept code snippets directly

**1.2 Identify programming language**
- Python, Java, JavaScript/Node.js, Ruby, C#, PHP, etc.

**1.3 Detect Subscription/Amendment/Subscribe API patterns**

Look for these endpoint patterns:

**Python indicators:**
```python
# Subscription API
requests.post("*/v1/subscriptions")
requests.put("*/v1/subscriptions/*")
requests.put("*/v1/subscriptions/*/cancel")
requests.put("*/v1/subscriptions/*/suspend")
requests.put("*/v1/subscriptions/*/resume")
requests.put("*/v1/subscriptions/*/renew")
requests.post("*/v1/amendments")

# Subscribe Action API
requests.post("*/v1/action/subscribe")
```

**Java indicators:**
```java
HttpPost("/v1/subscriptions")
HttpPut("/v1/subscriptions/")
new URI("*/v1/amendments")
HttpPost("/v1/action/subscribe")  // Subscribe Action API
```

**JavaScript/Node.js indicators:**
```javascript
fetch('*/v1/subscriptions', {method: 'POST'})
fetch('*/v1/subscriptions/*', {method: 'PUT'})
axios.post('*/v1/subscriptions')
fetch('*/v1/action/subscribe', {method: 'POST'})  // Subscribe Action API
axios.post('*/v1/action/subscribe')               // Subscribe Action API
```

**1.4 Catalog each API call**
- File name and line number
- API endpoint and HTTP method
- Request payload structure
- Response handling code
- For Subscribe API: Detect if creating new account or using existing account

**Output:** Table of detected API calls with context

### Step 2: Map to Order API Equivalents

For each detected S/A API call, reference the verified mapping documents in `../references/`:

**Available Reference Mappings:**

1. **Subscription Cancel** → Read `${CLAUDE_PLUGIN_ROOT}/references/amendment-rest-v1-cancel-api-mapping.md`
   - Maps `PUT /v1/subscriptions/{key}/cancel` to Order API `CancelSubscription` action
   - Verified against: `POSTSubscriptionCancellationMeta`, `PostOrderActionCancelMeta`

2. **Subscription Suspend** → Read `${CLAUDE_PLUGIN_ROOT}/references/amendment-rest-v1-suspend-api-mapping.md`
   - Maps `PUT /v1/subscriptions/{key}/suspend` to Order API `Suspend` action
   - Handle suspend with resume date (requires two actions: Suspend + Resume)
   - Verified against: `PUTSubscriptionSuspendMeta`, `PostOrderActionSuspendMeta`

3. **Subscription Resume** → Read `${CLAUDE_PLUGIN_ROOT}/references/amendment-rest-v1-resume-api-mapping.md`
   - Maps `PUT /v1/subscriptions/{key}/resume` to Order API `Resume` action
   - Important: `extendsTerm` belongs in Resume action, not Suspend
   - Verified against: `PUTSubscriptionResumeMeta`, `PostOrderActionResumeMeta`

4. **Subscription Renew** → Read `${CLAUDE_PLUGIN_ROOT}/references/amendment-rest-v1-renew-api-mapping.md`
   - Maps `PUT /v1/subscriptions/{key}/renew` to Order API `RenewSubscription` action
   - Important: Uses subscription's existing renewal term settings
   - Verified against: `POSTSubscriptionRenewalMeta`, `PostOrderActionRenewSubscriptionMeta`

5. **Subscription Create** → Read `${CLAUDE_PLUGIN_ROOT}/references/amendment-rest-v1-create-api-mapping.md`
   - Maps `POST /v1/subscriptions` to Order API `CreateSubscription` action
   - Covers all charge models and term configurations

6. **Subscription Update** → Read `${CLAUDE_PLUGIN_ROOT}/references/amendment-rest-v1-update-api-mapping.md`
   - Maps `PUT /v1/subscriptions/{key}` to appropriate Order API actions
   - May involve multiple action types depending on the update

7. **Subscribe Action** → Read `${CLAUDE_PLUGIN_ROOT}/references/action-subscribe-api-mapping.md`
   - Maps `POST /v1/action/subscribe` to Order API `CreateSubscription` action
   - Handles both new account creation and existing account scenarios
   - Maps Account, BillToContact, SoldToContact, PaymentMethod to Order API equivalents
   - Important: Payment methods can only be created for new accounts in Order API
   - Verified against: `SubscribeMeta`, `PostOrderActionCreateSubscriptionMeta`

**Output:** Mapping table showing each API call and its Order API equivalent

### Step 3: Assess Tenant Context (if applicable)

If tenant is connected and user wants data-driven analysis:

**3.1 Query current state**
- Call `mcp__zuora-mcp__query_objects` to inspect:
  - Subscription count, statuses, and term types
  - Amendment history and patterns
  - Rate plans and charge models in use
  - Custom fields on subscriptions and amendments

**3.2 Sample representative accounts**
- Use `mcp__zuora-mcp__get_account_summary` for typical accounts
- Understand subscription structures in production

**3.3 Call Zuora knowledge base**
- Use `mcp__zuora-mcp__ask_zuora` for Order API capabilities and best practices

**Output:** Current state summary with statistics

### Step 4: Identify Edge Cases and Risks

Based on code analysis and tenant data:

**Common edge cases:**
- Mid-term amendments (changes mid-billing-period)
- Future-dated amendments
- Charge-level overrides (price, quantity, billing period)
- Multi-product subscriptions
- Custom field usage on subscription and amendment objects
- Integration points that reference subscription or amendment IDs
- Suspend with resume date (requires two Order API actions)
- Error handling differences between APIs
- Subscribe API with new account vs existing account detection
- Payment method creation limitations (Order API only supports for new accounts)
- Credit card field name changes (creditCardNumber → cardNumber)
- Account and contact creation in Subscribe API → newAccount in Order API

**Risk assessment:**
- Breaking changes in response structure
- New required fields in Order API
- Processing option changes (`invoice`/`collect` → `processingOptions.runBilling`/`collect`)
- Contract effective date → trigger dates transformation
- Testing scope and sandbox requirements

**Output:** Edge case list and risk matrix (likelihood, impact, mitigation)

### Step 5: Generate Migration Plan Document

Produce a comprehensive migration plan:

```markdown
# Order API Migration Plan

**Generated:** {timestamp}
**Customer Code Analyzed:** {file_count} files, {line_count} lines
**Programming Language:** {language}

## Executive Summary

- **Total S/A API Calls Detected:** {count}
- **Operations:** {operation types: create, cancel, suspend, resume, renew, update, amendments}
- **Complexity:** {Low/Medium/High}
- **Estimated Effort:** {hours/days based on operation count and complexity}

### Why Migrate to Order API

- **Atomic operations**: Multiple subscription changes in one transaction
- **Future-dating**: Schedule changes in advance with precise control
- **Unified model**: Consistent action-based structure for all operations
- **Better error handling**: Transaction-level rollback
- **Enhanced flexibility**: Support for complex subscription scenarios

## Current State Assessment

### Detected API Calls

| File | Line | Current API | HTTP Method | Order API Equivalent |
|------|------|-------------|-------------|---------------------|
| customer_code.py | 45 | /v1/subscriptions/{key}/cancel | PUT | POST /v1/orders (CancelSubscription) |
| ... | ... | ... | ... | ... |

### Tenant Statistics (if available)

- Subscription count: {count}
- Active subscriptions: {count}
- Common charge models: {flat fee, per unit, tiered, etc.}
- Custom fields in use: {list}

## Field Mappings by Operation

[For each detected operation, include detailed field mapping from the reference documents]

### Example: Subscription Cancel Mapping

**Current Code (Subscription API):**
```python
# Line 45-52 in customer_code.py
response = requests.put(
    f"https://rest.zuora.com/v1/subscriptions/{subscription_key}/cancel",
    json={
        "cancellationPolicy": "SpecificDate",
        "cancellationEffectiveDate": cancel_date
    }
)
```

**Order API Equivalent:**
- Endpoint: `POST /v1/orders`
- Action type: `CancelSubscription`
- New required fields: `orderDate`, `existingAccountNumber`
- Field transformations:
  - `cancellationEffectiveDate` → both `triggerDates.triggerDate` and `cancelSubscription.cancellationEffectiveDate`
  - `invoiceCollect` → `processingOptions.runBilling` and `processingOptions.collect`

[Repeat for each operation]

## Migration Phases

### Phase 1: Code Migration
- Rewrite subscription management code to use Order API
- Update request/response handling
- Add new required fields
- Transform field names and structures

### Phase 2: Sandbox Validation
- Deploy to sandbox environment
- Test all operations with sample data
- Verify subscription state changes
- Check billing/invoice generation

### Phase 3: Integration Updates
- Update downstream systems for Order API responses
- Handle new field names (`orderNumber` vs `subscriptionId`)
- Update error handling for new error formats

### Phase 4: Parallel Run (if feasible)
- Run both APIs side-by-side during transition
- Compare results for validation
- Monitor for discrepancies

### Phase 5: Production Cutover
- Deploy Order API code to production
- Monitor initial transactions closely
- Have rollback plan ready

### Phase 6: Post-Migration Monitoring
- Watch billing runs for anomalies
- Monitor subscription changes
- Track error rates
- Gather customer feedback

## Edge Case Analysis

[For each identified edge case:]

**Edge Case:** Suspend with resume date

**Current Approach (S/A API):**
Single call with `resumeDate` field

**Order API Approach:**
Requires two separate actions in one order:
1. `Suspend` action
2. `Resume` action with `resumeSpecificDate`

**Migration Impact:**
Code must be refactored to create two action objects

[Repeat for each edge case]

## Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Response parsing errors | High | Medium | Update all response handling code, add unit tests |
| Missing required fields | Medium | High | Thorough code review, sandbox testing |
| Integration breakage | Medium | High | Update integrations before cutover |
| ... | ... | ... | ... |

## Key Migration Principles

### 1. Processing Options Move to Order Level
- `invoice`/`collect`/`invoiceCollect` → `processingOptions.runBilling` and `processingOptions.collect`

### 2. Subscription Number Moves to Request Body
- No longer in URL path, now in request body under `subscriptions[].subscriptionNumber`

### 3. Contract Effective Date → Trigger Dates
- `contractEffectiveDate` → `triggerDates[{name: "ContractEffective", triggerDate: "..."}]`

### 4. Action Type Must Be Explicit
- Subscription API: implicit from endpoint (cancel, suspend, renew)
- Order API: explicit `type` field in each action

## Common Gotchas

### ❌ Incorrect: Specifying Renewal Terms in Order API
Renewal terms must be pre-configured on the subscription. Order API uses existing settings.

### ✅ Correct: Order API Uses Subscription's Renewal Settings
`RenewSubscription` action relies on subscription's renewal term configuration

### ❌ Incorrect: extendsTerm in Suspend Action
`extendsTerm` belongs in Resume action, not Suspend

### ✅ Correct: extendsTerm in Resume Action
When suspending with resume date, `extendsTerm` goes in the Resume action

[Add more gotchas from reference documents]

## Validation Checklist

- [ ] All API calls identified and mapped (Subscription, Amendment, Subscribe Action)
- [ ] Field mappings verified against reference documents
- [ ] New required fields identified and sourced (orderDate, existingAccountNumber/newAccount)
- [ ] Response handling updated for new structure
- [ ] Error handling updated for new error formats
- [ ] Integration points identified and migration planned
- [ ] For Subscribe API: Identified if creating new or using existing accounts
- [ ] For Subscribe API: Payment method handling strategy defined (Order API limitation for existing accounts)
- [ ] Credit card field name changes handled (creditCardNumber → cardNumber)
- [ ] Sandbox environment prepared with test data
- [ ] Test cases written for all operations
- [ ] Rollback plan documented

## Next Steps

1. Review this migration plan with your team
2. Set up sandbox environment with Order API enabled
3. Run `/zuora-order-migration-build [file-paths]` to generate converted code
4. Execute sandbox testing
5. Update integrations
6. Plan production cutover

## Resources

- Order API reference mappings: 
  - Amendment APIs: `${CLAUDE_PLUGIN_ROOT}/references/amendment-rest-v1-*-api-mapping.md`
  - Subscribe Action API: `${CLAUDE_PLUGIN_ROOT}/references/action-subscribe-api-mapping.md`
- [Zuora Order API Documentation](https://www.zuora.com/developer/api-references/api/tag/Orders)
- [Subscription API Documentation](https://www.zuora.com/developer/api-references/api/tag/Subscriptions)
- [Subscribe Action API Documentation](https://developer.zuora.com/v1-api-reference/older-api/actions/action_postsubscribe)
```

**Output:** Complete migration plan document
