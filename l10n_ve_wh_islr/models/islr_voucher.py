# Copyright 2026 BWEALTHICS LLC
# Part of l10n_ve_wh_islr. License LGPL-3.

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from .islr_concept import PERSON_TYPES


class L10nVeIslrVoucher(models.Model):
    _name = "l10n.ve.islr.voucher"
    _description = "Comprobante de Retención de ISLR (art. 24, Decreto 1.808)"
    _order = "date desc, number desc"
    _rec_name = "number"
    _check_company_auto = True

    number = fields.Char(string="Número", readonly=True, copy=False, default="/")
    date = fields.Date(string="Fecha", required=True, default=fields.Date.context_today)
    period = fields.Char(
        string="Período", compute="_compute_period", store=True, index=True
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    partner_id = fields.Many2one("res.partner", string="Sujeto Retenido", required=True)
    payment_id = fields.Many2one(
        "account.payment", string="Pago", copy=False, check_company=True
    )
    move_ids = fields.Many2many(
        "account.move",
        string="Facturas Afectadas",
        domain="[('move_type', 'in', ('in_invoice', 'in_refund', 'in_receipt'))]",
        check_company=True,
    )
    concept_id = fields.Many2one(
        "l10n.ve.islr.concept", string="Concepto ISLR", required=True
    )
    person_type = fields.Selection(
        PERSON_TYPES,
        string="Tipo de Persona",
        required=True,
        default="pj_dom",
    )
    base = fields.Monetary(currency_field="currency_id")
    rate = fields.Float(string="Tarifa (%)", digits=(5, 2))
    subtrahend = fields.Monetary(string="Sustraendo", currency_field="currency_id")
    # amount = 0 is allowed by the SENIAT XML completeness rule.
    amount = fields.Monetary(string="Monto Retenido", currency_field="currency_id")
    state = fields.Selection(
        [("draft", "Borrador"), ("issued", "Emitido"), ("cancelled", "Anulado")],
        string="Estado",
        default="draft",
        copy=False,
    )
    company_vat = fields.Char(string="RIF del Agente", related="company_id.vat")
    partner_vat = fields.Char(string="RIF del Retenido", related="partner_id.vat")

    @api.depends("date")
    def _compute_period(self):
        for voucher in self:
            voucher.period = voucher.date and voucher.date.strftime("%Y%m") or False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("number") or vals["number"] == "/":
                seq_date = fields.Date.to_date(
                    vals.get("date")
                ) or fields.Date.context_today(self)
                company = (
                    self.env["res.company"].browse(vals["company_id"])
                    if vals.get("company_id")
                    else self.env.company
                )
                sequence = self._l10n_ve_islr_get_sequence(company)
                self._l10n_ve_islr_ensure_month_range(sequence, seq_date)
                vals["number"] = sequence.next_by_id(sequence_date=seq_date)
        return super().create(vals_list)

    @api.model
    def _l10n_ve_islr_get_sequence(self, company):
        """Get or create the voucher sequence for the withholding company."""
        sequence = (
            self.env["ir.sequence"]
            .sudo()
            .search(
                [
                    ("code", "=", "l10n.ve.islr.voucher"),
                    ("company_id", "=", company.id),
                ],
                limit=1,
            )
        )
        if not sequence:
            sequence = (
                self.env["ir.sequence"]
                .sudo()
                .create(
                    {
                        "name": self.env._(
                            "Comprobante de Retención ISLR (%s)", company.name
                        ),
                        "code": "l10n.ve.islr.voucher",
                        "prefix": "%(year)s%(month)s",
                        "padding": 8,
                        "implementation": "no_gap",
                        "use_date_range": True,
                        "company_id": company.id,
                    }
                )
            )
        return sequence

    @api.model
    def _l10n_ve_islr_ensure_month_range(self, sequence, seq_date):
        """Create an explicit monthly range so the sequence resets monthly."""
        date_range_model = self.env["ir.sequence.date_range"].sudo()
        if not date_range_model.search_count(
            [
                ("sequence_id", "=", sequence.id),
                ("date_from", "<=", seq_date),
                ("date_to", ">=", seq_date),
            ],
            limit=1,
        ):
            start = seq_date.replace(day=1)
            date_range_model.create(
                {
                    "sequence_id": sequence.id,
                    "date_from": start,
                    "date_to": start + relativedelta(months=1, days=-1),
                }
            )

    @api.ondelete(at_uninstall=False)
    def _unlink_except_issued(self):
        if any(voucher.state == "issued" for voucher in self):
            raise UserError(
                self.env._(
                    "No se puede eliminar un comprobante emitido: anúlelo primero."
                )
            )

    def action_issue(self):
        self.write({"state": "issued"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_draft(self):
        self.write({"state": "draft"})
