# v2 → Public API Parity Report

**Generated:** {date}
**Sandbox host:** {host}
**Plan checked:** {plan path}
**Read-only requests sent:** {n} (GET only)

> This report can contain record values from your sandbox. Do not commit it.

---

## Result per card

| Card | Verdict | Records compared | Fields matched | Fields mismatched | Fields skipped | New card status |
|---|---|---|---|---|---|---|
| {pack_id} | {verified / verified_with_limits / partial / mismatch / error} | {n} | {n} | {n} | {n} | {Verified (verified only) / unchanged / Needs human} |

`Verified` means: every field your code reads was compared and matched on every sampled record. It does not mean the rewritten code was run.

---

## Mismatches

| Card | v2 field | v2 value | Public value | Likely cause |
|---|---|---|---|---|

---

## Skipped fields (check these by hand)

| Card | v2 field | Reason |
|---|---|---|

---

## Public values v2 did not return

| Card | v2 field | Public value |
|---|---|---|

---

## Cards not checked

| Card | Reason |
|---|---|
