---
name: zuora-html-template-designer
description: Design and generate Zuora invoice, credit memo, and debit memo HTML templates from prompts and pdfs.
argument-hint: <template description or PDF attachment>
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash, Agent, mcp__zuora-mcp__query_objects, mcp__zuora-mcp__manage_document_presentment, mcp__zuora-mcp__ask_zuora]
---

Codex-only path resolution: When an instruction refers to `${CLAUDE_PLUGIN_ROOT}`, treat it as the root of this installed plugin. In Codex, resolve that root as the ancestor directory containing `skills/`, `references/`, and `.codex-plugin/`.

## Input

The user's request: $ARGUMENTS

# HTML Template Designer

This skill designs Zuora HTML Templates for Invoice/CreditMemo/DebitMemo documents.

## Workflow Detection

Detect the request type and route to appropriate workflow:

| Request Type | Detection | Workflow |
|--------------|-----------|----------|
| **PDF-based** | Attachment line: `* [PDF] /tmp/...` | 9-step PDF workflow (see below) |
| **Image-based** | Attachment line: `* [PNG]`, `* [JPG]`, `* [JPEG]`, or `* [WEBP] /tmp/...` | Image workflow (Steps 1 + 3–9; skip PDF conversion) |
| **Word-based** | Attachment line: `* [DOC]` or `* [DOCX] /tmp/...` | Office workflow (Steps 1 + Office→PDF + Step 2 + 3–9) |
| **Text-only** | No file attachment | Direct generation |

## Image Workflow (PNG / JPG / WEBP)

When an image attachment is detected, follow the PDF workflow but **skip Step 2** (`convert_pdf.py`).

1. **Step 1** — Setup folders (same as PDF workflow).
2. **Use the uploaded image path directly** as `png_path` for visual analysis (e.g. `/tmp/.../uploads/abc123.png`).
3. **Steps 3–9** — Same as the PDF workflow: analyze the image with Read, generate HTML, self-check, merge fields, validate.

## Word Workflow (DOC / DOCX)

When a Word attachment is detected:

1. **Step 1** — Setup folders (same as PDF workflow).
2. **Convert Office document to PDF** before PNG conversion:

**Install dependencies first (once per session):**
```bash
pip install -r ${CLAUDE_PLUGIN_ROOT}/skills/zuora-html-template-designer/requirements.txt
```

```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/zuora-html-template-designer/scripts/convert_office.py \
  --input <doc_file_path> \
  --output {session-folder}/uploads/
```

Response:
```json
{
  "success": true,
  "pdf_path": "/tmp/.../uploads/abc123.pdf",
  "source": "docx"
}
```

3. **Step 2** — Run `convert_pdf.py` on `pdf_path` (same as PDF workflow).
4. **Steps 3–9** — Same as the PDF workflow.

---

## CRITICAL: Root Object Rules

**Every merge field MUST trace back to the root object.** This is the #1 cause of validation errors.

| Template Type | Root Object | Example |
|--------------|-------------|---------|
| Invoice | `Invoice` | `{{Invoice.Account.Name}}` |
| CreditMemo | `CreditMemo` | `{{CreditMemo.Account.Name}}` |
| DebitMemo | `DebitMemo` | `{{DebitMemo.Account.Name}}` |

**Two valid approaches:**
1. **Full path**: `{{Invoice.Account.Name}}`
2. **Contextual section**: `{{#Invoice}}{{Account.Name}}{{/Invoice}}`

**WRONG** (will fail validation):
- `{{Account.Name}}` - Missing root object
- `{{InvoiceItems.ChargeName}}` - Missing root object

**CORRECT** equivalents:
- `{{Invoice.Account.Name}}` - Full path from root
- `{{#Invoice.InvoiceItems}}{{ChargeName}}{{/Invoice.InvoiceItems}}` - Inside section

---

## Progress Tracking

**IMPORTANT:** At the start of each workflow, use `TodoWrite` to create a todo list for all steps. Update each todo as you progress (mark in_progress when starting, completed when done). This gives the user visibility into your progress.

---

## Common Pitfalls & Lessons Learned

**Why templates fail user expectations (in order of frequency):**

### 1. Title Case Handling for ALL-CAPS Labels

**Problem:** Users ask for "camel case" on values like `CITY SALES TAX`, but there's no native merge-field function for this. Wrong approaches emerge (CSS-only tricks, unsafe JavaScript hacks).

**Root Cause:** Misunderstanding of "camel case" request (users mean **title case**: `City Sales Tax`). Native Zuora merge-field syntax has no title-case function.

**Solution:** Use a template `<script>` block with a `title-case` CSS class and JavaScript transformation. Requires **Enable JavaScript for HTML templates** in Billing settings. If JS is disabled, fix the value upstream instead.

**Correct approach:**
```html
<style>
  .title-case {
    /* CSS alone cannot capitalize all words; JavaScript is required */
    font-variant: small-caps; /* Optional visual hint while awaiting JS */
  }
</style>

<script>
  function titleCase(str) {
    return str.replace(/\b\w/g, c => c.toUpperCase());
  }
  document.querySelectorAll('.title-case').forEach(el => {
    el.textContent = titleCase(el.textContent);
  });
</script>

<!-- Usage: -->
<span class="title-case">{{Name}}</span>  <!-- Renders: "City Sales Tax" from "CITY SALES TAX" -->
```

**Wrong (do not use):**
- CSS `text-transform: capitalize` alone (only capitalizes first letter per word, but needs lowercase input)
- JavaScript inside `{{#Wp_Eval}}...{{/Wp_Eval}}` (unsafe and undocumented)
- Undocumented Java classes (`WordUtils`, etc.) — not available in Zuora templates

**Prevention:**
- Clarify user intent: ask if they want title case for display (use the script above) or if the data should be fixed upstream
- Always test JS rendering with **Enable JavaScript for HTML templates** enabled
- Document the `title-case` class in template comments so reviewers understand why JS is present

**See also:** [JavaScript guide](./references/javascript.md) for full integration details.

### 2. Typography & Spacing Mismatch (Most Common)

**Problem:** Generated template validates but looks "wrong" - too spacious, wrong font sizes, loose spacing.

**Root Cause:** Using "web-standard" CSS (10-12pt fonts, 1.4+ line-height, generous padding) for enterprise invoices that use "report-system" CSS (8-9pt fonts, 1.15 line-height, tight padding).

**How it happens:**
- Looked at PNG structure (✓) but didn't measure actual typography
- Used "reasonable defaults" instead of matching the source
- Focused on functional (merge fields work) over visual (looks identical)
- Didn't recognize enterprise invoice aesthetic

**Prevention:**
1. **Measure, don't assume**: Count pixels between sections, measure row heights, identify font appearance
2. **Identify document type**: Enterprise (tight/monospace) vs Modern (relaxed/proportional)
3. **Apply correct CSS preset**: See Step 4.5 - use enterprise settings for tight documents
4. **Visual verification**: Side-by-side PNG vs rendered HTML before proceeding to Step 6

**Key indicators of enterprise style:**
- Monospace/typewriter font (Courier New)
- Font size ≤9pt (looks small/dense)
- Line-height ≤1.2 (vertically compressed)
- Table rows very short (≤30px at 300 DPI)
- Minimal whitespace between sections (≤20px gaps)
- Footer text extremely small (6pt, barely readable)

### 2. Footer Overlap and Positioning

**Problem:** Footer overlaps table rows or totals (e.g., last line item hidden behind a "Powered by zuora" bar), or footer alignment is wrong (left/center/right).

**Root Cause:** Failing to reserve physical page space for fixed footers, or choosing `First(N)` too large so runtime line items extend into the footer zone. Page 1 can look correct by accident because natural whitespace at the bottom acts as a buffer; page 2+ breaks when content fills to the edge.

**Dynamic footer reserve rule (apply proactively on every multi-page template):**

First classify the uploaded PDF. Do **not** add a visible footer if the source PDF has no footer. Always reserve the unsafe bottom zone dynamically.

| Source PDF observation | What to generate |
|------------------------|------------------|
| Locked footer is visible | Use all three fixed-footer parts below |
| Footer flows after content | Keep footer in normal flow; do not use fixed positioning |
| No footer is visible | Do not create visible footer text/div; reserve only the platform bottom unsafe zone |

For a visible locked footer, all three footer parts must be present together. Missing any one causes footer overlap on page 2+.

```css
@page {
  margin-bottom: /* at least the explicit footer height */;
}

.page-footer {
  position: fixed;
  bottom: 0;
  height: /* explicit measured height */;
  background: #fff; /* opaque */
}
```

```html
<body>
  <div class="page-footer">...</div>
  <div class="page">...</div>
</body>
```

- `@page` bottom margin must be greater than or equal to the footer height.
- `.page-footer` must be `position: fixed`, anchored to `bottom: 0`, with explicit `height` and opaque `background`.
- The footer div must be a direct child of `<body>` and must appear before `.page`.
- Apply this even if the analyzed PNG page 1 looks fine; overlap usually appears only on continuation pages.
- If no footer is visible in the source PDF, omit `.page-footer` entirely and reserve only `platform_unsafe_zone_in + bottom_safety_gap_in` with `@page margin-bottom`.

**Required matching page-shell rule (prevents giant blank gaps / pushed-down page 2):**

Fixed footers must be paired with a stable page shell. Do not let `.page` blocks float naturally with arbitrary margins after adding `@page` footer reserve.

```css
body {
  margin: 0;
  padding: 0;
}

.page {
  width: 8.5in; /* or 210mm for A4 */
  box-sizing: border-box;
  padding: /* measured page padding from PNG */;
  break-after: page;
  page-break-after: always;
}

.page:last-child {
  break-after: auto;
  page-break-after: auto;
}
```

- Do **not** add large `margin-top`, `padding-top`, or spacer blocks between `.page` elements.
- Page 2+ continuation content must start at the measured top content position, not below the reserved footer area.
- `@page` bottom margin reserves footer space in the print page box; `.page` should not add a second large footer spacer unless measured content requires it.
- Use `break-after` / `page-break-after` for page boundaries. Avoid combining `break-before` on every page with large vertical margins that create visible gaps.

**Reserved content boundary rule (prevents footer/platform line crossing the last row):**

The bottom reserve is not only visual whitespace; it is a hard boundary for table rows, totals, notes, and payment slips.

- Define the printable content bottom as: `page_height - bottom_reserved_zone`.
- If a visible footer exists: `bottom_reserved_zone = measured_footer_height + bottom_offset + platform_unsafe_zone + bottom_safety_gap`.
- If no visible footer exists: `bottom_reserved_zone = platform_unsafe_zone + bottom_safety_gap`.
- Use a `bottom_safety_gap` of at least `0.12in` (or larger if the PNG shows more space above the footer).
- No table row, total, border, or text baseline may enter this reserved band.
- If the last visible row would cross this band, reduce `First(N)` / `First(M)` by one or move that row to the next page.
- This applies even when only the small `Powered by zuora` line appears; that line still occupies reserved physical space at render time.

**Prevention (measure from the uploaded PNG — values differ per PDF):**
1. **Classify footer mode per page:** locked-to-page-bottom vs flows-after-content (see Step 3.2 FOOTER and Step 4.2.2).
2. **Measure** footer band height, bottom offset, and gap from last content — convert px at 300 DPI to inches (`px / 300`).
3. **Locked footers:** use the fixed-footer rule above. Do not rely on `position: absolute` inside `.page` for multi-page PDFs.
4. **Flow footers:** keep footer in normal document flow with measured `margin-top`; do NOT use `position: absolute`.
5. **Zuora platform reserve:** add `0.35in` bottom clearance as a platform unsafe zone even when the source PDF has no footer — Zuora can inject a "Powered by zuora" bar at render time.
6. **`First(N)`:** count rows above the reserved footer band on page 1, then subtract 1–2 safety rows for runtime invoices with longer descriptions than the sample PDF.

### 3. Hardcoded Data Instead of Merge Fields

**Problem:** Static values (invoice numbers, dates, amounts) instead of dynamic Zuora fields.

**Root Cause:** Copied exact text from PNG without transforming to merge fields.

**Prevention:**
- Step 4: Use placeholders `[Invoice Number]`, `[Customer Name]`
- Step 7: Replace ALL placeholders with validated Zuora merge fields
- Step 8: Validation will fail if any hardcoded data remains in loops

### 4. Hyperlinks Without Extractable URLs

**Problem:** PDF contains text styled as a hyperlink (blue, underlined), but the actual destination URL cannot be extracted from the PDF — only the visible display text is available. The agent generates `<a href="the-display-text">` or `<a href="#">`, which either navigates to a nonsense URL or causes confusing UX.

**Root Cause:** PDF hyperlink annotations carry an invisible URL alongside the visible text. A PNG rendering captures only the visual appearance (blue/underlined text), not the hidden URL. The agent sees styled text but has no URL to use.

**Fix: render as non-navigating styled text.** Use one of these two patterns depending on context:

```html
<!-- Option A: span styled to look like a link (STRONGLY PREFERRED for invoice templates) -->
<span style="color: #0066cc; text-decoration: underline;">Visible Link Text</span>

<!-- Option B: anchor that does not navigate — ONLY when an <a> tag is semantically required -->
<a href="javascript:void(0)" style="color: #0066cc; text-decoration: underline; pointer-events: none; cursor: default;">Visible Link Text</a>
```

**Decision rule:**
- **Default to Option A** (`<span>`) for ALL hyperlink-styled text where no full URL was visible in the PNG.
- Option B is only for cases where the surrounding markup strictly requires an `<a>` element.
- **Email addresses:** if the actual email address is visible as plain text in the PNG, use `<a href="mailto:user@example.com">user@example.com</a>` — the preview handles `mailto:` correctly (opens the OS mail client). If only styled-as-link text is visible but no email address can be read, fall back to Option A (`<span>`).
- **Never** use `href="#"` — in a sandboxed iframe this reloads/blanks the preview window entirely.
- **Never** use the display text as an `href` value (e.g., `href="www.example.com"` without `https://`).
- **Never** leave a bare `<a href="#">` under any circumstances.
- If a full URL was explicitly visible as plain text in the PNG (e.g., `https://example.com`), use a real `<a href="https://example.com">` — the preview will open it in a new tab safely.
- Add an HTML comment documenting what was observed: `<!-- LINK: display text "[...]", URL not extractable from PDF -->`

**Prevention:** During Step 3.2 Text Extraction, note any underlined/colored text that may be a hyperlink. During Step 4.3 HTML generation, apply this rule immediately — do not emit a navigating `<a>` tag unless the full URL was explicitly visible in the PNG (e.g., `https://example.com` written out as plain text).

### 5. Invalid Merge Field Paths

**Problem:** Template fails validation with "invalid merge field" errors.

**Root Cause:** Using fields that don't exist (e.g., `RatePlanName` instead of `SKU`).

**Prevention:**
- Step 7: Query metadata BEFORE adding merge fields
- Validate each field path by calling `mcp__zuora-mcp__query_objects` with `{ "objectType": "Invoice", "help": "fields" }` and checking the returned field list
- Don't guess field names - look them up

---

## PDF Workflow (9 Steps with Metadata Integration)

When a PDF attachment is detected, follow this complete workflow from start to finish.

**CRITICAL: You MUST complete ALL 9 steps. Do NOT stop after generating plain HTML.**

**Key Enhancement:** Step 7 now includes querying live Zuora metadata to ensure accurate field mapping and discover custom fields specific to the tenant.

### Non-Negotiable Text Preservation Rule

**Do NOT drop visible text from the source PNG unless it is intentionally replaced by a validated merge field. This includes footer/end-of-page text, notes, legal disclaimers, remittance instructions, and payment/contact lines.**

Before generating final output, keep and enforce these three inventories:

1. **Observed Text Inventory** (from PNG): all visible labels, literals, headers, footers, notes, and table text.
2. **Dynamic Replacement Inventory**: every literal intentionally replaced with a merge field, with the exact replacement path.
3. **Must-Retain Static Inventory**: visible text that must remain literal in HTML/template output.

If a visible literal is missing from output and is not in the Dynamic Replacement Inventory, treat it as a defect and fix it before continuing.

### Step 1: Detect PDF and Setup Folders

Look for attachment format in the prompt:

```text
Attachments:
* [PDF] /tmp/html-template-designer/{session-id}/uploads/abc123.pdf (invoice.pdf, 100KB)
```

**Extract session folder from path:**
- PDF path: `/tmp/html-template-designer/550e8400-e29b-41d4/uploads/abc123.pdf`
- Session folder: `/tmp/html-template-designer/550e8400-e29b-41d4/`
- Pattern: `session_folder = parent(parent(pdf_path))`

**Create required folders:**
```bash
mkdir -p {session-folder}/html {session-folder}/templates
```

### Step 2: Convert PDF to a single combined PNG

Convert the PDF pages to a single combined PNG image for visual analysis.
For PDFs with more than 3 pages, only the **first, second-to-last, and last pages** are
included and stacked vertically — this keeps memory and token cost bounded for any PDF.

**Install dependencies first (once per session):**
```bash
pip install -r ${CLAUDE_PLUGIN_ROOT}/skills/zuora-html-template-designer/requirements.txt
```

```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/zuora-html-template-designer/scripts/convert_pdf.py \
  --input <pdf_file_path> \
  --output {session-folder}/uploads/
```

**Response format:**
```json
{
  "success": true,
  "png_path": "/tmp/.../uploads/abc123.pdf.png",
  "pages_used": [1, 2, 3],
  "pages": 3
}
```

For a 10-page PDF:
```json
{
  "success": true,
  "png_path": "/tmp/.../uploads/abc123.pdf.png",
  "pages_used": [1, 9, 10],
  "pages": 10
}
```

- `png_path`   — single combined PNG (always `{pdf}.png`).
- `pages_used` — 1-indexed list of source pages included in the combined PNG.
- `pages`      — total pages in the source PDF.

**Security checks performed automatically by `convert_pdf.py`:**
- PDF format validation via `validate_pdf()` (no encryption, polyglot detection, forbidden features)
- File size validation (max 4MB) is enforced at upload time before the agent runs
- Any page count accepted; conversion selects at most 3 representative pages

### Step 3: Analyze the combined PNG (DETAILED OBSERVATION)

**STOP. Read the combined PNG carefully. Write down your observations BEFORE generating any HTML.**

#### 3.0 Understand the combined PNG structure

The PNG at `png_path` may contain multiple source-PDF pages **stacked vertically**.
Pages are separated by a **thin red band** labelled `── PAGE N of TOTAL ──`.

- If there is no red separator, the PDF was a single page — treat it as one page.
- If you see red separators, each section between them (and before the first / after the last) is a separate source page.
- The `pages_used` field in the Step 2 response tells you exactly which page numbers are shown
  (e.g. `[1, 9, 10]` for a 10-page PDF). Pages not listed were omitted (they are continuation
  pages whose content follows the same pattern as the visible pages).

**Build a Page Map** before generating HTML:

```
PAGE MAP (example for pages_used=[1, 9, 10] from a 10-page PDF):
- Section 1 (source page 1):  header, company info, invoice details, line items rows 1-N
- Section 2 (source page 9):  continuation line items rows N+1-M (second-to-last page)
- Section 3 (source page 10): totals, footer, payment slip
```

You will reference this map in Step 4 to assign content to the correct page `<div>`.

You MUST document answers to ALL of the questions below for EACH visible section.

#### 3.1 Extract Exact Colors

**CRITICAL: Extract precise hex colors from the PNG instead of using generic defaults.**

Run the color extraction script on the combined PNG (colors are consistent across pages):

```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/zuora-html-template-designer/scripts/extract_colors.py --image {session-folder}/uploads/*.png --output {session-folder}/colors.json --verbose
```

**Color Analysis Results:**
Read the generated colors.json file and document the exact hex colors found:

```
EXTRACTED COLORS:
- Header title color: ___
- Company info text color: ___  
- Invoice details text color: ___
- Table header background: ___
- Table header text: ___
- Table data text: ___
- Labels color: ___
- Values color: ___
- Border colors: ___

RECOMMENDED CSS:
.header-title { color: ___; }
.company-info { color: ___; }
.invoice-details { color: ___; }
.table-header { background: ___; color: ___; }
.table-data { color: ___; }
.field-label { color: ___; }
.field-value { color: ___; }
```

**IMPORTANT: Use ONLY the extracted hex colors in your HTML/CSS. Do NOT use generic colors like #000, #333, #f0f0f0.**

#### 3.2 Layout Questions (write your answers)

```
HEADER:
- Background color (describe): ___
- Title text ("Invoice", etc.): ___
- Logo present? (yes/no): ___
- Logo position (left/center/right): ___
- Logo approximate dimensions (width x height in px on PNG): ___
- Logo shape/style (square, wide rectangle, circular, text-only wordmark, etc.): ___
- Logo dominant colors (describe): ___
- Logo includes address below it? (yes/no): ___
- Does the header band contain anything other than logo and doc-type label? (if yes, note what): ___

COMPANY INFO BLOCK (separate from header):
- Company name present? (yes/no): ___
- Company address present? (yes/no): ___
- Position on page (below header, left/right/center): ___

INVOICE DETAILS BLOCK (separate from header):
- List ALL invoice detail fields (number, date, due date, etc.):
  1. ___
  2. ___
  (continue...)
- Position on page (below header, left/right): ___

LEFT COLUMN:
- How many fields total: ___
- Are labels and values on SAME LINE or SEPARATE LINES: ___
- Label color (use extracted hex): ___
- Value color (use extracted hex): ___
- Is there indentation for multi-line values: ___
- List ALL field labels in order:
  1. ___
  2. ___
  3. ___
  (continue...)

RIGHT COLUMN:
- Is text LEFT-aligned or RIGHT-aligned: ___
- How many fields total: ___
- Are there section headers (italic text): ___
- List ALL field labels in order:
  1. ___
  2. ___
  (continue...)

TABLE:
- Number of columns: ___
- Column header names (exact text):
  1. ___
  2. ___
  (continue...)
- Column width proportions (e.g., 40% / 15% / 15% / 15% / 15%): ___
- Column text alignment per column (left/center/right):
  1. ___
  2. ___
  (continue...)
- Header background color (use extracted hex): ___
- Header text color (use extracted hex): ___
- Header font size and weight: ___
- Header text transform (uppercase/normal): ___
- Row borders: horizontal only / full grid / none: ___
- Border color and style (e.g., 1px solid #ddd): ___
- Cell vertical padding (tight ~4px / normal ~8px / spacious ~12px): ___
- Cell horizontal padding: ___
- Data row background color (white / uniform color / alternating→list colors): ___
- How many data rows: ___
- Does first column have sub-text (like "Quantity: 1"): ___
- Summary/subtotal rows at bottom? (yes/no): ___
- Summary row styling (bold? background color? top border?): ___
- Are numeric columns right-aligned? (yes/no): ___
- Currency formatting (symbol before/after, decimal places): ___

FOOTER (record separately for EACH page section in the combined PNG):
- Which sections have a footer band? (section 1 / section 2 / all / none): ___
- Footer mode per section:
  - **locked** — footer at fixed distance from physical page bottom; white gap above footer when content is short
  - **flow** — footer sits directly below last content; gap to footer stays constant as content grows
  - **none** — no footer text/band visible; reserve only platform unsafe zone + safety gap
- Footer text alignment (left / center / right / none): ___
- Footer font size (pt, or none): ___
- Footer band height at 300 DPI (px, or 0 if none): ___ → ___ in (px / 300)
- Footer bottom offset from page edge at 300 DPI (px, or 0 if none): ___ → ___ in (px / 300)
- Gap from last content row to footer top/reserved zone at 300 DPI (px): ___ → ___ in
- Number of footer text lines (0 if none): ___
- Computed bottom reserve for this section:
  locked = `footer_band_height_in + bottom_offset_in + 0.35in platform + safety_gap`
  none = `0.35in platform + safety_gap`
  selected reserve = ___ in
- Line items counted above bottom reserved zone on page 1 (for `First(N)`): ___ → use N = count minus 1 or 2 safety rows = ___

DATE & NUMBER FORMATS (observe from PDF values):
- Date format pattern(s) used (e.g., "Jun 20, 2021" → MMM dd, yyyy / "06/20/2021" → MM/dd/yyyy / "20-Jun-2021" → dd-MMM-yyyy): ___
- Are multiple date formats used? (yes/no, list each): ___
- Number decimal places for amounts (e.g., 2 decimals → 1,234.56): ___
- Number decimal places for quantities (e.g., 0 or 1): ___
- Number decimal places for unit prices (e.g., 2 or 4): ___
- Number thousands separator used? (comma, period, space, none): ___
```

#### 3.2 Text Extraction (write down EXACT text)

**Copy every piece of text you see in the PNG:**

```
Header title: ___
Company name: ___
Company address: ___

Field 1 label: ___  |  Field 1 value: ___
Field 2 label: ___  |  Field 2 value: ___
(continue for ALL fields...)

Table row 1, col 1: ___
Table row 1, col 2: ___
(continue for ALL cells...)

Footer/end-of-page line 1: ___
Footer/end-of-page line 2: ___
(continue for ALL footer/legal/remittance text...)
```

**WARNING: Do NOT fabricate or guess any text. If you can't read it clearly, write "[UNCLEAR]".**

#### 3.3 Classify Text: Static vs Dynamic (MANDATORY)

After extracting text, classify each extracted item into one of these buckets:

- **Static literal** (must remain as literal text in final template)
- **Dynamic value** (must be replaced with merge field later)
- **Unclear** (keep literal placeholder and flag for review; do not silently drop)

Create this table before Step 4:

| Source Text | Classification | Planned Output |
|-------------|----------------|----------------|
| Invoice Number: | Static literal | Keep as "Invoice Number:" |
| INV-001234 | Dynamic value | `{{Invoice.InvoiceNumber}}` |
| Terms and Conditions | Static literal | Keep literal |

**Rule:** Section labels, headers, instructional text, legal text, and table header labels are usually static literals and must remain unless explicitly requested otherwise.

### Step 4: Generate HTML

**Keep the PNG visible. Generate HTML directly from what you see.**

#### 4.1 Document Structure

Start with proper print-ready structure:

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    @page {
      size: letter; /* or A4 */
      margin: 0;
    }
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }
    body {
      font-family: Arial, Helvetica, sans-serif;
      font-size: 10pt;
      line-height: 1.2;
      color: #000;
      background: #fff;
    }
    .page {
      width: 8.5in;
      padding: /* exact margins from PNG */;
      position: relative;
      /* Locked footers reserve space with @page bottom margin + fixed .page-footer (see 4.2.2) */
      /* DO NOT use min-height: 11in - causes extra blank pages */
    }
  </style>
</head>
<body>
  <div class="page">
    <!-- content here -->
  </div>
</body>
</html>
```

#### 4.2 Div-Based Block Layout (MANDATORY)

**Every distinct horizontal region must be its own `<div>`. Every group of side-by-side columns must be wrapped in a flexbox or grid container `<div>`.** This ensures the HTML mirrors the PDF's spatial arrangement precisely.

**Rules for div placement:**

1. **One `<div>` per visual block** — header, info row, table section, totals row, footer are each their own block-level `<div>`.
2. **Side-by-side blocks → flexbox row** — whenever the PDF shows two or more columns next to each other, wrap them in a `<div style="display:flex;">` (or CSS grid) parent, with one child `<div>` per column.
3. **Stacked blocks → block flow** — when blocks appear top-to-bottom, let them be normal block `<div>`s; do NOT float or use flex unnecessarily.
4. **Vertical spacing** — use `margin-bottom` or `padding` on the block `<div>` to match the gap between sections as observed in the PNG.
5. **Horizontal alignment** — set `justify-content` (flex) or `text-align` (inner div) to match whether content is left-, center-, or right-aligned within each block.
6. **Width control** — set explicit `width` or `flex-basis` on column divs to match proportional widths observed in the PDF (e.g., left column 50%, right column 50%).

**Canonical div patterns:**

```html
<!-- Full-width block -->
<div class="section-block">
  ...
</div>

<!-- Two-column row (left + right) -->
<div style="display:flex; justify-content:space-between; align-items:flex-start;">
  <div style="width:50%;">
    <!-- left column content -->
  </div>
  <div style="width:45%; text-align:right;">
    <!-- right column content -->
  </div>
</div>

<!-- Three-column row -->
<div style="display:flex; gap:1em;">
  <div style="flex:1;"><!-- col 1 --></div>
  <div style="flex:1;"><!-- col 2 --></div>
  <div style="flex:1;"><!-- col 3 --></div>
</div>
```

#### 4.2.1 Pagination Fidelity Rules (CRITICAL FOR MULTI-PAGE PDFs)

Follow these rules when the PDF has more than one page.

**Page structure — one wrapper div per source page:**

```html
<div class="page page-1">
  <!-- all content from source PDF page 1 -->
</div>
<div class="page page-2" style="break-before:page; page-break-before:always;">
  <!-- all content from source PDF page 2 -->
</div>
<div class="page page-3" style="break-before:page; page-break-before:always;">
  <!-- all content from source PDF page 3 -->
</div>
```

**Rules:**
1. **One `.page` div per source PDF page.** Use the Page Map you built in Step 3.0 to decide what belongs in each.
2. **Page break CSS:** add `break-before:page; page-break-before:always;` (both for broad renderer support) to every `.page` div except the first.
3. **Never use `min-height:11in`.** Let content height determine the page height. Fixed height causes blank gaps when there is less content than the page height.
4. **Never duplicate headers.** Repeat a minimal "continuation header" (e.g., `<tr class="header-row">` inside a `<thead>`) only if the source PDF shows the table heading on each page. Do NOT repeat the full logo+company block on every page.

**Line items spanning multiple pages — use `First(N)` / `Skip(N)`:**

When a data table continues across pages, split the repeating section using Zuora merge functions so exactly the right rows appear on each page:

```html
<!-- Page 1 — first N rows (where N = rows counted in page 1 PNG) -->
{{#Invoice.InvoiceItems.First(N)}}
<tr>
  <td>{{InvoiceItem.ServiceStartDate}}</td>
  <td>{{InvoiceItem.Description}}</td>
  <td>{{InvoiceItem.ChargeAmount}}</td>
</tr>
{{/Invoice.InvoiceItems.First(N)}}

<!-- Page 2+ — rows after the first N -->
{{#Invoice.InvoiceItems.Skip(N)}}
<tr>
  <td>{{InvoiceItem.ServiceStartDate}}</td>
  <td>{{InvoiceItem.Description}}</td>
  <td>{{InvoiceItem.ChargeAmount}}</td>
</tr>
{{/Invoice.InvoiceItems.Skip(N)}}
```

- Count rows visible **above the footer band** on page 1 of the PNG — not all rows on the page.
- Set `N` = that count **minus 1 or 2 safety rows** so runtime invoices with longer descriptions than the sample PDF do not overflow into the footer zone.
- If page 2 also has a table that continues onto page 3, use `Skip(N).First(M)` for page 2 and `Skip(N+M)` for page 3.
- Table headers (`<thead>`) inside continuation pages should use the same column widths and styling so the columns align visually.

**Static continuation content (no merge fields):** place it verbatim in the appropriate page div.

#### 4.2.2 Footer Layout Rules (CRITICAL — prevents overlap)

Footers MUST NOT overlap table rows, totals, or payment slips. All footer dimensions come from Step 3.2 measurements for **this specific PDF** — never reuse one global footer size across uploads.

**Step A — Classify footer mode (per page section):**

| PNG observation | Mode | CSS approach |
|-----------------|------|--------------|
| Footer at fixed distance from physical page bottom; white gap between last content and footer when content is short | **locked** | `@page` bottom margin reserve + fixed `.page-footer` direct child of `<body>` |
| Footer immediately follows last content; gap stays constant as content grows | **flow** | Normal block flow; measured `margin-top`; NO `position: absolute` |
| No footer text/band visible | **none** | No visible footer element; reserve only platform unsafe zone + safety gap |

**Step B — Compute bottom reserve space dynamically (per page section):**

At 300 DPI: `inches = pixels / 300`

```
footer_band_height_in = footer height px / 300
bottom_offset_in      = footer bottom-to-page-edge px / 300
zuora_platform_in     = 0.35   /* platform unsafe zone — reserve even when no footer is visible */
bottom_safety_gap_in  = max(measured gap above footer, 0.12)
locked_footer_reserve_in = footer_band_height_in + bottom_offset_in + zuora_platform_in + bottom_safety_gap_in
no_footer_reserve_in     = zuora_platform_in + bottom_safety_gap_in
```

Page 1 and Page 2 often have different values — use each section's own measurements.

**Hard boundary:** the content area ends at the top of the chosen reserve (`locked_footer_reserve_in`, flow footer gap, or `no_footer_reserve_in`). No row border, row text, total, note, or payment slip can cross into this band. If content crosses it, reduce `First(N)` / `First(M)` before changing the footer CSS.

**Step C — Locked mode CSS/HTML (only when a visible locked footer exists):**

If the source PDF has a visible locked footer, all three parts must be present together. Missing any one causes overlap on page 2+.

```css
@page {
  size: letter; /* or A4 */
  margin: 0 0 /* locked_footer_reserve_in */ 0;
}

.page-footer {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: /* locked_footer_reserve_in */;
  width: 100%;
  background: #fff; /* opaque so rows never show through */
  text-align: /* left | center | right from PNG */;
  font-size: /* measured pt */;
  line-height: /* from PNG */;
}
```

```html
<body>
  <div class="page-footer">...</div>
  <div class="page page-1">...</div>
  <div class="page page-2">...</div>
</body>
```

- `@page` bottom margin must be greater than or equal to `.page-footer` height.
- `.page-footer` must be fixed at `bottom: 0` with explicit height and opaque background.
- `.page-footer` must be a direct child of `<body>` and must appear before `.page`.
- Apply proactively even if page 1 looks fine; page 2+ has no accidental whitespace buffer.

**Step C.0 — No visible footer mode:**

If Step A classifies the page as `none`, do not create `.page-footer` or footer text. Still reserve the platform unsafe bottom zone:

```css
@page {
  size: letter; /* or A4 */
  margin: 0 0 /* no_footer_reserve_in */ 0;
}
```

Keep the same stable `.page` shell from Step C.1, but do not add footer markup.

**Step C.1 — Required page shell with any bottom reserve:**

The bottom reserve (locked footer, flow footer clearance, or no-footer platform unsafe zone) must not push continuation pages down or create huge blank gaps between pages. Pair it with a stable page shell:

```css
body {
  margin: 0;
  padding: 0;
}

.page {
  width: 8.5in; /* or A4 width */
  box-sizing: border-box;
  padding: /* measured page padding from PNG */;
  break-after: page;
  page-break-after: always;
}

.page:last-child {
  break-after: auto;
  page-break-after: auto;
}
```

Rules:
- Do NOT add large `margin-top`, `padding-top`, or spacer blocks between `.page` elements.
- Page 2+ continuation tables must start at the measured top content position.
- Do NOT duplicate footer reserve by adding both a large `@page` bottom margin and a large `.page` bottom spacer.
- Use either measured page padding or measured content offsets, but keep every `.page` using the same top shell unless the PNG clearly shows a different continuation-page top offset.
- Keep a clear bottom safety gap between the final row/total border and the reserved bottom zone; if the final row touches or crosses that zone, move it to the next page.

**Step D — Flow mode CSS:**

```css
.footer {
  margin-top: /* measured gap from last content to footer, in inches */;
  text-align: /* from PNG */;
  font-size: /* measured pt */;
  /* NO position: absolute */
}
```

**CRITICAL rules:**
1. NEVER use `position: absolute` for locked footers in multi-page templates.
2. NEVER omit the `@page` bottom reserve for the chosen footer mode (`locked`, `flow`, or `none`).
3. For locked mode only, NEVER place the fixed footer inside `.page`; it must be a direct child of `<body>` before `.page`.
4. For no-footer mode, NEVER invent visible footer text or `.page-footer`; reserve only the platform unsafe zone + safety gap.
5. Always reserve `0.35in` for Zuora's injected bottom bar / platform unsafe zone.
6. If footer or platform text overlaps after render, reduce `First(N)` / `First(M)` before changing visual layout.

#### 4.3 Work Section by Section

For EACH section, follow this process:

1. **Look at PNG** - What exact content is there?
2. **Write HTML** - Match the content exactly using the div rules in 4.2
3. **Add CSS** - Match colors, sizes, spacing exactly
4. **Use placeholders** - Use `[Invoice Number]`, `[Customer Name]`, etc. for dynamic content

**Header:**
- Wrap the header band in a single `<div class="header">`
- **The header div contains ONLY the logo block and, if present, the document-type label (e.g. "INVOICE", "CREDIT MEMO"). It must NOT contain company name, company address, or any invoice detail fields (number, date, due date, amounts, etc.)**
- Company information (name, address) goes in its own `<div class="company-info">` block, placed BELOW the header div
- Invoice detail fields (invoice number, date, due date, balance, etc.) go in their own `<div class="invoice-details">` block, placed BELOW the header div
- **Logo MUST always be in its own `<div class="logo-block">` — never place any text inside the same div as the `<img>` tag**
- If the document-type label appears in the header band alongside the logo: use a flex row parent with `<div class="logo-block">` on one side and `<div class="doc-type">` on the other
- Logo position (left/center/right)?
- Document type label styling (font size, weight, color)?
- Any background colors or borders on the header band?

**LOGO PLACEHOLDER RULE (mandatory):**

If the PNG shows a logo, you MUST emit the following exact structure — the `<img>` tag wrapped in its own `<div class="logo-block">` with **no text or other elements inside that div**:

Using the logo dimensions you recorded in Step 3.1 (width W px, height H px), generate an SVG data URI that renders a dashed-border placeholder box at exactly those dimensions with a centered "[ Logo Placeholder ]" label. Substitute `{W}` and `{H}` with the actual observed pixel values.

```html
<div class="logo-block">
  <!-- LOGO: Replace the src attribute below with a base64-encoded data URI of your logo.
       Format : data:image/<ext>;base64,<encoded-data>
       Example: data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...
       Observed in PDF: position=[left|center|right], approx. {W}x{H} px,
                        style=[describe shape/colors from Step 3.1]
  -->
  <img src="data:image/svg+xml,%3Csvg%20xmlns%3D'http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg'%20width%3D'{W}'%20height%3D'{H}'%3E%3Crect%20width%3D'100%25'%20height%3D'100%25'%20fill%3D'%23f5f5f5'%20stroke%3D'%23aaaaaa'%20stroke-width%3D'2'%20stroke-dasharray%3D'6%2C3'%2F%3E%3Ctext%20x%3D'50%25'%20y%3D'44%25'%20text-anchor%3D'middle'%20dominant-baseline%3D'middle'%20font-family%3D'Arial%2Csans-serif'%20font-size%3D'13'%20fill%3D'%23888888'%3E%5BLogo%20Placeholder%5D%3C%2Ftext%3E%3Ctext%20x%3D'50%25'%20y%3D'66%25'%20text-anchor%3D'middle'%20dominant-baseline%3D'middle'%20font-family%3D'Arial%2Csans-serif'%20font-size%3D'10'%20fill%3D'%23bbbbbb'%3EReplace%20src%20with%20base64%20image%3C%2Ftext%3E%3C%2Fsvg%3E"
       alt="[Replace Placeholder with Logo]"
       class="company-logo"
       style="display:block;" />
</div>
```

**Important:** In the `src` value above, replace the literal `{W}` and `{H}` tokens with the actual observed width and height integers from Step 3.1 (e.g. `width%3D'180'%20height%3D'60'`).

**Any text that appears near the logo (company name, address, tagline) MUST go in a sibling `<div>`, never inside `<div class="logo-block">`.**

Size the `.company-logo` CSS class to match the dimensions you observed in Step 3.1:
```css
.company-logo {
  width: /* observed width, e.g. 1.5in */;
  height: auto;
}
```

If the logo is **not visible** in the PNG, omit the `<div class="logo-block">` and `<img>` tag entirely and add this comment instead:
```html
<!-- LOGO: No logo detected in source PDF. Add one here if required. -->
```

**Info Sections (usually two columns):**
- Wrap the whole info section in `<div class="info-section">`
- Use a flex row child div for the two-column layout
- Left column div: `width` matching PDF proportion, fields stacked vertically
- Right column div: `width` matching PDF proportion, `text-align:right` if PDF right-aligns
- Each label+value pair: either same-line (`<span>`) or stacked (`<div>`) matching PDF observation

**Tables (CRITICAL — match these precisely):**

Use `<table>` with `border-collapse: collapse; width: 100%;`

- Wrap the table area in `<div class="table-section">`
- **Column widths**: Set explicit `width` on `<th>`/`<col>` elements matching the proportions from Step 3. Use percentages (e.g., `width: 40%`). NEVER let columns auto-size.
- **Header row**: Match background color, text color, font-weight, font-size, and text-transform exactly. Use `text-align` matching each column's alignment from Step 3.
- **Cell alignment**: Numeric/amount columns MUST be `text-align: right`. Description columns `text-align: left`. Quantity columns typically `text-align: center`.
- **Borders**: Match the exact border pattern:
  - Horizontal-only: `border-bottom: 1px solid #xxx` on `<td>` 
  - Full grid: `border: 1px solid #xxx` on `<td>`
  - Header-only: `border-bottom: 2px solid #xxx` on `<thead>` or last `<th>`
- **Cell padding**: Match observed padding. Use `padding: Ypx Xpx` on all `<td>` and `<th>`.
- **Summary rows**: If present, use `<tfoot>` or a distinct `class`. Match bold, top-border, and background from Step 3.
- **Alternating rows**: If observed, use `tr:nth-child(even) { background: #xxx; }`

**Totals / Summary block:**
- Totals often appear as a right-aligned block; wrap in `<div style="display:flex; justify-content:flex-end;">`
- Inner div contains label+amount rows

**Footer:**
- Follow Step 4.2.2 — classify **locked** vs **flow** vs **none** from Step 3.2 measurements (per page)
- Locked mode: use `<div class="page-footer">` as a direct child of `<body>` before `.page`
- Flow mode only: keep `<div class="footer">` in normal flow near the content it follows
- No-footer mode: do not create footer markup or visible footer text
- Copy footer text exactly from PNG Observed Text Inventory only when footer text exists
- Apply measured `@page` bottom reserve for the selected mode: locked footer reserve, flow footer clearance, or no-footer platform unsafe zone
- Always include Zuora platform reserve (`0.35in`) in bottom-reserve calculations
- Page numbers present? Match alignment from PNG

#### 4.4 Pixel-Perfect CSS Guidelines

**Colors:** MANDATORY - Use ONLY the extracted hex colors from Step 3.1. Reference the colors.json file:

```css
/* Use extracted colors from colors.json - DO NOT use generic defaults */
.header-title { color: /* from colors.json header_title */; }
.company-info { color: /* from colors.json company_info */; }
.invoice-details { color: /* from colors.json invoice_details */; }
.table-header { 
  background: /* from colors.json table_header background */;
  color: /* from colors.json table_header text */;
}
.table-data { color: /* from colors.json table_data */; }
.field-label { color: /* from colors.json label colors */; }
.field-value { color: /* from colors.json value colors */; }
```

**FORBIDDEN: Do NOT use these generic colors anymore:**
- `#000`, `#333` (use extracted text colors instead)
- `#f0f0f0` (use extracted background colors instead)  
- `#ccc`, `#ddd` (use extracted border colors instead)

**Typography:**
- Use web-safe fonts: Arial, Helvetica, Times New Roman
- Match sizes exactly (in pt for print)
- Match weights (normal, bold, 600, 700)

**Spacing:** Use exact values in inches or points for print accuracy:
```css
.header { padding: 0.25in 0.5in; }
.field { margin-bottom: 0.1in; }
```

#### 4.5 Enterprise Invoice Typography & Spacing (CRITICAL)

**STOP. Before generating HTML, identify the document type:**

| Visual Characteristics | Document Type | CSS Approach |
|------------------------|---------------|--------------|
| Tight spacing, small font (8-9pt), monospace, dense tables, minimal whitespace | **Enterprise Invoice** (SAP/Oracle/legacy system) | Use "tight enterprise" settings below |
| Normal spacing, readable font (10-12pt), proportional, generous whitespace | **Modern Invoice** (web-generated) | Use standard settings |

**If you detect an ENTERPRISE INVOICE, you MUST apply these tight settings:**

```css
body {
  font-family: "Courier New", Courier, monospace;  /* Fixed-width font */
  font-size: 8-9pt;  /* Smaller than web standard */
  line-height: 1.15-1.2;  /* Tight vertical spacing */
  letter-spacing: -0.01em;  /* Compressed character spacing */
}

/* Page margins - tight */
.page {
  padding: 0.35in 0.45in;  /* NOT 0.5in+ */
}

/* Section spacing - minimal */
.section-title {
  margin-top: 0.1in;  /* NOT 0.15in+ */
  margin-bottom: 0.02in;  /* NOT 0.05in+ */
  padding: 0.04in 0.08in;  /* Thin padding */
  line-height: 1.1;  /* Extra tight */
}

/* Table spacing - compact */
table {
  font-size: 8pt;  /* Even smaller than body */
  margin-bottom: 0.05in;  /* Minimal gap after */
}

th {
  padding: 0.04in 0.06in;  /* Thin cell padding */
  line-height: 1.1;
  font-weight: 900;  /* Heavier bold weight */
}

td {
  padding: 0.03in 0.06in;  /* Minimal cell padding */
  line-height: 1.15;
}

/* Bold text - heavier weight */
strong, .bold, th {
  font-weight: 900;  /* NOT bold/700 */
}

/* Totals section - tight */
.total-row {
  margin-bottom: 0.015in;  /* NOT 0.03in+ */
  font-size: 8pt;
  line-height: 1.2;
}

/* Bottom reserve — use Step 4.2.2; choose locked/flow/none from Step 3.2 */
@page {
  margin-bottom: /* selected bottom reserve for footer mode */;
}

/* Include .page-footer ONLY when Step 4.2.2 classifies footer mode as locked. */
.page-footer {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: /* locked_footer_reserve_in */;
  width: 100%;
  background: #fff;
  text-align: /* from PNG */;
  font-size: /* measured, often 6pt enterprise */;
  line-height: 1.1;
}
```

**Key differences between Enterprise vs Modern:**

| Aspect | Enterprise (Tight) | Modern (Relaxed) |
|--------|-------------------|------------------|
| Body font size | 8-9pt | 10-12pt |
| Line-height | 1.15-1.2 | 1.4-1.6 |
| Section margins | 0.1in / 0.02in | 0.15in / 0.05in |
| Table cell padding | 0.03in / 0.04in | 0.06in / 0.08in |
| Bold weight | 900 | 700 / bold |
| Footer font | 6pt | 8-9pt |
| Character spacing | -0.01em | 0 (normal) |

**Why this matters:**

1. **Visual Density**: Enterprise invoices pack maximum information into minimal space - using modern web spacing makes them look "wrong"
2. **Font Appearance**: Monospace fonts at 10pt look too loose; 8-9pt with tight line-height matches the original
3. **Professional Feel**: Loose spacing = "amateur HTML conversion"; tight spacing = "professional report system"
4. **Footer Positioning**: Enterprise invoices often have footers locked to page bottom — use locked mode from Step 4.2.2 with measured `padding-bottom`, never bare absolute positioning

**How to detect Enterprise style from PNG:**

- Text appears very dense/compressed
- Tables have minimal row height
- Strong monospace/typewriter appearance
- Very little whitespace between sections
- Footer text is extremely small (barely readable)
- Overall "data report" aesthetic (not "marketing document")

**CRITICAL: Don't assume - measure the PNG:**

1. Count pixels between sections → if < 20px at 300 DPI, use tight spacing
2. Measure row heights in tables → if < 30px tall, use tight padding
3. Check font appearance → if looks like Courier/monospace, use enterprise settings
4. Compare to this session's feedback → user specifically called out spacing issues

### Step 5: Self-Check (PNG vs HTML) - Max 3 Iterations

**CRITICAL: Re-read the PNG. Compare your Step 3 observations against your HTML.**

#### 5.1 Re-Read the combined PNG

Open the combined PNG again: `{session-folder}/uploads/<file>.pdf.png`

For multi-page PDFs this single image contains all selected sections separated by red bands.
Verify each section (above/between/below the red separator bands) matches the corresponding
HTML page div.

**Do NOT rely on memory. Actually look at the image again.**

#### 5.2 Verification Checklist

Go through your Step 3 observations and verify each one against your HTML:

```
DIV LAYOUT:
[ ] Every distinct horizontal band (header, info row, table, totals, footer) has its own block <div>
[ ] Every side-by-side column group uses a flex/grid container <div> with one child <div> per column
[ ] Column widths (width / flex-basis) match PDF proportions
[ ] Vertical gaps between sections match PDF spacing (margin-bottom values)
[ ] No tables used for non-tabular layout (flexbox/grid only for multi-column regions)

HEADER:
[ ] Header div contains ONLY logo block and doc-type label — no company name, address, or invoice fields: YES/NO
[ ] Background color matches extracted hex: PNG=___ HTML=___ EXTRACTED=___
[ ] Logo wrapped in its own <div class="logo-block"> with NO text inside: YES/NO
[ ] Logo placeholder present (img tag with src="data:image/png;base64,LOGO_PLACEHOLDER"): YES/NO
[ ] Logo position matches: PNG=___ HTML=___
[ ] Logo CSS dimensions set to match observed size: YES/NO
[ ] LOGO comment block present with observed position/dimensions/style: YES/NO
[ ] Doc-type label (if in header band) in separate sibling <div class="doc-type">, NOT in logo-block: YES/NO

COMPANY INFO BLOCK (below header):
[ ] Company name/address in its own <div class="company-info"> below the header div: YES/NO
[ ] Content and position match PDF observation: YES/NO

INVOICE DETAILS BLOCK (below header):
[ ] Invoice detail fields in their own <div class="invoice-details"> below the header div: YES/NO
[ ] All invoice detail fields present and correctly positioned: YES/NO

LEFT COLUMN:
[ ] Field count matches: PNG=___ HTML=___
[ ] Label/value layout matches (inline vs stacked): PNG=___ HTML=___
[ ] Value color matches extracted hex: PNG=___ HTML=___ EXTRACTED=___
[ ] All labels present and spelled correctly
[ ] All values match exactly (dates, numbers, names)

RIGHT COLUMN:
[ ] Text alignment matches: PNG=___ HTML=___
[ ] Column div width/flex-basis proportional to PDF: YES/NO
[ ] All fields present
[ ] Section headers present (italic "For ACH..." etc.)

TABLE:
[ ] Table wrapped in its own <div class="table-section">: YES/NO
[ ] Column count matches: PNG=___ HTML=___
[ ] Column headers match exactly: PNG=___ HTML=___
[ ] Column width proportions match: PNG=___ HTML=___
[ ] Column text alignments match per column: PNG=___ HTML=___
[ ] Header background color matches extracted hex: PNG=___ HTML=___ EXTRACTED=___
[ ] Header text styling matches (weight, transform): PNG=___ HTML=___
[ ] Border pattern matches (grid/horizontal/none): PNG=___ HTML=___
[ ] Cell padding looks correct (not too tight/loose): visual ___
[ ] Numeric columns are right-aligned: PNG=___ HTML=___
[ ] Summary/subtotal row styling matches: PNG=___ HTML=___
[ ] Row count matches: PNG=___ HTML=___

TOTALS:
[ ] Totals block right-aligned using flex justify-content:flex-end or text-align:right: YES/NO
[ ] Totals block vertically positioned below table with correct gap: YES/NO

HYPERLINKS:
[ ] Any underlined/colored text that looked like a hyperlink in the PNG: YES/NO
[ ] If YES — no navigating <a href="..."> unless full URL was visible as plain text in PNG: YES/NO
[ ] Hyperlink-styled text uses <span style="color:...; text-decoration:underline;"> (preferred) or <a href="javascript:void(0)" pointer-events:none> — NEVER href="#": YES/NO
[ ] <!-- LINK: ... --> comment present for each hyperlink-styled element: YES/NO

TYPOGRAPHY & SPACING (CRITICAL - most common failure point):
[ ] Document type identified correctly (enterprise tight vs modern relaxed): ___
[ ] Font size matches visual density: PNG appears (tight 8-9pt / normal 10-12pt) HTML uses ___
[ ] Line-height matches compression: PNG appears (1.15-1.2 / 1.4-1.6) HTML uses ___
[ ] Font family correct: PNG shows (monospace / proportional) HTML uses ___
[ ] Bold weight heavy enough: PNG bold looks (heavy 900 / normal 700) HTML uses ___
[ ] Section margins match tightness: measure gaps in PNG ___ px, HTML uses ___ in
[ ] Table cell padding matches: measure row height ___ px, HTML td padding ___
[ ] Character spacing: PNG appears (compressed -0.01em / normal 0) HTML uses ___
[ ] Footer font size: PNG footer text is (tiny 6pt / small 8pt / normal 10pt) HTML uses ___
[ ] Footer mode matches PNG: (locked / flow / none) HTML uses ___
[ ] If footer mode is none: no visible footer element/text was invented: YES/NO
[ ] If footer mode is none: @page reserves only platform unsafe zone + safety gap: YES/NO
[ ] If footer mode is locked: @page bottom margin >= .page-footer height: YES/NO
[ ] If footer mode is locked: .page-footer is direct child of body before .page: YES/NO
[ ] If footer mode is locked: .page-footer has fixed bottom:0, explicit height, and opaque background: YES/NO
[ ] Bottom reserve paired with stable .page shell (body margin 0, no large inter-page spacers): YES/NO
[ ] No row, total, note, border, or text baseline enters the reserved bottom band: YES/NO
[ ] Bottom safety gap above footer is at least 0.12in (or measured larger gap): YES/NO
[ ] Footer does NOT overlap last table row or totals (no text hidden behind footer bar): YES/NO
[ ] First(N) uses count-above-footer minus 1–2 safety rows: counted=___ N=___
[ ] Overall visual match: side-by-side comparison shows (exact match / close / mismatch)

DATE & NUMBER FORMATTING:
[ ] All date fields use Format() decorator with pattern matching the PDF: YES/NO
[ ] All amount/currency fields use Round(2) (or observed precision): YES/NO
[ ] Quantity fields use appropriate Round() precision: YES/NO
[ ] Unit price fields use appropriate Round() precision: YES/NO

PAGINATION FIDELITY (multi-page PDFs only — skip if single-page):
[ ] HTML has exactly N .page divs matching N sections in the combined PNG: sections=___ divs=___
[ ] break-before:page AND page-break-before:always on every .page div except the first: YES/NO
[ ] NO min-height:11in (or any fixed page height) on .page divs: YES/NO
[ ] No blank gap between pages when rendered (content flows cleanly): YES/NO
[ ] Page 2+ content starts at measured top position, not pushed below footer reserve: YES/NO
[ ] Line items split correctly — page 1 uses First(N), remaining pages use Skip(N): YES/NO
[ ] N matches the row count visible in section 1 of the combined PNG: counted=___ used=___
[ ] Continuation table has a <thead> with the same columns/widths as section 1 table: YES/NO
[ ] Full header (logo, company) NOT repeated on continuation pages (unless PNG shows it): YES/NO
[ ] Each page div contains only the content belonging to that section of the combined PNG: YES/NO
[ ] If PDF has omitted middle pages (pages_used skips numbers), line-item Skip(N) accounts for ALL omitted rows: YES/NO
[ ] Each locked footer uses measured @page reserve; each flow footer uses measured margin-top per Step 4.2.2: YES/NO
[ ] Zuora platform reserve (0.35in) included in footer calculations: YES/NO
```

#### 5.3 Common Mistakes Checklist

| Check This | PNG Shows | Your HTML | Fix If Wrong |
|------------|-----------|-----------|--------------|
| Side-by-side columns as flex? | YES or NO? | `display:flex` on parent? | Wrap in flex div |
| Column widths proportional? | e.g. 60/40 split | `width` values? | Adjust width/flex-basis |
| Sections vertically separated? | Gap present? | `margin-bottom` set? | Add margin-bottom |
| Right column alignment | LEFT or RIGHT? | `text-align: ___` | Change CSS |
| Label/value on same line? | YES or NO? | `display: inline` or `block`? | Change CSS |
| Values in blue? | YES or NO? | `color: ___` | Add `.info-value { color: #xxx }` |
| Labels in bold? | YES or NO? | `font-weight: ___` | Add `font-weight: bold` |
| Table columns auto-sized? | Fixed widths | Missing `width` on `<th>` | Add explicit `width: XX%` |
| Amount columns left-aligned? | RIGHT-aligned | `text-align: left` | Change to `text-align: right` |
| Table borders wrong pattern? | Horizontal-only | Full grid or none | Match border style on `<td>` |
| Header text not uppercase? | UPPERCASE | Normal case | Add `text-transform: uppercase` |
| Summary row missing styling? | Bold + border | Plain row | Add bold, `border-top`, background |
| Footer/platform area overlapping table? | Clear gap | Rows hidden | Add measured `@page` bottom reserve for selected mode; reduce `First(N)` |
| Footer absolute/inside `.page`? | locked mode | absolute footer inside page | For locked mode only, move to fixed `.page-footer` direct child of `<body>` before `.page` |
| Zuora platform bar overlap? | N/A at PNG stage | "Powered by zuora" covers rows | Include 0.35in platform unsafe zone in the selected bottom reserve |
| Footer line crosses last row? | Clear gap above footer | "Powered by zuora" overlays row/border | Increase bottom safety gap and reduce `First(N)` / move last row to next page |
| Huge blank gap before continuation page? | Page 2 starts near top | Page 2 pushed down | Remove large inter-page margins/spacers; use stable `.page` shell with body margin 0 |

#### 5.4 Text Accuracy Verification

**Read every piece of text in the PNG again. Compare to HTML:**

| PNG Text | HTML Text | Match? |
|----------|-----------|--------|
| Invoice Date: | ? | ? |
| Feb 1, 2023 | ? | ? |
| Footer/end-of-page text line(s) | ? | ? |
| (continue for ALL text...) | | |

**If ANY text doesn't match, fix it NOW.**

#### 5.5 Text Preservation Gate (MANDATORY PASS/FAIL)

Before moving to Step 6, run this gate:

1. Compare **Observed Text Inventory** vs generated plain HTML.
2. For each missing text item, check if it is listed in **Dynamic Replacement Inventory**.
3. If missing and not intentionally replaced, **FAIL** the gate and restore the text.

Gate pass criteria:
- No unexplained missing literals.
- Every intentional replacement is documented with field mapping.
- No `[UNCLEAR]` item is silently removed.
- Footer/end-of-page literals are present unless intentionally replaced by a validated field.

#### 5.6 Iteration Rules

1. If anything doesn't match → Fix immediately
2. Re-verify the specific fix
3. Max 3 total iterations

**After 3 iterations:**
- Add HTML comment: `<!-- REVIEW: [specific issues] need manual adjustment -->`
- CONTINUE to Step 6 (do NOT stop)

### Step 6: Save Plain HTML

Save the HTML using the **`Write` tool** (not `Edit`, not Bash redirection):

```
Write: {session-folder}/html/plain-v{N}.html
Content: <entire plain HTML — full file content, not a fragment>
```

Where `{N}` is the version number (1, 2, 3...).

**CRITICAL FILE-WRITE RULES (apply to every HTML file this skill produces):**
- **Always use the `Write` tool** — it overwrites the entire file atomically.
- **Never use `Edit`** on HTML output files — `Edit` patches existing content and will corrupt the file if called after a partial write.
- **Never use Bash shell redirection** (`echo ... >> file`, `cat >> file`) — append operators produce duplicate/interleaved content.
- Write the **complete file content** in a single `Write` call. Do not split across multiple calls.

**IMPORTANT: Do NOT stop here. Continue immediately to Step 7.**

### Step 7: Add Zuora Merge Fields

Read the plain HTML from Step 6 and transform it into a Zuora template.

**Transform Process:**
1. Read the plain HTML file content (use `Read` tool on `{session-folder}/html/plain-v{N}.html`)
2. **Query Zuora metadata** to understand available fields
3. Identify dynamic content (dates, numbers, names, amounts, line items)
4. Replace placeholder text with validated Zuora merge fields
5. Wrap repeating table rows with section tags
6. Save to templates folder using the **`Write` tool** (never `Edit`, never Bash redirection — see Step 6 file-write rules)

#### 7.1 Query Object Metadata

First, determine the template type and query available fields using `mcp__zuora-mcp__query_objects`:

**List all queryable object types:**
```
mcp__zuora-mcp__query_objects: { "help": "types" }
```

**Get all fields for Invoice:**
```
mcp__zuora-mcp__query_objects: { "objectType": "Invoice", "help": "fields" }
```

**Get all fields for InvoiceItem:**
```
mcp__zuora-mcp__query_objects: { "objectType": "InvoiceItem", "help": "fields" }
```

**Get all fields for Account:**
```
mcp__zuora-mcp__query_objects: { "objectType": "Account", "help": "fields" }
```

> **Fallback:** If `query_objects` is unavailable (no credentials), read `${CLAUDE_PLUGIN_ROOT}/skills/zuora-html-template-designer/references/objects.yaml`. Each object entry has a `properties:` section (fields) and a `relationships:` section (navigable hops, e.g. `Invoice → account → Account`). Use both to discover available fields and traversal paths. Note: this file is a static snapshot and will not include tenant-specific custom fields.

#### 7.2 Validate Field Paths

Before using merge fields, validate they exist by checking the field appears in the `query_objects` field list for that object:

**Validate Invoice fields (e.g., InvoiceNumber, InvoiceDate, DueDate, Amount):**
```
mcp__zuora-mcp__query_objects: { "objectType": "Invoice", "help": "fields" }
```
Confirm `InvoiceNumber`, `InvoiceDate`, etc. appear in the returned list.

**Validate nested path (e.g., Invoice.Account.Name):**
```
mcp__zuora-mcp__query_objects: { "objectType": "Account", "help": "fields" }
```
Confirm `Name` appears in Account fields.

**Validate InvoiceItems section field:**
```
mcp__zuora-mcp__query_objects: { "objectType": "InvoiceItem", "help": "fields" }
```
Confirm section fields like `ChargeName`, `ServiceStartDate`, `ChargeAmount` exist.

**To discover navigable relationships (e.g. what objects Invoice can expand to):**
```
mcp__zuora-mcp__query_objects: { "objectType": "Invoice", "help": "expands" }
```

> **Fallback:** If `query_objects` is unavailable, use the `relationships:` entries in `${CLAUDE_PLUGIN_ROOT}/skills/zuora-html-template-designer/references/objects.yaml` to trace each hop in the path manually (e.g. `Invoice.relationships` → find `account` → `Account.properties` → confirm `Name` exists).

#### 7.3 Merge Field Mapping

Based on metadata queries, map placeholders to valid fields:

| Placeholder | Replace With | Validate First |
|-------------|--------------|----------------|
| `[Invoice Number]` or `INV-001234` | `{{Invoice.InvoiceNumber}}` | ✓ Query metadata |
| `[Invoice Date]` or `Jan 31, 2023` | `{{Invoice.InvoiceDate\|Format(MMM dd, yyyy)}}` | ✓ Query metadata |
| `[Due Date]` or `Mar 2, 2023` | `{{Invoice.DueDate\|Format(MMM dd, yyyy)}}` | ✓ Query metadata |
| `[Customer Name]` or `Acme Corp` | `{{Invoice.Account.Name}}` | ✓ Validate path |
| `[Account Number]` or `A00012345` | `{{Invoice.Account.AccountNumber}}` | ✓ Validate path |
| `[Bill To Name]` or `John Smith` | `{{Invoice.Account.BillTo.FirstName}} {{Invoice.Account.BillTo.LastName}}` | ✓ Validate path |
| `[Bill To Address]` or `123 Main St` | `{{Invoice.Account.BillTo.Address1}}` | ✓ Validate path |
| `[Currency]` or `USD` | `{{Invoice.Currency}}` | ✓ Query metadata |
| `[Total]` or `$1,194.00` | `{{Invoice.Account.Currency\|Symbol}}{{Invoice.Amount\|Round(2)}}` | ✓ Query metadata |
| `[Tax]` or `8.25%` (line item) | `{{#TaxationItems\|First(1)}}{{#Wp_Eval}}{{TaxRate}}*100\|Round(2){{/Wp_Eval}}%{{/TaxationItems\|First(1)}}{{^TaxationItems}}0%{{/TaxationItems}}` inside `{{#Invoice.InvoiceItems}}` — **not** `{{TaxCode}}` | ✓ Validate `Invoice.InvoiceItems.TaxationItems.TaxRate` |

**IMPORTANT:** The `Format` pattern in the table above (`MMM dd, yyyy`) is an example — always use the pattern that matches the date format observed in the PDF (Step 3.1).

**CRITICAL — Bill-To / Sold-To / Ship-To contact fields:** Always reach contact
fields through the **Account**, not through the document's own direct contact
relationship:

- Use `{{Invoice.Account.BillTo.<Field>}}`, `{{Invoice.Account.SoldTo.<Field>}}`,
  `{{Invoice.Account.ShipTo.<Field>}}` (e.g. `FirstName`, `LastName`, `Address1`,
  `City`, `State`, `PostalCode`, `Country`). For credit/debit memos use
  `{{CreditMemo.Account.BillTo.<Field>}}` / `{{DebitMemo.Account.BillTo.<Field>}}`.
- Do **NOT** use the direct relationships `Invoice.BillToContact.*`,
  `Invoice.SoldToContact.*`, `Invoice.ShipToContact.*` (or the `*Snapshot`
  variants), nor the same on `CreditMemo`/`DebitMemo`. These paths pass metadata
  validation (the relationship exists in the data model) but render **empty** —
  Zuora only hydrates the contact through the Account at render time.
- When in doubt about a contact path, query Account fields via `mcp__zuora-mcp__query_objects`
  with `{ "objectType": "Account", "help": "fields" }` and use only confirmed field names.

#### 7.3.1 Replacement Safety Rules (MANDATORY)

When replacing literals/placeholders with merge fields:

1. Replace only items classified as **Dynamic value** in Step 3.3.
2. Do **not** replace static literals (headers, labels, legal text, notes, instructions, table headers) with blanks or merge fields unless the PDF clearly shows they are data values.
3. Keep punctuation, separators, and surrounding label text intact when replacing a value.
4. If a merge field mapping is uncertain, keep the original literal and add:
   `<!-- REVIEW: unresolved mapping for "..." -->`
   Do not drop content.

Run a post-replacement check:
- `template-vN.html` must contain all items from Must-Retain Static Inventory.
- Every removed literal must appear in Dynamic Replacement Inventory with replacement field path.

#### 7.3.2 Strict Replacement Policy (Mandatory)

1. Extract exact visible text from the PNG (no guessing).
2. For each text item, record:
   `[source_text, classification(static/dynamic/unclear), candidate_field, validation_result, final_output]`
3. Use merge fields only when `classification=dynamic` and `validation_result=PASS`; otherwise keep literal text.
4. Never replace unresolved values with `&nbsp;`, empty tags, or removed text.
5. Before output, every removed literal must have validated merge-field evidence; if not, restore it.

**Note:** Use metadata queries to discover additional fields that may be relevant:
- Tax fields: `Invoice.TaxAmount`, `Invoice.TaxStatus`; line-item `%` values → `{{#TaxationItems|First(1)}}{{#Wp_Eval}}{{TaxRate}}*100|Round(2){{/Wp_Eval}}%{{/TaxationItems|First(1)}}{{^TaxationItems}}0%{{/TaxationItems}}` (`TaxRate` is decimal, e.g. `0.0825` = 8.25%; use `Round(2)` not `Round(0)` — `Round(0)` truncates `8.25%` to `8%`; `{{^TaxationItems}}0%{{/TaxationItems}}` when no tax applies; not `TaxCode`)
- Payment terms: `Invoice.PaymentTerm`, `Invoice.PaymentMethod`
- Custom fields: Query metadata may reveal custom fields specific to the tenant

#### 7.4 Format Date and Number Fields (MANDATORY)

**CRITICAL: Every date and number field MUST have a formatting decorator that matches the format observed in the PDF (Step 3.1).** Unformatted fields render as raw API values (e.g., `2023-01-31` instead of `Jan 31, 2023`, or `1194.0` instead of `1,194.00`), which breaks visual fidelity.

- **Date fields** — apply `Format(Pattern)` with the pattern that matches what the PDF shows (see [Functions Reference](${CLAUDE_PLUGIN_ROOT}/skills/zuora-html-template-designer/references/functions.md) for pattern letters and examples)
- **Number/amount fields** — apply `Round(Precision)` matching the decimal places shown in the PDF; chain `Localise` if the PDF uses thousands separators (see [Functions Reference](${CLAUDE_PLUGIN_ROOT}/skills/zuora-html-template-designer/references/functions.md))
- **Currency symbol** — prefix monetary amounts with `{{Invoice.Account.Currency|Symbol}}` whenever the PDF shows a currency symbol before the amount; the recommended pattern is `{{Invoice.Account.Currency|Symbol}}{{Amount|Round(2)|Localise}}`

Apply to **all** date, number, and currency fields — both top-level invoice fields and fields inside section loops.

#### 7.5 Section Tags for Line Items

Find the table body rows and wrap them with validated section tags:

```
# First validate InvoiceItem fields exist
mcp__zuora-mcp__query_objects: { "objectType": "InvoiceItem", "help": "fields" }
```
Confirm `ChargeName`, `ServiceStartDate`, `ServiceEndDate`, `Quantity`, `UnitPrice`, `ChargeAmount` appear in the result.

Then apply the section with proper formatting on date and number fields:
```html
{{#Invoice.InvoiceItems}}
<tr>
  <td>{{ChargeName}}</td>
  <td>{{ServiceStartDate|Format(MMM dd, yyyy)}} - {{ServiceEndDate|Format(MMM dd, yyyy)}}</td>
  <td>{{Quantity|Round(0)}}</td>
  <td>{{Invoice.Account.Currency|Symbol}}{{UnitPrice|Round(2)}}</td>
  <td>{{Invoice.Account.Currency|Symbol}}{{ChargeAmount|Round(2)}}</td>
</tr>
{{/Invoice.InvoiceItems}}
```

**Note:** Adjust `Format` patterns and `Round` precision to match what was observed in the PDF (Step 3.1). The examples above use common defaults — always defer to the actual PDF format.

**Benefits of Metadata Integration:**
- **Accuracy**: Use actual field names from the tenant's configuration
- **Discovery**: Find custom fields and additional attributes
- **Validation**: Verify paths exist before using them
- **Navigation**: Understand object relationships for complex paths

**CRITICAL: All merge fields must trace to root object (Invoice/CreditMemo/DebitMemo) and be validated against metadata.**

### Step 8: Validate Template

Validate the template before returning using `mcp__zuora-mcp__manage_document_presentment`:

```
mcp__zuora-mcp__manage_document_presentment: {
  "operation": "validate_template",
  "objectType": "Invoice",
  "template": "<entire HTML template content here>"
}
```

Replace `objectType` with `CreditMemo` or `DebitMemo` as appropriate.

**Success response:**
```json
{"success": true, "message": "Template is valid"}
```

**If validation fails:**
1. Read the error message
2. Fix the merge field (usually missing root object)
3. Retry validation (max 3 attempts)

> **If `manage_document_presentment` is unavailable** (no credentials): note that validation was skipped.

**Common Validation Errors:**

| Error | Cause | Fix |
|-------|-------|-----|
| `UnknownField: Account.Name` | Missing root object | `{{Invoice.Account.Name}}` |
| `UnknownField: ChargeName` | Used outside section | Wrap in `{{#Invoice.InvoiceItems}}...{{/Invoice.InvoiceItems}}` |

### Output Delivery Rules

**Save sequence (in order):**

1. **Validation copy** — use `Write` tool (full file, single call, never `Edit`):
   ```
   {session-folder}/templates/template-v{N}.html
   ```

2. **Auto-save to Downloads** — immediately after validation passes, copy to the user's Downloads folder using Bash:
   ```bash
   cp {session-folder}/templates/template-v{N}.html ~/Downloads/zuora-template.html
   ```
   If the copy succeeds, tell the user:
   > Template saved to **~/Downloads/zuora-template.html**

   If `~/Downloads/` does not exist (e.g. Linux CI environment), skip it.

3. **Return in chat** — include the full HTML in your response inside a fenced code block so the user can also copy it directly.

### Step 9: Return Final Template

Return the validated template per Output Delivery Rules above (validation copy → auto-save to Downloads → return in chat).

---

## Text-Only Workflow (Direct Generation)

For prompts without PDF attachments, generate templates directly.

### Instructions

1. **Understand requirements** - Identify business objects needed (Invoice, CreditMemo, DebitMemo)

2. **Query available objects:**
   ```
   mcp__zuora-mcp__query_objects: { "help": "types" }
   ```

3. **Query object metadata:**
   ```
   mcp__zuora-mcp__query_objects: { "objectType": "Invoice", "help": "fields" }
   ```

4. **Map requirements** to Zuora objects and navigation paths:
   - Invoice details at item level: `Invoice.InvoiceItems`
   - Product name: `Invoice.InvoiceItems -> RatePlanCharge.ProductRatePlanCharge.ProductRatePlan.Product.Name`

5. **Design template** using [Merge field syntax](${CLAUDE_PLUGIN_ROOT}/skills/zuora-html-template-designer/references/merge-field-syntax.md)

6. **Use JavaScript** if merge fields are insufficient: [JavaScript guide](${CLAUDE_PLUGIN_ROOT}/skills/zuora-html-template-designer/references/javascript.md)

7. **Output format:** HTML code snippet (no `<html>`, `<head>`, `<body>` tags)

8. **Validate template:**
   ```
   mcp__zuora-mcp__manage_document_presentment: {
     "operation": "validate_template",
     "objectType": "Invoice",
     "template": "<template content>"
   }
   ```
   - If validation fails: Fix and retry (max 3 attempts)
   - If validation passes: Follow Output Delivery Rules (auto-save to Desktop, then return in chat)

---

## Folder Structure

```
{session-folder}/
├── uploads/          # Original PDF and converted PNG (Step 2)
├── html/             # Plain HTML without merge fields (Step 6)
└── templates/        # Final templates with merge fields (Step 9)
```

---

## Metadata Queries

Metadata is queried live using the `mcp__zuora-mcp__query_objects` MCP tool, which queries the Zuora Object Query API for the configured tenant.

```
# List all queryable object types
mcp__zuora-mcp__query_objects: { "help": "types" }

# Get fields and descriptions for an object
mcp__zuora-mcp__query_objects: { "objectType": "Invoice", "help": "fields" }

# Get expandable relationships for an object
mcp__zuora-mcp__query_objects: { "objectType": "Invoice", "help": "expands" }

# Query a sample record to inspect live data
mcp__zuora-mcp__query_objects: {
  "objectType": "Invoice",
  "fields": ["Id", "InvoiceNumber", "InvoiceDate", "Amount"],
  "pageSize": 1
}
```

**Fallback (when MCP is unavailable):** Read `${CLAUDE_PLUGIN_ROOT}/skills/zuora-html-template-designer/references/objects.yaml` for static field reference.

---

## Rules

1. **Use documented functions only** - See [functions](${CLAUDE_PLUGIN_ROOT}/skills/zuora-html-template-designer/references/functions.md), [expressions](${CLAUDE_PLUGIN_ROOT}/skills/zuora-html-template-designer/references/expressions.md), [merge-field-syntax](${CLAUDE_PLUGIN_ROOT}/skills/zuora-html-template-designer/references/merge-field-syntax.md). Use JavaScript for complex logic.

2. **CSS in style tags** - Use `<style>...</style>` for styling

3. **Session folder consistency** - Derive from attachment path, use for ALL files

4. **Root object required** - Every merge field must trace to Invoice/CreditMemo/DebitMemo

5. **Complete all 9 steps** - For PDF workflows, never stop before Step 9

---

## References

- [Merge Field Syntax](${CLAUDE_PLUGIN_ROOT}/skills/zuora-html-template-designer/references/merge-field-syntax.md)
- [Functions](${CLAUDE_PLUGIN_ROOT}/skills/zuora-html-template-designer/references/functions.md)
- [Expressions](${CLAUDE_PLUGIN_ROOT}/skills/zuora-html-template-designer/references/expressions.md)
- [JavaScript Integration](${CLAUDE_PLUGIN_ROOT}/skills/zuora-html-template-designer/references/javascript.md)
- [Logic Control](${CLAUDE_PLUGIN_ROOT}/skills/zuora-html-template-designer/references/logic-control.md)
- [Object Metadata (fallback)](${CLAUDE_PLUGIN_ROOT}/skills/zuora-html-template-designer/references/objects.yaml)

---

## Limitations

- For PDFs with more than 3 pages, only the first, second-to-last, and last pages are
  converted. Middle pages follow the same row pattern as the visible continuation pages.
- Font matching is best-effort using web-safe alternatives
- Complex layouts may require manual refinement
