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

function methodSet(catalog) {
  const out = new Set();
  for (const cls of catalog.classes || []) {
    for (const m of cls.methods || []) {
      out.add(m.name);
      for (const a of m.aliases || []) out.add(a);
    }
  }
  return out;
}

function lintText(text, file, catalog = loadCatalog()) {
  const issues = [];
  const known = methodSet(catalog);
  const callRe = /(?:\bzqu\s*\.\s*)?\bzQuoteUtil\s*\.\s*([A-Za-z_]\w*)\s*\(/g;
  let m;
  while ((m = callRe.exec(text))) {
    if (!known.has(m[1])) {
      issues.push({ severity: 'error', rule: 'EAPEX001', file, line: lineOf(text, m.index), message: `unknown zQuoteUtil method "${m[1]}"` });
    }
  }

  const objectNames = ['Quote__c', 'QuoteRatePlan__c', 'QuoteRatePlanCharge__c', 'QuoteAmendment__c'];
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
  warnDuplicateNamespaceFieldFallbacks(text, file, issues);
  return issues;
}

function lintFiles(files) {
  const catalog = loadCatalog();
  return files.flatMap((f) => lintText(fs.readFileSync(f, 'utf8'), f, catalog));
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
module.exports = { lintText, lintFiles, loadCatalog };
