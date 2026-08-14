# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    l10n_ve_fiscal_payment_code = fields.Char(
        string="Fiscal payment code",
        compute="_compute_l10n_ve_fiscal_payment_code",
    )

    @api.depends(
        "journal_id.l10n_ve_fiscal_payment_code",
        "journal_id.inbound_payment_method_line_ids."
        "l10n_ve_fiscal_payment_method_id.code",
        "journal_id.outbound_payment_method_line_ids."
        "l10n_ve_fiscal_payment_method_id.code",
    )
    def _compute_l10n_ve_fiscal_payment_code(self):
        for method in self:
            code = False
            journal = method.journal_id
            if journal:
                for line in (
                    journal.inbound_payment_method_line_ids
                    | journal.outbound_payment_method_line_ids
                ):
                    fiscal_method = line.l10n_ve_fiscal_payment_method_id
                    if fiscal_method and fiscal_method.code:
                        code = fiscal_method.code
                        break
                if not code:
                    code = journal.l10n_ve_fiscal_payment_code or False
            method.l10n_ve_fiscal_payment_code = code

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        for field_name in ("journal_id", "l10n_ve_fiscal_payment_code", "is_cash_count"):
            if field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list
