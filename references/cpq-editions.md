# Zuora CPQ editions and terms

Canonical definitions for every CPQ skill in this plugin. Skills cite this file instead of re-explaining the editions.

## Editions

**Zuora Quotes** is the product (the `zqu` Salesforce managed package) and contains both editions: legacy CPQ (CPQ 9) and CPQ X, the latest CPQ. Package releases inside CPQ X carry version numbers such as 10.30 and 10.58. "Zuora Quotes" is therefore not a synonym for CPQ X.

| Edition | Also called | Quoting UI | Customized with |
|---|---|---|---|
| Legacy CPQ | CPQ 9 | Visualforce pages | Apex, Visualforce, Component Library, `zQuoteUtil` global methods, controller extensions, plugin interfaces |
| CPQ X | none | Quote Studio | Apex (global classes such as `zQuoteUtil`, `QPlanReader`, `QPlanWriter`, `QPlan`, `QCharge`, and plugin interfaces), plus Quote Studio LWC headless and sidebar components, hooks and events, `quoteState`/`pageState`/`metricState`, `ZQFClient` (package >= 10.58) |

- **Quote Studio** is the main quoting UI of CPQ X, not another name for it. CPQ X is the edition; Quote Studio lives inside it and is where users build quotes. Say "CPQ X" for the edition and "Quote Studio" for the quoting UI and its hooks and events.
- **Apex works in both editions.** CPQ X is built on Salesforce, so Apex, the global classes and the plugin interfaces are valid in CPQ X as well as in legacy CPQ. Only Visualforce pages and the Component Library belong to legacy CPQ.
- Live quote operations fail with `CPQX_NOT_ENABLED` when CPQ X is not enabled for the org. `UNKNOWN_ENDPOINT` is a different cause: the installed package does not include the quote API.
- "CPQ" with no qualifier means the product family, not an edition.

## Which skill serves which edition

| Skill | Edition | Capability |
|---|---|---|
| `zuora-cpq-apex-design`, `zuora-cpq-apex-build` | Both (Apex); legacy only (Visualforce, Component Library) | Design or generate Apex and Visualforce customization code |
| `zuora-cpq-js-design`, `zuora-cpq-js-build` | CPQ X | Design or generate customization code |
| `zuora-cpq-migration-design` | Legacy to CPQ X | Plan a move of Visualforce, Component Library and controller-extension customizations to Quote Studio hooks and events; Apex that works in both editions is kept |
| `zuora-cpq-validate`, `zuora-cpq-review` | Both | Validate or review code for either edition: Visualforce and the Component Library follow the legacy rules, Quote Studio LWC follows the CPQ X rules, and Apex follows the Apex rules in both |
| `zuora-cpq-context` | Both | Routes a CPQ request to the right skill |
| `zuora-cpqx-quotes` | CPQ X only | Operate live quotes in the user's org through the `manage_cpqx_quotes` tool |

## Edition check

Before acting, work out the edition from the request or the repo (Visualforce pages mean legacy; Quote Studio LWC hooks mean CPQ X; Apex and `zQuoteUtil` do not tell the edition, both use them). If it is unclear, ask which edition the org uses.

- A request for CPQ X output (LWC hooks, ZQFClient, live quotes) in a legacy org cannot be met: say so, and do not generate it or retry.

## Writing rules

- Prose: "CPQ X" (not "CPQX", "CPQ-X", "CPQ Quote Studio"). Legacy: "legacy CPQ".
- Keep literal identifiers exactly as they are: `manage_cpqx_quotes`, `CPQX_NOT_ENABLED`, the `CPQX` feature name.
