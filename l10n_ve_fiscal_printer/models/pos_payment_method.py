# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    l10n_ve_fiscal_payment_code = fields.Char(
        string="Fiscal Machine Payment Code",
        default="01",
        help="Payment slot from 01 through 24 in the HKA protocol.",
    )
    l10n_ve_igtf_applies = fields.Boolean(
        string="IGTF Applies",
        compute="_compute_l10n_ve_igtf_applies",
        help=(
            "Technical optional value read from the payment journal when an "
            "installed IGTF addon provides l10n_ve_igtf_applies."
        ),
    )

    @api.depends("journal_id")
    def _compute_l10n_ve_igtf_applies(self):
        journal_has_field = (
            "l10n_ve_igtf_applies" in self.env["account.journal"]._fields
        )
        for payment_method in self:
            payment_method.l10n_ve_igtf_applies = bool(
                journal_has_field
                and payment_method.journal_id
                and payment_method.journal_id.l10n_ve_igtf_applies
            )

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + [
            "l10n_ve_fiscal_payment_code",
            "l10n_ve_igtf_applies",
        ]
