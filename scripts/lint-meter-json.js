#!/usr/bin/env node

/**
 * Structural and semantic linter for Zuora Mediation meter JSON.
 *
 * Catches the class of errors that would break import on the Zuora Mediation
 * server. Because the plugin has no access to the live mediation validator,
 * this lint script is the only pre-import safety net.
 *
 * Usage:
 *   node scripts/lint-meter-json.js <path> [<path> ...]
 *   node scripts/lint-meter-json.js --json <path>          # JSON-formatted report
 *   node scripts/lint-meter-json.js --quiet <path>         # summary only
 *   node scripts/lint-meter-json.js --no-warn <path>       # exit nonzero only on errors
 *   node scripts/lint-meter-json.js --assign-uuids <path>  # lint then rewrite non-UUID ids
 *
 * Also exports { lintMeter, loadRules } for use from tests.
 */

"use strict";

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const PLUGIN_REFS = path.join(__dirname, "..", "references");
const OPERATORS_DIR = path.join(PLUGIN_REFS, "meter-operators");

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// ajv is optional — E143 is skipped if not installed
let Ajv;
try { Ajv = require("ajv"); } catch (_) { /* not installed */ }

/**
 * Create Ajv validator instance for JSON schema validation.
 * Returns { ajv, ajvAvailable: boolean }.
 * Returns empty result if Ajv is not installed.
 */
function initAjv() {
  if (!Ajv) return { validators: {}, ajvAvailable: false };
  const ajv = new Ajv({ allErrors: true, strict: false });
  const validators = {};
  // We need operator skeletons loaded first, but this runs inside loadRules
  // so we pass already-loaded operators
  return { ajvAvailable: true, ajv };
}

function loadRules() {
  const manifest = JSON.parse(fs.readFileSync(path.join(OPERATORS_DIR, "_manifest.json"), "utf8"));
  const operators = {};
  const operatorsByCanonicalType = {};
  for (const fname of fs.readdirSync(OPERATORS_DIR)) {
    if (fname === "_manifest.json" || !fname.endsWith(".json")) continue;
    const skeleton = JSON.parse(fs.readFileSync(path.join(OPERATORS_DIR, fname), "utf8"));
    operators[fname.replace(/\.json$/, "")] = skeleton;
    if (skeleton.operatorType) {
      operatorsByCanonicalType[skeleton.operatorType] = skeleton;
    }
  }

  // Initialize Ajv validator for schema validation
  const { ajvAvailable, ajv } = initAjv();
  const validators = {};
  if (ajvAvailable) {
    for (const [fname, skeleton] of Object.entries(operators)) {
      if (skeleton.schema && typeof skeleton.schema === "object") {
        try {
          // Key by operatorType so E143 lookup by task.operatorType works
          const opType = skeleton.operatorType || fname;
          validators[opType] = ajv.compile(skeleton.schema);
        } catch (e) {
          console.error(`Warning: failed to compile schema for ${fname}: ${e.message}`);
        }
      }
    }
  }

  return { manifest, operators, operatorsByCanonicalType, validators, ajvAvailable };
}

// Intentionally deferred rules (documented in the spec self-review):
//   E141 — per-operator required-field-null check. Operator skeletons encode
//          "required" via a `blockers[]` array rather than a flat field list;
//          the design skill already honors blockers and the build skill fails
//          loudly if the user skipped them, so a redundant lint check would
//          duplicate that semantic.
//   W171 — JSON-boolean-where-string-expected. No failing case in the gold
//          corpus; adding without a concrete repro violates TDD.
//   W172 — optional-field-outside-documented-set. Same rationale as W171.
function lintMeter(meter, rules) {
  const issues = [];

  // E110 — top-level required keys
  for (const key of ["name", "type", "version"]) {
    if (meter[key] === undefined || meter[key] === null || meter[key] === "") {
      issues.push({ severity: "error", rule: "E110", message: `missing or empty top-level "${key}"` });
    }
  }

  // E111 — type is a valid string enum
  const VALID_TYPES = new Set(["CUSTOM", "DIRECT", "DELTA", "CUMULATIVE", "SUM", "MAX", "MIN", "COUNT", "AVG"]);
  if (meter.type !== undefined && meter.type !== null && meter.type !== "") {
    if (typeof meter.type !== "string" || !VALID_TYPES.has(meter.type)) {
      issues.push({
        severity: "error",
        rule: "E111",
        message: `invalid type ${JSON.stringify(meter.type)} — must be one of ${[...VALID_TYPES].join(", ")}`,
      });
    }
  }

  // E120 / E121 — type shape consistency
  if (meter.type === "CUSTOM") {
    if (!Array.isArray(meter.tasks)) {
      issues.push({ severity: "error", rule: "E120", message: "CUSTOM meter must have tasks[]" });
    }
    if (meter.typeDefinition !== undefined) {
      issues.push({ severity: "error", rule: "E120", message: "CUSTOM meter must not have typeDefinition" });
    }
  } else if (meter.type && VALID_TYPES.has(meter.type)) {
    if (!meter.typeDefinition || typeof meter.typeDefinition !== "object") {
      issues.push({ severity: "error", rule: "E121", message: `${meter.type} meter must have typeDefinition` });
    }
    if (meter.tasks !== undefined) {
      issues.push({ severity: "error", rule: "E121", message: `${meter.type} meter must not have tasks[]` });
    }
  }

  // E150 — predefined meter required fieldMappings
  if (meter.type && VALID_TYPES.has(meter.type) && meter.type !== "CUSTOM" && meter.typeDefinition) {
    const required = new Set(["accountNumber", "uom", "startDateTime"]);
    if (meter.type !== "COUNT") required.add("quantity");
    const mappings = Array.isArray(meter.typeDefinition.fieldMappings) ? meter.typeDefinition.fieldMappings : [];
    const present = new Set(mappings.map((m) => m && m.name).filter(Boolean));
    for (const name of required) {
      if (!present.has(name)) {
        issues.push({
          severity: "error",
          rule: "E150",
          message: `${meter.type} meter missing required fieldMapping "${name}"`,
        });
      }
    }
  }

  // E151 — type-specific required configs
  if (meter.type && meter.typeDefinition) {
    const configs = meter.typeDefinition.configs || {};
    if (meter.type === "CUMULATIVE" && !configs.cumulativeMethod) {
      issues.push({
        severity: "error",
        rule: "E151",
        message: "CUMULATIVE meter requires typeDefinition.configs.cumulativeMethod",
      });
    }
    if (["SUM", "MAX", "MIN", "COUNT", "AVG"].includes(meter.type) && !configs.cumulativePeriod) {
      issues.push({
        severity: "error",
        rule: "E151",
        message: `${meter.type} meter requires typeDefinition.configs.cumulativePeriod`,
      });
    }
  }

  // W170 — predefined meter's typeDefinition.schemaId looks like an unresolved name
  if (meter.typeDefinition && typeof meter.typeDefinition === "object") {
    const sid = meter.typeDefinition.schemaId;
    if (typeof sid === "string" && sid.length > 0 && !/^\d+$/.test(sid) && !UUID_RE.test(sid)) {
      issues.push({
        severity: "warn",
        rule: "W170",
        message: `typeDefinition.schemaId: value ${JSON.stringify(sid)} looks like an unresolved name, not an integer ID`,
      });
    }
  }

  // E130–E136 — task-level and graph-level checks
  if (Array.isArray(meter.tasks)) {
    const VALID_NODE_TYPES = new Set(["SOURCE", "PROCESSOR", "SINK"]);
    const idCounts = new Map();
    for (const t of meter.tasks) {
      if (t && t.id !== undefined && t.id !== null) {
        const k = String(t.id);
        idCounts.set(k, (idCounts.get(k) || 0) + 1);
      }
    }
    for (const [id, count] of idCounts) {
      if (count > 1) {
        issues.push({ severity: "error", rule: "E135", message: `duplicate task id ${JSON.stringify(id)} (${count}×)` });
      }
    }
    const idSet = new Set(idCounts.keys());

    for (const [idx, task] of meter.tasks.entries()) {
      const loc = `tasks[${idx}]`;
      if (task == null || typeof task !== "object") {
        issues.push({ severity: "error", rule: "E130", message: `${loc}: not an object` });
        continue;
      }
      for (const key of ["id", "name", "nodeType"]) {
        if (task[key] === undefined || task[key] === null || task[key] === "") {
          issues.push({ severity: "error", rule: "E130", message: `${loc}: missing "${key}"` });
        }
      }
      if (task.nodeType !== undefined && !VALID_NODE_TYPES.has(task.nodeType)) {
        issues.push({
          severity: "error",
          rule: "E131",
          message: `${loc}: invalid nodeType ${JSON.stringify(task.nodeType)}`,
        });
      }
      const preds = Array.isArray(task.predecessors) ? task.predecessors : [];
      if (task.nodeType === "SOURCE" && preds.length > 0) {
        issues.push({ severity: "error", rule: "E132", message: `${loc}: SOURCE must have empty predecessors` });
      }
      if ((task.nodeType === "PROCESSOR" || task.nodeType === "SINK") && preds.length === 0) {
        issues.push({
          severity: "error",
          rule: "E133",
          message: `${loc}: ${task.nodeType} must have at least one predecessor`,
        });
      }
      for (const p of preds) {
        if (p && p.id !== undefined && !idSet.has(String(p.id))) {
          issues.push({
            severity: "error",
            rule: "E134",
            message: `${loc}: predecessor ${JSON.stringify(p.id)} not found among task ids`,
          });
        }
      }
    }

    // E140 — operatorType must be a known canonical operatorType value from the operator skeletons
    for (const [idx, task] of meter.tasks.entries()) {
      const loc = `tasks[${idx}]`;
      if (!task || typeof task !== "object") continue;
      const opKey = task.operatorType || task.operator_key;
      if (opKey && !rules.operatorsByCanonicalType[opKey]) {
        issues.push({
          severity: "error",
          rule: "E140",
          message: `${loc}: operatorType ${JSON.stringify(opKey)} not found in manifest`,
        });
      }
      if (task.metadata && typeof task.metadata === "object") {
        for (const [k, v] of Object.entries(task.metadata)) {
          if (/Id$/.test(k) && typeof v === "string" && v.length > 0) {
            const isDigits = /^\d+$/.test(v);
            const isUuid = UUID_RE.test(v);
            if (!isDigits && !isUuid) {
              issues.push({
                severity: "warn",
                rule: "W170",
                message: `${loc}.metadata.${k}: value ${JSON.stringify(v)} looks like an unresolved name, not an integer ID`,
              });
            }
          }
        }
      }
    }

    // E143 — per-operator metadata field validation against operator schema (via ajv)
    if (rules.ajvAvailable) {
      const SCHEMA_RULE = "E143";
      for (const [idx, task] of meter.tasks.entries()) {
        if (!task || typeof task !== "object") continue;
        const opKey = task.operatorType || task.operator_key;
        if (!opKey) continue;
        const validateFn = rules.validators[opKey];
        if (!validateFn) continue; // no schema for this operator
        if (!task.metadata || typeof task.metadata !== "object") {
          issues.push({
            severity: "error",
            rule: SCHEMA_RULE,
            message: `tasks[${idx}].metadata: metadata required for operator ${opKey}`,
          });
          continue;
        }
        const valid = validateFn(task.metadata);
        if (!valid) {
          for (const err of validateFn.errors) {
            // Map ajv instancePath (e.g. "/appendFields/0") to ".appendFields[0]"
            const parts = err.instancePath ? err.instancePath.split("/").filter(Boolean) : [];
            const propPath = parts.length > 0
              ? "." + parts.join(".").replace(/\.(\d+)(\.|$)/g, (_, n, after) => `[${n}]${after === "." ? "." : ""}`)
              : "";
            issues.push({
              severity: "error",
              rule: SCHEMA_RULE,
              message: `tasks[${idx}].metadata${propPath}: ${err.message}`,
            });
          }
        }
      }
    }

    // E136 — cycle detection via iterative DFS
    const graph = new Map();
    for (const t of meter.tasks) {
      if (!t || t.id === undefined) continue;
      graph.set(String(t.id), (Array.isArray(t.predecessors) ? t.predecessors : []).map((p) => String(p && p.id)));
    }
    const WHITE = 0, GRAY = 1, BLACK = 2;
    const color = new Map();
    for (const id of graph.keys()) color.set(id, WHITE);
    let cycleFound = false;
    for (const start of graph.keys()) {
      if (cycleFound) break;
      if (color.get(start) !== WHITE) continue;
      const stack = [[start, 0]];
      color.set(start, GRAY);
      while (stack.length > 0) {
        const [node, i] = stack[stack.length - 1];
        const preds = graph.get(node) || [];
        if (i < preds.length) {
          const next = preds[i];
          stack[stack.length - 1][1] = i + 1;
          if (!graph.has(next)) continue;
          const c = color.get(next);
          if (c === GRAY) { cycleFound = true; break; }
          if (c === WHITE) {
            color.set(next, GRAY);
            stack.push([next, 0]);
          }
        } else {
          color.set(node, BLACK);
          stack.pop();
        }
      }
    }
    if (cycleFound) {
      issues.push({ severity: "error", rule: "E136", message: "cycle detected in task graph" });
    }
  }

  // E142 — unreplaced <<REQUIRED: ...>> sentinel anywhere in the JSON
  const SENTINEL_RE = /<<REQUIRED[^>]*>>/;
  (function walk(node, pathParts) {
    if (typeof node === "string") {
      if (SENTINEL_RE.test(node)) {
        issues.push({
          severity: "error",
          rule: "E142",
          message: `unreplaced sentinel at ${pathParts.join(".") || "(root)"}: ${node}`,
        });
      }
    } else if (Array.isArray(node)) {
      node.forEach((v, i) => walk(v, [...pathParts, `[${i}]`]));
    } else if (node && typeof node === "object") {
      for (const k of Object.keys(node)) walk(node[k], [...pathParts, k]);
    }
  })(meter, []);

  return issues;
}

function assignUuids(meter) {
  const tasks = Array.isArray(meter.tasks) ? meter.tasks : [];
  const idMap = {};
  for (const t of tasks) {
    if (!t || t.id == null) continue;
    const cur = String(t.id);
    idMap[cur] = UUID_RE.test(cur) ? cur : crypto.randomUUID();
  }
  const remap = (x) => (x == null ? x : (idMap[String(x)] || String(x)));
  for (const t of tasks) {
    if (t && t.id != null) t.id = remap(t.id);
    if (Array.isArray(t && t.predecessors)) {
      for (const p of t.predecessors) {
        if (p && p.id != null) p.id = remap(p.id);
      }
    }
  }
  return meter;
}

// ---- CLI ----
function main(argv) {
  const args = argv.slice(2);
  if (args.length === 0) {
    console.error("usage: lint-meter-json.js [--json|--quiet|--no-warn|--assign-uuids] <path> [<path>...]");
    process.exit(2);
  }
  const flags = {
    json: args.includes("--json"),
    quiet: args.includes("--quiet"),
    noWarn: args.includes("--no-warn"),
    assignUuids: args.includes("--assign-uuids"),
  };
  const files = args.filter((a) => !a.startsWith("--"));
  const rules = loadRules();
  let worstExit = 0;
  const report = [];
  for (const file of files) {
    let meter;
    try {
      meter = JSON.parse(fs.readFileSync(file, "utf8"));
    } catch (e) {
      report.push({ file, issues: [{ severity: "error", rule: "E100", message: e.message }] });
      worstExit = 1;
      continue;
    }
    const issues = lintMeter(meter, rules);
    const hasError = issues.some((i) => i.severity === "error");
    if (flags.assignUuids && !hasError) {
      assignUuids(meter);
      fs.writeFileSync(file, JSON.stringify(meter, null, 2) + "\n");
    }
    if (hasError) worstExit = 1;
    else if (!flags.noWarn && issues.length > 0) worstExit = Math.max(worstExit, 0);
    report.push({ file, issues });
  }
  if (flags.json) {
    console.log(JSON.stringify(report, null, 2));
  } else if (!flags.quiet) {
    for (const r of report) {
      console.log(`\n${r.file}:`);
      if (r.issues.length === 0) {
        console.log("  ✓ clean");
      } else {
        for (const i of r.issues) {
          console.log(`  ${i.severity === "error" ? "✗" : "!"} ${i.rule}: ${i.message}`);
        }
      }
    }
  } else {
    const errs = report.reduce((n, r) => n + r.issues.filter((i) => i.severity === "error").length, 0);
    const warns = report.reduce((n, r) => n + r.issues.filter((i) => i.severity === "warn").length, 0);
    console.log(`${files.length} file(s): ${errs} error(s), ${warns} warning(s)`);
  }
  process.exit(worstExit);
}

if (require.main === module) main(process.argv);

module.exports = { lintMeter, loadRules, assignUuids, UUID_RE };
