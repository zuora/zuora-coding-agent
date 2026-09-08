# Expressions

In addition to the merge fields and functions, you can also use expressions in HTML templates. An expression is simply a text input with merge fields and operators, which is evaluated at runtime, and generates text as output.

To use an expression in your template, enclose your expression with the Wp_Eval section. For example, the following expression generates 2.5 as output.

```
{{#Wp_Eval}}
1 + 2 - 0.5
{{/Wp_Eval}}
```

The "Wp" prefix stands for "wrapper" lambda in Mustache. For more information, see the lambda section in the [Mustache Specification](https://mustache.github.io/mustache.5.html) for more information.

You can use merge fields within expressions. For example, to sum up the invoice item charge amount and tax amount, you can use the following expression:

```
{{#Wp_Eval}}
{{ChargeAmount}} + {{TaxAmount}}
{{/Wp_Eval}}
```

The merge fields are replaced with data before the expression is evaluated. If the charge amount is 100 and the tax amount is 10, the expression generates 110 as output.

Decorator functions are also supported in expressions. Like how they work in merge fields, the decorator functions are led and delimited by pipe characters, no whitespace is allowed. For example, you can use the following expressions to round the sum of the charge amount and tax amount in two decimals and format the sum value based on the default locale.

```
{{#Wp_Eval}}
{{ChargeAmount}} + {{TaxAmount}}|Round(2)|Localise
{{/Wp_Eval}}
```

In the preceding example, `{{ChargeAmount}} + {{TaxAmount}}` is the input for `|Round(2)|Localise`. If the charge amount is 100, the tax amount is 10, and the default locale is en_US, the expression generates 110.00 as output.

## Examples

You can use expressions to link different properties to meet business requirements.

### Comparing strings with whitespace characters

You can use expressions to compare strings with whitespace characters. 

You can use the following expression to indicate whether the charge model of a rate plan charge is `Flat Fee Pricing`. If yes, the Is `Flat Fee` message is displayed in the rendered result. If no, the `Not Flat Fee` message is displayed in the rendered result.

```
{{#Wp_Eval}}
"{{RatePlanCharge.ChargeModel}}" == "Flat Fee Pricing" ? "Is Flat Fee" : "Not Flat Fee"
{{/Wp_Eval}}
```

If you want to show bold text for product rate plan charges with the `Per Unit Pricing` charge model and the price in generated billing documents, use the following expression:

{{#Wp_Eval}}
"{{RatePlanCharge.ChargeModel}}" == "Per Unit Pricing" ? `
<b>Per Unit: {{Invoice.Account.Currency|Symbol}} {{UnitPrice|Round(2)|Localise}} Per {{UOM}}</b>
`: '
Flat Fee: {{Invoice.Account.Currency|Symbol}} {{UnitPrice|Round(2)|Localise}}
'{{/Wp_Eval}}<b>Per Unit: {{Invoice.Account.Currency|Symbol}} {{UnitPrice|Round(2)|Localise}} Per {{UOM}}</b>
```

If you want to display different texts for rate plan charges with different charge models in generated billing documents, use the following expression:

```
{{#Wp_Eval}}
"{{RatePlanCharge.ChargeModel}}" == "Flat Fee Pricing" ? "Is Flat Fee" : "{{RatePlanCharge.ChargeModel}}" == "Per Unit Pricing" ? "Per Unit Pricing" : "{{RatePlanCharge.ChargeModel}}" == "Tiered Pricing" ? "Tiered Pricing" : "Other Pricing"
{{/Wp_Eval}}
```

### Mapping state strings to state acronyms

You can use expressions to map state strings to state acronyms. For example, if the state name in a bill-to contact address is New York, you can use the following expression to generate NY as the rendered result:

```
{{#Invoice.Account.BillTo}}
{{#Wp_Eval}}
"{{State}}" == "New York" ? "NY" : "{{State}}" == "California" ? "CA" : "{{State}}" == "Taxas" ? "TX" : ""
{{/Wp_Eval}}
{{/Invoice.Account.BillTo}}
```

### Not displaying blank line when Address2 is empty
If Address2 in a bill-to contact is empty, you can use an expression to not display a blank line for the Address2 line on generated PDF files. To achieve this goal, you can place the following code into the HTML component.

```
{{Name}}<br/>
{{BillTo.Address1}}<br/>
{{#Wp_Eval}}
"{{BillTo.Address2}}" == "" ? "" : "{{BillTo.Address2}}<br/>"
{{/Wp_Eval}}
{{BillTo.City}}, {{BillTo.State}} {{BillTo.PostalCode}}
{{/Invoice.Account}}
```

### Red text for negative charge amounts

To display negative charge amounts in red text on generated PDF files, place the following code into a table column through the Data Table component. ChargeAmount is a field of the InvoiceItem object.

```html
{{#Wp_Eval}}
{{ChargeAmount}} < 10 ? "<span style='color:red;'>" : "<span>"
{{/Wp_Eval}}
{{Invoice.Account.Currency|Symbol}}{{ChargeAmount|Round(2)|Localise}}
</span>
```

### Red text for amount less than 110, calculating from custom fields

To display amounts that are less than 110 in red text on generated PDF files, place the following code into the HTML code editor through the HTML component:

```html
<td style="text-align: right">
<!-- red font for negative amount -->
{{#Wp_Eval}}
{{ActualPrice__c}} * {{ActualQTY__c}} < 110 ? "<span style='color:red;'>" : "<span>"{{/Wp_Eval}}
{{Invoice.Account.Currency|Symbol}}{{#Wp_Eval}}{{ActualPrice__c}} * {{ActualQTY__c}}|Round(2)|Localise
{{/Wp_Eval}}
</span>
</td>
```

### Calculating unit price excluding tax

When you use tax-inclusive products, the standard field UnitPrice is tax inclusive. You can calculate unit price excluding tax.

To achieve this goal, place the following code into a table column through the Data Table component or HTML component.

```
{{Invoice.Account.Currency|Symbol}}{{#Wp_Eval}}{{ChargeAmount}}/{{Quantity}}|Round(2)|Localise{{/Wp_Eval}}
```

### Displaying red text when account is overdue

To display red text on generated PDF files in scenarios where an account is overdue, place the following code into the HTML code editor through the HTML component:

```html
<strong style="color:Red; text-align:right;">
{{#Invoice}}
{{#Wp_Eval}}
{{Balance}} < {{Account.Balance}} ? "Your account is now overdue." : ""
{{/Wp_Eval}}
{{/Invoice}}
</strong>
```

If a customer account is overdue, the Your account is now overdue. message in red is displayed in the rendered result.

### Excluding items based on conditions

You can use expressions to exclude some invoice items but only display the invoice items whose start dates fall into a specific period. For example, you can use the following expression to display the invoice items whose service start date is in January 2021 or December 2021, and then sort the selected invoice items in the following order:

* `ServiceStartDate`: sorts invoice items by service start date in ascending order.
* `ServiceEndDate`: sorts invoice items by service end date in ascending order.
* `ChargeAmount`: sorts invoice items by charge amount in descending order.

```html
{{#InvoiceItems|SortBy(ServiceStartDate,ASC,ServiceEndDate,ASC,ChargeAmount,DESC)}}
{{#Wp_Eval}}
("{{ServiceStartDate}}" < "2021-02-01" or "{{ServiceStartDate}}" >= "2021-12-01") ? "" :
`
<tr>
<td >{{ChargeName}}</td><td >{{ServiceStartDate}}</td><td >{{ServiceEndDate}}</td><td >{{ChargeAmount}}</td>
</tr>
`
{{/Wp_Eval}}
{{/InvoiceItems|SortBy(ServiceStartDate,ASC,ServiceEndDate,ASC,ChargeAmount,DESC)}}
```

## Useful JEXL functions
JEXL functions are used due to its versatility and seamless integration within our system. It allows for dynamic expression evaluation, making it ideal for scripting, rule-based systems, and enhancing flexibility within our applications. 

Internally, our system utilizes the Apache JEXL engine. For more advanced usage, you can refer to the [Apache JEXL Syntax Reference](https://commons.apache.org/proper/commons-jexl/reference/syntax.html).

You can directly call Java methods of the String class. For example:

```
{{#Wp_Eval}}
"hello,world".split(",")[0]
{{/Wp_Eval}}
```

### Method Call

Calls a method of an object. For instance, "hello.world".hashCode() will invoke the hashCode method of the string "hello world". In scenarios involving multiple arguments and overloading, JEXL will strive to identify the most appropriate, non-ambiguous method to call.

Example:

```
{{#Wp_Eval}}
new("java.util.Formatter").format("%013d", {{#Wp_Eval}}"{{Invoice.Status}}" == "Draft" ?
    ({{Account.Balance|Default(0)}} + {{Invoice.Balance}} >= 0 ? ({{Account.Balance}} + {{Invoice.Balance}}) * 10 : 0)
    : ({{Account.Balance|Default(0)}} >= 0 ? {{Account.Balance}} * 10 : 0) * 100|Round(0){{/Wp_Eval}})
{{/Wp_Eval}}
```

In this example, a 13-digit text is generated, with the option to adjust the number of digits using the %013d format specifier. The nested Wp_Eval evaluates the expression within, ensuring the output is an integer. This result becomes the input for the outer `Wp_Eval`, which utilizes the format function to format the number.

### Supported JEXL functions

The following JEXL functions are supported:

* `empty`: Evaluates whether an expression is empty.
* `size`: Determines the size of an expression.
* `new`: Creates a new instance using a fully-qualified class name or class.

## Operators

Merge fields used in HTML templates support a variety of operators.

The following table lists the operators that you can use in HTML templates.

| Operator | Description |
|----------|-------------|
| Boolean and | The usual `&&` operator can be used as well as the word `and`. For example, `cond1 and cond2` and `cond1 && cond2` are equivalent. |
| Boolean or | The usual `||` operator can be used as well as the word `or`. For example, `cond1 or cond2` and `cond1 || cond2` are equivalent. |
| Boolean not | The usual `!` operator can be used as well as the word `not`. For example, `!cond1` and `not cond1` are equivalent. |
| Ternary conditional `?:` | The usual ternary conditional operator `condition ? if_true : if_false` can be used as well as the abbreviation `value ?: if_false`, which returns the value if its evaluation is defined, non-null and non-false. For example, `val1 ? val1 : val2` and `val1 ?: val2` are equivalent.<br><br>**Note:** The condition evaluates to false when it refers to an undefined variable or null. |
| Null coalescing operator `??` | The null coalescing operator returns the result of its first operand if it is defined and is not null.<br><br>When `x` and `y` are null or undefined, `x ?? 'unknown or null x'` evaluates as `'unknown or null x'`, and `y ?? "default"` evaluates as `"default"`.<br><br>When `var x = 42` and `var y = "forty-two"`, `x??"other"` evaluates as `42` and `y??"other"` evaluates as `"forty-two"`.<br><br>**Note:** This operator does not behave like the ternary conditional since it does not coerce the first argument to a boolean to evaluate the condition. When `var x = false` and `var y = 0`, `x??true` evaluates as `false` and `y??1` evaluates as `0`. |
| Equality | The usual `==` operator can be used as well as the abbreviation `eq`. For example, `val1 == val2` and `val1 eq val2` are equivalent.<br><br>`null` is only ever equal to null, that is if you compare null to any non-null value, the result is false. |
| Inequality | The usual `!=` operator can be used as well as the abbreviation `ne`. For example, `val1 != val2` and `val1 ne val2` are equivalent. |
| Less Than | The usual `<` operator can be used as well as the abbreviation `lt`. For example, `val1 < val2` and `val1 lt val2` are equivalent. |
| Less Than Or Equal To | The usual `<=` operator can be used as well as the abbreviation `le`. For example, `val1 <= val2` and `val1 le val2` are equivalent. |
| Greater Than | The usual `>` operator can be used as well as the abbreviation `gt`. For example, `val1 > val2` and `val1 gt val2` are equivalent. |
| Greater Than Or Equal To | The usual `>=` operator can be used as well as the abbreviation `ge`. For example, `val1 >= val2` and `val1 ge val2` are equivalent. |
| Addition | The usual `+` operator is used. For example, `val1 + val2`. |
| Subtraction | The usual `-` operator is used. For example, `val1 - val2`. |
| Multiplication | The usual `*` operator is used. For example, `val1 * val2`. |
| Division | The usual `/` operator is used, or you can use the `div` operator. For example, `val1 / val2` or `val1 div val2`. |
| Modulus (or remainder) | The `%` operator is used. An alternative is the `mod` operator. For example, `5 mod 2` gives 1 and is equivalent to `5 % 2`. |
| Negate | The unary `-` operator is used. It changes the sign of its numeric argument. For example, `-12` or `-(a * b)`. |

## Restrictions and limitations

When using expressions in HTML templates, keep the following restrictions and limitations in mind: 

* Be aware of the data type of each merge field used in expressions.
If you are trying to use a decorator function for a text type input, ensure that the input data is text or has been converted to text. For example, if you want to use the Substr function to decorate the ChargeAmount  numeric field, you have to convert the field to text first. To achieve this goal, you have to enclose the merge field with double quotation marks.

```
{{#Wp_Eval}}
"{{ChargeAmount}}"|Substr(0,2)
{{/Wp_Eval}}
```

* You cannot enclose any HTML tags within the `Wp_Eval` section, because the system treats them as part of the expression and throws validation errors.

* The combined usage of `Wp_Eval` and `Cmd_Assign` is not supported.

* If your expression contains special characters like `>` or `<`, you have to use an HTML component instead of a Text component, since the characters will be escaped.

For example, you want to display a message in red when your customer is overdue. You have to place the following expression into an HTML component, and the HTML style must be outside of the `Wp_Eval` section.

```html
<strong style="color:Red; text-align:right;">
{{#Invoice}}
{{#Wp_Eval}}
  {{Balance}} < {{Account.Balance}} ? "Your account is now overdue." : ""
{{/Wp_Eval}}
{{/Invoice}}
</strong>
```

