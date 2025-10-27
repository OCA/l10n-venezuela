from datetime import datetime
import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import format_date

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    reception_date = fields.Date(
        "Reception Date",
        help="Indicates when the invoice was received by the client/company",
        tracking=True,
    )
    l10n_ve_invoice_date = fields.Datetime("Invoice Datetime", readonly=True)

    def button_cancel(self):
        self = self.with_context(force_draft=True)
        return super(AccountMove, self).button_cancel()

    def button_draft(self):
        if self.country_code != self.env.ref("base.ve").code:
            return super().button_draft()

        if self.env.context.get("force_draft"):
            return super().button_draft()

        _logger.info("Button draft called on move %s", self.move_type)
        if self.move_type == "entry":
            return super().button_draft()

        raise ValidationError(
            """You cannot reset to draft an invoice in the Venezuelan localization.
Please create a credit note instead.
        """
        )

    def _post(self, soft=True):
        res = super()._post(soft=soft)
        for rec in self:
            if rec.state == "posted":
                rec.l10n_ve_invoice_date = fields.Datetime.now()
        return res


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    subtotal_company_currency = fields.Monetary(
        compute="_compute_subtotal_company_currency",
        string="Subtotal Company Currency",
        currency_field="company_currency_id",
    )

    @api.depends("balance")
    def _compute_subtotal_company_currency(self):
        for line in self:
            if line.move_id.move_type in ["out_invoice", "in_invoice"]:
                line.subtotal_company_currency = -line.balance
                continue
            if line.move_id.move_type in ["out_refund", "in_refund"]:
                line.subtotal_company_currency = line.balance
                continue
            line.subtotal_company_currency = 0.0
