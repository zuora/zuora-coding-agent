# CPQ JavaScript Component Registration

After implementing Quote Studio LWC or Aura components, register them in CPQ X.

Do not register Quote Studio hooks or events in Salesforce LWC `*-meta.xml` files. Do not add `<target>`, `<targets>`, `<targetConfig>`, `<targetConfigs>`, or `<hook>` entries for CPQ behavior. LWC metadata should stay standard Salesforce metadata; Quote Studio hooks are public `@api` methods in JavaScript, and CPQ component registration is handled in CPQ X Custom Component Settings.

## Registration path

Navigate to `Zuora Config > Quote Studio Settings > Custom Component Settings`, create a new component, and set:

- Component Namespace, if applicable.
- Component Name.
- Component Type: LWC or Aura.
- Component Event Action for events that require registration.
- Use as Headless Component for hook-only components.
- Active.
- Sort Order.
- Optional title and image static resource.

If an event action is missing after a package upgrade, add the picklist value to `zqu__Component_Event_Action__c` on `zqu__Add_on_component_registration__c`.

Source: https://docs.zuora.com/en/zuora-cpq/manage-subscriptions/customize-cpq-x/customize-quote-studio-with-extensibility-framework/register-custom-component-in-cpq-x
