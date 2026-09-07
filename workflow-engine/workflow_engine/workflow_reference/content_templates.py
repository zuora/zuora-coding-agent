"""Few-shot content examples, default task parameter shapes, and emergency
HTML fallbacks.

Creative content (Email HTML bodies, Callout / AsynchronousCallout JSON
``raw_body`` payloads) is **no longer** authored by selecting a static template.
The main planning LLM only emits a brief (``subject`` / ``intent`` /
``data_vars`` / ``body_brief`` / ``body_vars``) in the plan, and
``build_workflow_definition`` invokes a dedicated creative sub-agent
(``agent.creative_agent``) at build time to render production-quality HTML /
JSON using the few-shot examples below as style guidance.

This module therefore exposes three layers:

* ``FEW_SHOT_EMAIL_EXAMPLES`` and ``FEW_SHOT_CALLOUT_EXAMPLES`` — compact,
  representative style references that are embedded into the creative
  sub-agent's system prompt.  They are examples, not templates to copy
  verbatim.
* ``DEFAULT_CALLOUT_PARAMETERS`` / ``DEFAULT_CALLOUT_RETRY_RULES`` —
  parameter-level defaults the assembler fills in for Callout /
  AsynchronousCallout tasks.  These are structural, not creative, and remain
  deterministic.
* ``LIQUID_TEMPLATES`` — small Liquid snippets (days-overdue, balance-check,
  etc.) used for Logic::Liquid task examples.
* ``wrap_text_in_html_shell`` + ``_looks_like_html`` — emergency-only fallback
  used when the creative sub-agent fails to return usable HTML; the output is
  still a complete, styled HTML document.

Nothing in this module performs template *selection* — that was the rigid
behavior the creative sub-agent replaces.
"""

from __future__ import annotations

from typing import Any

# =============================================================================
# Few-shot EMAIL examples (fed into the creative sub-agent's system prompt).
# =============================================================================

FEW_SHOT_EMAIL_EXAMPLES: dict[str, dict[str, str]] = {
    "overdue_reminder": {
        "description": (
            "Friendly but firm payment reminder for a past-due invoice. "
            "Mentions invoice number, amount, and has a clear CTA."
        ),
        "subject": "Payment Reminder — Invoice #{{Data.Invoice.InvoiceNumber}}",
        "template": (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1.0'></head>"
            "<body style='margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,"
            "Segoe UI,Roboto,Helvetica,Arial,sans-serif;background-color:#f4f4f5;'>"
            "<div style='max-width:600px;margin:0 auto;padding:40px 20px;'>"
            "<div style='background-color:#fff;border-radius:8px;padding:40px;"
            "box-shadow:0 1px 3px rgba(0,0,0,0.1);'>"
            "<h1 style='margin:0 0 24px;font-size:24px;font-weight:600;color:#18181b;'>"
            "Payment Reminder</h1>"
            "<p style='margin:0 0 16px;font-size:16px;line-height:1.6;color:#3f3f46;'>"
            "Dear {{Data.BillToContact.FirstName}},</p>"
            "<p style='margin:0 0 16px;font-size:16px;line-height:1.6;color:#3f3f46;'>"
            "Your invoice #{{Data.Invoice.InvoiceNumber}} for "
            "{{Data.Invoice.Amount}} is past due.</p>"
            "<div style='background-color:#f4f4f5;border-radius:6px;padding:20px;margin:24px 0;'>"
            "<p style='margin:0 0 8px;font-size:14px;color:#71717a;'>Amount Due</p>"
            "<p style='margin:0;font-size:24px;font-weight:600;color:#18181b;'>"
            "{{Data.Invoice.Balance}}</p></div>"
            "<p style='margin:0 0 16px;font-size:16px;line-height:1.6;color:#3f3f46;'>"
            "Please remit payment at your earliest convenience.</p>"
            "</div>"
            "<p style='margin:32px 0 0;font-size:14px;color:#71717a;text-align:center;'>"
            "This is an automated notification.</p></div></body></html>"
        ),
    },
    "payment_confirmation": {
        "description": (
            "Warm confirmation that payment has been received. Uses a success "
            "icon, receipt-style details table, and thank-you close."
        ),
        "subject": "Payment Received — Thank You",
        "template": (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1.0'></head>"
            "<body style='margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,"
            "Segoe UI,Roboto,Helvetica,Arial,sans-serif;background-color:#f4f4f5;'>"
            "<div style='max-width:600px;margin:0 auto;padding:40px 20px;'>"
            "<div style='background-color:#fff;border-radius:8px;padding:40px;"
            "box-shadow:0 1px 3px rgba(0,0,0,0.1);'>"
            "<div style='text-align:center;margin-bottom:24px;'>"
            "<span style='display:inline-block;width:48px;height:48px;"
            "background-color:#dcfce7;border-radius:50%;line-height:48px;"
            "font-size:24px;'>&#10003;</span></div>"
            "<h1 style='margin:0 0 24px;font-size:24px;font-weight:600;color:#18181b;"
            "text-align:center;'>Payment Received</h1>"
            "<p style='margin:0 0 16px;font-size:16px;line-height:1.6;color:#3f3f46;'>"
            "Dear {{Data.BillToContact.FirstName}},</p>"
            "<p style='margin:0 0 16px;font-size:16px;line-height:1.6;color:#3f3f46;'>"
            "We have received your payment of {{Data.Payment.Amount}}. Thank you!</p>"
            "<div style='background-color:#f4f4f5;border-radius:6px;padding:20px;margin:24px 0;'>"
            "<table style='width:100%;'>"
            "<tr><td style='padding:8px 0;color:#71717a;'>Amount</td>"
            "<td style='padding:8px 0;text-align:right;font-weight:600;'>"
            "{{Data.Payment.Amount}}</td></tr>"
            "<tr><td style='padding:8px 0;color:#71717a;'>Date</td>"
            "<td style='padding:8px 0;text-align:right;'>"
            "{{Data.Payment.EffectiveDate}}</td></tr>"
            "<tr><td style='padding:8px 0;color:#71717a;'>Reference</td>"
            "<td style='padding:8px 0;text-align:right;font-family:monospace;'>"
            "{{Data.Payment.ReferenceId}}</td></tr></table></div>"
            "</div>"
            "<p style='margin:32px 0 0;font-size:14px;color:#71717a;text-align:center;'>"
            "This is your payment confirmation.</p></div></body></html>"
        ),
    },
    "suspension_notice": {
        "description": (
            "Urgent suspension notice. Uses a red-banner callout, outstanding "
            "balance, clear action-required framing."
        ),
        "subject": "Service Suspension Notice — Action Required",
        "template": (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1.0'></head>"
            "<body style='margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,"
            "Segoe UI,Roboto,Helvetica,Arial,sans-serif;background-color:#f4f4f5;'>"
            "<div style='max-width:600px;margin:0 auto;padding:40px 20px;'>"
            "<div style='background-color:#fff;border-radius:8px;padding:40px;"
            "box-shadow:0 1px 3px rgba(0,0,0,0.1);'>"
            "<div style='background-color:#fee2e2;border-left:4px solid #dc2626;"
            "padding:16px;margin:0 0 24px 0;border-radius:0 6px 6px 0;'>"
            "<p style='margin:0;font-size:14px;color:#991b1b;font-weight:500;'>"
            "Action Required</p></div>"
            "<h1 style='margin:0 0 24px;font-size:24px;font-weight:600;color:#18181b;'>"
            "Service Suspension Notice</h1>"
            "<p style='margin:0 0 16px;font-size:16px;line-height:1.6;color:#3f3f46;'>"
            "Dear {{Data.BillToContact.FirstName}},</p>"
            "<p style='margin:0 0 16px;font-size:16px;line-height:1.6;color:#3f3f46;'>"
            "Your subscription {{Data.Subscription.Name}} has been suspended "
            "due to non-payment.</p>"
            "<p style='margin:0 0 16px;font-size:16px;line-height:1.6;color:#3f3f46;'>"
            "Outstanding balance: <strong>{{Data.Account.Balance}}</strong></p>"
            "<p style='margin:0 0 16px;font-size:16px;line-height:1.6;color:#3f3f46;'>"
            "To restore service, please remit payment or contact our billing department.</p>"
            "</div>"
            "<p style='margin:32px 0 0;font-size:14px;color:#71717a;text-align:center;'>"
            "Questions? Contact our support team.</p></div></body></html>"
        ),
    },
    "welcome_notification": {
        "description": (
            "Friendly welcome after a new subscription is activated. Warm tone, "
            "positive highlight callout, light typography."
        ),
        "subject": "Welcome! Your subscription is active",
        "template": (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1.0'></head>"
            "<body style='margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,"
            "Segoe UI,Roboto,Helvetica,Arial,sans-serif;background-color:#f4f4f5;'>"
            "<div style='max-width:600px;margin:0 auto;padding:40px 20px;'>"
            "<div style='background-color:#fff;border-radius:8px;padding:40px;"
            "box-shadow:0 1px 3px rgba(0,0,0,0.1);'>"
            "<h1 style='margin:0 0 24px;font-size:24px;font-weight:600;color:#18181b;'>"
            "Welcome!</h1>"
            "<p style='margin:0 0 16px;font-size:16px;line-height:1.6;color:#3f3f46;'>"
            "Dear {{Data.BillToContact.FirstName}},</p>"
            "<p style='margin:0 0 16px;font-size:16px;line-height:1.6;color:#3f3f46;'>"
            "Thank you for subscribing to {{Data.Subscription.Name}}. "
            "Your subscription is now active and ready to use!</p>"
            "<div style='background-color:#dbeafe;border-left:4px solid #2563eb;"
            "padding:16px;margin:24px 0;border-radius:0 6px 6px 0;'>"
            "<p style='margin:0;font-size:14px;color:#1e40af;'>"
            "Your subscription is now active.</p></div>"
            "</div>"
            "<p style='margin:32px 0 0;font-size:14px;color:#71717a;text-align:center;'>"
            "Questions? Reply to this email or contact our support team.</p>"
            "</div></body></html>"
        ),
    },
}


# =============================================================================
# Few-shot CALLOUT examples (fed into the creative sub-agent's system prompt).
# =============================================================================

FEW_SHOT_CALLOUT_EXAMPLES: dict[str, dict[str, str]] = {
    "webhook_invoice": {
        "description": (
            "Simple webhook notifying an external system that an invoice event "
            "occurred. Flat payload keyed by invoice fields, ISO timestamp."
        ),
        "raw_body": (
            "{\n"
            '  "event": "invoice.{{event_type}}",\n'
            '  "timestamp": "{{ "now" | date: "%Y-%m-%dT%H:%M:%SZ" }}",\n'
            '  "invoice": {\n'
            '    "id": "{{Data.Invoice.Id}}",\n'
            '    "number": "{{Data.Invoice.InvoiceNumber}}",\n'
            '    "amount": {{Data.Invoice.Amount}},\n'
            '    "balance": {{Data.Invoice.Balance}},\n'
            '    "status": "{{Data.Invoice.Status}}",\n'
            '    "dueDate": "{{Data.Invoice.DueDate}}",\n'
            '    "accountId": "{{Data.Account.Id}}"\n'
            "  }\n"
            "}"
        ),
    },
    "webhook_invoice_with_items": {
        "description": (
            "Webhook with a nested line-items collection iterated via Liquid "
            "``{% for item in Data.InvoiceItem %}``."
        ),
        "raw_body": (
            "{\n"
            '  "event": "invoice.{{event_type}}",\n'
            '  "timestamp": "{{ "now" | date: "%Y-%m-%dT%H:%M:%SZ" }}",\n'
            '  "invoice": {\n'
            '    "id": "{{Data.Invoice.Id}}",\n'
            '    "number": "{{Data.Invoice.InvoiceNumber}}",\n'
            '    "invoiceItems": [\n'
            "      {% for item in Data.InvoiceItem %}\n"
            "      {\n"
            '        "id": "{{item.Id}}",\n'
            '        "productName": "{{item.ProductName}}",\n'
            '        "amount": {{item.ChargeAmount}}\n'
            "      }{% unless forloop.last %},{% endunless %}\n"
            "      {% endfor %}\n"
            "    ]\n"
            "  }\n"
            "}"
        ),
    },
    "slack_notification": {
        "description": (
            "Slack webhook message with channel, username, icon, text and a "
            "Slack attachment with fields."
        ),
        "raw_body": (
            "{\n"
            '  "channel": "{{channel}}",\n'
            '  "username": "Zuora Workflow",\n'
            '  "icon_emoji": ":zuora:",\n'
            '  "text": "{{message}}",\n'
            '  "attachments": [\n'
            "    {\n"
            '      "color": "{{color}}",\n'
            '      "fields": [\n'
            '        {"title": "Account", "value": "{{Data.Account.Name}}", "short": true},\n'
            '        {"title": "Amount", "value": "{{Data.Invoice.Balance | money}}", "short": true}\n'
            "      ]\n"
            "    }\n"
            "  ]\n"
            "}"
        ),
    },
    "zuora_cancel_subscription": {
        "description": (
            "Callout into the Zuora Orders API to cancel a subscription at the "
            "end of the current term. Shows a nested order-action payload."
        ),
        "raw_body": (
            "{\n"
            '  "orderDate": "{{ "now" | date: "%Y-%m-%d" }}",\n'
            '  "existingAccountNumber": "{{Data.Account.AccountNumber}}",\n'
            '  "subscriptions": [\n'
            "    {\n"
            '      "subscriptionNumber": "{{Data.Subscription.SubscriptionNumber}}",\n'
            '      "orderActions": [\n'
            "        {\n"
            '          "type": "CancelSubscription",\n'
            '          "cancelSubscription": {\n'
            '            "cancellationPolicy": "EndOfCurrentTerm"\n'
            "          }\n"
            "        }\n"
            "      ]\n"
            "    }\n"
            "  ],\n"
            '  "processingOptions": {\n'
            '    "runBilling": true,\n'
            '    "collectPayment": true\n'
            "  }\n"
            "}"
        ),
    },
}


# =============================================================================
# Liquid snippets (Logic::Liquid task building blocks).
# =============================================================================

LIQUID_TEMPLATES: dict[str, str] = {
    "days_overdue": (
        '{% assign now_unix = "now" | date: "%s" %}'
        '{% assign due_unix = Data.Invoice.DueDate | date: "%s" %}'
        "{% assign diff_seconds = now_unix | minus: due_unix %}"
        "{% assign Data.DaysPastDue = diff_seconds | divided_by: 86400 %}"
    ),
    "days_until": (
        '{% assign now_unix = "now" | date: "%s" %}'
        '{% assign target_unix = {{target_date}} | date: "%s" %}'
        "{% assign diff_seconds = target_unix | minus: now_unix %}"
        "{% assign {{output_var}} = diff_seconds | divided_by: 86400 %}"
    ),
    "amount_formatting": "{% assign {{output_var}} = {{amount_field}} | money %}",
    "percentage_calculation": (
        "{% assign {{output_var}} = {{numerator}} | times: 100.0 "
        "| divided_by: {{denominator}} | round: 2 %}"
    ),
    "string_concatenation": (
        "{% capture {{output_var}} %}{{value1}}{{separator}}{{value2}}{% endcapture %}"
    ),
    "conditional_value": (
        "{% if {{condition}} %}{% assign {{output_var}} = {{true_value}} %}"
        "{% else %}{% assign {{output_var}} = {{false_value}} %}{% endif %}"
    ),
    "array_first": "{% assign {{output_var}} = {{array_field}} | first %}",
    "array_size": "{% assign {{output_var}} = {{array_field}} | size %}",
    "date_format": '{% assign {{output_var}} = {{date_field}} | date: "{{format}}" %}',
    "escalation_level": (
        '{% if Data.DaysPastDue > 60 %}{% assign Data.EscalationLevel = "critical" %}'
        '{% elsif Data.DaysPastDue > 30 %}{% assign Data.EscalationLevel = "high" %}'
        '{% elsif Data.DaysPastDue > 14 %}{% assign Data.EscalationLevel = "medium" %}'
        '{% else %}{% assign Data.EscalationLevel = "low" %}{% endif %}'
    ),
    "balance_check": (
        "{% assign Data.HasBalance = false %}"
        "{% if Data.Invoice.Balance > 0 %}{% assign Data.HasBalance = true %}{% endif %}"
    ),
    "contact_preference": (
        "{% assign Data.ContactEmail = Data.Account.BillToContact.WorkEmail %}"
        "{% if Data.ContactEmail == blank %}"
        "{% assign Data.ContactEmail = Data.Account.SoldToContact.WorkEmail %}"
        "{% endif %}"
    ),
}


# =============================================================================
# Callout structural defaults (unchanged — still used by the assembler).
# =============================================================================

DEFAULT_CALLOUT_RETRY_RULES: dict[str, str] = {
    "retry_count": "0",
    "retry_window": "30",
}

DEFAULT_CALLOUT_PARAMETERS: dict[str, Any] = {
    "url": "",
    "method": "post",
    "headers": [{"key": "Content-Type", "value": "application/json"}],
    "api_name": "",
    "raw_body": "",
    "body_type": "raw",
    "form_datas": [{"key": "", "value": "", "upload": "false"}],
    "files": [],
    "validation": {
        "replace": "false",
        "zuora_call": "false",
        "status_codes": ["200", "201", "204"],
        "payload_location": "Callout",
    },
    "api_doc_url": "",
    "retry_rules": {"retry_count": "0", "retry_window": "30", "current_retry_count": "0"},
    "authorization": {"type": "none"},
    "finish_status": [""],
    "response_path": "",
    "polling_interval": "30",
    "strict_variables": "true",
    "validate_response": "false",
    "validation_scheme": "",
    "disable_validation": "false",
    "delete_payload_paths": [],
    "include_response_code": "true",
    "notification_history_enabled": "false",
}


# =============================================================================
# Emergency HTML-shell fallback.
# Used ONLY when the creative sub-agent fails to return usable HTML so the
# assembled workflow is still valid.
# =============================================================================

_HTML_MARKERS: tuple[str, ...] = (
    "<!doctype html",
    "<html",
    "<body",
    "<div",
    "<p ",
    "<p>",
    "<table",
    "<h1",
    "<h2",
    "<h3",
    "<br",
    "<a ",
    "<span",
)


def _looks_like_html(value: str) -> bool:
    """Return True when ``value`` already contains real HTML markup."""
    if not value:
        return False
    lowered = value.lower()
    return any(marker in lowered for marker in _HTML_MARKERS)


_INLINE_EMAIL_BODY_STYLE = (
    "margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,"
    "Segoe UI,Roboto,Helvetica,Arial,sans-serif;background-color:#f4f4f5;"
)
_INLINE_EMAIL_CONTAINER_STYLE = "max-width:600px;margin:0 auto;padding:40px 20px;"
_INLINE_EMAIL_CARD_STYLE = (
    "background-color:#ffffff;border-radius:8px;padding:40px;"
    "box-shadow:0 1px 3px rgba(0,0,0,0.1);"
)
_INLINE_EMAIL_PARAGRAPH_STYLE = "margin:0 0 16px;font-size:16px;line-height:1.6;color:#3f3f46;"
_INLINE_EMAIL_FOOTER_STYLE = "margin:32px 0 0;font-size:14px;color:#71717a;text-align:center;"


def wrap_text_in_html_shell(
    text: str,
    subject: str = "Notification",
    workflow_name: str = "",
) -> str:
    """Wrap a plain-text body / brief in a professional responsive HTML shell.

    Preserves Liquid expressions (``{{ ... }}`` / ``{% ... %}``) untouched
    and converts paragraph-style line breaks into ``<p>`` tags.  Returns a
    complete HTML document ready for the Zuora Email task ``template`` field.
    Emergency fallback only — the creative sub-agent should normally produce
    the final HTML.
    """
    paragraphs: list[str] = []
    for raw in (text or "").strip().split("\n\n"):
        chunk = raw.strip().replace("\n", "<br>")
        if chunk:
            paragraphs.append(f"<p style='{_INLINE_EMAIL_PARAGRAPH_STYLE}'>{chunk}</p>")
    if not paragraphs:
        paragraphs.append(
            f"<p style='{_INLINE_EMAIL_PARAGRAPH_STYLE}'>"
            f"This is an automated notification from {workflow_name or 'Zuora Workflows'}."
            "</p>"
        )
    header = (
        subject.strip()
        if subject and subject != "Notification"
        else (workflow_name.strip() or "Notification")
    )
    return (
        "<!DOCTYPE html>"
        "<html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        f"<title>{header}</title>"
        "</head>"
        f"<body style='{_INLINE_EMAIL_BODY_STYLE}'>"
        f"<div style='{_INLINE_EMAIL_CONTAINER_STYLE}'>"
        f"<div style='{_INLINE_EMAIL_CARD_STYLE}'>"
        f"<h1 style='margin:0 0 24px;font-size:24px;font-weight:600;color:#18181b;'>"
        f"{header}</h1>" + "".join(paragraphs) + "</div>"
        f"<p style='{_INLINE_EMAIL_FOOTER_STYLE}'>"
        "This is an automated notification.</p>"
        "</div></body></html>"
    )


__all__ = [
    "FEW_SHOT_EMAIL_EXAMPLES",
    "FEW_SHOT_CALLOUT_EXAMPLES",
    "LIQUID_TEMPLATES",
    "DEFAULT_CALLOUT_PARAMETERS",
    "DEFAULT_CALLOUT_RETRY_RULES",
    "_looks_like_html",
    "wrap_text_in_html_shell",
]
