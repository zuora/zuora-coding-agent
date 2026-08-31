# Zuora CPQ Customization Patterns

## Source Docs And Signatures

- Class names, method names, method parameters, return types, hook signatures, event names, event payload shapes, and Visualforce component attributes must strictly match official Zuora docs and examples bundled in this codebase.
- Do not invent helper classes, callback methods, overloads, event payload keys, or component attributes. If a signature is not documented locally or in the source docs, ask for the exact reference or state the assumption before generating code.
- Copy Quote Studio hook signatures exactly from `cpq-js-hooks.json`. Do not add resolver/reject parameters or host payload parameters such as `{ record, connectedQuote }`; `beforeSave`, `beforeSubmit`, and `beforePreviewCall` take no parameters and return optional Boolean values.
- Source docs:
  - https://docs.zuora.com/en/zuora-cpq/development-resources/zuora-cpq-component-library
  - https://docs.zuora.com/en/zuora-cpq/development-resources/overview-of-zuora-cpq-development-resources

## Quote Studio JavaScript

- Use headless components for save/submit/product lifecycle interception.
- Use sidebar components for visible UI assistance.
- Generate Quote Studio customizations as LWC classes extending `LightningElement` with public `@api` hook methods. Do not import `QuoteStudioHooks` from `@zuora/cpq`, extend `QuoteStudioHooks.ChargeFieldChange`, or generate `onInit`/`onChange` callbacks.
- Maintain one active headless component per Quote Studio configuration unless the user explicitly requests another component. Prefer the generic component name `headlessComponent`.
- For follow-up headless requirements, update the existing generic headless component instead of creating a new LWC. Consolidate hook and event logic into that component.
- If multiple existing headless components are found and the active component is ambiguous, ask the user which component to update before writing files.
- For non-MSQ headless components, include `@api quoteState`, `@api metricState`, and `@api pageState`.
- For MSQ headless components, include `@api quoteState`, `@api metricState`, `@api pageState`, `@api masterQuoteState`, and `@api parentQuoteState`.
- For Zuora managed package version 10.58 or later, or when the user states `zqfClient` is available, import `ZQFClient` from `zqu/zqfClient` and construct it from `quoteState` and `pageState` before reading, updating, or firing quote state changes.
- Do not call `this.quoteState.getQuote()`, `this.quoteState.updateQuote(...)`, `connectedQuote.updateQuote(...)`, or resolver-style hook callbacks. Do not declare `@api record` for headless hooks or return `{ success: true }`. Use `this.zqf.getQuote()`, `this.zqf.getQuoteField(...)`, and dispatched `this.zqf.updateQuote(patch)` events when ZQFClient is available.
- If the package version is unknown and the task requires quote state helper behavior, ask whether the installed Zuora managed package version is 10.58 or later.
- If the installed package version is earlier than 10.58, do not use `ZQFClient`; proceed with generic quote-state methods using supported hook return payloads and documented events from `cpq-js-events.json`.
- Use supported events to persist changes. Do not directly mutate CPQ-owned state and assume persistence.
- **Method selection priority**: (1) Use a documented ZQF helper from `cpq-zqf-client.md` first. (2) If no ZQF helper covers the requirement, fall back to generic patterns: hook return payloads, documented `quoteState` property reads, or raw `new CustomEvent(...)` with names from `cpq-js-events.json`; add a comment stating the assumption. (3) Never call a `this.zqf.*` method not listed in `cpq-zqf-client.md`, and never use raw `CustomEvent` for operations that have a ZQF mutation helper.
- Use `ZQFClient` mutation helpers instead of manually constructing quote-state update events when the target package version is 10.58 or later. Mutation helpers return `CustomEvent` objects; dispatch those returned events explicitly.
- For multiple CPQ object field updates in one hook, prefer the matching patch or bulk `ZQFClient` helper over repeated field-level helpers. Use `updateQuote(patch)` for quote fields, `updateCharges([...])` for QRPC charges, `updateRatePlans([...])` for QRP changes, `updateTiers([...])` for tiers, `updateAmendments([...])` for amendments, or `updateProducts({ ratePlans, charges, tiers })` for mixed product changes.
- For ramp interval charge updates, resolve the target interval with `getRampIntervals()`, `getActiveRampInterval()`, or `getRampIntervalByDate(...)` and use interval-scoped helpers such as `updateChargesInInterval(interval, updates)`. For second-ramp-interval QRPC updates, use the canonical `getRampIntervals()` plus `updateChargesInInterval(secondRampInterval, [{ filter, update }])` pattern from `cpq-zqf-client.md`. Use filter/update descriptors; do not select intervals with `getQuoteField(RAMP_INTERVAL_FIELD)`, manually traverse `getProducts()`, `product.ratePlans`, `ratePlan.charges`, `quoteState.quoteRatePlans`, `interval.charges`, or `secondInterval.charges`, and do not invent product/rate-plan-charge helpers.
- Read quote header fields with `getQuote()` / `getQuoteField(...)`; do not read from `quoteState.quote`.
- Read charge, rate plan, tier, and amendment fields from wrapper `.record` properties, for example `charge.record.zqu__Quantity__c` and `ratePlan.record.Name`; do not read `charge.zqu__Quantity__c`, `charge.Name`, or `ratePlan.Name` directly.
- `quoteState.productTimelines` is an object map, not an array. Use `this.zqf.getProductTimelines()` when timeline iteration is required.
- For ramp quote logic, iterate ramp **intervals** (`getRampIntervals()`), not timeline **versions** (`getVersions(...)`). Versions represent effective-date slices within one product timeline; ramp intervals represent pricing periods across the quote.
- Prefer documented `ZQFClient` read helpers over manual nested traversal of `product.ratePlans`, `ratePlan.charges`, or `quoteState.quoteRatePlans`.
- Do not detect ramp quotes by `RecordType.Name` or record type labels. For ramp-specific behavior, check whether ramp intervals exist and, when the real quote boolean field API name is known, whether that field is `true`.
- For product update hooks, return `{ proceed: true }` plus the updated payload keys required by the hook.
- For `toastMessageDisplay`, use `theme` values `warning`, `error`, or `success`.
- For `objectFieldConfig`, provide `field` and `object` and include timeline/charge context for charge-level configuration. Do not query or mutate Quote Studio DOM with `document.querySelector`, `[data-charge-id]`, `[data-field]`, or `.style.*`; use `objectfieldconfig` instead.
- Do not probe both namespaced and non-namespaced forms of the same field. Managed package fields use the `zqu__` namespace, for example `zqu__TriggerEvent__c`; custom fields outside the package do not use `zqu__`, for example `TriggerEvent__c`.
- Keep hook and event handler methods thin; extract business logic into a colocated `<componentName>Helper.js` module with plain exported functions, imported via relative path. Skip the helper file for trivial single-line hook bodies.

## Legacy Apex and Component Library

- Prefer global CPQ APIs over internal managed package classes.
- Keep namespace handling explicit: `zqu__Quote__c`, `zqu__QuoteRatePlan__c`, `zqu__QuoteRatePlanCharge__c`, and `zqu__QuoteAmendment__c`.
- Managed package fields and objects use the `zqu__` namespace. Custom fields and objects that are not part of the managed package must not use the `zqu__` namespace.
- Bulkify SOQL and DML.
- Keep Visualforce controllers thin and push reusable logic into Apex services.

## Migration

- Map legacy save/submit validation to `beforeSave` or `beforeSubmit`.
- Map legacy post-load UI behavior to `afterQuoteStudioLoad` plus supported events.
- Reimagine unsupported Visualforce/UI plugins as Quote Studio sidebar or headless components.

---

# Zuora CPQ Development Global Rules and Best Practices

This section contains comprehensive global rules and best practices for Zuora CPQ development across all Salesforce projects. These rules must be followed when creating Apex classes.

## Renewal Quote Field Mappings

Always apply these field mappings when creating renewal quotes:

- `Name` = Opportunity.Name (quote name matches opportunity name)
- `zqu__Amendment_Name__c` = Opportunity.Name (for amendment tracking)
- `zqu__ExistSubscriptionID__c` = Zuora__Subscription__r.Zuora__Zuora_Id__c (use Zuora ID, not Salesforce ID)
- `zqu__ZuoraAccountId__c` = Zuora__CustomerAccount__r.Zuora__Zuora_Id__c (use Zuora Account ID)
- `zqu__SubscriptionType__c` = 'Renew Subscription' (for renewal quotes)
- `zqu__InitialTerm__c` = Extract numeric part from `Zuora__Subscription__r.Zuora__InitialTerm__c` (e.g., '36 Months' → 36)

### Zuora Contact Mappings

When working with Zuora Contacts in the context of quotes, note that:

- `Zuora__CustomerAccount__r.Zuora__BillToContact__c` and `Zuora__CustomerAccount__r.Zuora__SoldToContact__c` reference `Zuora__ZContact__c` records, not standard Salesforce Contact records.

### Best Practice for Contact Mappings

1. **Custom External ID Field**: Add a custom field on the `Zuora__ZContact__c` object to store the corresponding Salesforce Contact ID or External ID.
2. **Lookup Resolution**: Use this field to maintain the relationship between Zuora and Salesforce contacts.
3. **Quote Contact Fields**: When mapping to quote contact fields, ensure you're using the correct Zuora Contact ID from the `Zuora__ZContact__c` record.

Example field mappings:
- `zqu__BillToContact__c` = `Zuora__CustomerAccount__r.Zuora__BillToContact__r.Zuora__External_Id__c`
- `zqu__SoldToContact__c` = `Zuora__CustomerAccount__r.Zuora__SoldToContact__r.Zuora__External_Id__c`

## Required Fields for zqu.zQuoteUtil.renewQuote() API

Always query these fields before calling renewQuote:

### Essential Fields
- `Id` (Quote record ID)
- `zqu__Currency__c` (Quote currency)
- `zqu__ExistSubscriptionID__c` (Existing subscription ID for renewal)
- `zqu__SubscriptionType__c` (Must be 'Renew Subscription' for renewals)
- `zqu__BillingEntity__r.zqu__EntityID__c` (Billing entity ID from related record)
- `zqu__IsMSQ__c` (Multi-Subscription Quote flag)
- `zqu__SubscriptionTermEndDate__c` (Subscription term end date)
- `zqu__Amendment_Name__c` (Amendment name field)
- `zqu__AmendmentName__c` (Alternative amendment name field)
- `zqu__RenewalTerm__c` (Renewal term length)

### Recommended Fields
- `Name` (Quote name)
- `zqu__Account__c` (Account reference)
- `zqu__Opportunity__c` (Opportunity reference)
- `zqu__StartDate__c` (Quote start date)
- `zqu__Status__c` (Quote status)

### Usage Pattern
```apex
List<zqu__Quote__c> quotes = [
    SELECT Id, Name, zqu__ExistSubscriptionID__c, zqu__Account__c, zqu__Opportunity__c,
           zqu__SubscriptionType__c, zqu__StartDate__c, zqu__Currency__c, zqu__Status__c,
           zqu__BillingEntity__r.zqu__EntityID__c, zqu__IsMSQ__c, zqu__SubscriptionTermEndDate__c,
           zqu__Amendment_Name__c, zqu__AmendmentName__c, zqu__RenewalTerm__c
    FROM zqu__Quote__c 
    WHERE Id = :quoteId 
    LIMIT 1
];

zqu__Quote__c quote = quotes[0];
zqu.zQuoteUtil.renewQuote(quote);
```

## Batch Processing Architecture Rules

Never call queueable-triggering APIs in batch context:

- Avoid `zqu.zQuoteUtil.getZuoraConfigInformation()` in batch execute()
- **CRITICAL**: `buildAndSave()` method triggers queueables - NEVER call in batch execute()
- **CRITICAL**: `zqu.MetricsUtil` methods trigger queueables - NEVER call in batch execute()
- Use queueable classes for individual quote processing
- Separate database operations (batch) from API calls (queueable)
- Chain queueables for multiple item processing to avoid limits

### Queueable-Triggering Methods to Avoid in Batch Execute()

- `zqu.Quote.buildAndSave()` - Loads subscription products, triggers queueables
- `zqu.MetricsUtil.getPreviewedInvoiceItems()` - Quote preview/metrics, triggers queueables
- `zqu.MetricsUtil.getExistingInvoiceItems()` - Existing subscription metrics, triggers queueables
- `zqu.QuoteRecalculateController.JR_recalculate()` - Recalculates and saves metrics to quote, triggers queueables
- `zqu.QuoteRecalculateController.JR_recalculateInvoiceItemSummaries()` - Saves invoice summaries to quote, triggers queueables
- `zqu.zQuoteUtil.getZuoraConfigInformation()` - Configuration retrieval, triggers queueables
- Any method that performs Zuora API callouts or complex calculations

### Critical Limitation: Individual Quote Processing Required

The `buildAndSave()` method and related Zuora CPQ operations can only process ONE quote at a time due to queueable job limits. This means:

- **NEVER** attempt to process multiple quotes simultaneously in batch execute()
- **ALWAYS** enqueue individual quote processing using queueable classes
- **EACH** quote must be processed independently to avoid "Too many queueable jobs" errors
- **BATCH SIZE** should be set to 1 when processing quotes that require buildAndSave operations

### Quote Creation and Preview Pattern

When creating quotes programmatically and then previewing them:
1. **Batch execute()**: Create quotes using database operations only
2. **Batch finish()**: Call MetricsUtil for quote previewing/metrics
3. **Queueable**: Handle buildAndSave and other API operations

### Architecture Pattern

```apex
// In Batch Class - CRITICAL: Use batch size of 1 for quote processing
public class MyRenewalQuoteBatch implements Database.Batchable<SObject> {
    private List<String> createdQuoteIds = new List<String>();
    
    public Database.QueryLocator start(Database.BatchableContext context) {
        return Database.getQueryLocator(query);
    }
    
    public void execute(Database.BatchableContext context, List<Opportunity> opportunities) {
        // Database operations only - NO API calls
        for (Opportunity opp : opportunities) {
            String quoteId = createQuoteViaDatabase(opp);
            createdQuoteIds.add(quoteId);
            enqueueIndividualQuoteProcessing(quoteId, quoteParams);
        }
    }
    
    public void finish(Database.BatchableContext context) {
        if (!createdQuoteIds.isEmpty()) {
            MyQuoteMetricsQueueable metricsJob = new MyQuoteMetricsQueueable(createdQuoteIds);
            System.enqueueJob(metricsJob);
        }
    }
}

// Execute batch with batch size of 1
Database.executeBatch(new MyRenewalQuoteBatch(), 1);

// In Queueable Class for Individual Quote Processing
public class IndividualQuoteProcessingQueueable implements Queueable, Database.AllowsCallouts {
    private String currentQuoteId;
    private List<String> remainingQuoteIds;
    
    public void execute(QueueableContext context) {
        if (String.isNotBlank(currentQuoteId)) {
            zqu.zQuoteUtil.renewQuote(quote);
            zqu.Quote quoteObj = new zqu.Quote(currentQuoteId);
            quoteObj.buildAndSave();
        }
        
        // Chain next quote processing if more quotes remain
        if (!remainingQuoteIds.isEmpty()) {
            String nextQuoteId = remainingQuoteIds.remove(0);
            IndividualQuoteProcessingQueueable nextJob = 
                new IndividualQuoteProcessingQueueable(nextQuoteId, remainingQuoteIds);
            System.enqueueJob(nextJob);
        }
    }
}
```

### Key Architectural Principles

1. **Database Operations**: Batch can create multiple quotes simultaneously
2. **buildAndSave Operations**: Must be processed ONE quote at a time in queueables
3. **Metrics Operations**: Can process multiple quotes in a single queueable
4. **Queueable Chaining**: Use chaining to process multiple quotes sequentially

## Quote Metrics and Recalculation Methods

Use these methods for saving metrics and calculations to quotes:

### Quote Recalculation Methods
- `zqu.QuoteRecalculateController.JR_recalculate()` - Recalculates and saves metrics to the quote
- `zqu.QuoteRecalculateController.JR_recalculateInvoiceItemSummaries()` - Saves invoice summaries to quote

### Configuration-Dependent Behavior

#### Charge Segment Metrics
- **Configuration**: Zuora Config > Quote Studio Settings > Admin Config > "Enable Charge Segment Metrics"
- **When Enabled**: `JR_recalculate()` generates charge segments along with metrics
- **When Disabled**: Only basic metrics are calculated and saved

#### Invoice Item Summaries
- **Configuration**: Zuora Config > Quote Studio Settings > Admin Config > "Summarize Invoice Item"
- **When Enabled**: `JR_recalculateInvoiceItemSummaries()` generates invoice item summary records
- **When Disabled**: Method returns failure result with appropriate message instead of generating summaries

### Usage Pattern in Queueable Context

```apex
public void execute(QueueableContext context) {
    for (String quoteId : quoteIds) {
        try {
            zqu.QuoteRecalculateController.JR_recalculate(quoteId);
            
            // Returns zqu.zQuoteUtil.ZBillingResult, not Map<String, Object>
            zqu.zQuoteUtil.ZBillingResult summaryResult = 
                zqu.QuoteRecalculateController.JR_recalculateInvoiceItemSummaries(quoteId);
            
            if (summaryResult != null && summaryResult.success) {
                System.debug('Invoice item summaries calculated for quote: ' + quoteId);
            }
        } catch (Exception e) {
            System.debug('Error recalculating metrics for quote ' + quoteId + ': ' + e.getMessage());
        }
    }
}
```

### Important Notes
- **NEVER call these methods in batch execute()** - they trigger queueables
- **Always call in queueable or finish() context** for proper execution
- **Check configuration settings** to understand expected behavior
- **Handle failures gracefully** when configuration settings are disabled

## Error Handling Patterns

Always implement defensive programming:

- Add null checks before accessing API result objects
- Use `if (result != null && result.success)` pattern
- Don't re-throw exceptions in metrics/secondary processing
- Log errors with specific context for debugging
- Continue processing other items when one fails
- On silent failures — a `null` or empty API result, `result.success == false` with no exception, or a call that returned but produced no effect — suggest logging the request arguments and returned result object to isolate the break (see `best-practices.md` `## Error handling`).

### Error Handling Template

```apex
try {
    zqu.MetricsUtil.InvoiceItemsResult result = zqu.MetricsUtil.getExistingInvoiceItems(quoteId);
    
    if (result != null && result.success && result.invoiceItems != null) {
        for (zqu.MetricsUtil.InvoiceItem item : result.invoiceItems) {
            if (item != null && item.chargeAmount != null) {
                // Process item safely
            }
        }
    } else {
        String errorMsg = 'No data available';
        if (result != null && result.message != null) {
            errorMsg = result.message;
        } else if (result == null) {
            errorMsg = 'API returned null';
        }
        System.debug('Error: ' + errorMsg);
    }
    
} catch (Exception e) {
    System.debug('Error in processing: ' + e.getMessage());
}
```

## Zuora CPQ API Hierarchy

Use APIs in this order of preference:

1. **CPQ-X APIs** (zqu.CPQX namespace) - for enterprise implementations
2. **Standard CPQ APIs** (zqu.QuoteUtil, zqu.MetricsUtil) - for standard implementations
3. **Direct database operations** - only when APIs are not available
4. **NEVER directly manipulate zqu__QuoteCharge__c** (deprecated)

### Key Zuora CPQ Global Classes

#### Standard CPQ Classes
- `zqu.Quote` - Main quote management class
- `zqu.QuoteUtil` - Quote utility functions
- `zqu.MetricsUtil` - Financial metrics and calculations
- `zqu.ProductTimeline` - Product timeline management
- `zqu.QPlan` - Quote plan management
- `zqu.QCharge` - Quote charge management
- `zqu.QTier` - Quote tier management

#### CPQ-X Classes
- `zqu.CPQX` - Main CPQ-X API entry point
- `zqu.CPQX.Quote` - CPQ-X Quote Management
- `zqu.CPQX.Product` - Product Management
- `zqu.CPQX.Subscription` - Subscription Operations
- `zqu.CPQX.Amendment` - Amendment Processing
- `zqu.CPQX.Billing` - Billing Integration
- `zqu.CPQX.Metrics` - Advanced Metrics

## Subscription and Account ID Usage

Always use Zuora IDs, not Salesforce record IDs:

- **Subscription ID**: `Zuora__Subscription__r.Zuora__Zuora_Id__c`
- **Account ID**: `Zuora__CustomerAccount__r.Zuora__Zuora_Id__c`
- **Billing Entity ID**: `zqu__BillingEntity__r.zqu__EntityID__c`
- **Invoice Owner ID**: `Zuora__InvoiceOwner__r.Zuora__Zuora_Id__c`

### Field Replacement Rules
- Replace `zqu__BillingAccount__c` (deprecated) with `zqu__ZuoraAccountId__c`
- Use `zqu__ExistSubscriptionID__c` with Zuora subscription ID, not Salesforce record ID

## Complete Field Mapping Template

Standard renewal quote field mappings:

```apex
Map<String, Object> quoteParams = new Map<String, Object>();

// Set Name and Amendment Name to Opportunity Name
quoteParams.put('Name', opportunity.Name);
quoteParams.put('zqu__Amendment_Name__c', opportunity.Name);
quoteParams.put('zqu__Account__c', opportunity.AccountId);
quoteParams.put('zqu__Opportunity__c', opportunity.Id);
quoteParams.put('zqu__SubscriptionType__c', 'Renew Subscription');
quoteParams.put('zqu__Primary__c', true);

// Set Zuora IDs (not Salesforce record IDs)
quoteParams.put('zqu__ExistSubscriptionID__c', subscription.Zuora__Zuora_Id__c);
quoteParams.put('zqu__ZuoraAccountId__c', customerAccount.Zuora__Zuora_Id__c);

// Set dates and terms
quoteParams.put('zqu__StartDate__c', subscription.Zuora__SubscriptionEndDate__c);
String initialTerm = subscription.Zuora__InitialTerm__c?.replaceAll('[^0-9]', '');
quoteParams.put('zqu__InitialTerm__c', String.isNotBlank(initialTerm) ? Integer.valueOf(initialTerm) : null);
quoteParams.put('zqu__RenewalTerm__c', subscription.Zuora__RenewalTerm__c);

// Set subscription details
quoteParams.put('zqu__Hidden_Subscription_Name__c', subscription.Name);
quoteParams.put('zqu__SubscriptionVersion__c', subscription.Zuora__Version__c);

// Set term dates
quoteParams.put('zqu__SubscriptionTermStartDate__c', subscription.Zuora__TermEndDate__c);
quoteParams.put('zqu__RenewalSubscriptionTermStartDate__c', subscription.Zuora__TermEndDate__c);
quoteParams.put('zqu__Subscription_Term_Type__c', subscription.Zuora__TermSettingType__c);
quoteParams.put('zqu__InitialTermPeriodType__c', subscription.Zuora__InitialTermPeriodType__c);
quoteParams.put('zqu__RenewalSetting__c', subscription.Zuora__RenewalTermPeriodType__c);

// Set contacts and billing
quoteParams.put('zqu__BillToContact__c', customerAccount.Zuora__BillToContact__c);
quoteParams.put('zqu__SoldToContact__c', customerAccount.Zuora__SoldToContact__c);
quoteParams.put('zqu__InvoiceOwnerId__c', invoiceOwner.Zuora__Zuora_Id__c);
```

## Testing Patterns

Always implement proper test patterns:

- Use `Test.isRunningTest()` to skip actual API calls
- Mock Zuora API responses in test context
- Test both success and failure scenarios
- Verify amendment creation after renewQuote calls
- Test queueable chaining and limits
- **CRITICAL**: Use `System.assert(false, message)` instead of `System.fail(message)` for test failures

### Test Assertion Rules

**NEVER use `System.fail()` - it does not exist in Salesforce Apex:**

```apex
// ❌ INCORRECT - This will cause compilation errors
System.fail('This should not happen');

// ✅ CORRECT - Use System.assert with false condition
System.assert(false, 'This should not happen');
```

### Exception Handling in Tests

```apex
try {
    someMethod();
    System.assert(true, 'Method executed successfully');
} catch (Exception e) {
    System.assert(false, 'Method should not throw exceptions: ' + e.getMessage());
}
```

### Test Pattern Example

```apex
@isTest
private static void testRenewalQuoteProcessing() {
    Test.startTest();
    
    if (Test.isRunningTest()) {
        // Mock Zuora API responses
    }
    
    try {
        processRenewalQuote();
        System.assert(true, 'Quote processing completed successfully');
    } catch (Exception e) {
        System.assert(false, 'Quote processing failed: ' + e.getMessage());
    }
    
    Test.stopTest();
    
    // Verify amendment creation
    List<zqu__QuoteAmendment__c> amendments = [
        SELECT Id, zqu__Type__c 
        FROM zqu__QuoteAmendment__c 
        WHERE zqu__Quote__c = :quoteId 
        AND zqu__Type__c = 'Renewal'
    ];
    System.assertEquals(1, amendments.size(), 'Renewal amendment should be created');
}
```

## SOQL Query Requirements

Include all related Zuora fields in queries:

### Required Zuora Subscription Fields

```sql
SELECT Id, Name, AccountId, Zuora_Subscription__c,
       Zuora_Subscription__r.Zuora__NextRenewalDate__c,
       Zuora_Subscription__r.Zuora__CustomerAccount__c,
       Zuora_Subscription__r.Zuora__CustomerAccount__r.Zuora__Currency__c,
       Zuora_Subscription__r.Zuora__CustomerAccount__r.Zuora__Zuora_Id__c,
       Zuora_Subscription__r.Zuora__CustomerAccount__r.Zuora__AccountNumber__c,
       Zuora_Subscription__r.Zuora__CustomerAccount__r.Zuora__BillToContact__c,
       Zuora_Subscription__r.Zuora__CustomerAccount__r.Zuora__SoldToContact__c,
       Zuora_Subscription__r.Zuora__Zuora_Id__c,
       Zuora_Subscription__r.Zuora__RenewalTerm__c,
       Zuora_Subscription__r.Zuora__InitialTerm__c,
       Zuora_Subscription__r.Zuora__SubscriptionEndDate__c,
       Zuora_Subscription__r.Zuora__TermEndDate__c,
       Zuora_Subscription__r.Zuora__TermSettingType__c,
       Zuora_Subscription__r.Zuora__InitialTermPeriodType__c,
       Zuora_Subscription__r.Zuora__RenewalTermPeriodType__c,
       Zuora_Subscription__r.Zuora__InvoiceOwner__c,
       Zuora_Subscription__r.Zuora__InvoiceOwner__r.Zuora__Zuora_Id__c,
       Zuora_Subscription__r.Zuora__Version__c,
       Zuora_Subscription__r.Name
FROM Opportunity
WHERE Type = 'Renewal'
AND Zuora_Subscription__c != null
```

## Deployment and Monitoring

Follow these deployment practices:

- Test in sandbox with actual Zuora integration
- Monitor Apex job queues for queueable processing
- Implement custom logging for Zuora API interactions
- Set up alerts for batch processing failures
- Verify amendment creation in Zuora after renewQuote calls

### Monitoring Checklist
- [ ] Batch job completion rates
- [ ] Queueable job success rates
- [ ] Quote creation success rates
- [ ] Amendment creation verification
- [ ] Error log analysis
- [ ] Performance metrics tracking

## Zuora CPQ API Return Types

**CRITICAL**: Always use correct return types for Zuora CPQ API methods:

### ZBillingResult Return Type

- `zqu.QuoteRecalculateController.JR_recalculateInvoiceItemSummaries()` returns `zqu.zQuoteUtil.ZBillingResult`
- **NOT** `Map<String, Object>` as commonly assumed
- Access success property directly: `result.success` (not `result.get('success')`)

### Correct Usage Pattern

```apex
// ✅ CORRECT - Use proper return type
zqu.zQuoteUtil.ZBillingResult summaryResult = 
    zqu.QuoteRecalculateController.JR_recalculateInvoiceItemSummaries(quoteId);

if (summaryResult != null && summaryResult.success) {
    System.debug('Invoice summaries calculated successfully');
}

// ❌ INCORRECT - Wrong return type
Map<String, Object> summaryResult = 
    zqu.QuoteRecalculateController.JR_recalculateInvoiceItemSummaries(quoteId);
```

### Other Common Return Types
- `zqu.MetricsUtil.getPreviewedInvoiceItems()` returns `zqu.MetricsUtil.InvoiceItemsResult`
- `zqu.MetricsUtil.getExistingInvoiceItems()` returns `zqu.MetricsUtil.InvoiceItemsResult`
- `zqu.Quote.buildAndSave()` returns `zqu.Quote` object (not boolean)

## Ramp Deal Processing Rules

For Zuora CPQ-X ramp deal quotes with multiple pricing intervals:

### Ramp Deal Detection
- Check `quote.zqu__Ramp__c = true` to identify ramp deals
- Access ramp intervals via `subscription.rampIntervals` array
- Each interval has `startDate`, `endDate`, and `index` properties

### Amendment Date Alignment

When processing ramp charges, update amendment dates to align with ramp intervals:

```apex
amendment.record.zqu__ContractEffectiveDate__c = rampInterval.startDate;
amendment.record.zqu__ServiceActivationDate__c = rampInterval.startDate;
amendment.record.zqu__CustomerAcceptanceDate__c = rampInterval.startDate;
```

### Charge Effective Date Alignment

Align charge effective dates with ramp interval start dates:

```apex
charge.record.zqu__EffectiveStartDate__c = rampInterval.startDate;
```

### Ramp Pricing Application
- Apply percentage uplifts only to recurring charges (`zqu__ChargeType__c = 'Recurring'`)
- Use ramp interval index for progressive uplift calculations
- Store original pricing for reset functionality
- Apply uplifts to tiered pricing structures when present

### Ramp Deal Processing Pattern

```apex
for (Integer i = 0; i < rampIntervals.size(); i++) {
    RampInterval interval = rampIntervals[i];
    
    // Apply pricing uplift for this interval
    Decimal upliftMultiplier = 1 + (upliftPercent / 100);
    Decimal newPrice = currentPrice * upliftMultiplier;
    
    // Align dates with ramp interval
    charge.zqu__EffectiveStartDate__c = interval.startDate;
    amendment.zqu__ContractEffectiveDate__c = interval.startDate;
    amendment.zqu__ServiceActivationDate__c = interval.startDate;
    amendment.zqu__CustomerAcceptanceDate__c = interval.startDate;
}
```

### Ramp Deal Custom Tracking Fields

Always add these custom fields to track ramp deal processing:

```javascript
charge.record.Ramp_Deal_Applied__c = true;
charge.record.Ramp_Deal_Uplift_Percent__c = upliftPercent;
charge.record.Ramp_Deal_Original_Price__c = originalPrice;
charge.record.Ramp_Deal_Ramp_Index__c = rampIndex;
```

## Common Pitfalls to Avoid

### Queueable Job Limits
- **Problem**: "Too many queueable jobs added to the queue: 2" error
- **Solution**: Never call queueable-triggering APIs in batch context

### Wrong ID Types
- **Problem**: Using Salesforce record IDs instead of Zuora IDs
- **Solution**: Always use `Zuora__Zuora_Id__c` fields for Zuora references

### Null Pointer Exceptions
- **Problem**: Accessing API result properties without null checks
- **Solution**: Always check `if (result != null && result.success)` before accessing properties

### Deprecated Fields
- **Problem**: Using `zqu__BillingAccount__c` or directly manipulating `zqu__QuoteCharge__c`
- **Solution**: Use `zqu__ZuoraAccountId__c` and Zuora APIs instead

### Wrong API Return Types
- **Problem**: Using `Map<String, Object>` for `JR_recalculateInvoiceItemSummaries()` return
- **Solution**: Use `zqu.zQuoteUtil.ZBillingResult` and access `result.success` directly

### Missing Amendment Date Alignment
- **Problem**: Ramp deal charges without proper amendment date alignment
- **Solution**: Set all three amendment dates to ramp interval start date

---

**CRITICAL: These rules apply to ALL Zuora CPQ development across any Salesforce org or project.**
