---
name: zuora-v2-migration-verify
description: Check a v2 migration plan against a Zuora sandbox with read-only requests and mark the cards whose mapping matched as Verified
argument-hint: "[plan=<path to v2-migration-plan.md>]"
allowed-tools: [Read, Write, Glob, Grep, Bash, AskUserQuestion]
---

Codex-only path resolution: When an instruction refers to `${CLAUDE_PLUGIN_ROOT}`, treat it as the root of this installed plugin. In Codex, resolve that root as the ancestor directory containing `skills/`, `references/`, and `.codex-plugin/`.

## Input

The migration plan to check: $ARGUMENTS

Expected format: `plan=/path/to/v2-migration-plan.md` (default: `./v2-migration/v2-migration-plan.md`). The plan is the output of `/zuora-v2-migration-design`.

## What this skill does

For each migration card it reads the same records through the v2 API and through the public route in a **sandbox**, and compares **only the fields your code reads**, using the mapping of the shipped pack. A card becomes `Verified` only when every field your code reads was compared and matched on every sampled record.

It checks that the pack's mapping holds on your sandbox data. It does not run the rewritten code in your repository.

## Hard rules

1. **Sandbox only, read only.** The comparison tool sends GET requests only and refuses a production host. Never use `--allow-non-sandbox`.
2. **Never handle secrets in chat.** Credentials come only from environment variables the user exported in their own terminal: `ZUORA_PARITY_BASE_URL` (a sandbox host), and either `ZUORA_PARITY_BEARER_TOKEN` or `ZUORA_PARITY_CLIENT_ID` with `ZUORA_PARITY_CLIENT_SECRET`. Never ask the user to paste a secret or a token into the conversation, never write one to a file, never print the environment. If the variables are not set, tell the user how to set them (below) and stop.
3. **Confirm before calling.** Show the exact request list (`--dry-run`) and wait for the user's yes before any request is sent.
4. **Tenant data stays local.** The report can contain record values. Tell the user not to commit it.
5. **Do not edit the pack or the customer's code.** A mismatch is reported, not fixed.
6. **Use only the vocabulary of the report.** `Verified` is set only for a card whose verdict is `verified`.

If the environment is not set up, give this and stop:

```bash
export ZUORA_PARITY_BASE_URL="https://rest.apisandbox.zuora.com"   # your sandbox host
export ZUORA_PARITY_CLIENT_ID="..."                                  # an OAuth client of your sandbox (read-only role)
export ZUORA_PARITY_CLIENT_SECRET="..."
```

## Workflow

### Step 1: Read the plan

Read the plan (default `./v2-migration/v2-migration-plan.md`; if it does not exist, stop and tell the user to run `/zuora-v2-migration-design` first). Take the cards from the "Migration cards" section: pack id, route, status, the request table, and the response table with the v2 fields the code reads. The output directory is the plan's directory.

### Step 2: Choose the cards

Check every card whose status is `Likely` or `Needs human`. Leave out, and say so in the report:
- a card with status `Not available in v1`;
- `billing_documents.list` (its route is three requests and the tool does not compare it yet);
- any field the pack marks as a limitation, GraphQL-only or not on the route (the tool lists these as skipped).

### Step 3: Sample records

Ask the user (`AskUserQuestion`) how to pick records:
- the user gives 1 to 3 keys per operation (an account id or number, an invoice id, a subscription key); or
- you read the first page of each list read-only and take the first ids (the dry run shows these requests too).
Prefer records the code actually handles. Sandbox data is often small; compare what exists.

### Step 4: Write the parity plan

Write `<outdir>/parity-plan.json` with one entry per checked card:

```json
{ "cards": [ { "pack_id": "accounts.get", "route": "public_oq",
               "used_fields": ["account_number", "remaining_invoice_balance"],
               "samples": [ { "key": "<id or number>" } ],
               "v2":     { "params": { "expand[]": ["bill_to"] } },
               "public": { "params": { "expand[]": ["billto"] } } } ] }
```

`used_fields` are the v2 field names from the card's "Response: what you read today" table. `v2.params` are the parameters your code sends today; `public.params` are the replacement parameters from the card's request table (public expand names, `Status.EQ:Posted` style filters). For list cards use `limit` (records per page) instead of `samples`, and a filter for operations that require one (invoice items need `filter[]` on both sides). Never write a credential into this file.

### Step 5: Show the requests and get confirmation

Run:

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/compare-parity.js" --plan <outdir>/parity-plan.json --dry-run
```

Show the printed request list, the host, and the call cap (default 40 requests). Ask with `AskUserQuestion`: "Send these read-only GET requests to <host>?" Stop unless the answer is yes.

### Step 6: Run the comparison

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/compare-parity.js" --plan <outdir>/parity-plan.json --out <outdir>/parity-report.json
```

If the tool reports a missing variable or a refused host, report it and stop. Do not retry with other settings.

### Step 7: Interpret each card

- `verified`: every field the code reads matched on every sampled record. Set the card's status to `Verified` in the plan and say which fields and how many records.
- `verified_with_limits`: every field that could be compared matched on every sampled record, and the only fields skipped are limits the pack states itself (a limitation, GraphQL only, not on this route). Say which fields matched and how many records, and list the limit fields with the pack's own note. The card's status stays as the design plan set it (never `Verified`): the limit fields are exactly what the plan already says needs a decision.
- `partial`: some fields matched, some were skipped for a reason other than a stated limit (a nested object, a transform the tool does not check, an expand that was not requested, or a field without a pack item), or nothing could be compared, or one sample record could not be read (the report lists the failed request). The status stays as it was. List the skipped fields and the reason of each; the customer checks those by hand.
- `mismatch`: a field differed. Set the card to `Needs human`, show the v2 value and the public value, and give the likely cause: a public expand the request did not send, a limitation, a data difference on that record, or a possible error in the pack mapping. If it looks like a pack error, say so and name the pack item (the card's pack id and the v2 field) so that the maintainers can look at it.
- `error`: a request failed. Show the status codes and stop for that card.
- A note "v2 returned nothing, public returns a value" is information: after the migration the code will see a value it did not see before.

### Step 8: Write the outputs

1. Fill `${CLAUDE_PLUGIN_ROOT}/templates/v2-v1/parity-report.md` into `<outdir>/parity-report.md`: the host, the number of requests, one row per card (verdict, records, fields matched, mismatched, skipped), the mismatches with both values, the skipped fields with reasons, and the cards left out with the reason.
2. Update the card statuses in `<outdir>/v2-migration-plan.md` (only the status line and the summary table; change nothing else).
3. Tell the user: the report contains tenant data and must not be committed; `Verified` means the mapping matched on the sampled sandbox records for the fields the code reads, not that the rewritten code ran; and any card that is not `Verified` still needs the checks listed for it.
