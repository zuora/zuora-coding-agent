# Functions used in merge fields

When customizing HTML templates for billing documents, you can decorate merge fields with filter, aggregator, and formatter functions. These functions cannot exist alone. Use them together with a data field, for example:

```
{{Invoice.Amount|Localise}}
```

The `Localise` function must be used with a numeric data field `Invoice.Amount`. A pipe "|" is used between the data field and the decorator function.

---

## Function Index

### Filter Functions (list → filtered list)
| Function | Description |
|----------|-------------|
| `FilterByValue(Field,Op,Value)` | Filter by comparing field to a value |
| `FilterByRef(Field,Op,RefAttr)` | Filter by comparing field to a reference attribute |
| `GroupBy(Field1,Field2,...)` | Group records by field(s), max 6 levels |
| `SortBy(Field,Dir,...)` | Sort by field(s) with ASC/DESC direction |
| `First(N)` | Return first N records |
| `Last(N)` | Return last N records |
| `Skip(N)` | Skip first N records, return rest |
| `Map(Field,...)` | Extract field(s) from each record |
| `FlatMap(ListField)` | Flatten nested lists |
| `Uniq` | Remove duplicate records |
| `DateAdd(Value,DatePart)` | Add interval to date (D/M/Y) |
| `Default(Value)` | Return value if input is null/undefined |
| `Nth(N)` | Return Nth element (negative indexes from end) |

### Aggregator Functions (list → scalar/object)
| Function | Description |
|----------|-------------|
| `Sum(Field)` | Sum numeric field values |
| `Size` | Return count of items in list |
| `Min(Field)` | Return record with minimum field value |
| `Max(Field)` | Return record with maximum field value |
| `IsEmpty` | Return true if list is empty |

### Formatter Functions (scalar → scalar)
| Function | Description |
|----------|-------------|
| `Substr(Begin,End)` | Extract substring from text |
| `Localise(locale)` | Format date/number by locale (e.g., `en_US`, `fr_FR`) |
| `EqualToVal(Value)` | Compare input to value, return boolean |
| `IsBlank` | Check if text is blank |
| `Symbol` | Convert currency code to symbol |
| `Round(Precision,Mode)` | Round number (modes: UP, DOWN, HALF_UP, etc.) |
| `Format(Pattern)` | Format date/datetime with pattern |
| `ConvertTz(Timezone)` | Convert datetime to timezone |
| `Fn_Today()` | Return current date (YYYY-MM-DD) |
| `Concat(Field1,Field2,Sep)` | Merge text with separator |

---

## Supported filter functions
Use filter functions to take in a list and output a list of filtered records.

The following sections list the filter functions used to decorate merge fields when customizing HTML templates for billing documents, including invoices, credit memos, and debit memos.

## FilterByValue function
This function filters input data based on the specified argument fields.

### Syntax

```
FilterByValue(FieldName,Operator,Value)
```

You can decorate the FieldName argument. 

This function supports the following operators: 

* LT: less than
* LE: less than or equal to
* GT: greater than
* GE: greater than or equal to
* EQ: equal to
* NE: not equal to
* IS_NULL: for example,InvoiceItems|FilterByValue(Description,IS_NULL)
* NOT_NULL: for example,InvoiceItems|FilterByValue(Description,NOT_NULL)

### Remarks

You can specify the FieldName argument to be dotted paths, but the first part must be an attribute of the input object. For example, in the InvoiceItems|FilterByValue(RatePlanCharge.ChargeType,EQ,OneTime) function, RatePlanCharge is a valid field of the InvoiceItems object. 

You can quote the Value argument, but the value cannot contain the dot character ".". If the value contains the following characters, you must escape them through URL encoding as follows:

* Whitespace ' ': %20
* Comma ',':  %2C
* Left curly brackets '{': %7B
* Right curly brackets '}': %7D

### Examples

If you want to filter all invoice items by comparing the 0 - 7 substring of their service start date with 2021-01, use the following function:

InvoiceItems|FilterByValue(ServiceStartDate|Substr(0,7),EQ,2021-01)

## FilterByRef function

This function filters input data based on the specified RefAttributeName argument.

### Syntax
```
FilterByRef(FieldName,Operator,RefAttributeName)
```

You can decorate the FieldName argument. 

This function supports the following operators: 

* LT: less than
* LE: less than or equal to
* GT: greater than
* GE: greater than or equal to
* EQ: equal to
* NE: not equal to

### Remarks
If the current object does not have any RefAttributeName property, its outer object in the stack context is used for searching until the property is found.

### Examples

`InvoiceItem` can be the regular charges and the discount charges. As a discount charge, it has an `AppliedToInvoiceItemId` pointing to a regular invoice item. This linkage enables you to show the inline discount by using FilterByRef function together with Cmd_Assign, see the following example:

```
{{#InvoiceItems|FilterByValue(ProcessingType,EQ,0)}}
{{Cmd_Assign(RegularItemId,Id)}}
{{ChargeName}} - {{ChargeAmount}}
{{#InvoiceItems|FilterByRef(AppliedToInvoiceItemId,EQ,RegularItemId)}}
 * {{ChargeName}} - {{ChargeAmount}}
{{/InvoiceItems|FilterByRef(AppliedToInvoiceItemId,EQ,RegularItemId)}}
{{/InvoiceItems|FilterByValue(ProcessingType,EQ,0)}}
```

This example has two list sections. The first one `InvoiceItems|FilterByValue(ProcessingType,EQ,0)` returns all the regular invoice items.

For each regular invoice item, use `Cmd_Assign(RegularItemId,Id)` to give Id an alias `RegularItemId`.

The second list section `InvoiceItems|FilterByRef(AppliedToInvoiceItemId,EQ,RegularItemId)` basically is to filter all the invoice items by the condition `AppliedToInvoiceItemId = RegularItemId`. `AppliedToInvoiceItemId` is an attribute of its input data `InvoiceItems`, and `RegularItemId` is defined in the outer object, also known as the object in the first list section.

## GroupBy function
This function takes in a list and groups the records by the argument fields.

### Syntax

```
GroupBy(FieldName0,FieldName1,FieldName2,...){0..5}
```

### Remarks

This function supports at most six arguments.

The FieldName argument must be a valid attribute of the input list object type. You can specify the FieldName argument to be dotted paths. 

For example, the InvoiceItems|GroupBy(RatePlanCharge.RatePlan.Name,ChargeName) function groups the invoice items by rate plan name first, and then by charge name for the records with the same rate plan name.

### Examples
Assume that an input list is as follows:

```json
[
{
  "ChargeName": "C-000001",
  "ChargeAmount": 10,
  "ServiceStartDate": "2021-01-01"
},
{
  "ChargeName": "C-000001",
  "ChargeAmount": 15,
  "ServiceStartDate": "2021-02-01"
},
{
  "ChargeName": "C-000002",
  "ChargeAmount": 12,
  "ServiceStartDate": "2021-01-01"
},
{
  "ChargeName": "C-000002",
  "ChargeAmount": 8,
  "ServiceStartDate": "2021-03-01"
}
]
```

If you apply the `GroupBy(ChargeName)` function to the input list, it returns the following output in the rendering result:

```json
[
  {
    "ChargeName": "C-000001",
    "_Group": [
        {
            "ChargeName": "C-000001",
            "ChargeAmount": 10,
            "ServiceStartDate": "2021-01-01"
        },
        {
            "ChargeName": "C-000001",
            "ChargeAmount": 15,
            "ServiceStartDate": "2021-02-01"
        }
    ]
  },
  {
    "ChargeName": "C-000002",
    "_Group": [
        {
            "ChargeName": "C-000002",
            "ChargeAmount": 12,
            "ServiceStartDate": "2021-01-01"
        },
        {
            "ChargeName": "C-000002",
            "ChargeAmount": 8,
            "ServiceStartDate": "2021-03-01"
        }
    ]
  }
]
```

The preceding example shows how the input list is transformed. The object in the transformed list consists of two fields only:

GroupBy key field, for example, ChargeName

_Group that is a hard-coded key for GroupBy use cases

If you specify multiple GroupBy fields in the function, the records in _Group is transformed in the same way. For three levels of GroupBy fields, such asItems|GroupBy(A,B,C), the final output example is as follows:

```json
[
{
    "A": "..",
    "_Group": [
        {
            "B": "..",
            "_Group": [
                {
                    "C": "..",
                    "_Group": [
                        {
                            "A": "..",
                            "B": "..",
                            "C": "..",
                            ...
                        }
                    ]
                }
            ]
        }
    ]
}
]
```

## SortBy function
This function sorts input data based on the specified argument fields.

### Syntax

```
SortBy(FieldName,Direction(,FieldName,Direction){0..2})
```

This function supports the following directions: 

- ASC: Digits first → Lowercase letters → Uppercase letters → Alphabetical order from A to Z.  For instance, in the sequence 0123 > 9aAbBcC > zZ. When sorting the list {123 abc, example, Abc, Example, EXAMPLE, abc 123}, the order would be:

* 123 abc
* Abc
* abc 123
* example
* Example
* EXAMPLE

Sample:

| Sample | Previous Sort | Enhanced Sort |
|---|---|---|
|example	| Example Test	| based |
|based | RANDOM | example|
|Example Test | based | Example Test|
|RANDOM	| example | RANDOM|

- DESC: sorting data from the largest to the smallest.

### Remarks
You can specify the FieldName argument to be dotted paths.

This function supports at most three pairs of field names and directions.

### Examples
Assume that you want to show all the charges in the order of service start date, use the following functions:

```
{{#InvoiceItems|SortBy(ServiceStartDate,ASC)}}
{{ChargeName}} - {{ChargeAmount}} - {{ServiceStartDate}}
{{/InvoiceItems|SortBy(ServiceStartDate,ASC)}}
```

## First function
This function returns the first N records of the input list. You can use this function with the SortBy function to define the sorting order.

### Syntax
```
First(N)
```

### Remarks
The value of N must be an integer greater than or equal to 1.

If less than N records exist, this function returns the original list.

### Examples
The InvoiceItems|First(5) function returns the first five invoice items in the rendering result based on the default sorting order.

## Last function
This function returns the last N records of the input list. You can use this function with the SortBy function to define the sorting order.

### Syntax
```
Last(N)
```

### Remarks
The value of N must be an integer greater than or equal to 1.

If less than N records exist, this function returns the original list.

### Examples
The InvoiceItems|Last(5) function returns the last five invoice items in the rendering result based on the default sorting order.

## Skip function
This function skips the processing of N records from the input list, and returns the remaining records after N records are skipped. 

With the Skip function, you can implement advanced use cases like displaying a fixed layout on the first page. For example, you can configure this function to display a fixed number of records, followed by a payment slip at the bottom of the first page. Meanwhile, the remaining records are displayed on the next pages.

### Syntax
```
Skip(N)
```

### Remarks
The value of N must be an integer greater than or equal to 1.

If less than N records exist, this function returns an empty list.

### Examples
You can split an input data list into two parts with the following merge field code. The first part is a fixed-size list, so that they can fit in the first page. The second part can be dynamic.

You can use the following functions to display the first seven invoice items on the first page, followed by a payment skip of seven invoice items at the bottom, and then display the remaining invoice items on the next pages.

```
{{#Invoice.InvoiceItems|First(7)}}
.. show header
{{/Invoice.InvoiceItems|First(7)}}
{{#Invoice.InvoiceItems|Skip(7)
.. for the others.
{{/Invoice.InvoiceItems|Skip(7)
```

## Map function

You can apply a `Map` function to define an element as the input and the element’s attribute as the output, in the format of `item -> item.FieldName`.

### Syntax

```
Map(FieldName|QuotedValue(,FieldName|QuotedValue)*)
```

* The argument can be either a field name or a quoted value, either single or double quoted.
* `FieldName` cannot be a dotted path.
* The `FieldName` data type cannot be a list.  For example, `InvoiceItems|Map(TaxationItems)` is invalid.
* If you specify only one argument, the Map function returns a list of fieldName values.
* If you specify multiple arguments, the Map function returns a list of lists.

### Examples
Assume that an InvoiceItems list is as follows:

```json
[
{
  "ChargeName": "C-000001",
  "ChargeAmount": 10,
  "ServiceStartDate": "2021-01-01"
},
{
  "ChargeName": "C-000001",
  "ChargeAmount": 15,
  "ServiceStartDate": "2021-02-01"
},
{
  "ChargeName": "C-000002",
  "ChargeAmount": 12,
  "ServiceStartDate": "2021-01-01"
},
{
  "ChargeName": "C-000002",
  "ChargeAmount": 8,
  "ServiceStartDate": "2021-03-01"
}
]
```

The `InvoiceItems|Map(ChargeName)` function returns the following value in the rendering result:

```
["C-000001","C-000001","C-000002","C-000002"]
```

The `InvoiceItems|Map(ChargeName,ChargeAmount)` function returns the following value in the rendering result:

```
 [["C-000001", 10],["C-000001",15],["C-000002",12],["C-000002",8]]
```

You can also use quoted values as arguments. For example, the `InvoiceItems|Map(ChargeName,'Charge')` function returns the following value in the rendering result:

```
[["C-000001","Charge"],["C-000001","Charge"],["C-000002","Charge"],["C-000002","Charge"]]
```

## FlatMap function
This function is similar to the Map function, except that FieldName has to be a list type.

### Syntax
```
FlatMap(ListFieldName)
```

### Examples
Assume that an input of this function is as follows:

```json
[
{
    "A": "...",
    "L": [
        {"B": "b1"},{"B": "b2"}
    ]
},
{
    "A": "...",
    "L": [
        {"B": "b3"}
    ]
}
]
```

The `FlatMap(L)` function returns the following output in the rendering result:

```json
[
  {"B": "b1"},
  {"B": "b2"},
  {"B": "b3"}
]
```

## Uniq function

This function filters out the duplicate records in the list.

### Remarks
You can use the Uniq function to dedup the rendering result.

### Examples
An invoice can be generated for multiple subscriptions, which are linked on InvoiceItem according to the object model. Use the following function to get all the subscriptions of this invoice:

`Invoice.InvoiceItems|Map(Subscription)`

But the problem is that the result contains duplicate records, since there are multiple invoice items for the same subscription.

To get a unique list of the subscription, append a Uniq function to the preceding function:

`Invoice.InvoiceItems|Map(Subscription)|Uniq`

## DateAdd function

This function filters an input list by a relative date value, which is calculated by adding a specified time interval to the current date. For example, you can use this function to get previous transactions in the last 30 days or the last year.

### Syntax
```
DateAdd(Value,DatePart)
```

The `DateAdd` function syntax has the following arguments:

| Argument | Description |
|---|---|
| Value | Required. The number of intervals that you want to add to the part of a date specified in the DatePart argument. The argument value is an integer, and can be positive (to get dates in the future) or negative (to get dates in the past). |
| DatePart | Required. The part of the date to which the DateAdd function adds the number of intervals.
The argument value can be any of the following options: D: stands for days, M: stands for months, Y: stands for years |

### Examples

Assume that you want to get payments with the effective date within the past month. To achieve this goal, you can use the following function sample:

```
{{Cmd_Assign(VarTheInvoiceDate,Invoice.InvoiceDate,True)}}
{{Cmd_Assign(VarTheDate,Invoice.InvoiceDate|DateAdd(-1,M),True)}}
{{#Invoice.Account.Payments|FilterByValue(Status,EQ,Processed)|FilterByRef(EffectiveDate,GT,VarTheDate)|FilterByRef(EffectiveDate,LE,VarTheInvoiceDate)}}
{{PaymentNumber}}, {{EffectiveDate}}
{{/Invoice.Account.Payments|FilterByValue(Status,EQ,Processed)|FilterByRef(EffectiveDate,GT,VarTheDate)|FilterByRef(EffectiveDate,LE,VarTheInvoiceDate)}}
```

The preceding function sample returns the following output in the rendered result:

`P-00000020, 2021-03-20 P-00000019, 2021-03-20 P-00000018, 2021-03-14`

## Default function
This function filters out null or blank/undefined records in the list.

### Syntax
```
Default(Value)
```

The Default(Value) function syntax is as follows:

* If the input data of the Default function is either null or undefined, this function returns the value of its argument.
* If the input data of the Default function is neither null nor undefined, this function returns its input data.

### Examples

If you want to look up a custom object by `Account.Locale__c` to implement globalization, you can use the following function example:

```
{{Cmd_ListToDict(default__messages|FilterByRef(locale__c,EQ,Invoice.Account.Locale__c),key__c,value__c,Message)}}
```

The preceding function example uses `FilterByRef(locale__c,EQ,Invoice.Account.Locale__c)`  to dynamically filter custom object records by an account custom field. However, if no account custom field is defined, the preceding function example returns empty in the rendered result.

In this case, you can append a `Default` function that uses a default value `en_US` in case the account custom field is undefined and the `Account.Locale__c` field is empty. The function example can be as follows:

```
{{Cmd_ListToDict(default__messages|FilterByRef(locale__c,EQ,Invoice.Account.Locale__c|Default(en__US)),key__c,value__c,Message)}}
```

If the `Account.Locale__c` field is undefined, the preceding function example returns `en_US` in the rendered result.

## Nth function
This function returns the Nth element of an input list.

### Syntax

```
Nth(number)
```

The `Nth` function syntax has the following arguments:

| Argument | Description |
| number | Required. The value of this argument is an ordinal number that specifies the position of an item in the input list. The argument value is an integer, and can be positive or negative. A positive integer indexes from the beginning of the input list; a negative integer indexes from the end of the input list. For example: `Nth(1)` returns the first item of the input list; `Nth(2)` returns the second item of the input list; `Nth(-1)` returns the last item of the input list; `Nth(-2)` returns the last but one item of the input list. |

### Remarks

If the input list is undefined, this function always returns null in the rendered result. If the index is out of the boundary, this function always returns null instead of throwing errors.

This function can be used to implement `list.size() > n` filter logic. For example, to check if a charge has multiple tiers, we can do:

```html
{{#Invoice.InvoiceItems}}
...
<!-- filter if the charge has multiple tiers. -->
{{#RatePlanCharge.RatePlanChargeTiers|Nth(2)}}
Tier Breakdown:
{{#RatePlanCharge.RatePlanChargeTiers}}
Tier {{Tier}}
{{/RatePlanCharge.RatePlanChargeTiers}}
{{/RatePlanCharge.RatePlanChargeTiers|Nth(2)}}
{{/Invoice.InvoiceItems}}
```

### Examples
If you want to achieve the same goal as one filter option `FromLastInvoice` is used in the Previous Transaction table in Word templates to get the last but one invoice with the transaction date right before the date the current invoice is posted in the list of `Account.Invoices`, you can use the following function in HTML templates:

```
Invoice.Account.Invoices|Nth(-2)
```

This function returns the last but one item of the invoices associated with the corresponding account. 

## Supported aggregator functions

Use aggregator functions to take in a list and return a scalar value or an object.

The following sections list the aggregator functions used to decorate merge fields when customizing HTML templates for billing documents, including invoices, credit memos, and debit memos.

## Sum function
This function adds up the values of FieldName of the object list. 

### Syntax
```
Sum(FieldName)
```

### Remarks
FieldName must be a numeric field.

### Examples
Use the following function to get the total charge amount of all invoice items in the rendering result:

```
InvoiceItems|Sum(ChargeAmount)
```

## Size function
This function returns the size of a list input.

### Remarks
If the input is null, 0 is returned.

### Examples

```
InvoiceItems|Size
```

## Min function

This function returns the minimum record of the input list, compared by FieldName.

This function is the opposite of the `Max(FieldName)` function. 

### Syntax

```
Min(FieldName)
```

### Remarks

`FieldName` must be fields of comparable data types, for example:

* Text
* Number
* Date/DateTime
* Boolean

### Examples

Use the following function to get the oldest invoice item of the `InvoiceItems` object in terms of ServiceStartDate in the rendering result:

```
InvoiceItems|Min(ServiceStartDate)
```

## Max function

This function returns the maximum record of the input, compared by FieldName. 

This function is the opposite of the `Min(FieldName)` function.

### Syntax

```
Max(FieldName)
```

### Examples

Use the following function to get the latest invoice item of the InvoiceItem object in terms of ServiceStartDate in the rendering result:

```
InvoiceItems|Max(ServiceStartDate)
```

## IsEmpty function

This function tells you whether a list is empty. It returns True for an empty list, False for a non-empty list.

### Examples

To check whether an account has any payment, use the following example:

```
Account.Payments|IsEmpty
```

## Supported formatter functions

Use formatter functions to take in a scalar type input and generate a scalar type value as output.

The following sections list the formatter functions used to decorate merge fields when customizing HTML templates for billing documents, including invoices, credit memos, and debit memos.

## Substr function

This function takes in a text type input and returns a text value.

### Syntax

```
Substr(Begin,End)
```

Arguments Begin and End are integers. The value of these arguments must follow the following formula:

```
0 <= Begin < End
```

### Remarks

If the input text length is less than End, the End value is set to the length of the input list.

For example, if you define the function as `Substr(0,10)` but the input text has only six characters, all the six characters are considered as the input data.

## Localise function

The `Localise` function formats input data according to a specified locale. For instance, you can use `Invoice.Balance|Localise(en_US)` to format invoice balances according to US English standards. To display fields or templates in a local language, ensure that you create a new communication profile with the desired locale and associate this profile with the customer account linked to the billing document (e.g., Invoice, Credit Memo, Debit Memo, Summary Statement, and so on). For more information about how to create communication profiles and configure the locale setting, see Communication profiles.

### Syntax

```
Localise(locale_NAME)
```

`localise_NAME` defines a language country code that is composed of two arguments separated by an underscore. For example, fr_CA indicates French Canadian.

* The first argument is a valid ISO Language Code. These codes are the lower-case two-letter codes as defined by ISO-639. 
* The second argument to both constructors is a valid ISO Country Code. These codes are the upper-case two-letter codes as defined by ISO-3166. 

For an example list of locale names, see Supported languages in HTML templates.

### Remarks

This function works only for date, datetime, and numeric fields.

The localise_NAME input parameter is optional. 

If no input parameter is specified, the default locale is determined based on the following order:

* Locale of the Communication Profile
* Locale in the tenant setting

### Examples

You can specify the locale name to override the default locale. The default locale is determined based on the following order:

* Use the locale specified in the communication profile
* Use the tenant locale if the communication profile specifies the locale as DEFAULT LOCALE.

For example, if the default locale is de_DE, the merge field examples and their outputs are as follows:

* `{{Invoice.InvoiceDate|Localise}}`: 16/12/2021
* `{{Invoice.InvoiceDate|Localise(it_IT)}}`: 16.12.2021
* `{{Invoice.CreatedDate|Localise}}`: 16.09.2021 02:26:07+08:00

You can specify the locale name to override the default locale. For example, if the default locale is de_DE, the merge field examples and their outputs are as follows: 

* `{{Amount|Localise}}`: 1,234,567.89
* `{{Amount|Localise(fr_FR)}}`: 1.234.567,89

## EqualToVal function

This function compares the input with the argument value and returns a boolean value so that it can be used as a boolean section.

### Syntax

```
EqualToVal(Value)
```

### Remarks
The input of this function must be a scalar value.

The argument value of the EqualToVal function supports containing whitespaces. You can also use expressions to compare two strings with whitespaces. For more examples of this function, see Logic control and looping. 

Use `EqualToVal(0)` to compare numbers, and it has the same behavior as EqualToVal(0.00).

Use `EqualToVal("0")` to compare strings.

### Examples

```
{{#Account.Status|EqualToVal(Active)}}
Handle Active Account
{{/Account.Status|EqualToVal(Active)}}
```

## IsBlank function
This function checks whether the input text is blank.

### Remarks
To check whether the Description property of the Account object is blank, use the following merge field:

Account.Description|IsBlank

## Symbol function
This function converts a currency code to a currency symbol.

### Syntax
```
Symbol
```

### Supported Currencies
- USD → $
- EUR → €
- GBP → £
- JPY → ¥
- CNY → ¥
- AUD → A$
- CAD → C$
- CHF → CHF
- And many more...

### Examples
```
{{Invoice.Account.Currency|Symbol}} {{Invoice.Balance|Localise}}
```

The output of the example can be displayed as $ 1,000.00.

```html
<!-- Currency symbol alone -->
{{Invoice.Account.Currency|Symbol}}  <!-- USD → $ -->

<!-- Combined with amount (recommended pattern) -->
{{Invoice.Account.Currency|Symbol}}{{Amount|Round(2)|Localise}}
<!-- USD: $1,234.56 -->
<!-- EUR: €1.234,56 -->
<!-- GBP: £1,234.56 -->

<!-- In a table cell -->
<td>{{Invoice.Account.Currency|Symbol}}{{ChargeAmount|Round(2)|Localise}}</td>
```

### Use Cases
- Display currency symbols
- Format monetary amounts
- Multi-currency documents

## Round function
This function is used for number rounding.

### Syntax
```
Round(Precision,RoundingMode)
```

The first argument is an integer between 0 and 10.

The second argument is optional. The default value of the second argument is HALF_UP. This argument has the following available options:

- UP - Round away from zero
- DOWN - Round towards zero
- CEILING - Round towards positive infinity
- FLOOR - Round towards negative infinity
- HALF_UP - Round to nearest, ties away from zero (default)
- HALF_DOWN - Round to nearest, ties towards zero
- HALF_EVEN - Round to nearest, ties to even number (banker's rounding)
- UNNECESSARY

### Examples
You can also use the Round function for padding purposes. If an invoice has the amount of 10.125, the `{{Amount|Round(2)}}` function returns 10.13 in the rendered result, and the `{{Amount|Round(4)}}` function returns 10.1250 in the rendered result.

```html
<!-- Round to 2 decimals (default HALF_UP) -->
{{Amount|Round(2)}}  <!-- 123.456 → 123.46 -->

<!-- Round to integer -->
{{Amount|Round(0)}}  <!-- 123.456 → 123 -->

<!-- Round with specific mode -->
{{Amount|Round(2,UP)}}       <!-- 123.451 → 123.46 -->
{{Amount|Round(2,DOWN)}}     <!-- 123.459 → 123.45 -->
{{Amount|Round(2,CEILING)}}  <!-- 123.451 → 123.46 -->
{{Amount|Round(2,FLOOR)}}    <!-- 123.459 → 123.45 -->

<!-- Chain with localization -->
{{Amount|Round(2)|Localise}}  <!-- 1,234.56 (en_US) -->

<!-- Currency display -->
{{Invoice.Account.Currency|Symbol}}{{Amount|Round(2)|Localise}}
```

### Use Cases
- Format currency (2 decimals)
- Display percentages
- Truncate precision
- Financial calculations

## Format function
This function is used to format the values of date and date time fields with pattern letters.

### Syntax
```
Format(Value)
```

### Remarks
Pattern letters are used to create a formatter. For example, “d MMM yyyy” can serve as pattern letters, and such pattern letters format 2011-12-03 as “3 Dec 2011.”

For more information about supported pattern letters, see Supported date time formats and time zones in HTML templates.

### Common Pattern Symbols
- `yyyy` - 4-digit year (2024)
- `yy` - 2-digit year (24)
- `MM` - 2-digit month (01)
- `MMM` - Short month name (Jan)
- `MMMM` - Full month name (January)
- `dd` - 2-digit day (15)
- `EEEE` - Full day name (Monday)
- `EEE` - Short day name (Mon)
- `HH` - Hour 0-23 (14)
- `hh` - Hour 1-12 (02)
- `mm` - Minute (30)
- `ss` - Second (45)
- `a` - AM/PM marker

### Important Notes
- Input must be a valid date/datetime string
- Pattern is case-sensitive
- Uses request locale for month/day names
- Handles both LocalDate and ZonedDateTime

### Examples
You can use `{{Invoice.CreatedDate|Format(dd.MMMM.yyyy HH:mm:ss a z)}}` to format a date time field as “20.April.2021 04:02:52 AM -07:00.”

The following table lists more formatting examples:

```
{{Invoice.InvoiceDate|Format(dd MMM yyyy)}}	20 Jun 2021
{{Invoice.InvoiceDate|Format(dd MM yyyy)}}	20 06 2021
{{Invoice.InvoiceDate|Format(dd.MM.yyyy)}}	20.06.2021
{{Invoice.InvoiceDate|Format(MM/dd/yyyy)}}	06/20/2021
{{Invoice.InvoiceDate|Format(dd-MMM-yyyy)}}	20-06-2021
{{Invoice.DueDate|Format(dd-MMM-yy)}}	05-Nov-21
{{Invoice.DueDate|Format(dd-MMMM-yyyy)}}	05-November-2021
{{Invoice.DueDate|Format(dd.MMMM.yyyy)}}	05.November.2021
{{Invoice.CreatedDate|Format(dd-MMM-yyyy HH:mm:ss z)}}	20-Apr-2021 04:02:52 -07:00
{{Invoice.InvoiceDate|Format(MMM dd, yyyy)}}	Jun 20, 2021
{{Invoice.InvoiceDate|Format(MMMM dd, yyyy)}}	June 20, 2021
{{Invoice.InvoiceDate|Format(EEEE, MMMM dd, yyyy)}}	Sunday, June 20, 2021
{{Invoice.InvoiceDate|Format(EEE, MMM dd)}}	Sun, Jun 20
{{Invoice.InvoiceDate|Format(yyyy-MM-dd)}}	2021-06-20
{{Invoice.CreatedDate|Format(yyyy-MM-dd HH:mm:ss)}}	2021-04-20 04:02:52
{{Invoice.CreatedDate|Format(hh:mm a)}}	04:02 AM
```

### Use Cases
- Custom date formatting
- Region-specific date formats
- Include time in output
- Formatted date ranges

## ConvertTz function

This function is used to convert the values of date time fields from the tenant default time zone to a specified time zone.

### Syntax
```
ConvertTz(Value)
```

### Remarks
The supported time zone names include short names and long names. For example, the short name “PST” is mapping the time zone “America/Los_Angeles.” The long name “America/Los_Angeles” means that the time zone is “UTC-07:00.”

For more information about supported time zone short names and mapping, see Supported date time formats and time zones in HTML templates.

For more information about supported time zone long names, see Supported date time formats and time zones in HTML templates.

### Examples
You can use `{{Invoice.CreatedDate|ConvertTz(IST)|Format(dd.MMMM.yyyy HH:mm:ss a z)}}` to format a date time field as “20.April.2021 16:32:52 PM IST.” You can also use `{{Invoice.CreatedDate|ConvertTz(AST)|Localise(ar_SA)}}` to format a date time field as “2021-04-20T02:02:52-09:00[America/Anchorage].” The following table lists more formatting examples:

```
{{Invoice.CreatedDate|ConvertTz(IST)}}	2021-04-20T16:32:52+05:30[Asia/Kolkata]
{{Invoice.CreatedDate|ConvertTz(America/Anchorage)}}	2021-04-20T02:02:52-09:00[America/Anchorage]
{{Invoice.CreatedDate|ConvertTz(IST)|Localise}}	2021-04-20T16:32:52+05:30[Asia/Kolkata]
{{Invoice.CreatedDate|ConvertTz(IST)|Format(dd MMM yyyy HH:mm:ss z)}}	20 Apr 2021 16:32:52 IST
{{Invoice.CreatedDate|ConvertTz(AST)|Format(dd MMM yyyy HH:mm:ss z)}}	20 Apr 2021 02:02:52 AST
```

## Fn_Today function

This function returns a date in the current session time zone in the default format: YYYY-MM-DD.

### Syntax
```
Fn_Today()
```

### Remarks
This function works with other functions, for example, `Localise` and `FilterbyRef`.

To localise the current date in the tenant timezone, use `{{Fn_Today()|Localise}}`.
To filter the input data where the invoice date is earlier than the current date in the tenant timezone, use `FilterByRef(InvoiceDate,LT,Fn_Today())`.

### Examples

The current time is August 30, 2022 in the Pacific time Zone (UTC-8) and the language is en_US.

* The formula `{{Fn_Today()}}` has a result of “2022-08-30.”
* The formula `{{Fn_Today()|Localise}}` has a result of “08/30/2022.”

You can use `FilterByRef(InvoiceDate,LT,Fn_Today())` to filter the input data where the invoice date is earlier than August 30, 2022.

## Concat function
This function merges text from multiple strings and separates it by a specified separator string.

### Examples
```
{{#Invoice}}{{Cmd_Assign(VarStr,.|Concat(Account.Name,InvoiceNumber,'-'))}}{{VarStr}}{{/Invoice}}
```

### Remarks
* `.` in `.|Concat(Account.name` is the invoice, and it’s a reference to the contextual object.
* To work, the `Concat` function decorator requires an input. Piping the invoice object `.` to the right side function requires the use of `|`.
