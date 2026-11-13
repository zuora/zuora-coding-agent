---
name: zuora-v2-migration-design
description: Find v2 API usage in a codebase and produce a migration plan to the public APIs from the shipped mapping pack
argument-hint: "[codebase=<path> [operation=<pack-id-or-resource-name>]]"
allowed-tools: [Read, Write, Glob, Grep, Bash, AskUserQuestion, Skill, mcp__zuora-mcp__zuora_codegen, mcp__zuora-mcp__ask_zuora]
---

Codex-only path resolution: When an instruction refers to `${CLAUDE_PLUGIN_ROOT}`, treat it as the root of this installed plugin. In Codex, resolve that root as the ancestor directory containing `skills/`, `references/`, and `.codex-plugin/`.

## Input

The user's codebase path and optional operation filter: $ARGUMENTS

Expected format: `codebase=/path/to/customer-repo` or `codebase=/path/to/customer-repo operation=invoices.list`

## REQUIRED INPUT: Codebase Path

Resolve the codebase path before any analysis:

1. If `$ARGUMENTS` contains `codebase=<path>`, use that path directly and inform the user:
   > "Analyzing codebase at: `<resolved-path>`"

2. If no path is provided, run `pwd` to get the current working directory, then ask:
   > "No codebase path was provided. I will use the current working directory:
   > `<pwd-result>`
   >
   > Is this correct, or would you like to specify a different path? (press Enter to confirm, or type the path)"

   **STOP. Wait for the user to confirm or provide a path before continuing.**

Do NOT proceed with any analysis until the path is confirmed.

## Output location and data handling

Default output directory: `./v2-migration/` in the current working directory (not inside the scanned repo).

If the user's provided or confirmed path is inside the scanned repository, ask:
> "The output directory `./v2-migration/` would be written inside the scanned repository. Are you sure you want to write inside the scanned repo? (yes/no)"

**STOP until the user answers.**

Data-handling note:
- Only the code snippets needed for triage and per-site analysis are sent to the LLM you are already using.
- Never print or log credential values; the scanner redacts them, and you must not reverse the redaction.
- The generated plan (`v2-migration-plan.md`) may contain customer-specific code snippets. Tell the user: **Do not commit the plan file to your repository — it may contain sensitive code.**

## Tool routing

Use local file tools (`Read`, `Glob`, `Grep`, `Bash`) for all code scanning, pack lookups, and plan writing. `mcp__zuora-mcp__zuora_codegen` may also be used for the target code style of SDK users (step 5.6). `mcp__zuora-mcp__zuora_codegen` and `mcp__zuora-mcp__ask_zuora` may be used only to clarify public API contract details that are not answered by the pack, and to learn SDK method names, model classes and call shape. They must never override a pack disposition (`confirmed`, `limitation`, `confirmed_via_graphql`, `not_on_route`) and must never promote a `limitation` item to `confirmed`.

## Workflow

> **When unsure about any aspect of the migration analysis, do NOT guess — list the uncertain items and ask the user before proceeding.**

### Step 1: Confirm codebase path

Apply the hard gate above. Record the confirmed path. If the `mcp__zuora-mcp__zuora_codegen` tool is available, it is called in Step 2b for every run, before any triage; do not start Step 2 without planning that call. If `$ARGUMENTS` contains `operation=<value>`, record it as the operation filter; only sites whose `pack_id` matches the filter will be analyzed in Steps 4–6.

### Step 2: Run the scanner

Check that the scanner script exists:

```
${CLAUDE_PLUGIN_ROOT}/scripts/scan-v2-usage.js
```

If `${CLAUDE_PLUGIN_ROOT}` is not set or is not expanded in your shell, resolve the plugin root yourself before deciding anything: it is the directory that contains this skill's `skills/` folder (two levels above this `SKILL.md`); then look for `scripts/scan-v2-usage.js` under it (for example with a file search). Only when that search finds nothing does the next paragraph apply.

If the scanner script is absent, stop immediately and report:
> "The scanner script (`${CLAUDE_PLUGIN_ROOT}/scripts/scan-v2-usage.js`) is not available in this plugin installation. Reinstall or update the plugin."

If the scanner exists, create the output directory and run it with the shell tool. Never conclude that the shell tool or `node` is unavailable without trying the command; if it fails, show the failure output and stop (do not substitute a manual scan unless the user asks for one).

Create the output directory and run:

```bash
mkdir -p <outdir>
cp "${CLAUDE_PLUGIN_ROOT}/templates/v2-v1/migration-plan.md" <outdir>/v2-migration-plan.md
node "${CLAUDE_PLUGIN_ROOT}/scripts/scan-v2-usage.js" <codebase-path> --out <outdir>/v2-inventory.json
```

The `cp` creates the plan file now, from the template, so that every later step fills a section of that file; the plan is never written from scratch and its section titles are never changed.

Show the user:
- `summary.files_scanned`, `summary.files_skipped`, `summary.sites`
- `summary.by_pack_id` — per-operation counts
- `summary.sdk_detection` and `summary.languages_without_sdk_pattern`: the v2 API has an SDK only for Java, so SDK calls are detected only in Java (the accessor chains `accounts()`, `invoices()`, `invoiceItems()`, `billingDocuments()`, `subscriptions()` on the v2 client `com.zuora.sdk.ZuoraClient`, directly or through `quickStartApi()` of the unified client; the unified client's own `xxxApi()` calls are v1 and are never reported). In every other language only raw HTTP calls (URL matches) are found; say that in the coverage summary.

If the scanner exits with code 2, stop and report the error message from stderr.

### Step 2b: Language check with the code generation tool (before any triage or plan text)

If the `mcp__zuora-mcp__zuora_codegen` tool is available in this session, call it now, once for each language the inventory shows (`list_api_classes`, then `get_class_apis` for `ObjectQueriesApi`, and `get_api_details` for the target operations of the routes you will use) and keep the answers: step 5.6 uses them. Do not read further into the code, triage, or write any plan text until the scanner output (Step 2) and these tool answers are both in the conversation. If the tool is not available, say so in one line and continue; never skip the call because the sites are raw HTTP, and never skip it for a language you expect the tool not to support: a rejected call is the evidence you cite ("the tool does not list <language>"), and a statement about what the tool supports without a call in this session is not evidence. Match languages by meaning, not by spelling: the scanner's `javascript` and `typescript` are the tool's `nodejs`, and a customer language the schema lists under another name counts as listed. When the tool's own schema limits the `language` parameter to a list that does not contain the customer's language, you cannot pass that language: make the calls anyway with a language the schema accepts that is not a customer language and carries no SDK (for example `curl`), for `list_api_classes` and for the target operations' details, and cite both the schema's language list and what those calls returned as the evidence that the customer's language is unsupported; never copy SDK names from that substitute call into the customer's language.

### Step 3: Triage unmatched and undetected-risk entries

First drop every `undetected_risk[]` entry whose file and line equal a matched site in `sites[]` (the scanner reports the same line as a risk when a URL is built from a base-URL variable; the site is already covered) and list the dropped count in the coverage summary. Then, for each remaining entry in `unmatched[]` and `undetected_risk[]` in the inventory:

1. Read the file at the given path and line range (use `Read` with an offset and limit around the site).
2. Read the surrounding functions, class names, and any URL construction logic.
3. Based solely on the code evidence just read, attempt to resolve the entry to a pack id from `pack/index.json` (nine operations: `accounts.get`, `accounts.list`, `billing_documents.list`, `invoice_items.list`, `invoices.get`, `invoices.list`, `subscriptions.get`, `subscriptions.list`, `subscriptions.versions`).
4. If the code clearly maps to one of those operations, add it to the working site list with confidence `medium` (triage-resolved). An extra v2 call you notice while reading is added as its own site the same way (see "Missed sites" in Step 4).
5. If the code cannot be resolved from evidence, mark it `needs-human` and record why.

Never resolve from memory. Cite the file path and line numbers of the code evidence read.

### Step 4: Per-site facts

For each site in `sites[]` plus any triage-resolved entries (apply the operation filter if set):

**Missed sites:** whenever reading the code, in Step 3 triage or in this step, shows a v2 call the scanner did not report (for example a path built as `BASE + "/" + id`, where the scanner reported only the constant), add it as an extra site: next id after the inventory's last, confidence `medium`, the evidence "found by reading the code", and say so in the coverage summary and in the site block. Do not edit `v2-inventory.json` by hand beyond appending it.


Read the surrounding code to determine:
- Which request parameters the call sends (query params, headers, request body fields)
- Which response fields the code reads, accesses, or passes to downstream consumers
- Whether there is a paging loop, and if so: how the cursor or page token is extracted and passed
- Error-handling code around the call (HTTP status checks, exception handlers, retry logic)
- Downstream consumers of the response (what happens with the data after the call)

Record these facts per site. Do not guess — read the actual code. The "Inventory table" of the plan has one row per site with the call style (raw HTTP, SDK, wrapper, config file, or an export from an integration tool), the request parameters sent and the response fields read, taken from these facts.

**Handoff sites:** a site whose file is an export of an integration tool the agent cannot edit (a Boomi process, a Workato recipe, a Power Automate flow, a Zuora Workflow definition) or a Postman collection is a handoff site. Mark it as such in the inventory table. Code and config files in the customer's repository, including Apex classes and YAML or properties files, are not handoff sites. Everything else in Steps 5 and 6 (pack lookup, card, status) applies to a handoff site unchanged; only the output differs (Step 7).

### Step 5: Pack lookup

For each site to be analyzed:

**5.1 Load the pack index:**

```
${CLAUDE_PLUGIN_ROOT}/references/v2-v1/pack/index.json
```

Find the card whose `id` matches the site's `pack_id`. Note the `recommended_route` and available routes.

**5.2 Choose the route:**

Use `recommended_route.api` unless:
- The customer's code is already written against the v1 REST client (use `v1_rest` instead), or
- The user specifies a different route.

State the rationale (quote `recommended_route.rationale` from the pack card).

**5.3 Load the route file:**

```
${CLAUDE_PLUGIN_ROOT}/references/v2-v1/pack/<pack_id>.<route>.json
```

**5.4 Load filter/sort/expand reference if needed:**

If the site sends `filter[]`, `sort[]`, or `expand[]`, also load:

```
${CLAUDE_PLUGIN_ROOT}/references/v2-v1/filter-sort-translation.md
```

**5.5 Apply dispositions per item:**

For each request parameter and response field the site uses, find the matching item in the route file's `request[]` or `response[]` array and apply its `disposition`:

- `confirmed` — Apply `target.transform` exactly. For `custom_fields`, "only when requested" means only when the customer's code reads that property: the API reference documents no parameter that requests custom fields, so do not invent one; if the code narrows the response with `fields[]`, name the custom fields it needs and list "confirm on a tenant that they are returned" as an open decision. One exception, which always wins: when a request value in the customer's code is a literal outside a numeric bound that the same route file states (for example a page size above the stated maximum), the transform's "pass the value unchanged" does not apply to that value; clamp it to the stated bound in the proposed code, show both values in the plan, and list the change under "Open decisions and limits". If the item has `computed_from`, the value is not returned by the public API: derive it in the customer's code from those v2 fields (each mapped through its own item on the same route) by following the rule in `target.transform`; if an input is `not_on_route`, or is a `limitation` that has no `target`, say the computed value cannot be rebuilt on this route; if an input is a `limitation` that still has a `target` (for example a paging limitation), rebuild the value from that target and carry the input's limitation note into the plan. Cite: pack id, route, and v2 field name. If the item has a `graphql_alternative` field, show it as additional guidance text alongside the REST mapping; do not treat `graphql_alternative` as containing GP-n ids.
- `limitation` — Show `limitation.note` in full (kind + reason + guidance). Apply a partial mapping only if the item's `target` field gives one. Look for `GP-n` identifiers (e.g. `GP-2`, `GP-7`) inside `limitation.note` itself and in the item's `pointer` field; if found, follow the entry into `graphql-parity.md` and report the guidance. If `limitation.note` or `pointer` says "No vetted GraphQL example is available", stop and report that no vetted alternative exists — do not guess. Do not look for GP-n ids in `graphql_alternative`; that field is additional guidance text only and does not carry GP-n ids.
- `confirmed_via_graphql` — Follow the GP-n identifier found in the item's `pointer` field into `graphql-parity.md`; state "public, undocumented; evidence is source-observed". Show any `graphql_alternative` text as additional context.
- `not_on_route` — Switch to the route that has the item (re-load that route file) or report why switching is not possible.
- No matching pack item — Report the parameter or field as "not covered". Never guess a mapping.

**5.6 Choose the target code style and the implementation choice:**

The customer decides how the new code is written; you recommend a default and show the alternatives. Do this once for the whole codebase (per language), not per site.

1. **Record how the customer calls Zuora today**, per language: raw HTTP (fetch, axios, requests, HttpClient, curl) or a Zuora SDK. The v2 SDK exists only for Java: a Java site uses either the v2 client directly (`com.zuora.sdk.ZuoraClient`) or `quickStartApi()` of the unified client `com.zuora.ZuoraClient`.
2. **Get evidence about SDK support before saying anything about it, and before choosing any default.** If the `mcp__zuora-mcp__zuora_codegen` tool is available in this session, you MUST call it, even when every site is raw HTTP: ask it which languages it supports, once per language the customer uses, and whether its SDK exposes the target operation of the chosen route (name the language and the operation; never assume a list of supported languages, and never state SDK availability for a language from memory). That the v2 SDK exists only for Java says nothing about the public SDKs: never conclude that a public SDK does not exist for a language from it, and never skip the call because the customer uses raw HTTP. If the tool is not available, rejects the language, or does not cover the operation, record that result: the SDK option for that language is "unconfirmed".
2b. **Shared wrappers:** when sites call Zuora through a customer helper or wrapper class (one place that builds headers, sends requests and parses errors), propose the change to the wrapper once, in the block of the first site that uses it, and let the other sites refer to that block; the cards still list every site.
3. **List the options for each language:** (a) raw HTTP code from the pack route (own HTTP code), possible in any language because the pack is written in wire-level names; (b) the SDK, only when step 2 confirmed it (use the tool's answer ONLY for SDK method names, model classes and call shape; the field mapping, transforms, dispositions, limitations and error handling still come from the pack item and never from the tool output). For a Java customer the SDK target is the unified client `com.zuora.ZuoraClient` constructed with the same credentials and environment, using its v1 accessors and `objectQueriesApi()`; the v2 `quickStartApi()` chain is what is being replaced.
4. **Names rule:** in proposed code use only SDK class, model and method names that (a) appear in the customer's own code and still exist in the target SDK (for example the client class and its builder) or (b) were returned by the code generation tool in this run. Model accessors are never carried over from the customer's v2 code: every getter, setter or property you use on a response model must be a field returned by the tool's model details for that model; when you use a getter on a nested or referenced model (for example the item type of a list response, a memo, a contact), request that model's details too before using it, instead of marking the getter "to be confirmed". A v2 accessor with no field in the target model (for example custom fields) is not written as a call; rebuild it as the pack item says (raw HTTP for that one value if needed) and list it as an open decision. Where a name would be needed and is neither, write a comment `// SDK method to be confirmed: <operation and HTTP path>` and give the same call as complete raw HTTP code; never guess a name or a model rename, and never keep imports of v2 SDK classes the proposed code no longer uses.
5. **Default = keep the customer's current style:** raw HTTP callers stay on raw HTTP; SDK callers stay on the SDK.
6. **Ask once** with `AskUserQuestion` when more than one option exists for a language, showing the default, the alternatives and their consequences (for an SDK caller, the SDK and raw HTTP, with the changes callers will see for each). State the consequences symmetrically and only what the pack and the tool support: computed fields, limitations and enum changes must be rebuilt in the customer's code under every option; never say that existing model classes or field names stay, or that fields map one-to-one, unless every item the code uses is a plain rename. When the SDK option for a language is "unconfirmed", only raw HTTP exists: ask no question and write the "No question" line. If you cannot ask or get no answer, proceed with the default and record it under "Open decisions" in the plan. Always write the "Implementation choice" section of the plan: the style chosen per language, why, the alternatives, and the evidence from step 2. The question is always the choice of implementation style for the language (use the Zuora SDK, or write your own HTTP code); details such as which client class to construct are consequences of the SDK option, not separate questions. In the same section write a "Question for the customer" block with the question exactly as you asked it (or would have asked it, when you cannot ask): the question, the default, each option, and the consequences of each. If you asked and got an answer, add the answer. If only one option exists for a language (for example the tool does not support it), write "No question: only raw HTTP is available for <language> because <reason>" for that language.
7. **SDK style, once chosen or defaulted, is built from the code generation tool whenever it is available.** Do not fall back to raw HTTP while the tool is available and covers the operation. For each site call the tool for the class and method of the target operation and for the response models, then write the calls with exactly the names and call shape it returns (for a Java customer, the unified client's `objectQueriesApi()` accessors), keep the customer's client construction, credentials and environment constant (for example the same `ZuoraEnv` value, or the same base URL variable) exactly as in their code, and never copy an environment, host, credential or other example value from the tool's sample code, and show the model types the callers now receive. Write each SDK call in the call shape the tool's coding rules give (for Java: the accessor, then the exact operation name the tool returned, then each parameter as a chained setter such as `.expand(...)`, `.filter(...)`, `.cursor(...)`, ending in `.execute()`), never as a positional argument list; parameters that are arrays in the tool's details (`expand`, `filter`, `sort`, `fields`) are passed as lists with one value per element (`.expand(List.of("invoiceowner", "rateplans"))`, never one comma-joined string or a bare string), and every value is spelled exactly as the pack gives it (for example the subscription number is filtered with the public `name` field, never a v2 or accessor name); never alter an operation name (for example `queryAccountByKeyApi`, not `queryAccountsByKeyApi`). Use the tool's answer only for names, models and call shape; every value, bound, parameter mapping, transform, limitation and error-handling change still comes from the pack item and never from the tool output (when the two disagree, for example on a page-size bound, follow the pack, which is aligned with the API reference; the API reference is the source of truth, never the tool). For every operation you used, compare the bounds and parameter facts the tool returned with the pack item; list each difference under "Tool and pack disagreements" in `## Open decisions and limits`, naming the operation, what the tool said and what the pack says. In the SDK request builders, passing `null` for the cursor is the same as passing no cursor: write the first-page call that way and do not raise it as an open question. Use raw HTTP for an SDK caller only when the tool is unavailable, does not support the language, or does not cover the operation, and say which in the plan.
8. **GraphQL rows** (an item with a `GP-n` pointer or `confirmed_via_graphql`): the code generation tool does not cover GraphQL. Do not call it for these rows; always write raw HTTP (a POST of the vetted document from `graphql-parity.md`) in the customer's language, and say so in the plan.
   **SDK call checklist (run it for every SDK call before you write the file):**
   - the operation name is exactly what the tool returned for that operation, including any suffix such as `Api` (copy it, do not retype it from memory), and after writing the file you re-read every SDK call against the tool's answer, one by one, before moving on;
   - parameters are chained setters ending in `.execute()`, and the first-page call omits the cursor (a `null` cursor is the same as none);
   - `expand`, `filter`, `sort` and `fields` are lists with one element per value, every value spelled exactly as the pack's route file and translation tables give it (public field names, documented expand names, the pack's `Status`/`Posted` style values);
   - a filter built from a customer-supplied key follows the pack's key rule for both forms of the key (a 32-character hexadecimal id and a number or name);
   - every getter and type on the result is a field or model the tool's model details returned;
   - the client construction, credentials and environment constant are the customer's own.
   Shape only (placeholders, not values to copy): `ExpandedX x = client.objectQueriesApi().<operationFromTool>(<pathParams>).expand(List.of("<public expand>")).filter(List.of("<PublicField>.EQ:<value>")).cursor(<cursorOrOmit>).execute();`
9. Read the customer's SDK property names by convention: SDK models are generated from the v2 schema, so `getBillCycleDay()` and `bill_cycle_day` are the same v2 field. Look the field up in the route file under its wire name.
10. Never put tool names or tool output text in the plan or in generated code; record only the result (for example "SDK method names confirmed with the plugin's code generation guidance"). Where the tool was unavailable, write: "No SDK guidance available for <language>/<operation>; SDK option unconfirmed."

### Step 6: Plan content: one card per operation, then the sites

Group the analyzed sites by pack id and route. Every group is one **migration card**, however many call sites it has (14 calls to one endpoint give one card listing 14 sites, not 14 blocks). Everything that depends on the operation goes in its card, once; the per-site block holds only what is specific to the site (facts, the diff, open questions).

**Card status: exactly one value per card, with no qualifier such as "(with limitations)" and no per-site statuses; when the card's sites differ, the card takes the most severe one (`Not available in v1`, then `Needs human`, then `Likely`) and its one-line reason names the site that decides it. Use exactly these values; never `Verified`, which only `/zuora-v2-migration-verify` sets after a sandbox parity run this skill does not perform:**
- `Likely`: every parameter and field this customer uses has a confirmed mapping, or a limitation that states a mapping, and no decision is open.
- `Needs human`: a used item is a limitation without a stated mapping, is GraphQL-only, or the route requires an input the old call did not send, or anything is not covered or unresolved.
  - A field the code only forwards without reading is still a used item; if its mapping is GraphQL-only or a limitation, the card is `Needs human` and the open decision asks whether any caller reads it (the answer can lower the status).
  - A sub-field of an object (for example `bill_to.work_email`) is covered only when a pack item names it; the object's own item covers the object, and its limitation note covers a sub-field only when the note names it. Otherwise list the sub-field under "not covered" and use `Needs human`.
- `Not available in v1`: a used item has no public equivalent on any route.

**Card heading:** `### Card <pack id>: <v2 method> <v2 path> → <public route>`, where the v2 method and path are copied from the pack index card's `v2` field (for example `/invoice_items` and `/billing_documents` with underscores, prefixed with the base the customer's code uses, such as `/v2`), never rebuilt from the public path (which uses hyphens).

**Each card contains:** status with one line of why; route and rationale; occurrences (all sites); the request table (what the customer sends and what replaces it), the public path and steps, headers and auth, required inputs the old call did not send; the response table (what the customer reads and where it lives now), the v2 response fields the customer does not read (a compact list of v2 names from the route file), the public response fields on the route that the customer does not read today (a compact list from the route file, pointing to the API reference for the complete schema), computed or unavailable fields; and the differences in input, output, paging and errors. The content rules below say how to fill each part.

**URL/params/auth change:**
- New endpoint (path, method) — from the route file's `steps[]` array.
- Renamed parameters — from confirmed request items only; cite v2 field and `target.param`.
- Header and auth changes — read the route file's `unsupported[]` array. For each item with `kind: header_not_supported`, quote or paraphrase its `note` and cite the v2 item name. Do not state generic auth steps (bearer token names, OAuth flow names, specific header names) that are not stated in the `unsupported[]` note. If no `header_not_supported` item exists in the route file, do not add header guidance.

**Response-parsing changes:**
- Renamed fields (confirmed renames from `target.transform`)
- Type coercions (confirmed type changes)
- Enum value mappings (confirmed enum maps from `target.transform`)
- Computed/removed fields (`not_on_route`)
- `confirmed_via_graphql` fields (with GP-n pointer from `pointer` field and caveat)

**SDK and client calls:** The pack describes REST routes (and vetted GraphQL), not SDK methods. For a site that uses an SDK, follow step 5.6: use SDK method names only when `mcp__zuora-mcp__zuora_codegen` returned them for that language and operation; otherwise propose the equivalent REST call (and say the customer's SDK version must expose the same public operation). Never invent SDK method names. Never add a paging loop the customer's code does not already have: if the route pages (cursor) and the site does not loop, report that results may be truncated and show the loop as an optional suggestion.

**Public base URL:** The public APIs (v1 REST, Object Query REST and GraphQL) use the same base URL as v2 for each environment (production, sandbox, region). Keep the customer's configured base URL variable or host exactly as is and change only the path as the route file gives it; do not invent or change a host and do not raise a base-URL question.

**Pagination loop changes:**
- Cursor and page-size parameter names — from the confirmed request items for the cursor and page-size parameters; cite v2 parameter, `target.param`, and `target.transform` text exactly.
- Page-size bounds — from the `invalid_page_size_or_cursor` error case in `errors.cases` only; quote the bounds stated there. Never replace the pack's bounds with a bound, default or limit reported by the code generation tool or any other source, and never describe the change as the public bound being lower than v2's: the tool's value is only a disagreement to list. Do not claim bounds not stated in the route file. If the customer's code sends a value outside those bounds, never pass it through unchanged: clamp it to the stated bound in the proposed code and flag the change in the plan.

**Inputs the public route requires that the customer's call does not send:**
When the route file (`steps[]`, `errors.cases` or an item note) says the public call needs an input the v2 call did not send, report it under "Open decisions" with the options the pack gives. Never leave a request that the route rejects in the proposed code (no unfiltered call, no placeholder such as `<FILTER>` or a TODO instead of a filter): add the smallest required argument that carries the filter value the route file names (for example the parent id), say in the code comment and in the plan that every caller must change, and list the other options the pack gives as the open decision. The proposed file always contains a live call for every site: options for the customer go in the plan (and short comments), never as the only code, and a function is never replaced by commented-out alternatives.
- Paging model — describe only what the confirmed items and error cases state. Do not assert paging model differences (e.g. offset vs cursor) that are not stated by the route file items.

**Error-handling changes:**
Write the six situations once per route in the plan section "Error handling by route" (not once per card or site); a card writes only the differences specific to its operation and refers to the route section. For the chosen route's `errors.cases`, report all six situations:
- `not_found`
- `invalid_filter_or_enum`
- `invalid_page_size_or_cursor`
- `malformed_identifier`
- `authorization_failure`
- `server_error_retry`

For each: state v2 behavior, public route behavior, and the migration note from the pack. Where the route file says "not documented", report that as-is.

**Limitations and guidance:**
Show each `limitation` note in full (kind, reason, guidance, any GP-n pointer in `limitation.note` or `pointer`) once, in the plan section "Limitations"; a card names its limitations and refers to that section. Do not repeat the same text per card or per site.

**Downstream consumers affected:**
List the consumers identified in Step 4 that will need updates, in the per-site block of the site that feeds them.

### Step 7: Write outputs

Create the output directory (confirmed in Step 1):

1. `<outdir>/v2-migration-plan.md` already exists (copied from the template in Step 2). Fill it in place section by section with the edit tool, and read it back at the end to check that no template section title was renamed, merged or dropped. If the file does not exist, copy the template now with the shell tool. If no shell tool works in this session (the scanner could not run either), read the template file and create the plan with the write tool from the template's complete text, every section title and table header kept exactly, then fill it in; a plan written from scratch, or from a summary of the template, is wrong. Read the template first and keep its section titles exactly and in its order (you may add sections, never rename, merge or drop one); fill every section; include proposed diffs inline.

2. Copy `<outdir>/v2-inventory.json` from the scanner output (already written there by the scanner in Step 2).

3. For a handoff site write no diff and no file under `<outdir>/proposed/`: its "Per-site changes" block holds the facts and the open questions, and its "Proposed diff" says "None: see Handoff pack". Write one `### Handoff pack: <system>, <export file>` block under `## Handoff packs` for each system or export file, filled from the template: where to change it (the step, action or request named as the export shows it; "to confirm in <system>" for anything the export does not show), the v1 request from the card, the field mapping table limited to the fields that tool reads (copied from the card), a "What we still need from you" block that names, in the tool's terms, what to send back when the export does not show which fields the tool reads ("Nothing" otherwise), numbered steps in the tool's own terms, and a test checklist with what to run and what result means it is correct. Every pack starts with the status line "Unverified. Written from the export file; nothing was tried in <system> and nothing was rewritten." Write "None" under `## Handoff packs` when there is no handoff site. For all other sites: show proposed diffs inline in the plan, in the "Per-site changes" block of each site, using language-appropriate diff format (do NOT apply them to the customer repo). Fill the "Migration cards" section first (one `### Card <pack id>` per distinct operation and route), then the per-site blocks, then the summary table of cards at the top.

4. The plan MUST contain these two headings, spelled exactly, even when no question could be asked or nothing is open (write "None"): `## Implementation choice` (step 5.6) and `## Open decisions and limits`. Keep them where the template puts them (do not move them to the end). "Open decisions and limits" lists: every decision still open for the customer, every parameter or field that could not be mapped (with the reason), and the statement that nothing was verified against a tenant. Repeat the open decisions and the not-verified statement in your final message to the user.

Proposed diffs may reference small helper functions the customer must write only when the pack rule needs them (for example a computed field); name each helper, state which pack item it implements, and never leave an unnamed placeholder.

**Output files:** write proposed files only with `Write` under `<outdir>/proposed/` (same relative paths as the customer's files) and fill the plan with `Edit`; never use `Edit` or `Write` on a path inside the customer's codebase.

**Do NOT edit any file in the customer's codebase** unless the user explicitly asks (use `AskUserQuestion` to confirm before any write outside the output directory).

### Step 8: Coverage summary and completion check

Before reporting, read the plan file back and confirm it still has the template's own section titles, in particular `## Migration cards`, `## Error handling by route`, `## Limitations`, `## Per-site changes`, `## GraphQL pointers`, `## Handoff packs`, `## Implementation choice` and `## Open decisions and limits`, and that there is exactly one `### Card <pack id>` per distinct pack id and route among the sites, each listing all of its sites and carrying one status value (if any is missing or renamed, restore it from the template now), that, when the code generation tool was used, `## Open decisions and limits` has a "Tool and pack disagreements" entry (list each difference, or write "None"), that `## Open decisions and limits` contains the sentence "Nothing in this plan was verified against a tenant." (a note to "verify on your tenant" in some other place does not replace it), that, when the code generation tool is available, you called it before writing any SDK call (if you did not, call it now and fix every SDK name before reporting), that no request in the proposed code sends a numeric value outside a bound the route file states, that every site of the scanner inventory has a block or a needs-human entry, that every handoff site has a pack under `## Handoff packs` (with the Unverified line, the field mapping and a test checklist) and no file under `proposed/`, and that the scanner actually ran (if `node` was unavailable and the scanner could not run, say so first in the report and in the plan, and mark the coverage as unverified).


After writing outputs, report counts:

| Category | Count |
|---|---|
| Sites matched to pack ids | |
| Migration cards (one per v2 operation) | |
| Sites with at least one limitation | |
| Parameters / fields not covered (no pack item) | |
| Sites needing human review (needs-human) | |
| Undetected risk entries (iPaaS, dynamic URLs, wrappers) | |
| Languages where SDK calls cannot be detected (`languages_without_sdk_pattern`) | |

---

## Hard rules

1. **Never rewrite from memory.** Every proposed change must cite the pack id, route, and item field that authorizes it.

2. **GraphQL query text comes only from `graphql-parity.md`.** Never write or paraphrase a GraphQL query from memory. When an item points to a `GP-n` entry, copy that entry's vetted document and variable bindings VERBATIM into the plan's "GraphQL pointers" section and into the proposed diff, changing only what the entry itself says to substitute (its variable bindings, and the page-size literals when the entry says to replace them with the customer's page size; keep every literal the entry says to keep, for example a root page size that must stay 1); state the entry id and quote the entry's own substitution rule. If the entry does not fit the site (for example a different filter), report that and stop: do not edit the query shape. For nested items that the REST expansion returns only the first page of, the supported fallback is a separate list call on the items route filtered by the parent id, with the filter and paging the route file states; offer it as an option in the open decisions, do not write GraphQL for it.

3. **Generated customer code and diffs contain only Zuora public REST/GraphQL calls.** Never embed MCP tool names (`mcp__zuora-mcp__*`, `query_objects`, `get_account_summary`, `manage_*`, `ask_zuora`, `zuora_codegen`) in customer-facing code, diffs, or the plan document.

4. **No tenant calls.** This skill does not connect to a Zuora tenant and does not verify parity.

5. **`zuora_codegen` and `ask_zuora` have two allowed uses only:** clarifying public contract details the pack does not answer, and (`zuora_codegen`) SDK method names, model classes and call shape for SDK users in step 5.6. They must never override a pack disposition, never change a field mapping, transform, limitation or error-handling change, and never promote a `limitation` to `confirmed`.

6. **Stop and ask when unsure.** List the uncertain items explicitly and use `AskUserQuestion` before proceeding.

7. **Do not claim a rewrite is "verified".** Use only the pack vocabulary: `confirmed` (applies cleanly) or `limitation` (applies with noted constraints).

8. **GP-n pointers live in `pointer` and `limitation.note`, not in `graphql_alternative`.** When looking for GraphQL parity references, read the item's `pointer` field and the text of `limitation.note`. The `graphql_alternative` field is additional human-readable guidance text; it does not carry GP-n ids and must not be searched for them. Auth and header guidance must come from the route file's `unsupported[]` items (`kind: header_not_supported`); do not state header names, token types, or OAuth flow steps that are not written in those notes.
