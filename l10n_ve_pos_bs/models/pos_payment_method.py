# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    l10n_ve_ves_tender = fields.Boolean(
        string="Payment in Bolivars",
        help="Capture the exact VES amount received while keeping the payment "
        "amount in the POS currency.",
    )
    l10n_ve_require_reference = fields.Boolean(
        string="Require Transaction Reference",
        help="Require the bank or card transaction reference before validating "
        "the POS order.",
    )

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + [
            "l10n_ve_ves_tender",
            "l10n_ve_require_reference",
        ]

    @api.constrains(
        "company_id",
        "config_ids",
        "journal_id",
        "l10n_ve_require_reference",
        "l10n_ve_ves_tender",
    )
    def _check_l10n_ve_ves_tender(self):
        ves = self.env.ref("base.VES")
        for payment_method in self:
            if (
                payment_method.l10n_ve_require_reference
                and not payment_method.l10n_ve_ves_tender
            ):
                raise ValidationError(
                    self.env._(
                        "A transaction reference can only be required for a VES tender."
                    )
                )
            if payment_method.l10n_ve_ves_tender and payment_method.type != "bank":
                raise ValidationError(
                    self.env._("VES tenders must use a bank journal.")
                )
            if payment_method.l10n_ve_ves_tender and (
                payment_method.company_id.currency_id == ves
                or ves in payment_method.config_ids.currency_id
            ):
                raise ValidationError(
                    self.env._(
                        "VES tender tracking requires both the company and POS to use "
                        "a currency other than VES."
                    )
                )
