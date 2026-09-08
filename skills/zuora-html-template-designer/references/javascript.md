# Use JavaScript in HTML invoice templates

This article demonstrates how to use JavaScript in HTML invoice templates.

The HTML Templates feature provides you the flexibility to design and customize HTML invoice templates by using an online editor. With merge fields and decorator functions, you can easily manipulate data by formatting, filtering, grouping, transforming, and aggregating data. Additionally, you can also use custom cascading style sheets (CSS) to adjust the page layout, look-and-feel, page break, and so on.

However, the HTML Templates feature cannot support all use cases out of the box (OOTB). You can use JavaScript to extend the OOTB functionalities.

## Enable JavaScript for HTML templates

JavaScript is not enabled by default. To enable it, activate a security setting by selecting the Enable JavaScript for HTML templates check box from the Settings tab, after navigating to Billing > Manage Billing Document Configuration. This setting applies to all existing and subsequently created HTML templates. 

Note that when this setting is enabled, existing HTML templates that were previously error-free may be disrupted. New errors require remediation if existing templates are to be used to generate documents. 

## Add JavaScript codes to HTML invoice templates

To add JavaScript codes to your HTML invoice template, perform the following steps:

1. In your HTML invoice template, click the Rows block where you want to configure JavaScript codes.
The Content panel is displayed on the right of the template editor. 

2. In the Content tab, drag and drop the HTML component into the HTML template. 

3. In the HTML template, click the HTML block.
The Content panel is displayed on the right of the template editor.

4. In the HTML section, type JavaScript codes in the HTML code editor.
For example, you can type the following JavaScript codes in the HTML code editor:

```html
<strong id='greeting'></strong>
<script>
  document.getElementById('greeting').innerText = 'Hello World';
</script>
```

5. Click Save to save the configurations.
6. Click Preview to switch to the Preview mode.
7. In the Preview Settings section, select an existing account and one invoice to preview the rendering result. 

You can see the `Hello World` text displayed on the generated invoice PDF file.

## Pass data to your JavaScript code

In the context of templating, JavaScript is not attractive without the ability to manipulate data. To understand how HTML templates pass data to your JavaScript code, it is best practice to understand how JavaScript works in the context of template-based document generation.

```
                       ┌───────────────────────────────────────────┐
                       │       Processing in the background        │
                       │                                           │
        ┌────────────┐ |             ┌──────────────┐   Rendering  │
        │  HTML      │──────────────▶│ Generated    │──────────────┼────▶ PDF files
        │ templates  │ | Data        │   HTML       │   ▲          |
        └────────────┘ |binding.     └──────────────┘   |          │
                ▲      |               ▲                |          │
                │      |               │                │          │
  JavaScript templates |               │                │          |     
                       │               |                │          │
                       │           JavaScript     JavaScript       │
                       │           (binding)       execution       │
                       └───────────────────────────────────────────┘
```

When adding a snippet of JavaScript codes to an HTML template by using an HTML component, you can consider the JavaScript code snippet as a JavaScript template, which is part of the HTML template. The HTML template eventually produces JavaScript codes after the data binding phase.

For example, if you type the following JavaScript codes in the HTML code editor of an HTML invoice template:

```html
<div id='container'></div>
<script>
document.getElementById('container').innerText ="{{Invoice.InvoiceNumber}}";
</script>
```

After data binding, the generated HTML is as follows:

```html
<div id='container'></div>
<script>
document.getElementById('container').innerText ="INV-00000101";
</script>
```

The preceding example is the way that you can pass data to your JavaScript code. It is easier to understand how JavaScript works to consider it as template-based code generation.

With this idea in mind, you can pass complex data to your JavaScript code. For example, you can type the following snippet of JavaScript template codes in an HTML invoice template by using an HTML component:

```html
<label>Recent Total Balance:</label><span id='recentTotal'></span>
<script>
var invoicesOfAccount =[
{{#Invoice.Account.Invoices}}
 {
 "id":"{{Id}}",
 "number":"{{InvoiceNumber}}",
 "balance":{{Balance}},
 "amount":{{Amount}},
 "invoiceDate":"{{InvoiceDate}}"
 },
{{/Invoice.Account.Invoices}}
];
var totalBalanceInLast30Days = invoicesOfAccount
 .filter(invoice=> invoice.invoiceDate >=(new Date(Date.now()-30*24*60*60*1000)).toISOString().substr(0,10))
 .reduce((sum,inv)=> sum + inv.balance,0);
document.getElementById('recentTotal').innerText = totalBalanceInLast30Days;
</script>
```

In the preceding sample JavaScript template, you declare a variable to hold all invoices of an account, filter all the invoices whose InvoiceDate is in the last 30 days, and then add up the balances of the filtered invoices. After data binding, the generated variable declaration is as follows in the generated HTML:

```html
<script>
var invoicesOfAccount = [
  {
    "id": "2c92c8957d5847df017d63f1ef9277a2",
    "number": "INV00000051",
    "balance": 0.0,
    "amount": 8271.0,
    "invoiceDate": "2021-11-27"
  },
  {
    "id": "2c92c8957c12843e017c1512c80a0404",
    "number": "INV00000044",
    "balance": 0.0,
    "amount": 94210.0,
    "invoiceDate": "2021-10-08"
  },
  {
    "id": "2c92c895796534100179683f0f9f0515",
    "number": "INV00000028",
    "balance": 0.0,
    "amount": 108.0,
    "invoiceDate": "2020-06-01"
  },
  {
    "id": "8a90f3207e9bd34c017e9f7beaae0346",
    "number": "INV00000061",
    "balance": 27349.0,
    "amount": 27349.0,
    "invoiceDate": "2022-02-01"
  },
];
...
</script>
```

When previewing the template, you can see the following rendering result displayed on the generated invoice PDF file.

## Common use cases

With the capability to pass data to JavaScript, you can implement a number of use cases that might or might not be supported OOTB. This section describes some common use cases that you might want to implement with JavaScript in HTML invoice templates.

### Configuring barcodes

In HTML invoice templates, you can configure barcodes by using the `Wp_Barcode` merge field. However, currently, this merge field only supports popular barcode types. For more information, see Configure barcodes in HTML invoice templates.

If your business requires a barcode that is not included in the list of supported barcode types, you can either leverage the JavaScript library approach or submit your request in Zuora Community. You can also use JavaScript in HTML invoice templates to generate barcodes including `Swiss QR codes`, use your own fonts for barcode text, and configure QR code styling. For more use cases, see Use JavaScript in your template.

To use JavaScript in HTML invoice templates to generate barcodes, perform the steps documented in Add JavaScript codes to HTML invoice templates. In this use case, you can type the following JavaScript codes in the HTML code editor:

```html
<!-- ① -->
<script type="text/javascript" src="https://cdnjs.cloudflare.com/ajax/libs/bwip-js/3.0.4/bwip-js.min.js"></script>
<!-- ② -->
<canvas id="qrcodeCanvas"></canvas>
<script>
  try {
    // The return value is the canvas element
    let canvas = bwipjs.toCanvas('qrcodeCanvas', {
        bcid:        'qrcode',       // Barcode type
        text:        '{{Invoice.InvoiceNumber}}',    // ③
    });
  } catch (e) {
      // `e` may be a string or Error object
  }
</script>
```

When previewing the template, you can see the following QR code displayed on the generated invoice PDF file.

In the preceding JavaScript code snippet, `bwip-js` is a JavaScript library to generate various barcode images, and it is just used for demonstration purposes in this article. You can use your own JavaScript library to generate barcodes.

Read the following information to understand how data transformation works in the preceding example:

①: Loads the bwip-js library when rendering the HTML.
②: Creates a canvas element to draw the barcode image.
③: Replaces the merge field with a real invoice number.

Keep in mind that the merge field substitution occurs before the HTML rendering, so the qrcode content is replaced with something like INV00000028.
The bwip-js library supports various barcode types. For more information, see the full list of supported BWIPP barcode types and Symbologies Reference.

## Restrictions and limitations

When using JavaScript in HTML invoice templates, keep the following restrictions and limitations in mind:

* JavaScript is executed at the PDF rendering phase, so outgoing requests might significantly slow down PDF file generation, and probably end up with a timeout error.
* If the JavaScript execution process exceeds 30 seconds, a timeout error occurs.
* The endpoint resources for outgoing requests have to be CORS-enabled. Otherwise, the outgoing requests are blocked.
* HTML invoice templates support outgoing requests through JavaScript, but it is best practice to not use it in Production environments because outgoing requests make the document generation process vulnerable. Use it at your discretion.
