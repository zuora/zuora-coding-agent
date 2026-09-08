# Merge field syntax for HTML templates

This article describes the merge field syntax you must follow when using HTML templates. 

The merge field syntax is an extension of [Mustache template](https://mustache.github.io/mustache.5.html). A merge field is also a valid Mustache tag.

A merge field is a field you can put into templates to automatically incorporate values from data when a document is generated from the template. In templates, you can define merge fields that are automatically filled with the value when a document is generated.

A merge field used in HTML templates is surrounded by double curly brackets. You can refer to the Mustache Specification for more information about the merge field syntax that Zuora supports in HTML templates. 

When creating new HTML templates under Settings > Billing > Manage Billing Document Configuration > Add New HTML Template, you must use the correct HTML syntax. The syntax name must exactly match the names listed on the KC page. Using an incorrect or misspelled function name will lead to an error. For example, if you use `{{InvoiceItems|Sizes}}` in the HTML template editor instead of the correct Size, the following error will be displayed:

The function 'Sizes' is not supported in HTML Templates. Please try with 'Size' instead. Code: {{InvoiceItems|Sizes}}

Note: Starting 2025.Q2.0.0, all newly created or updated templates will be subject to strict function name validation. Existing templates will continue to function as-is unless modified. However, if an existing template is edited in the future, it must also comply with the correct function naming conventions, otherwise, an error will be triggered.

## Overview

A merge field is a dotted data path consisting of objects and fields enclosed by double curly brackets. For example:

* `{{Invoice.InvoiceNumber}}`: used to incorporate the invoice number of an invoice. 
* `{{Invoice.Account.BillTo.FirstName}}`: used to incorporate the first name of the bill-to-contact associated with an invoice.
You cannot omit the root object when defining merge fields in HTML templates.

* `Invoice` is the root object for invoice templates.
* `CreditMemo` is the root object for credit memo templates.
* `DebitMemo` is the root object for debit memo templates.

When defining merge fields, you can only place objects on the left of the dot (.), while scalar type fields or lists are not allowed. For example, the following merge fields are valid:

* `{{Invoice.Account.Name}}`
* `{{Invoice.Account.BillTo.FirstName}}`
* `{{Invoice.Account.Invoices}}`

IMPORTANT: 
* You can't do `Invoice.InvoiceItems.RatePlanCharge` because `InvoiceItems` is a collection, you have to use a list section to iterate over the invoice items, and access the rate plan charge inside the list section, like: `{{#Invoice.InvoiceItems}} {{RatePlanCharge.ProductRatePlanCharge.ProductRatePlan.Product.Name}} {{/Invoice.InvoiceItems}}`.
* Relative path in the merge field `../` is not supported, Mustache engine can look up the proper contextual object bubbling up to the outmost object.
* Bill-to / sold-to / ship-to contact fields MUST be accessed through the Account: use `{{Invoice.Account.BillTo.FirstName}}`, `{{Invoice.Account.SoldTo.FirstName}}`, `{{Invoice.Account.ShipTo.Address1}}` (and `CreditMemo.Account.BillTo.*` / `DebitMemo.Account.BillTo.*`). Do NOT use the document's own direct contact relationships such as `Invoice.BillToContact.*`, `Invoice.SoldToContact.*`, or `Invoice.ShipToContact.*` (or their `*Snapshot` variants). Those exist in the object model and pass validation, but Zuora does not populate them when the document is rendered, so they produce blank values. Note also that the Account relationship is named `BillTo` (not `BillToContact`); `Invoice.Account.BillToContact` is invalid.

Merge fields are mainly classified into three types: `variables`, `sections`, and `inverted sections`. You can decorate each type of merge fields with different functions to achieve the goal of data transformation.

**Best Practice:** Given the Mustache hierarchical contextual object lookup mechanism, it's better to do:
```
{{#Invoice}}
{{#InvoiceItems}}
...
{{/InvoiceItems}}
{{/Invoice}}
```
rather than:
```
{{#Invoice.InvoiceItems}} ... {{/Invoice.InvoiceItems}}
```
Since if you want to access `{{Account.Currency}}` in the middle, the first option works but the second not, because the outmost contextual objects are `Invoice` and `InvoiceItem` correspondingly. 



### Variables

Variables are the most basic merge fields. A variable type merge field like {{Invoice.InvoiceNumber}} is replaced with a corresponding value according to the data path indicated by the merge field at template rendering time. 

For example, assume that an invoice has the invoice number of INV-0000001, and its balance is 100.00.

If you define the following merge fields in an HTML invoice template, you can see they are replaced with the following values on the rendered invoice:

* `{{Invoice.InvoiceNumber}}` is replaced by INV-0000001.
* `{{Invoice.Balance}}` is replaced by 100.00.

HTML templates support two types of variables:

* Builtin variables

Builtin variables are variables whose names are Zuora business objects and field names. For example, `{{Account.AccountNumber}}`, `{{InvoiceDate}}`, and so on.

* Custom variables

Custom variables are user-defined variables by using the `Cmd_Assign` command. Each custom variable has its own scope. If it is a local variable, it can only be used in the section of its immediate parent object. For example:

```
{{#Invoice}}
{{Cmd_Assign(MainId,Id,False)
……  {{MainId}} is valid here.
{{/Invoice}}

{{#default__customobjects}}
…… {{! MainId is invalid here}}
{{/default__customobjects}}
```

In the preceding example, `MainId` is a local variable that is available within the "Invoice" section, but it is not accessible in the section of `default__customobjects`.

However, if a variable is defined as a global variable, it can be used anywhere in the template. You can use global variables as merge fields, in expressions, and as part of conditional logic in functions. For more information about how to define global variables, see Defining global variables.

To use custom variables, you must define them first. It is recommended to refrain from assigning the name of a standard object or attribute to a new variable as it may lead to unexpected results.

### Sections

You can use sections to render blocks of text one or more times, depending on the value of the key in the current context. 

A section begins with a pound and ends with a slash. That is, `{{#Invoice}}` begins an "Invoice" section while `{{/Invoice}}` ends it.

Inside sections, you can use variable-type merge fields, and can omit the object name of a field.

Sections can be classified into three types: object sections, list sections, and boolean sections.

#### Object sections

If a merge field represents an object, you can use the merge field as an object section. 

For example, Invoice is a single object for invoice templates, you can define it as an object section.

```
{{#Invoice}}
  {{InvoiceNumber}}   # In the context of Invoice, you can directly use InvoiceNumber.
  {{Amount}}
  {{Account.Name}}
{{/Invoice}}
```

You can use object sections to shorten merge fields defined in HTML templates. For example, to simplify the {{Invoice.InvoiceNumber}}  {{Invoice.Balance}}merge fields, you can use the following section instead:
```
{{#Invoice.InvoiceItems}}       # InvoiceItems is a list type attribute of the Invoice object.
ChargeName:  {{ChargeName}}
{{/Invoice.InvoiceItems}}
```

#### List sections

If a merge field represents a list of records, you can use the merge field as a list section. The content inside the section will be rendered and displayed for each record in the list. 

List sections are typically used to build a data table. If a list is empty, no content is displayed on the rendered billing document.

For example, to display the line items of an invoice, you can define the following list section in HTML templates:

```
{{#Invoice.InvoiceItems}}       # InvoiceItems is a list type attribute of the Invoice object.
ChargeName:  {{ChargeName}}
{{/Invoice.InvoiceItems}}
```

Assume that an invoice contains three charge line items as follows:

```json
{
 ....,
   "InvoiceItems": [
       {
           "ChargeName": "C-000001"
       },
       {
           "ChargeName": "C-000002"
       },
       {
           "ChargeName": "C-000003"
       }
   ],
 ...
}
```

If you define the preceding list section in an HTML invoice template, you can see the following information displayed on the rendered invoice:

```
ChargeName: C-000001
ChargeName: C-000002
ChargeName: C-000003
```

#### Boolean sections

In addition to object and list sections, you can also use boolean values as sections.

For example, if an account has the AutoPay option enabled, the following merge fields only display the value of CreditCardMaskNumber for the account.

```
{{#Invoice.Account.AutoPay}}
    Payment Method: {{Invoice.Account.DefaultPaymentMethod.CreditCardMaskNumber}}
{{/Invoice.Account.AutoPay}}
```

#### Inverted sections

You can use inverted sections to render text once based on the inverse value of the merge field. That is, they will be rendered if the object merge field key does not exist, the boolean value is false, or the list is empty. 

For example, if the input InvoiceItems list is empty, you cannot see any invoice items but the No line items. message displayed in the rendering result. If an invoice account does not have the AutoPay option enabled, you can see the Not Auto Pay message displayed in the rendering result. 

```
{{^Invoice.InvoiceItems}}   # If the InvoiceItems list is empty.
No line items.                 
{{/Invoice.InvoiceItems}}

{{^Invoice.Account.AutoPay}}
Not Auto Pay
{{/Invoice.Account.AutoPay}}
 ```

## Decorated merge fields

To transform data, you can apply functions to the data represented by a merge field.

A decorated merge field is a regular merge field, like `{{Invoice.InvoiceItems}}`, decorated with functions. For example:

```
{{Invoice.InvoiceItems|FilterByValue(ChargeAmount,GT,0)|Sum(ChargeAmount)}}
```

A Pipe character ("|") is an operator that passes the previous data as input to its right side function. In the preceding example, it transforms data as follows:

`Invoice.InvoiceItems|FilterByValue(ChargeAmount,GT,0)` filters out all invoice items with zero and negative amounts.

`FilterByValue` is a function applied to the `InvoiceItems` list, and `(ChargeAmount,GT,0)` are the three arguments of the function. The output of the function is all the invoice items with positive amounts.

`Sum` is another function whose input is all the invoice items with positive amounts; it simply sums up all charge amounts of positive invoice items and outputs a total number.

As you can see from the preceding example, you can chain decorator functions as long as the input type matches the function's argument type.

The following image shows an example of decorated merge fields:

For a full list of supported decorator functions, see [Functions used in merge fields](./functions.md) for more information.


## Supported objects and fields
Zuora supports two types of objects when customizing HTML templates.

* Objects related to invoices, credit memos, or debit memos.
* Custom objects.

### Standard Objects

Users have the ability to navigate through invoice/credit memo/debit memo to access all objects and fields in the data schema tree. If an object or field is absent from the data schema tree, it cannot be utilized in the HTML template.

See [Business Objects](./objects.yaml) for object schema and relationship between objects, and also load detailed object metadata via the link.

### Custom Objects
Zuora’s data schema tool provides a comprehensive repository of field values, enabling users to effectively customize document templates. By leveraging fields from various objects, users can personalize PDFs of invoices, credit memos, and debit memos sent to customers, thereby enhancing the document generation process. To know more about creating and accessing data schema, see, Search, and insert Merge Fields.


## Logic control and looping

For more information, see [Logic control and looping](./logic-control.md).

### Functions used in merge fields
For more information about the functions that you can use in HTML templates, see [Functions used in merge fields](./functions.md).

### Expressions
For information on utilizing Expressions in your HTML templates, see [Expressions](./expressions.md).

### Commands
A command is a merge field that is parsed and executed with side effects, for example, to change the value of other objects or create new objects. Commands have no return value, so if a Command merge field is used, the merge field itself shows nothing.

Note: Command is not a section tag, don't add the leading `#` like `{{#Cmd_xxx(...)}}`.

#### Cmd_Assign

The `Cmd_Assign` command takes three arguments. The first one is a variable name, which can only contain alphabet characters, aka, `[0_9a-zA-Z_]`. The second argument is a merge field whose value will be assigned to the variable and the merge field can be decorated. For example, `{{Cmd_Assign(MaxInvoiceAmount,Account.Invoices|Max(Amount),False)}}`.

The third argument is an optional boolean value indicating whether this variable is a global variable; its default value is False, which means the variable is a local variable.

What this command does is to evaluate the right argument if it is a merge field and assign the value to the variable, and then append that variable as a new field of its immediate container object. For example:

```
{{#Invoice}}
{{Cmd_Assign(Inv_id,Id)}}
{{/Invoice}}
```

In the preceding example, a new attribute of `Inv_id` will be appended to the invoice with the value of `Invoice.Id`.

You can also use `Cmd_Assign` in a list section, for example:

```
{{#InvoiceItems|FilterByValue(ProcessingType,EQ,0)}}                            (1)
    {{Cmd_Assign(RegularItemId,Id)}}                                                (2)
    {{ChargeName}} - {{ChargeAmount}} - {{#InvoiceItems|FilterByRef(AppliedToInvoiceItemId,EQ,RegularItemId)}}          (3)
* {{ChargeName}} - {{ChargeAmount}}
    {{/InvoiceItems|FilterByRef(AppliedToInvoiceItemId,EQ,RegularItemId)}}
{{/InvoiceItems|FilterByValue(ProcessingType,EQ,0)}}
```

In the preceding example, line (1) lists all invoice items for non-discount charges. Line (2) appends a new attribute named `RegularItemId` with the value of `InvoiceItem.Id`. Line (3) is to get all the `InvoiceItems`, of which `AppliedToInvoiceItemId` equals to the variable RegularItemId. Because the `RegularItemId` attribute is created only for the non-discount charges, so for discount charges, no such attribute exists. Therefore, the engine will check its outer object, which is the object of the list defined in line (1).

The `Cmd_Assign` command does not support defining variables according to conditions. For one variable, it can have only one definition.

Note that the variable defined by `Cmd_Assign` is only available in scope of its immediate container object, so it cannot be used as a global variable.

#### Cmd_ListToDict

You can use `Cmd_ListToDict` to transform a list of object into a dict object. For example,

```
{{Cmd_ListToDict(default__messageses|FilterByValue(locale__c,EQ,zh_CN),key__c,value__c,Message)}}
  {{#Invoice}}
    {{Message.account_name}}: {{Account.Name}}
    {{Message.invoice_number}}: {{InvoiceNumber}}
  {{/Invoice}}
```

To execute the above command, four parameters are needed.

* A list of object
* A key attribute name
* A value column name
* A New Dict name (to reference this object in the template)

With the above command you can perform a localization similar to as follows, 

```
{{Message.invoice_title}}
   {{Message.account_name}}
```   

The values of `invoice_title` and `account_name` belong to the `key` column.

#### Cmd_Compose and Cmd_Column

The `Cmd_Compose` and `Cmd_Column` helps to create a new table dynamically. To learn more about the dynamic table, you can refer to the source code of the Previous Transaction table. For example,

```
{{#Cmd_Compose(PreviousTransactionsPosted)}}
                {{#Cmd_Column(TransactionType)}}Transaction Type{{/Cmd_Column(TransactionType)}}
                {{#Cmd_Column(TransactionDate)}}Transaction Date{{/Cmd_Column(TransactionDate)}}
                {{#Cmd_Column(TransactionNumber)}}Transaction Number{{/Cmd_Column(TransactionNumber)}}
                {{#Cmd_Column(Description)}}Description{{/Cmd_Column(Description)}}
                {{#Cmd_Column(TransactionAmount)}}Transaction Amount{{/Cmd_Column(TransactionAmount)}}
                {{#Cmd_Column(AccountBalanceImpact)}}Account Balance Impact{{/Cmd_Column(AccountBalanceImpact)}}
                {{#Cmd_Column(TaxAmount)}}Tax Amount{{/Cmd_Column(TaxAmount)}}
                {{#Cmd_Column(AmountWithoutTax)}}Amount Without Tax{{/Cmd_Column(AmountWithoutTax)}}
                {{#Cmd_Column(ReferenceId)}}Payment Reference Id{{/Cmd_Column(ReferenceId)}}
                {{#Cmd_Column(AdjustmentType)}}Adjustment Type{{/Cmd_Column(AdjustmentType)}}
                {{! Payments }}
                {{Account.Invoices|SortBy(PostedDate,DESC)|FilterByValue(Status,EQ,Posted)|FilterByRef(PostedDate,LE,VarPrevDate)|Map("Invoice",InvoiceDate,InvoiceNumber,Comments,Amount,Amount,TaxAmount,AmountWithoutTax,'','')|First(1)}}
                {{Account.Payments|FilterByValue(Status,EQ,Processed)|FilterByRef(CreatedDate,GE,VarPrevDate)|FilterByRef(CreatedDate,LE,VarEndDate2)|Map("Payment",EffectiveDate,PaymentNumber,Comment,Amount,Amount,'','',ReferenceId,'')}}
                {{! Refunds, Refund.Refund.Status=Processed }}
                {{Account.Refunds|FlatMap(RefundInvoicePayments)|FilterByValue(Status,EQ,Processed)|FilterByRef(CreatedDate,GE,VarPrevDate)|FilterByRef(CreatedDate,LE,VarEndDate2)|Map("Refund",RefundDate,RefundNumber,Comment,RefundAmount,RefundAmount,'','','','')}}
                {{! CreditMemo }}
                {{Account.CreditMemoes|FilterByValue(Status,EQ,Posted)|FilterByRef(PostedOn,GE,VarPrevDate)|FilterByRef(PostedOn,LE,VarEndDate2)|Map("CreditMemo",MemoDate,MemoNumber,Comments,TotalAmount,TotalAmount,TaxAmount,TotalAmountWithoutTax,'','')}}
                {{! DebitMemo }}
                {{Account.DebitMemoes|FilterByValue(Status,EQ,Posted)|FilterByRef(PostedOn,GE,VarPrevDate)|FilterByRef(PostedOn,LE,VarEndDate2)|Map("DebitMemo",MemoDate,MemoNumber,Comments,TotalAmount,TotalAmount,TaxAmount,TotalAmountWithoutTax,'','')}}
{{/Cmd_Compose(PreviousTransactionsPosted)}}
```            

#### Defining global variables

You can use the `Cmd_Assign` command to define global variables.

In the following example, the value of the third argument in the `Cmd_Assign` command is `True`, indicating that `VarEntityNumber` and `VarEntityTotalAmount` are defined as global variables. The value of the `EntityNumber__c` merge field is assigned to the `VarEntityNumber` global variable, and the value of the `EntityTotalAmount__c` merge field is assigned to the `VarEntityTotalAmount` global variable.

For example, the following boolean values of variables are True:

```
{{#Invoice.Account.default__legalentities|First(1)}}
{{Cmd_Assign(VarEntityNumber,EntityNumber__c,True)}}
{{Cmd_Assign(VarEntityTotalAmount,EntityTotalAmount__c,True)}}
{{/Invoice.Account.default__legalentities|First(1)}}
```

The rendering result of the preceding global variables can be `VarEntityNumber` and `VarEntityTotalAmount`.

You can use the global variables defined in the preceding command example as merge fields in HTML templates, for example:

```
Entity Number: {{VarEntityNumber}}
Entity Total Amount: {{VarEntityTotalAmount}}
Entity Total Amount: {{VarEntityTotalAmount|Localise}}
```

In addition, you can also use the global variables in functions as part of conditional logic. For example, to display the tax information for the UK entity and countries other than the UK entity, you can use the global variables in the `EqualToVal` function as part of conditional logic in the following section:

```
{{#VarEntityNumber|EqualToVal(100001)}}
Display tax information for UK entity
{{/VarEntityNumber|EqualToVal(100001)}}
 
{{^VarEntityNumber|EqualToVal(100001)}}
Display tax information for countries other than UK entity
{{/VarEntityNumber|EqualToVal(100001)}}
```

You can also use the global variables in expressions. For example, you can use the global variables in the following expression to display the UK tax information:

```
{{#Wp_Eval}}
"{{VarEntityNumber}}" == "100001" ? "show UK tax info" : ""
{{/Wp_Eval}}
```
 
