from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = "pos.config"

    l10n_ve_pos_igtf_percent = fields.Float(
        related="company_id.l10n_ve_igtf_percent",
        readonly=False,
        string="IGTF (%)",
    )

    @api.constrains(
        "pricelist_id",
        "use_pricelist",
        "available_pricelist_ids",
        "journal_id",
        "invoice_journal_id",
        "payment_method_ids",
    )
    def _check_currencies(self):
        ve_configs = self.filtered(
            lambda config: config.company_id.account_fiscal_country_id.code == "VE"
        )
        other_configs = self - ve_configs
        result = True
        if other_configs:
            result = super(PosConfig, other_configs)._check_currencies()
        for config in ve_configs:
            if (
                config.use_pricelist
                and config.pricelist_id
                and config.pricelist_id not in config.available_pricelist_ids
            ):
                raise ValidationError(
                    _(
                        "The default pricelist must be included in "
                        "the available pricelists."
                    )
                )
            if (
                config.invoice_journal_id.currency_id
                and config.invoice_journal_id.currency_id != config.currency_id
            ):
                raise ValidationError(
                    _(
                        "The invoice journal must be in the same currency as the "
                        "Sales Journal or the company currency if that is not set."
                    )
                )
        return result
