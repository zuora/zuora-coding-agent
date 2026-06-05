#!/usr/bin/env node

/**
 * Structural and semantic linter for Zuora Workflow JSON.
 *
 * Catches the class of errors that make Workflow::Setup.import fail or that
 * make a workflow correct-at-import-but-broken-at-runtime. Because Task.import
 * runs with validate: false and skips task_setup_validation, the linter is the
 * primary defense for parameter semantics.
 *
 * Usage:
 *   node scripts/lint-workflow-json.js <path> [<path> ...]
 *   node scripts/lint-workflow-json.js --json <path>          # JSON-formatted report
 *   node scripts/lint-workflow-json.js --quiet <path>         # Only summary
 *   node scripts/lint-workflow-json.js --no-warn <path>       # Exit nonzero only on errors
 *
 * Also exports { lintWorkflow, loadRules } for use from tests.
 */

"use strict";

const fs = require("fs");
const path = require("path");

const PLUGIN_REFS = path.join(__dirname, "..", "references");

// ---------- Utilities ----------

function readJson(p) {
  const raw = fs.readFileSync(p, "utf8");
  try {
    return JSON.parse(raw);
  } catch (e) {
    const err = new Error(`JSON parse error in ${p}: ${e.message}`);
    err.parseError = true;
    throw err;
  }
}

function getPath(obj, dottedPath) {
  if (obj == null) return undefined;
  const parts = dottedPath.split(".");
  let cur = obj;
  for (const part of parts) {
    if (cur == null || typeof cur !== "object") return undefined;
    cur = cur[part];
  }
  return cur;
}

function isPlainObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function isNonEmpty(v) {
  if (v == null) return false;
  if (typeof v === "string") return v.trim().length > 0;
  if (Array.isArray(v)) return v.length > 0;
  if (typeof v === "object") return Object.keys(v).length > 0;
  return true;
}

function workflowParameterObjectNames(standardFields) {
  const allowed = new Set(["Workflow", "Files"]);
  if (standardFields && isPlainObject(standardFields.objects)) {
    for (const objectName of Object.keys(standardFields.objects)) {
      allowed.add(objectName);
    }
  }
  return allowed;
}

function hasUnreplacedSentinel(value) {
  if (typeof value === "string") {
    return /<<[^>]*>>/.test(value);
  }
  if (Array.isArray(value)) {
    return value.some(hasUnreplacedSentinel);
  }
  if (isPlainObject(value)) {
    for (const k of Object.keys(value)) {
      if (hasUnreplacedSentinel(k)) return true;
      if (hasUnreplacedSentinel(value[k])) return true;
    }
  }
  return false;
}

function walkStrings(value, visit, pathParts = []) {
  if (typeof value === "string") {
    visit(value, pathParts.join("."));
  } else if (Array.isArray(value)) {
    value.forEach((v, i) => walkStrings(v, visit, pathParts.concat(`[${i}]`)));
  } else if (isPlainObject(value)) {
    for (const k of Object.keys(value)) {
      walkStrings(value[k], visit, pathParts.concat(k));
    }
  }
}

// ---------- Rules loading ----------

function loadRules(refDir) {
  refDir = refDir || PLUGIN_REFS;
  const templates = readJson(path.join(refDir, "workflow-task-templates.json"));
  const enums = readJson(path.join(refDir, "workflow-enums.json"));
  let railsTimezones = null;
  try {
    railsTimezones = readJson(path.join(refDir, "rails-timezones.json"));
  } catch (_) {
    railsTimezones = null;
  }
  let standardFields = null;
  try {
    standardFields = readJson(path.join(refDir, "zuora-standard-fields.json"));
  } catch (_) {
    standardFields = null;
  }
  return { templates, enums, railsTimezones, standardFields };
}

// ---------- Issue collector ----------

function makeCollector() {
  const errors = [];
  const warnings = [];
  return {
    errors,
    warnings,
    error(rule, msg, loc) {
      errors.push({ rule, msg, loc });
    },
    warn(rule, msg, loc) {
      warnings.push({ rule, msg, loc });
    },
  };
}

// ---------- Envelope / top-level rules ----------

function checkEnvelope(doc, out, enums, opts) {
  opts = opts || {};
  const railsTimezones = opts.railsTimezones || null;
  const standardFields = opts.standardFields || null;
  const required = ["workflow_definition", "workflow", "tasks", "linkages"];
  for (const key of required) {
    if (!(key in doc)) {
      out.error("E001", `Missing top-level "${key}" block`, `$`);
    }
  }

  if (!isPlainObject(doc.workflow)) {
    out.error("E002", `"workflow" must be an object`, `$.workflow`);
    return;
  }

  const w = doc.workflow;

  // E003: type must be Workflow::Setup
  if (w.type !== undefined && w.type !== "Workflow::Setup") {
    out.error(
      "E003",
      `workflow.type must be the literal string "Workflow::Setup" (got ${JSON.stringify(
        w.type
      )}). Rails overrides this on import but a stable export matches Workflow::Setup#export.`,
      `$.workflow.type`
    );
  }

  // E004: workflow.id must be a positive integer
  if (!Number.isInteger(w.id) || w.id <= 0) {
    out.error(
      "E004",
      `workflow.id must be a positive integer (got ${JSON.stringify(w.id)})`,
      `$.workflow.id`
    );
  }

  // E005: at least one trigger flag true. Workflow::Setup permits multiple
  // trigger flags on one workflow and validates each enabled trigger's
  // prerequisites independently.
  const triggerFlags = [
    "ondemand_trigger",
    "callout_trigger",
    "scheduled_trigger",
    "event_trigger",
  ];
  const triggerValues = triggerFlags.map((f) => ({ f, v: w[f] }));
  const trueTriggers = triggerValues.filter((t) => t.v === true);
  if (trueTriggers.length === 0) {
    out.error(
      "E005",
      `No trigger flag set. At least one of ${triggerFlags.join(
        ", "
      )} must be true.`,
      `$.workflow`
    );
  }

  // E006: scheduled_trigger => interval + timezone
  if (w.scheduled_trigger === true) {
    if (!isNonEmpty(w.interval)) {
      out.error(
        "E006",
        `scheduled_trigger is true but workflow.interval is blank. Set a cron expression.`,
        `$.workflow.interval`
      );
    }
    if (!isNonEmpty(w.timezone)) {
      out.error(
        "E006",
        `scheduled_trigger is true but workflow.timezone is blank. Set a Rails ActiveSupport timezone friendly name (e.g., "UTC", "Eastern Time (US & Canada)", "London", "Tokyo"). See references/rails-timezones.json for the canonical list.`,
        `$.workflow.timezone`
      );
    }
    const promptFields =
      isPlainObject(w.parameters) && Array.isArray(w.parameters.fields)
        ? w.parameters.fields
        : [];
    promptFields.forEach((field, index) => {
      if (!isPlainObject(field)) return;
      const required = field.required === true || field.required === "true";
      const value = field.default;
      const blankDefault =
        value === null ||
        value === undefined ||
        (typeof value === "string" && value.trim().length === 0);
      if (required && blankDefault) {
        out.error(
          "E006",
          `scheduled_trigger is true but workflow.parameters.fields[${index}] (${field.field_name || "unnamed"}) is required and has a blank default. Scheduled runs cannot prompt a user; provide a default or make the field optional.`,
          `$.workflow.parameters.fields[${index}].default`
        );
      }
    });
  }

  // E007: event_trigger => parameters.event_triggers non-empty array
  if (w.event_trigger === true) {
    const evts = getPath(w, "parameters.event_triggers");
    if (!Array.isArray(evts) || evts.length === 0) {
      out.error(
        "E007",
        `event_trigger is true but workflow.parameters.event_triggers is not a non-empty array.`,
        `$.workflow.parameters.event_triggers`
      );
    }
  }

  // W123: event metadata is configured but the workflow is not actually event-triggered.
  if (w.event_trigger !== true && isPlainObject(w.parameters)) {
    const evts = w.parameters.event_triggers;
    const ep = w.parameters.event_parameters;
    const hasEventTriggers = Array.isArray(evts) && evts.some((name) => isNonEmpty(name));
    const hasEventParameters = Array.isArray(ep) && ep.length > 0;
    if (hasEventTriggers || hasEventParameters) {
      out.warn(
        "W123",
        `workflow.parameters.${
          hasEventTriggers ? "event_triggers" : "event_parameters"
        } is configured but workflow.event_trigger is not true. Set workflow.event_trigger = true when the workflow should run from a standard or custom event; custom event names are allowed in event_triggers[] once registered.`,
        `$.workflow.event_trigger`
      );
    }
  }

  // E008: call_type must be a known value (any user-facing OR deprecated value)
  // E150 (below) is the stricter rule that forbids deprecated values.
  if (w.call_type != null) {
    const userFacing = (enums.workflow_call_types.user_facing || []).map((c) => c.value);
    const deprecated = enums.workflow_call_types.deprecated_or_internal || [];
    const allKnown = userFacing.concat(deprecated);
    if (!allKnown.includes(w.call_type)) {
      out.error(
        "E008",
        `workflow.call_type "${w.call_type}" is not a known value. Known: ${JSON.stringify(
          userFacing
        )} (user-facing) or ${JSON.stringify(deprecated)} (deprecated/internal).`,
        `$.workflow.call_type`
      );
    }
  }

  // E115: workflow.name must be a non-empty string
  if (w.name !== undefined && (typeof w.name !== "string" || w.name.trim().length === 0)) {
    out.error(
      "E115",
      `workflow.name must be a non-empty string (got ${JSON.stringify(w.name)})`,
      `$.workflow.name`
    );
  }

  // E116: workflow.data must be an empty object
  if (w.data !== undefined && (!isPlainObject(w.data) || Object.keys(w.data).length > 0)) {
    out.error(
      "E116",
      `workflow.data must be an empty object {} (got ${JSON.stringify(w.data)}). Workflow::Instance#set_data populates this at runtime; populating it at import time has no effect.`,
      `$.workflow.data`
    );
  }

  // E118: workflow.status should be "Inactive" on import (use activate_version: true to flip on)
  if (w.status === "Active") {
    out.error(
      "E118",
      `workflow.status "Active" is invalid in import payload. Always emit "Inactive" and pass activate_version: true to the import_workflow tool to flip it on.`,
      `$.workflow.status`
    );
  }

  // E119: workflow must NOT carry ui_trigger (not a column on workflows; silently dropped)
  if ("ui_trigger" in w) {
    out.error(
      "E119",
      `workflow.ui_trigger is NOT a column on the workflows table. Workflow::Setup.import slices the input against Workflow.column_names and silently drops this key. Use call_type "UIACTION" or "SYNC_UI_ACTION" + ui_pages instead.`,
      `$.workflow.ui_trigger`
    );
  }

  // E119: workflow.parameters must NOT carry merge_task_ids (auto-derived; deleted on save)
  if (isPlainObject(w.parameters) && "merge_task_ids" in w.parameters) {
    out.error(
      "E119",
      `workflow.parameters.merge_task_ids is auto-derived during Logic::Merge validation; Workflow::Setup.import deletes any inbound value before save (workflow/setup.rb:452, 468). Do not emit this key.`,
      `$.workflow.parameters.merge_task_ids`
    );
  }

  // E124: JSON run-prompt defaults must be non-null and size-able.
  // Workflow::Setup validation calls field['default'].size for JSON fields, so nil,
  // booleans, or numbers raise NoMethodError before a user-friendly import error.
  const promptFields =
    isPlainObject(w.parameters) && Array.isArray(w.parameters.fields)
      ? w.parameters.fields
      : [];

  // E126: workflow run-prompt fields must use Workflow import keys, not UI/agent-adapter keys.
  // Rails expects field_name/datatype/default/object_name. Shapes like
  // name/label/type/default_value look plausible but do not bind as Data.Workflow.*.
  promptFields.forEach((field, index) => {
    if (!isPlainObject(field)) return;
    const uiStyleKeys = ["name", "label", "type", "default_value"].filter((key) =>
      Object.prototype.hasOwnProperty.call(field, key)
    );
    if (uiStyleKeys.length === 0) return;
    const missingCanonicalKeys = ["field_name", "datatype", "default", "object_name"].filter(
      (key) => !Object.prototype.hasOwnProperty.call(field, key)
    );
    if (missingCanonicalKeys.length === 0) return;
    out.error(
      "E126",
      `workflow.parameters.fields[${index}] uses UI-style key(s) ${uiStyleKeys.join(
        ", "
      )} but is missing Workflow import key(s) ${missingCanonicalKeys.join(
        ", "
      )}. Emit run-prompt fields with index, field_name, datatype, default, required, and object_name (usually "Workflow"), not name/label/type/default_value.`,
      `$.workflow.parameters.fields[${index}]`
    );
  });

  promptFields.forEach((field, index) => {
    if (!isPlainObject(field) || field.datatype !== "JSON") return;
    const value = field.default;
    const validDefault =
      typeof value === "string" || Array.isArray(value) || isPlainObject(value);
    if (!validDefault) {
      out.error(
        "E124",
        `workflow.parameters.fields[${index}] (${field.field_name || "unnamed"}) has datatype JSON but default ${JSON.stringify(
          value
        )}. Workflow::Setup validation calls default.size for JSON fields; use ""/[]/{} (or a valid JSON string) instead of null, boolean, or number.`,
        `$.workflow.parameters.fields[${index}].default`
      );
    }
  });

  // E125: workflow parameter object_name must be a real run-prompt namespace.
  // The server/UI expects workflow-level inputs under Workflow (Data.Workflow.*),
  // file uploads under Files, or a supported Zuora object exposed by the dropdown.
  // Invented grouping objects such as BillRunConfig create invalid prompt syntax.
  const allowedParameterObjects = workflowParameterObjectNames(standardFields);
  promptFields.forEach((field, index) => {
    if (!isPlainObject(field)) return;
    const fieldName = field.field_name || "unnamed";
    const objectName = field.object_name;
    const loc = `$.workflow.parameters.fields[${index}].object_name`;
    if (typeof objectName !== "string" || objectName.trim().length === 0) {
      out.error(
        "E125",
        `workflow.parameters.fields[${index}] (${fieldName}) must set object_name to "Workflow" for ordinary workflow inputs, "Files" for File-Field uploads, or a supported Zuora object name from the run-prompt dropdown.`,
        loc
      );
      return;
    }
    const normalizedObjectName = objectName.trim();
    if (!allowedParameterObjects.has(normalizedObjectName)) {
      out.error(
        "E125",
        `workflow.parameters.fields[${index}] (${fieldName}) uses object_name "${objectName}", which is not a supported workflow parameter object. Use "Workflow" for ordinary workflow inputs like filters and dates, "Files" for File-Field uploads, or a real Zuora object available in the run-prompt dropdown; do not invent grouping objects.`,
        loc
      );
    }
  });

  // E120: parameters.event_parameters shape (when present, even if event_trigger is false)
  if (isPlainObject(w.parameters) && w.parameters.event_parameters !== undefined) {
    const ep = w.parameters.event_parameters;
    if (!Array.isArray(ep)) {
      out.error(
        "E120",
        `workflow.parameters.event_parameters must be an array (got ${
          ep === null ? "null" : isPlainObject(ep) ? "object" : typeof ep
        }). The React UI sometimes serializes it as an object with numeric keys; the composer MUST normalize to an array.`,
        `$.workflow.parameters.event_parameters`
      );
    } else {
      ep.forEach((entry, i) => {
        const epLoc = `$.workflow.parameters.event_parameters[${i}]`;
        if (!isPlainObject(entry)) {
          out.error("E120", `event_parameters[${i}] must be an object`, epLoc);
          return;
        }
        if (typeof entry.eventName !== "string" || entry.eventName.length === 0) {
          out.error(
            "E120",
            `event_parameters[${i}].eventName must be a non-empty string`,
            `${epLoc}.eventName`
          );
        }
        if (!Array.isArray(entry.params)) {
          out.error(
            "E120",
            `event_parameters[${i}].params must be an array (got ${
              entry.params === null ? "null" : typeof entry.params
            }). Both event_parameters AND its inner params MUST be JSON arrays for BusinessEvent#parse_event to bind multi-field events correctly.`,
            `${epLoc}.params`
          );
        } else {
          entry.params.forEach((p, j) => {
            const pLoc = `${epLoc}.params[${j}]`;
            if (!isPlainObject(p)) {
              out.error("E120", `event_parameters[${i}].params[${j}] must be an object`, pLoc);
              return;
            }
            for (const k of ["object", "key", "value"]) {
              if (typeof p[k] !== "string" || p[k].length === 0) {
                out.error(
                  "E120",
                  `event_parameters[${i}].params[${j}].${k} must be a non-empty string (got ${JSON.stringify(
                    p[k]
                  )})`,
                  `${pLoc}.${k}`
                );
              }
            }
          });
        }
      });
    }
  }

  // E122: when event_trigger == true, every event_parameters[*].eventName must be in event_triggers[]
  if (w.event_trigger === true && isPlainObject(w.parameters)) {
    const evts = w.parameters.event_triggers;
    const ep = w.parameters.event_parameters;
    if (Array.isArray(evts) && Array.isArray(ep)) {
      const evtSet = new Set(evts);
      ep.forEach((entry, i) => {
        if (isPlainObject(entry) && typeof entry.eventName === "string" && !evtSet.has(entry.eventName)) {
          out.error(
            "E122",
            `event_parameters[${i}].eventName "${
              entry.eventName
            }" is not declared in workflow.parameters.event_triggers ${JSON.stringify(
              Array.from(evtSet)
            )}. Each event_parameters entry must correspond to a registered event trigger.`,
            `$.workflow.parameters.event_parameters[${i}].eventName`
          );
        }
      });
    }
  }

  // W121: unknown event names (not in standard_events catalog and no MCP preflight confirmation)
  if (w.event_trigger === true && isPlainObject(w.parameters)) {
    const evts = w.parameters.event_triggers;
    const stdNames = new Set(
      ((enums.standard_events && enums.standard_events.events) || []).map((e) => e.name)
    );
    const corrections = (enums.standard_events && enums.standard_events.$canonical_name_corrections) || {};
    if (Array.isArray(evts)) {
      evts.forEach((name, i) => {
        if (typeof name !== "string") return;
        if (stdNames.has(name)) return;
        const correction = corrections[name];
        if (correction) {
          out.warn(
            "W121",
            `event_triggers[${i}] "${name}" is not a canonical Zuora event name; did you mean "${correction}"? See workflow-events.md.`,
            `$.workflow.parameters.event_triggers[${i}]`
          );
        } else {
          out.warn(
            "W121",
            `event_triggers[${i}] "${name}" is not in the standard event catalog and was not confirmed via MCP preflight. The workflow will not fire until this custom event is registered (Settings -> Notifications -> Custom Events, or POST /events/event-triggers).`,
            `$.workflow.parameters.event_triggers[${i}]`
          );
        }
      });
    }
  }

  // E177 / W179: event_parameters[].params[].value token validation.
  //
  // workflow/rails/app/models/business_event.rb L143-185 defines how a token is resolved:
  //   1. Tokens in $event_special_tokens always resolve (Event.Category, Event.Date,
  //      Event.Timestamp, Functions.Today, Tenant.ID, Tenant.Name).
  //   2. Any other <X...X> value has its angle brackets and optional `DataSource.` /
  //      `Event.` prefix stripped, then used as a LITERAL key on the Avro payload.
  //   3. Literal (non-angle-bracket) values pass through unchanged.
  //
  // What we can validate statically:
  //   - E177 (hard error): the token is `<BaseObject.Field>` style and `BaseObject` does
  //     NOT match the event's declared baseObject per
  //     references/zuora-standard-fields.json#/$event_base_objects.events[eventName].
  //     Every Zuora-published event exposes its baseObject as the dropdown namespace, so
  //     a mismatched prefix means the agent guessed a token that will 100% resolve to nil.
  //   - W179 (warning): the token is not a recognised special token and the agent did
  //     not demonstrate a describe step. Cannot verify the payload key statically; flag
  //     so the composer confirms against /notifications/email-templates/info/selections.
  if (
    isPlainObject(w.parameters) &&
    Array.isArray(w.parameters.event_parameters) &&
    Array.isArray(w.parameters.event_triggers) &&
    standardFields &&
    isPlainObject(standardFields.$event_base_objects) &&
    isPlainObject(standardFields.$event_base_objects.events)
  ) {
    const baseObjectMap = standardFields.$event_base_objects.events;
    const specialTokens = new Set(
      (standardFields.$event_special_tokens && Array.isArray(standardFields.$event_special_tokens.tokens)
        ? standardFields.$event_special_tokens.tokens
        : [])
    );
    const standardEventByName = new Map(
      ((enums.standard_events && enums.standard_events.events) || []).map((evt) => [evt.name, evt])
    );
    const eventCategoryHint = (eventName) => {
      const event = standardEventByName.get(eventName);
      if (event && event.id) return event.id;
      return `<namespace>:${eventName}`;
    };

    w.parameters.event_parameters.forEach((entry, i) => {
      if (!isPlainObject(entry)) return;
      const eventName = typeof entry.eventName === "string" ? entry.eventName : "";
      const declaredBaseObject = baseObjectMap[eventName];
      if (!Array.isArray(entry.params)) return;
      entry.params.forEach((p, j) => {
        if (!isPlainObject(p)) return;
        const value = typeof p.value === "string" ? p.value.trim() : "";
        if (value.length === 0) return;
        const pLoc = `$.workflow.parameters.event_parameters[${i}].params[${j}].value`;

        // Non-angle-bracket values: Rails passes them through unchanged. This is a
        // valid pattern (static literal) and out of scope for token validation.
        if (!(value.startsWith("<") && value.endsWith(">"))) return;

        // Special tokens -- always resolve, no further checks.
        if (specialTokens.has(value)) return;

        // Strip angle brackets and the optional DataSource. / Event. prefix.
        let stripped = value.slice(1, -1);
        let prefixType = null;
        if (stripped.startsWith("DataSource.")) {
          prefixType = "DataSource";
          stripped = stripped.slice("DataSource.".length);
        } else if (stripped.startsWith("Event.")) {
          prefixType = "Event";
          stripped = stripped.slice("Event.".length);
        }

        // Dot-path form: "<BaseObject.Field>" or "<Event.BaseObject.Field>" etc.
        if (stripped.includes(".")) {
          const dotIdx = stripped.indexOf(".");
          const prefix = stripped.slice(0, dotIdx);
          const rest = stripped.slice(dotIdx + 1);
          if (declaredBaseObject && prefix !== declaredBaseObject && prefixType !== "Event" && prefixType !== "DataSource") {
            out.error(
              "E177",
              `event_parameters[${i}].params[${j}].value "${value}" starts with "<${prefix}." but the event "${eventName}" declares baseObject="${declaredBaseObject}" (references/zuora-standard-fields.json#/$event_base_objects.events). Either switch the token to "<${declaredBaseObject}.${rest}>" (if ${declaredBaseObject}.${rest} is published in the notifications mergeFields for this event) or, if you intended a payload key unrelated to the baseObject, prefix it with "Event." (e.g. "<Event.${prefix}.${rest}>") so Rails strips the Event. prefix and looks up "${prefix}.${rest}" as a literal payload key. Discover the real token list via GET /notifications/email-templates/info/selections?category=${eventCategoryHint(eventName)} (standard events use the 4-digit event id; custom events use namespace:eventName; mcp__zuora-mcp__ask_zuora can fetch it).`,
              pLoc
            );
            return;
          }
          // Prefix matches the declared baseObject OR the event has no registered baseObject
          // OR the agent used an Event./DataSource. escape -- all three are valid, but we
          // cannot statically confirm the payload actually publishes this field. Emit W179.
          out.warn(
            "W179",
            `event_parameters[${i}].params[${j}].value "${value}" is not a Rails-recognised special token (${Array.from(specialTokens).join(", ")}). The resolved payload key will be "${stripped}". Confirm via GET /notifications/email-templates/info/selections?category=${eventCategoryHint(eventName)} (standard events use the 4-digit event id; custom events use namespace:eventName; mcp__zuora-mcp__ask_zuora can fetch it) that the notifications service publishes "${stripped}" for this event -- otherwise Data.${p.object || declaredBaseObject || "?"}.${p.key || "?"} will be nil at runtime.`,
            pLoc
          );
        } else {
          // Single-token form: "<Foo>" -- resolves to payload["Foo"] (or payload["Foo"] after
          // stripping Event./DataSource. prefix). Always legal, but unverifiable statically.
          out.warn(
            "W179",
            `event_parameters[${i}].params[${j}].value "${value}" is a single-segment merge token. Rails will look up "${stripped}" in the event Avro payload. Confirm via GET /notifications/email-templates/info/selections?category=${eventCategoryHint(eventName)} (standard events use the 4-digit event id; custom events use namespace:eventName; mcp__zuora-mcp__ask_zuora can fetch it) that this key is published -- otherwise Data.${p.object || declaredBaseObject || "?"}.${p.key || "?"} will be nil.`,
            pLoc
          );
        }
      });
    });
  }

  // W133: scheduled_trigger interval format. Rufus::Scheduler accepts 5-token Unix cron,
  // 6-token cron (with seconds), and shorthand durations (e.g., "5m"). We only flag clearly
  // malformed values: whitespace-separated strings with token count outside 5 or 6.
  if (w.scheduled_trigger === true && typeof w.interval === "string" && w.interval.trim().length > 0) {
    const trimmed = w.interval.trim();
    if (/\s/.test(trimmed)) {
      const tokens = trimmed.split(/\s+/);
      if (tokens.length !== 5 && tokens.length !== 6) {
        out.warn(
          "W133",
          `workflow.interval "${w.interval}" has ${tokens.length} whitespace-separated tokens; cron strings should have 5 (Unix) or 6 (with seconds) tokens. See workflow-enums.json -> interval_schema.examples.`,
          `$.workflow.interval`
        );
      }
    }
  }

  // E175: scheduled_trigger.timezone must be a Rails ActiveSupport friendly name.
  // Validated server-side by `validates :timezone, inclusion: ActiveSupport::TimeZone.all.map(&:name)`
  // (workflow/setup.rb L32). Bare IANA strings like "America/New_York" FAIL even though Rufus
  // would parse them, because import-time validation rejects them before they reach the scheduler.
  if (
    w.scheduled_trigger === true &&
    typeof w.timezone === "string" &&
    w.timezone.trim().length > 0 &&
    railsTimezones &&
    isPlainObject(railsTimezones.mapping)
  ) {
    const tz = w.timezone.trim();
    if (!Object.prototype.hasOwnProperty.call(railsTimezones.mapping, tz)) {
      const ianaMap = railsTimezones.iana_to_friendly_recommendations || {};
      const suggestion = ianaMap[tz];
      const hint = suggestion
        ? ` Did you mean "${suggestion}"?`
        : ` See references/rails-timezones.json for the canonical list.`;
      out.error(
        "E175",
        `workflow.timezone "${w.timezone}" is not a Rails ActiveSupport friendly name. The Rails validator (workflow/setup.rb L32) only accepts entries from ActiveSupport::TimeZone.all.map(&:name) -- bare IANA strings like "America/New_York" are rejected.${hint}`,
        `$.workflow.timezone`
      );
    }
  }

  // E140: notifications consistency (any boolean flag true => emails non-empty; vice versa)
  if (isPlainObject(w.notifications)) {
    const n = w.notifications;
    const flags = ["failure", "success", "pending", "skipped_scheduled_run"];
    const anyFlagTrue = flags.some((f) => n[f] === true);
    const emails = Array.isArray(n.emails) ? n.emails.filter((e) => typeof e === "string" && e.trim().length > 0) : [];
    if (anyFlagTrue && emails.length === 0) {
      out.error(
        "E140",
        `workflow.notifications has at least one boolean flag set to true (failure/success/pending/skipped_scheduled_run) but emails[] is empty. Workflow::Setup validates that recipients exist when notifications are enabled (workflow/setup.rb:194-196).`,
        `$.workflow.notifications.emails`
      );
    }
    if (!anyFlagTrue && emails.length > 0) {
      out.warn(
        "W140",
        `workflow.notifications.emails has ${emails.length} recipient(s) but no boolean flag is true; no notifications will fire.`,
        `$.workflow.notifications`
      );
    }
    if (typeof n.error_ignore === "string" && n.error_ignore.length > 0) {
      try {
        new RegExp(n.error_ignore);
      } catch (e) {
        out.error(
          "E140",
          `workflow.notifications.error_ignore "${n.error_ignore}" is not a valid regular expression: ${e.message}`,
          `$.workflow.notifications.error_ignore`
        );
      }
    }
  }

  // E150: deprecated call_type values are forbidden by the React settings UI and the composer
  if (w.call_type != null) {
    const deprecated = enums.workflow_call_types.deprecated_or_internal || [];
    if (deprecated.includes(w.call_type)) {
      const replacement = { ASYNC: "BATCH", RULE: "BUSINESS_PROCESS", UI: "UIACTION" }[w.call_type] || "BATCH";
      out.error(
        "E150",
        `workflow.call_type "${w.call_type}" is deprecated/internal. Use "${replacement}" instead. The React settings UI hides these (workflows_controller.rb:20-21).`,
        `$.workflow.call_type`
      );
    }
  }

  // E153: workflow.version must match the version regex
  if (w.version != null && enums.version_regex) {
    const re = new RegExp(enums.version_regex);
    if (typeof w.version !== "string" || !re.test(w.version)) {
      out.error(
        "E153",
        `workflow.version ${JSON.stringify(w.version)} must match ${enums.version_regex} (e.g., "0.0.1", "1", "2.3").`,
        `$.workflow.version`
      );
    }
  }

  // E160: UIACTION/SYNC_UI_ACTION require ui_pages with exactly one entry from supported_ui_pages
  if (["UIACTION", "SYNC_UI_ACTION"].includes(w.call_type)) {
    const uiPages = w.ui_pages;
    if (!isPlainObject(uiPages) || Object.keys(uiPages).length === 0) {
      out.error(
        "E160",
        `workflow.call_type "${w.call_type}" requires workflow.ui_pages to declare exactly one entry. Shape: { "<page-key>": { "label": "<button label>" } }. See workflow-enums.json -> supported_ui_pages.pages.`,
        `$.workflow.ui_pages`
      );
    } else if (Object.keys(uiPages).length > 1) {
      out.error(
        "E160",
        `workflow.ui_pages must have exactly one entry for ${w.call_type} (got ${Object.keys(uiPages).length}: ${JSON.stringify(Object.keys(uiPages))}).`,
        `$.workflow.ui_pages`
      );
    } else {
      const supportedValues = new Set(
        ((enums.supported_ui_pages && enums.supported_ui_pages.pages) || []).map((p) => p.value)
      );
      const key = Object.keys(uiPages)[0];
      if (!supportedValues.has(key)) {
        out.error(
          "E160",
          `workflow.ui_pages key "${key}" is not in supported_ui_pages.pages. Allowed: ${JSON.stringify(
            Array.from(supportedValues)
          )}.`,
          `$.workflow.ui_pages`
        );
      } else if (!isPlainObject(uiPages[key]) || typeof uiPages[key].label !== "string" || uiPages[key].label.trim().length === 0) {
        out.error(
          "E160",
          `workflow.ui_pages["${key}"] must be an object with a non-empty string "label" (got ${JSON.stringify(uiPages[key])}).`,
          `$.workflow.ui_pages.${key}`
        );
      }
    }
  } else if (isPlainObject(w.ui_pages) && Object.keys(w.ui_pages).length > 0) {
    out.warn(
      "W160",
      `workflow.ui_pages is populated but workflow.call_type "${w.call_type}" is not UIACTION/SYNC_UI_ACTION; ui_pages will be ignored.`,
      `$.workflow.ui_pages`
    );
  }

  // E009: priority enum
  if (
    w.priority != null &&
    !enums.workflow_priorities.includes(w.priority)
  ) {
    out.error(
      "E009",
      `workflow.priority "${w.priority}" is not in ${JSON.stringify(
        enums.workflow_priorities
      )}`,
      `$.workflow.priority`
    );
  }

  // E010: status enum
  if (w.status != null && !enums.workflow_statuses.includes(w.status)) {
    out.error(
      "E010",
      `workflow.status "${w.status}" is not in ${JSON.stringify(
        enums.workflow_statuses
      )}`,
      `$.workflow.status`
    );
  }

  // W011: css pixel suffix
  if (isPlainObject(w.css)) {
    for (const k of ["top", "left"]) {
      if (w.css[k] != null && typeof w.css[k] === "string" && !/px$/.test(w.css[k])) {
        out.warn(
          "W011",
          `workflow.css.${k} "${w.css[k]}" should end with "px"`,
          `$.workflow.css.${k}`
        );
      }
    }
  }

  // E012: tasks non-empty
  if (!Array.isArray(doc.tasks) || doc.tasks.length === 0) {
    out.error(
      "E012",
      `"tasks" must be a non-empty array. Workflow::Setup.import raises "No tasks present in import payload" on an empty array.`,
      `$.tasks`
    );
  }

  // E013: linkages non-empty
  if (!Array.isArray(doc.linkages) || doc.linkages.length === 0) {
    out.error(
      "E013",
      `"linkages" must be a non-empty array. Workflow::Setup.import raises "No linkages present in import payload" on an empty array.`,
      `$.linkages`
    );
  }
}

// ---------- Per-task rules ----------

function checkTasks(doc, out, templates, enums) {
  if (!Array.isArray(doc.tasks)) return;

  const seenIds = new Set();

  doc.tasks.forEach((task, i) => {
    const loc = `$.tasks[${i}]`;
    if (!isPlainObject(task)) {
      out.error("E100", `tasks[${i}] must be an object`, loc);
      return;
    }

    // E101: id integer and unique
    if (!Number.isInteger(task.id)) {
      out.error(
        "E101",
        `tasks[${i}].id must be an integer (got ${JSON.stringify(task.id)})`,
        `${loc}.id`
      );
    } else if (seenIds.has(task.id)) {
      out.error(
        "E101",
        `tasks[${i}].id ${task.id} is duplicated`,
        `${loc}.id`
      );
    } else {
      seenIds.add(task.id);
    }

    // E102: name
    if (typeof task.name !== "string" || task.name.trim().length === 0) {
      out.error("E102", `tasks[${i}].name must be a non-empty string`, `${loc}.name`);
    }

    // E103: parameters object
    if (!isPlainObject(task.parameters)) {
      out.error(
        "E103",
        `tasks[${i}].parameters must be an object (got ${
          task.parameters === null ? "null" : Array.isArray(task.parameters) ? "array" : typeof task.parameters
        }). Task.import calls parameters.merge! which raises NoMethodError on nil.`,
        `${loc}.parameters`
      );
    }

    if (task.action_type === "Data::Warehouse") {
      out.error(
        "E184",
        `tasks[${i}].action_type "Data::Warehouse" is not supported for generated Workflow JSON. Use Data::Link / Data Query for SQL-style row queries that feed downstream Workflow tasks, or Query/Export/Data::Aqua for supported Zuora object reads.`,
        `${loc}.action_type`
      );
      return;
    }

    // E104: action_type
    if (!task.action_type || !enums.action_types.includes(task.action_type)) {
      out.error(
        "E104",
        `tasks[${i}].action_type "${
          task.action_type
        }" is not a known action_type. See workflow-enums.json.action_types for the canonical list.`,
        `${loc}.action_type`
      );
      return; // Can't validate further without a template
    }

    const template = templates[task.action_type];
    if (!template) {
      out.warn(
        "W105",
        `tasks[${i}].action_type "${task.action_type}" is in the enum list but has no template in workflow-task-templates.json`,
        `${loc}.action_type`
      );
      return;
    }

    // E106: required_params
    const requiredParams = template.required_params || [];
    for (const paramPath of requiredParams) {
      const v = getPath(task.parameters, paramPath);
      if (!isNonEmpty(v)) {
        out.error(
          "E106",
          `tasks[${i}] (${task.action_type}) is missing required parameter "${paramPath}"`,
          `${loc}.parameters.${paramPath}`
        );
      }
    }

    // E107: required_at_import — top-level task attributes
    const requiredAtImport = template.required_at_import || [];
    for (const attr of requiredAtImport) {
      const v = task[attr];
      if (!isNonEmpty(v)) {
        out.error(
          "E107",
          `tasks[${i}] (${task.action_type}) is missing required_at_import attribute "${attr}". This top-level attribute is validated by ActiveRecord column presence on import.`,
          `${loc}.${attr}`
        );
      }
    }

    // E108: param_enums
    const paramEnums = template.param_enums || {};
    for (const [paramPath, allowedValues] of Object.entries(paramEnums)) {
      const v = getPath(task.parameters, paramPath);
      if (v != null && !allowedValues.includes(v)) {
        out.error(
          "E108",
          `tasks[${i}] (${task.action_type}) parameter "${paramPath}" = ${JSON.stringify(
            v
          )} is not in allowed enum ${JSON.stringify(allowedValues)}`,
          `${loc}.parameters.${paramPath}`
        );
      }
    }

    // E109: boolean_string_params
    const booleanStringParams = template.boolean_string_params || [];
    for (const paramPath of booleanStringParams) {
      const v = getPath(task.parameters, paramPath);
      if (v == null) continue;
      if (typeof v === "boolean") {
        out.error(
          "E109",
          `tasks[${i}] (${task.action_type}) parameter "${paramPath}" must be the STRING "true"/"false", not the JSON boolean ${v}. Rails parses these with .to_bool which expects strings.`,
          `${loc}.parameters.${paramPath}`
        );
      } else if (typeof v !== "string" || !["true", "false"].includes(v.toLowerCase())) {
        out.warn(
          "W109",
          `tasks[${i}] (${task.action_type}) parameter "${paramPath}" = ${JSON.stringify(
            v
          )} should be the string "true" or "false"`,
          `${loc}.parameters.${paramPath}`
        );
      }
    }

    // E110: unreplaced sentinel tokens
    if (hasUnreplacedSentinel(task)) {
      out.error(
        "E110",
        `tasks[${i}] (${task.action_type}) still contains an unreplaced composition sentinel token (e.g., <<REQUIRED: ...>>, <<TASK_ID>>). All placeholders must be replaced before writing.`,
        loc
      );
    }

    // E111: Logic::Case — sequential Case_N keys
    if (task.action_type === "Logic::Case") {
      const conditions = getPath(task.parameters, "case_condition");
      if (isPlainObject(conditions)) {
        const keys = Object.keys(conditions);
        const caseKeys = keys.filter((k) => /^Case_\d+$/.test(k));
        const elseKeys = keys.filter((k) => k === "Case_Else");
        const otherKeys = keys.filter(
          (k) => !/^Case_\d+$/.test(k) && k !== "Case_Else"
        );
        if (otherKeys.length > 0) {
          out.error(
            "E111",
            `tasks[${i}] (Logic::Case) parameters.case_condition contains non-canonical keys ${JSON.stringify(
              otherKeys
            )}. Use sequential Case_1, Case_2, ..., Case_Else. Rails renumbers on save and destroys linkages that don't map.`,
            `${loc}.parameters.case_condition`
          );
        }
        // E112: sequential numbering
        const nums = caseKeys
          .map((k) => parseInt(k.slice(5), 10))
          .sort((a, b) => a - b);
        for (let n = 0; n < nums.length; n++) {
          if (nums[n] !== n + 1) {
            out.error(
              "E112",
              `tasks[${i}] (Logic::Case) parameters.case_condition keys must be sequential Case_1..Case_N. Found ${JSON.stringify(
                caseKeys
              )}.`,
              `${loc}.parameters.case_condition`
            );
            break;
          }
        }
        // W113: else keys duplicated or out of place
        if (elseKeys.length > 1) {
          out.warn(
            "W113",
            `tasks[${i}] (Logic::Case) parameters.case_condition has multiple Case_Else keys`,
            `${loc}.parameters.case_condition`
          );
        }
      }
    }
  });
}

// ---------- Linkage / graph rules ----------

const STATIC_LINKAGE_TYPES = new Set([
  "Start",
  "Success",
  "Failure",
  "True",
  "False",
  "Complete",
  "For Each",
  "Approve",
  "Reject",
  "Upload",
  "Timeout",
  "next",
  "error",
]);

function isValidLinkageType(linkageType, sourceHooks) {
  if (typeof linkageType !== "string" || linkageType.length === 0) return false;
  if (STATIC_LINKAGE_TYPES.has(linkageType)) return true;
  if (/^Case_\d+$/.test(linkageType)) return true;
  if (linkageType === "Case_Else") return true;
  if (/^Page:.+/.test(linkageType)) return true;
  if (/^Webshare:.+/.test(linkageType)) return true;
  if (sourceHooks && sourceHooks.includes(linkageType)) return true;
  return false;
}

function checkLinkages(doc, out, templates, enums) {
  if (!Array.isArray(doc.linkages)) return;

  const taskById = new Map();
  (doc.tasks || []).forEach((t) => {
    if (isPlainObject(t) && Number.isInteger(t.id)) {
      taskById.set(t.id, t);
    }
  });

  const workflowId = doc.workflow && doc.workflow.id;
  let startLinkages = 0;
  const typoHints = enums.typo_hints || {};

  // First pass: per-linkage validation
  doc.linkages.forEach((l, i) => {
    const loc = `$.linkages[${i}]`;
    if (!isPlainObject(l)) {
      out.error("E200", `linkages[${i}] must be an object`, loc);
      return;
    }

    // E201: linkage_type non-empty string
    if (typeof l.linkage_type !== "string" || l.linkage_type.length === 0) {
      out.error(
        "E201",
        `linkages[${i}].linkage_type must be a non-empty string`,
        `${loc}.linkage_type`
      );
      return;
    }

    // W202: typo hint
    if (typoHints[l.linkage_type]) {
      out.warn(
        "W202",
        `linkages[${i}].linkage_type "${l.linkage_type}" looks like a typo — did you mean "${typoHints[l.linkage_type]}"?`,
        `${loc}.linkage_type`
      );
    }

    // E203: Start linkage shape
    if (l.linkage_type === "Start") {
      startLinkages++;
      if (l.source_workflow_id !== workflowId) {
        out.error(
          "E203",
          `linkages[${i}] (Start) source_workflow_id ${JSON.stringify(
            l.source_workflow_id
          )} must equal workflow.id ${workflowId}`,
          `${loc}.source_workflow_id`
        );
      }
      if (l.source_task_id != null) {
        out.error(
          "E203",
          `linkages[${i}] (Start) source_task_id must be null (got ${JSON.stringify(
            l.source_task_id
          )})`,
          `${loc}.source_task_id`
        );
      }
      if (l.target_task_id == null || !taskById.has(l.target_task_id)) {
        out.error(
          "E203",
          `linkages[${i}] (Start) target_task_id ${JSON.stringify(
            l.target_task_id
          )} does not match any task id`,
          `${loc}.target_task_id`
        );
      }
      return; // Start's linkage_type is intrinsically valid
    }

    // E204: non-Start linkage shape
    if (l.source_workflow_id != null && l.source_task_id != null) {
      out.warn(
        "W204",
        `linkages[${i}] has BOTH source_workflow_id and source_task_id set. The Rails source-XOR validation is currently disabled but this is almost always a bug.`,
        loc
      );
    } else if (l.source_workflow_id == null && l.source_task_id == null) {
      out.warn(
        "W204",
        `linkages[${i}] has NEITHER source_workflow_id nor source_task_id set. A non-Start linkage needs source_task_id.`,
        loc
      );
    }

    if (l.source_task_id != null && !taskById.has(l.source_task_id)) {
      out.error(
        "E205",
        `linkages[${i}].source_task_id ${l.source_task_id} does not match any task id`,
        `${loc}.source_task_id`
      );
    }
    if (l.target_task_id != null && !taskById.has(l.target_task_id)) {
      out.error(
        "E206",
        `linkages[${i}].target_task_id ${l.target_task_id} does not match any task id`,
        `${loc}.target_task_id`
      );
    }

    // E207: linkage_type ∈ source task hooks
    if (l.source_task_id != null && taskById.has(l.source_task_id)) {
      const sourceTask = taskById.get(l.source_task_id);
      const template = templates[sourceTask.action_type];
      const sourceHooks = template ? template.hooks : null;
      if (!isValidLinkageType(l.linkage_type, sourceHooks)) {
        const hint = typoHints[l.linkage_type]
          ? ` Did you mean "${typoHints[l.linkage_type]}"?`
          : ``;
        out.error(
          "E207",
          `linkages[${i}].linkage_type "${l.linkage_type}" is not a valid hook on source task ${sourceTask.id} (${sourceTask.action_type}). Allowed hooks: ${JSON.stringify(
            sourceHooks || ["Success", "Failure"]
          )}.${hint}`,
          `${loc}.linkage_type`
        );
      }
    }
  });

  // E208: exactly one Start linkage
  if (startLinkages === 0) {
    out.error(
      "E208",
      `No Start linkage found. Every workflow needs exactly one linkage with linkage_type "Start", source_workflow_id = workflow.id, source_task_id = null.`,
      `$.linkages`
    );
  } else if (startLinkages > 1) {
    out.error(
      "E208",
      `Multiple Start linkages found (${startLinkages}). A workflow must have exactly one.`,
      `$.linkages`
    );
  }

  // Graph warnings
  checkGraph(doc, out, taskById);

  // E300: Case_N linkages match Logic::Case keys
  checkCaseLinkageConsistency(doc, out, taskById);
}

// Collect (sourceTaskId|'workflow') -> [{ target, linkageType, index }]
function buildAdjacency(doc) {
  const adj = new Map();
  (doc.linkages || []).forEach((l, i) => {
    if (!isPlainObject(l)) return;
    const source =
      l.source_workflow_id != null ? "workflow" : l.source_task_id;
    if (source == null) return;
    if (!adj.has(source)) adj.set(source, []);
    adj.get(source).push({ target: l.target_task_id, linkageType: l.linkage_type, index: i });
  });
  return adj;
}

function checkGraph(doc, out, taskById) {
  const adj = buildAdjacency(doc);

  // Orphans: tasks with no incoming edge (neither Start-targeted nor task-targeted).
  const inbound = new Set();
  (doc.linkages || []).forEach((l) => {
    if (isPlainObject(l) && l.target_task_id != null) {
      inbound.add(l.target_task_id);
    }
  });
  for (const id of taskById.keys()) {
    if (!inbound.has(id)) {
      const task = taskById.get(id);
      out.warn(
        "W301",
        `Task ${id} (${task.action_type} - "${task.name}") has no inbound linkage — it is orphaned and unreachable.`,
        `$.tasks[id=${id}]`
      );
    }
  }

  // Cycle detection via DFS
  const WHITE = 0, GRAY = 1, BLACK = 2;
  const color = new Map();
  for (const id of taskById.keys()) color.set(id, WHITE);

  function dfs(id, stack) {
    color.set(id, GRAY);
    stack.push(id);
    const edges = adj.get(id) || [];
    for (const e of edges) {
      if (e.target == null) continue;
      const c = color.get(e.target);
      if (c === GRAY) {
        const cycleStart = stack.indexOf(e.target);
        const cyclePath = stack.slice(cycleStart).concat(e.target);
        out.warn(
          "W302",
          `Cycle detected in workflow graph: ${cyclePath.join(
            " -> "
          )}. Rails will import this without error but the workflow will loop at runtime.`,
          `$.linkages`
        );
        break;
      } else if (c === WHITE) {
        dfs(e.target, stack);
      }
    }
    stack.pop();
    color.set(id, BLACK);
  }

  // Start DFS from any workflow-sourced targets (Start linkages)
  const starts = (adj.get("workflow") || []).map((e) => e.target);
  for (const s of starts) {
    if (s != null && color.get(s) === WHITE) {
      dfs(s, []);
    }
  }
  // Any remaining WHITE task is unreachable from Start (already warned above).

  // For Each before Logic::Merge rule
  checkForEachMergeRule(doc, out, taskById, adj);
}

function checkForEachMergeRule(doc, out, taskById, adj) {
  const mergeTaskIds = [];
  for (const [id, t] of taskById.entries()) {
    if (t.action_type === "Logic::Merge") mergeTaskIds.push(id);
  }
  if (mergeTaskIds.length === 0) return;

  // For each merge task M, DFS all paths from 'workflow' to M collecting the
  // sequence of linkage types traversed. Flag any path containing "For Each".
  for (const mergeId of mergeTaskIds) {
    const paths = [];
    function dfs(node, pathTypes, visited) {
      if (node === mergeId) {
        paths.push(pathTypes.slice());
        return;
      }
      const edges = adj.get(node) || [];
      for (const e of edges) {
        if (e.target == null) continue;
        if (visited.has(e.target)) continue; // avoid infinite loop on cycles
        visited.add(e.target);
        pathTypes.push(e.linkageType);
        dfs(e.target, pathTypes, visited);
        pathTypes.pop();
        visited.delete(e.target);
      }
    }
    dfs("workflow", [], new Set(["workflow"]));
    for (const p of paths) {
      if (p.includes("For Each")) {
        out.error(
          "E303",
          `Logic::Merge task ${mergeId} is reachable via a path containing a "For Each" linkage (path types: ${JSON.stringify(
            p
          )}). Rails rejects this via Linkage#avoid_for_each_linkage_before_merge_task.`,
          `$.linkages`
        );
        break;
      }
    }
  }
}

function checkCaseLinkageConsistency(doc, out, taskById) {
  (doc.tasks || []).forEach((task) => {
    if (!isPlainObject(task) || task.action_type !== "Logic::Case") return;
    const conditions = getPath(task.parameters, "case_condition");
    if (!isPlainObject(conditions)) return;
    const declaredCaseKeys = new Set(
      Object.keys(conditions).filter((k) => /^Case_\d+$/.test(k))
    );

    (doc.linkages || []).forEach((l, i) => {
      if (!isPlainObject(l)) return;
      if (l.source_task_id !== task.id) return;
      if (!/^Case_\d+$/.test(l.linkage_type)) return;
      if (!declaredCaseKeys.has(l.linkage_type)) {
        out.error(
          "E304",
          `linkages[${i}] has linkage_type "${l.linkage_type}" but Logic::Case task ${
            task.id
          } does not declare that case key in parameters.case_condition (keys: ${JSON.stringify(
            Array.from(declaredCaseKeys)
          )}).`,
          `$.linkages[${i}].linkage_type`
        );
      }
    });
  });
}

function isAssignOnlyLiquid(code) {
  if (typeof code !== "string" || code.trim().length === 0) return false;
  const assignPattern = /{%-?\s*assign\s+[A-Za-z_][\w]*\s*=\s*[^%]*?-?%}/g;
  const hasAssign = assignPattern.test(code);
  assignPattern.lastIndex = 0;
  const stripped = code.replace(assignPattern, "").trim();
  return stripped.length === 0 && hasAssign;
}

function isManualArraySelectionLiquid(code) {
  if (typeof code !== "string" || code.trim().length === 0) return false;

  const resultMatch = code.match(
    /{%-?\s*assign\s+([A-Za-z_][\w]*)\s*=\s*(?:null|nil|empty|empty_array|''|"")\s*\|\s*array\s*-?%}/
  );
  if (!resultMatch) return false;
  const resultVar = resultMatch[1];

  const forMatch = code.match(/{%-?\s*for\s+([A-Za-z_][\w]*)\s+in\s+[^%]+-?%}/);
  if (!forMatch) return false;
  const loopVar = forMatch[1];

  const conditionalPattern = new RegExp(`{%-?\\s*(?:if|unless)\\s+[^%]*\\b${loopVar}\\b`);
  if (!conditionalPattern.test(code)) return false;

  const pushPattern = new RegExp(
    `{%-?\\s*assign\\s+${resultVar}\\s*=\\s*${resultVar}\\s*\\|\\s*push\\s*:\\s*${loopVar}\\b`
  );
  return pushPattern.test(code);
}

function liquidOutputScope(task) {
  const params = isPlainObject(task) ? task.parameters : null;
  const placement = params && typeof params.placement === "string" ? params.placement.trim() : "";
  return placement || "Liquid";
}

function taskConsumesLiquidOutput(task, scope, assignedVars) {
  const refs = extractDataReferences(task, "");
  return refs.some((ref) => {
    if (ref.scope !== scope) return false;
    if (ref.fieldPath.length === 0) return true;
    return assignedVars.has(ref.fieldPath[0]);
  });
}

function updateFieldNames(task) {
  if (!isPlainObject(task) || task.action_type !== "Update") return [];
  if (!isPlainObject(task.parameters) || !isPlainObject(task.parameters.fields)) return [];
  const objectName = typeof task.object === "string" ? task.object.trim() : "";
  const fieldsForObject = isPlainObject(task.parameters.fields[objectName])
    ? task.parameters.fields[objectName]
    : null;
  if (!fieldsForObject) return [];
  return Object.keys(fieldsForObject).filter((fieldName) => fieldName !== "fieldsToNull");
}

function normalizedUpdateObjectId(task) {
  if (!isPlainObject(task) || typeof task.object_id !== "string") return "";
  return task.object_id.replace(/\s+/g, " ").trim();
}

const SUPPORTED_BILL_RUN_PARAMS = new Set([
  "AccountId",
  "AutoEmail",
  "AutoPost",
  "AutoRenewal",
  "Batch",
  "BillCycleDay",
  "BillRunApi",
  "BillRunMode",
  "ChargeTypeToExclude",
  "InvoiceDate",
  "NoEmailForZeroAmountInvoice",
  "SourceBillRunId",
  "SubscriptionIds",
  "TargetDate",
  "delete_payload_paths",
  "disable_validation",
  "poll_time",
  "strict_variables",
  "workflow_tags",
]);

function unsupportedBillRunFilterParams(task) {
  if (!isPlainObject(task) || task.action_type !== "Billing::BillRun") return [];
  const params = isPlainObject(task.parameters) ? task.parameters : {};
  return Object.keys(params).filter((key) => {
    if (SUPPORTED_BILL_RUN_PARAMS.has(key)) return false;
    return /filter/i.test(key) || /accountnumber|batchnumber|prpc|productrateplancharge/i.test(key);
  });
}

function isLegacySubscriptionCancelTask(task) {
  return isPlainObject(task) && task.action_type === "Cancel";
}

function checkCompositionQuality(doc, out) {
  if (!Array.isArray(doc.tasks) || !Array.isArray(doc.linkages)) return;

  const taskById = new Map();
  const taskIndexById = new Map();
  doc.tasks.forEach((task, i) => {
    if (isPlainObject(task) && Number.isInteger(task.id)) {
      taskById.set(task.id, task);
      taskIndexById.set(task.id, i);
    }
  });

  const outgoingBySource = new Map();
  doc.linkages.forEach((linkage) => {
    if (!isPlainObject(linkage) || !Number.isInteger(linkage.source_task_id)) return;
    if (!outgoingBySource.has(linkage.source_task_id)) outgoingBySource.set(linkage.source_task_id, []);
    outgoingBySource.get(linkage.source_task_id).push(linkage);
  });

  for (const [taskId, task] of taskById.entries()) {
    if (task.action_type !== "Logic::Liquid") continue;
    const code = isPlainObject(task.parameters) ? task.parameters.code : "";
    if (!isManualArraySelectionLiquid(code)) continue;
    const taskIndex = taskIndexById.get(taskId);
    out.warn(
      "W184",
      `Logic::Liquid task ${taskId} manually builds a filtered array with for/if/push. Zuora Workflow registers custom filters from rails/lib/liquid/filters.rb; prefer where/where_exp for array selection or group_by/group_by_exp for grouping before writing a manual loop. Keep the loop only when it is intentionally transforming rows or performing more than simple filtering.`,
      Number.isInteger(taskIndex) ? `$.tasks[${taskIndex}].parameters.code` : `$.tasks[id=${taskId}].parameters.code`
    );
  }

  for (const [taskId, task] of taskById.entries()) {
    if (task.action_type !== "Logic::Liquid") continue;
    const assignedVars = scanLiquidAssigns(isPlainObject(task.parameters) ? task.parameters.code : "");
    if (assignedVars.size === 0) continue;

    const outgoingEdges = outgoingBySource.get(taskId) || [];
    const successEdges = outgoingEdges.filter((edge) => edge.linkage_type === "Success");
    if (outgoingEdges.length !== 1 || successEdges.length !== 1) continue;

    const downstreamTask = taskById.get(successEdges[0].target_task_id);
    if (!downstreamTask) continue;

    const outputScope = liquidOutputScope(task);
    if (!taskConsumesLiquidOutput(downstreamTask, outputScope, assignedVars)) continue;

    const consumerIds = new Set();
    for (const [otherId, otherTask] of taskById.entries()) {
      if (otherId === taskId) continue;
      if (taskConsumesLiquidOutput(otherTask, outputScope, assignedVars)) {
        consumerIds.add(otherId);
      }
    }
    if (consumerIds.size !== 1 || !consumerIds.has(downstreamTask.id)) continue;

    const taskIndex = taskIndexById.get(taskId);
    out.warn(
      "W187",
      `Logic::Liquid task ${taskId} only prepares ${Array.from(assignedVars).join(", ")} for immediate downstream task ${downstreamTask.id} (${downstreamTask.action_type}). This is usually an avoidable Liquid shim: inline the calculation, condition, or request body Liquid into the downstream task's own parameters (for example Export/Query predicates, Logic::Case clauses, or Callout raw_body) to keep the workflow graph smaller. Keep a separate Liquid task when the value is reused by multiple tasks, normalizes a large shared payload, or needs independent failure/retry/review behavior.`,
      Number.isInteger(taskIndex) ? `$.tasks[${taskIndex}]` : `$.tasks[id=${taskId}]`
    );
  }

  for (const [taskId, task] of taskById.entries()) {
    const unsupportedParams = unsupportedBillRunFilterParams(task);
    if (unsupportedParams.length === 0) continue;
    const taskIndex = taskIndexById.get(taskId);
    out.warn(
      "W185",
      `Billing::BillRun task ${taskId} includes unsupported bill-run filter parameter(s): ${unsupportedParams.join(", ")}. The OOTB Bill Run task only supports standard bill-run fields plus AccountId/SubscriptionIds for v1 single-account/subscription filters. If the requirement needs filters such as BatchNumberFilter, AccountNumberFilter, or APM/ProductRatePlanCharge IDs, use a custom Zuora Callout to the bill run API instead of Billing::BillRun.`,
      Number.isInteger(taskIndex) ? `$.tasks[${taskIndex}].parameters` : `$.tasks[id=${taskId}].parameters`
    );
  }

  for (const [taskId, task] of taskById.entries()) {
    if (!isLegacySubscriptionCancelTask(task)) continue;
    const taskIndex = taskIndexById.get(taskId);
    out.warn(
      "W189",
      `Cancel task ${taskId} uses the legacy SOAP subscription-cancel amendment task. For the new API stack, model subscription cancellation with a Zuora Callout to the Orders API (resource path "orders") containing an orderActions entry with type "CancelSubscription", and set authorization.type = "zuora". Keep the SOAP Cancel task only when the user explicitly asks for a legacy amendment workflow.`,
      Number.isInteger(taskIndex) ? `$.tasks[${taskIndex}]` : `$.tasks[id=${taskId}]`
    );
  }

  for (const [firstId, firstTask] of taskById.entries()) {
    if (firstTask.action_type !== "Data::Link") continue;
    const firstSuccessEdges = (outgoingBySource.get(firstId) || []).filter((edge) => edge.linkage_type === "Success");

    for (const edgeToLiquid of firstSuccessEdges) {
      const liquidTask = taskById.get(edgeToLiquid.target_task_id);
      if (!liquidTask || liquidTask.action_type !== "Logic::Liquid") continue;
      const liquidCode = isPlainObject(liquidTask.parameters) ? liquidTask.parameters.code : "";
      if (!isAssignOnlyLiquid(liquidCode)) continue;
      if (!/Data\.(LinkRun|Link)\.first|Data\.(LinkRun|Link)\[[0-9]+\]/.test(liquidCode)) continue;

      const liquidSuccessEdges = (outgoingBySource.get(liquidTask.id) || []).filter((edge) => edge.linkage_type === "Success");
      for (const edgeToSecondQuery of liquidSuccessEdges) {
        const secondTask = taskById.get(edgeToSecondQuery.target_task_id);
        if (!secondTask || secondTask.action_type !== "Data::Link") continue;
        const liquidIndex = taskIndexById.get(liquidTask.id);
        out.warn(
          "W180",
          `Data::Link task ${firstId} feeds assign-only Logic::Liquid task ${liquidTask.id}, which then feeds Data::Link task ${secondTask.id}. This is usually an avoidable two-query design. If the first query only resolves scalar context (for example ProductRatePlanId from a run-prompt charge id), fold it into the second Data::Link SQL with a CTE/CROSS JOIN and project those scalar values on each result row; downstream Iterate/Callout tasks can then use row.<field> directly. Keep separate queries only when the first query is intentionally reused by multiple branches, must stop the workflow independently, or cannot be expressed in the same query.`,
          Number.isInteger(liquidIndex) ? `$.tasks[${liquidIndex}]` : `$.tasks[id=${liquidTask.id}]`
        );
      }
    }
  }

  for (const [firstId, firstTask] of taskById.entries()) {
    if (!firstTask || firstTask.action_type !== "Update") continue;
    const objectName = typeof firstTask.object === "string" ? firstTask.object.trim() : "";
    const objectId = normalizedUpdateObjectId(firstTask);
    const firstFields = updateFieldNames(firstTask);
    if (!objectName || !objectId || firstFields.length === 0) continue;

    const firstSuccessEdges = (outgoingBySource.get(firstId) || []).filter((edge) => edge.linkage_type === "Success");
    for (const edgeToSecondUpdate of firstSuccessEdges) {
      const secondTask = taskById.get(edgeToSecondUpdate.target_task_id);
      if (!secondTask || secondTask.action_type !== "Update") continue;
      const secondObjectName = typeof secondTask.object === "string" ? secondTask.object.trim() : "";
      if (secondObjectName !== objectName) continue;
      if (normalizedUpdateObjectId(secondTask) !== objectId) continue;

      const secondFields = updateFieldNames(secondTask);
      if (secondFields.length === 0) continue;
      const hasOverlappingField = secondFields.some((fieldName) => firstFields.includes(fieldName));
      if (hasOverlappingField) continue;

      const secondIndex = taskIndexById.get(secondTask.id);
      const prpcHint =
        objectName === "ProductRatePlanCharge"
          ? " For ProductRatePlanCharge (PRPC) updates, this is the preferred PRPC object-task shape."
          : "";
      out.warn(
        "W183",
        `Update task ${firstId} and Update task ${secondTask.id} both target the same ${objectName} record (${objectId}) with separate field sets (${firstFields.join(", ")} vs ${secondFields.join(", ")}). This is usually an avoidable same-record per-field CRUD design: one Update task can send all field values together under parameters.fields.${objectName}, reducing API calls and avoiding partial-update risk.${prpcHint} Keep separate updates only when each update intentionally needs independent failure/retry behavior, an intermediate validation step, or ordered side effects.`,
        Number.isInteger(secondIndex) ? `$.tasks[${secondIndex}]` : `$.tasks[id=${secondTask.id}]`
      );
    }
  }
}

// ---------- Callout URL composition rules ----------

const ZUORA_REST_ENDPOINT_REF = /Credentials\s*\.\s*zuora\s*\.\s*rest_endpoint/;
const ZUORA_URL_REF =
  /Credentials\s*\.\s*zuora\s*\.\s*(?:rest_endpoint|url)|GlobalConstants\s*\.\s*ZUORA_[A-Z0-9_]*(?:BASE|URL|ENDPOINT)|https?:\/\/[^"'\s{}]*\.?zuora\.com(?:[\/"'?\s}]|$)/i;

function liquidExpressionStripsV1Base(expr) {
  return (
    /(?:split|replace|remove|remove_first|gsub)\s*:\s*["']\/?v1\/?["']/.test(expr) ||
    /chomp\s*:\s*["']v1\/?["']/.test(expr)
  );
}

function liquidExpressionUsesFragileV1BaseRemoval(expr) {
  return (
    /(?:replace|remove|remove_first|gsub)\s*:\s*["']\/?v1\/["']/.test(expr) ||
    /chomp\s*:\s*["']v1\/["']/.test(expr)
  );
}

function zuoraRestEndpointUrlCanRenderDoubleV1(url) {
  if (typeof url !== "string" || !ZUORA_REST_ENDPOINT_REF.test(url)) return false;

  const outputTag = /{{([\s\S]*?)}}/g;
  let match;
  while ((match = outputTag.exec(url)) !== null) {
    const expr = match[1] || "";
    if (!ZUORA_REST_ENDPOINT_REF.test(expr)) continue;

    const appendsV1InsideExpression = /\bappend\s*:\s*["']\/?v1(?:\/|["']|$)/.test(expr);
    if (appendsV1InsideExpression && !liquidExpressionStripsV1Base(expr)) return true;
    if (appendsV1InsideExpression && liquidExpressionUsesFragileV1BaseRemoval(expr)) return true;

    const suffix = url.slice(outputTag.lastIndex);
    const appendsV1AfterExpression = /^\s*\/?v1(?:\/|$|[?#])/.test(suffix);
    if (!appendsV1AfterExpression) continue;
    if (!liquidExpressionStripsV1Base(expr)) return true;
    if (liquidExpressionUsesFragileV1BaseRemoval(expr)) return true;
  }

  return false;
}

function looksLikeZuoraApiUrl(url) {
  return typeof url === "string" && ZUORA_URL_REF.test(url);
}

function collectHeaderRows(params, prefix) {
  const rows = [];
  const keys = prefix ? [`${prefix}_headers`, `${prefix}_headers_attributes`] : ["headers", "headers_attributes"];
  for (const key of keys) {
    const value = params[key];
    if (Array.isArray(value)) {
      rows.push(...value);
    } else if (isPlainObject(value)) {
      rows.push(...Object.values(value));
    }
  }
  return rows;
}

function manualZuoraAuthHeaderKeys(params, prefix) {
  const headerRows = collectHeaderRows(params, prefix);
  const badKeys = [];
  for (const header of headerRows) {
    if (!isPlainObject(header) || typeof header.key !== "string") continue;
    const normalized = header.key.replace(/[-_\s]/g, "").toLowerCase();
    if (
      normalized === "apiaccesskeyid" ||
      normalized === "apisecretaccesskey" ||
      normalized === "authorization"
    ) {
      badKeys.push(header.key);
    }
  }
  return badKeys;
}

function calloutAuthType(params, prefix) {
  const authKey = prefix ? `${prefix}_authorization` : "authorization";
  const auth = params[authKey];
  if (!isPlainObject(auth) || typeof auth.type !== "string") return "none";
  return auth.type;
}

function truthyParam(value) {
  return value === true || (typeof value === "string" && value.trim().toLowerCase() === "true");
}

function falseyParam(value) {
  return value === false || (typeof value === "string" && value.trim().toLowerCase() === "false");
}

function calloutValidation(params, prefix) {
  const key = prefix ? `${prefix}_validation` : "validation";
  return isPlainObject(params[key]) ? params[key] : null;
}

function calloutPayloadLocation(params, prefix) {
  const validation = calloutValidation(params, prefix);
  const location = validation && validation.payload_location;
  return typeof location === "string" && location.trim().length > 0 ? location.trim() : "Callout";
}

function calloutIncludesResponseCode(params, prefix) {
  const key = prefix ? `${prefix}_include_response_code` : "include_response_code";
  return !falseyParam(params[key]);
}

function looksLikeLegacyBillRunObjectCrudUrl(url) {
  if (typeof url !== "string") return false;
  const compact = url.replace(/\s+/g, "").toLowerCase();
  return /(?:^|[\/}])(?:v1\/)?object\/bill-run(?:$|[/?#'"}`])/.test(compact);
}

function checkZuoraCalloutAuthorization(doc, out) {
  if (!Array.isArray(doc.tasks)) return;

  doc.tasks.forEach((task, i) => {
    if (!isPlainObject(task) || !["Callout", "AsynchronousCallout"].includes(task.action_type)) return;
    if (!isPlainObject(task.parameters)) return;

    const legs = [{ urlField: "url", authPrefix: "", label: "initial" }];
    if (task.action_type === "AsynchronousCallout") {
      legs.push({ urlField: "polling_url", authPrefix: "polling", label: "polling" });
    }

    for (const leg of legs) {
      const url = task.parameters[leg.urlField];
      if (!looksLikeZuoraApiUrl(url)) continue;

      const authType = calloutAuthType(task.parameters, leg.authPrefix);
      const manualAuthHeaders = manualZuoraAuthHeaderKeys(task.parameters, leg.authPrefix);
      if (authType === "zuora" && manualAuthHeaders.length === 0) continue;

      const authPath = leg.authPrefix ? `${leg.authPrefix}_authorization.type` : "authorization.type";
      const headerText =
        manualAuthHeaders.length > 0
          ? ` Remove manual credential header(s): ${manualAuthHeaders.join(", ")}.`
          : "";
      out.error(
        "E186",
        `${task.action_type} task ${task.id || i} targets a Zuora API in parameters.${leg.urlField} but the ${leg.label} authorization type is ${JSON.stringify(authType)}. Zuora API callouts must use parameters.${authPath} = "zuora" so Workflow injects tenant credentials and entity context.${headerText} Keep ordinary headers such as Content-Type, and add authorization.entity_id only when a multi-entity tenant requires it.`,
        `$.tasks[${i}].parameters.${leg.authPrefix ? leg.authPrefix + "_" : ""}authorization`
      );
    }
  });
}

function checkLegacyBillRunObjectCrudCallouts(doc, out) {
  if (!Array.isArray(doc.tasks)) return;

  doc.tasks.forEach((task, i) => {
    if (!isPlainObject(task) || !["Callout", "AsynchronousCallout"].includes(task.action_type)) return;
    if (!isPlainObject(task.parameters)) return;

    const urlFields = ["url"];
    if (task.action_type === "AsynchronousCallout") urlFields.push("polling_url");

    for (const field of urlFields) {
      const url = task.parameters[field];
      if (!looksLikeLegacyBillRunObjectCrudUrl(url)) continue;
      out.warn(
        "W192",
        `${task.action_type} task ${task.id || i} uses legacy bill-run object CRUD endpoint in parameters.${field}. For Create a bill run, use the modern Zuora REST bill run API resource path, for example {{ Credentials.zuora.rest_endpoint }}bill-runs, with authorization.type = "zuora"; use bill-runs/{id}/post and bill-runs/{id} for post/status follow-up calls instead of /object/bill-run.`,
        `$.tasks[${i}].parameters.${field}`
      );
    }
  });
}

function checkZuoraCalloutValidation(doc, out) {
  if (!Array.isArray(doc.tasks)) return;

  doc.tasks.forEach((task, i) => {
    if (!isPlainObject(task) || !["Callout", "AsynchronousCallout"].includes(task.action_type)) return;
    if (!isPlainObject(task.parameters)) return;

    const legs = [{ urlField: "url", validationPrefix: "", label: "initial" }];
    if (task.action_type === "AsynchronousCallout") {
      legs.push({ urlField: "polling_url", validationPrefix: "polling", label: "polling" });
    }

    for (const leg of legs) {
      const url = task.parameters[leg.urlField];
      if (!looksLikeZuoraApiUrl(url)) continue;

      const validation = calloutValidation(task.parameters, leg.validationPrefix);
      const missing = [];
      if (!validation || !truthyParam(validation.replace)) missing.push("replace: \"true\"");
      if (!validation || !truthyParam(validation.zuora_call)) missing.push("zuora_call: \"true\"");
      if (missing.length === 0) continue;

      const validationPath = leg.validationPrefix ? `${leg.validationPrefix}_validation` : "validation";
      out.warn(
        "W190",
        `${task.action_type} task ${task.id || i} targets a Zuora API in parameters.${leg.urlField} but parameters.${validationPath} is missing ${missing.join(
          " and "
        )}. Zuora API callouts should include validation.replace = "true" so each response overwrites the payload scope, and validation.zuora_call = "true" so Workflow applies Zuora-aware retry/error handling.`,
        `$.tasks[${i}].parameters.${validationPath}`
      );
    }
  });
}

function checkZuoraRestEndpointUrls(doc, out) {
  if (!Array.isArray(doc.tasks)) return;

  doc.tasks.forEach((task, i) => {
    if (!isPlainObject(task) || !isPlainObject(task.parameters)) return;
    const urlFields = [];
    if (typeof task.parameters.url === "string") {
      urlFields.push(["url", task.parameters.url]);
    }
    if (typeof task.parameters.polling_url === "string") {
      urlFields.push(["polling_url", task.parameters.polling_url]);
    }

    for (const [field, url] of urlFields) {
      if (!zuoraRestEndpointUrlCanRenderDoubleV1(url)) continue;
      out.error(
        "E182",
        `${task.action_type || "Task"} task ${task.id || i} builds parameters.${field} from Credentials.zuora.rest_endpoint and a path beginning with /v1. Credentials.zuora.rest_endpoint is already the Zuora REST v1 base URL, so this can render a /v1/v1 endpoint. For v1 APIs, append only the resource path, for example {{ Credentials.zuora.rest_endpoint }}orders. Use an explicit base-url normalization only for non-v1 APIs.`,
        `$.tasks[${i}].parameters.${field}`
      );
    }
  });
}

// ---------- Data-flow helpers ----------
//
// extractDataReferences(value, sourceParameterPath) walks any JSON value
// recursively, scans every string for Liquid `{{ Data.X.Y... }}` and
// `{% if/elsif/case/when/for ... Data.X.Y ... %}` expressions, and returns
// `[{scope, fieldPath, isBracketed, hasArrayIndex, hasArrayOp, raw, sourceParameterPath}]`.
//
// computeAvailableScopes(doc, templates, enums) topologically walks the
// linkage graph and returns:
//   {
//     perTask: Map<taskId, Map<scope, ScopeInfo>>,    // scopes available at the start of each task
//     perTaskOutbound: Map<taskId, Map<scope, ScopeInfo>>,  // scopes after the task's writes
//     iterateContext: Map<taskId, { iterateObject: string, sourceTaskId: number }>,
//     callees: Map<taskId, Task>,
//     errors: Array<{ rule, msg, loc }>,
//   }
// where ScopeInfo = {
//   fields: Set<string>,
//   predictability: 'deterministic' | 'semi-deterministic' | 'opaque' | 'scoping' | 'none',
//   opaque: boolean,
//   opaque_resolved: boolean,
//   fields_partial_known: boolean,
//   array: boolean,                 // top-level shape is Array<Hash>?
//   iterate_array_in_for_each: boolean,  // true inside an Iterate For-Each branch
//   branch_partial: boolean,        // produced only on some Logic::Case branches
//   contributors: Set<number>,      // task ids that contributed
// }

const DATA_REF_REGEX = /\bData\.([A-Za-z_][A-Za-z0-9_]*)((?:\.[A-Za-z_][A-Za-z0-9_]*|\[\d+\]|\[[^\]]*\])*)/g;
// Tail filters that imply array semantics on the LHS scope.
const ARRAY_OP_FILTERS = new Set([
  "size",
  "first",
  "last",
  "join",
  "map",
  "where",
  "compact",
  "uniq",
  "sort",
  "sort_natural",
  "reverse",
  "concat",
  "find",
  "find_index",
  "sum",
  "limit",
  "offset",
  "slice",
]);

function parseRefSuffix(suffix) {
  const segments = [];
  let isBracketed = false;
  let hasArrayIndex = false;
  if (!suffix) return { fieldPath: segments, isBracketed, hasArrayIndex };
  const tokenRegex = /\.([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\]|\[([^\]]+)\]/g;
  let m;
  while ((m = tokenRegex.exec(suffix)) !== null) {
    if (m[1] !== undefined) {
      segments.push(m[1]);
    } else if (m[2] !== undefined) {
      isBracketed = true;
      hasArrayIndex = true;
    } else {
      isBracketed = true;
    }
  }
  return { fieldPath: segments, isBracketed, hasArrayIndex };
}

function extractDataReferences(value, sourceParameterPath = "") {
  const refs = [];
  if (typeof value === "string") {
    DATA_REF_REGEX.lastIndex = 0;
    let m;
    while ((m = DATA_REF_REGEX.exec(value)) !== null) {
      const scope = m[1];
      const suffix = m[2] || "";
      const { fieldPath, isBracketed, hasArrayIndex } = parseRefSuffix(suffix);
      const tail = value.slice(m.index + m[0].length);
      const filterMatch = tail.match(/^\s*\|\s*([a-zA-Z_]+)/);
      const hasArrayOp = !!(filterMatch && ARRAY_OP_FILTERS.has(filterMatch[1]));
      refs.push({
        scope,
        fieldPath,
        isBracketed,
        hasArrayIndex,
        hasArrayOp,
        raw: m[0],
        sourceParameterPath,
      });
    }
  } else if (Array.isArray(value)) {
    value.forEach((v, i) => {
      const child = sourceParameterPath ? `${sourceParameterPath}[${i}]` : `[${i}]`;
      refs.push(...extractDataReferences(v, child));
    });
  } else if (isPlainObject(value)) {
    for (const k of Object.keys(value)) {
      const child = sourceParameterPath ? `${sourceParameterPath}.${k}` : k;
      refs.push(...extractDataReferences(value[k], child));
    }
  }
  return refs;
}

function newScopeInfo(overrides) {
  return Object.assign(
    {
      fields: new Set(),
      predictability: "deterministic",
      opaque: false,
      opaque_resolved: true,
      fields_partial_known: false,
      array: false,
      iterate_array_in_for_each: false,
      branch_partial: false,
      contributors: new Set(),
    },
    overrides || {}
  );
}

function cloneScopeInfo(info) {
  return {
    fields: new Set(info.fields),
    predictability: info.predictability,
    opaque: info.opaque,
    opaque_resolved: info.opaque_resolved,
    fields_partial_known: info.fields_partial_known,
    array: info.array,
    iterate_array_in_for_each: info.iterate_array_in_for_each,
    branch_partial: info.branch_partial,
    contributors: new Set(info.contributors),
  };
}

function cloneScopeMap(map) {
  const copy = new Map();
  for (const [k, v] of map.entries()) copy.set(k, cloneScopeInfo(v));
  return copy;
}

function mergeScopeInto(target, scope, incoming) {
  const existing = target.get(scope);
  if (!existing) {
    target.set(scope, cloneScopeInfo(incoming));
    return;
  }
  for (const f of incoming.fields) existing.fields.add(f);
  for (const c of incoming.contributors) existing.contributors.add(c);
  // Tighten predictability to the more permissive of the two
  if (existing.predictability !== incoming.predictability) {
    const order = { deterministic: 0, "semi-deterministic": 1, opaque: 2, scoping: 3, none: 4 };
    if ((order[incoming.predictability] || 0) > (order[existing.predictability] || 0)) {
      existing.predictability = incoming.predictability;
    }
  }
  existing.opaque = existing.opaque || incoming.opaque;
  existing.opaque_resolved = existing.opaque_resolved && incoming.opaque_resolved;
  existing.fields_partial_known = existing.fields_partial_known || incoming.fields_partial_known;
  existing.array = existing.array || incoming.array;
  // iterate_array_in_for_each is per-edge, set after merge
  // branch_partial is set explicitly when merging post-Case branches
}

function unionScopeMaps(maps) {
  const out = new Map();
  for (const m of maps) {
    if (!m) continue;
    for (const [scope, info] of m.entries()) {
      mergeScopeInto(out, scope, info);
    }
  }
  return out;
}

function computeWorkflowSeedScopes(doc, enums) {
  const scopes = new Map();
  const w = doc.workflow || {};
  const params = isPlainObject(w.parameters) ? w.parameters : {};

  const defaultKeys =
    (enums.default_data_workflow_keys && enums.default_data_workflow_keys.Workflow) ||
    ["ExecutionDate", "ExecutionDateTime", "Name", "Id", "Tenant", "User"];
  scopes.set(
    "Workflow",
    newScopeInfo({ fields: new Set(defaultKeys), predictability: "deterministic" })
  );

  if (["UIACTION", "SYNC_UI_ACTION"].includes(w.call_type)) {
    scopes.set(
      "UIAction",
      newScopeInfo({
        fields: new Set(["ObjectId", "ObjectName", "ObjectNumber"]),
        predictability: "deterministic",
      })
    );
  }

  // parameters.fields[] entries: { object_name, field_name } seed Data.<object_name>.<field_name>
  const fieldsList = Array.isArray(params.fields) ? params.fields : [];
  for (const f of fieldsList) {
    if (!isPlainObject(f)) continue;
    const obj = f.object_name || f.object;
    const fld = f.field_name || f.field || f.key;
    if (!obj || typeof obj !== "string") continue;
    let info = scopes.get(obj);
    if (!info) {
      info = newScopeInfo({ predictability: "deterministic" });
      scopes.set(obj, info);
    }
    if (typeof fld === "string") info.fields.add(fld);
  }

  // event_parameters[*].params[*]
  const eventParams = Array.isArray(params.event_parameters) ? params.event_parameters : [];
  for (const ep of eventParams) {
    if (!isPlainObject(ep) || !Array.isArray(ep.params)) continue;
    for (const p of ep.params) {
      if (!isPlainObject(p)) continue;
      if (typeof p.object !== "string" || typeof p.key !== "string") continue;
      let info = scopes.get(p.object);
      if (!info) {
        info = newScopeInfo({ predictability: "deterministic" });
        scopes.set(p.object, info);
      }
      info.fields.add(p.key);
    }
  }

  // callout_trigger seeds Data.Callout (or whatever placement was configured)
  if (w.callout_trigger === true) {
    const calloutScope = "Callout";
    const wfTrusted = params._opaque_trusted === "true" || params._opaque_trusted === true;
    const declaredSchema = isPlainObject(params._expected_response_schema)
      ? params._expected_response_schema[calloutScope]
      : null;
    const declaredFields = new Set();
    if (isPlainObject(declaredSchema)) {
      for (const k of Object.keys(declaredSchema)) declaredFields.add(k);
    }
    scopes.set(
      calloutScope,
      newScopeInfo({
        fields: declaredFields,
        predictability: "opaque",
        opaque: true,
        opaque_resolved: wfTrusted || isPlainObject(declaredSchema),
      })
    );
  }

  return scopes;
}

function resolveScopeFromTemplate(toTemplate, task) {
  // Returns { scope: string|null, isFiles: bool, isLiquidScope: bool, dynamicSubKey: string|null }
  // Handles three patterns:
  //   1. Literal:                  "Data.BillRun"                        → scope="BillRun"
  //   2. Templated top-level:      "Data.{parameters.placement | self.object}" → scope=resolved
  //   3. Hash-of-Hash with dyn sub-key: "Data.Export.<object>"           → scope="Export", dynamicSubKey=resolved
  //   4. Hash-of-Hash + Files:     "Data.Files.<filename>"               → scope="Files"
  //   5. Hash-of-Hash + Liquid:    "Data.Liquid.<assigned_var>"          → scope="Liquid" (or placement)
  if (typeof toTemplate !== "string") return { scope: null };
  let s = toTemplate.trim();
  if (s.startsWith("Data.")) s = s.slice(5);

  // Resolve a single segment ("self.object" / "parameters.x" / "{...}" / "<...>" / literal).
  function resolveSegment(seg, allowLookup = true) {
    if (!seg) return null;
    const params = isPlainObject(task.parameters) ? task.parameters : {};
    if (/^['"][^'"]*['"]$/.test(seg)) return seg.slice(1, -1);
    if (seg === "self.object" || seg === "object") {
      return isNonEmpty(task.object) ? String(task.object) : null;
    }
    const stripped = seg.replace(/^self\./, "");
    if (stripped.startsWith("parameters.")) {
      const v = getPath(params, stripped.slice("parameters.".length));
      if (isNonEmpty(v) && (typeof v === "string" || typeof v === "number")) return String(v);
      return null;
    }
    if (allowLookup && /^[A-Za-z_][A-Za-z0-9_]*$/.test(seg)) return seg;
    return null;
  }

  function resolveBraceExpr(expr) {
    const choices = expr.split("|").map((p) => p.trim());
    for (const c of choices) {
      const r = resolveSegment(c, false);
      if (r != null) return r;
    }
    return null;
  }

  // Split top scope from the rest, respecting {...} and <...> grouping so dots
  // inside brace expressions don't split prematurely.
  let dotIdx = -1;
  let depth = 0;
  for (let i = 0; i < s.length; i++) {
    const ch = s[i];
    if (ch === "{" || ch === "<") depth++;
    else if (ch === "}" || ch === ">") depth = Math.max(0, depth - 1);
    else if (ch === "." && depth === 0) {
      dotIdx = i;
      break;
    }
  }
  const topRaw = dotIdx === -1 ? s : s.slice(0, dotIdx);
  const restRaw = dotIdx === -1 ? "" : s.slice(dotIdx + 1);

  let topScope = null;
  if (topRaw.startsWith("{") && topRaw.endsWith("}")) {
    topScope = resolveBraceExpr(topRaw.slice(1, -1));
  } else if (topRaw.startsWith("<") && topRaw.endsWith(">")) {
    topScope = resolveSegment(topRaw.slice(1, -1));
  } else {
    topScope = topRaw;
  }
  if (!topScope) return { scope: null };

  // Handle Files / Liquid hash-of-hash specially.
  if (topScope === "Files") return { scope: "Files", isFiles: true };
  if (topScope === "Liquid" && task.action_type === "Logic::Liquid") {
    const placement = task.parameters && task.parameters.placement;
    return {
      scope: typeof placement === "string" && placement.length > 0 ? placement : "Liquid",
      isLiquidScope: true,
    };
  }

  // Dynamic sub-key (Export.<object>, etc.)
  let dynamicSubKey = null;
  if (restRaw) {
    const subM = restRaw.match(/^<([^>]+)>$/);
    if (subM) dynamicSubKey = resolveSegment(subM[1]);
  }

  return { scope: topScope, dynamicSubKey };
}

function resolveContractFieldSet(writeEntry, task) {
  const result = { fields: new Set(), partial: false, isLiquid: false };
  if (typeof writeEntry.fields !== "string") return result;
  const f = writeEntry.fields.trim();
  if (!f || f === "OPAQUE") return result;

  const fieldsParam = isPlainObject(task.parameters) ? task.parameters.fields : null;

  // from_param:fields[<obj>] [+ 'Id'] [+ ...]
  const fromParam = f.match(/^from_param:fields\[<?([^>\]]+)>?\]/);
  if (fromParam) {
    let key = fromParam[1];
    if (key === "object") key = task.object;
    if (key && isPlainObject(fieldsParam)) {
      const declared = fieldsParam[key];
      // Two shapes accepted by Zuora:
      //   array form:   ["Id", "Name"]   or   [{ field_name: "Id" }, ...]
      //   object form:  { Id: "true", Name: "true" }   (UI selection)
      if (Array.isArray(declared)) {
        for (const d of declared) {
          if (typeof d === "string") result.fields.add(d);
          else if (isPlainObject(d) && typeof d.field_name === "string") result.fields.add(d.field_name);
        }
      } else if (isPlainObject(declared)) {
        for (const fname of Object.keys(declared)) {
          if (declared[fname] === "true" || declared[fname] === true) result.fields.add(fname);
          else if (declared[fname] === "false" || declared[fname] === false) {
            // skip explicitly disabled fields
          } else {
            // any other value form: include the key
            result.fields.add(fname);
          }
        }
      }
      // Joined sub-objects (e.g. Account query with BillToContact sub-fields):
      // the SOAP response embeds them as nested hashes on the parent row, so
      // Data.<key>.<otherTopLevelKeyInFields>.<subField> resolves to a valid
      // joined-field reference. Add every other top-level key in the same
      // fields[] map as a "joined object" pseudo-field on this scope.
      for (const otherKey of Object.keys(fieldsParam)) {
        if (otherKey !== key) result.fields.add(otherKey);
      }
    }
    if (/\+\s*['"]Id['"]/.test(f)) result.fields.add("Id");
    return result;
  }

  if (f === "LIQUID_SCOPE") {
    result.isLiquid = true;
    return result;
  }

  // GraphQL / report / link selection sets — partial.
  if (/from_param:query|GraphQL|selection set|report|columns|column names|joined columns|json_output|file blob|standard CO/.test(f)) {
    result.partial = true;
    return result;
  }

  // Plain CSV list of identifiers
  if (/^[A-Za-z_][A-Za-z0-9_,\s]*$/.test(f)) {
    for (const part of f.split(",")) {
      const tok = part.trim();
      if (tok) result.fields.add(tok);
    }
    return result;
  }

  // Mixed text — try to extract identifiers but mark partial
  result.partial = true;
  for (const tok of f.match(/\b[A-Za-z_][A-Za-z0-9_]*\b/g) || []) {
    // Filter out common noise words
    if (
      ![
        "and",
        "or",
        "the",
        "a",
        "from",
        "param",
        "params",
        "fields",
        "object",
        "Id",
        "Hash",
        "object",
        "Array",
        "File",
        "string",
        "OPAQUE",
        "true",
        "false",
        "json_output",
        "shape",
        "notes",
        "blob",
        "blobs",
        "file",
      ].includes(tok)
    ) {
      result.fields.add(tok);
    }
  }
  return result;
}

function scanLiquidAssigns(code) {
  const set = new Set();
  if (typeof code !== "string") return set;
  let m;
  const assignRe = /\{%-?\s*assign\s+([A-Za-z_][A-Za-z0-9_]*)\s*=/g;
  while ((m = assignRe.exec(code)) !== null) set.add(m[1]);
  const captureRe = /\{%-?\s*capture\s+([A-Za-z_][A-Za-z0-9_]*)\s*-?%\}/g;
  while ((m = captureRe.exec(code)) !== null) set.add(m[1]);
  return set;
}

function getDataContract(task, templates) {
  const tpl = templates[task.action_type];
  if (tpl && isPlainObject(tpl.data_contract)) return tpl.data_contract;
  if (isPlainObject(templates.$default_data_contract)) return templates.$default_data_contract;
  return { predictability: "opaque", writes: [], opaque: true };
}

// Strip the `__<TaskId>.<ext>` suffix from a possibly-file-name form to get the
// base object name (e.g. "Account__601.csv.zip" -> "Account"). Mirrors
// workflow/rails/app/models/tasks/iterate.rb#retrieve_object L696-698.
function stripFileHolderSuffix(name) {
  if (typeof name !== "string") return name;
  const m = name.match(/^(\w+)__\d+\.(?:csv\.zip|csv|tsv\.zip|tsv|dsv\.zip|dsv|json\.zip|txt|dat|zip|xml)$/i);
  if (m) return m[1];
  return name;
}

// Returns the set of file holder names that a file-producing task is expected to
// register under Data.Files. For Export, follows the convention enforced by
// workflow/rails/app/models/tasks/export.rb#file_holder_name:
//   "<Object>__<TaskId>.csv" (or ".csv.zip" when parameters.zip is "true")
// Rails runtime never registers the bare "<Object>" string under Data.Files --
// Iterate#task_process (L68) checks `self.data['Files'].keys.include?(self.object)`
// against the literal file-holder name only, so the linter mirrors that to catch
// bare-object Iterate mistakes at design time.
function synthesizeFileHolderNames(task) {
  const out = new Set();
  if (!isPlainObject(task)) return out;
  const id = task.id;
  if (!Number.isInteger(id)) return out;
  const action = task.action_type;
  const params = isPlainObject(task.parameters) ? task.parameters : {};
  const obj = typeof task.object === "string" ? task.object : null;
  if (!obj) return out;
  if (action === "Export") {
    const zipped = params.zip === "true" || params.zip === true;
    const ext = zipped ? "csv.zip" : "csv";
    out.add(`${obj}__${id}.${ext}`);
  } else if (action === "Data::Link" || action === "Data::BillingPreviewRun") {
    // Data::Link writes either CSV or a JSON file depending on parameters.
    // Both forms are possible; the linter accepts either when present as a
    // downstream Iterate.object.
    out.add(`${obj}__${id}.csv.zip`);
    out.add(`${obj}__${id}.csv`);
  } else if (typeof action === "string" && action.startsWith("File::")) {
    out.add(`${obj}__${id}.csv.zip`);
    out.add(`${obj}__${id}.csv`);
  }
  return out;
}

function applyTaskWrites(task, contract, templates, parentScopes) {
  // Returns Map<scope, ScopeInfo> — only the scopes this task contributes (or rebinds).
  const contrib = new Map();
  const params = isPlainObject(task.parameters) ? task.parameters : {};
  const predictability = contract.predictability || "opaque";

  // Opaque-resolution lookup from the task's parameters.
  const opaqueTrusted = params._opaque_trusted === "true" || params._opaque_trusted === true;
  const expectedSchema = isPlainObject(params._expected_response_schema)
    ? params._expected_response_schema
    : null;

  if (predictability === "scoping" || predictability === "none") {
    return contrib;
  }

  const writes = Array.isArray(contract.writes) ? contract.writes : [];
  for (const w of writes) {
    const { scope, isFiles, isLiquidScope, dynamicSubKey } = resolveScopeFromTemplate(
      w.to_template,
      task
    );
    if (!scope) continue;

    if (isFiles) {
      // Data.Files keys are file holder names; register the Files scope and best-effort
      // populate the file holder field name so downstream Iterate(file-name form) checks
      // (E176) and the For-Each rebinding (computeOutboundFor) can resolve it.
      const info =
        parentScopes.get("Files") ||
        newScopeInfo({ predictability: "semi-deterministic", fields_partial_known: true });
      const cloned = cloneScopeInfo(info);
      cloned.predictability = "semi-deterministic";
      cloned.fields_partial_known = true;
      cloned.contributors.add(task.id);
      // Synthesize the file holder name for tasks that publish a known-shape file.
      // The Iterate dropdown (workflow/rails/app/models/tasks/iterate.rb#objects) shows
      // entries like "<Object>__<TaskId>.csv.zip" for Export(zip:true), or
      // "<Object>__<TaskId>.csv" for Export(zip:false). We register both the
      // "<Object>__<TaskId>.<ext>" form and the bare "<Object>" so that downstream
      // checks tolerant of both forms succeed.
      const holderNames = synthesizeFileHolderNames(task);
      for (const n of holderNames) cloned.fields.add(n);
      contrib.set("Files", cloned);
      continue;
    }

    let fieldSet;
    let partial = false;
    let isLiquid = false;
    if (isLiquidScope || task.action_type === "Logic::Liquid") {
      const liquidVars = scanLiquidAssigns(params.code || "");
      fieldSet = liquidVars;
      partial = true; // {% assign %} set may be incomplete relative to dynamic templates
      isLiquid = true;
    } else {
      const r = resolveContractFieldSet(w, task);
      fieldSet = r.fields;
      partial = r.partial;
      isLiquid = r.isLiquid;
    }

    const isOpaque = predictability === "opaque";
    let resolved = !isOpaque;
    if (isOpaque) {
      if (opaqueTrusted) resolved = true;
      if (expectedSchema && isPlainObject(expectedSchema[scope])) {
        resolved = true;
        for (const k of Object.keys(expectedSchema[scope])) fieldSet.add(k);
      }
    }

    // For Hash-of-Hash writes (e.g. Data.Export.<object>), the dynamic sub-key
    // becomes the visible field on the top-level scope, and the sub-key's own
    // fields are the resolved fields from this contract.
    let effectiveFields = fieldSet;
    if (dynamicSubKey) {
      effectiveFields = new Set([dynamicSubKey]);
    }

    const info = newScopeInfo({
      fields: effectiveFields,
      predictability,
      opaque: isOpaque,
      opaque_resolved: resolved,
      fields_partial_known:
        partial ||
        predictability === "semi-deterministic" ||
        isLiquid ||
        (isOpaque && !resolved),
      array: w.shape && /Array/i.test(w.shape),
      contributors: new Set([task.id]),
    });
    mergeScopeInto(contrib, scope, info);
  }

  return contrib;
}

function buildAdjacencyMaps(doc) {
  const incoming = new Map();
  const outgoing = new Map();
  (doc.linkages || []).forEach((l, i) => {
    if (!isPlainObject(l)) return;
    const target = l.target_task_id;
    const linkageType = l.linkage_type;
    const source = l.source_workflow_id != null ? "workflow" : l.source_task_id;
    if (target == null) return;
    if (source == null) return;
    if (!incoming.has(target)) incoming.set(target, []);
    incoming.get(target).push({ source, linkageType, index: i });
    if (!outgoing.has(source)) outgoing.set(source, []);
    outgoing.get(source).push({ target, linkageType, index: i });
  });
  return { incoming, outgoing };
}

function topoOrder(doc, adj) {
  const taskIds = (doc.tasks || [])
    .filter((t) => isPlainObject(t) && Number.isInteger(t.id))
    .map((t) => t.id);
  const taskSet = new Set(taskIds);
  const inDegree = new Map();
  for (const id of taskIds) {
    const inbound = (adj.incoming.get(id) || []).filter(
      (e) => e.source !== "workflow" && taskSet.has(e.source)
    );
    inDegree.set(id, inbound.length);
  }
  const queue = [];
  for (const id of taskIds) if ((inDegree.get(id) || 0) === 0) queue.push(id);
  const ordered = [];
  while (queue.length > 0) {
    const id = queue.shift();
    ordered.push(id);
    for (const e of adj.outgoing.get(id) || []) {
      if (e.target == null || !taskSet.has(e.target)) continue;
      const d = (inDegree.get(e.target) || 0) - 1;
      inDegree.set(e.target, d);
      if (d === 0) queue.push(e.target);
    }
  }
  for (const id of taskIds) if (!ordered.includes(id)) ordered.push(id);
  return ordered;
}

function computeAvailableScopes(doc, templates, enums) {
  const adj = buildAdjacencyMaps(doc);
  const ordered = topoOrder(doc, adj);
  const taskById = new Map();
  (doc.tasks || []).forEach((t) => {
    if (isPlainObject(t) && Number.isInteger(t.id)) taskById.set(t.id, t);
  });

  const seed = computeWorkflowSeedScopes(doc, enums);

  // perTaskInbound[taskId] = Map<scope, ScopeInfo>  (snapshot at task entry)
  // perTaskContrib[taskId] = Map<scope, ScopeInfo>  (this task's local writes)
  // perEdgeOutbound[`${sourceTaskId}->${targetTaskId}#${linkageType}`] = scopes propagated on that edge
  const perTaskInbound = new Map();
  const perTaskContrib = new Map();
  const iterateContext = new Map(); // taskId -> { iterateObject, sourceIterateTaskId } if reached via For Each branch

  for (const id of ordered) {
    const task = taskById.get(id);
    if (!task) continue;

    // Inbound: union of (predecessor's outbound on the linkage that targets this task), plus seed.
    const inboundContribs = [];
    let isStart = false;
    let inForEachOf = null; // {iterateObject, sourceTaskId}
    let postMergeBranchSets = null;

    for (const inEdge of adj.incoming.get(id) || []) {
      if (inEdge.source === "workflow") {
        isStart = true;
        continue;
      }
      const upstream = taskById.get(inEdge.source);
      if (!upstream) continue;
      const upstreamOutbound = computeOutboundFor(
        upstream,
        perTaskInbound.get(inEdge.source) || new Map(),
        perTaskContrib.get(inEdge.source) || new Map(),
        inEdge.linkageType
      );
      inboundContribs.push(upstreamOutbound);

      // Propagate iterate context: if upstream is Iterate AND we're reached via "For Each", we're in a loop body.
      if (upstream.action_type === "Iterate" && inEdge.linkageType === "For Each") {
        const obj = upstream.object;
        if (typeof obj === "string" && obj.length > 0) {
          inForEachOf = { iterateObject: obj, sourceTaskId: upstream.id };
        }
      } else {
        // Inherit iterate context from the upstream (still inside an outer loop, unless that linkage was Complete).
        const upstreamCtx = iterateContext.get(upstream.id);
        if (upstreamCtx && inEdge.linkageType !== "Complete") {
          inForEachOf = inForEachOf || upstreamCtx;
        }
      }
    }

    // Logic::Merge branch-intersection: detect if all inbound edges trace back to the same Logic::Case.
    if (task.action_type === "Logic::Merge" && inboundContribs.length > 1) {
      postMergeBranchSets = inboundContribs.map((m) => new Set(m.keys()));
    }

    let inbound;
    if (isStart) {
      inbound = cloneScopeMap(seed);
      for (const c of inboundContribs) for (const [k, v] of c.entries()) mergeScopeInto(inbound, k, v);
    } else if (inboundContribs.length === 0) {
      inbound = cloneScopeMap(seed);
    } else {
      inbound = unionScopeMaps(inboundContribs);
      // Carry over the original seed too (Workflow / UIAction / event_parameters etc.)
      for (const [k, v] of seed.entries()) {
        if (!inbound.has(k)) inbound.set(k, cloneScopeInfo(v));
      }
    }

    // Mark branch_partial for scopes only present on some branches at a Logic::Merge.
    if (postMergeBranchSets) {
      const intersection = new Set(postMergeBranchSets[0]);
      for (let i = 1; i < postMergeBranchSets.length; i++) {
        for (const k of intersection) {
          if (!postMergeBranchSets[i].has(k)) intersection.delete(k);
        }
      }
      for (const [scope, info] of inbound.entries()) {
        if (seed.has(scope)) continue; // workflow seed isn't branch-partial
        if (!intersection.has(scope)) info.branch_partial = true;
      }
    }

    // If we're in an Iterate For-Each body, mark the iterated scope as single-Hash (rebound).
    if (inForEachOf) {
      iterateContext.set(id, inForEachOf);
      const reboundScope = inForEachOf.iterateObject;
      const info = inbound.get(reboundScope);
      if (info) info.iterate_array_in_for_each = true;
    }

    perTaskInbound.set(id, inbound);

    // Compute this task's local writes (contributions to outbound).
    const contract = getDataContract(task, templates);
    const contrib = applyTaskWrites(task, contract, templates, inbound);
    perTaskContrib.set(id, contrib);
  }

  // Helper: compute outbound for an upstream on a particular linkageType.
  function computeOutboundFor(upstream, upstreamInbound, upstreamContrib, linkageType) {
    // Start from upstream inbound, layer on upstream contrib. For "Complete" linkages
    // out of an Iterate, restore the iterated scope to its array binding.
    const out = cloneScopeMap(upstreamInbound);
    for (const [k, v] of upstreamContrib.entries()) mergeScopeInto(out, k, v);

    if (upstream.action_type === "Iterate") {
      const rawObj = upstream.object;
      if (typeof rawObj === "string" && rawObj.length > 0 && rawObj !== "CUSTOM LIQUID") {
        // The loop scope name inside the For-Each body is the BASE object name --
        // workflow/rails/app/models/tasks/iterate.rb#retrieve_object strips the
        // "__<TaskId>.<ext>" suffix when self.object is a file holder name. So
        // Iterate(object="Account__601.csv.zip") binds Data.Account, NOT
        // Data.Account__601.csv.zip, inside the loop body.
        const obj = stripFileHolderSuffix(rawObj);
        if (linkageType === "For Each") {
          // Iterate(object='X') rebinds Data.X to a single Hash inside the For-Each body.
          // Three cases:
          //   (a) Data.X already exists (upstream Query produced an Array<Hash>):
          //       reuse its fields, mark as iterate_array_in_for_each.
          //   (b) Data.X is missing but the iterated source is Data.Files.X (file-streaming
          //       pattern after Export): seed Data.X with fields from the upstream Export's
          //       parameters.fields[X].
          //   (c) Otherwise: seed Data.X with predictability=semi-deterministic and no
          //       fields (let downstream rules treat references as best-effort).
          let info = out.get(obj);
          if (info) {
            info.iterate_array_in_for_each = true;
          } else {
            const exportFields = lookupExportFieldsForFileHolder(upstream, rawObj);
            info = newScopeInfo({
              fields: exportFields || new Set(),
              predictability: exportFields ? "deterministic" : "semi-deterministic",
              fields_partial_known: !exportFields,
              iterate_array_in_for_each: true,
              contributors: new Set([upstream.id]),
            });
            out.set(obj, info);
          }
        } else if (linkageType === "Complete") {
          const info = out.get(obj);
          if (info) info.iterate_array_in_for_each = false;
        }
      }
    }
    return out;
  }

  // For an Iterate task, search upstream tasks for an Export (or other file-holder writer)
  // whose `object` matches the Iterate's object, and return its declared fields.
  // Accepts both forms of fileHolderName:
  //   - the bare object name ("Account") -- match upstream Export with the same object
  //   - the file-name form ("Account__601.csv.zip") -- strip the suffix to get the base
  //     object name and (optionally) the source task id, then match.
  function lookupExportFieldsForFileHolder(iterateTask, fileHolderName) {
    if (typeof fileHolderName !== "string" || fileHolderName.length === 0) return null;
    const baseObj = stripFileHolderSuffix(fileHolderName);
    const sourceTaskIdM = fileHolderName.match(/__(\d+)\.(?:csv|csv\.zip|tsv|tsv\.zip|dsv|dsv\.zip|json\.zip|txt|dat|zip|xml)$/i);
    const sourceTaskId = sourceTaskIdM ? Number(sourceTaskIdM[1]) : null;
    // BFS upstream until we find a matching Export
    const seen = new Set();
    const queue = [iterateTask.id];
    while (queue.length > 0) {
      const id = queue.shift();
      if (seen.has(id)) continue;
      seen.add(id);
      for (const inEdge of adj.incoming.get(id) || []) {
        if (inEdge.source === "workflow") continue;
        const upstream = taskById.get(inEdge.source);
        if (!upstream) continue;
        const matchesByObject =
          upstream.action_type === "Export" && upstream.object === baseObj;
        const matchesByTaskId =
          sourceTaskId != null &&
          upstream.action_type === "Export" &&
          upstream.id === sourceTaskId;
        if (matchesByObject || matchesByTaskId) {
          const params = isPlainObject(upstream.parameters) ? upstream.parameters : {};
          const fieldsParam = isPlainObject(params.fields) ? params.fields : {};
          // Export's parameters.fields is keyed by the bare object name.
          const declared = fieldsParam[upstream.object];
          if (isPlainObject(declared)) {
            const set = new Set(Object.keys(declared));
            return set;
          }
          if (Array.isArray(declared)) {
            const set = new Set();
            for (const d of declared) {
              if (typeof d === "string") set.add(d);
              else if (isPlainObject(d) && typeof d.field_name === "string") set.add(d.field_name);
            }
            return set;
          }
        }
        queue.push(upstream.id);
      }
    }
    return null;
  }

  return { perTaskInbound, perTaskContrib, iterateContext, taskById, seed };
}

// ---------- Data-flow rules (E170 / W171 / W172 / W173 / W174) ----------

// Where in a task's parameters do we scan for Liquid `Data.X.Y` references?
// We deliberately skip the linter sentinels (`_opaque_trusted`,
// `_expected_response_schema`) so they don't generate false positives.
function extractTaskDataReferences(task) {
  const params = isPlainObject(task.parameters) ? task.parameters : {};
  const refs = [];
  for (const [k, v] of Object.entries(params)) {
    if (k === "_opaque_trusted" || k === "_expected_response_schema") continue;
    refs.push(...extractDataReferences(v, `parameters.${k}`));
  }
  // Also scan top-level liquid-bearing fields if present (some tasks use task.object as a liquid expr).
  for (const k of ["object_id", "object", "name", "description"]) {
    if (typeof task[k] === "string") {
      refs.push(...extractDataReferences(task[k], k));
    }
  }
  return refs;
}

function suggestClosestScope(missing, available) {
  let best = null;
  let bestDist = Infinity;
  for (const candidate of available) {
    if (candidate === missing) continue;
    const d = levenshtein(missing, candidate);
    if (d < bestDist) {
      bestDist = d;
      best = candidate;
    }
  }
  if (best && bestDist <= Math.max(2, Math.floor(missing.length / 3))) return best;
  return null;
}

function levenshtein(a, b) {
  if (a === b) return 0;
  if (!a) return b.length;
  if (!b) return a.length;
  const m = a.length;
  const n = b.length;
  const prev = new Array(n + 1);
  const curr = new Array(n + 1);
  for (let j = 0; j <= n; j++) prev[j] = j;
  for (let i = 1; i <= m; i++) {
    curr[0] = i;
    for (let j = 1; j <= n; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      curr[j] = Math.min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost);
    }
    for (let j = 0; j <= n; j++) prev[j] = curr[j];
  }
  return prev[n];
}

function exportBackedMissingScopeHint(scope, fieldPath, inbound, taskById) {
  const exportInfo = inbound.get("Export");
  if (!exportInfo || !exportInfo.fields || !exportInfo.fields.has(scope)) return "";

  const exportTasks = Array.from(exportInfo.contributors || [])
    .map((id) => taskById.get(id))
    .filter((task) => task && task.action_type === "Export" && task.object === scope);
  const holders = exportTasks.flatMap((task) => Array.from(synthesizeFileHolderNames(task)));
  const holderHint = holders.length > 0 ? ` (for example "${holders[0]}")` : "";
  const field = fieldPath && fieldPath.length > 0 ? `.${fieldPath.join(".")}` : ".<field>";

  return ` An upstream Export of ${scope} is visible here, but Export writes file/reference metadata (Data.Export.${scope} and Data.Files.<file-holder>), not Data.${scope}.* row variables directly. Use a Query task when downstream tasks need Data.${scope}${field}, or add an Iterate task over the Export file holder${holderHint} and reference Data.${scope}.* inside the For Each branch.`;
}

const CALLOUT_RESPONSE_WRAPPER_FIELDS = new Set(["ResponseBody", "ResponseCode", "URL"]);

function calloutTaskWrapsResponseScope(task, scope) {
  if (!isPlainObject(task) || !["Callout", "AsynchronousCallout"].includes(task.action_type)) return false;
  const params = isPlainObject(task.parameters) ? task.parameters : {};
  if (calloutPayloadLocation(params, "") === scope && calloutIncludesResponseCode(params, "")) return true;
  return (
    task.action_type === "AsynchronousCallout" &&
    calloutPayloadLocation(params, "polling") === scope &&
    calloutIncludesResponseCode(params, "polling")
  );
}

function wrappedCalloutProducerIds(scopeInfo, scope, taskById) {
  return Array.from(scopeInfo.contributors || []).filter((producerId) => {
    const producer = taskById.get(producerId);
    return calloutTaskWrapsResponseScope(producer, scope);
  });
}

function checkDataFlow(doc, out, templates, enums) {
  if (!Array.isArray(doc.tasks) || doc.tasks.length === 0) return;
  if (!Array.isArray(doc.linkages) || doc.linkages.length === 0) return;

  let walker;
  try {
    walker = computeAvailableScopes(doc, templates, enums);
  } catch (e) {
    out.warn(
      "W170-internal",
      `Data-flow walker bailed out: ${e.message}. Validate workflow structure first; data-flow checks are skipped.`,
      `$.tasks`
    );
    return;
  }

  const { perTaskInbound, perTaskContrib, taskById } = walker;

  for (const [taskId, task] of taskById.entries()) {
    const inbound = perTaskInbound.get(taskId) || new Map();
    const refs = extractTaskDataReferences(task);
    if (refs.length === 0) continue;

    const taskLoc = `$.tasks[id=${taskId}]`;
    const taskLabel = `tasks[id=${taskId}] (${task.action_type} - "${task.name || ""}")`;

    for (const ref of refs) {
      const refLoc = `${taskLoc}.${ref.sourceParameterPath}`;

      // E170: scope missing
      if (!inbound.has(ref.scope)) {
        const suggestion = suggestClosestScope(ref.scope, Array.from(inbound.keys()));
        const hint = suggestion ? ` Did you mean "Data.${suggestion}"?` : "";
        const exportHint = exportBackedMissingScopeHint(ref.scope, ref.fieldPath, inbound, taskById);
        out.error(
          "E170",
          `${taskLabel} references "Data.${ref.scope}" (in ${ref.raw}) but no upstream task or trigger seed produces that scope. Available scopes here: ${JSON.stringify(
            Array.from(inbound.keys()).sort()
          )}.${hint}${exportHint}`,
          refLoc
        );
        continue;
      }

      const scopeInfo = inbound.get(ref.scope);

      // W173: array-shape reference inside an Iterate For-Each body
      if (
        scopeInfo.iterate_array_in_for_each &&
        (ref.hasArrayIndex || ref.hasArrayOp)
      ) {
        out.warn(
          "W173",
          `${taskLabel} references "Data.${ref.scope}" with array-shape syntax (${ref.raw}) inside an Iterate For-Each body. Inside the loop, Data.${ref.scope} is a single Hash (one row), not an Array -- drop the bracket index / array filter and reference Data.${ref.scope}.<field> directly. Note that Iterate.object can be either an upstream object scope name (e.g. "Account") OR a file-name like "<Object>__<TaskId>.csv.zip" produced by an upstream Export -- the loop-body Hash shape is the same in both cases.`,
          refLoc
        );
        continue;
      }

      // W174: scope produced only on some Logic::Case branches
      if (scopeInfo.branch_partial) {
        out.warn(
          "W174",
          `${taskLabel} references "Data.${ref.scope}" (in ${ref.raw}) but the scope is only produced on some Logic::Case branches upstream of the Logic::Merge. The reference will resolve to nothing on the branches that don't write Data.${ref.scope}.`,
          refLoc
        );
        continue;
      }

      // W191: Callout response-code wrapping means the parsed response body lives
      // under ResponseBody unless include_response_code is explicitly false.
      if (
        ref.fieldPath.length > 0 &&
        !CALLOUT_RESPONSE_WRAPPER_FIELDS.has(ref.fieldPath[0])
      ) {
        const wrappedProducers = wrappedCalloutProducerIds(scopeInfo, ref.scope, taskById);
        if (wrappedProducers.length > 0) {
          out.warn(
            "W191",
            `${taskLabel} references "Data.${ref.scope}.${ref.fieldPath.join(
              "."
            )}" (in ${ref.raw}), but upstream Callout task(s) ${wrappedProducers.join(
              ", "
            )} write response-code-wrapped data by default. Use Data.${ref.scope}.ResponseBody.${ref.fieldPath.join(
              "."
            )}, or set include_response_code = "false" on the producing callout if downstream tasks should read the response body directly.`,
            refLoc
          );
        }
      }

      // W172: opaque scope without resolution annotation
      if (scopeInfo.opaque && !scopeInfo.opaque_resolved && ref.fieldPath.length > 0) {
        out.warn(
          "W172",
          `${taskLabel} references "Data.${ref.scope}.${ref.fieldPath.join(".")}" (in ${ref.raw}) but the producing task is OPAQUE (response shape unknowable until runtime). Add parameters._expected_response_schema={"${ref.scope}":{...}} or parameters._opaque_trusted="true" on the producing task to resolve. See Step 3e in zuora-workflow-build/SKILL.md.`,
          refLoc
        );
        continue;
      }

      // W171: deterministic scope but field unknown
      if (
        ref.fieldPath.length > 0 &&
        scopeInfo.predictability === "deterministic" &&
        scopeInfo.fields.size > 0 &&
        !scopeInfo.fields_partial_known
      ) {
        const head = ref.fieldPath[0];
        if (head !== "Id" && !scopeInfo.fields.has(head)) {
          out.warn(
            "W171",
            `${taskLabel} references "Data.${ref.scope}.${head}" (in ${ref.raw}) but the upstream task that writes Data.${ref.scope} did not declare "${head}" in its known field set. Known fields: ${JSON.stringify(
              Array.from(scopeInfo.fields).sort()
            )}. If "${head}" is a custom field or an undeclared schema field, add it to the upstream parameters.fields[] (or to _expected_response_schema) so the linter sees it.`,
            refLoc
          );
          continue;
        }
      }

      // Notice-level for semi-deterministic / liquid scope: silent (no warning).
    }
  }
}

// ---------- E176 / W177 / W178 (Iterate.object + describe-field + UI-leak rules) ----------

// File-name pattern produced by Export / File::* tasks ("<Object>__<TaskId>.<ext>"
// or "<Filename>__<TaskId>.<ext>"). Matches the Iterate model's file-streaming branch
// (workflow/rails/app/models/tasks/iterate.rb) which routes any object ending in one
// of these extensions through the file-iterating handler.
const ITERATE_FILE_PATTERN = /__\d+\.(csv|csv\.zip|tsv|tsv\.zip|dsv|dsv\.zip|json\.zip|txt|dat|zip|xml)$/i;

function stripLiquidAndQuotedStrings(value) {
  return String(value || "")
    .replace(/{{[\s\S]*?}}/g, " ")
    .replace(/{%[\s\S]*?%}/g, " ")
    .replace(/'(?:''|\\'|[^'])*'/g, " ")
    .replace(/"(?:\\"|[^"])*"/g, " ");
}

function normalizeWhereFieldName(candidate, objectName) {
  if (typeof candidate !== "string") return "";
  const trimmed = candidate.trim();
  if (!trimmed) return "";
  if (!trimmed.includes(".")) return trimmed;

  const parts = trimmed.split(".");
  if (parts.length === 2 && parts[0] === objectName) return parts[1];
  return trimmed;
}

function extractWhereClauseFieldNames(whereClause, objectName) {
  if (typeof whereClause !== "string" || whereClause.trim().length === 0) return [];
  const cleaned = stripLiquidAndQuotedStrings(whereClause);
  const fieldNames = new Set();
  const predicatePattern =
    /\b([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*(?:=|!=|<>|<=|>=|<|>|\b(?:NOT\s+)?(?:IN|LIKE)\b|\bIS(?:\s+NOT)?\b|\bBETWEEN\b)/gi;

  let match;
  while ((match = predicatePattern.exec(cleaned)) !== null) {
    const fieldName = normalizeWhereFieldName(match[1], objectName);
    if (fieldName) fieldNames.add(fieldName);
  }
  return Array.from(fieldNames);
}

function checkIterateAndDescribe(doc, out, templates, enums, standardFields) {
  if (!Array.isArray(doc.tasks) || doc.tasks.length === 0) return;
  if (!Array.isArray(doc.linkages)) return;

  // Build a quick task index + a topological-ish walker context so we know which
  // upstream scopes are visible at each Iterate / field-bearing task.
  let walker;
  try {
    walker = computeAvailableScopes(doc, templates, enums);
  } catch (_) {
    return;
  }
  const { perTaskInbound, taskById } = walker;

  for (const [taskId, task] of taskById.entries()) {
    if (!isPlainObject(task)) continue;
    const taskLoc = `$.tasks[id=${taskId}]`;
    const taskLabel = `tasks[id=${taskId}] (${task.action_type} - "${task.name || ""}")`;

    // ---- E176: Iterate.object resolution ----
    if (task.action_type === "Iterate") {
      const obj = typeof task.object === "string" ? task.object.trim() : "";
      const inbound = perTaskInbound.get(taskId) || new Map();

      if (obj === "" || obj === null || obj === undefined) {
        // Empty / null / missing: separate rule (E102/W173 etc may already cover).
      } else if (obj === "CUSTOM LIQUID") {
        const liquidStmt =
          isPlainObject(task.parameters) && typeof task.parameters.liquid_statement === "string"
            ? task.parameters.liquid_statement.trim()
            : "";
        if (liquidStmt.length === 0) {
          out.error(
            "E176",
            `${taskLabel} has Iterate.object="CUSTOM LIQUID" but parameters.liquid_statement is missing or empty. Iterate(custom-liquid) requires a non-empty Liquid expression that evaluates to an Array under parameters.liquid_statement.`,
            `${taskLoc}.parameters.liquid_statement`
          );
        }
      } else if (ITERATE_FILE_PATTERN.test(obj)) {
        // File-name form: must be produced by an upstream Export / File task whose
        // `Data.Files.<obj>` (or matching new_fields['Files']) appears in inbound.
        const filesScope = inbound.get("Files");
        const objNoExt = obj.replace(/\.(csv|tsv|dsv|json|txt|dat|xml)(\.zip)?$/i, "");
        const knownFile =
          filesScope &&
          filesScope.fields &&
          (filesScope.fields.has(obj) ||
            filesScope.fields.has(objNoExt) ||
            // Many Export tasks declare the bare file holder name without the
            // <task-id> suffix; accept any prefix match on the object base.
            Array.from(filesScope.fields).some((f) => obj.startsWith(f.replace(/\.(csv|tsv|dsv|json|txt|dat|xml)(\.zip)?$/i, ""))));
        if (!filesScope || !knownFile) {
          out.error(
            "E176",
            `${taskLabel} has Iterate.object="${obj}" (file-name form) but no upstream task produces that file under Data.Files. Add an Export / File::FileOperations task upstream that emits this file holder, or change Iterate.object to a scope name (e.g. "Account") that an upstream Query / CustomObject::Query / GraphQuery writes as Array<Hash>.`,
            `${taskLoc}.object`
          );
        }
      } else {
        // Object-name form. Only ONE valid sub-case, enforced by the Rails runtime:
        //  (i) The scope is in inbound — i.e. an upstream Query / GraphQuery /
        //      CustomObject::Query / Callout(with _expected_response_schema) wrote
        //      Data.<obj> as Array<Hash>. At runtime Iterate#task_process (L66)
        //      routes this through the `:query` mode: `self.data["<obj>"].class == Array`.
        //
        // The bare-object form after a file-producing parent (Export / File::* /
        // Data::Link) is INVALID at runtime: Iterate#task_process (L68) only matches
        // `self.data['Files'].keys.include?(self.object)` against the literal
        // file-holder name ("<Object>__<TaskId>.<ext>"), not the bare object. The
        // Iterate UI dropdown (app/views/tasks/partials/_iterate.html.erb L7-14)
        // likewise only exposes Query/Array scopes, file-holder names, or CUSTOM
        // LIQUID — never the bare object after an Export. If the agent used the
        // bare form here, the workflow will raise
        // "The selected file or object '<obj>' could not be found. Please ensure
        //  correct iterate setup." on execution.
        if (!inbound.has(obj)) {
          // Search upstream for a file-producing task whose `object` matches so we
          // can give the agent the exact file-holder name to switch to.
          let upstreamFileProducer = null;
          const seen = new Set();
          const queue = [taskId];
          const incomingByTarget = new Map();
          for (const lk of doc.linkages) {
            if (!isPlainObject(lk)) continue;
            if (!Number.isInteger(lk.target_task_id)) continue;
            if (!incomingByTarget.has(lk.target_task_id)) incomingByTarget.set(lk.target_task_id, []);
            incomingByTarget.get(lk.target_task_id).push(lk);
          }
          while (queue.length > 0) {
            const cur = queue.shift();
            if (seen.has(cur)) continue;
            seen.add(cur);
            for (const inEdge of incomingByTarget.get(cur) || []) {
              if (!Number.isInteger(inEdge.source_task_id)) continue;
              const upstream = taskById.get(inEdge.source_task_id);
              if (!upstream) continue;
              if (
                (upstream.action_type === "Export" ||
                  upstream.action_type === "Data::Link" ||
                  upstream.action_type === "Data::BillingPreviewRun" ||
                  (typeof upstream.action_type === "string" && upstream.action_type.startsWith("File::"))) &&
                typeof upstream.object === "string" &&
                upstream.object === obj
              ) {
                upstreamFileProducer = upstream;
                break;
              }
              queue.push(upstream.id);
            }
            if (upstreamFileProducer) break;
          }
          if (upstreamFileProducer) {
            // Compute the exact file-holder name the agent should switch to.
            const holderNames = Array.from(synthesizeFileHolderNames(upstreamFileProducer))
              .filter((n) => ITERATE_FILE_PATTERN.test(n));
            const suggestion = holderNames.length > 0 ? holderNames[0] : `${obj}__${upstreamFileProducer.id}.csv.zip`;
            out.error(
              "E176",
              `${taskLabel} has Iterate.object="${obj}" (bare form) but the parent task ${upstreamFileProducer.id} (${upstreamFileProducer.action_type}) is file-producing — at runtime Iterate#task_process looks for Data.Files.keys.include?("${obj}") which will fail (the actual Files key is "${suggestion}"). Change Iterate.object to "${suggestion}" (file-holder form) to match the Rails runtime, which then routes this through the file-streaming branch (workflow/rails/app/models/tasks/iterate.rb L68-109). The For-Each body will still rebind Data.${obj}.<field> per row.`,
              `${taskLoc}.object`
            );
          } else {
            // E170 already fires; emit E176 too so the iterate-specific guidance
            // appears alongside the generic missing-scope error.
            out.error(
              "E176",
              `${taskLabel} has Iterate.object="${obj}" but no upstream task or trigger seed produces Data.${obj} as Array<Hash>. Iterate.object must be either (a) an upstream Array<Hash> scope name (Query/CustomObject::Query/GraphQuery writes Data.<Object> as Array), (b) a file-name like "<Object>__<TaskId>.csv(.zip)" produced by an Export/File::*/Data::Link, or (c) the literal "CUSTOM LIQUID" with parameters.liquid_statement set.`,
              `${taskLoc}.object`
            );
          }
        }
      }
    }

    // ---- W177: undeclared describe field ----
    // Tasks whose selected fields or where_clause predicates reference field names
    // that should be present in the live tenant describe (or in the bundled
    // fallback catalog).
    const FIELD_BEARING = new Set([
      "Export",
      "Query",
      "Create",
      "Update",
      "CustomObject::Query",
      "CustomObject::Create",
      "CustomObject::Update",
    ]);
    if (FIELD_BEARING.has(task.action_type) && standardFields && isPlainObject(standardFields.objects)) {
      const objectName = typeof task.object === "string" ? task.object.trim() : "";
      const params = isPlainObject(task.parameters) ? task.parameters : {};
      const fieldsParam = isPlainObject(params.fields) ? params.fields : null;
      if (objectName.length > 0) {
        // Normalize: Export/Query use parameters.fields[<object>] => Array<string|object>
        // CustomObject::* use parameters.fields[<object>] => Hash<FieldName, value>
        const selectedFieldNames = [];
        if (fieldsParam) {
          const declaredForObject = fieldsParam[objectName];
          if (Array.isArray(declaredForObject)) {
            for (const entry of declaredForObject) {
              if (typeof entry === "string") selectedFieldNames.push(entry);
              else if (isPlainObject(entry) && typeof entry.field_name === "string")
                selectedFieldNames.push(entry.field_name);
            }
          } else if (isPlainObject(declaredForObject)) {
            selectedFieldNames.push(...Object.keys(declaredForObject));
          }
        }

        const whereFieldNames =
          task.action_type === "Export" || task.action_type === "Query"
            ? extractWhereClauseFieldNames(params.where_clause, objectName)
            : [];
        const candidateFieldRefs = selectedFieldNames
          .map((fieldName) => ({ fieldName, source: "parameters.fields", loc: `${taskLoc}.parameters.fields.${objectName}` }))
          .concat(
            whereFieldNames.map((fieldName) => ({
              fieldName,
              source: "parameters.where_clause",
              loc: `${taskLoc}.parameters.where_clause`,
            }))
          );

        if (candidateFieldRefs.length > 0) {
          // Custom Object describe is tenant-specific; never warn for those.
          const isCustomObject = task.action_type.startsWith("CustomObject::");
          if (!isCustomObject) {
            const objectEntry = standardFields.objects[objectName];
            if (objectEntry && Array.isArray(objectEntry.fields)) {
              const known = new Set(objectEntry.fields);
              for (const { fieldName, source, loc } of candidateFieldRefs) {
                // Skip custom fields and dotted joins (linter can't resolve these statically).
                if (/__c$/.test(fieldName)) continue;
                if (fieldName.includes(".")) continue;
                if (!known.has(fieldName)) {
                  out.warn(
                    "W177",
                    `${taskLabel} references field "${fieldName}" on object "${objectName}" in ${source}, but the static fallback catalog (references/zuora-standard-fields.json) does not list it. Confirm via live describe before using Object Query/Export filters. If the field is not selectable/filterable on this object, do not build an Object Query with it; use a supported API/Data::Link query path or ask the user for the supported relationship. (When live describe is unavailable in this lint run, treat as a notice; the tenant may still know this field.)`,
                    loc
                  );
                }
              }
            }
            // If the object is unknown to the catalog, we can't check fields -- emit no warning.
          }
        }
      }
    }

    // ---- W178: UI-only parameter leaked ----
    // For tasks whose template carries a configuration_contract.fields[], every key
    // in task.parameters must be either listed in the contract, or a universally-
    // permitted housekeeping key. Catches typo'd parameter names that the model
    // would silently drop at runtime.
    const tmpl = templates[task.action_type];
    if (tmpl && isPlainObject(tmpl.configuration_contract) && Array.isArray(tmpl.configuration_contract.fields)) {
      const allowed = new Set([
        "strict_variables",
        "disable_validation",
        "disable_regex",
        "_opaque_trusted",
        "_expected_response_schema",
      ]);
      for (const fieldDef of tmpl.configuration_contract.fields) {
        if (!isPlainObject(fieldDef) || typeof fieldDef.$field !== "string") continue;
        const fld = fieldDef.$field.trim();
        // Only consider top-level parameters.* fields; nested paths (e.g. parameters.sms.numbers)
        // are validated by the model, and the linter would need a deeper walk to verify them.
        const m = /^parameters\.([^.[]+)/.exec(fld);
        if (m) allowed.add(m[1]);
      }
      const params = isPlainObject(task.parameters) ? task.parameters : {};
      for (const k of Object.keys(params)) {
        if (allowed.has(k)) continue;
        // Tolerate keys whose values are themselves nested-form containers (e.g. Approval
        // delivery_method-specific subhashes); only warn for true scalar/array leaks.
        out.warn(
          "W178",
          `${taskLabel} has parameters.${k} but it is not declared in the task's configuration_contract.fields[] (workflow-task-templates.json). Either the field is misspelled, the contract is incomplete, or the field is a UI-only artifact that the controller drops. See workflow-task-configuration.md for the canonical field list.`,
          `${taskLoc}.parameters.${k}`
        );
      }
    }
  }
}

// ---------- Public API ----------

function lintWorkflow(doc, rules) {
  const r = rules || loadRules();
  const { templates, enums, railsTimezones, standardFields } = r;
  const out = makeCollector();

  if (!isPlainObject(doc)) {
    out.error("E000", `Root document must be an object`, `$`);
    return { errors: out.errors, warnings: out.warnings };
  }

  checkEnvelope(doc, out, enums, { railsTimezones, standardFields });
  checkTasks(doc, out, templates, enums);
  checkLinkages(doc, out, templates, enums);
  checkCompositionQuality(doc, out);
  checkZuoraRestEndpointUrls(doc, out);
  checkZuoraCalloutAuthorization(doc, out);
  checkLegacyBillRunObjectCrudCallouts(doc, out);
  checkZuoraCalloutValidation(doc, out);
  checkDataFlow(doc, out, templates, enums);
  checkIterateAndDescribe(doc, out, templates, enums, standardFields);

  return { errors: out.errors, warnings: out.warnings };
}

// ---------- CLI ----------

function formatIssue(kind, issue) {
  return `  ${kind} [${issue.rule}] ${issue.loc ? `at ${issue.loc}: ` : ""}${issue.msg}`;
}

function printReport(file, errors, warnings, { quiet = false, noWarn = false } = {}) {
  const hasErrors = errors.length > 0;
  const hasWarns = warnings.length > 0 && !noWarn;
  if (!quiet || hasErrors || hasWarns) {
    console.log(`\n${file}`);
  }
  if (!quiet) {
    for (const e of errors) console.log(formatIssue("ERROR  ", e));
    if (!noWarn) {
      for (const w of warnings) console.log(formatIssue("WARN   ", w));
    }
  }
  if (!quiet || hasErrors || hasWarns) {
    console.log(
      `  ${errors.length} error(s), ${warnings.length} warning(s)${
        noWarn ? " (warnings suppressed from exit code)" : ""
      }`
    );
  }
}

function main(argv) {
  const args = argv.slice(2);
  const files = [];
  const opts = { quiet: false, noWarn: false, json: false };

  for (const arg of args) {
    if (arg === "--quiet" || arg === "-q") opts.quiet = true;
    else if (arg === "--no-warn") opts.noWarn = true;
    else if (arg === "--json") opts.json = true;
    else if (arg === "--help" || arg === "-h") {
      console.log(
        `Usage: lint-workflow-json.js [--quiet] [--no-warn] [--json] <file> [<file> ...]`
      );
      process.exit(0);
    } else files.push(arg);
  }

  if (files.length === 0) {
    console.error("lint-workflow-json.js: no input files");
    process.exit(2);
  }

  const rules = loadRules();
  let totalErrors = 0;
  let totalWarnings = 0;
  const results = [];

  for (const f of files) {
    let doc;
    try {
      doc = readJson(f);
    } catch (e) {
      if (e.parseError) {
        if (opts.json) {
          results.push({ file: f, parseError: e.message, errors: [], warnings: [] });
        } else {
          console.log(`\n${f}\n  ERROR   [E001-parse] ${e.message}`);
        }
        totalErrors++;
        continue;
      }
      throw e;
    }
    const { errors, warnings } = lintWorkflow(doc, rules);
    if (opts.json) {
      results.push({ file: f, errors, warnings });
    } else {
      printReport(f, errors, warnings, opts);
    }
    totalErrors += errors.length;
    totalWarnings += warnings.length;
  }

  if (opts.json) {
    console.log(JSON.stringify({ results, totalErrors, totalWarnings }, null, 2));
  } else {
    console.log(
      `\nTotal: ${totalErrors} error(s), ${totalWarnings} warning(s) across ${files.length} file(s)`
    );
  }

  const exitOnWarn = !opts.noWarn && totalWarnings > 0 && totalErrors === 0;
  if (totalErrors > 0) process.exit(1);
  // Convention: warnings alone don't fail (let CI opt in with default).
  process.exit(0);
}

if (require.main === module) {
  main(process.argv);
}

module.exports = { lintWorkflow, loadRules };
