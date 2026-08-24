import base64
import json
import re

from odoo import api, fields, models

STATE_NOT_SENT = "not_sent"
STATE_QUEUED = "queued"
STATE_SENT = "sent"
STATE_FAILED = "failed"


class L10nVeEdiMixin(models.AbstractModel):
    _name = "l10n_ve.edi.mixin"
    _description = "Venezuela digital invoicing tracking mixin"

    l10n_ve_edi_show_tab = fields.Boolean(
        compute="_compute_l10n_ve_edi_show_tab",
        string="Show EDI Tab",
    )
    l10n_ve_edi_send_state = fields.Selection(
        selection=[
            (STATE_NOT_SENT, "Not Sent"),
            (STATE_QUEUED, "Queued"),
            (STATE_SENT, "Sent"),
            (STATE_FAILED, "Failed"),
        ],
        default=STATE_NOT_SENT,
        copy=False,
        readonly=True,
        string="EDI Send State",
    )
    l10n_ve_edi_sent_at = fields.Datetime(
        copy=False, readonly=True, string="EDI Sent At"
    )
    l10n_ve_edi_payload_attachment_id = fields.Many2one(
        "ir.attachment",
        copy=False,
        readonly=True,
        string="EDI Payload Attachment",
    )
    l10n_ve_edi_payload_debug_json = fields.Text(
        compute="_compute_l10n_ve_edi_payload_debug_json",
        string="EDI Payload JSON",
    )
    l10n_ve_edi_last_error = fields.Text(
        copy=False, readonly=True, string="EDI Last Error"
    )
    l10n_ve_edi_response_json = fields.Text(
        copy=False, readonly=True, string="EDI Response JSON"
    )

    l10n_ve_edi_journal_id = fields.Many2one(
        "account.journal",
        compute="_compute_l10n_ve_edi_journal_id",
        string="EDI Journal",
    )

    @api.depends()
    def _compute_l10n_ve_edi_journal_id(self):
        for record in self:
            record.l10n_ve_edi_journal_id = record._l10n_ve_edi_get_edi_journal()

    def _l10n_ve_edi_get_edi_journal(self):
        self.ensure_one()
        if "journal_id" in self._fields and self.journal_id:
            return self.journal_id
        return self.env["account.journal"]

    def _l10n_ve_edi_compute_show_tab(self):
        self.ensure_one()
        journal = self._l10n_ve_edi_get_edi_journal()
        provider = journal.l10n_ve_edi_provider if journal else False
        return bool(provider and provider != "none")

    @api.depends()
    def _compute_l10n_ve_edi_show_tab(self):
        for record in self:
            record.l10n_ve_edi_show_tab = record._l10n_ve_edi_compute_show_tab()

    @api.depends("l10n_ve_edi_payload_attachment_id")
    def _compute_l10n_ve_edi_payload_debug_json(self):
        for record in self:
            record.l10n_ve_edi_payload_debug_json = False
            attachment = record.l10n_ve_edi_payload_attachment_id
            if not attachment or not attachment.datas:
                continue
            try:
                raw = base64.b64decode(attachment.datas)
                payload = json.loads(raw.decode("utf-8"))
                record.l10n_ve_edi_payload_debug_json = json.dumps(
                    payload, ensure_ascii=False, indent=2
                )
            except Exception:
                record.l10n_ve_edi_payload_debug_json = False

    def _l10n_ve_edi_parse_ve_vat(self, vat):
        clean = (vat or "").upper().strip()
        if not clean:
            return "", ""
        clean = re.sub(r"^RIF\s*", "", clean)
        match = re.match(r"^([VEJPGC])[-\s]?(.*)$", clean)
        if match:
            prefix = match.group(1)
            raw_number = (match.group(2) or "").strip()
            number = re.sub(r"[^0-9A-Z\-]", "", raw_number)
            return prefix, number
        compact = re.sub(r"[\s\._/]", "", clean)
        prefix_match = re.search(r"[VEJPGC]", compact)
        prefix = prefix_match.group(0) if prefix_match else ""
        number = re.sub(
            r"[^0-9A-Z\-]", "", compact[len(prefix) :] if prefix else compact
        )
        return prefix, number

    def _l10n_ve_edi_format_decimal(self, amount):
        return f"{abs(amount or 0.0):.2f}"
