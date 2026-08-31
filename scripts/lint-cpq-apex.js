#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const REF_DIR = [
  path.join(__dirname, '..', 'zuora-coding-agent', 'references'),
  path.join(__dirname, '..', 'references')
].find((dir) => fs.existsSync(dir));

function loadCatalog() {
  return JSON.parse(fs.readFileSync(path.join(REF_DIR, 'cpq-global-apex-methods.json'), 'utf8'));
}

function loadFieldCatalog() {
  return JSON.parse(fs.readFileSync(path.join(REF_DIR, 'cpq-salesforce-fields.json'), 'utf8'));
}

function indexFieldCatalog(fieldCatalog) {
  const byObject = new Map();
  const byFieldName = new Map();
  for (const [objectName, entry] of Object.entries(fieldCatalog.objects || {})) {
    const fieldMap = new Map();
    for (const field of entry.fields || []) {
      fieldMap.set(field.name, field);
      if (!byFieldName.has(field.name)) byFieldName.set(field.name, { objectName, field });
    }
    byObject.set(objectName, { entry, fieldMap });
  }
  return { byObject, byFieldName, commonMistakes: fieldCatalog.$common_mistakes || {}, qrpcContextMistakes: fieldCatalog.$qrpc_context_mistakes || {} };
}

function collectFiles(targets) {
  const files = [];
  function walk(p) {
    if (!fs.existsSync(p)) return;
    const st = fs.statSync(p);
    if (st.isDirectory()) for (const e of fs.readdirSync(p)) walk(path.join(p, e));
    else if (p.endsWith('.cls') || p.endsWith('.trigger')) files.push(p);
  }
  targets.forEach(walk);
  return files;
}

function lineOf(text, index) {
  return text.slice(0, index).split(/\r?\n/).length;
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
        rule: 'WAPEX011',
        file,
        line: lineOf(text, index),
        message: `do not check both "zqu__${base}" and "${base}"; managed package fields use zqu__, custom fields outside the package do not`
      });
    }
  }
}

function indexCatalog(catalog) {
  const zQuoteUtil = new Map();
  const quoteInstance = new Set();
  const metricsUtilMethods = new Map();
  const recalcControllerMethods = new Map();
  for (const cls of catalog.classes || []) {
    const classKey = cls.namespace ? `${cls.namespace}.${cls.name}` : cls.name;
    for (const method of cls.methods || []) {
      const names = [method.name, ...(method.aliases || [])];
      const entry = { ...method, classKey };
      if (classKey === 'zqu.zQuoteUtil') {
        for (const n of names) zQuoteUtil.set(n, entry);
      } else if (classKey === 'zqu.Quote' && cls.instanceClass) {
        for (const n of names) quoteInstance.add(n);
      } else if (classKey === 'zqu.MetricsUtil') {
        for (const n of names) metricsUtilMethods.set(n, entry);
      } else if (classKey === 'zqu.QuoteRecalculateController') {
        for (const n of names) recalcControllerMethods.set(n, entry);
      }
    }
  }
  return { zQuoteUtil, quoteInstance, metricsUtilMethods, recalcControllerMethods };
}

function extractCallArgs(text, openParenIndex) {
  let depth = 0;
  let i = openParenIndex;
  for (; i < text.length; i++) {
    const ch = text[i];
    if (ch === '(') depth++;
    else if (ch === ')') {
      depth--;
      if (depth === 0) return text.slice(openParenIndex + 1, i);
    }
  }
  return '';
}

function splitTopLevelArgs(argsText) {
  const args = [];
  let current = '';
  let depth = 0;
  for (const ch of argsText) {
    if (ch === '(' || ch === '{' || ch === '[') depth++;
    else if (ch === ')' || ch === '}' || ch === ']') depth--;
    else if (ch === ',' && depth === 0) {
      args.push(current.trim());
      current = '';
      continue;
    }
    current += ch;
  }
  if (current.trim()) args.push(current.trim());
  return args;
}

function argsMatchInvalidPatterns(argsText, patterns) {
  if (!patterns || patterns.length === 0) return false;
  const args = splitTopLevelArgs(argsText);
  if (args.length !== 1) return false;
  return patterns.some((p) => new RegExp(p, 'i').test(args[0]));
}

function looksLikeQuoteCreationFlow(text) {
  return /\brenewQuote\s*\(/.test(text)
    || /\binsert\s+[\w\s,]*zqu__Quote__c/.test(text)
    || /\bnew\s+zqu__Quote__c\s*\(/.test(text);
}

function lintZQuoteUtilCalls(text, file, zQuoteUtil, issues) {
  const callRe = /(?:\bzqu\s*\.\s*)?\bzQuoteUtil\s*\.\s*([A-Za-z_]\w*)\s*\(/g;
  let m;
  while ((m = callRe.exec(text))) {
    const methodName = m[1];
    const meta = zQuoteUtil.get(methodName);
    const argsText = extractCallArgs(text, m.index + m[0].length - 1);
    if (!meta) {
      issues.push({
        severity: 'error',
        rule: 'EAPEX001',
        file,
        line: lineOf(text, m.index),
        message: `unknown zQuoteUtil method "${methodName}"`
      });
      continue;
    }
    if (argsMatchInvalidPatterns(argsText, meta.invalidArgumentPatterns)) {
      const expected = (meta.parameters || []).map((p) => p.type).join(', ') || 'zqu__Quote__c';
      issues.push({
        severity: 'error',
        rule: 'EAPEX002',
        file,
        line: lineOf(text, m.index),
        message: `${methodName}() expects ${expected}, not Id — query zqu__Quote__c first`
      });
    }
  }
}

function lintQuoteInstanceCalls(text, file, quoteInstance, issues) {
  const callRe = /(?:new\s+(?:zqu\s*\.\s*)?Quote\s*\([^)]*\)|\b(?:quoteObj|quoteWrapper|quoteInstance)\b)\s*\.\s*([A-Za-z_]\w*)\s*\(/g;
  let m;
  while ((m = callRe.exec(text))) {
    if (!quoteInstance.has(m[1])) {
      issues.push({
        severity: 'error',
        rule: 'EAPEX003',
        file,
        line: lineOf(text, m.index),
        message: `unknown zqu.Quote method "${m[1]}" — supported: ${[...quoteInstance].join(', ')}`
      });
    }
  }
}

function lintStaticClassCalls(text, file, className, knownMethods, rulePrefix, issues) {
  const escaped = className.replace(/\./g, '\\s*\\.\\s*');
  const callRe = new RegExp(`(?:\\bzqu\\s*\\.\\s*)?${escaped}\\s*\\.\\s*([A-Za-z_]\\w*)\\s*\\(`, 'g');
  let m;
  while ((m = callRe.exec(text))) {
    if (!knownMethods.has(m[1])) {
      issues.push({
        severity: 'error',
        rule: `${rulePrefix}001`,
        file,
        line: lineOf(text, m.index),
        message: `unknown ${className} method "${m[1]}"`
      });
    }
  }
}

function firstMatchIndex(text, patterns) {
  for (const re of patterns) {
    const idx = text.search(re);
    if (idx >= 0) return idx;
  }
  return 0;
}

function lintQuoteCreationLifecycle(text, file, issues) {
  if (!looksLikeQuoteCreationFlow(text)) return;
  if (/\bbuildAndSave\s*\(/.test(text)) return;
  const anchor = firstMatchIndex(text, [
    /\brenewQuote\s*\(/,
    /\binsert\s+[\w\s,]*zqu__Quote__c/,
    /\bnew\s+zqu__Quote__c\s*\(/
  ]);
  issues.push({
    severity: 'warn',
    rule: 'WAPEX040',
    file,
    line: lineOf(text, anchor >= 0 ? anchor : 0),
    message: 'quote creation/renewQuote flow should call new zqu.Quote(quoteId).buildAndSave() in a Queueable after DML'
  });
}

function isManagedPackageField(fieldName) {
  return fieldName.startsWith('zqu__') || fieldName.startsWith('Zuora__');
}

function shouldValidateField(fieldName) {
  if (fieldName === 'Id' || fieldName === 'Name') return true;
  if (fieldName.includes('.')) {
    const leaf = fieldName.split('.').pop();
    return isManagedPackageField(leaf) || leaf === 'Id' || leaf === 'Name';
  }
  return isManagedPackageField(fieldName);
}

function lookupField(indexed, objectName, fieldName) {
  const obj = indexed.byObject.get(objectName);
  if (obj && obj.fieldMap.has(fieldName)) return obj.fieldMap.get(fieldName);
  const global = indexed.byFieldName.get(fieldName);
  return global ? global.field : null;
}

function inferLiteralType(valueText) {
  const trimmed = valueText.trim();
  if (/^null$/i.test(trimmed)) return 'null';
  if (/^(true|false)$/i.test(trimmed)) return 'boolean';
  if (/^-?\d+(?:\.\d+)?[dD]?$/.test(trimmed)) return 'number';
  if (/^'(?:[^'\\]|\\.)*'$/.test(trimmed) || /^"(?:[^"\\]|\\.)*"$/.test(trimmed)) return 'string';
  if (/^Date\.(?:today|newInstance)\b/.test(trimmed) || /^Date\.valueOf\(/.test(trimmed)) return 'date';
  if (/^Datetime\.(?:now|newInstance)\b/.test(trimmed) || /^Datetime\.valueOf\(/.test(trimmed)) return 'datetime';
  if (/^Integer\.valueOf\(/.test(trimmed) || /^Decimal\.valueOf\(/.test(trimmed)) return 'number';
  return 'expression';
}

function isTypeCompatible(fieldType, literalType) {
  if (literalType === 'null' || literalType === 'expression') return true;
  const numericTypes = new Set(['decimal', 'integer', 'double', 'currency', 'percent']);
  const stringTypes = new Set(['string', 'text', 'picklist', 'email', 'url', 'phone', 'textarea', 'id', 'reference']);
  const booleanTypes = new Set(['boolean']);
  const dateTypes = new Set(['date']);
  const datetimeTypes = new Set(['datetime']);
  if (numericTypes.has(fieldType)) return literalType === 'number';
  if (stringTypes.has(fieldType)) return literalType === 'string' || literalType === 'number';
  if (booleanTypes.has(fieldType)) return literalType === 'boolean';
  if (dateTypes.has(fieldType)) return literalType === 'date' || literalType === 'string';
  if (datetimeTypes.has(fieldType)) return literalType === 'datetime' || literalType === 'string';
  return true;
}

function splitSelectFields(selectClause) {
  const fields = [];
  let current = '';
  let depth = 0;
  for (const ch of selectClause) {
    if (ch === '(') depth++;
    else if (ch === ')') depth--;
    else if (ch === ',' && depth === 0) {
      const part = current.trim();
      if (part) fields.push(part.replace(/\s+/g, ' '));
      current = '';
      continue;
    }
    current += ch;
  }
  const last = current.trim();
  if (last) fields.push(last.replace(/\s+/g, ' '));
  return fields;
}

function normalizeSelectField(fieldExpr) {
  const trimmed = fieldExpr.trim();
  const aliasMatch = trimmed.match(/\b(?:AS|as)\s+([A-Za-z_]\w*)$/);
  if (aliasMatch) return null;
  if (/^(COUNT|SUM|AVG|MIN|MAX)\s*\(/i.test(trimmed)) return null;
  if (/^(TYPEOF|FORMAT)\b/i.test(trimmed)) return null;
  return trimmed.replace(/\s+/g, ' ');
}

function extractSoqlBlocks(text) {
  const blocks = [];
  const re = /\[\s*SELECT\b([\s\S]*?)\bFROM\s+([A-Za-z0-9_.]+)/gi;
  let m;
  while ((m = re.exec(text))) {
    blocks.push({
      selectClause: m[1],
      objectName: m[2],
      index: m.index
    });
  }
  return blocks;
}

function lintCommonMistakes(text, file, indexed, issues) {
  for (const [bad, hint] of Object.entries(indexed.commonMistakes)) {
    const re = new RegExp(`\\b${bad.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'g');
    let m;
    while ((m = re.exec(text))) {
      issues.push({
        severity: 'error',
        rule: 'EAPEX052',
        file,
        line: lineOf(text, m.index),
        message: `invalid field "${bad}" — ${hint}`
      });
    }
  }
}

function lintManagedFieldReference(fieldName, objectName, index, text, file, indexed, issues, context) {
  if (!shouldValidateField(fieldName)) return;
  const meta = lookupField(indexed, objectName, fieldName);
  if (meta) return;
  issues.push({
    severity: 'error',
    rule: 'WAPEX050',
    file,
    line: lineOf(text, index),
    message: `${context}: "${fieldName}" is not a known ${objectName || 'CPQ/Zuora'} field — confirm against cpq-salesforce-fields.json or live SFDX describe`
  });
}

function lintSoqlFields(text, file, indexed, issues) {
  for (const block of extractSoqlBlocks(text)) {
    const fields = splitSelectFields(block.selectClause)
      .map(normalizeSelectField)
      .filter(Boolean);
    for (const fieldName of fields) {
      lintManagedFieldReference(fieldName, block.objectName, block.index, text, file, indexed, issues, `SOQL SELECT on ${block.objectName}`);
    }
  }
}

function lintQuoteParamsPut(text, file, indexed, issues) {
  const putRe = /\.put\s*\(\s*'([^']+)'\s*,\s*([\s\S]*?)\)/g;
  let m;
  while ((m = putRe.exec(text))) {
    const fieldName = m[1];
    const valueText = m[2];
    lintManagedFieldReference(fieldName, 'zqu__Quote__c', m.index, text, file, indexed, issues, 'quoteParams.put');
    const meta = lookupField(indexed, 'zqu__Quote__c', fieldName);
    if (meta) {
      const literalType = inferLiteralType(valueText);
      if (!isTypeCompatible(meta.type, literalType)) {
        issues.push({
          severity: 'error',
          rule: 'EAPEX050',
          file,
          line: lineOf(text, m.index),
          message: `quoteParams.put('${fieldName}', ...) uses ${literalType} literal for ${meta.type} field — use a compatible Apex type`
        });
      }
    }
  }
}

function lintRenewQuoteRequiredFields(text, file, indexed, issues) {
  if (!/\brenewQuote\s*\(/.test(text)) return;
  const quoteObject = indexed.byObject.get('zqu__Quote__c');
  if (!quoteObject) return;
  const required = quoteObject.entry.requiredFor?.renewQuote || [];
  if (required.length === 0) return;

  const selected = new Set();
  for (const block of extractSoqlBlocks(text)) {
    if (block.objectName !== 'zqu__Quote__c') continue;
    for (const fieldName of splitSelectFields(block.selectClause).map(normalizeSelectField).filter(Boolean)) {
      selected.add(fieldName);
    }
  }
  const missing = required.filter((fieldName) => !selected.has(fieldName));
  if (missing.length === 0) return;
  const anchor = text.search(/\brenewQuote\s*\(/);
  issues.push({
    severity: 'warn',
    rule: 'WAPEX051',
    file,
    line: lineOf(text, anchor),
    message: `renewQuote() requires SOQL fields on zqu__Quote__c: ${missing.join(', ')}`
  });
}

function lintText(text, file, catalog = loadCatalog(), fieldCatalog = loadFieldCatalog()) {
  const issues = [];
  const { zQuoteUtil, quoteInstance, metricsUtilMethods, recalcControllerMethods } = indexCatalog(catalog);
  const indexed = indexFieldCatalog(fieldCatalog);

  lintZQuoteUtilCalls(text, file, zQuoteUtil, issues);
  lintQuoteInstanceCalls(text, file, quoteInstance, issues);
  lintStaticClassCalls(text, file, 'MetricsUtil', metricsUtilMethods, 'EMET', issues);
  lintStaticClassCalls(text, file, 'QuoteRecalculateController', recalcControllerMethods, 'EREC', issues);
  lintQuoteCreationLifecycle(text, file, issues);

  const objectNames = ['Quote__c', 'QuoteRatePlan__c', 'QuoteRatePlanCharge__c', 'QuoteAmendment__c'];
  let m;
  for (const obj of objectNames) {
    const re = new RegExp(`(?<!zqu__)\\b${obj}\\b`, 'g');
    while ((m = re.exec(text))) {
      issues.push({ severity: 'warn', rule: 'WAPEX010', file, line: lineOf(text, m.index), message: `CPQ object "${obj}" is missing zqu__ namespace prefix` });
    }
  }

  const hardcoded = /(client_secret|password|Authorization\s*=|Bearer\s+[A-Za-z0-9._-]{12,})/i;
  if (hardcoded.test(text)) {
    issues.push({ severity: 'error', rule: 'EAPEX020', file, line: lineOf(text, text.search(hardcoded)), message: 'possible hardcoded credential or authorization token' });
  }

  const loopSoql = /for\s*\([^)]*\)\s*\{[\s\S]{0,600}\[[\s\S]{0,80}\bSELECT\b/i;
  if (loopSoql.test(text)) {
    issues.push({ severity: 'warn', rule: 'WAPEX030', file, line: lineOf(text, text.search(loopSoql)), message: 'SOQL appears inside a loop; bulkify this logic' });
  }

  lintCommonMistakes(text, file, indexed, issues);
  lintSoqlFields(text, file, indexed, issues);
  lintQuoteParamsPut(text, file, indexed, issues);
  lintRenewQuoteRequiredFields(text, file, indexed, issues);
  warnDuplicateNamespaceFieldFallbacks(text, file, issues);
  return issues;
}

function lintFiles(files) {
  const catalog = loadCatalog();
  const fieldCatalog = loadFieldCatalog();
  return files.flatMap((f) => lintText(fs.readFileSync(f, 'utf8'), f, catalog, fieldCatalog));
}

function main() {
  const args = process.argv.slice(2);
  const json = args.includes('--json');
  const targets = args.filter((a) => !a.startsWith('--'));
  if (targets.length === 0) {
    console.error('Usage: node scripts/lint-cpq-apex.js [--json] <file-or-dir>...');
    process.exit(2);
  }
  const files = collectFiles(targets);
  const issues = lintFiles(files);
  if (json) console.log(JSON.stringify({ files, issues }, null, 2));
  else {
    for (const i of issues) console.log(`${i.severity.toUpperCase()} ${i.rule} ${i.file}:${i.line || 1} ${i.message}`);
    console.log(`Checked ${files.length} Apex file(s), ${issues.length} issue(s).`);
  }
  if (issues.some((i) => i.severity === 'error')) process.exit(1);
}

if (require.main === module) main();
module.exports = { lintText, lintFiles, loadCatalog, loadFieldCatalog, indexFieldCatalog, indexCatalog };
