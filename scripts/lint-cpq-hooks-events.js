#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const { loadFieldCatalog, indexFieldCatalog } = require('./lint-cpq-apex');
const REF_DIR = [
  path.join(__dirname, '..', 'zuora-coding-agent', 'references'),
  path.join(__dirname, '..', 'references')
].find((dir) => fs.existsSync(dir));
const ZQF_CLIENT_MIN_VERSION = '10.58';
const ZQF_CLIENT_HELPERS = new Set([
  'getQuote',
  'getQuoteField',
  'getSubscription',
  'getProductTimelines',
  'getTimeline',
  'getVersions',
  'getRatePlans',
  'getRatePlansByAmendmentType',
  'getUpdatedRatePlans',
  'getRemovedRatePlans',
  'getOriginalRatePlans',
  'getLatestVersion',
  'getVersionByEffectiveDate',
  'getCharges',
  'getCharge',
  'getTiers',
  'getTier',
  'getRampIntervals',
  'getActiveRampInterval',
  'getRampIntervalByDate',
  'getAmendments',
  'getAmendment',
  'getAmendmentRecord',
  'getAmendmentType',
  'updateQuote',
  'updateQuoteField',
  'addProducts',
  'addProductsInInterval',
  'addCharge',
  'addChargeInInterval',
  'updateCharge',
  'updateChargeInInterval',
  'updateChargeField',
  'updateChargeFieldInInterval',
  'removeCharge',
  'removeChargeInInterval',
  'updateTier',
  'updateTierInInterval',
  'updateTierField',
  'updateTierFieldInInterval',
  'updateProduct',
  'updateProductInInterval',
  'removeProducts',
  'removeProductsInInterval',
  'removeProduct',
  'removeProductInInterval',
  'updateCharges',
  'updateChargesInInterval',
  'updateRatePlans',
  'updateRatePlansInInterval',
  'updateAmendments',
  'updateAmendmentsInInterval',
  'updateTiers',
  'updateTiersInInterval',
  'updateProducts',
  'updateProductsInInterval'
]);

function loadCatalogs() {
  const hooks = JSON.parse(fs.readFileSync(path.join(REF_DIR, 'cpq-js-hooks.json'), 'utf8'));
  const events = JSON.parse(fs.readFileSync(path.join(REF_DIR, 'cpq-js-events.json'), 'utf8'));
  return { hooks, events };
}

function collectFiles(targets) {
  const files = [];
  function walk(p) {
    if (!fs.existsSync(p)) return;
    const st = fs.statSync(p);
    if (st.isDirectory()) for (const e of fs.readdirSync(p)) walk(path.join(p, e));
    else if (p.endsWith('.js') || p.endsWith('.js-meta.xml')) files.push(p);
  }
  targets.forEach(walk);
  return files;
}

function lineOf(text, index) {
  return text.slice(0, index).split(/\r?\n/).length;
}

function lintMetadataText(text, file) {
  const issues = [];
  const patterns = [
    {
      re: /<targetConfigs?\b/i,
      message: 'do not add targetConfig/targetConfigs to LWC meta XML for Quote Studio components; keep CPQ hook/event registration in CPQ X setup notes'
    },
    {
      re: /<target\b/i,
      message: 'do not add Salesforce targets to LWC meta XML for Quote Studio headless components; use CPQ X Custom Component Settings for registration'
    },
    {
      re: /<hook\b/i,
      message: 'do not add Quote Studio hook entries to LWC meta XML; hooks are @api methods in the component JavaScript'
    }
  ];

  for (const { re, message } of patterns) {
    const match = text.match(re);
    if (match) {
      issues.push({
        severity: 'error',
        rule: 'EXML090',
        file,
        line: lineOf(text, match.index || 0),
        message
      });
    }
  }
  return issues;
}

function collectApiProperties(text) {
  const props = new Set();
  const propRe = /@api\s+([A-Za-z_$][\w$]*)\s*(?:[;=]|$)/g;
  let m;
  while ((m = propRe.exec(text))) props.add(m[1]);
  return props;
}

function compareVersions(left, right) {
  const leftMatch = String(left || '').match(/\d+(?:\.\d+)*/);
  const rightMatch = String(right || '').match(/\d+(?:\.\d+)*/);
  if (!leftMatch || !rightMatch) return null;
  const leftParts = leftMatch[0].split('.').map(Number);
  const rightParts = rightMatch[0].split('.').map(Number);
  const max = Math.max(leftParts.length, rightParts.length);
  for (let i = 0; i < max; i++) {
    const l = leftParts[i] || 0;
    const r = rightParts[i] || 0;
    if (l > r) return 1;
    if (l < r) return -1;
  }
  return 0;
}

function packageVersionStatus(packageVersion) {
  if (!packageVersion) return 'unknown';
  const comparison = compareVersions(packageVersion, ZQF_CLIENT_MIN_VERSION);
  if (comparison === null) return 'unknown';
  return comparison >= 0 ? 'supports-zqf-client' : 'generic-events';
}

function warnDuplicateNamespaceFieldFallbacks(text, file, issues) {
  const namespaced = new Map();
  const unnamespaced = new Map();
  const namespacedRe = /\bzqu__([A-Za-z][A-Za-z0-9_]*__c)\b/g;
  const unnamespacedRe = /(?<!zqu__)\b([A-Za-z][A-Za-z0-9_]*__c)\b/g;
  let m;
  while ((m = namespacedRe.exec(text))) {
    if (!namespaced.has(m[1])) namespaced.set(m[1], m.index);
  }
  while ((m = unnamespacedRe.exec(text))) {
    if (!unnamespaced.has(m[1])) unnamespaced.set(m[1], m.index);
  }
  for (const [base, index] of namespaced) {
    if (unnamespaced.has(base)) {
      issues.push({
        severity: 'warn',
        rule: 'WJS030',
        file,
        line: lineOf(text, index),
        message: `do not check both "zqu__${base}" and "${base}"; managed package fields use zqu__, custom fields outside the package do not`
      });
    }
  }
}

function warnUnknownZqfHelpers(text, file, issues) {
  const helperRe = /\b(?:this\.)?zqf\.([A-Za-z_$][\w$]*)\s*\(/g;
  const reported = new Set();
  let m;
  while ((m = helperRe.exec(text))) {
    const helper = m[1];
    if (!ZQF_CLIENT_HELPERS.has(helper) && !reported.has(helper)) {
      reported.add(helper);
      issues.push({
        severity: 'warn',
        rule: 'WJS068',
        file,
        line: lineOf(text, m.index),
        message: `unknown ZQFClient helper "${helper}"; use documented helpers from cpq-zqf-client.md. For ramp interval QRPC updates use getRampIntervals() with updateChargesInInterval(...) instead of invented rate-plan-charge helpers`
      });
    }
  }
}

function warnManualRampChargeUpdates(text, file, issues) {
  if (!/\b(?:this\.)?zqf\.updateCharges(?:InInterval)?\s*\(/.test(text)) return;

  const patterns = [
    {
      re: /\bthis\.quoteState(?:\?\.|\.)quoteRatePlans\b/,
      message: 'manual quoteState.quoteRatePlans traversal found for charge updates; use updateChargesInInterval/updateCharges filter descriptors where the parent rate plan is passed to the filter callback'
    },
    {
      re: /\b[A-Za-z_$][\w$]*\.charges\s*\.\s*(?:map|forEach)\s*\(/,
      message: 'manual interval charges traversal found for charge updates; use updateChargesInInterval(interval, [{ filter, update }]) instead of mapping interval.charges'
    },
    {
      re: /\bfor\s*\([^)]*\bof\s+[A-Za-z_$][\w$]*\.charges\b/,
      message: 'manual rate plan charges traversal found for charge updates; use updateChargesInInterval/updateCharges filter descriptors instead of iterating ratePlan.charges'
    },
    {
      re: /\b(?:id|chargeId|chargeID|chargeIdOrKey)\s*:\s*charge\.(?:id|Id)\b/,
      message: 'charge update payload uses charge id fields; use documented updateCharges/updateChargesInInterval descriptors with filter and update keys'
    }
  ];

  for (const { re, message } of patterns) {
    const match = text.match(re);
    if (match) {
      issues.push({
        severity: 'warn',
        rule: 'WJS069',
        file,
        line: lineOf(text, match.index || 0),
        message
      });
      return;
    }
  }
}

function warnInvalidZqfHelpers(text, file, issues) {
  // Check for non-existent ZQF methods that are commonly hallucinated
  const invalidMethods = [
    { name: 'updateChargeFieldConfig', useInstead: 'use new CustomEvent("objectfieldconfig") for field styling' },
    { name: 'updateFieldConfig', useInstead: 'use new CustomEvent("objectfieldconfig") for field styling' },
    { name: 'setFieldConfig', useInstead: 'use new CustomEvent("objectfieldconfig") for field styling' },
    { name: 'setField', useInstead: 'use documented update helpers for value changes or new CustomEvent("objectfieldconfig") for readOnly/backgroundColor/helptext field styling' }
  ];

  for (const { name, useInstead } of invalidMethods) {
    const re = new RegExp(`\\b(?:this\\.)?zqf\\.${name}\\s*\\(`);
    if (re.test(text)) {
      issues.push({
        severity: 'error',
        rule: 'EJS075',
        file,
        line: lineOf(text, text.search(re)),
        message: `ZQF helper "${name}" does not exist; ${useInstead}`
      });
    }
  }
}

function warnUnsupportedHookClassApi(text, file, issues) {
  const patterns = [
    {
      re: /from\s+['"]@zuora\/cpq['"]/,
      message: 'do not import QuoteStudioHooks from @zuora/cpq; Quote Studio customizations should be LWC components that extend LightningElement'
    },
    {
      re: /\bclass\s+[A-Za-z_$][\w$]*\s+extends\s+QuoteStudioHooks\.[A-Za-z_$][\w$]*/,
      message: 'do not extend QuoteStudioHooks classes such as ChargeFieldChange; declare supported Quote Studio hooks as @api methods on a LightningElement LWC'
    },
    {
      re: /\bonInit\s*\(/,
      message: 'do not use onInit for Quote Studio hooks; declare @api quoteState/pageState properties and construct ZQFClient from them'
    },
    {
      re: /\bonChange\s*\(/,
      message: 'do not use onChange for charge field changes; use supported hooks such as beforeProductUpdate/afterProductUpdate and supported events'
    }
  ];

  for (const { re, message } of patterns) {
    const match = text.match(re);
    if (match) {
      issues.push({
        severity: 'error',
        rule: 'EJS078',
        file,
        line: lineOf(text, match.index || 0),
        message
      });
    }
  }
}

function warnDirectDomFieldStyling(text, file, issues) {
  const patterns = [
    {
      re: /\bdocument\.querySelector\s*\(/,
      message: 'do not query Quote Studio DOM to locate fields; use objectfieldconfig CustomEvent for field readOnly/backgroundColor/helptext behavior'
    },
    {
      re: /\.style\.(?:backgroundColor|background|color|display|visibility|pointerEvents)\s*=/,
      message: 'do not style Quote Studio field DOM directly; use objectfieldconfig CustomEvent with configs instead'
    },
    {
      re: /\bdata-charge-id\b|\bdata-field\b/,
      message: 'do not rely on Quote Studio DOM data selectors; use hook payloads, quoteState, and objectfieldconfig configs'
    }
  ];

  for (const { re, message } of patterns) {
    const match = text.match(re);
    if (match) {
      issues.push({
        severity: 'warn',
        rule: 'WJS079',
        file,
        line: lineOf(text, match.index || 0),
        message
      });
      return;
    }
  }
}

function warnManualRampIntervalTraversal(text, file, issues) {
  // Detect manual iteration over ramp intervals and charges
  const manualTraversal = /\bfor\s*\(\s*(?:const|let|var)\s+\w+\s+of\s+rampIntervals\)/;
  if (manualTraversal.test(text) && /\brampInterval\.charges\b/.test(text)) {
    issues.push({
      severity: 'error',
      rule: 'EJS076',
      file,
      line: lineOf(text, text.search(manualTraversal)),
      message: 'manual ramp interval and charge traversal found; use updateChargesInInterval(interval, [{ filter, update }]) with filter descriptors instead of iterating rampInterval.charges'
    });
  }
}

function warnInvalidFieldConfigShape(text, file, issues) {
  // Detect invalid fieldConfig property in update payloads
  const fieldConfigInUpdate = /fieldConfig\s*:\s*\{/;
  if (fieldConfigInUpdate.test(text)) {
    issues.push({
      severity: 'error',
      rule: 'EJS077',
      file,
      line: lineOf(text, text.search(fieldConfigInUpdate)),
      message: 'invalid "fieldConfig" property in payload; for field styling use new CustomEvent("objectfieldconfig", { detail: { configs: [...] } }), for charge updates use { filter, update } descriptors'
    });
  }
}

function warnUnsupportedQuoteStateMethods(text, file, issues) {
  const patterns = [
    {
      re: /\b(?:this\.)?quoteState\.(?:getQuote|updateQuote|getQuoteField|updateQuoteField|setQuoteField|setQuoteFieldValue|setFieldValue)\s*\(/,
      message: 'do not call quoteState.getQuote()/setQuoteField()/updateQuote() style methods; for package >= 10.58 use ZQFClient helpers such as this.zqf.getQuote(), this.zqf.getQuoteField(...), and dispatch this.zqf.updateQuote(patch)'
    },
    {
      re: /\b(?:resolve|reject)\s*\(/,
      message: 'do not use resolve/reject callback style in Quote Studio hooks; use the documented hook return value, for example return true/false for beforeSave'
    }
  ];

  for (const { re, message } of patterns) {
    const match = text.match(re);
    if (match) {
      issues.push({
        severity: 'error',
        rule: 'EJS080',
        file,
        line: lineOf(text, match.index || 0),
        message
      });
    }
  }
}

function warnUnsupportedExternalHookPayloads(text, file, issues) {
  const patterns = [
    {
      re: /@api\s+record\b/,
      message: 'do not declare @api record for Quote Studio headless hooks; declare @api quoteState, @api metricState, and @api pageState'
    },
    {
      re: /@api\s+recordId\b/,
      message: 'do not declare @api recordId for Quote Studio headless hooks; declare @api quoteState, @api metricState, and @api pageState'
    },
    {
      re: /\bconnectedQuote\b/,
      message: 'do not use connectedQuote hook payloads or connectedQuote.updateQuote(...); Quote Studio hooks use documented @api signatures and ZQFClient helpers such as this.zqf.updateQuote(patch)'
    },
    {
      re: /return\s*\{\s*success\s*:\s*true\s*\}/,
      message: 'do not return { success: true } from Quote Studio hooks; use the documented return value, for example return true for beforeSave or { proceed: true } for proceed hooks'
    }
  ];

  for (const { re, message } of patterns) {
    const match = text.match(re);
    if (match) {
      issues.push({
        severity: 'error',
        rule: 'EJS083',
        file,
        line: lineOf(text, match.index || 0),
        message
      });
    }
  }
}

function warnRampRecordTypeDetection(text, file, issues) {
  const rampRecordTypeCheck = /\b(?:this\.)?zqf\.getQuoteField\s*\(\s*['"]RecordType\.Name['"]\s*\)/;
  if (rampRecordTypeCheck.test(text)) {
    issues.push({
      severity: 'warn',
      rule: 'WJS071',
      file,
      line: lineOf(text, text.search(rampRecordTypeCheck)),
      message: 'do not detect ramp quote behavior from RecordType.Name; use ramp interval existence and, when provided, the actual ramp boolean quote field'
    });
  }
}

function warnQuoteFieldRampIntervalSelection(text, file, issues) {
  const getQuoteFieldRe = /\b(?:this\.)?zqf\.getQuoteField\s*\(\s*([^)]+?)\s*\)/g;
  let m;
  while ((m = getQuoteFieldRe.exec(text))) {
    if (/\bRAMP\b|RAMP/i.test(m[1]) && /\bINTERVAL\b|INTERVAL/i.test(m[1])) {
      issues.push({
        severity: 'warn',
        rule: 'WJS072',
        file,
        line: lineOf(text, m.index),
        message: 'do not select ramp intervals using quote fields; use getRampIntervals(), getActiveRampInterval(), or getRampIntervalByDate(...) and pass the interval object to updateChargesInInterval(...)'
      });
      return;
    }
  }
}

function isRampQuoteContext(text) {
  return /\b(?:getRampIntervals|updateChargesInInterval|updateProductsInInterval|updateRatePlansInInterval|updateAmendmentsInInterval|updateTiersInInterval|rampInterval|isRampQuote|RampDeal|RAMP_)\b/i.test(text);
}

function warnRampVersionIteration(text, file, issues) {
  if (!isRampQuoteContext(text)) return;

  const patterns = [
    {
      re: /\bfor\s*\(\s*(?:const|let|var)\s+\w+\s+of\s+(?:this\.)?zqf\.getVersions\s*\(/,
      message: 'ramp quote logic must iterate getRampIntervals(), not getVersions(); timeline versions are effective-date slices, not ramp pricing intervals'
    },
    {
      re: /\bfor\s*\(\s*(?:const|let|var)\s+\w+\s+of\s+\w+\.versions\b/,
      message: 'do not iterate timeline .versions for ramp quote logic; use getRampIntervals() and interval-scoped helpers such as updateChargesInInterval(...)'
    },
    {
      re: /\b(?:this\.)?zqf\.getVersions\s*\([^)]*\)[\s\S]{0,500}?\bfor\s*\(\s*(?:const|let|var)\s+\w+\s+of\s+\w+\s*\)/,
      message: 'do not loop over getVersions() for ramp interval pricing; resolve intervals with getRampIntervals() and apply changes with updateChargesInInterval(...) or related *InInterval helpers'
    }
  ];

  for (const { re, message } of patterns) {
    const match = text.match(re);
    if (match) {
      issues.push({
        severity: 'error',
        rule: 'EJS085',
        file,
        line: lineOf(text, match.index || 0),
        message
      });
      return;
    }
  }
}

function warnDirectQuoteStateNestedAccess(text, file, issues) {
  const patterns = [
    {
      re: /\b(?:this\.)?(?:quoteState\??\.)(?:quote|subscription|subscriptions)\b/,
      message: 'do not read quote header or subscription data from nested quoteState paths; use this.zqf.getQuote(), this.zqf.getQuoteField(...), or this.zqf.getSubscription()'
    }
  ];

  for (const { re, message } of patterns) {
    const match = text.match(re);
    if (match) {
      issues.push({
        severity: 'warn',
        rule: 'WJS074',
        file,
        line: lineOf(text, match.index || 0),
        message
      });
      return;
    }
  }
}

function warnDirectQuoteStateCollectionAccess(text, file, issues) {
  const patterns = [
    {
      re: /\bfor\s*\(\s*(?:const|let|var)\s+\w+\s+of\s+(?:this\.)?(?:quoteState\??\.)?productTimelines\b/,
      message: 'quoteState.productTimelines is an object map keyed by timeline ID, not an array; use this.zqf.getProductTimelines() which returns an array'
    },
    {
      re: /\b(?:this\.)?(?:quoteState\??\.)?productTimelines\s*\.\s*(?:map|forEach|filter|reduce|find|some|every)\s*\(/,
      message: 'quoteState.productTimelines is an object map, not an array; use this.zqf.getProductTimelines() which returns an array'
    },
    {
      re: /\[\.\.\.(?:this\.)?(?:quoteState\??\.)?productTimelines\]/,
      message: 'quoteState.productTimelines is an object map, not an array; use this.zqf.getProductTimelines() which returns an array'
    },
    {
      re: /\bfor\s*\(\s*(?:const|let|var)\s+\w+\s+of\s+(?:this\.)?(?:quoteState\??\.)?quoteRatePlans\b/,
      message: 'do not iterate quoteState.quoteRatePlans directly; use this.zqf.getRatePlans(...), getUpdatedRatePlans(...), or updateCharges/updateChargesInInterval filter descriptors'
    },
    {
      re: /\b(?:this\.)?(?:quoteState\??\.)?quoteRatePlans\s*\.\s*(?:map|forEach|filter|reduce|find|some|every)\s*\(/,
      message: 'do not iterate quoteState.quoteRatePlans directly; use this.zqf.getRatePlans(...), getUpdatedRatePlans(...), or updateCharges/updateChargesInInterval filter descriptors'
    }
  ];

  for (const { re, message } of patterns) {
    const match = text.match(re);
    if (match) {
      issues.push({
        severity: 'warn',
        rule: 'WJS073',
        file,
        line: lineOf(text, match.index || 0),
        message
      });
      return;
    }
  }
}

function warnMissingRecordNesting(text, file, issues) {
  const wrapperFieldRes = [
    {
      re: /\bcharge\.(?!record\b|id\b|charges\b|tiers\b|originalQRPC\b)(?:zqu__|[A-Za-z_][\w]*__c|Name|Id)\b/,
      message: 'charge wrapper fields must be read from charge.record.<FieldApiName>; use charge.record.zqu__Quantity__c instead of charge.zqu__Quantity__c'
    },
    {
      re: /\bratePlan\.(?!record\b|id\b|charges\b|versions\b|productRatePlan\b)(?:zqu__|[A-Za-z_][\w]*__c|Name|Id)\b/,
      message: 'rate plan wrapper fields must be read from ratePlan.record.<FieldApiName>; use ratePlan.record.Name instead of ratePlan.Name'
    },
    {
      re: /\btier\.(?!record\b|id\b)(?:zqu__|[A-Za-z_][\w]*__c|Name|Id)\b/,
      message: 'tier wrapper fields must be read from tier.record.<FieldApiName>; use tier.record.zqu__Discount__c instead of tier.zqu__Discount__c'
    },
    {
      re: /\bamendment\.(?!record\b|id\b|type\b)(?:zqu__|[A-Za-z_][\w]*__c|Name|Id)\b/,
      message: 'amendment wrapper fields must be read from amendment.record.<FieldApiName>'
    },
    {
      re: /\bversion\.(?!record\b|id\b|charges\b|effectiveDate\b)(?:zqu__|[A-Za-z_][\w]*__c|Name|Id)\b/,
      message: 'version wrapper fields must be read from version.record.<FieldApiName> when present'
    }
  ];

  for (const { re, message } of wrapperFieldRes) {
    const match = text.match(re);
    if (match) {
      issues.push({
        severity: 'error',
        rule: 'EJS086',
        file,
        line: lineOf(text, match.index || 0),
        message
      });
      return;
    }
  }
}

function warnManualProductTreeTraversal(text, file, issues) {
  if (!/\bZQFClient\b|['"]zqu\/zqfClient['"]/.test(text)) return;

  const patterns = [
    {
      re: /\bfor\s*\(\s*(?:const|let|var)\s+\w+\s+of\s+\w+\.ratePlans\b/,
      message: 'manual product.ratePlans traversal found; use this.zqf.getRatePlans(...), getVersions(...), getCharges(...), or updateCharges filter descriptors instead'
    },
    {
      re: /\bfor\s*\(\s*(?:const|let|var)\s+\w+\s+of\s+\w+\.charges\b/,
      message: 'manual ratePlan.charges traversal found; use this.zqf.getCharges(...), updateCharges([...]), or updateChargesInInterval(...) filter descriptors instead'
    },
    {
      re: /\b\w+\.ratePlans\s*\.\s*(?:map|forEach|filter|reduce|find|some|every)\s*\(/,
      message: 'manual product.ratePlans traversal found; use documented ZQFClient read or mutation helpers instead of iterating nested ratePlans arrays'
    },
    {
      re: /\b\w+\.charges\s*\.\s*(?:map|forEach|filter|reduce|find|some|every)\s*\(/,
      message: 'manual ratePlan.charges traversal found; use documented ZQFClient read or mutation helpers instead of iterating nested charges arrays'
    }
  ];

  for (const { re, message } of patterns) {
    const match = text.match(re);
    if (match) {
      issues.push({
        severity: 'warn',
        rule: 'WJS075',
        file,
        line: lineOf(text, match.index || 0),
        message
      });
      return;
    }
  }
}

function warnQuoteStateClientUsage(text, file, issues, declaredProps, options = {}) {
  const usesZqfClientModule = /\bZQFClient\b|['"]zqu\/zqfClient['"]/.test(text);
  const usesInjectedZqfClient = /@api\s+zqfClient\b|\bthis\.zqfClient\b|\bzqfClient\./.test(text);
  const usesZqfClientHookParam = /@api\s+(?:async\s+)?[A-Za-z_$][\w$]*\s*\([^)]*\bzqfClient\b/.test(text);
  const usesZqfClient = usesZqfClientModule || usesInjectedZqfClient;
  const versionStatus = packageVersionStatus(options.packageVersion);
  const zqfClientIndex = text.search(/\bZQFClient\b|['"]zqu\/zqfClient['"]|@api\s+zqfClient\b|\bthis\.zqfClient\b|\bzqfClient\./);

  if (usesZqfClient && versionStatus === 'generic-events') {
    issues.push({
      severity: 'warn',
      rule: 'WJS063',
      file,
      line: lineOf(text, zqfClientIndex),
      message: `ZQFClient requires Zuora managed package ${ZQF_CLIENT_MIN_VERSION} or later; for earlier versions use documented hook return payloads and supported events`
    });
  }

  if (usesInjectedZqfClient) {
    issues.push({
      severity: 'warn',
      rule: 'WJS060',
      file,
      line: lineOf(text, text.search(/@api\s+zqfClient\b|\bthis\.zqfClient\b|\bzqfClient\./)),
      message: 'do not use injected or bare zqfClient; import ZQFClient from zqu/zqfClient and construct it from quoteState/pageState'
    });
  }

  if (usesZqfClientHookParam) {
    issues.push({
      severity: 'error',
      rule: 'EJS084',
      file,
      line: lineOf(text, text.search(/@api\s+(?:async\s+)?[A-Za-z_$][\w$]*\s*\([^)]*\bzqfClient\b/)),
      message: 'do not pass zqfClient as a Quote Studio hook parameter; copy the exact hook signature and construct ZQFClient from this.quoteState/this.pageState'
    });
  }

  const hookRegistration = /\bzqfClient\.hooks\.register\b|\bthis\.zqfClient\.hooks\.register\b|\.hooks\.register\s*\(/;
  if (hookRegistration.test(text)) {
    issues.push({
      severity: 'warn',
      rule: 'WJS065',
      file,
      line: lineOf(text, text.search(hookRegistration)),
      message: 'do not register Quote Studio hooks through zqfClient.hooks.register; declare supported hook methods directly with @api'
    });
  }

  const subscribeHooks = /\bsubscribe\s*\(\s*this\s*,\s*['"]([^'"]+)['"]/;
  if (subscribeHooks.test(text)) {
    issues.push({
      severity: 'error',
      rule: 'EJS070',
      file,
      line: lineOf(text, text.search(subscribeHooks)),
      message: 'do not use subscribe/unsubscribe from zqu/hooks; declare Quote Studio hooks as @api methods'
    });
  }

  const directMutation = /\bthis\.quoteState(?:\s*=|\.[A-Za-z_$][\w$.[\]'"]*\s*=|\.setFieldValue\s*\()/;
  if (directMutation.test(text)) {
    issues.push({
      severity: 'warn',
      rule: 'WJS061',
      file,
      line: lineOf(text, text.search(directMutation)),
      message: 'do not directly mutate quoteState; for managed package >= 10.58 use ZQFClient helpers, otherwise use supported hook return payloads/events'
    });
  }

  const quoteStateSetter = /\bthis\.quoteState\.setFieldValue\s*\(/;
  if (quoteStateSetter.test(text)) {
    issues.push({
      severity: 'warn',
      rule: 'WJS066',
      file,
      line: lineOf(text, text.search(quoteStateSetter)),
      message: 'quoteState.setFieldValue is not a supported Quote Studio mutation pattern; use ZQFClient helpers for package >= 10.58 or supported events/hooks for earlier versions'
    });
  }

  // WJS081: ZQFClient referenced but not imported — will not compile.
  const referencesZqfClient =
    /\bZQFClient\s*\.\s*from\s*\(|\bnew\s+ZQFClient\s*\(|\bthis\.zqf\b/.test(text);
  const hasZqfClientImport =
    /import\s+(?:ZQFClient|\{[^}]*\bZQFClient\b[^}]*\})\s+from\s+['"]zqu\/zqfClient['"]/.test(text);
  if (versionStatus === 'supports-zqf-client' && referencesZqfClient && !hasZqfClientImport) {
    const zqfRefMatch = text.match(/\bZQFClient\s*\.\s*from\s*\(|\bnew\s+ZQFClient\s*\(|\bthis\.zqf\b/);
    issues.push({
      severity: 'warn',
      rule: 'WJS081',
      file,
      line: lineOf(text, zqfRefMatch ? zqfRefMatch.index : 0),
      message: "ZQFClient is referenced but not imported; add `import ZQFClient from 'zqu/zqfClient';` at the top of the file"
    });
  }

  warnUnknownZqfHelpers(text, file, issues);
  warnManualRampChargeUpdates(text, file, issues);
  warnRampRecordTypeDetection(text, file, issues);
  warnQuoteFieldRampIntervalSelection(text, file, issues);
  warnRampVersionIteration(text, file, issues);
  warnDirectQuoteStateNestedAccess(text, file, issues);
  warnDirectQuoteStateCollectionAccess(text, file, issues);
  warnMissingRecordNesting(text, file, issues);
  warnManualProductTreeTraversal(text, file, issues);
  warnInvalidZqfHelpers(text, file, issues);
  warnManualRampIntervalTraversal(text, file, issues);
  warnInvalidFieldConfigShape(text, file, issues);
  warnUnsupportedHookClassApi(text, file, issues);
  warnDirectDomFieldStyling(text, file, issues);
  warnUnsupportedQuoteStateMethods(text, file, issues);
  warnUnsupportedExternalHookPayloads(text, file, issues);

  const fieldLevelUpdateMatches = [...text.matchAll(/\b(?:this\.)?zqf\.(update(?:Quote|Charge|Tier)Field(?:InInterval)?)\s*\(/g)];
  if (fieldLevelUpdateMatches.length > 1) {
    issues.push({
      severity: 'warn',
      rule: 'WJS067',
      file,
      line: lineOf(text, fieldLevelUpdateMatches[1].index),
      message: 'multiple field-level ZQF update helpers found; use patch or bulk helpers such as zqf.updateQuote(patch), updateCharges([...]), updateRatePlans([...]), updateTiers([...]), updateAmendments([...]), or updateProducts({ ... }) for multiple CPQ object field updates'
    });
  }

  const quoteStateEvent = /new\s+CustomEvent\(\s*['"](?:updateQuote|updatequote|upsertQuoteLineItems|upsertquotelineitems|updateProducts|updateproducts|previewQuoteState|previewquotestate|saveQuote|savequote)['"]/;
  if (quoteStateEvent.test(text) && versionStatus === 'supports-zqf-client') {
    issues.push({
      severity: 'error',
      rule: 'EJS064',
      file,
      line: lineOf(text, text.search(quoteStateEvent)),
      message: `raw quote-state event construction found for package version ${options.packageVersion}; use ZQFClient helpers for version ${ZQF_CLIENT_MIN_VERSION} or later`
    });
  } else if (quoteStateEvent.test(text) && !usesZqfClient && versionStatus !== 'generic-events') {
    issues.push({
      severity: 'warn',
      rule: 'WJS062',
      file,
      line: lineOf(text, text.search(quoteStateEvent)),
      message: 'raw quote-state event construction found without ZQFClient; confirm package version. For versions earlier than 10.58 generic event examples are valid; for 10.58 or later use ZQFClient helpers'
    });
  }
}

// Banned hook names that are commonly hallucinated by AI
const BANNED_HOOKS = new Map([
  ['onFieldChange', 'use beforeProductUpdate or afterProductUpdate'],
  ['onMetricFieldChange', 'use beforeProductUpdate or afterProductUpdate'],
  ['onQuoteLoad', 'use afterQuoteStudioLoad'],
  ['onChargeChange', 'use beforeProductUpdate or afterProductUpdate'],
  ['beforeCalculate', 'not a valid Quote Studio hook'],
  ['afterCalculate', 'use afterRulesExecution'],
  ['beforePrice', 'not a valid Quote Studio hook'],
  ['afterPrice', 'not a valid Quote Studio hook'],
  ['subscribe', 'hooks are @api methods, not subscriptions; do not import from zqu/hooks']
]);

function headlessHookNames(catalogs) {
  return new Set((catalogs.hooks.hooks || [])
    .filter((hook) => hook.componentType === 'headless')
    .map((hook) => hook.name));
}

function isHeadlessComponentText(text, catalogs) {
  const hooks = headlessHookNames(catalogs);
  for (const hook of hooks) {
    const re = new RegExp(`@api\\s+(?:async\\s+)?${hook}\\s*\\(`);
    if (re.test(text)) return true;
  }
  return false;
}

function lintText(text, file, catalogs = loadCatalogs(), options = {}) {
  const issues = [];
  const hookMap = new Map(catalogs.hooks.hooks.map((h) => [h.name, h]));
  const publicProps = new Set(catalogs.hooks.publicProperties || []);
  const eventByName = new Map();
  for (const e of catalogs.events.events) {
    eventByName.set(e.name, e);
    for (const a of e.aliases || []) eventByName.set(a, e);
  }

  const declaredProps = collectApiProperties(text);
  const usedHeadlessHooks = new Set();
  // Check for banned/hallucinated hooks first
  const apiMethodRe = /@api\s+(?:async\s+)?([A-Za-z_$][\w$]*)\s*\(([^)]*)\)\s*\{/g;
  let m;
  while ((m = apiMethodRe.exec(text))) {
    const name = m[1];
    if (BANNED_HOOKS.has(name)) {
      issues.push({ severity: 'error', rule: 'EJS000', file, line: lineOf(text, m.index), message: `banned hook "${name}" detected; ${BANNED_HOOKS.get(name)}` });
      continue;
    }
    const hook = hookMap.get(name);
    if (!hook && !publicProps.has(name)) {
      issues.push({ severity: 'warn', rule: 'WJS001', file, line: lineOf(text, m.index), message: `@api method "${name}" is not in cpq-js-hooks.json` });
      continue;
    }
    if (hook) {
      if (hook.componentType === 'headless') usedHeadlessHooks.add(name);
      const params = m[2].split(',').map((s) => s.trim()).filter(Boolean);
      if (params.length !== hook.params.length) {
        issues.push({
          severity: 'error',
          rule: 'EJS081',
          file,
          line: lineOf(text, m.index),
          message: `hook "${name}" declares ${params.length} parameter(s), catalog signature requires exactly ${hook.params.length}: (${hook.params.join(', ')})`
        });
      }
      if (/\bresolve\b|\breject\b/.test(m[2])) {
        issues.push({
          severity: 'error',
          rule: 'EJS082',
          file,
          line: lineOf(text, m.index),
          message: `hook "${name}" must not use resolve/reject parameters; use the documented hook return value instead`
        });
      }
      if (hook.returnRequiredKeys.includes('proceed')) {
        const bodyStart = apiMethodRe.lastIndex;
        const nextChunk = text.slice(bodyStart, bodyStart + 1200);
        if (!/proceed\s*:/.test(nextChunk)) {
          issues.push({ severity: 'error', rule: 'EJS003', file, line: lineOf(text, m.index), message: `hook "${name}" should return an object containing proceed` });
        }
      }
    }
  }

  if (usedHeadlessHooks.size) {
    for (const prop of ['quoteState', 'metricState', 'pageState']) {
      if (!declaredProps.has(prop)) {
        issues.push({ severity: 'warn', rule: 'WJS040', file, line: 1, message: `headless component should declare @api ${prop}` });
      }
    }
    if ([...usedHeadlessHooks].some((name) => name.toLowerCase().includes('msq'))) {
      for (const prop of ['masterQuoteState', 'parentQuoteState']) {
        if (!declaredProps.has(prop)) {
          issues.push({ severity: 'warn', rule: 'WJS041', file, line: 1, message: `MSQ headless component should declare @api ${prop}` });
        }
      }
    }
  }

  const eventRe = /new\s+CustomEvent\(\s*['"]([^'"]+)['"]\s*,?\s*([\s\S]{0,700}?)\)/g;
  while ((m = eventRe.exec(text))) {
    const eventName = m[1];
    const event = eventByName.get(eventName);
    const loc = lineOf(text, m.index);
    if (!event) {
      issues.push({ severity: 'error', rule: 'EJS010', file, line: loc, message: `unknown CPQ event "${eventName}"` });
      continue;
    }
    const snippet = m[0];
    for (const key of event.requiredDetailKeys || []) {
      if (!new RegExp(`\\b${key}\\b`).test(snippet)) {
        issues.push({ severity: 'warn', rule: 'WJS011', file, line: loc, message: `event "${eventName}" should include detail key "${key}"` });
      }
    }
    if (eventName === 'toastMessageDisplay' && /theme\s*:\s*['"]([^'"]+)['"]/.test(snippet)) {
      const theme = snippet.match(/theme\s*:\s*['"]([^'"]+)['"]/)[1];
      if (!['warning', 'error', 'success'].includes(theme)) {
        issues.push({ severity: 'error', rule: 'EJS012', file, line: loc, message: `toastMessageDisplay theme must be warning, error, or success` });
      }
    }
    if (event.registrationRequired) {
      issues.push({ severity: 'info', rule: 'IJS020', file, line: loc, message: `event "${event.name}" requires Component Event Action registration in CPQ X` });
    }
  }

  lintJsQuoteFieldReferences(text, file, issues);
  warnDuplicateNamespaceFieldFallbacks(text, file, issues);
  warnQuoteStateClientUsage(text, file, issues, declaredProps, options);
  return issues;
}

function isKnownQuoteField(indexed, fieldName) {
  const quoteObject = indexed.byObject.get('zqu__Quote__c');
  return Boolean(quoteObject && quoteObject.fieldMap.has(fieldName));
}

function isKnownObjectField(indexed, objectName, fieldName) {
  const objectEntry = indexed.byObject.get(objectName);
  return Boolean(objectEntry && objectEntry.fieldMap.has(fieldName));
}

function extractManagedFieldKeys(body) {
  const keys = [];
  const keyRe = /(?:['"](zqu__[^'"]+)['"]|(zqu__[\w]+))\s*:/g;
  let km;
  while ((km = keyRe.exec(body))) {
    keys.push({ fieldName: km[1] || km[2], index: km.index });
  }
  return keys;
}

function isInsideStringLiteral(text, index) {
  const before = text.slice(0, index);
  let single = 0;
  let double = 0;
  for (const ch of before) {
    if (ch === "'") single++;
    else if (ch === '"') double++;
  }
  return single % 2 === 1 || double % 2 === 1;
}

function objectLabelToCatalogName(objectLabel) {
  const map = {
    Quote: 'zqu__Quote__c',
    QuoteRatePlanCharge: 'zqu__QuoteRatePlanCharge__c',
    QuoteChargeTier: 'zqu__QuoteCharge_Tier__c'
  };
  return map[objectLabel] || null;
}

function lintJsQrpcFieldReferences(text, file, issues, indexed) {
  const QRPC = 'zqu__QuoteRatePlanCharge__c';
  const TIER = 'zqu__QuoteCharge_Tier__c';
  const qrpcContextMistakes = indexed.qrpcContextMistakes || {};

  const chargeRecordRe = /\bcharge\.record\.(zqu__[\w]+__c)\b/g;
  let m;
  while ((m = chargeRecordRe.exec(text))) {
    const fieldName = m[1];
    if (qrpcContextMistakes[fieldName]) {
      issues.push({
        severity: 'error',
        rule: 'WJS082',
        file,
        line: lineOf(text, m.index),
        message: `charge.record field read: invalid field "${fieldName}" — ${qrpcContextMistakes[fieldName]}`
      });
      continue;
    }
    if (!isKnownObjectField(indexed, QRPC, fieldName)) {
      issues.push({
        severity: 'error',
        rule: 'WJS082',
        file,
        line: lineOf(text, m.index),
        message: `charge.record field read: "${fieldName}" is not a known ${QRPC} field — confirm against cpq-salesforce-fields.json or live SFDX describe`
      });
    }
  }

  const tierRecordRe = /\btier\.record\.(zqu__[\w]+__c)\b/g;
  while ((m = tierRecordRe.exec(text))) {
    if (!isKnownObjectField(indexed, TIER, m[1])) {
      issues.push({
        severity: 'error',
        rule: 'WJS082',
        file,
        line: lineOf(text, m.index),
        message: `tier.record field read: "${m[1]}" is not a known ${TIER} field — confirm against cpq-salesforce-fields.json or live SFDX describe`
      });
    }
  }

  const chargeFieldPatterns = [
    /updateChargeField\s*\(\s*[^,]+,\s*[^,]+,\s*['"](zqu__[^'"]+)['"]/g,
    /updateChargeFieldInInterval\s*\(\s*[^,]+,\s*[^,]+,\s*[^,]+,\s*['"](zqu__[^'"]+)['"]/g
  ];
  for (const re of chargeFieldPatterns) {
    while ((m = re.exec(text))) {
      const fieldName = m[1];
      if (qrpcContextMistakes[fieldName]) {
        issues.push({
          severity: 'error',
          rule: 'WJS082',
          file,
          line: lineOf(text, m.index),
          message: `updateChargeField: invalid field "${fieldName}" — ${qrpcContextMistakes[fieldName]}`
        });
        continue;
      }
      if (!isKnownObjectField(indexed, QRPC, fieldName)) {
        issues.push({
          severity: 'error',
          rule: 'WJS082',
          file,
          line: lineOf(text, m.index),
          message: `updateChargeField: "${fieldName}" is not a known ${QRPC} field`
        });
      }
    }
  }

  const tierFieldPatterns = [
    /updateTierField\s*\(\s*[^,]+,\s*[^,]+,\s*[^,]+,\s*['"](zqu__[^'"]+)['"]/g,
    /updateTierFieldInInterval\s*\(\s*[^,]+,\s*[^,]+,\s*[^,]+,\s*[^,]+,\s*['"](zqu__[^'"]+)['"]/g
  ];
  for (const re of tierFieldPatterns) {
    while ((m = re.exec(text))) {
      if (!isKnownObjectField(indexed, TIER, m[1])) {
        issues.push({
          severity: 'error',
          rule: 'WJS082',
          file,
          line: lineOf(text, m.index),
          message: `updateTierField: "${m[1]}" is not a known ${TIER} field`
        });
      }
    }
  }

  const updateBlockRe = /update\s*:\s*\{([\s\S]*?)\}/g;
  while ((m = updateBlockRe.exec(text))) {
    for (const { fieldName, index } of extractManagedFieldKeys(m[1])) {
      if (!fieldName.startsWith('zqu__')) continue;
      const inQrpc = isKnownObjectField(indexed, QRPC, fieldName);
      const inTier = isKnownObjectField(indexed, TIER, fieldName);
      if (!inQrpc && !inTier) {
        issues.push({
          severity: 'error',
          rule: 'WJS082',
          file,
          line: lineOf(text, m.index + 'update: {'.length + index),
          message: `charge/tier update patch key "${fieldName}" is not a known ${QRPC} or ${TIER} field`
        });
      }
    }
  }

  const configEntryPatterns = [
    /object\s*:\s*['"](QuoteRatePlanCharge|QuoteChargeTier|Quote)['"][\s\S]{0,240}?\bfield\s*:\s*['"](zqu__[^'"]+)['"]/g,
    /\bfield\s*:\s*['"](zqu__[^'"]+)['"][\s\S]{0,240}?\bobject\s*:\s*['"](QuoteRatePlanCharge|QuoteChargeTier|Quote)['"]/g
  ];
  for (const re of configEntryPatterns) {
    while ((m = re.exec(text))) {
      const objectLabel = m[1].startsWith('zqu__') ? m[2] : m[1];
      const fieldName = m[1].startsWith('zqu__') ? m[1] : m[2];
      const catalogObject = objectLabelToCatalogName(objectLabel);
      if (!catalogObject || !fieldName.startsWith('zqu__')) continue;
      if (catalogObject === QRPC && qrpcContextMistakes[fieldName]) {
        issues.push({
          severity: 'error',
          rule: 'WJS082',
          file,
          line: lineOf(text, m.index),
          message: `objectfieldconfig ${objectLabel} field "${fieldName}" — ${qrpcContextMistakes[fieldName]}`
        });
        continue;
      }
      if (!isKnownObjectField(indexed, catalogObject, fieldName)) {
        issues.push({
          severity: 'error',
          rule: 'WJS082',
          file,
          line: lineOf(text, m.index),
          message: `objectfieldconfig ${objectLabel} field "${fieldName}" is not a known ${catalogObject} field`
        });
      }
    }
  }
}

function lintJsQuoteFieldReferences(text, file, issues) {
  const indexed = indexFieldCatalog(loadFieldCatalog());
  const commonMistakes = indexed.commonMistakes || {};

  for (const [bad, hint] of Object.entries(commonMistakes)) {
    const re = new RegExp(`['"]${bad.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}['"]`, 'g');
    let m;
    while ((m = re.exec(text))) {
      issues.push({
        severity: 'error',
        rule: 'EJS090',
        file,
        line: lineOf(text, m.index),
        message: `invalid field "${bad}" — ${hint}`
      });
    }
    if (/^zqu__|^Zuora__/.test(bad)) {
      const unquotedRe = new RegExp(`\\b${bad.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'g');
      while ((m = unquotedRe.exec(text))) {
        if (isInsideStringLiteral(text, m.index)) continue;
        issues.push({
          severity: 'error',
          rule: 'EJS090',
          file,
          line: lineOf(text, m.index),
          message: `invalid field "${bad}" — ${hint}`
        });
      }
    }
  }

  const fieldArgRe = /(?:getQuoteField|updateQuoteField|setFieldValue)\s*\(\s*['"]([^'"]+)['"]/g;
  let m;
  while ((m = fieldArgRe.exec(text))) {
    const fieldName = m[1];
    if (!fieldName.startsWith('zqu__')) continue;
    if (!isKnownQuoteField(indexed, fieldName)) {
      issues.push({
        severity: 'error',
        rule: 'WJS080',
        file,
        line: lineOf(text, m.index),
        message: `"${fieldName}" is not a known zqu__Quote__c field — confirm against cpq-salesforce-fields.json or live SFDX describe`
      });
    }
  }

  const patchKeyRe = /updateQuote\s*\(\s*\{([\s\S]*?)\}\s*\)/g;
  while ((m = patchKeyRe.exec(text))) {
    const body = m[1];
    const keyRe = /(?:['"](zqu__[^'"]+)['"]|(zqu__[\w]+))\s*:/g;
    let km;
    while ((km = keyRe.exec(body))) {
      const fieldName = km[1] || km[2];
      if (!isKnownQuoteField(indexed, fieldName)) {
        issues.push({
          severity: 'error',
          rule: 'WJS080',
          file,
          line: lineOf(text, m.index + km.index),
          message: `updateQuote patch key "${fieldName}" is not a known zqu__Quote__c field`
        });
      }
    }
  }

  lintJsQrpcFieldReferences(text, file, issues, indexed);
}

function lintFiles(files, options = {}) {
  const catalogs = loadCatalogs();
  const entries = files.map((file) => ({ file, text: fs.readFileSync(file, 'utf8') }));
  const issues = entries.flatMap(({ file, text }) =>
    file.endsWith('.js-meta.xml') ? lintMetadataText(text, file) : lintText(text, file, catalogs, options)
  );
  const headlessFiles = entries
    .filter(({ file, text }) => file.endsWith('.js') && isHeadlessComponentText(text, catalogs))
    .map(({ file }) => file);
  if (headlessFiles.length > 1) {
    for (const file of headlessFiles) {
      issues.push({
        severity: 'warn',
        rule: 'WJS050',
        file,
        line: 1,
        message: `multiple headless components found (${headlessFiles.length}); update the active generic headlessComponent unless the user explicitly requested multiple components`
      });
    }
  }
  return issues;
}

function parseArgs(args) {
  const parsed = {
    json: false,
    packageVersion: process.env.ZUORA_CPQ_PACKAGE_VERSION || process.env.CPQ_PACKAGE_VERSION,
    targets: []
  };
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--json') {
      parsed.json = true;
    } else if (arg === '--package-version') {
      parsed.packageVersion = args[++i];
    } else if (arg.startsWith('--package-version=')) {
      parsed.packageVersion = arg.slice('--package-version='.length);
    } else {
      parsed.targets.push(arg);
    }
  }
  return parsed;
}

function main() {
  const { json, packageVersion, targets } = parseArgs(process.argv.slice(2));
  if (targets.length === 0) {
    console.error('Usage: node scripts/lint-cpq-hooks-events.js [--json] [--package-version <version>] <file-or-dir>...');
    process.exit(2);
  }
  const files = collectFiles(targets);
  const issues = lintFiles(files, { packageVersion });
  if (json) console.log(JSON.stringify({ files, issues }, null, 2));
  else {
    for (const i of issues) console.log(`${i.severity.toUpperCase()} ${i.rule} ${i.file}:${i.line || 1} ${i.message}`);
    console.log(`Checked ${files.length} JS file(s), ${issues.length} issue(s).`);
  }
  if (issues.some((i) => i.severity === 'error')) process.exit(1);
}

if (require.main === module) main();
module.exports = { lintText, lintMetadataText, lintFiles, loadCatalogs };
