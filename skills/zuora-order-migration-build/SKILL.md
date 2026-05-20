---
name: zuora-order-migration-build
description: Generate Order API implementation code by converting customer's Subscription/Amendment/Subscribe Action API code (supports both preview and create modes)
argument-hint: [customer code file paths or migration plan reference]
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash, Agent, mcp__zuora-mcp__zuora_codegen, mcp__zuora-mcp__ask_zuora, mcp__zuora-mcp__query_objects, mcp__zuora-mcp__create_subscriptions, mcp__zuora-mcp__cancel_subscriptions, mcp__zuora-mcp__renew_subscriptions]
---

Codex-only path resolution: When an instruction refers to `${CLAUDE_PLUGIN_ROOT}`, treat it as the root of this installed plugin. In Codex, resolve that root as the ancestor directory containing `skills/`, `references/`, and `.codex-plugin/`.


You are generating Order API implementation code by converting customer integration code from Subscription/Amendment API and Subscribe Action API. The Subscribe Action API supports two distinct modes (preview vs create) which map to different Order API endpoints. The user should have a migration plan (from `/zuora-order-migration-design`) or provide their source code directly.

## Input

The user's request: $ARGUMENTS

This could be:
- Customer source code file paths
- Reference to a migration plan document
- Specific operations to convert (cancel, suspend, resume, renew, create, update)

## Tool routing

Use local file reads and edits for conversion work, bundled mapping references for known S/A-to-Order transformations, and `mcp__zuora-mcp__zuora_codegen` for exact Order API endpoint/model details. Use subscription MCP tools only for their specific create/cancel/renew operations when validation requires them. `mcp__zuora-mcp__ask_zuora` is allowed only as a fallback for a specific Order API capability or migration-tradeoff question that remains after references and codegen are checked. If business intent is ambiguous, ask the user to confirm the mapping.

## Workflow

**⚠️ CRITICAL PRINCIPLE: Always Modify Existing Files**

When converting customer integration code:
- ✅ DO: Use Edit tool to modify existing customer files in-place
- ✅ DO: Comment out old code and add converted code in the same location
- ✅ DO: Create clear BEFORE/AFTER markers in the same file
- ❌ DON'T: Create new files like `*_converted.py` or `*_order_api.py`
- ❌ DON'T: Use Write tool for existing integration files

**Why:** PR reviews need to see the diff between old and new code. New files hide the changes and make it impossible to review what actually changed.

**Exception:** New supporting files (validation scripts, checklists, documentation) can be created with Write tool since they don't replace existing code.

### Step 1: Review Context

**If migration plan exists:**
- Read the migration plan to understand:
  - Which S/A API calls were detected
  - The field mappings for each operation
  - Programming language used
  - Edge cases identified

**If no plan exists:**
- Read the customer's source code files
- Identify the programming language
- Detect API patterns (Subscription, Amendment, Subscribe Action)
- Recommend running `/zuora-order-migration-design` first for comprehensive analysis

### Step 2: Read Reference Mappings

For each operation being converted, read the corresponding reference document from `${CLAUDE_PLUGIN_ROOT}/references/`:

**Available Reference Mappings:**

1. **Subscription Cancel** → `${CLAUDE_PLUGIN_ROOT}/references/amendment-rest-v1-cancel-api-mapping.md`
2. **Subscription Suspend** → `${CLAUDE_PLUGIN_ROOT}/references/amendment-rest-v1-suspend-api-mapping.md`
3. **Subscription Resume** → `${CLAUDE_PLUGIN_ROOT}/references/amendment-rest-v1-resume-api-mapping.md`
4. **Subscription Renew** → `${CLAUDE_PLUGIN_ROOT}/references/amendment-rest-v1-renew-api-mapping.md`
5. **Subscription Create** → `${CLAUDE_PLUGIN_ROOT}/references/amendment-rest-v1-create-api-mapping.md`
6. **Subscription Update** → `${CLAUDE_PLUGIN_ROOT}/references/amendment-rest-v1-update-api-mapping.md`
7. **Subscribe Action** → `${CLAUDE_PLUGIN_ROOT}/references/action-subscribe-api-mapping.md`
   - **Note**: Subscribe API supports two modes (preview vs create) controlled by `PreviewOptions`
   - **Preview mode** (PreviewOptions present) → `/v1/orders/preview` with `previewAccountInfo`
   - **Create mode** (PreviewOptions absent) → `/v1/orders` with `newAccount` or `existingAccountNumber`
   - See "Subscribe API: Preview vs Create Mode Detection" in Step 4 for complete handling

These documents provide field-accurate mappings verified against Zuora Billing source code.

### Step 3: Generate Converted Code

For each API call in the customer's code (Subscription, Amendment, or Subscribe Action), generate the Order API equivalent following these guidelines:

#### Code Generation Guidelines

**CRITICAL: Always Modify Existing Files, Never Create New Files**

**Why:** When converting integration code, changes must be visible in PR diffs. Creating new files makes it impossible to see what changed from the original code. Always use the Edit tool to modify existing customer files directly.

**How:**
1. Read the existing customer file first
2. Locate the exact S/A API code to convert
3. Use Edit tool to replace the old code with converted code in-place
4. Keep commented BEFORE/AFTER blocks to show the transformation
5. Preserve all surrounding code unchanged

**1. Preserve Structure**
- Keep similar code organization and flow
- Maintain the same variable names where possible
- Preserve error handling patterns
- Keep the same file and function names

**2. Match Coding Style**
- Use same indentation (spaces vs tabs)
- Follow same naming conventions
- Maintain consistent formatting
- Match the customer's code style exactly

**3. Add Explanatory Comments**
- Mark the original S/A API code with "BEFORE" comment (keep original as comment)
- Mark the new Order API code with "AFTER" comment
- Explain what changed and why
- Reference the field mapping source
- This creates clear before/after comparison in PR diff

**4. Include TODO Markers**
- Mark areas requiring customer input (account numbers, dates, etc.)
- Highlight new required fields that don't have obvious sources
- Flag response handling changes that need attention

**5. Update Response Handling**
- Show old response structure vs new (as comments)
- Update field extraction code
- Handle new response fields (`orderNumber`, nested structures)

**6. Add Error Handling**
- Include Order API specific error handling
- Handle validation errors from new required fields
- Add transaction-level error handling

#### Output Format - Modify Existing Files In-Place

**Step-by-step process:**

1. **Read the existing customer file:**
   ```
   Read(file_path="customer_code.py")
   ```

2. **Identify the exact code block to convert** (e.g., lines 45-52)

3. **Use Edit tool to replace the old code with converted code:**
   ```
   Edit(
       file_path="customer_code.py",
       old_string="<exact original code>",
       new_string="<converted code with comments>"
   )
   ```

**Example of converted code structure in the file:**

```python
# ============================================================================
# BEFORE - Subscription Cancel API (Original code below, kept for reference)
# ============================================================================
# response = requests.put(
#     f"https://rest.zuora.com/v1/subscriptions/{subscription_key}/cancel",
#     json={
#         "cancellationPolicy": "SpecificDate",
#         "cancellationEffectiveDate": cancel_date,
#         "invoiceCollect": True
#     },
#     headers=headers
# )
# subscription_id = response.json()['subscriptionId']

# ============================================================================
# AFTER - Order API Equivalent
# Converted using: ${CLAUDE_PLUGIN_ROOT}/references/amendment-rest-v1-cancel-api-mapping.md
# ============================================================================

# TODO: Add account_number variable
# You can get this from:
# - Subscription lookup before cancellation
# - Configuration/settings
# - Database query
account_number = "A00000001"  # TODO: Replace with actual account number

# TODO: Set orderDate (typically today or the effective date)
order_date = datetime.today().strftime('%Y-%m-%d')  # or use cancel_date

response = requests.post(
    "https://rest.zuora.com/v1/orders",
    json={
        "orderDate": order_date,  # New required field
        "existingAccountNumber": account_number,  # New required field
        "processingOptions": {
            "runBilling": True,  # Replaces invoiceCollect
            "collect": True      # Replaces invoiceCollect
        },
        "subscriptions": [{
            "subscriptionNumber": subscription_key,
            "orderActions": [{
                "type": "CancelSubscription",  # Explicit action type
                "triggerDates": [{
                    "name": "ContractEffective",
                    "triggerDate": cancel_date  # Same date as before
                }],
                "cancelSubscription": {
                    "cancellationPolicy": "SpecificDate",  # Same value
                    "cancellationEffectiveDate": cancel_date  # Same value
                }
            }]
        }]
    },
    headers=headers
)

# ============================================================================
# RESPONSE HANDLING CHANGES
# Old response: {"subscriptionId": "2c92...", "success": true}
# New response: {"orderNumber": "O-00000123", "subscriptions": [...], "success": true}
# ============================================================================
order_number = response.json()['orderNumber']  # New field
subscription_id = response.json()['subscriptions'][0]['subscriptionId']  # New nested path
```

**Key principles for in-place editing:**

- Comment out the original S/A API code (don't delete it)
- Add the converted Order API code below with clear BEFORE/AFTER markers
- All changes should be in the same file at the same location
- The PR diff will clearly show: old code commented out, new code added
- Never create separate new files like `customer_code_converted.py`

### Step 4: Handle Special Cases

#### Subscribe API: Preview vs Create Mode Detection

Subscribe Action API supports two distinct modes controlled by the `PreviewOptions` parameter. These must be detected and routed to different Order API endpoints:

**Detection Logic:**
```python
# Check if PreviewOptions exists and is not empty
has_preview_options = 'PreviewOptions' in subscribe_request and subscribe_request['PreviewOptions']

if has_preview_options:
    # Route to PREVIEW MODE
else:
    # Route to CREATE MODE
```

**Preview Mode (PreviewOptions present):**

When the Subscribe API includes `PreviewOptions`, it returns preview results **without creating** any records. This maps to the Order Preview API.

```python
# BEFORE - Subscribe API with PreviewOptions
requests.post("/v1/action/subscribe", json={
    "Account": {
        "name": "Example Corp",
        "currency": "USD",
        "billCycleDay": 1,
        "billToContact": {...}
    },
    "PreviewOptions": {
        "enablePreviewMode": True,
        "numberOfPeriods": 3
    },
    "SubscriptionData": {
        "Subscription": {
            "termType": "TERMED",
            "contractEffectiveDate": "2026-05-01",
            "initialTerm": 12
        },
        "RatePlanData": [{
            "RatePlan": {"productRatePlanId": "2c92..."}
        }]
    }
})

# AFTER - Order Preview API
requests.post("/v1/orders/preview", json={  # Different endpoint!
    "orderDate": "2026-05-01",
    "previewAccountInfo": {  # Changed from newAccount
        "name": "Example Corp",
        "currency": "USD",
        "billCycleDay": 1,
        "billToContact": {...}
    },
    "previewOptions": {  # Required for preview mode
        "previewTypes": ["BillingDocs", "ChargeMetrics"],  # Required! Subscribe API only supports these two
        "previewNumberOfPeriods": 3  # Converted from PreviewOptions.numberOfPeriods
    },
    # NO processingOptions in preview mode!
    "subscriptions": [{
        "orderActions": [{
            "type": "CreateSubscription",
            "triggerDates": [{
                "name": "ContractEffective",
                "triggerDate": "2026-05-01"
            }],
            "createSubscription": {
                "terms": {...},
                "subscribeToRatePlans": [{...}]
            }
        }]
    }]
})
```

**Key differences for Preview Mode:**
- **Endpoint**: Use `/v1/orders/preview` (NOT `/v1/orders`)
- **New Account Field**: Use `previewAccountInfo` (NOT `newAccount`)
- **Existing Account Field**: Still use `existingAccountNumber` (same as create mode)
- **Required Field**: Must include `previewOptions` with `previewTypes: ["BillingDocs", "ChargeMetrics"]` (Subscribe API only supports these two types)
- **Skip**: Do NOT include `processingOptions` (not applicable in preview)
- **Response**: Returns preview data (billing docs, metrics) instead of actual IDs

**Create Mode (PreviewOptions absent or empty):**

When `PreviewOptions` is NOT provided, the Subscribe API creates actual records. This maps to the Order Create API.

```python
# BEFORE - Subscribe API without PreviewOptions
requests.post("/v1/action/subscribe", json={
    "Account": {
        "name": "Example Corp",
        "currency": "USD",
        "billToContact": {...}
    },
    "SubscribeOptions": {
        "generateInvoice": True,
        "processPayments": True
    },
    "SubscriptionData": {
        "Subscription": {
            "termType": "TERMED",
            "contractEffectiveDate": "2026-04-20",
            "initialTerm": 12
        },
        "RatePlanData": [{...}]
    }
})

# AFTER - Order Create API
requests.post("/v1/orders", json={  # Standard endpoint
    "orderDate": "2026-04-20",
    "newAccount": {  # Use newAccount for new accounts
        "name": "Example Corp",
        "currency": "USD",
        "billToContact": {...}
    },
    "processingOptions": {  # Include billing/payment options
        "runBilling": True,  # From SubscribeOptions.generateInvoice
        "collect": True      # From SubscribeOptions.processPayments
    },
    "subscriptions": [{
        "orderActions": [{
            "type": "CreateSubscription",
            "triggerDates": [{
                "name": "ContractEffective",
                "triggerDate": "2026-04-20"
            }],
            "createSubscription": {
                "terms": {...},
                "subscribeToRatePlans": [{...}]
            }
        }]
    }]
})
```

**Key differences for Create Mode:**
- **Endpoint**: Use `/v1/orders`
- **New Account Field**: Use `newAccount`
- **Existing Account Field**: Use `existingAccountNumber`
- **Include**: Add `processingOptions` for billing/payment control
- **Response**: Returns actual `orderNumber`, `subscriptionId`, `invoiceId`, etc.

**Complete conversion example with mode detection:**

```python
# ============================================================================
# BEFORE - Subscribe Action API (mode depends on PreviewOptions)
# ============================================================================
# subscribe_request = {
#     "Account": {"name": "Example Corp", "currency": "USD", ...},
#     "PreviewOptions": {"enablePreviewMode": True, "numberOfPeriods": 3},  # or absent
#     "SubscribeOptions": {"generateInvoice": True, "processPayments": True},
#     "SubscriptionData": {...}
# }
# response = requests.post("/v1/action/subscribe", json=subscribe_request, headers=headers)

# ============================================================================
# AFTER - Order API with mode detection
# ============================================================================

# Detect mode based on PreviewOptions presence
has_preview = 'PreviewOptions' in subscribe_request and subscribe_request['PreviewOptions']

if has_preview:
    # PREVIEW MODE - Use Order Preview API
    endpoint = f"{base_url}/v1/orders/preview"
    
    order_request = {
        "orderDate": subscribe_request['SubscriptionData']['Subscription']['contractEffectiveDate'],
        "previewOptions": {  # Required for preview
            "previewTypes": ["BillingDocs", "ChargeMetrics"],  # Subscribe API only supports these two
            "previewNumberOfPeriods": subscribe_request['PreviewOptions'].get('numberOfPeriods', 1)
        }
    }
    
    # Handle account info
    if 'accountKey' in subscribe_request['Account']:
        # Existing account - same as create mode
        order_request['existingAccountNumber'] = subscribe_request['Account']['accountKey']
    else:
        # New account - use previewAccountInfo
        order_request['previewAccountInfo'] = {
            "name": subscribe_request['Account']['name'],
            "currency": subscribe_request['Account']['currency'],
            "billCycleDay": subscribe_request['Account'].get('billCycleDay', 0),
            "billToContact": subscribe_request['Account'].get('billToContact')
        }
    
    # NO processingOptions in preview mode
    
else:
    # CREATE MODE - Use Order Create API
    endpoint = f"{base_url}/v1/orders"
    
    order_request = {
        "orderDate": subscribe_request['SubscriptionData']['Subscription']['contractEffectiveDate'],
        "processingOptions": {
            "runBilling": subscribe_request['SubscribeOptions'].get('generateInvoice', False),
            "collect": subscribe_request['SubscribeOptions'].get('processPayments', False)
        }
    }
    
    # Handle account info
    if 'accountKey' in subscribe_request['Account']:
        # Existing account
        order_request['existingAccountNumber'] = subscribe_request['Account']['accountKey']
    else:
        # New account - use newAccount
        order_request['newAccount'] = {
            "name": subscribe_request['Account']['name'],
            "currency": subscribe_request['Account']['currency'],
            "billCycleDay": subscribe_request['Account'].get('billCycleDay', 0),
            "billToContact": subscribe_request['Account'].get('billToContact'),
            "paymentMethod": subscribe_request['Account'].get('paymentMethod')  # If provided
        }

# Common subscription structure for both modes
order_request['subscriptions'] = [{
    "orderActions": [{
        "type": "CreateSubscription",
        "triggerDates": [{
            "name": "ContractEffective",
            "triggerDate": subscribe_request['SubscriptionData']['Subscription']['contractEffectiveDate']
        }],
        "createSubscription": {
            "terms": {
                # Convert term configuration (same for both modes)
                "initialTerm": {
                    "period": subscribe_request['SubscriptionData']['Subscription']['initialTerm'],
                    "periodType": "Month",
                    "termType": subscribe_request['SubscriptionData']['Subscription']['termType']
                },
                "autoRenew": subscribe_request['SubscriptionData']['Subscription'].get('autoRenew', False)
            },
            "subscribeToRatePlans": [
                # Convert rate plans (same for both modes)
            ]
        }
    }]
}]

# Execute the request
response = requests.post(endpoint, json=order_request, headers=headers)

# Handle response (different structure for preview vs create)
if has_preview:
    # Preview response contains billing docs, metrics, etc.
    preview_invoices = response.json().get('invoices', [])
    preview_metrics = response.json().get('orderMetrics', {})
else:
    # Create response contains actual IDs
    order_number = response.json()['orderNumber']
    subscription_id = response.json()['subscriptions'][0]['subscriptionId']
```

**Important Notes:**

1. **Always detect mode first** before building the request
2. **Preview mode requires** `previewOptions.previewTypes` array - Subscribe API only supports `["BillingDocs", "ChargeMetrics"]` (do NOT include OrderMetrics or other types)
3. **Preview mode uses** `previewAccountInfo` for new accounts (NOT `newAccount`)
4. **Create mode requires** `processingOptions` for billing control
5. **Credit card field names** are different: `creditCardNumber` → `cardNumber`, `creditCardType` → `cardType`
6. **Response structures** are different between preview and create modes

**Reference:** See `${CLAUDE_PLUGIN_ROOT}/references/action-subscribe-api-mapping.md` for complete field mappings, especially:
- **Scenario 1 & 2**: Create mode mappings
- **Scenario 3**: Preview mode mappings
- **Pattern 0**: Mode detection logic

#### Suspend with Resume Date

This requires TWO separate actions in Order API:

```python
# BEFORE - S/A API: Single call with resumeDate
requests.put(f"/v1/subscriptions/{key}/suspend", json={
    "suspendPolicy": "SpecificDate",
    "suspendDate": "2026-04-01",
    "resumeDate": "2026-05-01"
})

# AFTER - Order API: Two separate actions
{
    "orderActions": [
        {
            "type": "Suspend",
            "triggerDates": [{
                "name": "ContractEffective",
                "triggerDate": "2026-04-01"
            }],
            "suspend": {
                "suspendPolicy": "SpecificDate",
                "suspendDate": "2026-04-01"
            }
        },
        {
            "type": "Resume",
            "resume": {
                "resumePolicy": "SpecificDate",
                "resumeSpecificDate": "2026-05-01",
                "extendsTerm": True  # Note: extendsTerm goes here, not in Suspend
            }
        }
    ]
}
```

#### Multiple Operations in One Order

Order API allows batching multiple operations:

```python
# Combine multiple S/A API calls into one Order API call
{
    "subscriptions": [
        {
            "subscriptionNumber": "A-S00000001",
            "orderActions": [
                {"type": "UpdateProduct", ...},
                {"type": "AddProduct", ...}
            ]
        },
        {
            "subscriptionNumber": "A-S00000002",
            "orderActions": [
                {"type": "CancelSubscription", ...}
            ]
        }
    ]
}
```

#### Subscribe API: New Account vs Existing Account

Subscribe API can create a new account or use an existing one. This must be detected and handled differently:

```python
# BEFORE - Subscribe API with NEW account
requests.post("/v1/action/subscribe", json={
    "Account": {
        "name": "New Customer",
        "currency": "USD",
        "billToContact": {...},
        "paymentMethod": {
            "type": "CreditCard",
            "creditCardNumber": "4111111111111111",
            "creditCardType": "Visa"
        }
    },
    "SubscriptionData": {...}
})

# AFTER - Order API with NEW account
requests.post("/v1/orders", json={
    "orderDate": "2026-04-20",
    "newAccount": {
        "name": "New Customer",
        "currency": "USD",
        "billToContact": {...},
        "paymentMethod": {
            "cardNumber": "4111111111111111",  # Field name changed
            "cardType": "Visa"                 # Field name changed
        }
    },
    "subscriptions": [{
        "orderActions": [{
            "type": "CreateSubscription",
            "createSubscription": {...}
        }]
    }]
})

# BEFORE - Subscribe API with EXISTING account
requests.post("/v1/action/subscribe", json={
    "Account": {
        "accountKey": "A00000001"  # Using existing account
    },
    "SubscriptionData": {...}
})

# AFTER - Order API with EXISTING account
requests.post("/v1/orders", json={
    "orderDate": "2026-04-20",
    "existingAccountNumber": "A00000001",  # Changed from Account.accountKey
    "subscriptions": [{
        "orderActions": [{
            "type": "CreateSubscription",
            "createSubscription": {...}
        }]
    }]
})
```

**Important:** Order API cannot create payment methods for existing accounts. If the Subscribe API includes a payment method for an existing account, you must:
1. Note this in a TODO comment
2. Suggest using the Payment Methods API separately
3. Or use an existing payment method on the account

#### Subscribe API: Term Configuration

Subscribe API uses simple fields for terms, Order API uses structured objects:

```python
# BEFORE - Subscribe API with TERMED subscription
{
    "Subscription": {
        "termType": "TERMED",
        "initialTerm": 12,
        "renewalTerm": 12,
        "autoRenew": True
    }
}

# AFTER - Order API with TERMED subscription
{
    "createSubscription": {
        "terms": {
            "initialTerm": {
                "period": 12,
                "periodType": "Month",
                "termType": "TERMED"
            },
            "autoRenew": True,
            "renewalSetting": "RENEW_WITH_SPECIFIC_TERM",
            "renewalTerms": [{
                "period": 12,
                "periodType": "Month"
            }]
        }
    }
}

# BEFORE - Subscribe API with EVERGREEN subscription
{
    "Subscription": {
        "termType": "EVERGREEN"
    }
}

# AFTER - Order API with EVERGREEN subscription
{
    "createSubscription": {
        "terms": {
            "initialTerm": {
                "termType": "EVERGREEN"
            },
            "autoRenew": False
        }
    }
}
```

### Step 5: Generate Supporting Artifacts

**Note:** Supporting artifacts (validation scripts, checklists) are NEW files and can be created with Write tool. Only the actual customer integration code must be modified in-place with Edit tool.

#### Validation Script

Generate a script to validate the migration in sandbox:

```python
#!/usr/bin/env python3
"""
Order API Migration Validation Script
Tests converted code against sandbox environment
"""

import requests
from datetime import datetime

# Configuration
ZUORA_BASE_URL = "https://rest.sandbox.zuora.com"
# TODO: Add authentication credentials

def test_subscription_cancel():
    """Test subscription cancellation with Order API"""
    # TODO: Get test subscription number from sandbox
    test_subscription = "A-S00000001"
    
    # TODO: Implement test
    print("Testing subscription cancel...")
    # [Generated test code based on customer's cancel operation]
    
def test_subscription_suspend():
    """Test subscription suspension with Order API"""
    # TODO: Implement test
    pass

def compare_results(s_a_result, order_result):
    """Compare S/A API result with Order API result"""
    # Check if subscription ended up in same state
    # Compare billing outcomes
    # Validate field values
    pass

if __name__ == "__main__":
    test_subscription_cancel()
    test_subscription_suspend()
    # Add more tests based on detected operations
```

#### Migration Checklist

Generate a checklist document:

```markdown
# Order API Migration Implementation Checklist

## Pre-Migration

- [ ] Review migration plan from `/zuora-order-migration-design`
- [ ] Sandbox environment has Order API enabled
- [ ] Test accounts and subscriptions created in sandbox
- [ ] Authentication credentials configured for sandbox

## Code Changes

### Subscription Cancel Operation (customer_code.py:45-52)

- [ ] Added `orderDate` field
- [ ] Added `existingAccountNumber` field (TODO: source account number)
- [ ] Converted `invoiceCollect` to `processingOptions`
- [ ] Moved subscription key from URL to request body
- [ ] Added `type: "CancelSubscription"` field
- [ ] Converted `cancellationEffectiveDate` to `triggerDates`
- [ ] Updated response handling code
- [ ] Added error handling for Order API errors

### Subscribe Action API Operation (customer_code.py:XX-YY)

**Mode Detection:**
- [ ] Detected if PreviewOptions present in original code
- [ ] Routed to correct Order API endpoint based on mode

**If Preview Mode (PreviewOptions present):**
- [ ] Changed endpoint to `/v1/orders/preview`
- [ ] Changed `newAccount` to `previewAccountInfo` (for new accounts)
- [ ] Added required `previewOptions.previewTypes` array
- [ ] Removed `processingOptions` (not applicable in preview)
- [ ] Converted `PreviewOptions.numberOfPeriods` to `previewOptions.previewNumberOfPeriods`
- [ ] Updated response handling for preview structure (billing docs, metrics)

**If Create Mode (PreviewOptions absent):**
- [ ] Used endpoint `/v1/orders`
- [ ] Used `newAccount` or `existingAccountNumber` based on Account.accountKey presence
- [ ] Converted `SubscribeOptions` to `processingOptions`
- [ ] Updated credit card field names (creditCardNumber → cardNumber, creditCardType → cardType)
- [ ] Updated response handling for create structure (orderNumber, subscriptionId)

**Common to Both Modes:**
- [ ] Added `orderDate` field
- [ ] Converted term configuration to structured format (initialTerm, renewalTerms)
- [ ] Added `renewalSetting` when autoRenew is true
- [ ] Converted `contractEffectiveDate` to `triggerDates`
- [ ] Converted `RatePlanData` to `subscribeToRatePlans`
- [ ] Noted payment method limitation for existing accounts (if applicable)

[Repeat for each operation]

## Testing

- [ ] Unit tests pass locally
- [ ] Sandbox test for cancel operation
- [ ] Sandbox test for suspend operation
- [ ] Sandbox test for resume operation
- [ ] Sandbox test for renew operation
- [ ] Sandbox test for Subscribe Action API (create mode) - verify actual subscription created
- [ ] Sandbox test for Subscribe Action API (preview mode) - verify no records created, preview data returned
- [ ] Verify subscription states in Zuora UI
- [ ] Verify billing/invoices generated correctly
- [ ] Test error scenarios

## Integration Updates

- [ ] Updated downstream systems for new response structure
- [ ] Updated logging/monitoring for orderNumber
- [ ] Updated webhooks/callbacks if needed

## Production Readiness

- [ ] Code review completed
- [ ] All tests passing
- [ ] Rollback plan documented
- [ ] Production deployment scheduled
```

### Step 6: Use Zuora Codegen (Optional)

If using `mcp__zuora-mcp__zuora_codegen` for additional guidance:

1. Call `code_guidance` with "Order API migration"
2. Call `get_api_details` for Order API endpoints
3. Call `get_model_details` for Order request/response models
4. Call `code_rules` for validation rules

### Step 7: Provide Testing Guidance

**Unit Testing:**
```python
def test_order_api_cancel_request():
    """Test Order API cancel request structure"""
    request = build_cancel_order_request(
        subscription_key="A-S00000123",
        account_number="A00000001",
        cancel_date="2026-09-01"
    )
    
    assert request['orderDate'] is not None
    assert request['existingAccountNumber'] == "A00000001"
    assert len(request['subscriptions']) == 1
    assert request['subscriptions'][0]['orderActions'][0]['type'] == "CancelSubscription"
```

**Integration Testing in Sandbox:**

1. Create test subscription in sandbox
2. Execute converted code against sandbox
3. Verify subscription state changed correctly
4. Check billing/invoice generation
5. Compare with expected S/A API behavior

### Step 8: Document Key Changes

Summarize what changed (emphasizing in-place modifications):

```markdown
## Summary of Changes

### File: customer_code.py (Modified in-place)

**Lines 45-65: Subscription Cancel (Original code commented out, converted code added)**
- Changed endpoint: PUT /v1/subscriptions/{key}/cancel → POST /v1/orders
- Added required fields: orderDate, existingAccountNumber
- Converted invoiceCollect → processingOptions.runBilling + processingOptions.collect
- Moved subscription key from URL to request body
- Updated response handling: subscriptionId path changed
- **PR diff will show:** Old code commented out (lines with #), new Order API code added

**Lines 120-145: Subscription Suspend (Original code commented out, converted code added)**
- Changed endpoint: PUT /v1/subscriptions/{key}/suspend → POST /v1/orders
- Added suspend with resume date handling (two separate actions)
- Added extendsTerm field in Resume action (not Suspend)
- Updated response handling
- **PR diff will show:** Clear before/after comparison in the same file

[Continue for each file and operation]

## New Dependencies

- None (using same HTTP client library)

## Configuration Changes

- Need to source account numbers (not in S/A API calls)
- Need to set orderDate for each request

## Breaking Changes

- Response structure changed
- Error response format changed
- Field names changed (invoiceCollect → processingOptions)

## Testing Requirements

- Sandbox testing required before production
- All operations must be tested
- Edge cases must be validated
```

### Step 9: Suggest Next Steps

After generating code:

1. **Verify all modifications were done in-place** (no new `*_converted` files created)
2. Review PR diff to confirm before/after is clearly visible
3. Review all converted code with customer
4. Address all TODO items (account numbers, dates, etc.)
5. Run validation script in sandbox
6. Update integration points
7. Run `/zuora-validate` on modified code
8. Plan production deployment

**Final Checklist:**
- [ ] All customer integration files modified with Edit tool (not Write tool)
- [ ] Original API code preserved as comments (BEFORE section)
- [ ] Converted Order API code added with clear markers (AFTER section)
- [ ] No new `*_converted.py` or `*_order_api.py` files created
- [ ] PR diff clearly shows what changed in each file
- [ ] For Subscribe API: Detected if preview mode (PreviewOptions present) or create mode
- [ ] For Subscribe API: Preview mode uses `/v1/orders/preview` endpoint with `previewAccountInfo`
- [ ] For Subscribe API: Create mode uses `/v1/orders` endpoint with `newAccount` or `existingAccountNumber`
- [ ] For Subscribe API: Preview mode includes required `previewOptions.previewTypes` array
- [ ] For Subscribe API: Create mode includes `processingOptions` (not used in preview)
- [ ] For Subscribe API: Detected if new or existing account
- [ ] For Subscribe API: Credit card field names updated (creditCardNumber → cardNumber)
- [ ] For Subscribe API: Term configuration converted to structured format
- [ ] For Subscribe API: Payment method handling noted (Order API limitation for existing accounts)
- [ ] Supporting artifacts (validation scripts, checklists) created as separate new files
