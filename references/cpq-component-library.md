# CPQ Component Library Reference

Use this reference for legacy CPQ customizations using Component Library, global Apex classes, Visualforce pages/components, and plugin-interface patterns.

## Guidance

- Treat the official Zuora docs below and examples bundled in this codebase as the signature authority for Component Library classes, global Apex methods, plugin interfaces, Visualforce components, attributes, parameters, and return types.
- Generated class names, method names, method parameters, return types, interface implementations, and Visualforce attributes must match those docs/examples exactly. Do not invent overloads or alternate signatures. If the required signature is not present in this reference, stop and ask for the exact source or state the assumption before generating code.
- Prefer supported global Apex methods over direct mutation of managed package internals.
- Keep CPQ namespace handling explicit. Managed package objects usually use the `zqu__` prefix.
- For Visualforce customizations, place pages under `force-app/main/default/pages/` and reusable components under `force-app/main/default/components/`.
- Avoid hardcoded IDs, tenant URLs, credentials, and environment-specific assumptions.
- Bulkify Apex when logic can run against multiple quote or charge records.

## Build outputs

- Apex classes: `force-app/main/default/classes/`
- Visualforce pages: `force-app/main/default/pages/`
- Visualforce components: `force-app/main/default/components/`
- Notes: `docs/cpq-agent/<task-slug>/registration.md`

## Source docs

- https://docs.zuora.com/en/zuora-cpq/development-resources/zuora-cpq-component-library
- https://docs.zuora.com/en/zuora-cpq/development-resources/overview-of-zuora-cpq-development-resources
