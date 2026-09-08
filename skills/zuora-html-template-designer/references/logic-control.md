# Logic control and looping

Although Mustache is an illogical template engine, you can still use merge fields to conduct basic logic control and looping in HTML templates for billing documents, including invoices, credit memos, and debit memos.

## Conditional control 

If the input data meets the condition specified by the merge fields, the content defined in the middle of merge fields is displayed in the rendered result.

The following table lists merge field examples with conditional control.

 	
| | Pseudo-code | Merge Fields | Description |
|---|---|---|---|
| **Boolean field** | `If Invoice.Account.AutoPay == True`<br>`  "Auto pay account"`<br>`Else`<br>`  "AutoPay is not enabled"` | `{{#Invoice.Account.AutoPay}}`<br>`  "Auto pay account"`<br>`{{/Invoice.Account.AutoPay}}`<br><br>`{{^Invoice.Account.AutoPay}}`<br>`  "AutoPay is not enabled."`<br>`{{/Invoice.Account.AutoPay}}` | If an account has the AutoPay option enabled, the Auto pay account message is displayed in the rendered result.<br><br>If an account has the AutoPay option disabled, the AutoPay is not enabled. message is displayed in the rendered result. |
| **Field with Boolean functions** | `If InvoiceItems.IsEmpty`<br>`  "Empty Invoice"`<br>`Else`<br>`  "Non-Empty Invoice"` | `{{#Invoice.InvoiceItems\|IsEmpty}}`<br>`  "Empty invoice"`<br>`{{/Invoice.InvoiceItems\|IsEmpty}}`<br><br>`{{^Invoice.InvoiceItems\|IsEmpty}}`<br>`  "Non-Empty Invoice"`<br>`{{/Invoice.InvoiceItems\|IsEmpty}}` | If the InvoiceItems list is empty, the Empty invoice message is displayed in the rendered result.<br><br>If the InvoiceItems list is non-empty, the Non-Empty Invoice message is displayed in the rendered result. |
| | `If Account.AccountNumber == null or Account.AccountNumber.isBlank`<br><br>`  "Show a blank string"`<br><br>`Else`<br><br>`{{Account.AccountNumber}}` | `{{#Invoice.Account.AccountNumber\|IsBlank}}`<br>`  ""`<br>`{{/Invoice.Account.AccountNumber\|IsBlank}}`<br><br>`{{^Invoice.Account.AccountNumber\|IsBlank}}`<br>`{{Invoice.Account.AccountNumber}}`<br>`{{/Invoice.Account.AccountNumber\|IsBlank}}` | If the AccountNumber value of an account is blank, a blank string is displayed.<br><br>If the AccountNumber value of an account is not blank, the actual account number is displayed in the rendered result. |
| **And** | `If Account.AutoPay and Balance == 0`<br>`  "AutoPay account and zero balance"` | `{{#Account.AutoPay}}`<br>`{{#Balance\|EqualToVal(0)}}`<br>`  "AutoPay account and zero balance"`<br>`{{/Balance\|EqualToVal(0)}}`<br>`{{/Account.AutoPay}}` | If an account has the AutoPay option enabled and the account's balance is equal to zero, the automatically paid account with zero balance is displayed in the rendered result. |
| **Exists** | `If Account.Entity__c == French and Hardware Product exists`<br>`  "Display a message."` | `{{#Invoice}}`<br><br>`{{#Account.Entity__c\|EqualToVal(French)}}`<br><br>`{{^InvoiceItems\|Map(RatePlanCharge)\|Map(ProductRatePlanCharge)\|Map(ProductRatePlan)\|Map(Product)\|FilterByValue(ProductType__c,EQ,Hardware)\|IsEmpty}}`<br><br>`"Display message 1"`<br><br>`{{/InvoiceItems\|Map(RatePlanCharge)\|Map(ProductRatePlanCharge)\|Map(ProductRatePlan)\|Map(Product)\|FilterByValue(ProductType__c,EQ,Hardware)\|IsEmpty}}`<br><br>`{{/Account.Entity__c\|EqualToVal(French)}}`<br><br>`{{/Invoice}}` | The example above is based on the following assumptions and will need to be updated to meet your use case:<br><br>The custom fields Account.entity__c and ProductType__c exist.<br><br>The custom field ProductType__c = Hardware.<br><br>If an account has a custom field named Entity__c and a product has a custom field named ProductType__c, the Map Map function returns a list of Product values. |
| **Equals** | `If RatePlanCharge.ChargeModel == "Flat Fee Pricing"`<br><br>`"Is Flat Fee"`<br><br>`Else`<br><br>`"Not Flat Fee"` | `{{#Wp_Eval}}`<br><br>`"{{RatePlanCharge.ChargeModel}}" == "Flat Fee Pricing" ? "Is Flat Fee" : "Not Flat Fee"`<br><br>`{{/Wp_Eval}}` | The assumption for the above code is that it would be copied and pasted into a Charge Details table component.<br><br>If the charge model of a rate plan charge is Flat Fee Pricing, the Is Flat Fee message is displayed in the rendered result.<br><br>Otherwise, the Not Flat Fee message is displayed in the rendered result. |
| | `If RatePlanCharge.ChargeModel == "Per Unit Pricing"`<br><br>`Display like Per Unit: $ 70.00 Per License`<br><br>`Else Display like Flat Fee: $ 4.50` | `{{#Wp_Eval}}`<br><br>`"{{RatePlanCharge.ChargeModel}}" == "Per Unit Pricing" ? \``<br><br>`<b>Per Unit: {{Invoice.Account.Currency\|Symbol}} {{UnitPrice\|Round(2)\|Localise}} Per {{UOM}}</b>`<br><br>`\`: '`<br><br>`Flat Fee: {{Invoice.Account.Currency\|Symbol}} {{UnitPrice\|Round(2)\|Localise}}`<br><br>`'`<br><br>`{{/Wp_Eval}}` | The assumption for the above code is that it would be copied and pasted into a Charge Details table component.<br><br>If the charge model of a rate plan charge is Per Unit Pricing, the text in the format of Per Unit: {{Invoice.Account.Currency\|Symbol}} {{UnitPrice\|Round(2)\|Localise}} Per {{UOM}} is displayed in the rendered result, for example, Per Unit: $ 70.00 Per License.<br><br>Otherwise, the text in the format of Flat Fee: {{Invoice.Account.Currency\|Symbol}} {{UnitPrice\|Round(2)\|Localise}} like is displayed in the rendered result, for example, Flat Fee: $ 4.50. |
| **Multiple conditions** | `If RatePlanCharge.ChargeModel == "Flat Fee Pricing"`<br><br>`"Flat Fee Pricing"`<br><br>`Else If RatePlanCharge.ChargeModel == "Per Unit Pricing"`<br><br>`"Per Unit Pricing"`<br><br>`Else If RatePlanCharge.ChargeModel == "Tiered Pricing"`<br><br>`"Tiered Pricing"`<br><br>`Else`<br><br>`"Other Pricing"` | `{{#Wp_Eval}}`<br><br>`"{{RatePlanCharge.ChargeModel}}" == "Flat Fee Pricing" ? "Flat Fee Pricing" : "{{RatePlanCharge.ChargeModel}}" == "Per Unit Pricing" ? "Per Unit Pricing" : "{{RatePlanCharge.ChargeModel}}" == "Tiered Pricing" ? "Tiered Pricing" : "Other Pricing"`<br><br>`{{/Wp_Eval}}` | The assumption for the above code is that it would be copied and pasted into a Charge Details table component.<br><br>If the charge model of a rate plan charge is Flat Fee Pricing, the Flat Fee Pricing message is displayed in the rendered result.<br><br>If the charge model of a rate plan charge is not Flat Fee Pricing, the rendered result depends on conditions.<br><br>If the charge model of a rate plan charge is Per Unit Pricing, the Per Unit Pricing message is displayed in the rendered result.<br>If the charge model of a rate plan charge is Tiered Pricing, the Tiered Pricing message is displayed in the rendered result.<br>If the charge model of a rate plan charge is not any of the preceding charge models, the Other Pricing message is displayed in the rendered result. | 

## Loop control 
You can use list section merge fields to achieve looping. The following table lists merge field examples with loop control.

| | Pseudo-code | Merge Fields | Description |
|---|---|---|---|
| **Loop lists** | `for item in Invoice.InvoiceItems`<br>`  print item.ChargeName - item.ServiceStartDate -- item.ServiceEndDate` | `{{#Invoice.InvoiceItems}}`<br>`{{ChargeName}} - {{ServiceStartDate}} -- {{ServiceEndDate}}`<br>`{{/Invoice.InvoiceItems}}` | You can use this example to show the charge name and service period of all invoice items in generated invoices. |
| **Nested loops** | `for invoiceItem in Invoice.InvoiceItems`<br>`  print invoiceItem.ChargeName :`<br>`  for taxItem in invoiceItem.TaxationItems`<br>`    print taxItem.Name -- taxItem.TaxAmount` | `{{#Invoice.InvoiceItems}}`<br>`{{ChargeName}} :`<br>`{{#TaxationItems}}`<br>`{{Name}} -- {{TaxAmount}}`<br>`{{/TaxationItems}}`<br>`{{/Invoice.InvoiceItems}}` | You can use this example to show all taxation items of every invoice item in generated invoices. |

## Nested loops 

A nested loop is a loop inside another loop. For example, you might want to show all taxation items for every invoice item.

The pseudocode is as follows:
```
for invoiceItem in Invoice.InvoiceItems
  print invoiceItem.ChargeName :
  for taxItem in invoiceItem.TaxationItems
    print taxItem.Name -- taxItem.TaxAmount
```

To do the same with merge fields in HTML invoice templates, you can use the following merge fields:
```
{{#Invoice.InvoiceItems}}
{{ChargeName}} :
{{#TaxationItems}}
{{Name}} -- {{TaxAmount}}
{{/TaxationItems}}
{{/Invoice.InvoiceItems}}
```

For example, if you want to show a charge details table for each subscription. One invoice contains multiple subscriptions.

The pseudocode is as follows:
```
for subscription in Invoice.InvoiceItems.Subscription
  print subscription.Name
  for invoiceItem in invoiceItems of Subscription
    print ChargeName -- ChargeAmount
```

To do the same with merge fields in HTML invoice templates, you can use the following example HTML code. The GroupBy function transforms an InvoiceItems list into a new list, which consists of two fields only:

* `Subscription.Name`: It is the field name used for grouping.
* `_Group`: It is a hard-coded key, which contains a list of InvoiceItems with the same subscription name.

See the `GroupBy` function in Functions used in merge fields for more information.

```html
{{#InvoiceItems|SortBy(ServiceStartDate,ASC)|GroupBy(Subscription.Name)}}
<h4>Subscription: {{Subscription.Name}}</h4>
{{Cmd_Assign(BySubscriptionName,_Group)}}
  <table class="table-grid u_content_custom_generic_table_1">
  <thead><tr>
      <th style="width:auto; text-align:right;">
          Description
      </th>
      <th style="width:auto; text-align:right;">
          Charge Amount
      </th>
      <th style="width:auto;text-align:right; ">
          Tax
      </th>
      <th style="width:auto; text-align:right;">
          Total
      </th></tr></thead>
  <tbody>
  {{#BySubscriptionName}}
    <tr>
      <td style="">{{ChargeName}}</td>
      <td style="text-align:right;">{{ChargeAmount}}</td>
      <td style="text-align:right;">{{TaxAmount}}</td>
      <td style="text-align:right;">{{#Wp_Eval}}{{ChargeAmount}}+{{TaxAmount}}{{/Wp_Eval}}</td>
    </tr>
  {{/BySubscriptionName}} 
    <tr>
      <td style="text-align:right;">Subtotal</td>
      <td style="text-align:right;">{{BySubscriptionName|Sum(ChargeAmount)}}</td>
      <td style="text-align:right;">{{BySubscriptionName|Sum(TaxAmount)}}</td>
      <td style="text-align:right;">{{#Wp_Eval}}{{BySubscriptionName|Sum(ChargeAmount)}}+{{BySubscriptionName|Sum(TaxAmount)}}{{/Wp_Eval}}</td>
    </tr>
  </tbody>
  </table>
  {{/InvoiceItems|SortBy(ServiceStartDate,ASC)|GroupBy(Subscription.Name)}}
{{/Invoice}}
```