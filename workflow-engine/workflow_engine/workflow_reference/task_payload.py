"""Build a Rails-wire-format task request body for edit_workflow's
``add_task`` / ``update_task`` / ``patch_task`` actions.

Pipeline
--------
1. ``plan_normalizer.normalize_task`` — idempotent, mutates ``parameters``
   in place to the shape Rails stores (wrap flat Email → ``{email: {...}}``,
   canonicalise Query/Export ``fields``, canonicalise Callout ``headers``
   to ``[{key, value}, …]`` dicts, stringify non-Callout ``headers`` and
   ``retry_rules`` ints → strings, …).
2. ``TASK_TYPE_CONFIG_MAP[action_type].model_validate(parameters)`` — strict
   Pydantic validation catches missing required fields, wrong types, and
   unknown keys on nested objects (``EmailTaskEmail``, ``CalloutTaskEmail``,
   ``NotificationsSmsTaskSms``, …). A validation failure returns an error
   envelope *before* any HTTP call, so we never reproduce the
   ``Email#cast`` HTTP 500 class of failures on the Rails side.
3. **Canonical wire dump** — the validated instance is dumped with
   ``mode="json"``, ``by_alias=True``, ``exclude_none=False``. This is
   the uniform defence against the ``NoMethodError: '[]' / 'reject!' for
   nil:NilClass`` class of Rails crashes that applies to **every** task
   type in the manifest, not just Email. Rails' ``before_validation``
   callbacks (``Email#cast`` on ``cc`` / ``bcc``, ``Notifications::SMS#cast``
   on ``numbers``, …) and ``task_setup_validation`` guards
   (``Callout`` on ``validation.status_codes``, ``WriteOff`` on
   ``fields.write_off.*``, …) iterate declared sub-fields without
   nil-checks, so the payload must always carry the full declared shape
   with Pydantic defaults in place (``cc=[]``, ``bcc=[]``, ``reply_to=""``,
   ``authorization.username=None``, ``validation.status_codes=[]``, …).
   ``mode="json"`` also serialises enums (``Callout.body_type``,
   ``DataQuery.step_type``, …) as their underlying strings so ``httpx``
   JSON encoding is happy.
4. ``TaskTemplateEngine`` params pipeline — whitelist parameters to those
   declared on ``<Action>TaskParameters`` (plus the common pass-through
   set) and convert ``bool → "true"/"false"`` strings for Rails.

Callers
-------
* ``add_task`` → ``hydrate_defaults=True``. Every declared top-level and
  nested field is present on the wire (mirror of
  ``build_workflow_definition`` used by ``generate_workflow``).
* ``update_task`` / ``patch_task`` → ``hydrate_defaults=False``. Rails
  replaces the parameters dict wholesale on a PATCH, so adding top-level
  defaults for fields the user didn't mention would silently reset them.
  Nested sub-dicts are *still* materialised from the dump so Rails'
  ``before_validation`` callbacks don't crash on missing declared
  children (that's a correctness requirement, not a preference).

Returns ``(body, [])`` on success or ``(None, errors)`` on failure. Errors
follow the envelope shape used by ``plan_validator._validate_pydantic`` so
the LLM sees a familiar, structured message.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ValidationError

from workflow_engine.workflow_reference.models import TASK_TYPE_CONFIG_MAP
from workflow_engine.workflow_reference.plan_normalizer import normalize_task
from workflow_engine.workflow_reference.task_templates import (
    CALLOUT_EXTRA_PASS_THROUGH,
    COMMON_PASS_THROUGH,
    TaskTemplateEngine,
    _base_type,
)

_ENGINE = TaskTemplateEngine()


# Per-action_type allow-list of parameter keys that Rails dereferences
# **without** a nil-guard, but our generated Pydantic model declares with
# a ``None`` default. ``model_dump(exclude_none=False)`` would emit them
# as ``null`` on the wire, and Rails would crash with
# ``NoMethodError: undefined method '<...>' for nil:NilClass`` because
# the typical Ruby idiom ``parameters.fetch(key, {}).reverse_merge(...)``
# returns the **value** (``nil``) when the key is present-but-nil, not
# the default ``{}``.
#
# Confirmed crashes / citations:
#   * Callout / AsynchronousCallout — ``parameters['validation']``
#     crashes ``app/models/tasks/callout.rb:719`` in
#     ``Callout#validation`` (called from ``task_setup_validation``):
#         self.parameters.fetch('validation', {}).reverse_merge({...})
#     Pydantic default: ``CalloutTaskParameters.validation = None``.
#     Triggers on every ``add_task`` for a Callout where the user did
#     not opt into response validation.
#
#   * File::CustomPDF::CustomDocument /
#     Billing::CustomBillingDocument — ``parameters['advanced']``
#     crashes ``app/models/tasks/file/custom_pdf.rb:130`` in
#     ``File::CustomPDF#advanced_settings``:
#         self.parameters.fetch('advanced', {}).reverse_merge!({...})
#     This is invoked at *runtime* (``task_process`` → ``generate_pdf``)
#     rather than ``task_setup_validation``, so ``add_task`` itself
#     succeeds — but the very first execution of the task crashes
#     before any PDF is produced. Same Ruby footgun
#     (``Hash#fetch(k, default)`` returns ``nil`` if ``k`` is
#     present-but-nil), same fix.
#     Pydantic defaults:
#       - ``CustomPdfDocumentTaskParameters.advanced = None``
#       - ``BillingCustomDocumentTaskParameters.advanced = None``
#     ``Billing::CustomBillingDocument`` < ``File::CustomPDF::CustomDocument``
#     < ``File::CustomPDF`` so both inherit the same call.
#
# Adding a key here means: "if the value is ``None`` after the dump,
# drop it from the wire payload entirely so Rails uses its own
# ``fetch(...)`` default." User-supplied non-``None`` values are
# preserved as-is. Do **not** add keys that Rails handles safely
# (``Email.email.cc`` / ``bcc``, ``Callout.authorization.username``,
# ``Callout.force_new_token``, …) — the deliberate
# ``exclude_none=False`` behaviour for those is documented at the top
# of this module and is required for ``Email#cast`` and friends.
_RAILS_NIL_FRAGILE_PARAMETERS: dict[str, frozenset[str]] = {
    "Callout": frozenset({"validation"}),
    "AsynchronousCallout": frozenset({"validation"}),
    "File::CustomPDF::CustomDocument": frozenset({"advanced"}),
    "Billing::CustomBillingDocument": frozenset({"advanced"}),
}


def _strip_rails_nil_fragile_keys(action_type: str, params: dict[str, Any]) -> None:
    """Drop ``None`` values from ``params`` for keys Rails can't tolerate as ``null``.

    See ``_RAILS_NIL_FRAGILE_PARAMETERS`` for the rationale. Mutates
    ``params`` in place and is a no-op for action types not in the map
    or for keys whose values are not exactly ``None``.
    """
    fragile = _RAILS_NIL_FRAGILE_PARAMETERS.get(action_type)
    if not fragile:
        return
    for key in fragile:
        if key in params and params[key] is None:
            del params[key]


def _validate_required_strings_nonblank(
    instance: BaseModel,
    base_path: str = "parameters",
) -> list[dict[str, Any]]:
    """Report any required string field on ``instance`` whose value is blank.

    The generated Pydantic models use ``str`` (without a ``min_length``
    constraint) for fields that are *required to be present* — that is
    the manifest contract from upstream Rails. ``""`` therefore passes
    Pydantic validation, but Rails enforces non-emptiness on several
    columns at the model layer:

    * ``Email.email.template``  →  HTTP 400/422 ``"Email template
      cannot be blank."``
    * ``Email.email.subject``   →  HTTP 422 ``"Subject can't be blank"``
    * ``Notifications::SMS.sms.body`` → HTTP 422 ``"Body is required"``
    * ``Callout.callout.url``  →  HTTP 422 ``"URL is required"``

    Rather than enumerate per-task-type rules (which would drift
    against upstream changes), we walk the validated instance, find
    every field marked ``is_required()`` whose value is a string, and
    fail fast if it strips to empty. The same pass also recurses into
    nested ``BaseModel`` children (e.g. ``EmailTaskEmail`` inside
    ``EmailTaskParameters``) and into items of ``list[BaseModel]``
    fields (e.g. ``CalloutTaskHeadersItem`` entries).

    Returned errors use the same ``{path, code, message, fix_hint}``
    shape as ``_format_pydantic_error`` so the agent's existing
    ``render_validation_errors`` formatter can surface them without
    a special case.
    """
    errors: list[dict[str, Any]] = []

    def _walk(model: BaseModel, path: str) -> None:
        cls = type(model)
        fields = getattr(cls, "model_fields", None) or {}
        for field_name, field_info in fields.items():
            value = getattr(model, field_name, None)
            # Use the wire-format alias when the field is aliased
            # (e.g. ``EmailTaskEmail.from_`` → ``"from"``) so error
            # paths match what the user typed in ``parameters``.
            wire_name = field_info.alias or field_name
            sub_path = f"{path}.{wire_name}"

            if isinstance(value, BaseModel):
                _walk(value, sub_path)
                continue

            if isinstance(value, list):
                # Flag empty lists for *required* fields that don't carry a
                # ``min_length`` constraint at the Pydantic layer. Rails'
                # ``task_setup_validation`` rejects these (e.g.
                # ``Notifications::SMS#task_setup_validation`` raises
                # "SMS numbers are required" when ``sms.numbers == []``),
                # but because the corresponding generated model only
                # declares ``list[str]`` we'd otherwise happily POST the
                # empty array. Once we layer ``disable_validation="true"``
                # onto in-place patches, Rails stops catching this for us
                # and the task persists in a broken state. Catch it here
                # so the failure mode stays "refuse client-side" instead of
                # "silently save a task that can never run".
                if field_info.is_required() and not value:
                    errors.append(
                        {
                            "path": sub_path,
                            "code": "REQUIRED_LIST_EMPTY",
                            "message": (
                                f"Required field `{sub_path}` is present but "
                                "empty. Rails rejects empty arrays on "
                                "required list columns (e.g. "
                                "`Notifications::SMS.sms.numbers`, "
                                "`Email.email.to`)."
                            ),
                            "fix_hint": (f"Provide at least one value for `{sub_path}`."),
                        }
                    )
                for idx, item in enumerate(value):
                    if isinstance(item, BaseModel):
                        _walk(item, f"{sub_path}[{idx}]")
                continue

            if not field_info.is_required():
                continue

            if isinstance(value, str) and not value.strip():
                errors.append(
                    {
                        "path": sub_path,
                        "code": "REQUIRED_STRING_BLANK",
                        "message": (
                            f"Required field `{sub_path}` is present but "
                            "blank. Rails rejects empty values on required "
                            "string columns (e.g. Email template, subject, "
                            "Callout URL, SMS body)."
                        ),
                        "fix_hint": (
                            f"Provide a non-empty value for `{sub_path}` "
                            "or omit the field entirely if the existing "
                            "tenant value should be preserved (note: "
                            "in-place patches replace `parameters` "
                            "wholesale on Rails, so omitting a required "
                            "field is *not* the same as keeping the prior "
                            "value)."
                        ),
                    }
                )

    _walk(instance, base_path)
    return errors


def _format_pydantic_error(err: dict[str, Any]) -> dict[str, Any]:
    """Translate a ``ValidationError`` entry into the agent's envelope."""
    loc = [p for p in err.get("loc", []) if p != "__root__"]
    path_parts = [str(p) for p in loc]
    path = "parameters" + ("." + ".".join(path_parts) if path_parts else "")
    err_type = err.get("type", "validation_error")
    message = err.get("msg", "validation error")
    return {
        "path": path,
        "code": err_type.upper(),
        "message": message,
        "fix_hint": _pydantic_fix_hint(path, message, err_type),
    }


def _pydantic_fix_hint(path: str, msg: str, err_type: str) -> str:
    lower = msg.lower()
    if err_type == "missing" or "missing" in lower or "field required" in lower:
        return f"Required field `{path}` is missing. Add it to `parameters`."
    if "too_short" in err_type or ("list" in lower and "at least" in lower):
        return f"Field `{path}` must contain at least one item."
    if "enum" in lower or err_type.startswith("enum"):
        return f"Field `{path}` uses a value outside the allowed enum."
    if "extra_forbidden" in err_type or "extra inputs" in lower:
        return f"Unknown field `{path}` — remove it from `parameters`."
    if "type" in err_type or "str type" in lower:
        return f"Field `{path}` has the wrong type. " "Check the task schema and convert the value."
    return "Fix the parameters to match the task's JSON schema, then retry."


def build_task_request_body(
    *,
    action_type: str,
    name: Optional[str],
    parameters: Optional[dict[str, Any]] = None,
    object_name: Optional[str] = None,
    object_id: Optional[str] = None,
    hydrate_defaults: bool = True,
) -> tuple[Optional[dict[str, Any]], list[dict[str, Any]]]:
    """Produce a validated Rails request body for a task create/patch call.

    Parameters
    ----------
    action_type
        The Zuora task type (``"Email"``, ``"Callout"``, ``"Query"``, …).
        Must be present in ``TASK_TYPE_CONFIG_MAP``; anything else is a hard
        validation failure.
    name
        Task display name. Echoed back on the body; ``None`` is allowed for
        ``patch_task`` (name optional in a config-only patch).
    parameters
        User-supplied parameters dict. May be in any of the "LLM-friendly"
        shapes the normalizer knows about (flat Email, list-of-dict Callout
        headers, …). ``None`` is treated as an empty dict.
    object_name / object_id
        Optional top-level fields echoed into the body. Required for some
        task types (Query, Export, CRUD) but that requirement is enforced
        by the ``<Action>Task`` Pydantic model, not here.
    hydrate_defaults
        When ``True`` (``add_task`` default) every Pydantic-declared field
        is set to its default if the caller omits it. When ``False``
        (``update_task`` / ``patch_task``) only user-supplied keys make it
        into the payload — Rails replaces ``parameters`` wholesale, so
        hydrating would reset custom values on every update.

    Returns
    -------
    ``(body, [])`` on success. ``body`` is a dict with
    ``name``, ``action_type``, ``parameters`` (plus ``object`` /
    ``object_id`` when present). Suitable for both
    ``POST /workflows/:wid/tasks`` and
    ``PATCH /workflows/tasks/:tid/config`` — both endpoints permit only
    these keys plus the linkage arrays (which the caller owns).

    ``(None, errors)`` on any validation failure. ``errors`` is a list of
    ``{path, code, message, fix_hint}`` entries — same shape
    ``plan_validator._validate_pydantic`` produces so the LLM gets a
    consistent error format.
    """
    errors: list[dict[str, Any]] = []

    if not action_type:
        errors.append(
            {
                "path": "action_type",
                "code": "ACTION_TYPE_REQUIRED",
                "message": "action_type is required.",
                "fix_hint": (
                    "Set `action_type` on the task_spec / task_patch (e.g. "
                    "'Email', 'Callout', 'Query', 'Notifications::SMS')."
                ),
            }
        )
        return None, errors

    config_cls = TASK_TYPE_CONFIG_MAP.get(action_type)
    if config_cls is None:
        errors.append(
            {
                "path": "action_type",
                "code": "UNKNOWN_ACTION_TYPE",
                "message": f"Unknown action_type {action_type!r}.",
                "fix_hint": (
                    "Use a value from TaskTypeEnum (e.g. 'Email', 'Callout', "
                    "'Query', 'Export', 'Iterate', 'Notifications::SMS', …)."
                ),
            }
        )
        return None, errors

    params_in = dict(parameters or {})
    shim: dict[str, Any] = {
        "action_type": action_type,
        "parameters": params_in,
    }
    if name is not None:
        shim["name"] = name
    if object_name is not None:
        shim["object"] = object_name

    try:
        normalize_task(shim)
    except Exception as exc:
        errors.append(
            {
                "path": "parameters",
                "code": "NORMALIZER_ERROR",
                "message": str(exc),
                "fix_hint": (
                    "Make sure `parameters` is a plain dict. The normalizer "
                    "accepts flat Email / Callout shapes and rewrites them."
                ),
            }
        )
        return None, errors

    params = shim.get("parameters") or {}

    try:
        validated = config_cls.model_validate(params)
    except ValidationError as exc:
        for err in exc.errors():
            errors.append(_format_pydantic_error(err))  # type: ignore[arg-type]
        return None, errors

    # Pydantic-only validation accepts ``""`` for required ``str``
    # fields because the manifest's ``required`` array only checks
    # presence, not non-emptiness. Rails enforces non-emptiness on
    # several columns (Email.template, Email.subject, Callout.url,
    # Notifications::SMS.body, …) and returns 400/422 on blank input.
    # Catch the full class of failure here so the agent never makes
    # the round-trip just to learn ``"Email template cannot be blank"``.
    blank_errors = _validate_required_strings_nonblank(validated)
    if blank_errors:
        return None, blank_errors

    # Dump the validated instance into its canonical wire shape.
    #
    # ``mode="json"`` — enum values serialise as their underlying strings
    # (``Callout.body_type``, ``DataQuery.step_type``, …) rather than
    # ``<Enum.member>`` objects that break ``httpx`` JSON encoding.
    # ``by_alias=True`` — aliased fields use their wire names
    # (``EmailTaskEmail.from_`` → ``"from"``).
    # ``exclude_none=False`` — keep declared ``None`` defaults so Rails
    # sees consistent shape (``validation: null``, ``retry_rules: null``).
    #
    # This is the **uniform fix across all task types** for the
    # ``NoMethodError: 'reject!' / '[]' for nil:NilClass`` class of
    # failure. Any Rails callback that iterates declared sub-fields
    # without nil-checks (``Email#cast`` on ``cc`` / ``bcc``,
    # ``Notifications::SMS#cast`` on ``numbers``, ``Callout`` inspecting
    # ``validation.status_codes``, …) gets a fully-populated hash
    # because every declared field on every nested ``BaseModel`` is
    # present with either the user-supplied value or the Pydantic
    # default.
    # ``warnings="none"`` — some generated models (e.g. ``Callout.body_type``)
    # declare an enum annotation but carry a plain-string default in the
    # schema. Pydantic emits a cosmetic ``PydanticSerializationUnexpectedValue``
    # on dump; it has no effect on correctness but clutters callers' logs.
    dumped = validated.model_dump(
        mode="json",
        by_alias=True,
        exclude_none=False,
        warnings="none",
    )

    # Targeted post-dump scrub of keys Rails dereferences without a
    # nil-guard (e.g. ``Callout.validation`` → ``callout.rb:719``). The
    # surrounding ``exclude_none=False`` behaviour stays — Rails callbacks
    # like ``Email#cast`` rely on those keys being present-with-null.
    # Only the explicitly-listed fields are dropped.
    _strip_rails_nil_fragile_keys(action_type, dumped)

    if hydrate_defaults:
        # ``add_task`` — mirror ``build_workflow_definition``: every
        # declared top-level and nested field is present on the wire.
        # Replaces the old ``_ENGINE._hydrate_defaults`` call which
        # only reached the top level and missed nested defaults.
        raw = dict(dumped)
    else:
        # ``update_task`` / ``patch_task`` — Rails replaces
        # ``parameters`` wholesale on a PATCH, so adding defaults for
        # fields the user didn't mention would silently reset them.
        # Start from the user-supplied keys only, but pull each nested
        # sub-dict from the dump so Rails' ``before_validation``
        # callbacks see the declared inner defaults
        # (``email.cc=[]`` / ``email.bcc=[]`` / ``email.reply_to=""`` /
        # ``sms.numbers`` being an array / …).
        raw = {}
        rails_nil_fragile = _RAILS_NIL_FRAGILE_PARAMETERS.get(action_type) or frozenset()
        for key, user_val in params.items():
            # Even when the caller explicitly passes ``key: None`` for a
            # Rails-nil-fragile field on a patch, never echo it back —
            # Rails' ``parameters.fetch(key, {}).reverse_merge(...)``
            # would crash. Treat it as "remove this key" instead.
            if key in rails_nil_fragile and user_val is None:
                continue
            dumped_val = dumped.get(key)
            if isinstance(dumped_val, dict) and isinstance(user_val, dict):
                raw[key] = dumped_val
            elif key in dumped:
                # Scalar / list / enum post-validation form — use the
                # dumped value (strings for enums, booleans coerced).
                raw[key] = dumped_val
            else:
                raw[key] = user_val

    # ``_wrap_flat_fields`` re-applies the Suspend/Resume/Cancel/NewProduct
    # /RemoveProduct/InvoiceGenerate/WriteOff wrapper key. ``normalize_task``
    # already does this, so the second pass is a no-op — but keeping it
    # makes the pipeline robust against any caller that bypasses the
    # normalizer (tests, future callers).
    TaskTemplateEngine._wrap_flat_fields(action_type, raw)

    allowed = _ENGINE.allowed_params(action_type) or set()
    filtered: dict[str, Any] = {}
    for key, value in raw.items():
        if key in allowed:
            filtered[key] = TaskTemplateEngine._convert_value(value, _base_type(action_type, key))

    pass_keys = COMMON_PASS_THROUGH
    if action_type in ("Callout", "AsynchronousCallout"):
        pass_keys = pass_keys | CALLOUT_EXTRA_PASS_THROUGH
    for key in pass_keys:
        if key in raw and key not in filtered:
            filtered[key] = TaskTemplateEngine._convert_value(raw[key], None)

    if hydrate_defaults:
        _ENGINE._hydrate_required_fields(action_type, filtered)

    body: dict[str, Any] = {
        "name": name,
        "action_type": action_type,
        "parameters": filtered,
    }
    if object_name is not None:
        body["object"] = object_name
    if object_id is not None:
        body["object_id"] = object_id
    return body, []


def render_validation_errors(errors: list[dict[str, Any]]) -> str:
    """Format a list of validation errors as a markdown bullet list for
    inclusion in an agent error envelope."""
    if not errors:
        return ""
    lines: list[str] = []
    for err in errors:
        path = err.get("path") or "?"
        code = err.get("code") or "VALIDATION_ERROR"
        message = err.get("message") or "(no message)"
        fix_hint = err.get("fix_hint") or ""
        lines.append(f"- **`{path}`** ({code}): {message}")
        if fix_hint:
            lines.append(f"  - _Fix:_ {fix_hint}")
    return "\n".join(lines)
