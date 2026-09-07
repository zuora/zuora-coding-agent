"""
DataFlowTracker — tracks available Data.* payload paths as workflow tasks execute.

Used by build_workflow_json to:
1. Validate that every {{Data.X.Y}} Liquid reference is available at the point it is used.
2. Produce the human-readable data_payload_trace table in the output.
"""

from __future__ import annotations

import re
from typing import Any

# Common fields added after a Query on a named object
_QUERY_DEFAULT_FIELDS = ["Id", "Name", "Status", "CreatedDate", "UpdatedDate"]

# Standard fields present on most Zuora objects (always considered "available"
# even if a Query/Export didn't explicitly name them). Used when validating
# Liquid references against explicitly-selected fields.
_STANDARD_OBJECT_FIELDS: frozenset[str] = frozenset(
    {
        "Id",
        "Name",
        "Status",
        "CreatedDate",
        "UpdatedDate",
        "CreatedById",
        "UpdatedById",
    }
)


# ---------------------------------------------------------------------------
# Opaque-output task types
# ---------------------------------------------------------------------------
# These task types write payload roots whose nested shape we cannot predict
# at validation time:
#   * Callout / AsynchronousCallout — the response body comes from an
#     external HTTP service.
#   * Logic::Lambda / Script::JavaScript — arbitrary user code.
#   * Logic::JSONTransform / Logic::XMLTransform / Logic::ResponseFormatter
#     — user-defined transformations whose output keys we don't enumerate.
#   * Logic::Liquid base path — free-form Liquid template output (specific
#     ``{% assign %}`` paths *are* still recorded as concrete entries).
#   * CustomObject::* — tenant-defined schemas.
#   * Data::* warehouse / preview / link / aqua — bulk-data outputs whose
#     row schema is determined at run time.
#   * Iterate.Tasks — per-task result map keyed by task id.
#   * File / Reporting / Usage / Notifications / UI mediation outputs —
#     opaque payloads sourced from downstream services.
#
# The tracker still records ``Data.<root>`` in ``available`` so the
# ``parent_available`` reachability check passes for any nested ref. Marking
# the same path in ``dynamic_paths`` tells ``validate_expression`` to *skip*
# the selected-field check when the reference resolves under one of these
# roots — that prevents false-positive ``LIQUID_FIELD_NOT_SELECTED`` errors
# whenever the opaque root happens to share a name with a Zuora object that
# was previously narrowed by a Query/Export selected-fields list (e.g. a
# Callout with ``payload_location: "Account"`` after ``Query Account``
# selected only ``Id``). Strict field validation is preserved everywhere
# else — including direct ``Data.<obj>.<field>`` references that were *not*
# routed through a dynamic-output task.


def _extract_field_names(obj_fields: Any) -> list[str]:
    """Extract the set of field names from either dict-of-dicts or dict-of-list fields spec.

    Supports:
      - {"Id": "true", "Name": "true"}  -> ["Id", "Name"]
      - ["Id", "Name"]                  -> ["Id", "Name"]
    """
    if isinstance(obj_fields, dict):
        return [f for f in obj_fields.keys() if isinstance(f, str) and f.strip()]
    if isinstance(obj_fields, list):
        return [f for f in obj_fields if isinstance(f, str) and f.strip()]
    return []


class DataFlowTracker:
    """Tracks the set of available Data.* paths through a workflow execution.

    Also tracks which specific fields have been explicitly selected by Query/Export/
    GraphQuery tasks for each data object, so Liquid references like
    ``{{Data.Invoice.CustomerName}}`` can be validated against the actual selection
    (not just the presence of ``Data.Invoice``).
    """

    def __init__(self) -> None:
        self.available: set[str] = {
            # Always available from workflow start
            "Data.Workflow",
            "Data.Workflow.ExecutionDate",
            "Data.Workflow.ExecutionDateTime",
            "Data.UIAction",
            "Data.UIAction.ObjectId",
            "WorkflowInstance",
            "WorkflowInstance.id",
            "Credentials",
            "Credentials.zuora",
            "Credentials.zuora.bearer_token",
            "Credentials.zuora.rest_endpoint",
            "GlobalConstants",
        }
        # Tracks {object_name: set(field_names)} that were explicitly selected
        # by a producing task (Query/Export/GraphQuery) or provided as input.
        self.selected_fields: dict[str, set[str]] = {}
        # Roots whose nested shape is opaque (Callout response, Lambda
        # output, custom-object schema, etc.). When a Liquid reference
        # resolves *under* any of these roots the selected-field check is
        # skipped to avoid false positives — see ``_under_dynamic_root``.
        self.dynamic_paths: set[str] = set()

    def _mark_dynamic(self, path: str) -> None:
        """Record ``path`` as opaque/unpredictable.

        Called from ``after_task`` for every task type whose output we
        cannot statically enumerate (Callout, Lambda, JSONTransform, …).
        Also records the path in ``available`` so callers don't need a
        separate ``self.available.add`` line at every site.
        """
        if not path:
            return
        self.available.add(path)
        self.dynamic_paths.add(path)

    def _under_dynamic_root(self, ref_path: str) -> bool:
        """Return True if any prefix of ``ref_path`` is a dynamic root.

        ``ref_path`` is the brackets-stripped Liquid reference (e.g.
        ``"Data.Callout.user.email"``). Walking ancestor segments left to
        right matches both single-segment roots (``Data.Callout``) and
        multi-segment ones (``Data.Iterate.Tasks``, ``Data.AQuA.Invoice``)
        without false-positiving on partial-name overlaps.
        """
        if not self.dynamic_paths or not ref_path:
            return False
        parts = ref_path.split(".")
        for i in range(2, len(parts) + 1):
            if ".".join(parts[:i]) in self.dynamic_paths:
                return True
        return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_input_fields(self, input_fields: list[dict]) -> None:
        """Seed the tracker with workflow input parameter paths."""
        for field in input_fields:
            obj = field.get("object_name", "")
            fname = field.get("field_name", "")
            if obj and fname:
                self.available.add(f"Data.{obj}")
                self.available.add(f"Data.{obj}.{fname}")
                self.selected_fields.setdefault(obj, set()).add(fname)

    def add_event_payload(self, payload_by_object: dict[str, list[str]]) -> None:
        """Seed the tracker with event payload fields per object.

        Call once after event_parameters are wired so that Liquid references
        targeting event payload fields validate correctly.
        """
        for obj, fields in payload_by_object.items():
            if not isinstance(obj, str) or not obj:
                continue
            self.available.add(f"Data.{obj}")
            field_set = self.selected_fields.setdefault(obj, set())
            for f in fields or []:
                if isinstance(f, str) and f.strip():
                    self.available.add(f"Data.{obj}.{f}")
                    field_set.add(f)

    def _record_selected(self, object_name: str, fields: list[str]) -> None:
        """Record explicitly-selected field names for an object."""
        if not object_name:
            return
        field_set = self.selected_fields.setdefault(object_name, set())
        for f in fields:
            if isinstance(f, str) and f.strip():
                field_set.add(f)
                self.available.add(f"Data.{object_name}.{f}")

    def after_task(self, task_type: str, config: dict, task_name: str = "") -> None:
        """Update available paths after a task of the given type executes."""
        obj = config.get("object") or config.get("placement") or ""
        task_id = config.get("id", "")

        if task_type == "Query":
            placement = config.get("placement") or obj
            if placement:
                self.available.add(f"Data.{placement}")
                fields_param = config.get("fields", {})
                selected_names: list[str] = []
                if isinstance(fields_param, dict):
                    for obj_name, obj_fields in fields_param.items():
                        names = _extract_field_names(obj_fields)
                        if obj_name == placement:
                            selected_names.extend(names)
                        else:
                            self._record_selected(obj_name, names)
                if selected_names:
                    self._record_selected(placement, selected_names)
                else:
                    # No explicit fields -> treat as "select-all" for this placement
                    # (no selected_fields recorded so validation falls back to
                    # parent-path + standard-fields check)
                    for field in _QUERY_DEFAULT_FIELDS:
                        self.available.add(f"Data.{placement}.{field}")

        elif task_type == "Export":
            export_obj = obj or config.get("object", "")
            if export_obj:
                self.available.add(f"Data.Export.{export_obj}")
                self.available.add(f"Data.{export_obj}")
                fields_param = config.get("fields", {})
                if isinstance(fields_param, dict):
                    for obj_name, obj_fields in fields_param.items():
                        names = _extract_field_names(obj_fields)
                        target = obj_name if obj_name else export_obj
                        self._record_selected(target, names)
                        if obj_name and obj_name != export_obj:
                            self.available.add(f"Data.{obj_name}")
            self.available.add("Data.Files")

        elif task_type == "Data::Link":
            # Data::Link writes link-script output into LinkRun / LinkData;
            # both shapes are user-defined per Connect link template.
            self._mark_dynamic("Data.LinkRun")
            self._mark_dynamic("Data.LinkData")
            self.available.add("Data.Files")

        elif task_type == "Data::Aqua":
            aqua_obj = obj or ""
            if aqua_obj:
                # AQuA bulk-export rows are emitted under Data.AQuA.<obj>
                # but the column set comes from the customer's ZOQL query
                # text (which we don't parse for fields here).
                self._mark_dynamic(f"Data.AQuA.{aqua_obj}")
            self.available.add("Data.Files")

        elif task_type == "Data::Warehouse":
            # Warehouse query → opaque result rows.
            self._mark_dynamic("Data.WarehouseResult")

        elif task_type == "Data::BillingPreviewRun":
            # BillingPreview returns a deeply nested preview document with
            # tenant-dependent fields.
            self._mark_dynamic("Data.BillingPreview")

        elif task_type == "GraphQuery":
            placement = config.get("placement", "")
            if placement:
                self.available.add(f"Data.{placement}")
            base_obj = obj
            if base_obj:
                self.available.add(f"Data.{base_obj}")
            fields_param = config.get("fields", {})
            if isinstance(fields_param, dict):
                for obj_name, obj_fields in fields_param.items():
                    names = _extract_field_names(obj_fields)
                    self._record_selected(obj_name, names)
                    if obj_name and obj_name != base_obj:
                        self.available.add(f"Data.{obj_name}")

        elif task_type == "Iterate":
            iterate_obj = config.get("object") or obj
            if iterate_obj:
                # The current iteration item carries the same field set the
                # upstream collection-source produced, so this root stays
                # under strict validation (NOT dynamic).
                self.available.add(f"Data.{iterate_obj}")
            # ``Iterate.Tasks`` is keyed by per-task subscription ids whose
            # nested output is opaque.
            self._mark_dynamic("Data.Iterate.Tasks")

        elif task_type == "Logic::Liquid":
            # Zuora persists each ``{% assign <name> = <expr> %}`` under the workflow
            # Liquid payload: the **left-hand side** ``<name>`` is the key; the RHS only
            # supplies the value (e.g. ``{% assign example = Data.Workflow %}`` stores
            # whatever ``Data.Workflow`` resolves to, and the **next** task reads it as
            # ``{{ Data.Liquid.example }}`` — not ``Data.example``).
            #
            # We still mark ``Data.Liquid`` as dynamic (opaque nested shape) and record
            # assign LHS paths for reachability checks inside this tracker.
            self._mark_dynamic("Data.Liquid")
            code = config.get("code", "")
            assign_pattern = re.compile(r"\{%-?\s*assign\s+([\w.]+)\s*=", re.IGNORECASE)
            for match in assign_pattern.finditer(code):
                var_path = match.group(1).strip()
                self.available.add(var_path)
                parts = var_path.split(".")
                for i in range(1, len(parts)):
                    self.available.add(".".join(parts[:i]))
                # Path the next task uses in Liquid for this assign's stored value.
                if "." not in var_path:
                    self.available.add(f"Data.Liquid.{var_path}")
                elif var_path.startswith("Data.Liquid."):
                    self.available.add(var_path)

        elif task_type == "Logic::ResponseFormatter":
            # User-defined response shape; we record only the root.
            self._mark_dynamic("Data.ResponseFormatter")

        elif task_type == "Logic::Merge":
            # Merge merges all branch data; we can't enumerate it here
            # The caller is responsible for union-ing all branch trackers
            pass

        elif task_type == "Logic::CSVTranslator":
            self.available.add("Data.Files")

        elif task_type == "Logic::JSONTransform":
            # JSONTransform output keys are user-defined.
            self._mark_dynamic("Data.TransformResult")

        elif task_type == "Logic::XMLTransform":
            self._mark_dynamic("Data.TransformResult")

        elif task_type == "Logic::Lambda":
            self._mark_dynamic("Data.LambdaResult")

        elif task_type == "Script::JavaScript":
            self._mark_dynamic("Data.ScriptResult")

        elif task_type == "Callout":
            payload_loc = config.get("validation", {})
            if isinstance(payload_loc, dict):
                payload_loc = payload_loc.get("payload_location", "Callout")
            else:
                payload_loc = "Callout"
            # The Callout response is opaque — mark the placement root
            # dynamic so nested refs like ``Data.Callout.user.email`` and
            # custom ``payload_location`` overrides (e.g. "Account") are
            # not falsely rejected by the selected-field check.
            self._mark_dynamic(f"Data.{payload_loc or 'Callout'}")

        elif task_type == "AsynchronousCallout":
            pass  # fire and forget — no data written

        elif task_type == "Create":
            if obj:
                self.available.add(f"Data.{obj}")

        elif task_type == "Update":
            if obj:
                self.available.add(f"Data.{obj}")

        elif task_type == "Delete":
            pass  # removes data rather than adding it

        elif task_type in ("CustomObject::Create", "CustomObject::Update", "CustomObject::Query"):
            # CustomObjects are tenant-defined; the field set is unknown
            # at design time.
            self._mark_dynamic("Data.CustomObject")

        elif task_type == "CustomObject::Delete":
            pass

        elif task_type == "Execute::WorkflowTask":
            # Sub-workflow output has whatever shape the child workflow
            # produces — opaque to the parent at validation time.
            placement = config.get("placement", "ExecuteWorkflow")
            self._mark_dynamic(f"Data.{placement or 'ExecuteWorkflow'}")

        elif task_type == "Email":
            self.available.add("Data.Files")
            # email__<taskId>.html and email_encoded__<taskId>.txt
            if task_id:
                self.available.add(f"Data.Files.email__{task_id}.html")
                self.available.add(f"Data.Files.email_encoded__{task_id}.txt")

        elif task_type == "Notifications::SMS":
            # Provider response payload — opaque.
            self._mark_dynamic("Data.SMSResult")

        elif task_type == "Notifications::Kafka":
            self._mark_dynamic("Data.KafkaResult")

        elif task_type == "Approval":
            # Approval result carries reviewer-supplied free-form fields.
            self._mark_dynamic("Data.Approval")

        elif task_type == "Delay":
            pass  # no data written

        elif task_type in ("If", "Logic::Case"):
            pass  # control flow only

        elif task_type in ("Billing::BillRun", "InvoiceGenerate", "WriteOff"):
            self.available.add("Data.Invoice")
            self.available.add("Data.BillingRun")

        elif task_type == "Billing::ReverseInvoice":
            self.available.add("Data.Invoice")

        elif task_type == "Billing::CurrencyConversion":
            self.available.add("Data.CurrencyResult")

        elif task_type == "Billing::CustomBillingDocument":
            # The custom document body is templated by the customer, so
            # the resulting Data.BillingDocument shape is opaque.
            self._mark_dynamic("Data.BillingDocument")
            self.available.add("Data.Files")

        elif task_type == "Payment::PaymentRun":
            self.available.add("Data.PaymentRun")
            self.available.add("Data.Payment")

        elif task_type == "Payment::GatewayReconciliation":
            # Gateway response shape is provider-specific.
            self._mark_dynamic("Data.GatewayReconciliation")

        elif task_type in ("NewProduct", "RemoveProduct", "Suspend", "Resume", "Cancel"):
            self.available.add("Data.Subscription")
            self.available.add("Data.Amendment")

        elif task_type in ("File::DownloadFile", "Download::SFTP", "Download::S3"):
            self.available.add("Data.Files")

        elif task_type in ("Upload::FTP", "Upload::SFTP", "Upload::S3"):
            pass  # upload only — no payload data written

        elif task_type in ("File::FileOperations", "File::FileStreamingUpload"):
            self.available.add("Data.Files")

        elif task_type == "File::ZuoraImport":
            # Import response shape varies by import action.
            self._mark_dynamic("Data.ImportResult")

        elif task_type == "File::CustomPDF::CustomDocument":
            self._mark_dynamic("Data.PDFDocument")
            self.available.add("Data.Files")

        elif task_type == "Attachment":
            # Attachment metadata varies (filename / mime / size / id).
            self._mark_dynamic("Data.Attachment")

        elif task_type == "Reporting::RunReport":
            self.available.add("Data.Files")

        elif task_type == "Reporting::OracleFusionReport":
            # Report payload depends on the customer's report definition.
            self._mark_dynamic("Data.OracleFusionReport")
            self.available.add("Data.Files")

        elif task_type == "Usage::ImportUsage":
            self._mark_dynamic("Data.UsageImport")

        # Usage-mediation outputs are tenant-defined map/filter/sink shapes.
        elif task_type == "UsageMediation::Source":
            self._mark_dynamic("Data.Source")

        elif task_type == "UsageMediation::Watermark":
            self._mark_dynamic("Data.Watermark")

        elif task_type == "UsageMediation::Filter":
            self._mark_dynamic("Data.Filter")

        elif task_type == "UsageMediation::Map":
            self._mark_dynamic("Data.Map")

        elif task_type == "UsageMediation::Group":
            self._mark_dynamic("Data.Group")

        elif task_type == "UsageMediation::Sink":
            self._mark_dynamic("Data.Sink")

        elif task_type == "Mediation::SendEvents":
            self._mark_dynamic("Data.SendEvents")

        elif task_type == "UI::Page":
            # UI::Page form fields are configured per workflow; treat the
            # whole payload as dynamic so generic field references don't
            # need a separate static schema.
            self._mark_dynamic("Data.UIPage")

        elif task_type in ("UI::Stop",):
            pass

        elif task_type == "UI::WebShare":
            self._mark_dynamic("Data.WebShare")

        elif task_type == "File::BulkDataLoader":
            self._mark_dynamic("Data.BulkDataLoader")

    def is_field_selected(self, object_name: str, field_name: str) -> bool:
        """True if ``field_name`` was explicitly selected by a producing task for ``object_name``.

        Returns True if:
          - the field was explicitly named in a preceding Query/Export/GraphQuery, OR
          - the field is a widely-available standard field (``Id``, ``Name``, etc.), OR
          - no selection has been tracked for the object (no Query/Export with
            explicit fields has run; caller should fall back to parent-path check).
        """
        if not object_name:
            return False
        if object_name not in self.selected_fields:
            return True
        selected = self.selected_fields[object_name]
        if field_name in selected:
            return True
        if field_name in _STANDARD_OBJECT_FIELDS:
            return True
        return False

    def validate_expression(self, expr: str, context: str = "") -> list[str]:
        """Return list of error strings for any {{Data.X}} refs not yet available.

        Produces two error categories:
          - ``LIQUID_UNREACHABLE`` — neither the path nor any parent is present
          - ``LIQUID_FIELD_NOT_SELECTED`` — the parent object is present but the
            specific field was not selected by any preceding producer

        When a multi-object Export/Query selected the referenced field under a
        different object key (e.g. ``{{Data.Invoice.AccountNumber}}`` but
        ``AccountNumber`` was selected on ``Account``), the error suggests the
        flat ``{{Data.<CorrectObject>.<field>}}`` shape — the common LLM
        mis-nesting symptom.

        References whose ancestor path is in :pyattr:`dynamic_paths` (Callout
        responses, Lambda/Script outputs, custom-object payloads, sub-workflow
        results, etc.) skip the selected-field check — those payload shapes
        are determined at run time and we cannot enumerate them statically.
        """
        errors: list[str] = []
        for match in re.finditer(r"\{\{(.*?)\}\}", expr):
            ref = match.group(1).strip()
            if not ref.startswith("Data."):
                continue
            # Strip Liquid filters (e.g. "| date: '%B %d, %Y'", "| money") before path parsing
            ref_path = ref.split("|")[0].strip()
            clean_ref = re.sub(r"\[\d+\]", "", ref_path)
            clean_ref = re.sub(r"\[.*?\]", "", clean_ref)

            if clean_ref in self.available:
                continue

            parts = clean_ref.split(".")
            parent_available = any(
                ".".join(parts[:i]) in self.available for i in range(2, len(parts))
            )

            if not parent_available:
                errors.append(
                    f"{'[' + context + '] ' if context else ''}Liquid reference "
                    f"'{{{{{ref}}}}}' references data that may not be available at this "
                    f"point in the workflow. Available paths include: "
                    f"{', '.join(sorted(p for p in self.available if 'Data.' in p)[:5])}..."
                )
                continue

            # When the reference resolves under any dynamic-output root
            # (Callout / Lambda / CustomObject / sub-workflow / …) we
            # cannot know the field set, so skip the selected-field check
            # rather than emit a false-positive LIQUID_FIELD_NOT_SELECTED.
            if self._under_dynamic_root(clean_ref):
                continue

            if len(parts) >= 3:
                obj_name = parts[1]
                field_name = parts[-1]
                if obj_name in self.selected_fields and not self.is_field_selected(
                    obj_name, field_name
                ):
                    suggestion = self._suggest_related_path(parts, field_name)
                    available = ", ".join(sorted(self.selected_fields[obj_name])) or "(none)"
                    if suggestion:
                        errors.append(
                            f"{'[' + context + '] ' if context else ''}Liquid reference "
                            f"'{{{{{ref}}}}}' nests '{field_name}' under '{obj_name}', but "
                            f"that field was selected on a related object. Use "
                            f"'{{{{{suggestion}}}}}' instead — multi-object Export/Query "
                            f"results expose related objects at their own flat "
                            f"`Data.<Object>.*` namespace, not nested under the base object."
                        )
                    else:
                        errors.append(
                            f"{'[' + context + '] ' if context else ''}Liquid reference "
                            f"'{{{{{ref}}}}}' uses field '{field_name}' on {obj_name} but "
                            f"preceding tasks only selected: {available}. Add '{field_name}' to "
                            f"the producing task's fields list, or — if '{field_name}' lives "
                            f"on a related object — reference it at its own flat namespace "
                            f"(e.g. '{{{{Data.<RelatedObject>.{field_name}}}}}')."
                        )
        return errors

    def _suggest_related_path(self, parts: list[str], field_name: str) -> str | None:
        """When the referenced field was selected on another tracked object,
        return the flat ``Data.<Object>.<field>`` suggestion. Prefer the
        mid-path token (``parts[-2]`` when ``len(parts) >= 3``) if it matches a
        selected object — that is the most common mis-nesting shape
        (``Data.Invoice.BillToContact.WorkEmail`` -> ``Data.BillToContact.WorkEmail``).
        Falls back to any other selected object that has the field.
        """
        if len(parts) >= 4:
            mid = parts[-2]
            if mid in self.selected_fields and field_name in self.selected_fields[mid]:
                return f"Data.{mid}.{field_name}"
        candidates = [
            name
            for name, fields in self.selected_fields.items()
            if field_name in fields and name not in {parts[1]}
        ]
        if len(candidates) == 1:
            return f"Data.{candidates[0]}.{field_name}"
        return None

    def validate_task_config(self, task_type: str, config: dict, task_name: str = "") -> list[str]:
        """Validate all Liquid expressions in a task's config dict."""
        errors: list[str] = []
        self._scan_for_liquid(config, task_name, errors)
        return errors

    def get_available(self) -> list[str]:
        """Return sorted list of currently available paths."""
        return sorted(self.available)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _scan_for_liquid(self, value: Any, task_name: str, errors: list[str]) -> None:
        """Recursively scan a config value for Liquid expressions."""
        if isinstance(value, str):
            if "{{" in value:
                errors.extend(self.validate_expression(value, task_name))
        elif isinstance(value, dict):
            for v in value.values():
                self._scan_for_liquid(v, task_name, errors)
        elif isinstance(value, list):
            for item in value:
                self._scan_for_liquid(item, task_name, errors)
