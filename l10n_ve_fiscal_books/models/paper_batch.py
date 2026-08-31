# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

NUMBER_RE = re.compile(r"^(.*?)(\d+)$")
LOW_PAPER_THRESHOLD = 10


class L10nVePaperBatch(models.Model):
    """Preprinted fiscal paper supplied by an authorized printer."""

    _name = "l10n.ve.paper.batch"
    _description = "Venezuelan Preprinted Fiscal Paper"
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(compute="_compute_name", store=True)
    type = fields.Selection(
        [
            ("talonario", "Contingency booklet"),
            ("forma_libre", "Free forms"),
        ],
        string="Paper Type",
        required=True,
        default="talonario",
        help="A contingency booklet has preprinted invoice and control numbers. "
        "Free-form paper has only a preprinted control number.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    active = fields.Boolean(default=True)
    printer_name = fields.Char(
        string="Authorized Printer",
        help="Legal name of the authorized printer shown on each form.",
    )
    printer_vat = fields.Char(string="Printer Tax ID")
    printer_authorization = fields.Char(
        string="Printer Authorization Number",
        help="Authorization number printed on each form.",
    )
    control_from = fields.Char(
        string="Control Number From", required=True, default="000001"
    )
    control_to = fields.Char(
        string="Control Number To",
        help="Last control number in the batch. Leave empty for an open range.",
    )
    invoice_from = fields.Char(
        string="Invoice Number From",
        default="000001",
        help="First preprinted invoice number for contingency booklets. Free-form "
        "invoice numbers are assigned by the journal sequence.",
    )
    invoice_to = fields.Char(string="Invoice Number To")

    @api.depends("type", "control_from", "control_to", "printer_name")
    def _compute_name(self):
        for batch in self:
            label = "Talonario" if batch.type == "talonario" else "Formas libres"
            control = f"{batch.control_from or '?'}-{batch.control_to or '...'}"
            name = f"{label} control {control}"
            if batch.printer_name:
                name += f" ({batch.printer_name})"
            batch.name = name

    @staticmethod
    def _split(value):
        """Return prefix, numeric tail, and width for a formatted number."""
        match = NUMBER_RE.match((value or "").strip())
        if not match:
            return None
        prefix, digits = match.groups()
        return prefix, int(digits), len(digits)

    @api.constrains("type", "control_from", "control_to", "invoice_from", "invoice_to")
    def _check_ranges(self):
        for batch in self:
            kinds = [("control", batch.control_from, batch.control_to)]
            if batch.type == "talonario":
                if not batch.invoice_from:
                    raise ValidationError(
                        self.env._(
                            "A contingency booklet has a preprinted invoice number; "
                            "set 'Invoice Number From'."
                        )
                    )
                kinds.append(("invoice", batch.invoice_from, batch.invoice_to))
            for label, start, end in kinds:
                start_parts = self._split(start)
                if not start_parts:
                    raise ValidationError(
                        self.env._(
                            "The initial %(label)s number '%(value)s' must end in "
                            "digits, for example 000001 or 00-000001.",
                            label=label,
                            value=start or "",
                        )
                    )
                if end:
                    end_parts = self._split(end)
                    if not end_parts or end_parts[0] != start_parts[0]:
                        raise ValidationError(
                            self.env._(
                                "The %(label)s number range must use the same prefix "
                                "('%(start)s' and '%(end)s').",
                                label=label,
                                start=start,
                                end=end,
                            )
                        )
                    if end_parts[1] < start_parts[1]:
                        raise ValidationError(
                            self.env._(
                                "The %(label)s number range is reversed "
                                "('%(start)s' > '%(end)s').",
                                label=label,
                                start=start,
                                end=end,
                            )
                        )

    def _used_numbers(self, kind):
        """Return numeric tails already used within this batch's format."""
        self.ensure_one()
        if kind == "control":
            move_field = "l10n_ve_control_number"
            order_field = "l10n_ve_contingency_control"
            start = self.control_from
        else:
            move_field = "l10n_ve_paper_number"
            order_field = "l10n_ve_contingency_invoice_number"
            start = self.invoice_from
        prefix, _number, _width = self._split(start)
        move_domain = [
            ("company_id", "=", self.company_id.id),
            ("move_type", "in", ("out_invoice", "out_refund")),
            "|",
            ("l10n_ve_emission_medium", "in", ("contingency", "free")),
            "&",
            ("state", "=", "draft"),
            ("journal_id.l10n_ve_emission_medium", "in", ("contingency", "free")),
            (move_field, "!=", False),
        ]
        order_domain = [
            ("company_id", "=", self.company_id.id),
            (order_field, "!=", False),
        ]
        if prefix:
            move_domain.append((move_field, "=like", prefix + "%"))
            order_domain.append((order_field, "=like", prefix + "%"))
        values = self.env["account.move"].sudo().search(move_domain).mapped(move_field)
        values += self.env["pos.order"].sudo().search(order_domain).mapped(order_field)
        used = set()
        for value in values:
            parts = self._split(value)
            if parts and parts[0] == prefix:
                used.add(parts[1])
        return used

    def _next_number(self, kind):
        """Return the next formatted number and remaining available numbers."""
        self.ensure_one()
        start = self.control_from if kind == "control" else self.invoice_from
        end = self.control_to if kind == "control" else self.invoice_to
        prefix, first, width = self._split(start)
        last = self._split(end)[1] if end else None
        used = {
            number
            for number in self._used_numbers(kind)
            if number >= first and (last is None or number <= last)
        }
        next_number = max(used) + 1 if used else first
        if last is not None and next_number > last:
            return False, 0
        remaining = None if last is None else last - next_number + 1
        return f"{prefix}{next_number:0{width}d}", remaining

    def next_numbers(self):
        """Return the next control and invoice numbers for POS contingency use."""
        self.ensure_one()
        control, control_left = self._next_number("control")
        if not control:
            return {
                "error": self.env._(
                    "Batch '%(batch)s' has no control numbers left. Register the "
                    "next paper batch in Accounting > Configuration > Venezuelan "
                    "Fiscal Paper.",
                    batch=self.display_name,
                )
            }
        result = {
            "type": self.type,
            "control": control,
            "invoice": False,
            "warning": False,
        }
        remaining = [control_left]
        if self.type == "talonario":
            invoice, invoice_left = self._next_number("invoice")
            if not invoice:
                return {
                    "error": self.env._(
                        "Batch '%(batch)s' has no invoice numbers left. Register "
                        "the next booklet in Accounting > Configuration > "
                        "Venezuelan Fiscal Paper.",
                        batch=self.display_name,
                    )
                }
            result["invoice"] = invoice
            remaining.append(invoice_left)
        low_counts = [count for count in remaining if count is not None]
        if low_counts and min(low_counts) <= LOW_PAPER_THRESHOLD:
            result["warning"] = self.env._(
                "Only %(count)s forms remain in this batch. Order the next batch "
                "from the authorized printer.",
                count=min(low_counts),
            )
        return result

    def check_numbers(self, invoice_number, control_number):
        """Validate entered numbers against the batch range and prior use."""
        self.ensure_one()
        checks = [("control", control_number, self.control_from, self.control_to)]
        if self.type == "talonario":
            checks.append(
                ("invoice", invoice_number, self.invoice_from, self.invoice_to)
            )
        for kind_label, value, start, end in checks:
            kind = "control" if kind_label == "control" else "invoice"
            parts = self._split(value)
            expected_prefix, first, _width = self._split(start)
            if not parts or parts[0] != expected_prefix:
                return self.env._(
                    "The %(kind)s number '%(value)s' does not match the batch "
                    "format, for example %(sample)s.",
                    kind=kind_label,
                    value=value or "",
                    sample=start,
                )
            number = parts[1]
            last = self._split(end)[1] if end else None
            if number < first or (last is not None and number > last):
                return self.env._(
                    "The %(kind)s number '%(value)s' is outside the batch range "
                    "(%(start)s-%(end)s).",
                    kind=kind_label,
                    value=value,
                    start=start,
                    end=end or "...",
                )
            if number in self._used_numbers(kind):
                return self.env._(
                    "The %(kind)s number '%(value)s' is already used by another "
                    "document.",
                    kind=kind_label,
                    value=value,
                )
        return False
