#!/usr/bin/env node
'use strict';
// Sandbox parity check for the v2 -> public API migration (read-only).
//
// For each card of a parity plan it reads the same record(s) through the v2 API and through the public Object Query
// route, then compares only the fields the customer's code reads, using the mapping of the shipped pack
// (references/v2-v1/pack). A card is "verified" only when every field the customer reads was compared and matched on
// every sampled record. "verified_with_limits": everything that could be compared matched, and the only fields skipped are
// limits the pack states itself (limitation, GraphQL only, not on this route); any other skip keeps the card "partial".
//
// Safety: GET requests only; sandbox hosts only (override with --allow-non-sandbox, not recommended); the token is
// requested or read from the environment and is never printed or written; a call cap bounds the run.
//
//   ZUORA_PARITY_BASE_URL           default https://rest.apisandbox.zuora.com
//   ZUORA_PARITY_BEARER_TOKEN       a ready bearer token, or
//   ZUORA_PARITY_CLIENT_ID + ZUORA_PARITY_CLIENT_SECRET   (client credentials; a token is requested from <base>/oauth/token)
//
// Usage: node compare-parity.js --plan parity-plan.json [--out parity-report.json] [--dry-run] [--max-calls 40]
//                               [--allow-non-sandbox]
//
// Plan:  { "cards": [ { "pack_id": "accounts.get", "route": "public_oq",
//                       "used_fields": ["account_number", "remaining_invoice_balance"],      // v2 field names the code reads
//                       "samples": [ { "key": "<id or number>" } ],                          // get cards
//                       "limit": 3,                                                          // list cards: records per page
//                       "v2": { "params": { "expand[]": ["bill_to"] } },
//                       "public": { "params": { "expand[]": ["billto"] } } } ] }
// The v2 and public request parameters come from the card of the migration plan; this tool does not translate them.

const fs = require('fs');
const path = require('path');

const PACK_DIR = path.resolve(__dirname, '../references/v2-v1/pack');
const arg = (n, d = null) => { const i = process.argv.indexOf(n); return i < 0 ? d : process.argv[i + 1]; };
const flag = (n) => process.argv.includes(n);

// ---- value helpers ----
function getPath(obj, p) {
  return String(p).split('.').reduce((o, k) => (o === null || o === undefined ? undefined : o[k]), obj);
}
function norm(v) {
  if (v === undefined || v === null || v === '') return null;
  if (typeof v === 'string' && /^-?\d+(\.\d+)?$/.test(v.trim())) return Number(v);
  if (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(v)) { const t = Date.parse(v); if (!Number.isNaN(t)) return t; }
  if (typeof v === 'number') return v;
  return v;
}
function same(a, b) {
  const x = norm(a); const y = norm(b);
  if (typeof x === 'number' && typeof y === 'number') return Math.abs(x - y) < 1e-9;
  return JSON.stringify(x) === JSON.stringify(y);
}
const short = (v) => { const s = JSON.stringify(v); return s === undefined ? 'undefined' : s.length > 80 ? s.slice(0, 77) + '...' : s; };

// ---- known transforms (pack items whose mapping is a rule, not a rename) ----
const STATE_MAPS = {
  invoices: { draft: ['Draft'], posted: ['Posted'], open: ['Posted'], canceled: ['Canceled'], failed: ['Error'] },
  billing_documents: { draft: ['Draft'], open: ['Posted'], uncollectible: ['Canceled'], failed: ['Error'] },
  subscriptions: { draft: ['Draft'], pending_activation: ['Pending Activation'], pending_acceptance: ['Pending Acceptance'], active: ['Active'], expired: ['Expired'], canceled: ['Cancelled'], paused: ['Suspended'] }
};
function customFields(rec) {
  const arr = rec.customFields || rec.custom_fields;
  const out = {};
  if (Array.isArray(arr)) {
    for (const e of arr) {
      let v = e.value;
      if (e.type === 'long' || e.type === 'number') v = v === null || v === undefined ? v : Number(v);
      else if (e.type === 'boolean') v = typeof v === 'string' ? JSON.parse(v) : v;
      out[e.key] = v;
    }
    return out;
  }
  for (const k of Object.keys(rec)) if (k.endsWith('__c')) out[k] = rec[k];
  return out;
}
function compareCustomFields(v2rec, pubrec) {
  const a = v2rec.custom_fields || {}; const b = customFields(pubrec);
  const keys = [...new Set([...Object.keys(a), ...Object.keys(b)])];
  const bad = keys.filter((k) => !same(a[k], b[k]));
  return bad.length ? { ok: false, v2: short(Object.fromEntries(bad.map((k) => [k, a[k]]))), pub: short(Object.fromEntries(bad.map((k) => [k, b[k]]))) } : { ok: true };
}
const family = (id) => id.split('.')[0];
const SPECIAL = {
  enabled: (v2, pub) => ({ ok: same(v2.enabled, pub.status === 'Active'), v2: short(v2.enabled), pub: short(pub.status) }),
  state: (v2, pub, id) => {
    const map = STATE_MAPS[family(id)]; if (!map) return null;
    const allowed = map[v2.state]; return { ok: !!allowed && allowed.includes(pub.status), v2: short(v2.state), pub: short(pub.status) };
  },
  paid: (v2, pub) => { if (pub.balance === undefined || pub.balance === null || !pub.status) return { ok: v2.paid === undefined || v2.paid === null, v2: short(v2.paid), pub: 'not derivable' }; const d = Number(pub.balance) === 0 && pub.status === 'Posted'; return { ok: same(v2.paid, d), v2: short(v2.paid), pub: short(d) }; },
  past_due: (v2, pub) => { if (!pub.dueDate || pub.balance === undefined || pub.balance === null || !pub.status) return { ok: v2.past_due === undefined || v2.past_due === null, v2: short(v2.past_due), pub: 'not derivable' }; const paid = Number(pub.balance) === 0 && pub.status === 'Posted'; const d = Date.parse(pub.dueDate) < Date.now() && !paid; return { ok: same(v2.past_due, d), v2: short(v2.past_due), pub: short(d) }; },
  custom_fields: (v2, pub) => compareCustomFields(v2, pub)
};

// ---- pack access ----
const readJson = (f) => JSON.parse(fs.readFileSync(f, 'utf8'));
function loadCard(packId, route) {
  const index = readJson(path.join(PACK_DIR, 'index.json'));
  const card = index.cards.find((c) => c.id === packId);
  if (!card) throw new Error(`unknown pack id ${packId}`);
  const file = card.files[route];
  if (!file) throw new Error(`${packId} has no route ${route}`);
  return { card, route: readJson(path.join(PACK_DIR, file)) };
}

// ---- HTTP (GET only) ----
let BASE = (process.env.ZUORA_PARITY_BASE_URL || 'https://rest.apisandbox.zuora.com').replace(/\/+$/, '');
let TOKEN = process.env.ZUORA_PARITY_BEARER_TOKEN || null;
let CALLS = 0; let MAX_CALLS = Number(arg('--max-calls', 40));
async function fetchRetry(url, init) {
  let last;
  for (let attempt = 0; attempt < 3; attempt++) {
    try { return await fetch(url, init); } catch (e) { last = e; await new Promise((r) => setTimeout(r, 1000 * (attempt + 1))); }
  }
  throw new Error('network error: ' + ((last && last.cause && last.cause.code) || (last && last.message)));
}
async function ensureToken() {
  if (TOKEN) return;
  const id = process.env.ZUORA_PARITY_CLIENT_ID; const secret = process.env.ZUORA_PARITY_CLIENT_SECRET;
  if (!id || !secret) throw new Error('Set ZUORA_PARITY_BEARER_TOKEN or ZUORA_PARITY_CLIENT_ID and ZUORA_PARITY_CLIENT_SECRET');
  const body = new URLSearchParams({ grant_type: 'client_credentials', client_id: id, client_secret: secret });
  const res = await fetchRetry(`${BASE}/oauth/token`, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body });
  if (!res.ok) throw new Error(`token request failed: HTTP ${res.status}`);
  TOKEN = (await res.json()).access_token;
  if (!TOKEN) throw new Error('token response has no access_token');
}
function qs(params) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params || {})) for (const x of Array.isArray(v) ? v : [v]) p.append(k, String(x));
  const s = p.toString(); return s ? '?' + s : '';
}
async function get(pathAndQuery) {
  if (CALLS >= MAX_CALLS) throw new Error(`call cap of ${MAX_CALLS} reached`);
  CALLS++;
  const res = await fetchRetry(BASE + pathAndQuery, { method: 'GET', headers: { Authorization: `Bearer ${TOKEN}`, Accept: 'application/json' } });
  let body = null; try { body = await res.json(); } catch (_) { /* not json */ }
  return { status: res.status, body };
}

// ---- card comparison ----
function requestsFor(plan, packCard, packRoute) {
  const isList = /\.(list|versions)$/.test(plan.pack_id);
  const v2Path = '/v2' + packCard.v2.path;
  const pubPath = packRoute.steps[0].path;
  const out = [];
  if (!isList) {
    for (const s of plan.samples || []) {
      const key = encodeURIComponent(s.key);
      out.push({ v2: v2Path.replace(/\{[^}]+\}/g, key) + qs(plan.v2 && plan.v2.params), pub: pubPath.replace(/\{[^}]+\}/g, key) + qs(plan.public && plan.public.params), list: false });
    }
  } else {
    const limit = plan.limit || 3;
    out.push({
      v2: v2Path.replace(/\{[^}]+\}/g, encodeURIComponent((plan.samples && plan.samples[0] && plan.samples[0].key) || '')) + qs(Object.assign({ page_size: limit }, plan.v2 && plan.v2.params)),
      pub: pubPath + qs(Object.assign({ pageSize: limit }, plan.public && plan.public.params)), list: true
    });
  }
  return out;
}

function itemFor(packRoute, v2Field) {
  return packRoute.response.find((i) => i.v2 === v2Field);
}
function pubValue(rec, item) {
  const f = ((item.target && item.target.field) || '').replace(/^data\[\]\./, '');
  return f ? getPath(rec, f) : undefined;
}

function compareRecord(plan, packRoute, v2rec, pubrec, fields) {
  const rows = [];
  for (const f of fields) {
    const item = itemFor(packRoute, f);
    if (!item) { rows.push({ field: f, verdict: 'skipped', reason: 'no pack item for this field' }); continue; }
    if (item.disposition === 'limitation') { rows.push({ field: f, verdict: 'skipped', reason: 'limitation (see the pack note)' }); continue; }
    if (item.disposition === 'not_on_route') { rows.push({ field: f, verdict: 'skipped', reason: 'not on this route' }); continue; }
    if (item.disposition === 'confirmed_via_graphql') { rows.push({ field: f, verdict: 'skipped', reason: 'GraphQL only' }); continue; }
    if (SPECIAL[f]) {
      const r = SPECIAL[f](v2rec, pubrec, plan.pack_id);
      if (r) { rows.push({ field: f, verdict: r.ok ? 'match' : 'mismatch', v2: r.ok ? undefined : r.v2, public: r.ok ? undefined : r.pub }); continue; }
    }
    const t = ((item.target && item.target.transform) || '').trim();
    if (item.computed_from || !(t === 'none' || t === 'rename' || t === '')) { rows.push({ field: f, verdict: 'skipped', reason: 'transform not checked automatically: ' + t.slice(0, 60) }); continue; }
    if (item.v2_type === 'object' || item.v2_type === 'array') { rows.push({ field: f, verdict: 'skipped', reason: 'nested value (compare through its own expand)' }); continue; }
    const tf = ((item.target && item.target.field) || '').replace(/^data\[\]\./, '');
    if (tf.includes('.')) {
      const rel = tf.split('.')[0].toLowerCase();
      const expands = [].concat((plan.public && plan.public.params && plan.public.params['expand[]']) || []).map((x) => String(x).toLowerCase());
      if (!expands.includes(rel)) { rows.push({ field: f, verdict: 'skipped', reason: `needs expand[]=${rel} on the public request` }); continue; }
    }
    const a = getPath(v2rec, f); const b = pubValue(pubrec, item);
    if (same(a, b)) rows.push({ field: f, verdict: 'match' });
    else if (norm(a) === null && norm(b) !== null) rows.push({ field: f, verdict: 'extra', v2: short(a), public: short(b) });
    else rows.push({ field: f, verdict: 'mismatch', v2: short(a), public: short(b) });
  }
  return rows;
}

async function runCard(plan, dry) {
  const { card, route } = loadCard(plan.pack_id, plan.route || 'public_oq');
  const reqs = requestsFor(plan, card, route);
  const result = { pack_id: plan.pack_id, route: plan.route || 'public_oq', calls: reqs.map((r) => ({ v2: 'GET ' + r.v2.replace(/Bearer.*/, ''), public: 'GET ' + r.pub })), records: 0, fields: {}, errors: [] };
  if (dry) return result;
  const fields = plan.used_fields && plan.used_fields.length ? plan.used_fields : route.response.filter((i) => i.disposition === 'confirmed' && !i.computed_from).map((i) => i.v2).filter((f) => !/[\[\]]/.test(f) && f !== 'data' && f !== 'next_page');
  for (const r of reqs) {
    const a = await get(r.v2); const b = await get(r.pub);
    if (a.status !== 200 || b.status !== 200) { result.errors.push(`v2 HTTP ${a.status}, public HTTP ${b.status}`); continue; }
    const pairs = [];
    if (r.list) {
      const pubRows = b.body.data || []; const byId = new Map(pubRows.map((x) => [x.id, x]));
      for (const x of a.body.data || []) if (byId.has(x.id)) pairs.push([x, byId.get(x.id)]);
      if (!pairs.length) result.errors.push('no record appears in both lists (compare by id)');
    } else pairs.push([a.body, b.body]);
    for (const [x, y] of pairs) {
      result.records++;
      for (const row of compareRecord(plan, route, x, y, fields)) {
        const e = result.fields[row.field] || (result.fields[row.field] = { match: 0, mismatch: 0, extra: 0, skipped: 0, reason: row.reason, examples: [] });
        e[row.verdict]++;
        if ((row.verdict === 'mismatch' || row.verdict === 'extra') && e.examples.length < 2) e.examples.push({ v2: row.v2, public: row.public });
        if (row.reason) e.reason = row.reason;
      }
    }
  }
  const f = Object.values(result.fields);
  const mism = f.some((e) => e.mismatch > 0); const skipped = f.some((e) => e.skipped > 0 && e.match === 0 && e.mismatch === 0 && e.extra === 0);
  // Verified needs zero request errors: a sample that could not be read means the card was not fully compared.
  // Skips the pack itself states as limits (limitation, GraphQL only, not on this route) do not make a card "partial":
  // the compared fields are verified and the stated limits stay as the plan says. Any other skip (a transform the tool does
  // not check, a nested value, a missing expand, a field without a pack item) still leaves the card partial.
  const STATED = /^(limitation|GraphQL only|not on this route)/;
  const onlyStated = f.filter((e) => e.skipped > 0 && !e.match && !e.mismatch && !e.extra).every((e) => STATED.test(e.reason || ''));
  const anyCompared = f.some((e) => e.match > 0 || e.extra > 0);
  result.verdict = mism ? 'mismatch' : (!result.records ? 'error' : (result.errors.length || (skipped && !(onlyStated && anyCompared))) ? 'partial' : (skipped ? 'verified_with_limits' : 'verified'));
  return result;
}

async function main() {
  const planFile = arg('--plan'); if (!planFile) { console.error('usage: compare-parity.js --plan parity-plan.json [--out report.json] [--dry-run] [--max-calls 40]'); process.exit(2); }
  const host = new URL(BASE).hostname;
  if (!/sandbox|\.test\.|^(localhost|127\.0\.0\.1)$/i.test(host) && !flag('--allow-non-sandbox')) throw new Error(`refusing to run against non-sandbox host ${host}`);
  const plan = readJson(planFile); const dry = flag('--dry-run');
  if (!dry) await ensureToken();
  const report = { generated_at: new Date().toISOString(), base_host: host, dry_run: dry, note: 'Read-only GET calls. Values appear only for mismatches and may contain tenant data: do not commit this file.', cards: [] };
  for (const c of plan.cards) { try { report.cards.push(await runCard(c, dry)); } catch (e) { report.cards.push({ pack_id: c.pack_id, verdict: 'error', errors: [String(e.message)] }); } }
  report.calls_made = CALLS;
  const out = arg('--out'); if (out) fs.writeFileSync(out, JSON.stringify(report, null, 2) + '\n');
  for (const c of report.cards) {
    if (dry) { console.log(`${c.pack_id}: ${c.calls.length} request pair(s)`); c.calls.forEach((x) => console.log('   ', x.v2, '|', x.public)); continue; }
    const fl = Object.entries(c.fields || {});
    console.log(`${c.pack_id}: ${c.verdict} (${c.records || 0} record(s); ${fl.filter(([, e]) => (e.match || e.extra) && !e.mismatch).length} fields match, ${fl.filter(([, e]) => e.mismatch).length} mismatch, ${fl.filter(([, e]) => !e.match && !e.mismatch && !e.extra).length} skipped, ${fl.filter(([, e]) => e.extra).length} where public returns a value v2 did not)`);
    for (const [k, e] of fl) if (e.mismatch) console.log(`    MISMATCH ${k}: v2 ${e.examples[0] && e.examples[0].v2} vs public ${e.examples[0] && e.examples[0].public}`);
    for (const [k, e] of fl) if (e.extra && !e.mismatch) console.log(`    NOTE ${k}: v2 returned nothing, public returns ${e.examples[0] && e.examples[0].public}`);
    for (const e of c.errors || []) console.log('    ERROR', e);
  }
  console.log(`calls made: ${CALLS}`);
}

module.exports = { norm, same, customFields, compareRecord, requestsFor, loadCard };
if (require.main === module) main().catch((e) => { console.error('error:', e.message); process.exit(1); });
