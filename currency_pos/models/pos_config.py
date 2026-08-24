from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = "pos.config"

    allow_multi_currency_payment = fields.Boolean(
        string="Allow Payments in Other Currencies",
        default=False,
        help="Allow payment methods whose journal currency differs from the POS currency.",
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        if not fields_list:
            return fields_list
        if "allow_multi_currency_payment" not in fields_list:
            fields_list.append("allow_multi_currency_payment")
        return fields_list

    @api.constrains(
        "pricelist_id",
        "use_pricelist",
        "available_pricelist_ids",
        "journal_id",
        "invoice_journal_id",
        "payment_method_ids",
        "allow_multi_currency_payment",
    )
    def _check_currencies(self):
        for config in self:
            if (
                config.use_pricelist
                and config.pricelist_id
                and config.pricelist_id not in config.available_pricelist_ids
            ):
                raise ValidationError(
                    _("The default pricelist must be included in the available pricelists.")
                )

            if not config.allow_multi_currency_payment:
                for pm in config.payment_method_ids:
                    if (
                        pm.journal_id
                        and pm.journal_id.currency_id
                        and pm.journal_id.currency_id != config.currency_id
                    ):
                        raise ValidationError(
                            _(
                                "All payment methods must be in the same currency as the Sales "
                                "Journal or the company currency if that is not set."
                            )
                        )

            if (
                config.invoice_journal_id.currency_id
                and config.invoice_journal_id.currency_id != config.currency_id
            ):
                raise ValidationError(
                    _(
                        "The invoice journal must be in the same currency as the Sales Journal"
                        " or the company currency if that is not set."
                    )
                )
